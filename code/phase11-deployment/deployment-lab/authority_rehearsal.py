"""L95: sequential fixed-clock and scoped authority observations on a scratch store."""

import argparse
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from host import Host, audit


class FixedClock:
    def __init__(self):
        self.seconds = 0

    def __call__(self):
        return self.seconds


def worked():
    with TemporaryDirectory(prefix="p11-authority-") as tmp:
        root, clock = Path(tmp), FixedClock()
        throttle_dir = root / "quota"
        quota = Host(throttle_dir, quota=2, window=10, clock=clock)
        requests = [("support", "ask", {"topic": "export"}),
                    ("lin", "ask", {"topic": "export"}),
                    ("support", "ask", {"topic": "export"}),
                    ("other", "ask", {"topic": "export"})]
        limited = [quota.dispatch(*request) for request in requests]
        clock.seconds = 10
        reopened = quota.dispatch("support", "ask", {"topic": "export"})
        review_dir = root / "review"
        tight = Host(review_dir, read_cap=1)
        over = tight.dispatch("support", "stage", {"job": "export", "topic": "export", "revision": 1})
        forbidden = tight.dispatch("support", "publish", {"note": "classroom-no-audit-content"})
        bait = tight.dispatch("support", "ask", {"topic": "sync", "actor": "reviewer"})
        staged = tight.dispatch("support", "stage", {"job": "sync", "topic": "sync", "revision": 1})
        binding = staged["binding"]
        before_wrong_role = audit(review_dir)
        no_role = tight.dispatch("support", "review", {"binding": binding, "decision": "approve"})
        after_wrong_role = audit(review_dir)
        decision = tight.dispatch("reviewer", "review", {"binding": binding, "decision": "deny"})
        after_decision = audit(review_dir)
        denied = tight.dispatch("reviewer", "recover", {"binding": binding})
        after_recovery = audit(review_dir)

        # Approval is a separate control; it must not change the denial store.
        sync_dir = root / "cap-one-sync"
        sync = Host(sync_dir, read_cap=1)
        sync_stage = sync.dispatch("support", "stage", {"job": "sync", "topic": "sync", "revision": 1})
        sync_binding = sync_stage["binding"]
        approval = sync.dispatch("reviewer", "review", {"binding": sync_binding, "decision": "approve"})
        recovery = sync.dispatch("reviewer", "recover", {"binding": sync_binding})
        return {"limited": limited, "reopened": reopened, "over": over, "forbidden": forbidden, "bait": bait,
                "staged": staged, "no_role": no_role, "decision": decision, "denied": denied,
                "before_wrong_role": before_wrong_role, "after_wrong_role": after_wrong_role,
                "after_decision": after_decision, "state": after_recovery,
                "events": list(tight.events), "quota_state": audit(throttle_dir),
                "cap_one_sync": {"stage": sync_stage, "approval": approval, "recovery": recovery, "state": audit(sync_dir)}}


def assert_denial(row):
    """Check the folded example against the fixture contract and independent readback."""
    draft = ["需人工确认：同步时间", "同步任务每天 02:00 运行。", ["KB-03"]]
    binding = {"tenant": "support", "actor": "mei", "job": "sync", "action": "save_local_draft",
               "revision": 1, "digest": "08ec8e28e06fccb6c71236ddcfce8913ed15fa1939b10a19cfe703e85b8a583c"}
    assert row["staged"] == {"status": "pending", "binding": binding, "draft": draft, "receipt": None,
                             "read_calls": 1, "inserts": []}
    for step, status in (("no_role", "forbidden"), ("decision", "review_recorded"), ("denied", "denied")):
        assert row[step] == {"status": status, "receipt": None, "draft": None, "read_calls": 0, "inserts": []}, step

    checkpoint = ["support", "mei", "sync", 1, draft, "pending", None]
    before = row["before_wrong_role"]
    assert before == {"schema": 1, "checkpoints": [checkpoint], "reviews": [],
                      "saved": [], "revocations": [], "extras": []}, "expected only the pending sync checkpoint"
    assert row["after_wrong_role"] == before, "wrong role must not alter any audited state"
    deny = ["support", "mei", "sync", "save_local_draft", 1, binding["digest"], "deny"]
    after_decision = row["after_decision"]
    assert after_decision == {**before, "reviews": [deny]}, "record only the exact bound deny"
    assert row["state"] == {**after_decision, "checkpoints": [[*checkpoint[:5], "denied", None]]}, (
        "recovery must change only the checkpoint status from pending to denied"
    )

    for event in row["events"]:
        assert set(event) == {"event", "trace_id", "result"}
        assert re.fullmatch(r"[0-9a-f]{24}", event["trace_id"])
    wrong, decision, recovery = row["events"][-3:]
    assert [(e["event"], e["result"]) for e in (wrong, decision, recovery)] == [
        ("review", "forbidden"), ("review", "review_recorded"), ("recover", "denied")]
    assert wrong["trace_id"] != decision["trace_id"] == recovery["trace_id"]


def transfer():
    with TemporaryDirectory(prefix="p11-withhold-") as tmp:
        directory = Path(tmp)
        lab = Host(directory)
        staged = lab.dispatch("support", "stage", {"job": "sync", "topic": "sync", "revision": 1})
        binding = staged["binding"]
        hidden = lab.dispatch("other", "inspect", {"job": "sync"})
        lab.dispatch("reviewer", "review", {"binding": binding, "decision": "approve"})
        saved = lab.dispatch("reviewer", "recover", {"binding": binding})
        before = audit(directory)
        lab.dispatch("reviewer", "fixture_revoke", {"topic": "sync"}, fixtures=True)
        restarted = Host(directory)
        withheld = restarted.dispatch("reviewer", "recover", {"binding": binding})
        intake = restarted.dispatch("support", "ask", {"topic": "sync"})
        other = restarted.dispatch("support", "ask", {"topic": "export"})
        return {"hidden": hidden, "saved": saved, "before": before, "withheld": withheld,
                "intake": intake, "other": other, "after": audit(directory),
                "before_events": list(lab.events), "after_events": list(restarted.events)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("worked", "transfer"))
    args = parser.parse_args()
    print(json.dumps((worked if args.case == "worked" else transfer)(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
