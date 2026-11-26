"""L93 observations: two real local replacements on the same synthetic DBs."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from host import audit
from transport import Worker


# Independent expected literals, not built from the candidate returned draft.
GOLD = {
    "export": {"draft": ["需人工确认：导出保留期", "导出文件生成后保留 7 天。 超过保留期需重新发起导出。", ["KB-01", "KB-02"]],
               "quote": "导出文件生成后保留 7 天。", "key": ["EXPORT-POLICY", 1, "§1"], "reads": 2,
               "digest": "d45c47d3c0bbccfc503cd56ac79c53aa7fc2b1a3ef40d15f1586505ed448745a"},
    "sync": {"draft": ["需人工确认：同步时间", "同步任务每天 02:00 运行。", ["KB-03"]],
             "quote": "同步任务每天 02:00 运行。", "key": ["SYNC-POLICY", 1, "§1"], "reads": 1},
}


def worked():
    with TemporaryDirectory(prefix="p11-service-") as tmp:
        path = Path(tmp)
        with Worker(path) as initial:
            answer = initial.call("ask", topic="export")
            staged = initial.call("stage", job="export", revision=1, topic="export")
        before = audit(path)
        binding = staged["binding"]
        with Worker(path, profile="reviewer", outage=True) as unavailable:
            pending = unavailable.call("inspect", job="export")
            approval = unavailable.call("review", binding=binding, decision="approve")
            blocked = unavailable.call("recover", binding=binding)
        during = audit(path)
        with Worker(path, profile="reviewer") as replacement:
            resumed = replacement.call("recover", binding=binding)
        after = audit(path)
        return {"answer": answer, "staged": staged, "pending": pending, "approval": approval,
                "blocked": blocked, "resumed": resumed, "before": before, "during": during, "after": after,
                "pids": [initial.pid, unavailable.pid, replacement.pid]}


def transfer():
    with TemporaryDirectory(prefix="p11-persist-review-") as tmp:
        live, empty = Path(tmp) / "live", Path(tmp) / "empty"
        with Worker(live, profile="reviewer") as old:
            original = old.call("stage", job="sync", revision=1, topic="sync")
            revised = old.call("stage", job="sync", revision=2, topic="sync")
        with Worker(empty) as wrong_volume:
            missing = wrong_volume.call("inspect", job="sync")
        with Worker(live, profile="reviewer") as new:
            wrong = new.call("review", binding=original["binding"], decision="approve")
            decision = new.call("review", binding=revised["binding"], decision="deny")
        before = audit(live)
        with Worker(live, profile="reviewer", outage=True) as restarted:
            denied = restarted.call("recover", binding=revised["binding"])
        return {"original": original, "revised": revised, "missing": missing, "wrong": wrong,
                "decision": decision, "denied": denied, "before": before, "after": audit(live),
                "empty": audit(empty)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("worked", "transfer"))
    args = parser.parse_args()
    print(json.dumps((worked if args.case == "worked" else transfer)(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
