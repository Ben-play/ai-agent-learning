"""Seal v1 inputs, prepare each case once, and grade independent observations."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from host import ACTOR, FIELDS, JOB, P5, audit, connect, open_store, put_review

HERE = Path(__file__).resolve().parent
GOLD = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
BAD_FIELDS = {"wrong_actor": ("actor", "another-reviewer"), "wrong_tenant": ("tenant", "another-tenant"),
              "wrong_job": ("job", "another-job"), "wrong_action": ("action", "submit"),
              "wrong_revision": ("revision", 1), "wrong_digest": ("digest", "0" * 64)}
FALLBACK_CASES = ("deny", "approve", "apply_approved", "replay", "missing_receipt", "mismatched_receipt",
                  "wrong_actor", "wrong_tenant", "wrong_revision", "old_review", "source_revoked")


def require(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: observed {actual!r}, expected {expected!r}")


def hashes(directory, names):
    # Extra files (including live SQLite journals/WAL/SHM) prevent sealing or matching a copy.
    require("closed bundle entries", set(p.name for p in directory.iterdir()), set(names))
    return {name: sha256((directory / name).read_bytes()).hexdigest() for name in sorted(names)}


def clone(source, destination, origin):
    require("sealed origin before copy", hashes(source, origin), origin)
    shutil.copytree(source, destination)
    require("new working copy", hashes(destination, origin), origin)
    return destination


def golden_review(task, decision):
    return [*(task[field] for field in GOLD["binding_order"]), decision]


def golden_reply(status, receipt=None, draft=None):
    return {"status": status, "receipt": receipt, "draft": draft}


def check_ledger(ledger, expected):
    require("business checkpoints, all subjects", ledger["checkpoints"], expected["checkpoints"])
    require("approval binding readback", ledger["reviews"], expected["reviews"])
    require("current source records", ledger["sources"], expected["sources"])
    require("all durable drafts", ledger["saved"], expected["saved"])


def seed_bundle(adapter, root, stop, encoding):
    root.mkdir()
    old, lost = adapter.seed(root, stop, encoding)
    origin = hashes(root, (adapter.CHECKPOINT, "reviews.sqlite", "business.sqlite"))
    graph, ledger = adapter.inspect(root), audit(root)
    require("closed bundle after readback", hashes(root, origin), origin)
    task, receipt, draft = GOLD["task"], GOLD["receipt"], GOLD["draft"]
    require("binding of earlier revision", old, dict(task, revision=1, digest=GOLD["old_digest"]))
    expected = GOLD["seeds"][stop]
    values = {"schema": 1, "status": expected["status"],
              "binding": task if encoding == "named" else [task[field] for field in GOLD["binding_order"]]}
    require("v1 graph snapshot", graph, {"thread": GOLD["thread"], "values": values, "next": expected["next"],
                                       "interrupts": [{"job": task["job"], "revision": task["revision"]}]
                                       if stop == "pending" else []})
    require("v1 committed/no reply", lost, {"reply": golden_reply("reply_lost"), "nodes": ["apply_review"],
                  "calls": 1, "inserts": [receipt]} if stop == "committed" else None)
    subject = [task["tenant"], task["actor"], task["job"]]
    check_ledger(ledger, {"checkpoints": [[*subject, task["revision"], draft, expected["business"],
                                           receipt if expected["business"] == "saved" else None]],
                          "reviews": [] if stop == "pending" else [golden_review(task, "approve")],
                          "sources": GOLD["sources"],
                          "saved": [[receipt, *subject, draft]] if expected["saved"] else []})
    return {"origin": origin, "graph": graph, "ledger": ledger, "fault_observer": lost, "old_binding": old}


def change_fixture(directory, case, before):
    """Trusted injector: no gold or expected observations, and no writes to the graph."""
    if case in {"approve", "deny", "old_review", "revised", *BAD_FIELDS}:
        raw = before["graph"]["values"]["binding"]
        task = dict(zip(FIELDS, raw)) if isinstance(raw, list) else dict(raw)
        if case in BAD_FIELDS:
            key, value = BAD_FIELDS[case]
            task[key] = value
        if case == "old_review":
            task = before["old_binding"]  # The real revision-1 binding produced by v1.
        put_review(directory, task, "deny" if case == "deny" else "approve")
    if case == "revised":
        with open_store(directory / "business.sqlite") as store:
            store.stage(ACTOR, JOB, 3, P5["QUESTION"])
    if case in {"source_changed", "source_revoked"}:
        with connect(directory / "reviews.sqlite", write=True) as db:
            if case == "source_changed":
                db.execute("UPDATE sources SET revision=2, text=? WHERE source_id='KB-01'", ("导出仅保留 3 天。",))
            else:
                db.execute("DELETE FROM sources WHERE source_id='KB-02'")
    if case in {"missing_receipt", "mismatched_receipt"}:
        with connect(directory / "business.sqlite", write=True) as db:
            if case == "missing_receipt":
                db.execute("DELETE FROM saved_drafts")
            else:
                db.execute("UPDATE saved_drafts SET payload=?", (json.dumps(["错误草稿", "不匹配的回执正文", ["KB-01"]]),))


def golden_prepared(before, case):
    # Apply only literal gold deltas to the already verified seed. Every other field must match exactly.
    expected = dict(before["ledger"])
    changes = GOLD["prepared_changes"].get(case, {})
    if "review" in changes:
        row = dict(GOLD["task"], **changes["review"])
        expected["reviews"] = [golden_review(row, row["decision"])]
    if "business_revision" in changes:
        checkpoint, = expected["checkpoints"]
        expected["checkpoints"] = [[*checkpoint[:3], changes["business_revision"], *checkpoint[4:]]]
    if "source_replaced" in changes:
        replacement = changes["source_replaced"]
        expected["sources"] = [replacement if row[:3] == replacement[:3] else row for row in expected["sources"]]
    if "source_removed" in changes:
        expected["sources"] = [row for row in expected["sources"] if row != changes["source_removed"]]
    if "saved_removed" in changes:
        expected["saved"] = []
    if "saved_payload" in changes:
        saved, = expected["saved"]
        expected["saved"] = [[*saved[:-1], changes["saved_payload"]]]
    return expected


def prepare(adapter, sealed, directory, case, before):
    clone(sealed, directory, before["origin"])
    change_fixture(directory, case, before)
    origin = hashes(directory, before["origin"])
    graph, ledger = adapter.inspect(directory), audit(directory)
    require("prepared graph unchanged", graph, before["graph"])
    expected = golden_prepared(before, case)
    check_ledger(ledger, expected)
    original = before["ledger"]
    allowed = {filename for filename, tables in (("reviews.sqlite", ("reviews", "sources")),
                                                  ("business.sqlite", ("checkpoints", "saved")))
               if any(original[name] != expected[name] for name in tables)}
    require("only intended input files changed", {name for name in origin if origin[name] != before["origin"][name]},
            allowed)
    require("prepared bundle after readback", hashes(directory, origin), origin)
    return {"origin": origin, "graph": graph, "ledger": ledger}


def verify_arm(prepared, after, expected, version, graph, ledger):
    releases = expected["releases"]
    receipt = GOLD["receipt"] if releases else None
    nodes = expected["nodes"] + (["finish"] if version == 2 and releases else [])
    require("actual invocation", after, {"reply": golden_reply(expected["status"], receipt, GOLD["draft"] if releases else None),
                                       "nodes": nodes, "calls": expected["calls"],
                                       "inserts": [GOLD["receipt"]] if expected["inserts"] else []})
    expected_graph = prepared["graph"]
    if nodes:
        values = dict(expected_graph["values"], status=expected["status"], receipt=receipt)
        if version == 2 and releases:
            values.update(schema=2, completion="receipt_checked")
        expected_graph = {"thread": GOLD["thread"], "values": values, "next": [], "interrupts": []}
    require("observed checkpoint after run", graph, expected_graph)
    start = prepared["ledger"]
    checkpoint, = start["checkpoints"]
    op = GOLD["receipt"] if expected["business"] == "saved" else None
    saved = [[op, *checkpoint[:3], GOLD["draft"]]] if expected["inserts"] else start["saved"]
    require("expected durable draft count", len(ledger["saved"]), expected["saved"])
    check_ledger(ledger, dict(start, checkpoints=[[*checkpoint[:5], expected["business"], op]], saved=saved))


def restart(adapter, directory, version):
    # Each invocation is a fresh interpreter, not a new copy of the prepared input.
    proc = subprocess.run([sys.executable, "-B", adapter.__file__, "_advance", str(directory), str(version)],
                          check=True, capture_output=True, encoding="utf-8", timeout=30)
    return json.loads(proc.stdout)


def worker():
    if len(sys.argv) == 4 and sys.argv[1] == "_advance":
        adapter = sys.modules["__main__"]
        print(json.dumps(adapter.advance(Path(sys.argv[2]), int(sys.argv[3]))))
        return True
    return False


def scenario(adapter, workspace, case, versions, *, legacy=False, repeat=0):
    expected = GOLD["cases"][case]
    sealed = workspace / "sealed"
    before = seed_bundle(adapter, sealed, expected["seed"], "ordered" if legacy else "named")
    prepared_dir = workspace / "prepared"
    prepared = prepare(adapter, sealed, prepared_dir, case, before)
    origin = prepared["origin"]
    refused, arms = [], {}
    if repeat:
        failed = clone(prepared_dir, workspace / "candidate", origin)
        # Reopen the very same working copy in each fresh process, without repair or reseeding.
        for _ in range(repeat):
            starting = hashes(failed, origin)
            require("candidate inputs before recovery", starting, origin)
            result = restart(adapter, failed, 2)
            require("candidate refused before dispatch", result, {"reply": golden_reply("migration_refused"),
                                                                 "nodes": [], "calls": 0, "inserts": []})
            graph, ledger = adapter.inspect(failed), audit(failed)
            require("candidate checkpoint unchanged", graph, prepared["graph"])
            check_ledger(ledger, prepared["ledger"])
            after = hashes(failed, origin)
            require("candidate preserved every input file", after, origin)
            refused.append({**result, "origin": starting, "after": after, "graph": graph, "ledger": ledger})
    for version in versions:
        arm = clone(prepared_dir, workspace / f"v{version}", origin)
        starting = hashes(arm, origin)
        require("arm inputs before recovery", starting, origin)
        actual = restart(adapter, arm, version) if legacy else adapter.advance(arm, version)
        graph, ledger = adapter.inspect(arm), audit(arm)
        verify_arm(prepared, actual, expected, version, graph, ledger)
        after = hashes(arm, origin)
        require("arm preserved approval and source database", after["reviews.sqlite"], origin["reviews.sqlite"])
        if all(ledger[name] == prepared["ledger"][name] for name in ("checkpoints", "saved")):
            require("arm preserved business database with no durable changes", after["business.sqlite"],
                    origin["business.sqlite"])
        if not actual["nodes"]:
            require("non-dispatched arm preserved every input file", after, origin)
        arms[f"v{version}"] = {**actual, "from_origin": before["origin"], "from_prepared": starting,
                               "after": after, "graph": graph, "ledger": ledger}
    require("prepared bundle after all arms", hashes(prepared_dir, origin), origin)
    require("sealed origin after all arms", hashes(sealed, before["origin"]), before["origin"])
    return {"before": before, "prepared": prepared, "arms": arms, "refused": refused}


def run(adapter, action, *, cases=None):
    """Run all cases by default; compare/fallback may select named cases in caller order."""
    modes = {"compare": (tuple(GOLD["cases"]), (1, 2)), "fallback": (FALLBACK_CASES, (1,))}
    if action not in (*modes, "seed", "stage"):
        raise ValueError(f"unknown rehearsal action: {action}")
    if cases is not None:
        if action not in modes:
            raise ValueError("case selection is only available for compare or fallback")
        selected = (cases,) if isinstance(cases, str) else tuple(cases)
        if not selected or len(set(selected)) != len(selected):
            raise ValueError("select at least one case, without duplicates")
        allowed, versions = modes[action]
        unknown = [name for name in selected if name not in allowed]
        if unknown:
            raise ValueError(f"unknown {action} case: {', '.join(unknown)}")
        modes[action] = selected, versions
    with TemporaryDirectory(prefix="p10-checkpoints-") as tmp:
        root = Path(tmp)
        if action == "seed":
            seeds = {stop: seed_bundle(adapter, root / stop, stop, "named") for stop in GOLD["seeds"]}
            require("three distinct checkpoint bundles", len({tuple(s["origin"].values()) for s in seeds.values()}), 3)
            return seeds
        report = {}
        for mode, (names, versions) in modes.items():
            if action == mode or action == "stage":
                report[mode] = {}
                for case in names:
                    workspace = root / f"{mode}-{case}"
                    workspace.mkdir()
                    report[mode][case] = scenario(adapter, workspace, case, versions,
                                                  legacy=mode == "fallback", repeat=2 if mode == "fallback" else 0)
        return report if action == "stage" else report[action]
