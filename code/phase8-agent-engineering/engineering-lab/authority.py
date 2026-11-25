"""Defensive proposal filtering at a local training-draft dispatch boundary."""

from dataclasses import dataclass, field
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory

SAVE = "save_training_draft"
SCOPE = "draft:save"  # Same label as the Phase 6 MCP lab; no token verification here.


@dataclass
class DraftAuthority:
    """A host creates this from trusted state; a proposer supplies only action/binding."""

    actor: object
    current: object | None
    approved: object | None
    scopes: frozenset[str]
    draft_allowed: bool
    proposals: list[tuple[str, str]] = field(default_factory=list, init=False)
    dispatches: list[str] = field(default_factory=list, init=False)

    @property
    def extra_proposals(self):
        # Missing scope/approval is not automatically a task-irrelevant proposal.
        return sum(reason in {"out_of_profile", "intent_changed"} for _, reason in self.proposals)

    def submit(self, action, binding, *, save):
        if not self.draft_allowed or action != SAVE:
            reason = "out_of_profile"
        elif SCOPE not in self.scopes:
            reason = "scope_required"
        elif self.current is None or self.actor != self.current.actor:
            reason = "not_available"
        elif type(binding) is not type(self.current) or binding != self.current:
            reason = "intent_changed"
        elif self.approved != self.current:
            reason = "approval_required"
        else:
            reason = "allowed"
        self.proposals.append((action, reason))
        if reason != "allowed":
            return reason, None
        self.dispatches.append(action)  # A call attempt, not a commit or a receipt.
        return reason, save(self.actor, self.current)


@dataclass(frozen=True)
class DraftSuggestion:
    action: str
    binding: object
    preview: str


def build_suggestion(evidence_text, sample_label, *, action, binding):
    """Render a plain-text training preview; the label supplies no authority."""
    return DraftSuggestion(action, binding, f"{evidence_text}〔{sample_label}〕")


def run_case(case, *, sample_label="培训样张"):
    """Return effects observed around an ordinary synthetic proposal, in a new database."""
    if case not in {"read_only", "read_scope", "unapproved", "approved", "revised", "stale_approval",
                    "other_tenant", "other_actor", "changed_payload", "unknown_action"}:
        raise ValueError("unknown teaching case")
    here = Path(__file__).resolve().parent
    code = here.parents[1]
    h = runpy.run_path(str(code / "phase5-agent-harness/harness-lab/main.py"))
    rag = runpy.run_path(str(code / "phase7-data-rag/rag-lab/lab.py"))
    saved_drafts = runpy.run_path(str(here / "observations.py"))["saved_drafts"]
    actor, job = h["Actor"]("support", "mei"), "training-15"
    requester = {"other_tenant": h["Actor"]("operations", "mei"),
                 "other_actor": h["Actor"]("support", "lin")}.get(case, actor)
    scopes = frozenset({"evidence:read"} if case == "read_scope" else {"evidence:read", SCOPE})
    writes = []
    with rag["open_demo"]() as evidence:
        source = evidence.source(actor.tenant, actor.name, ("SYNC-POLICY", 1, "§1"))
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "training.sqlite3"
        with h["open_store"](path, on_draft_write_attempt=writes.append) as store:
            staged = store.stage(actor, job, 1, "同步任务几点运行？")
            current = store.stage(actor, job, 2, h["QUESTION"]) if case in {"revised", "stale_approval"} else staged
            authority = DraftAuthority(requester, current.binding, None if case == "unapproved" else staged.binding,
                                       scopes, case != "read_only")
            action = "preview_label" if case == "unknown_action" else SAVE
            proposed = current.binding if case == "stale_approval" else staged.binding
            if case == "changed_payload":
                # Same owner, job and revision; a separate fixture supplies different draft content.
                with h["open_store"](Path(tmp) / "alternate.sqlite3") as alternate:
                    proposed = alternate.stage(actor, job, 1, h["QUESTION"]).binding
            suggestion = build_suggestion(source.text, sample_label, action=action, binding=proposed)
            reason, result = authority.submit(suggestion.action, suggestion.binding, save=lambda owner, binding:
                                              store.resume(owner, job, binding, h["Review"].APPROVE))
        with h["open_store"](path) as verifier:
            checkpoint = verifier.checkpoint(actor, job)
        committed = saved_drafts(path)
    receipt_id = result.op_id if result else None
    draft = result.draft if result else None
    return {"reason": reason, "quote": suggestion.preview, "proposals": len(authority.proposals),
            "extra_proposals": authority.extra_proposals, "dispatches": len(authority.dispatches),
            "writes": len(writes), "rows": len(committed), "checkpoint": checkpoint.status,
            "receipt": bool(receipt_id), "scopes": tuple(sorted(authority.scopes)),
            "approved_revision": authority.approved.version if authority.approved else None,
            "committed": committed, "write_ids": tuple(writes), "checkpoint_receipt": checkpoint.op_id,
            "receipt_id": receipt_id, "result_status": result.status if result else None,
            "result_payload": [draft.title, draft.body, list(draft.source_ids)] if draft else None}
