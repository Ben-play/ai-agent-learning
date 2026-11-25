"""Synthetic telemetry with a real, local batch receiver. Neither an OTel SDK nor OTLP."""

from copy import deepcopy


class FixedClock:
    def __init__(self, now_ms=0):
        self._now_ms = 0
        self.advance(now_ms)

    @property
    def now_ms(self):
        return self._now_ms

    def advance(self, elapsed_ms):
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("advance by nonnegative integer milliseconds")
        self._now_ms += elapsed_ms


class LocalReceiver:
    """Hold projected rows in memory, with demo read roles and TTL from receipt."""

    def __init__(self, clock, *, retention_ms=3000):
        if type(retention_ms) is not int or retention_ms <= 0:
            raise ValueError("retention_ms must be a positive integer")
        self.clock = clock
        self.retention_ms = retention_ms
        self._batches = {}

    def receive(self, rows):
        """Trusted same-process ingress; caller must project before invoking it."""
        self.purge()
        trace_id = rows[0]["trace_id"]
        if trace_id in self._batches:
            raise ValueError("duplicate trace id")
        self._batches[trace_id] = (self.clock.now_ms + self.retention_ms, deepcopy(tuple(rows)))

    def read_trace(self, trace_id, *, role):
        if role != "trace_reader":
            raise PermissionError("trace access denied")
        self.purge()
        batch = self._batches.get(trace_id)
        return deepcopy(batch[1]) if batch is not None else ()

    def purge(self):
        expired = [key for key, (deadline, _) in self._batches.items()
                   if self.clock.now_ms >= deadline]
        for key in expired:
            del self._batches[key]
        return len(expired)


_STATES = ("waiting_approval", "executing", "succeeded", "failed")


def _project_attributes(name, raw):
    """Only construct allowlisted metadata; never copy a raw field by default."""
    if name == "retrieval":
        return {"gen_ai.operation.name": "retrieval", "phase8.retrieved_count": raw["phase8.retrieved_count"]}
    if name == "chat lesson-model":
        attrs = {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "synthetic_fixture",
                 "gen_ai.request.model": "lesson-model"}
        for key in ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"):
            value = raw.get(key)
            if type(value) is int and value >= 0:
                attrs[key] = value
        if raw.get("error.type") == "synthetic_model_error":
            attrs["error.type"] = "synthetic_model_error"
        return attrs
    if name == "execute_tool draft_preview":
        return {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "draft_preview",
                "gen_ai.tool.type": "function"}
    if name == "approval.check" and raw["phase8.approval"] in ("pending", "granted"):
        return {"phase8.approval": raw["phase8.approval"]}
    if name in ("state.snapshot", "terminal.snapshot") and raw["phase8.state"] in _STATES:
        return {"phase8.state": raw["phase8.state"], "phase8.state_since_ms": raw["phase8.state_since_ms"]}
    return {}


def run_trial(receiver, *, task, trial, trace_key, usage=(12, 4), outcome="succeeded", extra_fields=None):
    """Generate one read-only synthetic scenario and send projected spans to receiver.

    usage is (input_tokens, output_tokens); use None for an unknown count. Numeric
    IDs are fixture codes, not production IDs. extra_fields simulates accidental
    capture upstream of projection; only supply synthetic values.
    """
    if any(type(n) is not int or not 0 < n < 2**128 for n in (task, trial, trace_key)):
        raise ValueError("IDs must be positive integers below 2**128")
    if outcome not in _STATES:
        raise ValueError("unknown fixture outcome")
    input_tokens, output_tokens = usage
    trace_id = f"{trace_key:032x}"
    root_id = "0000000000000001"
    clock = receiver.clock
    origin = clock.now_ms
    rows = []

    def emit(name, start, *, raw=None, status="UNSET", root=False):
        fields = dict(extra_fields or {})
        fields.update(raw or {})  # Fixture metadata takes precedence over extra fields.
        attrs = {"phase8.task_id": f"task-{task}", "phase8.trial_id": f"trial-{trial}"}
        attrs.update(_project_attributes(name, fields))
        if root and status == "ERROR":
            attrs["error.type"] = "synthetic_model_error"
        rows.append({"trace_id": trace_id, "span_id": root_id if root else f"{len(rows)+2:016x}",
                     "parent_span_id": None if root else root_id, "name": name, "kind": "INTERNAL",
                     "start_offset_ms": start - origin, "duration_s": (clock.now_ms - start) / 1000,
                     "status": status, "attributes": attrs})

    def step(name, duration_ms, *, raw=None, status="UNSET"):
        start = clock.now_ms
        clock.advance(duration_ms)
        emit(name, start, raw=raw, status=status)

    evidence = ("SYNTHETIC EVIDENCE",)  # The fixture's only local match; never exported verbatim.
    step("retrieval", 30, raw={"gen_ai.retrieval.query.text": "SYNTHETIC QUERY",
                               "evidence_body": evidence, "phase8.retrieved_count": len(evidence)})
    status = "ERROR" if outcome == "failed" else "UNSET"
    step("chat lesson-model", 250,
         raw={"gen_ai.input.messages": "SYNTHETIC PROMPT", "gen_ai.output.messages": "SYNTHETIC REPLY",
              "gen_ai.usage.input_tokens": input_tokens, "gen_ai.usage.output_tokens": output_tokens,
              "error.type": "synthetic_model_error" if status == "ERROR" else None},
         status=status)
    if outcome != "failed":
        step("execute_tool draft_preview", 20,
             raw={"gen_ai.tool.call.arguments": "SYNTHETIC DRAFT",
                  "gen_ai.tool.call.result": "SYNTHETIC PREVIEW"})
        if outcome == "waiting_approval":
            step("approval.check", 0, raw={"phase8.approval": "pending"})
        else:
            clock.advance(400)  # Idle approval interval; not execution time.
            step("approval.check", 0, raw={"phase8.approval": "granted"})
            if outcome == "succeeded":
                step("agent.execute", 120)  # A timed fixture mark, not a real executor.
    snapshot = "state.snapshot" if outcome in ("waiting_approval", "executing") else "terminal.snapshot"
    step(snapshot, 0, raw={"phase8.state": outcome, "phase8.state_since_ms": clock.now_ms})
    emit("agent.trial", origin, status=status, root=True)
    receiver.receive((rows[-1], *rows[:-1]))
    return trace_id


def summarize_trace(receiver, trace_id, *, role):
    """Read a fixture's trace as a versioned, JSON-ready handoff summary."""
    rows = receiver.read_trace(trace_id, role=role)
    if not rows:
        raise ValueError("trace is missing or expired")
    tags = rows[0]["attributes"]
    return {"summary_version": "telemetry-summary-v1", "projection_version": "telemetry-projection-v1",
            "otel_genai_version": "v0.1.0", "origin": "separate-local-telemetry-fixture", "trace_id": trace_id,
            "task_id": tags["phase8.task_id"], "trial_id": tags["phase8.trial_id"],
            "terminal": rows[-1]["attributes"]["phase8.state"],
            "spans": [{"name": row["name"], "duration_s": row["duration_s"]} for row in rows]}


def evaluate_alert(receiver, trace_id, *, execution_budget_ms, approval_sla_ms):
    """Synthetic internal alert consumer; no pages, no network, no action."""
    if any(type(x) is not int or x <= 0 for x in (execution_budget_ms, approval_sla_ms)):
        raise ValueError("budgets must be positive integer milliseconds")
    spans = receiver.read_trace(trace_id, role="trace_reader")
    if not spans:
        return {"signal": "trace_missing", "state": None, "age_ms": None}
    snapshot = spans[-1]["attributes"]
    state = snapshot["phase8.state"]
    age_ms = receiver.clock.now_ms - snapshot["phase8.state_since_ms"]
    signal = None
    if state == "executing" and age_ms >= execution_budget_ms:
        signal = "execution_timeout"
    elif state == "waiting_approval" and age_ms >= approval_sla_ms:
        signal = "approval_sla"
    return {"signal": signal, "state": state, "age_ms": age_ms}


def run_acceptance():
    """Offline gate for the default teaching fixture; return normally or raise."""
    clock = FixedClock()
    receiver = LocalReceiver(clock, retention_ms=1000)
    trace_id = run_trial(receiver, task=71, trial=1, trace_key=711, usage=(None, 0),
                         outcome="waiting_approval", extra_fields={"credential": "GATE_CANARY"})
    spans = receiver.read_trace(trace_id, role="trace_reader")
    tags = {"phase8.task_id": "task-71", "phase8.trial_id": "trial-1"}
    expected = [
        ("agent.trial", tags),
        ("retrieval", {**tags, "gen_ai.operation.name": "retrieval", "phase8.retrieved_count": 1}),
        ("chat lesson-model", {**tags, "gen_ai.operation.name": "chat", "gen_ai.provider.name": "synthetic_fixture",
                               "gen_ai.request.model": "lesson-model", "gen_ai.usage.output_tokens": 0}),
        ("execute_tool draft_preview", {**tags, "gen_ai.operation.name": "execute_tool",
                                        "gen_ai.tool.name": "draft_preview", "gen_ai.tool.type": "function"}),
        ("approval.check", {**tags, "phase8.approval": "pending"}),
        ("state.snapshot", {**tags, "phase8.state": "waiting_approval", "phase8.state_since_ms": 300}),
    ]
    markers = ("GATE_CANARY", "SYNTHETIC QUERY", "SYNTHETIC EVIDENCE", "SYNTHETIC PROMPT", "SYNTHETIC REPLY",
               "SYNTHETIC DRAFT", "SYNTHETIC PREVIEW")
    if any(marker in repr(spans) for marker in markers):
        raise AssertionError("sensitive fixture escaped projection")
    if [(s["name"], s["attributes"]) for s in spans] != expected:
        raise AssertionError("unexpected waiting span projection")
    if not all(s["trace_id"] == trace_id and s["parent_span_id"] == spans[0]["span_id"] for s in spans[1:]):
        raise AssertionError("span correlation failed")
    if spans[2]["duration_s"] != 0.25 or type(spans[2]["attributes"]["gen_ai.usage.output_tokens"]) is not int:
        raise AssertionError("unexpected model duration or usage type")
    try:
        receiver.read_trace(trace_id, role="support")
    except PermissionError:
        pass
    else:
        raise AssertionError("unprivileged trace read succeeded")
    clock.advance(500)
    if evaluate_alert(receiver, trace_id, execution_budget_ms=100, approval_sla_ms=500)["signal"] != "approval_sla":
        raise AssertionError("waiting age was misclassified")
    clock.advance(500)
    if receiver.purge() != 1 or receiver.read_trace(trace_id, role="trace_reader"):
        raise AssertionError("expired trace was retained")
