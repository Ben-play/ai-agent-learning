# Phase 2 前大纲复审（2026-07-02）—— 结论：v7 骨架仍稳，一处 P1 术语补强

在开写 Phase 2 前，按用户要求对照 2026 最新资料复审整份大纲。**WebSearch 通道再次降级**（每条结果都是模型自称"无法联网"后给参数知识——正是 [[verify-strong-claims-search-not-found]] 警告的失败模式），故弃用搜索、改从权威源直取信号：Anthropic 工程博客、Chip Huyen、MCP 官网、GitHub API。

## 权威源核实结果
| 核实项 | 结果 |
|--------|------|
| OpenClaw / Hermes / LangGraph 仓库 | 全部真实且**今日仍在推送**（381K★ / 207K★ / 36K★，均未 archived）→ Phase 10 案例无需动 |
| MCP 2026 地位 | 官网证实**已成事实标准**，Claude / **ChatGPT·OpenAI** / VS Code / Cursor 均支持 → 大纲「MCP=必修基础设施」定位正确 |
| Building Effective Agents | 五大模式（chaining/routing/parallelization/orchestrator-workers/evaluator-optimizer）+ workflows vs agents + 工具工程（ACI/poka-yoke）→ 已被 Phase 3.4/5 覆盖 |
| Chip Huyen《Agents》| planning=搜索问题、decouple plan/execution、失败模式分类、ReAct/Reflexion → 已被 Phase 5 覆盖 |

## 唯一实质缺口（P1）：Context Engineering 术语未对齐官方
Anthropic 2025 末发布官方文《Effective Context Engineering for AI Agents》，把 2026 面试高频词固化下来，而我的 Phase 4/5 讲得较松、**未点名**这些术语：
- **context rot**（token 越多召回越差）、**attention budget**（注意力预算）
- **compaction**（接近上限时压缩重启）、**structured note-taking / agentic memory**（上下文外持久化笔记）
- **sub-agent architectures**（子代理带干净窗口、只回 1–2k 精炼摘要）
- **just-in-time retrieval / progressive disclosure**（轻量标识符运行时按需加载 vs 预取）

**How to apply:** 在 Phase 4「Context Engineering 基础」与 Phase 5「Context Engineering 进阶」补齐上述官方术语与技法，并把该文列为 Phase 4/5 首选一手资料（加进 RESOURCES）。属**增强非重构**——不改阶段结构。其余 P0/P1（Function Calling 专章、系统设计、原生缓存、Agentic 评估）v7 已落地，本轮复审确认无回退。

**Why:** 用户在进 Phase 2 前要求再做一次对照最新资料的大纲审核。
**Verdict:** 大纲维持 v7 结构，仅需 1 处内容补强 + RESOURCES 加 1 条一手来源。参见 [[0007]] 初版审核、[[0008]] v7.1。
