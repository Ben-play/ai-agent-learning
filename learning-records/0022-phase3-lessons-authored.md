# Phase 3 全部课程落地（L25–L38 + 大纲 0044）

## 概述
按已审大纲（学习记录 [[0021-phase3-outline-audit-tavily]]）落地 Phase 3「LLM API 工程实践」全部 **14 课 L25–L38**（文件 `0030`–`0043`）+ Phase 3 大纲页 `0044`。这是目前最大的一个阶段。Tavily 联网佐证、SDK 真实 API 核对、代码全 ast 校验。

## 课程清单（5 模块 14 课）
| 课 | 文件 | 模块 | 核心 |
|----|------|------|------|
| L25 | 0030 | 3.1 | messages 心智模型 / OpenAI·Anthropic 差异 / **base_url 兼容切厂商** / key 环境变量 |
| L26 | 0031 | 3.1 | 流式=SSE 逐块 / stream=True + delta.content / TTFT |
| L27 | 0032 | 3.2 | FC 原理：**模型只出调用意图不执行** / tool_calls / json.loads |
| L28 | 0033 | 3.2 | **Structured Outputs(约束解码保证 schema) ≠ JSON mode**（P1 审核重点）|
| L29 | 0034 | 3.2 | Vision/音频 / **图片按分辨率折算大量 token** |
| L30 | 0035 | 3.3 | 滑动窗口/摘要(compaction)/压缩 / tiktoken 触发 |
| L31 | 0036 | 3.3 | 退避+**full jitter(防重试风暴)**+**幂等键(有副作用工具安全重试)**（审核补强）|
| L32 | 0037 | 3.3 | Fallback主备 / 路由 / **AI Gateway(LiteLLM)统一 OpenAI 格式** |
| L33 | 0038 | 3.3 | 三支柱 / **OTel GenAI 语义约定 gen_ai.* + Langfuse**（审核补强）|
| L34 | 0039 | 3.4 | Tool Schema：**description 决定模型选得对不对** / Pydantic / strict |
| L35 | 0040 | 3.4 | **完整 FC while 循环 = Agent Loop 骨架** / 并行 / 防死循环 |
| L36 | 0041 | 3.4 | 校验失败回填重试 / 流式拼工具调用 / **@tool Registry(闭合 L11)** |
| L37 | 0042 | 3.5 | 缓存分层：前缀缓存 vs **语义缓存**(区别是面试题) / LLMLingua / Batch |
| L38 | 0043 | 3.5 | 收官：生产级多模型 Agent 客户端(整合 L25–L37) |

## 关键实证
- **SDK API 核对**：装 openai 2.44 / anthropic 0.115，introspect 确认 `chat.completions.create`、`responses.create`、`messages.create`、`messages.stream`、`base_url` override 全部存在——L25 及后续代码按真实 API 写。
- **Tavily 佐证**：OpenAI 主推 Responses API（L25 教 Chat Completions 作通用心智模型、Responses 作了解）；约束解码保证 schema（L28）；OTel GenAI semconv 1.42（L33）；jitter+幂等专文（L31）；语义缓存 vs 前缀缓存（L37）；LLMLingua 压缩（L37）。
- **代码全 ast 校验**：L25–L38 所有 Python 块 `ast.parse` 0 错。

## 生产方式
- **L25 我亲写**（有最新 SDK introspect），**L26–L38 派 13 个并行 subagent**（分两波 6+7），每个给：精确文件名、L25 样板、Tavily 核过的事实+引用、文件号交叉链接表、铁律。
- **导航**：bottom-nav.js + course-bar.js 各补 14 课（phase='第三阶段'）；大纲 button 逻辑扩展第三阶段→0044；node --check 过、TOTAL=38、L24→L25 桥接、L25→L38 连续、L## 编号自动对。
- **大纲页 0044**：与 0002/0029 对称，14 课链接+练习+一手源；总览 0001 Phase 3 卡片加「查看详细大纲」链接。

## 审核（独立复核，非仅信 subagent 自述）
- **结构**：14 课 div 全平衡、6 脚本+单 style、phase 标签齐。
- **交叉链接**：独立扫描揪出 **6 个 broken href**（subagent 猜错兄弟课文件名，如 `0041-L36-agent-loop`/`0036-L31-retry-timeout-backoff`/`0026-L22-model-selection`/`0030-L30-...`）→ 全部修正为真实文件名。**这是并行 subagent 的典型 bug，必须自己扫。**
- **Quiz 泄露**：去标签查，15 个 flag 里 14 个是误报（等长并列/含 code 选项/正确项更短），仅 **L30-Q3** 真的 correct=unique-longest → 已重平衡。
- **代码**：全 ast.parse 通过。

## 遗留
- 老遗留仍在：Phase 5 补 L13 移走的 Generic/Protocol。
- 本阶段代码需真实 key 才能端到端跑（无 key 走 mock，同 Phase 2 处理）。

**Why:** 按已审大纲落地 Phase 3 全部课程，用真实 SDK + Tavily 佐证。
**How to apply:** 续 Phase 4 沿用：foundational 自写 + 并行 subagent 铺 + 分波；**交叉链接必自己扫**（subagent 爱猜错兄弟文件名）；代码 ast + 关键实证；nav 数组注册 + 大纲页对称 + 大纲 button 加新阶段分支。数据 Tavily/SDK 实证，版本号不写死。
