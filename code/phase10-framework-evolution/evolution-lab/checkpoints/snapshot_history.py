"""Read live and pinned checkpoints through the public LangGraph graph API."""

from contextlib import contextmanager
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from rehearsal import require

CHECKPOINT = "graph.sqlite"


@contextmanager
def graph_probe(directory):
    """Saver setup may touch SQLite; only open a disposable copy for readback."""
    with TemporaryDirectory(prefix="p10-graph-probe-") as tmp:
        probe = Path(tmp)
        shutil.copy2(directory / CHECKPOINT, probe / CHECKPOINT)
        yield probe


def view(snapshot):
    return {"thread": snapshot.config["configurable"]["thread_id"], "values": snapshot.values,
            "next": list(snapshot.next), "interrupts": [item.value for task in snapshot.tasks for item in task.interrupts]}


def checkpoint_id(snapshot_config):
    key = snapshot_config["configurable"].get("checkpoint_id")
    if not isinstance(key, str) or not key:
        raise AssertionError("public snapshot did not expose a checkpoint ID")
    return key


def history(graph, config):
    rows = list(graph.get_state_history(config))
    if not rows:
        raise AssertionError("expected nonempty checkpoint history")
    return rows


def pinned_view(graph, config, key):
    pinned = {"configurable": {**config["configurable"], "checkpoint_id": key}}
    snapshot = graph.get_state(pinned)  # Historical read only; never pass this config to invoke.
    require("explicit historical checkpoint identity", checkpoint_id(snapshot.config), key)
    return view(snapshot)


def frontier(graph, config):
    latest = graph.get_state(config)
    key = checkpoint_id(latest.config)
    rows = history(graph, config)
    require("thread lookup chose latest history entry", key, checkpoint_id(rows[0].config))
    live = view(latest)
    for row in rows[1:]:
        older_id = checkpoint_id(row.config)
        older = pinned_view(graph, config, older_id)
        if older_id != key and older != live:
            return {"id": key, "state": live, "older": {"id": older_id, "state": older}}
    raise AssertionError("fixture must contain a distinguishable earlier checkpoint")


def verify_start(graph, config, expected):
    actual = graph.get_state(config)
    require("working graph selected the expected latest checkpoint", checkpoint_id(actual.config), expected["id"])
    require("working graph latest state", view(actual), expected["state"])
    older = expected["older"]
    require("older checkpoint before invoke", pinned_view(graph, config, older["id"]), older["state"])
    return actual


def invoke_latest(graph, config, signal, **kwargs):
    # Build a fresh lookup regardless of what config a public snapshot may expose.
    lookup = {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
    return graph.invoke(signal, lookup, durability="sync", **kwargs)


def verify_advanced(graph, config, before, *, may_stay=False):
    latest = graph.get_state(config)
    key = checkpoint_id(latest.config)
    rows = history(graph, config)
    require("latest after continuation", key, checkpoint_id(rows[0].config))
    if key == before["id"] and not may_stay:
        raise AssertionError("the latest checkpoint did not advance")
    by_id = {checkpoint_id(row.config): row for row in rows}
    path, seen = [key], set()
    while path[-1] != before["id"]:
        ancestor = path[-1]
        row = by_id.get(ancestor)
        if ancestor in seen or row is None or row.parent_config is None:
            raise AssertionError("continuation did not descend from the selected latest checkpoint")
        seen.add(ancestor)
        path.append(checkpoint_id(row.parent_config))
    older = before["older"]
    require("older checkpoint after invoke", pinned_view(graph, config, older["id"]), older["state"])
    return {"id": key, "state": view(latest), "parent_path_to_previous_latest": path}
