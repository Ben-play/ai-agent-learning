# Phase 1 大纲优化（v7.1：补工程地基）

以资深视角审 Phase 1（Python 基础）大纲后，做了一轮「补工程地基」的优化。Phase 1 原本已很扎实（Agent 导向、15 课、A/B/C 结构），主要补的是几个生产 Agent 必需却缺位的工程技能。

## 改动（仅改大纲页 0002，未写课程内容）

1. **新增 L15「网络请求与 HTTP（httpx）」**（新模块 3.3）—— 最大的洞：原大纲从没真正教过「怎么发一个 HTTP 请求」，但每次 LLM 调用 / 工具调外部 API 本质都是 HTTP。含同步/异步客户端、状态码、鉴权头、SSE 流式（LLM streaming 的传输层本质）。async 课顺延为 L16（模块 3.4）。
2. **L10 折入 `logging` 结构化日志 + `tenacity` 重试库** —— 呼应「工程习惯前移」；生产代码从第一天用 logging 而非 print，重试用 tenacity 而非手写。模块 2.3 更名「文件、JSON、异常与日志」。
3. **L13 类型提示瘦身** —— 聚焦 Optional/Union/Literal/Callable + mypy；Generic/TypeVar/Protocol 深水区**后移到 Phase 5**（Agent 状态管理需要时再深讲），把 Phase 1 working memory 让给更紧迫的 Pydantic + async。
4. **修计数 bug** —— total-bar 原写「8 个模块」实为 9（off-by-one）；新增后为 **10 模块 · 16 课**。同步修正：总览页 0001 的 Phase 1 课时（原 22，已是错的 → 16）、Part C 描述补 httpx、Part B 描述补 logging/tenacity、类型提示行去掉 Generic/Protocol；README Phase 1 课时 → 16。
5. **RESOURCES.md** 补 httpx / tenacity / logging / asyncio 官方文档（新课的引用源）。

## 对后续教学的影响（重要）

- Phase 1 现在是 **L01–L16、10 个模块**。后面真正写课程时，httpx（L15）应排在 async（L16）之前，async 的并发练习直接复用 httpx.AsyncClient。
- L13 不再讲 Generic/Protocol —— **Phase 5（Agent 核心架构）需要补讲泛型状态 AgentState[T] 与 Protocol 工具接口**，否则会断档。
- 验证：大纲页 div 标签平衡、模块/课时编号连续无跳号、新增 4 个 URL 中 3 个 curl 200（Real Python 被 Cloudflare 拦 curl，已换成 asyncio 官方文档）。

**Why:** 用户要求「都优化改一下」，且课程定位是生产级、实战导向。httpx/logging/tenacity 是 Agent 工程地基，原大纲假设「你会」，对一个「有基础但不深」的学习者是断层。
**How to apply:** 写 Phase 1 具体课程时按 L01–L16 新顺序；L13 收窄范围、Phase 5 补泛型；httpx 课用真实 HTTP API 做练习。详见 [[0007-v7-curriculum-audit]]。
