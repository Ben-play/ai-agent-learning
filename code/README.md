# 代码练习目录

本目录保存课程示例与阶段级离线综合项目。课件仍以 `../lessons/` 中的正式课程为线性学习入口；这里的项目不增加课号或课时。

## 当前目录

```text
code/
├── phase1-python/
│   ├── part-a-basics/
│   │   ├── agent-hello/              # L01/L02 使用的锁定 uv 包项目
│   │   └── my-first-agent/           # 入门练习草稿
│   └── phase1-practices-capstone/     # Phase 1 非编号离线综合验收
├── phase2-model-selection/
│   └── phase2-practices-capstone/     # Phase 2 离线模型评测与选型验收
└── phase4-prompt-context/             # 证据问答＋工单草稿起始项目
```

## Phase 1 综合项目

`phase1-practices-capstone/` 使用 Pydantic v2、`httpx.MockTransport`、asyncio、pytest 与 mypy，离线组合验证：

- 稳定包接口与显式状态所有权；
- 执行前验证、失败安全注册和有界动作；
- 单一重试 owner、真实异步流关闭与按项批次隔离；
- 异常根因、脱敏日志和原子 JSON 持久化；
- “重试整个批次”“只导出 Schema 不实例验证”两个故意失败的反事实。

运行方式见 [`phase1-python/phase1-practices-capstone/README.md`](phase1-python/phase1-practices-capstone/README.md)。对应的阶段决策压缩页位于 [`../best-practices/phase1-python-engineering-practices.html`](../best-practices/phase1-python-engineering-practices.html)。

## Phase 2 综合项目

`phase2-practices-capstone/` 使用固定 fixture 和两个真实 adapter 实现，在不访问模型或网络的前提下验证：

- 模型能力驱动的控制映射与 provider 原生 Token 口径；
- 重复观测、事实错误、发散、正确弃权与证据覆盖分离；
- 未缓存输入、缓存写/读、输出、重试和升级的完整成本；
- 硬门槛先于归一化排名，路由计入升级概率；
- “一致即真值”“先排名后门槛”两个故意失败的反事实。

公共入口仅为 `build_offline_lab(...)` 和 `AssessmentLab.assess()`；调用者不需要了解 fixture 解析、计数、证据与排名实现。运行方式见 [`phase2-model-selection/phase2-practices-capstone/README.md`](phase2-model-selection/phase2-practices-capstone/README.md)，对应复盘页位于 [`../best-practices/phase2-model-selection-practices.html`](../best-practices/phase2-model-selection-practices.html)。

## Phase 4 起始项目

[证据问答＋工单草稿](phase4-prompt-context/README.md) 复用 L38 的离线调用边界，练习提示版本、证据来源、预算和拒绝无依据输出。只产出草稿，不执行工单动作。项目配合 [Phase 4 的 L39–L44](../lessons/0045-phase4-prompt-context-outline.html#lesson-plan) 学习，不另计课号。

## Phase 5 Harness 项目

[离线 Harness 项目](phase5-agent-harness/harness-lab/README.md) 复用 Phase 4 的证据与草稿，练习有界运行、应用审批、SQLite 检查点和幂等保存。只使用本地合成数据；配合 [L45–L54](../lessons/0063-phase5-agent-harness-outline.html#lesson-plan) 学习，不另计课号。

## Phase 6 LangGraph 与 MCP 实验

[L55–L59](../lessons/0069-phase6-langgraph-mcp-outline.html#lesson-plan) 分开验收 [LangGraph 迁移](phase6-langgraph-mcp/graph-lab/README.md)、[MCP stdio](phase6-langgraph-mcp/stdio-lab/README.md) 和 [loopback HTTP 与授权](phase6-langgraph-mcp/http-lab/README.md)。MCP 仅覆盖课堂子集；LangGraph 的依赖锁定和运行状态见项目说明。

## Phase 7 可追溯 RAG

[L60–L69](../lessons/0080-phase7-data-rag-outline.html#lesson-plan) 使用[可追溯证据问答实验](phase7-data-rag/rag-lab/README.md)：先验授权与来源，再比较检索、重排、缓存和分层评估。课程核心使用合成数据与本地标准库；PostgreSQL 和向量索引的实测状态按课标注。

## Phase 8 Agent 工程实验

[L70–L79](../lessons/0091-phase8-agent-engineering-outline.html#lesson-plan) 使用[工程实验](phase8-agent-engineering/engineering-lab/README.md)验证合成遥测、离线评估、草稿权限、成本账本、PR 门禁与基线交接。示例不需要真实模型、账单、远程后端或生产身份。

## 使用规范

- 使用第三方依赖的项目用 `pyproject.toml` 描述依赖；完成实测后提供 `uv.lock`，从项目根运行 `uv run --offline --locked ...`。纯标准库项目使用自身说明中的 Python 命令；
- `.venv`、缓存、日志和运行生成文件不进入版本控制；
- 验收只使用占位敏感值，不要求真实 API Key 或网络；
- 新阶段开始时再按真实课程结构创建对应代码目录，不预先维护虚构课号。
