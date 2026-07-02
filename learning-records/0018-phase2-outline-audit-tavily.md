# Phase 2 大纲审核（Tavily 联网复审 · 2026）

## 背景
用户在正式写 Phase 2 课程前，要求**用 Tavily 联网搜最新资料**对 Module 2（Phase 2「AI 知识与模型选型」）大纲做审核优化。这是继 [[0016-pre-phase2-audit-2026]]（当时 WebSearch 降级、改走权威源）之后，**首次用真正可用的实时搜索通道**复审。

## 搜索通道现状
- **Tavily 现已可用**：`TAVILY_API_KEY`（长度 58）已对 bash 进程可见，直接 `curl` API 返回 `HTTP 200` + 真实 2026 URL。本次审核的所有联网结论均由 Tavily 实搜得来。
- 原生 `/mcp` 仍显示 "No MCP servers configured"——根因不变：交互会话启动目录是 `Q:\Agent`（非项目子目录），已运行的会话不热加载 user 作用域 MCP 配置，下次启动自现。**不阻塞**，因我直接走 API。详见 [[0017-tavily-mcp-setup]]。

## 铁律复用（这次真派上用场）
Tavily top 结果大量是 SEO/营销站，充斥**不可核实的版本号与跑分**（"GPT-5.4""Opus 4.6""Arena Elo 1548"）。按 [[verify-strong-claims-search-not-found]] + 审核清单「强声明必经权威源验证」：**这些数字一律不写进大纲**，只取其中的**一手源**（arXiv / 厂商官方 docs）。这恰好**反向验证**了大纲原有的「版本号不写死、重在怎么选」原则是对的。

## 采到的一手源（已验证）
- **幻觉的"为什么"**：OpenAI《Why Language Models Hallucinate》——arXiv `2509.04664`（curl 200）+ 官方博客（curl 403 属 bot 拦截、Tavily 证其在线）。论点：幻觉是**校准/评估激励**问题（训练与评分奖励「猜」而非「弃权」），是通用模型的数学必然。
- **推理 vs 标准的决策规则**：OpenAI `reasoning-best-practices`（200）——速度+成本+任务明确→标准；准确+可靠+难→推理。
- **模型能力/价格锚点**：Anthropic `models/overview` + `pricing`（均 200）——逐 token 真价、真实在售型号矩阵，避开 SEO 失真。
- **降本定量**：Prompt Caching 官方倍率（读 ~0.1×、写 ~1.25×、5min/1h TTL，`docs.anthropic.com` 实锤）；独立案例（ProjectDiscovery / Morph / Redis）证实缓存+压缩+路由降本 **59–70%**；输出 token 普遍 **3–5× 输入**。

## 审核结论：结构过关，三处增强（非重构）
大纲 Module 2.1/2.2/2.3 骨架正确，无需改结构或加课（仍 8 课）。补三个 2026 面试/JD 高频缺口：

1. **P1 · 幻觉「为什么」补校准视角**（Module 2.2）——原来只写「为什么发生」，现点名 OpenAI/arXiv 校准论点。**最高价值补丁**。
2. **P2 · 新增「看懂 Benchmark」bullet**（Module 2.2）——MMLU-Pro/GPQA/SWE-bench/ARC-AGI 各测什么 + 榜单为何失真（污染/过拟合）+ 开源 vs 闭源权衡（自托管成本拐点）。选型模块此前只比能力、不教怎么读跑分。
3. **P2 · Token 经济学点名两大杠杆**（Module 2.3）——Prompt Caching（读 ~0.1×/写 ~1.25×）+ Model Routing（便宜兜底、贵接难题），标注真实降本 59–70%、输出 3–5× 输入。

同步：面试题 7+ → **9+**（加「幻觉校准」「benchmark 各测什么」「Caching/Routing 降本」）；实战项目补「Prompt Caching 前后成本对比」。RESOURCES `### LLM 原理与 API` 加 3 条一手源（幻觉论文 / reasoning-best-practices / Claude models+pricing）。

## 校验
- HTML div 平衡 **96/96**；9 个新术语全部在页；"8 课"标注未失真（加的是 bullet，非新课，故模块数不变——避开了 v7.1 那次的计数 desync）。
- RESOURCES 新增 URL：arXiv 2509.04664 / reasoning-best-practices / models-overview / pricing 均 curl 200；OpenAI 博客 403 属 bot 拦截，用 arXiv 版作主引。

**Why:** 进 Phase 2 前用真实 2026 资料校准大纲，确保教到的是当年面试/JD 真正考的（幻觉校准论、benchmark 素养、caching/routing 降本）。
**How to apply:** 写 Phase 2 课程时——2.2 幻觉课以 arXiv 2509.04664 的校准论点开场；选型课加一节 benchmark 判读；2.3 用 Anthropic 官方倍率讲 caching、用 LiteLLM 讲 routing。版本号/跑分一律引厂商 docs，绝不抄 SEO 榜单。
