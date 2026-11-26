"""In-memory task boundary exercise, not an A2A implementation or SDK test."""

import argparse
from dataclasses import dataclass, replace
from enum import Enum

from support_case import CASES, LIN, MEI, OTHER_MEI, Actor, Evidence


class State(str, Enum):
    WORKING = "WORKING"
    CANCELED = "CANCELED"
    COMPLETED = "COMPLETED"


PEER = "classroom-policy-desk"
WORKED_TASK, TRANSFER_TASK = "task-export", "task-sync"
_TASK_CASES = {WORKED_TASK: "export", TRANSFER_TASK: "sync"}


@dataclass(frozen=True)
class AgentCard:
    peer: str
    capability: str


@dataclass(frozen=True)
class Task:
    id: str
    owner: Actor
    peer: str
    state: State
    evidence: Evidence | None = None


@dataclass(frozen=True)
class PeerResult:
    task_id: str
    peer: str
    evidence: Evidence


@dataclass(frozen=True)
class Reply:
    code: str
    task: Task | None = None


class TaskDesk:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def discover(self) -> AgentCard:
        return AgentCard(PEER, "support-evidence")

    def submit(self, actor: Actor, task_id: str) -> Reply:
        # Actor comes from the classroom host, not from task/card data.
        if type(task_id) is not str or task_id not in _TASK_CASES:
            return Reply("not_found")
        if type(actor) is not Actor or actor != CASES[_TASK_CASES[task_id]].owner:
            return Reply("not_found")
        if task_id in self._tasks:
            return Reply("already_exists")
        task = Task(task_id, actor, PEER, State.WORKING)
        self._tasks[task_id] = task
        return Reply("ok", task)

    def _owned_task(self, actor: Actor, task_id: str) -> Task | None:
        task = self._tasks.get(task_id) if type(task_id) is str else None
        return task if task and type(actor) is Actor and task.owner == actor else None

    def get_task(self, actor: Actor, task_id: str) -> Reply:
        task = self._owned_task(actor, task_id)
        return Reply("ok", task) if task else Reply("not_found")

    def cancel_task(self, actor: Actor, task_id: str) -> Reply:
        task = self._owned_task(actor, task_id)
        if task is None:
            return Reply("not_found")
        if task.state is not State.WORKING:
            return Reply("not_cancelable")
        canceled = replace(task, state=State.CANCELED)
        self._tasks[task_id] = canceled
        return Reply("ok", canceled)

    def accept_result(self, expected_task_id: str, result: PeerResult) -> str:
        # Internal classroom handoff; the host remembers the originating task ID.
        # A matching peer label here is not evidence of authenticated peer identity.
        task = self._tasks.get(expected_task_id)
        if task is None:
            return "not_found"
        if result.task_id != task.id or result.peer != task.peer:
            return "binding_mismatch"
        if task.state is not State.WORKING:
            return "not_working"
        if result.evidence != CASES[_TASK_CASES[task.id]].evidence:
            return "evidence_mismatch"
        self._tasks[task.id] = replace(task, state=State.COMPLETED, evidence=result.evidence)
        return "accepted"


def classroom_result(task_id: str) -> PeerResult:
    """One of two fixed peer-result fixtures; never dispatched to a peer."""
    return PeerResult(task_id, PEER, CASES[_TASK_CASES[task_id]].evidence)


def worked() -> None:
    desk = TaskDesk()
    print("能力：", desk.discover().capability)
    denied = desk.submit(OTHER_MEI, WORKED_TASK)
    working = desk.submit(MEI, WORKED_TASK)
    foreign = desk.get_task(OTHER_MEI, WORKED_TASK)
    before = desk.get_task(MEI, WORKED_TASK)
    canceled = desk.cancel_task(MEI, WORKED_TASK)
    late = desk.accept_result(WORKED_TASK, classroom_result(WORKED_TASK))
    after = desk.get_task(MEI, WORKED_TASK)
    assert denied == foreign == Reply("not_found")
    assert working == before and before.task and before.task.state is State.WORKING
    assert canceled == after and after.task and after.task.state is State.CANCELED
    assert late == "not_working" and after.task.evidence is None
    print(f"导出：{foreign.code} / {before.task.state.value} → {after.task.state.value} / {late} / 无证据")
    print("L90 ACCEPTED")


def transfer() -> None:
    desk = TaskDesk()
    started = desk.submit(MEI, TRANSFER_TASK)
    other = desk.submit(MEI, WORKED_TASK)
    denied = desk.cancel_task(LIN, TRANSFER_TASK)
    wrong_task = desk.accept_result(TRANSFER_TASK, classroom_result(WORKED_TASK))
    assert denied == Reply("not_found") and wrong_task == "binding_mismatch"
    assert desk.get_task(MEI, TRANSFER_TASK) == started
    assert desk.get_task(MEI, WORKED_TASK) == other
    result = classroom_result(TRANSFER_TASK)
    accepted = desk.accept_result(TRANSFER_TASK, result)
    done = desk.get_task(MEI, TRANSFER_TASK)
    late_cancel = desk.cancel_task(MEI, TRANSFER_TASK)
    assert accepted == "accepted" and late_cancel == Reply("not_cancelable")
    expected = Evidence("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。")
    assert done == Reply("ok", Task("task-sync", MEI, PEER, State.COMPLETED, expected))
    assert desk.accept_result(TRANSFER_TASK, result) == "not_working"
    assert done == desk.get_task(MEI, TRANSFER_TASK)
    print(f"同步：{denied.code} / {wrong_task} / {done.task.state.value} / {late_cancel.code}")
    print("L90 TRANSFER PASSED")


def main() -> None:
    if not __debug__:
        raise SystemExit("请不要用 -O 运行自检")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", action="store_true", help="只运行独立变式")
    if not parser.parse_args().variant:
        worked()
    transfer()


if __name__ == "__main__":
    main()
