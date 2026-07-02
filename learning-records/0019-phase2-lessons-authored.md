# Phase 2 全部课程落地（L17–L24，Tavily 联网佐证）

## 概述
用户 `/teach 生成模块2的课程，可以使用Tavily联网搜索最新的资料`。据已审核的大纲（学习记录 [[0018-phase2-outline-audit-tavily]]），一次性写完 Phase 2「AI 知识与模型选型」全部 **8 节课 L17–L24**（文件 `0021`–`0028`）。全程用 **Tavily 实时搜索**佐证、关键数据用真实工具跑出来。

## 课程清单
| 课 | 文件 | 模块 | 核心 |
|----|------|------|------|
| L17 | 0021 | 2.1 | LLM=概率预测本质 / 注意力直觉 / temperature·top_p·惩罚项 / **temp=0≠可复现** |
| L18 | 0022 | 2.1 | Token=子词 / BPE·byte-level / tiktoken 计数 / **中文更费token取决于分词器** / 成本换算 |
| L19 | 0023 | 2.2 | 幻觉=**校准/评估激励问题**(arXiv 2509.04664) / 检测(Self-Consistency…) / 缓解(RAG·CoT·多采样，不可根除) |
| L20 | 0024 | 2.2 | 标准vs推理模型 / Extended Thinking·budget_tokens / 何时用哪个(OpenAI决策规则) / 成本延迟权衡 |
| L21 | 0025 | 2.2 | Base vs Instruct(**微调不加知识**) / RLHF / 六大局限(知识截止·不擅计算·幻觉·上下文·无记忆·lost-in-middle) → Agent 用工具补 |
| L22 | 0026 | 2.2 | MMLU-Pro/GPQA/SWE-bench/ARC-AGI 各测什么 / **榜单失真(污染·过拟合)** / 开源vs闭源拐点 / 选型框架 |
| L23 | 0027 | 2.3 | 成本公式 / **两杠杆:Prompt Caching(读~0.1×写~1.25×)+Model Routing** / 压缩·批处理 / token 预算 |
| L24 | 0028 | 2.3 | 收官项目:模型体检报告(tiktoken 成本+async 多模型对比+幻觉测试+选型结论) |

## 关键 Tavily 佐证（真实数据，非参数记忆）
- **temp=0≠确定性**：6 源印证(Thinking Machines Lab、vLLM 维护者)——浮点非结合 `(a+b)+c≠a+(b+c)`+硬件差异。→ L17 面试加分点。
- **中文 token 数实测**（本机 tiktoken 0.13.0 跑）："我喜欢学习语言。" **cl100k=11 → o200k=5**，与英文同。推翻"中文一定贵一倍"民间说法；两篇 arXiv(2604.14210/2506.07541)佐证是分词器问题。→ L18 用真实表格。
- **幻觉校准论**：arXiv 2509.04664(curl 200)——奖励猜而非弃权。→ L19 开场。
- **降本量级**：Anthropic 官方(读~0.1×/写~1.25×,5min/1h TTL)、OpenAI(~50%)、案例 59–70%；routing 40–85%。→ L23。
- **benchmark 污染**：arXiv 2406.04244 survey + OpenReview。→ L22。

## 生产方式
- **L17/L18 我亲写**（有最新鲜的 tiktoken 实测数据）；**L19–L24 派 6 个并行 subagent**，每个给：精确文件名、L18 作风格样板、Tavily 核过的事实+引用 URL、文件号交叉链接表、审核清单铁律(Quiz 等长/正确项非最长、`<details>` 折叠练习、每点 Agent 关联、primary source)。
- **导航注册**：`bottom-nav.js` + `course-bar.js` 的 LESSONS 数组各补 8 行(`phase:'第二阶段'`)——否则新课无 prev/next、无进度点、L## 编号错。node --check 通过，TOTAL=24，L16→L17 桥接正确，L17→…→L24 连续。

## 审核（独立复核，非仅信 subagent 自述）
- **结构**：8 课 div 全平衡(44/41/43/45/43/45/46/43)、各 6 脚本+单一 style、phase 标签齐、**全部内部交叉链接解析成功**。
- **Quiz 泄露**：独立脚本按去标签字数查"正确项是否唯一最长"。发现 **L22-Q1 spread=9**(Chatbot Arena 选项过长)→已改为等长 12/14/14/12。其余"correct_is_longest"均为**等长并列**(spread≤2)=无长度线索,合格。L23-Q1 早前误报是脚本把 `<code>` 标签算进长度,去标签后 17/16/16/15 本就合格。

## 遗留
- Phase 2 **没有独立大纲页**(Phase 1 有 `0002`)。当前 Phase 2 各课靠彼此交叉链接 + bottom-nav/course-bar 可达,总览 `0001` 本就不放课级链接(设计如此)。**如需与 Phase 1 对称,可后续补一个 `phase2-outline` 页**——本次未做(避免未受要求的扩建)。
- 老遗留仍在：Phase 5 补 L13 移走的 Generic/Protocol。

**Why:** 用户要按已审大纲落地 Phase 2 全部课程,并用真实 2026 资料佐证。
**How to apply:** 续写 Phase 3 时沿用此法——foundational 课自写+并行 subagent 铺量,给 subagent 喂"文件名+样板+核过的事实+铁律";写完必跑 div 平衡/Quiz 去标签等长/交叉链接存在/nav 数组注册 四项独立审核,别只信 subagent 自述。数据一律 Tavily/工具实证,版本号跑分不写死。
