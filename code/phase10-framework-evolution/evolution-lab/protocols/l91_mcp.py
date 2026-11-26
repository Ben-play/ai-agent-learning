"""Local policy-read boundary exercise, not an MCP server or SDK test."""

import argparse
from dataclasses import dataclass, replace

from support_case import CASES, LIN, MEI, OTHER_MEI, Actor, Evidence

ISSUER = "classroom-support-host"
AUDIENCE = "classroom-policy-reader"
READ_SCOPE = "policy:read"
MAX_ATTEMPTS = 12
_OWNERS = {key: case.owner for key, case in CASES.items()}


@dataclass(frozen=True)
class Context:
    issuer: str
    audience: str
    actor: Actor
    scopes: frozenset[str]


SUPPORT_CONTEXT = Context(ISSUER, AUDIENCE, MEI, frozenset({READ_SCOPE}))


@dataclass(frozen=True)
class Reply:
    code: str
    evidence: Evidence | None = None


@dataclass(frozen=True)
class AuditEvent:
    operation: str
    reason: str


class ReadObserver:
    """Fixed fixture store: record entry into the read method, not a reply flag."""

    def __init__(self) -> None:
        self._reads: list[str] = []

    @property
    def reads(self) -> tuple[str, ...]:
        return tuple(self._reads)

    def read(self, topic: str) -> Evidence:
        self._reads.append(topic)
        return CASES[topic].evidence


class PolicyBoundary:
    def __init__(self, store: ReadObserver) -> None:
        self._store = store
        self._audit: list[AuditEvent] = []

    @property
    def audit(self) -> tuple[AuditEvent, ...]:
        return tuple(self._audit)

    def read_policy(self, context: Context | None, args: object) -> Reply:
        if len(self._audit) >= MAX_ATTEMPTS:
            return Reply("budget_exhausted")
        if context is None:
            return self._reject("missing_context")
        if type(context) is not Context or type(context.actor) is not Actor:
            return self._reject("invalid_context")
        if type(context.issuer) is not str or context.issuer != ISSUER:
            return self._reject("issuer_mismatch")
        if type(context.audience) is not str or context.audience != AUDIENCE:
            return self._reject("audience_mismatch")
        if type(context.scopes) is not frozenset or READ_SCOPE not in context.scopes:
            return self._reject("insufficient_scope")
        if type(args) is not dict or len(args) != 1 or any(type(key) is not str for key in args):
            return self._reject("invalid_arguments", "invalid_arguments")
        topic = args.get("topic")
        if type(topic) is not str or topic not in _OWNERS:
            return self._reject("invalid_arguments", "invalid_arguments")
        if context.actor != _OWNERS[topic]:
            return self._reject("owner_mismatch")

        evidence = self._store.read(topic)
        self._audit.append(AuditEvent("read_policy", "ok"))
        return Reply("ok", evidence)

    def _reject(self, reason: str, code: str = "denied") -> Reply:
        self._audit.append(AuditEvent("read_policy", reason))
        return Reply(code)


def worked() -> None:
    store = ReadObserver()
    boundary = PolicyBoundary(store)
    args = {"topic": "export"}
    for context, reason in (
        (None, "missing_context"),
        (replace(SUPPORT_CONTEXT, issuer="classroom-other-issuer"), "issuer_mismatch"),
        (replace(SUPPORT_CONTEXT, audience="classroom-index-reader"), "audience_mismatch"),
        (replace(SUPPORT_CONTEXT, scopes=frozenset({"queue:read"})), "insufficient_scope"),
        (replace(SUPPORT_CONTEXT, actor=LIN), "owner_mismatch"),
    ):
        reply = boundary.read_policy(context, args)
        assert reply == Reply("denied") and store.reads == ()
        assert boundary.audit[-1] == AuditEvent("read_policy", reason)
        print(f"导出：{reason} / {reply.code} / 读 {len(store.reads)} 次")
    reply = boundary.read_policy(SUPPORT_CONTEXT, {"topic": True})
    assert reply == Reply("invalid_arguments") and store.reads == ()
    assert boundary.audit[-1] == AuditEvent("read_policy", "invalid_arguments")
    print(f"导出：{reply.code} / 读 {len(store.reads)} 次")
    reply = boundary.read_policy(SUPPORT_CONTEXT, args)
    assert reply == Reply("ok", Evidence("EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。"))
    assert store.reads == ("export",) and boundary.audit[-1] == AuditEvent("read_policy", "ok")
    assert reply.evidence is not None
    print(f"导出：{reply.code} / 读 {len(store.reads)} 次 / {reply.evidence.text}")
    print("L91 ACCEPTED")


def transfer() -> None:
    store = ReadObserver()
    boundary = PolicyBoundary(store)
    args = {"topic": "sync"}
    assert boundary.read_policy(replace(SUPPORT_CONTEXT, actor=OTHER_MEI), args) == Reply("denied")
    assert boundary.read_policy(SUPPORT_CONTEXT, {**args, "note": "只用于变式"}) == Reply("invalid_arguments")
    assert store.reads == ()
    assert boundary.read_policy(SUPPORT_CONTEXT, args) == Reply(
        "ok", Evidence("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"))
    revoked = replace(SUPPORT_CONTEXT, scopes=frozenset())
    assert boundary.read_policy(revoked, args) == Reply("denied") and store.reads == ("sync",)
    assert boundary.audit == tuple(AuditEvent("read_policy", reason) for reason in (
        "owner_mismatch", "invalid_arguments", "ok", "insufficient_scope"))
    print(f"同步：{[event.reason for event in boundary.audit]} / 读 {len(store.reads)} 次")
    print("L91 TRANSFER PASSED")


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
