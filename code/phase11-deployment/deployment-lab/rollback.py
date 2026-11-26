"""L97: local rollback evidence from successive workers and closed SQLite stores."""

import argparse
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import canary
from host import audit
from transport import StartupRefused, Worker

SUBJECT = ("support", "mei")
ACTION = "save_local_draft"
STORE_FILES = ("business.sqlite", "review.sqlite")
DRAFTS = {
    "export": ["需人工确认：导出保留期", "导出文件生成后保留 7 天。 超过保留期需重新发起导出。", ["KB-01", "KB-02"]],
    "sync": ["需人工确认：同步时间", "同步任务每天 02:00 运行。", ["KB-03"]],
}


def _expect(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, observed {actual!r}")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stage(dispatch, job, topic="export", revision=1):
    reply = dispatch("stage", job=job, revision=revision, topic=topic)
    binding = reply["binding"]
    _result(f"{job} stage", reply, "pending", draft=DRAFTS[topic], read_calls=len(DRAFTS[topic][-1]), binding=binding)
    _expect(f"{job} binding", binding, {
        "tenant": SUBJECT[0], "actor": SUBJECT[1], "job": job, "action": ACTION, "revision": revision,
        "digest": _digest(json.dumps(DRAFTS[topic], separators=(",", ":"))),
    })
    return reply


def _review(dispatch, binding, decision):
    reply = dispatch("review", binding=binding, decision=decision)
    _result(f"{binding['job']} review", reply, "review_recorded")
    return reply


def _receipt(binding):
    # Phase 5 operation identity contract, not the ID from the response under test.
    return _digest(json.dumps([ACTION, *SUBJECT, binding["job"], binding["revision"], binding["digest"]]))


def _checkpoint(binding, topic, status="pending", receipt=None):
    return [*SUBJECT, binding["job"], binding["revision"], DRAFTS[topic], status, receipt]


def _decision(binding, decision):
    return [*SUBJECT, binding["job"], ACTION, binding["revision"], binding["digest"], decision]


def _saved(binding, topic):
    return [_receipt(binding), *SUBJECT, binding["job"], DRAFTS[topic]]


def _read_snapshot(directory):
    observed = audit(directory)
    # audit reads the business version; independently read the review file's version too.
    with closing(sqlite3.connect((directory / "review.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        review_version, = db.execute("PRAGMA user_version").fetchone()
    return {**observed, "schemas": {"business.sqlite": observed["schema"], "review.sqlite": review_version}}


def _snapshot(directory, checkpoints, reviews=(), saved=(), revocations=(), extras=()):
    observed = _read_snapshot(directory)
    _expect("store schema versions", observed["schemas"], {name: 1 for name in STORE_FILES})
    _expect("all-subject audit", observed, {
        "schema": 1, "schemas": observed["schemas"],
        "checkpoints": sorted(checkpoints, key=lambda row: row[:3]),
        "reviews": sorted(reviews),
        "saved": sorted(saved, key=lambda row: row[0]),
        "revocations": sorted(revocations),
        "extras": sorted(extras),
    })
    return observed


def _result(label, reply, status, *, receipt=None, draft=None, inserts=(), read_calls=0, **extra):
    _expect(label, reply, {
        "status": status, "receipt": receipt, "draft": draft, "read_calls": read_calls,
        "inserts": list(inserts), **extra,
    })


def _lost(dispatch, binding, topic):
    _review(dispatch, binding, "approve")
    injection = dispatch("fixture_lost", binding=binding)
    _result("post-commit fault", injection, "reply_lost", inserts=[_receipt(binding)],
            read_calls=len(DRAFTS[topic][-1]))
    return injection


@contextmanager
def _logged_worker(directory, *, role, build, lifecycle):
    with Worker(directory, build=build, profile="reviewer") as worker:
        identity = {"role": role, "build": build, "pid": worker.pid, "store": _digest(str(directory.resolve()))}
        lifecycle.append({"event": "started", **identity})  # The worker has replied ready.
        paused = False

        def dispatch(operation, **payload):
            nonlocal paused
            if paused:
                raise RuntimeError("cannot dispatch to a paused candidate")
            reply = worker.call(operation, **payload)
            status = reply["status"]
            if role == "candidate" and status == "reply_lost":
                paused = True  # Fence this pipe as soon as the outcome becomes uncertain.
            job = payload["binding"]["job"] if "binding" in payload else payload["job"]
            review = {"decision": payload["decision"]} if operation == "review" else {}
            lifecycle.append({"event": "dispatch", **identity, "operation": operation, "job": job,
                              "status": status, **review})
            return reply

        yield identity, dispatch
    lifecycle.append({"event": "exited", **identity})  # close() joined normally or raised.


def _stage_decisions(dispatch, era):
    tasks = {}
    for decision in ("approve", "deny"):
        job = f"{era}-{decision}"
        pending = _stage(dispatch, job)
        binding = pending["binding"]
        tasks[job] = {"binding": binding, "pending": pending, "review": _review(dispatch, binding, decision)}
    return tasks


def _candidate_stop(candidate, reply):
    # The controller has no confirmed outcome yet. Do not infer commit from the fixture's INSERT counter.
    status = reply["status"]
    signals = ("uncertain_outcome",) if status == "reply_lost" else ()
    decision, reasons = canary.decide({}, {}, complete=False, hard_signals=signals)
    _expect("candidate stop", (decision, reasons), ("STOP_AND_ROLLBACK", ["uncertain_outcome"]))
    return {"pid": candidate["pid"], "operation": "fixture_lost", "job": "lost",
            "observed_status": status, "decision": decision, "reasons": reasons}


def worked():
    """Stop the running v2 candidate, then replace it with v1 over the same durable files."""
    lifecycle = []
    with TemporaryDirectory(prefix="l97-worked-") as root:
        directory = Path(root)
        with _logged_worker(directory, role="before", build="v1", lifecycle=lifecycle) as (prior, dispatch):
            tasks = _stage_decisions(dispatch, "pre")
        waiting = [_checkpoint(task["binding"], "export") for task in tasks.values()]
        reviews = [_decision(task["binding"], job.split("-")[1]) for job, task in tasks.items()]
        before = _snapshot(directory, waiting, reviews)

        with _logged_worker(directory, role="candidate", build="v2", lifecycle=lifecycle) as (candidate, dispatch):
            canary_tasks = _stage_decisions(dispatch, "canary")
            undecided = _stage(dispatch, "sync", "sync")["binding"]
            lost = _stage(dispatch, "lost", "sync")["binding"]
            _review(dispatch, lost, "approve")
            waiting.extend(_checkpoint(task["binding"], "export") for task in canary_tasks.values())
            waiting.append(_checkpoint(undecided, "sync"))
            reviews.extend(_decision(task["binding"], job.split("-")[1]) for job, task in canary_tasks.items())
            reviews.append(_decision(lost, "approve"))
            extras = [[job, 1] for job in (*canary_tasks, "sync", "lost")]
            # The pipe is idle between synchronous calls. Independently observe both committed stores.
            pre_stop = _snapshot(directory, [*waiting, _checkpoint(lost, "sync")], reviews, extras=extras)
            lifecycle.append({"event": "pre_stop_audited", **candidate})
            injection = dispatch("fixture_lost", binding=lost)
            stop = _candidate_stop(candidate, injection)
            lifecycle.append({"event": "stop", **candidate, **stop})

        lost_row = _saved(lost, "sync")
        _result("post-commit fault", injection, "reply_lost", inserts=[lost_row[0]], read_calls=1)
        handoff = _snapshot(directory, [*waiting, _checkpoint(lost, "sync", "saved", lost_row[0])],
                            reviews, [lost_row], extras=extras)
        persisted_receipt = handoff["saved"][0][0]
        lifecycle.append({"event": "preflight_passed", **candidate})

        # Only a recorded stop, clean exit and matching readback reach here. Never restore an old copy.
        tasks.update(canary_tasks)
        checkpoints = [_checkpoint(undecided, "sync"), _checkpoint(lost, "sync", "saved", persisted_receipt)]
        saved = [lost_row]
        with _logged_worker(directory, role="restored", build="v1", lifecycle=lifecycle) as (restored, dispatch):
            pids = {identity["role"]: identity["pid"] for identity in (prior, candidate, restored)}
            _expect("distinct process IDs", len(set(pids.values())), 3)
            for job, task in tasks.items():
                binding = task["binding"]
                outcome = dispatch("recover", binding=binding)
                if job.endswith("-approve"):
                    row = _saved(binding, "export")
                    status, receipt = "saved", row[0]
                    _result(job, outcome, status, receipt=receipt, draft=row[-1], inserts=[receipt], read_calls=2)
                    saved.append(row)
                else:
                    status, receipt = "denied", None
                    _result(job, outcome, status)
                checkpoints.append(_checkpoint(binding, "export", status, receipt))
                task["outcome"] = outcome
            pending = dispatch("recover", binding=undecided)
            _result("unreviewed sync", pending, "pending")
            replay = dispatch("recover", binding=lost)
            repeated = dispatch("recover", binding=lost)
            for reply in (replay, repeated):
                _result("lost reply replay", reply, "replayed", receipt=persisted_receipt, draft=lost_row[-1], read_calls=1)
        after = _snapshot(directory, checkpoints, reviews, saved, extras=extras)
    return {"pids": pids, "lifecycle": lifecycle, "stop": stop, "tasks": tasks, "before": before,
            "pre_stop": pre_stop, "handoff": handoff, "after": after, "undecided": {"binding": undecided, "outcome": pending},
            "lost": {"binding": lost, "injection": injection, "persisted_receipt": persisted_receipt,
                     "replay": replay, "repeated": repeated}}


def wrong_actor():
    """Changing actor text or switching tenant never transfers a trusted approval."""
    with TemporaryDirectory(prefix="l97-wrong-actor-") as root:
        directory = Path(root)
        with Worker(directory, build="v2", profile="reviewer") as candidate:
            binding = _stage(candidate.call, "export")["binding"]
            _review(candidate.call, binding, "approve")
        checkpoints = [_checkpoint(binding, "export")]
        reviews, extras = [_decision(binding, "approve")], [["export", 1]]
        before = _snapshot(directory, checkpoints, reviews, extras=extras)
        wrong_binding = dict(binding, actor="lin")
        with Worker(directory, profile="reviewer") as restored:
            outcome = restored.call("recover", binding=wrong_binding)
            _result("wrong-actor binding", outcome, "rejected")
        with Worker(directory, profile="other") as outsider:
            inspect = outsider.call("inspect", job="export")
            cross_scope = outsider.call("recover", binding=binding)
            _result("cross-scope inspect", inspect, "not_available")
            _result("cross-scope recovery", cross_scope, "forbidden")
        after = _snapshot(directory, checkpoints, reviews, extras=extras)
    return {"binding": binding, "wrong_binding": wrong_binding, "outcome": outcome,
            "inspect": inspect, "cross_scope": cross_scope, "before": before, "after": after}


def stale():
    """An approved original draft cannot authorize a newer pending draft."""
    with TemporaryDirectory(prefix="l97-stale-") as root:
        directory = Path(root)
        with Worker(directory, build="v1", profile="reviewer") as prior:
            old_binding = _stage(prior.call, "export")["binding"]
            _review(prior.call, old_binding, "approve")
        original = _snapshot(directory, [_checkpoint(old_binding, "export")], [_decision(old_binding, "approve")])
        with Worker(directory, build="v2") as candidate:
            binding = _stage(candidate.call, "export", revision=2)["binding"]
        _expect("revision-only change", binding, dict(old_binding, revision=2))
        checkpoints, reviews, extras = [_checkpoint(binding, "export")], [_decision(old_binding, "approve")], [["export", 2]]
        before = _snapshot(directory, checkpoints, reviews, extras=extras)
        with Worker(directory, profile="reviewer") as restored:
            outcome = restored.call("recover", binding=old_binding)
            current = restored.call("recover", binding=binding)
            _result("stale approval", outcome, "rejected")
            _result("current draft with no matching approval", current, "pending")
        after = _snapshot(directory, checkpoints, reviews, extras=extras)
    return {"old_binding": old_binding, "binding": binding, "outcome": outcome,
            "current": current, "original": original, "before": before, "after": after}


def revoked():
    """Revocation follows the stored scope across replacement, without undoing the commit."""
    with TemporaryDirectory(prefix="l97-revoked-") as root:
        directory = Path(root)
        with Worker(directory, build="v2", profile="reviewer") as candidate:
            binding = _stage(candidate.call, "sync", "sync")["binding"]
            _lost(candidate.call, binding, "sync")
            control = candidate.call("recover", binding=binding)
            row = _saved(binding, "sync")
            _result("replay before revocation", control, "replayed", receipt=row[0], draft=row[-1], read_calls=1)
            revoke = candidate.call("fixture_revoke", topic="sync")
            _result("trusted revocation", revoke, "revoked")
        checkpoints, reviews = [_checkpoint(binding, "sync", "saved", row[0])], [_decision(binding, "approve")]
        records = dict(revocations=[[*SUBJECT, "SYNC-POLICY"]], extras=[["sync", 1]])
        before = _snapshot(directory, checkpoints, reviews, [row], **records)
        with Worker(directory, profile="reviewer") as restored:
            outcome = restored.call("recover", binding=binding)
            _result("replay after revocation", outcome, "replay_withheld", read_calls=1)
        after = _snapshot(directory, checkpoints, reviews, [row], **records)
    return {"binding": binding, "control": control, "revoke": revoke, "outcome": outcome,
            "before": before, "after": after}


def _copy_closed(source, target):
    """Copy a closed lab pair for fault injection, never to restore the live branch."""
    target.mkdir()
    _expect("closed store files", sorted(path.name for path in source.iterdir()), sorted(STORE_FILES))
    for name in STORE_FILES:
        shutil.copyfile(source / name, target / name)


def _fingerprints(directory):
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(directory.iterdir())}


def corrupt_receipt():
    """A valid SQLite row with the wrong draft is not a valid receipt."""
    with TemporaryDirectory(prefix="l97-corrupt-") as root:
        source, copy = Path(root) / "source", Path(root) / "corrupt"
        with Worker(source, build="v2", profile="reviewer") as candidate:
            binding = _stage(candidate.call, "export")["binding"]
            _lost(candidate.call, binding, "export")
        row = _saved(binding, "export")
        checkpoints = [_checkpoint(binding, "export", "saved", row[0])]
        reviews, extras = [_decision(binding, "approve")], [["export", 1]]
        original = _snapshot(source, checkpoints, reviews, [row], extras=extras)
        original_files = _fingerprints(source)
        _copy_closed(source, copy)
        corrupt = ["错误草稿", "不匹配的回执正文", ["KB-01"]]
        with closing(sqlite3.connect(copy / "business.sqlite")) as db, db:
            update = db.execute("UPDATE saved_drafts SET payload=? WHERE op_id=?", (json.dumps(corrupt), row[0]))
            _expect("corruption target rows", update.rowcount, 1)
        saved = [[*row[:-1], corrupt]]
        before = _snapshot(copy, checkpoints, reviews, saved, extras=extras)
        with Worker(copy, profile="reviewer") as restored:
            outcome = restored.call("recover", binding=binding)
            _result("corrupt receipt", outcome, "inconsistent")
        after = _snapshot(copy, checkpoints, reviews, saved, extras=extras)
        _expect("untouched original store files", _fingerprints(source), original_files)
    return {"binding": binding, "original": original, "before": before, "after": after, "outcome": outcome}


def incompatible():
    """Exercise the real startup guard with a synthetic version on an offline copy."""
    with TemporaryDirectory(prefix="l97-incompatible-") as root:
        source, copy = Path(root) / "source", Path(root) / "unknown"
        with Worker(source, build="v2", profile="reviewer") as candidate:
            binding = _stage(candidate.call, "sync", "sync")["binding"]
            _review(candidate.call, binding, "approve")
        original = _snapshot(source, [_checkpoint(binding, "sync")], [_decision(binding, "approve")],
                             extras=[["sync", 1]])
        original_files = _fingerprints(source)
        _copy_closed(source, copy)
        with closing(sqlite3.connect(copy / "business.sqlite")) as db, db:
            db.execute("PRAGMA user_version = 2")
        before, before_files = _read_snapshot(copy), _fingerprints(copy)
        _expect("only the copy's schema changed", before,
                dict(original, schema=2, schemas={**original["schemas"], "business.sqlite": 2}))
        _expect("only the copied business file changed", {
            name for name in STORE_FILES if before_files[name] != original_files[name]
        }, {"business.sqlite"})
        try:
            with Worker(copy, profile="reviewer"):
                raise AssertionError("incompatible writer started")
        except StartupRefused as exc:
            status = str(exc)
            _expect("startup refusal", status, "incompatible_schema")
        after, after_files = _read_snapshot(copy), _fingerprints(copy)
        _expect("refused store rows", after, before)
        _expect("refused store files", after_files, before_files)
        _expect("untouched original store files", _fingerprints(source), original_files)
    return {"status": status, "original": original, "before": before, "after": after,
            "fingerprints": {"original": original_files, "before": before_files, "after": after_files}}


def transfer():
    """Exercise independent mutations, each from new temporary state."""
    return {"wrong_actor": wrong_actor(), "stale": stale(), "revoked": revoked(),
            "corrupt_receipt": corrupt_receipt(), "incompatible": incompatible()}


def rehearse():
    """Return validated L97 evidence; raise instead of reporting success on a mismatch."""
    return {"worked": worked(), "transfer": transfer(), "decision": "LOCAL_ROLLBACK_VERIFIED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("worked", "transfer", "stage"))
    mode = parser.parse_args().mode
    runner, marker = {
        "worked": (worked, "L97 ACCEPTED"),
        "transfer": (transfer, "L97 TRANSFER PASSED"),
        "stage": (rehearse, "P11 LOCAL ROLLBACK PASSED"),
    }[mode]
    print(json.dumps(runner(), sort_keys=True))
    print(marker)


if __name__ == "__main__":
    main()
