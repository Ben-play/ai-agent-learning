# Phase 3 大纲审核（Tavily 联网复审 · 2026）

## 背景
用户在进 Phase 3 前，要求按 Phase 2 那套流程审核「LLM API 工程实践」大纲（14 课，5 模块），用 Tavily 联网核对 2026 最新实践找可优化点。

## 现状评估：大纲已强，且贴合 2026
Phase 3 = 3.1 API基础 / 3.2 核心能力(Function Calling·Structured Output·多模态) / 3.3 工程实践(Context管理·重试·Fallback·可观测性) / 3.4 工具工程(Tool Schema·完整FC循环·健壮性·注册系统) / 3.5 成本工程(降本优先级)。Tavily 核对后，**主体全部经得起 2026 检验**：退避/429、Fallback/AI Gateway/LiteLLM、FC 循环、strict mode、原生 Prompt Caching、可观测性、成本分层——都是当年生产实践。

## Tavily 核过的一手源
- **Structured Outputs = 约束解码保证 schema**：OpenAI 官方博客《Introducing Structured Outputs》+ docs guide(200) + Anthropic「increase-consistency」文(200) 均确认——constrained decoding 在 **token 级保证**符合 JSON Schema，**≠ 旧 JSON mode**（后者只保证合法 JSON）。
- **OTel GenAI 语义约定**：opentelemetry.io semconv(1.42)、`gen_ai.*` span 已是厂商无关标准，VS Code Copilot 都在发；Langfuse 原生接。
- **语义缓存 vs 前缀缓存**：Redis/Spheron 2026 确认是两种不同机制——前缀缓存逐字节命中静态前缀，语义缓存按 embedding 相似度命中，互补。
- **抖动 + 幂等**：多篇 2026 源（含专文《The Idempotency Crisis: LLM Agents》）——退避要加 full jitter 防重试风暴；有副作用的工具调用必须用幂等键才能安全重试。

## 审核结论：结构过关，四处增强（非重构，仍 14 课）
1. **P1 · Structured Output 补「约束解码 ≠ JSON mode」**（Module 3.2）——原写「JSON mode、输出验证与重试」，未点破 2026 的 token 级保证机制。已改：Structured Outputs(strict/约束解码，保证符合 Schema) ≠ 旧 JSON mode，验证重试降为「无法保证时的兜底」。**最高价值补丁、面试必考**。
2. **P2 · 可观测性点名 OTel GenAI 标准**（Module 3.3）——原写「调用日志/Token追踪/成本告警」（自建口径）。已补：OpenTelemetry GenAI 语义约定（`gen_ai.*` span，厂商无关）+ Langfuse。
3. **P2 · 成本工程加「语义缓存」为独立杠杆**（Module 3.5）——interview-box 早就问「Prompt Caching 与语义缓存的区别」，但降本清单里没有语义缓存。已插入为 ②（按语义相似度命中，GPTCache/Redis，与前缀缓存互补），原 ②③④⑤ 顺延。
4. **P2 · 重试策略补「抖动 + 幂等键」**（Module 3.3）——原写「429/指数退避/重试预算」，缺 full jitter（防重试风暴）与 idempotency key（有副作用的工具调用可安全重试）——两者都是 2026 资深必答。已补。

同步：面试题 12+ → **14+**（加「Structured Outputs vs JSON mode」「有副作用工具调用如何安全重试(幂等)」，速率限制题标注退避+抖动）；RESOURCES「工具工程」段补 Structured Outputs 两条一手源（OpenAI guide + Anthropic consistency）。GPTCache/OTel semconv/LiteLLM/FC guide 已在库，无需重复加。

## 校验
- HTML div 平衡 **96/96**；5 个新术语（约束解码/full jitter/幂等键/OpenTelemetry GenAI/语义缓存）全部在页。
- RESOURCES 新增 URL：`developers.openai.com/.../structured-outputs`、`docs.anthropic.com/.../increase-consistency` 均 curl 200；OpenAI 博客 403 属 bot 拦截（Tavily 证其在线），用 docs guide 作主引。
- 属增强非重构：模块数/课数（14）不变，只加 bullet 与命名概念。

**Why:** 进 Phase 3 前用真实 2026 资料校准大纲，确保教到当年 API 工程真正考的（约束解码保证、OTel 标准、语义缓存、抖动+幂等）。
**How to apply:** 写 Phase 3 课程时——3.2 结构化输出课以「Structured Outputs vs JSON mode」开场、引 OpenAI/Anthropic 官方；3.3 重试课必讲 jitter + 幂等键（举有副作用工具调用被重复执行=真金白银损失的例子）；可观测性课用 `gen_ai.*` span 讲；3.5 成本课把语义缓存与前缀缓存并列讲清区别。版本号/价格一律引厂商 docs，不写死。
