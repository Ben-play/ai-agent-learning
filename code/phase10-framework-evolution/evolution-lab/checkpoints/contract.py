"""Stdlib application checkpoint contract, deliberately not a LangGraph file format."""

import argparse
import json
import sys

from host import THREAD, Host, LostReply, binding_fields, finish, initial_state, put_review, reply
import rehearsal

CHECKPOINT = "contract.json"


def read(directory):
    return json.loads((directory / CHECKPOINT).read_text(encoding="utf-8"))


def write(directory, snapshot):
    path = directory / CHECKPOINT
    # Atomic replacement for the sequential teaching worker, not power-loss simulation.
    partial = path.with_suffix(".tmp")
    partial.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
    partial.replace(path)


def inspect(directory):
    return read(directory)


def seed(directory, stop, encoding):
    """Carry out v1 steps and stop at one boundary; do not manufacture a v2 checkpoint."""
    host = Host(directory)
    old, current = host.stage()
    snapshot = {"thread": THREAD, "values": initial_state(current, encoding), "next": ["review"],
                "interrupts": [{"job": current.job, "revision": current.version}]}
    write(directory, snapshot)
    if stop != "pending":
        put_review(directory, binding_fields(current), "approve")
        advance(directory, 1, pause=True)
    lost = advance(directory, 1, lose=True) if stop == "committed" else None
    return binding_fields(old), lost


def advance(directory, version, *, pause=False, lose=False):
    snapshot, host, nodes = read(directory), Host(directory), []
    stop = host.preflight(snapshot, version)
    if stop is not None:
        host.result = reply(stop)
        return {"reply": host.result, "nodes": nodes, "calls": host.calls, "inserts": host.inserts}
    values = snapshot["values"]
    if snapshot["next"] == ["review"]:
        # This is the v1 resume order, also preserved by v2.
        nodes.append("review")
        values["status"] = "reviewed"
        snapshot.update(next=["apply_review"], interrupts=[])
        write(directory, snapshot)
    if host.result is None and not pause:
        if snapshot["next"] == ["apply_review"]:
            nodes.append("apply_review")
            try:
                status = host.apply(values, version, lose=lose)
            except LostReply:
                host.result = reply("reply_lost")  # fault observer, not a delivered business reply
            else:
                values.update(status=status, receipt=host.result["receipt"])
                if version == 2 and status in {"saved", "replayed"}:
                    nodes.append("finish")
                    values.update(finish())
                snapshot["next"] = []
                write(directory, snapshot)
        else:
            host.result = reply("not_runnable")
    return {"reply": host.result, "nodes": nodes, "calls": host.calls, "inserts": host.inserts}


def run(action, *, cases=None):
    return rehearsal.run(sys.modules[__name__], action, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seed", "compare", "fallback", "stage"))
    parser.add_argument("--case", action="append", metavar="NAME",
                        help="select a compare or fallback case; repeat for multiple cases")
    args = parser.parse_args()
    try:
        report = run(args.action, cases=args.case)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.action == "stage":
        print("P10 LOCAL CHECKPOINT CONTRACT PASSED")


if __name__ == "__main__" and not rehearsal.worker():
    main()
