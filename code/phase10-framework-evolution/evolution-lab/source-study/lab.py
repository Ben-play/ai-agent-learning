"""Read-only comparison of course-owned records; never import or run Hermes."""

from dataclasses import dataclass, replace
from hashlib import sha256

VERSION = "source-boundaries-v1"
HERMES_REVISION = "8fc0374447313e276f6b9a2764bfc750190c966a"


@dataclass(frozen=True)
class Binding:
    tenant: str
    actor: str
    task: str
    action: str
    revision: int
    digest: str


@dataclass(frozen=True)
class Task:
    binding: Binding
    operation_id: str | None
    committed_hint: bool


@dataclass(frozen=True)
class Receipt:
    operation_id: str
    binding: Binding
    body: str


@dataclass(frozen=True)
class Records:
    transcript: tuple[str, ...]
    task: Task
    approval: Binding | None
    receipts: tuple[Receipt, ...]


def inspect(records: Records, *, tenant: str, actor: str) -> dict:
    """Classify independent evidence. This function cannot dispatch or save."""
    task = records.task
    binding = task.binding
    if (tenant, actor) != (binding.tenant, binding.actor):
        return {"status": "not_available", "receipt": None}
    bound_rows = [row for row in records.receipts if row.binding == binding]
    if task.committed_hint or task.operation_id is not None:
        by_id = [row for row in records.receipts if row.operation_id == task.operation_id]
        if (task.operation_id and len(by_id) == len(bound_rows) == 1 and by_id == bound_rows
                and sha256(by_id[0].body.encode("utf-8")).hexdigest() == binding.digest):
            return {"status": "receipt_verified", "receipt": task.operation_id}
        return {"status": "reconcile", "receipt": None}
    if bound_rows:
        # Do not treat a missing operation reference as permission for another save.
        return {"status": "reconcile", "receipt": None}
    if records.approval != binding:
        return {"status": "wait_for_review", "receipt": None}
    return {"status": "ready_for_host_review", "receipt": None}


BODY = "同步任务每天 02:00 运行。"
BOUND = Binding("support", "mei", "sync-training", "save_local_draft", 2, sha256(BODY.encode("utf-8")).hexdigest())
OP = "fixture-receipt-02"
PENDING = Records(("已恢复客服会话。", "记录中的回复曾显示已确认。"), Task(BOUND, None, False), None, ())
COMMITTED = replace(PENDING, task=Task(BOUND, OP, True), approval=BOUND,
                    receipts=(Receipt(OP, BOUND, BODY),))


def main():
    print(VERSION)
    for name, records in (("transcript-only", PENDING), ("receipt-present", COMMITTED),
                          ("missing-receipt", replace(COMMITTED, receipts=()))):
        print(name, inspect(records, tenant="support", actor="mei"))


if __name__ == "__main__":
    main()
