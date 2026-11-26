"""L81: deterministic catalogue comparison over fixed, local business reads only."""

from dataclasses import asdict, dataclass
import json

COHORT_VERSION = "phase9-tools/v1"
STRATEGIES = ("small", "all-authorized", "lazy")


@dataclass(frozen=True)
class Principal:
    tenant: str
    actor: str


SUPPORT = Principal("support", "mei")
OPERATIONS = Principal("operations", "mei")


@dataclass(frozen=True)
class Record:
    tenant: str
    doc_id: str
    version: int
    locator: str
    text: str


@dataclass(frozen=True)
class Tool:
    owner: Principal
    scope: str
    topic: str
    description: str
    records: tuple[Record, ...]


CATALOG = {
    "read_retention": Tool(SUPPORT, "policy:read", "retention", "查客服导出文件留存期。", (
        Record("support", "EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。"),
        Record("support", "EXPORT-OPS", 1, "§2", "导出文件过期后，需重新发起导出。"),
    )),
    "read_retention_notes": Tool(SUPPORT, "policy:read", "retention", "查导出留存术语说明。", (
        Record("support", "EXPORT-NOTES", 1, "§1", "留存期从文件生成时起算。"),
    )),
    "read_sync": Tool(SUPPORT, "policy:read", "schedule", "查客服每日同步时间。", (
        Record("support", "SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"),
    )),
    "read_duty": Tool(SUPPORT, "desk:read", "duty", "查客服交班值守时间。", (
        Record("support", "DUTY-DESK", 1, "§1", "值守每天 09:00 开始。"),
    )),
    "read_queue": Tool(SUPPORT, "desk:read", "queue", "查培训工单的分组说明。", (
        Record("support", "QUEUE-DESK", 1, "§1", "培训工单归入演练队列。"),
    )),
    "read_labels": Tool(SUPPORT, "desk:read", "labels", "查本地客服草稿标签说明。", (
        Record("support", "LABEL-DESK", 1, "§1", "培训样张必须标记为演练。"),
    )),
    "read_ops_retention": Tool(OPERATIONS, "policy:read", "retention", "查运维导出留存期。", (
        Record("operations", "EXPORT-POLICY", 1, "§1", "运维导出文件保留 30 天。"),
    )),
}
TOPICS = frozenset(tool.topic for tool in CATALOG.values())


@dataclass
class Host:
    principal: Principal = SUPPORT
    scopes: frozenset[str] = frozenset({"policy:read", "desk:read"})

    def allows(self, name: str) -> bool:
        tool = CATALOG.get(name)
        return tool is not None and tool.owner == self.principal and tool.scope in self.scopes


@dataclass(frozen=True)
class Limits:
    calls: int = 2
    rows: int = 2

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in (self.calls, self.rows)):
            raise ValueError("limits must be nonnegative integers")


def serialize(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def definition(name: str) -> dict:
    tool = CATALOG[name]
    return {"name": name, "description": tool.description, "input_schema": {
        "type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 2}},
        "required": ["limit"], "additionalProperties": False,
    }}


def ranked(pool, topic: str) -> tuple[str, ...]:
    """Exact topic match; equal matches sort by stable name, never insertion order."""
    return tuple(sorted(name for name in pool if CATALOG[name].topic == topic))


class Session:
    """One task: catalogue visibility, a live host gate and an aggregate read budget."""

    def __init__(self, strategy: str, host: Host, limits=Limits()):
        if strategy not in STRATEGIES:
            raise ValueError("unknown strategy")
        self.strategy, self.host, self.limits = strategy, host, limits
        self.principal = host.principal  # The host also binds an in-flight session to its initial identity.
        allowed = {name for name in CATALOG if host.allows(name)}
        self.visible = (allowed if strategy == "all-authorized" else
                        allowed & {"read_retention"} if strategy == "small" else set())
        self.manifest = [{"type": "definitions", "tools": [definition(name) for name in sorted(self.visible)]}]
        if strategy == "lazy":
            self.manifest.append({"type": "discovery", "description": "按预设业务主题查已授权工具，最多返回一个名称。"})
        self.results = []
        self.records = []
        self.reads = []  # Only incremented inside the actual local read boundary.

    def select(self, topic: str) -> str | None:
        if type(topic) is not str or topic not in TOPICS:
            return None  # Only fixed classifier outputs can enter the emitted manifest.
        if self.strategy == "lazy":
            allowed = (name for name in CATALOG if self.host.principal == self.principal and self.host.allows(name))
            candidates = ranked(allowed, topic)[:1]  # Filter first; hidden names never get a rank.
            self.manifest.append({"type": "discovery_result", "topic": topic, "candidates": list(candidates)})
            new = [name for name in candidates if name not in self.visible]
            if new:
                self.manifest.append({"type": "definitions", "tools": [definition(name) for name in new]})
                self.visible.update(new)
        else:
            candidates = ranked(self.visible, topic)
        return candidates[0] if candidates else None

    def _read(self, name: str, limit: int) -> tuple[Record, ...]:
        self.reads.append(name)
        return CATALOG[name].records[:limit]

    def dispatch(self, name: str | None, args: object) -> str:
        """Suggestions are data; authorization and argument/budget checks precede any read."""
        if name is None:
            status = "no_candidate"
        elif (type(name) is not str or self.host.principal != self.principal
              or not self.host.allows(name) or name not in self.visible):
            # Generic denial: do not echo an unapproved or unknown tool name into context.
            status = "not_allowed"
        elif type(args) is not dict or set(args) != {"limit"} or type(args["limit"]) is not int or not 1 <= args["limit"] <= 2:
            status = "invalid_arguments"
        elif len(self.reads) >= self.limits.calls or len(self.records) + args["limit"] > self.limits.rows:
            status = "budget_exhausted"  # Reserve the requested maximum, not the likely result size.
        else:
            rows = self._read(name, args["limit"])
            self.records.extend(rows)
            self.results.append({"status": "ok", "tool": name, "records": [asdict(row) for row in rows]})
            return "ok"
        self.results.append({"status": status})
        return status

    def emitted(self) -> bytes:
        return serialize({"manifest": self.manifest, "results": self.results})


@dataclass(frozen=True)
class Outcome:
    task_id: str
    selected: tuple[str | None, ...]
    reads: tuple[str, ...]
    records: tuple[Record, ...]
    context: bytes

    @property
    def context_bytes(self) -> int:
        return len(self.context)


TASKS = (
    ("routine", ("retention",)),
    ("policy-and-sync", ("retention", "schedule")),
    ("duty", ("duty",)),
)

# Independently specified support catalogue and facts for this cohort, never derived from
# CATALOG, TASKS, definition(), or a replay. The definition order below is part of the gold.
GOLD_DESCRIPTIONS = {
    "read_duty": "查客服交班值守时间。",
    "read_labels": "查本地客服草稿标签说明。",
    "read_queue": "查培训工单的分组说明。",
    "read_retention": "查客服导出文件留存期。",
    "read_retention_notes": "查导出留存术语说明。",
    "read_sync": "查客服每日同步时间。",
}
GOLD_INPUT_SCHEMA = {
    "type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 2}},
    "required": ["limit"], "additionalProperties": False,
}
GOLD_DISCOVERY_STEPS = {
    "routine": (("retention", "read_retention"),),
    "policy-and-sync": (("retention", "read_retention"), ("schedule", "read_sync")),
    "duty": (("duty", "read_duty"),),
}
GOLD_TOOLS = {"routine": ("read_retention",), "policy-and-sync": ("read_retention", "read_sync"), "duty": ("read_duty",)}
RETENTION = Record("support", "EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。")
GOLD_RECORDS = {
    "routine": (RETENTION,),
    "policy-and-sync": (RETENTION, Record("support", "SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。")),
    "duty": (Record("support", "DUTY-DESK", 1, "§1", "值守每天 09:00 开始。"),),
}


def run_task(strategy: str, task, *, limits=Limits()) -> Outcome:
    task_id, topics = task
    session = Session(strategy, Host(), limits)
    selected = []
    for topic in topics:
        name = session.select(topic)
        selected.append(name)
        session.dispatch(name, {"limit": 1})
    return Outcome(task_id, tuple(selected), tuple(session.reads), tuple(session.records), session.emitted())


def replay(strategy: str, *, limits=Limits()) -> tuple[Outcome, ...]:
    return tuple(run_task(strategy, task, limits=limits) for task in TASKS)


@dataclass(frozen=True)
class Report:
    candidate_hits: int
    expected_candidates: int
    read_calls: int
    context_bytes: int
    ineligible_tasks: tuple[str, ...]
    manifest_errors: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.ineligible_tasks


def _expected_manifest(strategy: str, task_id: str) -> list[dict]:
    def definitions(names):
        return {"type": "definitions", "tools": [
            {"name": name, "description": GOLD_DESCRIPTIONS[name], "input_schema": GOLD_INPUT_SCHEMA}
            for name in names
        ]}

    if strategy == "small":
        return [definitions(("read_retention",))]
    if strategy == "all-authorized":
        return [definitions(GOLD_DESCRIPTIONS)]
    if strategy == "lazy":
        manifest = [definitions(()), {"type": "discovery", "description": "按预设业务主题查已授权工具，最多返回一个名称。"}]
        for topic, name in GOLD_DISCOVERY_STEPS[task_id]:
            manifest.extend([
                {"type": "discovery_result", "topic": topic, "candidates": [name]},
                definitions((name,)),
            ])
        return manifest
    raise ValueError("unknown strategy")


def _same_json(actual, expected) -> bool:
    """Compare ordered arrays and exact JSON types (Python equates False with 0)."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same_json(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same_json(a, e) for a, e in zip(actual, expected))
    return actual == expected


def compare(rows: tuple[Outcome, ...], *, strategy: str) -> Report:
    """Score the fixed cohort against the strategy chosen by the trusted caller."""
    if tuple(row.task_id for row in rows) != tuple(GOLD_TOOLS):
        raise ValueError("not the same ordered cohort")
    hits = expected = 0
    ineligible = []
    manifest_errors = []
    for row in rows:
        try:
            payload = json.loads(row.context.decode("utf-8"))
        except ValueError:
            payload = None
        expected_manifest = _expected_manifest(strategy, row.task_id)
        manifest_ok = isinstance(payload, dict) and _same_json(payload.get("manifest"), expected_manifest)
        if not manifest_ok:
            manifest_errors.append(row.task_id)
        tools = GOLD_TOOLS[row.task_id]
        expected += len(tools)
        hits += sum(got == want for got, want in zip(row.selected, tools))
        records = GOLD_RECORDS[row.task_id]
        expected_results = [{"status": "ok", "tool": name, "records": [asdict(record)]}
                            for name, record in zip(tools, records, strict=True)]
        delivery_ok = (row.selected == tools and row.reads == tools and row.records == records
                       and isinstance(payload, dict) and _same_json(payload.get("results"), expected_results))
        if not manifest_ok or not delivery_ok or set(payload) != {"manifest", "results"}:
            ineligible.append(row.task_id)
    return Report(hits, expected, sum(len(row.reads) for row in rows),
                  sum(row.context_bytes for row in rows), tuple(ineligible), tuple(manifest_errors))


def main():
    print(COHORT_VERSION)
    for strategy in STRATEGIES:
        report = compare(replay(strategy), strategy=strategy)
        print(strategy, f"eligible={report.eligible}", f"hits={report.candidate_hits}/{report.expected_candidates}",
              f"local_reads={report.read_calls}", f"context={report.context_bytes} B", f"blocked={report.ineligible_tasks}",
              f"manifest_errors={report.manifest_errors}")


if __name__ == "__main__":
    main()
