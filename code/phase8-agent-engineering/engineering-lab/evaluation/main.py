"""Offline evaluation for Phase 8 L72–L74; no network, judge API or production writes."""

import argparse
from contextlib import closing, nullcontext
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
import runpy
import sqlite3
from tempfile import TemporaryDirectory
import unicodedata

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[2]
FIXTURES = HERE / "fixtures" / "v1"
DATASET_VERSION = "p8-eval-v1"
RUBRIC_VERSION = "p8-judge-v1"
RAG = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/lab.py"))
CHECKS = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/assessment/checks.py"))
HARNESS = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
saved_drafts = runpy.run_path(str(HERE.parent / "observations.py"))["saved_drafts"]
ACTIONS = frozenset({"approve", "deny", "without_review", "approve_lose_reply"})
FACTS = {
    "retention": ("EXPORT-POLICY", "导出文件生成后保留 7 天。", "7 天"),
    "schedule": ("SYNC-POLICY", "同步任务每天 02:00 运行。", "02:00"),
    "renewal": ("EXPORT-OPS", "导出文件过期后，需重新发起导出。", "重新发起导出"),
}


def _read_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _question_key(question):
    return "".join(c for c in unicodedata.normalize("NFKC", question).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith("P"))


def validate_splits(dev, acceptance):
    """Fail on cross-split family/text leakage and on any duplicate task ID."""
    all_ids, families, questions = set(), {}, {}
    for split, envelope, prefix in (("dev", dev, "DEV-"), ("acceptance", acceptance, "ACC-")):
        if envelope["dataset_version"] != DATASET_VERSION or envelope["split"] != split:
            raise ValueError(f"invalid version or split: {split}")
        if not envelope["tasks"]:
            raise ValueError(f"empty split: {split}")
        for task in envelope["tasks"]:
            task_id, family, request = task["id"], task["family"], task["request"]
            # Check uniqueness before the prefix, so copied task IDs are reported as duplicates.
            if task_id in all_ids:
                raise ValueError(f"duplicate ID: {task_id}")
            if not task_id.startswith(prefix) or not task_id[len(prefix):]:
                raise ValueError(f"invalid ID prefix: {task_id}")
            all_ids.add(task_id)
            if type(family) is not str or not family or family != family.strip():
                raise ValueError(f"invalid family label (expected a nonempty unpadded string): {task_id}")
            question = _question_key(request["question"])
            if not question:
                raise ValueError(f"missing question: {task_id}")
            if families.setdefault(family, split) != split:
                raise ValueError(f"family overlap: {family}")
            if questions.setdefault(question, split) != split:
                raise ValueError(f"question overlap: {task_id}")
            if task["kind"] == "qa":
                facts = request["facts"]
                if not facts or len(set(facts)) != len(facts) or set(facts) - FACTS.keys():
                    raise ValueError(f"invalid fact slots: {task_id}")
            elif task["kind"] == "draft":
                if set(request["actions"]) - ACTIONS:
                    raise ValueError(f"unknown draft action: {task_id}")
            else:
                raise ValueError(f"unknown task kind: {task_id}")


def load_datasets():
    dev, acceptance = _read_fixture("dev.json"), _read_fixture("acceptance.json")
    validate_splits(dev, acceptance)
    return {"dev": dev["tasks"], "acceptance": acceptance["tasks"]}


@dataclass(frozen=True)
class Citation:
    tenant: str
    key: tuple[str, int, str]
    quote: str


@dataclass(frozen=True)
class Claim:
    fact: str
    value: str
    citation: Citation


@dataclass(frozen=True)
class Answer:
    status: str
    claims: tuple[Claim, ...]
    gaps: tuple[str, ...]


def make_packet(db, request):
    """The packet comes from real authorized lexical retrieval in the Phase 7 lab."""
    tenant, actor = request["tenant"], request["actor"]
    hits = db.search(tenant, actor, RAG["Query"](tuple(request["terms"])), k=3)
    return tuple(Citation(tenant, hit.chunk.key, hit.chunk.text) for hit in hits)


def answer_from_packet(request, packet):
    """Scripted evidence-to-fact adapter. It receives no task ID, split or gold label."""
    claims, gaps = [], []
    for fact in request["facts"]:
        doc, quote, value = FACTS[fact]
        citation = next((c for c in packet if c.key[0] == doc and c.quote == quote), None)
        if citation is None:
            gaps.append(fact)
        else:
            claims.append(Claim(fact, value, citation))
    status = "partial" if claims and gaps else "answer" if claims else "refuse"
    return Answer(status, tuple(claims), tuple(gaps))


def exact_provenance(db, request, packet, answer):
    """Shared hard gate: check the whole packet and each claimed citation, without gold."""
    tenant, actor = request["tenant"], request["actor"]

    def citation_checks(citation):
        if (type(citation) is not Citation or citation.tenant != tenant
                or type(citation.key) is not tuple or len(citation.key) != 3
                or type(citation.key[1]) is not int
                or any(type(citation.key[i]) is not str for i in (0, 2))):
            return False, False
        source = db.source(tenant, actor, citation.key)
        return source is not None, source is not None and bool(citation.quote) and source.text == citation.quote

    axes = []
    for claim in answer.claims:
        locator_ok, quote_ok = citation_checks(claim.citation)
        axes.append({"fact": claim.fact, "authorized_locator": locator_ok, "quote_exact": quote_ok,
                     "authorized_exact": locator_ok and quote_ok, "in_packet": claim.citation in packet})
    packet_ok = all(all(citation_checks(c)) for c in packet)
    passed = packet_ok and all(row["authorized_exact"] and row["in_packet"] for row in axes)
    return {"passed": passed, "packet_ok": packet_ok, "claims": axes}


def grade_qa(db, request, packet, answer, expected):
    """Add independent literal fact, shape and support gold to the hard provenance gate."""
    provenance = exact_provenance(db, request, packet, answer)
    axes = provenance["claims"]
    for claim, row in zip(answer.claims, axes):
        citation = claim.citation
        gold = expected["claims"].get(claim.fact)
        value_ok = gold is not None and claim.value == gold["value"]
        supported = bool(value_ok and type(citation) is Citation and citation.key == tuple(gold["key"])
                         and citation.quote == gold["quote"])
        row.update(value_ok=value_ok, supported=supported)
    facts = [claim.fact for claim in answer.claims]
    shape_ok = (answer.status == expected["status"] and sorted(answer.gaps) == sorted(expected["gaps"])
                and sorted(facts) == sorted(expected["claims"]))
    passed = provenance["passed"] and shape_ok and all(row["supported"] for row in axes)
    return {"passed": passed, "packet_ok": provenance["packet_ok"], "shape_ok": shape_ok, "claims": axes}


def _draft_payload(draft):
    return {"title": draft.title, "body": draft.body, "source_ids": list(draft.source_ids)}


# Host-owned bridge, independent of the request, generated draft and current store.
# KB-02's legacy sentence is a reviewed paraphrase, not a Phase 7 quote.
LEGACY_SOURCES = {
    "KB-01": ("导出文件生成后保留 7 天。", CHECKS["DEMO_POLICY"]),
    "KB-02": ("超过保留期需重新发起导出。", CHECKS["DEMO_RENEWAL"]),
    "KB-03": ("同步任务每天 02:00 运行。", CHECKS["DEMO_SYNC"]),
}
LEGACY_DRAFTS = {
    ("KB-01", "KB-02"): "需人工确认：导出保留期",
    ("KB-03",): "需人工确认：同步时间",
}


def _draft_sources_current(db, actor, draft):
    ids = draft.source_ids
    if ids not in LEGACY_DRAFTS or draft.title != LEGACY_DRAFTS[ids]:
        return False
    mapped = tuple(LEGACY_SOURCES[source_id] for source_id in ids)
    scope = CHECKS["Scope"](actor.tenant, actor.name)
    return draft.body == " ".join(text for text, _ in mapped) and all(
        CHECKS["exact_source"](db, scope, citation) for _, citation in mapped
    )


class DraftSourceBlocked(ValueError):
    """The host cannot verify this draft against the current authorized corpus."""


def observe_draft(request, *, block_draft_insert=False, temp_parent=None, evidence_store=None, before_review=None):
    """Observe the actual Phase 5 store; each step reopens the same trial DB.

    The host may supply a real Phase 7 store and a before_review(step, db)
    fixture callback; by default the trial owns a fresh demo corpus. The
    optional fixed SQLite trigger is only fault injection in this temporary
    lab: an authorized INSERT reaches SQLite but adds no row.
    """
    actor = HARNESS["Actor"](request["tenant"], request["actor"])
    job, review = request["job"], HARNESS["Review"]
    reviews = {"deny": review.DENY, "approve": review.APPROVE,
               "approve_lose_reply": review.APPROVE, "without_review": None}
    attempts, steps = [], []
    operation_ok, staged = True, None
    evidence = RAG["open_demo"]() if evidence_store is None else nullcontext(evidence_store)
    with evidence as db, TemporaryDirectory(prefix="p8-draft-", dir=temp_parent) as tmp:
        path = Path(tmp) / "trial.sqlite3"

        def before_stage(draft):
            if not _draft_sources_current(db, actor, draft):
                raise DraftSourceBlocked("draft evidence is not current or authorized")

        for index, action in enumerate(("stage", *request["actions"])):
            attempts.clear()
            if index and before_review is not None:
                before_review(index, db)
            with HARNESS["open_store"](path, on_draft_write_attempt=attempts.append,
                                       before_stage=before_stage) as store:
                if action == "stage":
                    if store.checkpoint(actor, job) is not None or store.saved_count(actor, job) != 0:
                        raise RuntimeError("trial did not start empty")
                    try:
                        staged = store.stage(actor, job, request["version"], request["question"])
                        result = staged.status
                    except DraftSourceBlocked:
                        result = "source_blocked"
                else:
                    current = store.checkpoint(actor, job)
                    decision = reviews[action]
                    if current is None or current.binding != staged.binding:
                        result = "rejected"
                        operation_ok = False
                    elif (decision is review.APPROVE and current.status in {"pending", "saved"}
                          and not _draft_sources_current(db, actor, current.draft)):
                        result = "replay_withheld" if current.status == "saved" else "source_blocked"
                    else:
                        # Review and Phase 7 changes are serialized by this offline host.
                        # Denial and missing review need not release or access the draft's sources.
                        try:
                            reply = store.resume(actor, job, staged.binding, decision,
                                                 lose_reply=action == "approve_lose_reply")
                            result = reply.status
                        except HARNESS["LostReply"]:
                            result = "lost_reply"
                        except sqlite3.IntegrityError as exc:
                            if not block_draft_insert or str(exc) != "phase8 fixture blocks draft insert":
                                raise
                            result = "insert_blocked"
                checkpoint = store.checkpoint(actor, job)
            rows = saved_drafts(path)
            steps.append({"action": action, "result": result, "state": checkpoint.status if checkpoint else None,
                          "attempts": len(attempts), "rows": len(rows)})
            if staged is None or checkpoint is None:
                operation_ok &= staged is None and checkpoint is None and not attempts and not rows
                break
            if action == "stage" and block_draft_insert:
                with closing(sqlite3.connect(path)) as conn:
                    conn.execute("""CREATE TRIGGER block_fixture_insert BEFORE INSERT ON saved_drafts
                                    BEGIN SELECT RAISE(ABORT, 'phase8 fixture blocks draft insert'); END""")
                    conn.commit()
            durable_payload = [staged.draft.title, staged.draft.body, list(staged.draft.source_ids)]
            operation_ok &= all(row == (checkpoint.op_id, actor.tenant, actor.name, job, durable_payload)
                                for row in rows)
            if result in {"saved", "lost_reply", "replayed"}:
                operation_ok &= (len(rows) == 1 and bool(checkpoint.op_id))
                if result == "replayed":
                    operation_ok &= reply.op_id == previous.op_id == checkpoint.op_id and reply.draft == staged.draft
                elif result == "saved":
                    operation_ok &= reply.op_id == checkpoint.op_id and reply.draft == staged.draft
                if result in {"saved", "lost_reply"}:
                    operation_ok &= attempts == [checkpoint.op_id]
            previous = checkpoint
        # The live rehearsal report is a preview too: never return a stale payload.
        preview = _draft_payload(staged.draft) if staged and _draft_sources_current(db, actor, staged.draft) else None
    return {"steps": steps, "draft": preview, "operation_ok": operation_ok, "cleanup_ok": not path.parent.exists()}


def no_draft_write(step):
    """A forbidden write must not reach INSERT or leave a row in an empty trial."""
    return step["attempts"] == 0 and step["rows"] == 0


def grade_draft(observed, expected):
    failures = []
    if len(observed["steps"]) != len(expected["steps"]):
        failures.append("step_count")
    for index, (actual, target) in enumerate(zip(observed["steps"], expected["steps"])):
        for field in ("action", "result", "state", "attempts", "rows"):
            if actual[field] != target[field]:
                failures.append(f"step_{index}.{field}")
    if observed["draft"] != expected["draft"]:
        failures.append("draft_payload")
    for field in ("operation_ok", "cleanup_ok"):
        if not observed[field]:
            failures.append(field)
    return {"passed": not failures, "failures": failures, "steps": observed["steps"]}


def run_trial(task):
    # Fixtures are trusted; only request fields enter the candidate. The host keeps gold separate.
    request, expected = task["request"], task["expected"]
    if task["kind"] == "qa":
        with RAG["open_demo"]() as db:
            packet = make_packet(db, request)
            return grade_qa(db, request, packet, answer_from_packet(request, packet), expected)
    return grade_draft(observe_draft(request), expected)


def run_split(split, *, repeats=2):
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("repeats must be an integer from 1 to 20")
    tasks = load_datasets()[split]
    trials = [{"id": task["id"], "kind": task["kind"], "trial": index, **run_trial(task)}
              for task in tasks for index in range(1, repeats + 1)]
    passed_trials = sum(row["passed"] for row in trials)
    return {"dataset_version": DATASET_VERSION, "split": split, "tasks": len(tasks),
            "repeats": repeats, "total_trials": len(trials), "passed_trials": passed_trials,
            "passed": passed_trials == len(trials), "trials": trials}


def run_acceptance(*, repeats=2):
    """Return a JSON-compatible report. Callers must check its `passed` field."""
    return run_split("acceptance", repeats=repeats)


def _index(rows):
    by_id = {row["id"]: row for row in rows}
    if not by_id or len(by_id) != len(rows) or any(not isinstance(key, str) or not key.strip() for key in by_id):
        raise ValueError("calibration IDs must be nonempty and unique")
    return by_id


def calibrate(gold, predicted, axis):
    """Pass is the positive class. Uncertain gold and judge abstention are orthogonal."""
    if axis not in {"support", "completeness"}:
        raise ValueError("unknown rubric axis")
    expected, actual = _index(gold), _index(predicted)
    if expected.keys() != actual.keys():
        raise ValueError("calibration ID sets differ")
    matrix = dict.fromkeys(("TP", "TN", "FP", "FN"), 0)
    categories = {"uncertain": [], "abstained": [], "known_abstained": [], "disagreements": []}
    for row_id in sorted(expected):
        label, vote = expected[row_id][axis], actual[row_id][axis]
        if label not in {"pass", "fail", "uncertain"} or vote not in {"pass", "fail", "abstain"}:
            raise ValueError(f"invalid calibration label: {row_id}")
        if vote == "abstain":
            categories["abstained"].append(row_id)
        if label == "uncertain":
            categories["uncertain"].append(row_id)
        elif vote == "abstain":
            categories["known_abstained"].append(row_id)
        else:
            correct = label == vote
            if not correct:
                categories["disagreements"].append(row_id)
            cell = {("pass", "pass"): "TP", ("fail", "fail"): "TN",
                    ("fail", "pass"): "FP", ("pass", "fail"): "FN"}[label, vote]
            matrix[cell] += 1
    total, matched = len(expected), sum(matrix.values())
    known = total - len(categories["uncertain"])
    return {**matrix, **categories, "total": total, "known": known, "decided_known": matched,
            "coverage": matched / known if known else None,
            "agreement": (matrix["TP"] + matrix["TN"]) / matched if matched else None,
            "disagreement_rate": (matrix["FP"] + matrix["FN"]) / matched if matched else None,
            "uncertain_rate": len(categories["uncertain"]) / total,
            "abstention_rate": len(categories["abstained"]) / total}


def run_calibration():
    gold, mock = _read_fixture("judge-gold.json"), _read_fixture("judge-mock.json")
    if gold["rubric_version"] != RUBRIC_VERSION or mock["rubric_version"] != RUBRIC_VERSION:
        raise ValueError("rubric version mismatch")
    return {"rubric_version": RUBRIC_VERSION, "judge_version": mock["judge_version"],
            **{axis: calibrate(gold["rows"], mock["rows"], axis) for axis in ("support", "completeness")}}


def quality_decision(hard_pass, support, completeness):
    """Mock/human semantic votes cannot rescue a failed deterministic check."""
    if hard_pass is not True:
        return "blocked"
    votes = {support, completeness}
    if not votes <= {"pass", "fail", "uncertain", "abstain"}:
        raise ValueError("invalid quality votes")
    if votes & {"uncertain", "abstain"}:
        return "review"
    return "pass" if votes == {"pass"} else "quality_fail"


# Deliberately narrow syntax for this corpus, not a general semantic evaluator.
_QUOTE_PATTERNS = {
    "retention": r"导出文件生成后保留(\d+天)。",
    "schedule": r"同步任务每天(\d{2}:\d{2})运行。",
    "renewal": r"导出文件过期后,需(重新发起导出)。",
}
_EQUIVALENT_PHRASES = {
    "retention": {"一周": "7天", "七天": "7天"},
    "schedule": {"凌晨两点": "02:00", "每天凌晨两点": "02:00"},
    "renewal": {"重新导出": "重新发起导出"},
}
_VALUE_PATTERNS = {"retention": r"\d+天", "schedule": r"\d{2}:\d{2}", "renewal": "重新发起导出"}


def _compact(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def scripted_judge(*, question, facts, packet, answer):
    """Local stub: compare a small phrase vocabulary to evidence, not reference labels.

    The host supplies requested fact slots rather than making the stub parse the question.
    """
    quotes = {citation: _compact(citation.quote) for citation in packet}
    votes, filled = [], set()
    for claim in answer.claims:
        value = _compact(claim.value)
        if value:
            filled.add(claim.fact)
        pattern = _QUOTE_PATTERNS.get(claim.fact)
        match = re.fullmatch(pattern, quotes.get(claim.citation, "")) if pattern else None
        if claim.fact not in facts or not match or not value:
            votes.append("fail")
            continue
        normalized = _EQUIVALENT_PHRASES[claim.fact].get(value, value)
        if not re.fullmatch(_VALUE_PATTERNS[claim.fact], normalized):
            votes.append("abstain")
        else:
            votes.append("pass" if normalized == match[1] else "fail")
    support = "fail" if "fail" in votes else "abstain" if "abstain" in votes else "pass"
    return {"support": support, "completeness": "pass" if set(facts) <= filled else "fail"}


def judge_qa(db, request, packet, answer, *, judge=scripted_judge):
    """Release evidence to the judge only after exact provenance has passed."""
    provenance = exact_provenance(db, request, packet, answer)
    if not provenance["passed"]:
        return {"decision": "blocked", "provenance": provenance, "votes": None}
    votes = judge(question=request["question"], facts=tuple(request["facts"]), packet=packet, answer=answer)
    decision = quality_decision(True, votes["support"], votes["completeness"])
    return {"decision": decision, "provenance": provenance, "votes": votes}


def _stage_draft_boundaries(tasks):
    def revoke(_, db):
        db.revoke("support", "mei", "EXPORT-OPS")

    def revise(_, db):
        old = db.source("support", "mei", ("EXPORT-OPS", 1, "§2"))
        db.replace_document("support", old.doc_id, 2, (replace(old, version=2, locator="§3"),))

    def revoke_after_commit(step, db):
        if step == 2:
            revoke(step, db)

    save = tasks["ACC-EXPORT-SAVE"]["request"]
    replay = tasks["ACC-EXPORT-REPLAY"]["request"]
    reports = {
        "blocked_stage": observe_draft(dict(save, actor="lin")),
        "revoke_before_save": observe_draft(save, before_review=revoke),
        "revise_before_save": observe_draft(save, before_review=revise),
        "revoke_before_replay": observe_draft(replay, before_review=revoke_after_commit),
    }
    for case, expected in (
        ("blocked_stage", ("source_blocked", None, 0, 0)),
        ("revoke_before_save", ("source_blocked", "pending", 0, 0)),
        ("revise_before_save", ("source_blocked", "pending", 0, 0)),
        ("revoke_before_replay", ("replay_withheld", "saved", 0, 1)),
    ):
        observed = reports[case]
        terminal = observed["steps"][-1]
        if (tuple(terminal[k] for k in ("result", "state", "attempts", "rows")) != expected
                or observed["draft"] is not None or not (observed["operation_ok"] and observed["cleanup_ok"])):
            raise RuntimeError(f"draft authorization boundary failed: {case}")
    return reports


def run_stage_check():
    acceptance = run_acceptance()
    if not acceptance["passed"]:
        raise RuntimeError("acceptance trial failed")
    tasks = {row["id"]: row for row in load_datasets()["acceptance"]}
    qa = tasks["ACC-HANDOFF-QA"]
    request = qa["request"]
    calls = 0

    def observe_judge(**inputs):
        nonlocal calls
        calls += 1
        return scripted_judge(**inputs)

    with RAG["open_demo"]() as db:
        packet = make_packet(db, request)
        answer = answer_from_packet(request, packet)
        retention, schedule = answer.claims
        bad_citation = replace(retention.citation, key=("EXPORT-POLICY", 1, "§9"))
        altered = replace(answer, claims=(replace(retention, citation=bad_citation), schedule))
        guarded = grade_qa(db, request, packet, altered, qa["expected"])
        blocked = judge_qa(db, request, packet, altered, judge=observe_judge)
        if blocked["decision"] != "blocked" or blocked["votes"] is not None or calls:
            raise RuntimeError("bad citation reached the semantic judge")
        equivalent = replace(answer, claims=(replace(retention, value="一周"),
                                              replace(schedule, value="每天凌晨两点")))
        semantic = judge_qa(db, request, packet, equivalent, judge=observe_judge)
        literal = grade_qa(db, request, packet, equivalent, qa["expected"])
    if guarded["passed"] or guarded["claims"][0]["authorized_exact"]:
        raise RuntimeError("citation mutation was not rejected")
    if literal["passed"] or semantic["decision"] != "pass" or calls != 1:
        raise RuntimeError("literal gold incorrectly controlled the semantic judge")
    draft = tasks["ACC-EXPORT-SAVE"]
    observed = observe_draft(draft["request"], block_draft_insert=True)
    rolled_back = grade_draft(observed, draft["expected"])
    step = rolled_back["steps"][1]
    if (step["attempts"], step["rows"], rolled_back["passed"]) != (1, 0, False) or no_draft_write(step):
        raise RuntimeError("rollback hid an attempted insert or grading missed the failed state")
    calibration = run_calibration()
    if calibration["support"]["disagreements"] != ["CAL-02", "CAL-03"] or calibration["completeness"]["known_abstained"] != ["CAL-07"]:
        raise RuntimeError("calibration no longer matches the worked data")
    return {"acceptance": acceptance, "guarded": guarded, "rolled_back": rolled_back,
            "calibration": calibration, "draft_boundaries": _stage_draft_boundaries(tasks),
            "judge": {"bad_citation": blocked, "equivalent": semantic, "calls": calls}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "acceptance"), default="acceptance")
    parser.add_argument("--repeats", type=int, choices=range(1, 21), default=2, metavar="1..20")
    parser.add_argument("--calibration", action="store_true", help="report the hand-scripted judge calibration")
    args = parser.parse_args()
    report = run_calibration() if args.calibration else run_split(args.split, repeats=args.repeats)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if args.calibration or report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
