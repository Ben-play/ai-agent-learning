# Phase 2 内容深审（读内容层，非结构层）

## 背景
用户 `/teach 再审核一下模块2刚生成的课程`。上一轮已过结构检查（div/脚本/链接/Quiz 等长）。**这轮读内容**：知识正确性、代码可跑、事实准确、Quiz 解析、跨课一致、面试覆盖。

## 方法
- **代码全部实证**：抽出 L17–L24 所有 `<pre><code>`，`ast.parse` 逐块查语法；L18/L24 的 tiktoken 代码**用真库跑**核对 claimed 输出；L24 httpx/async 骨架逐行审（Bearer/raise_for_status/Semaphore/gather/env读key/mock）。
- **并行 3 个 subagent 深读**（L17-19 / L20-22 / L23-24+0029），每个当资深工程师找茬、按 P1/P2/P3 定级、要求引权威源。
- **关键：P1 我独立复核，不盲信 subagent**（[[verify-strong-claims-search-not-found]]）——两条 P1 都亲自验了才改。

## subagent 报告汇总：0 P1?→ 实为 2 P1、8 P2、17 P3
三个 reader 各自结论：L17-19 = 0 P1/4 P2/7 P3；L20-22 = 0 P1/4 P2/7 P3；L23-24+0029 = **2 P1**/5 P2/3 P3。

## 两条 P1（独立复核后确认真实，已修）
1. **L24 tiktoken 示例 token 数 12≠真实 10**。课程 line 106 明说"token 数是真的"却写 12——学生一跑就穿帮。我 `tiktoken` 跑 `"用一句话解释什么是向量数据库。"` o200k = **10**。已改 line 107-108（12→10、金额 0.004536→0.00453 / 0.000456→0.000455），并把"token 数是真的"软化为"本地 tiktoken 实算、不同版本可能 ±1"。
2. **L23 OpenAI 缓存"约省 50%"已过时**。查 OpenAI 官方 pricing：`gpt-5` 输入 $1.25 / 缓存输入 $0.125 = **省 90%（0.1×）**；cookbook「Prompt Caching 201」明说"新模型折扣更大"；仅老 gpt-4o 代才是 50%。**"50%"对当前模型严重低估**，且课程自己承诺"以官方为准"却与官方矛盾。已把 5 处（表格/速查卡/面试tip/summary/正文）统一改为 **"50%~90%（视模型代次，较新模型可达 ~90%）"**——不写死 90%（不同 family 不同），符合"volatile 数字不写死"原则。

## 修的 6 条 P2（高 ROI）
3. **L24 self_consistency 温度无法透传**：`call_model` 写死 `temperature:0`，但 self_consistency 注释说"调高到 0.8"——注释承诺代码没实现，学生照抄得到永远判不出发散的检测器。已给 `call_model` 加 `temperature: float = 0` 形参、payload 用它、self_consistency 传 `0.8`。**Step 2 对比仍默认 0（不破坏控变量教学）**。
4. **L23「真正管用的杠杆只有两根」**：与本课第 5 节（还有压缩/控输出/批处理）自相矛盾。改「**最大的两根**杠杆（其余为补充）」。
5. **0029 大纲「真实案例降本 59~70%」口径错**：59~70% 在 L23 正文专指缓存那一个案例，路由是另一区间 40~85%；大纲挂在两杠杆后像是合计。改「缓存 59~70%、路由 40~85%」。
6. **L20 第 5 节标题「推理模型要"少说"」**：易被读成"少给约束"，但 OpenAI 原文是"别强制 CoT，但要把目标/约束说具体"。改「**别替它安排思考步骤**」。
7. **L19 Self-Consistency「提高 temperature」**：技术上错（应适中温度 0.5~0.7，一味调高抬高误报）+ 与 L17「抽取用低温」读起来打架。改「用适中温度，如 0.5~0.7」。
8. **L19 Quiz Q2 stem「按 OpenAI 2025 论文」**：arXiv 2509.04664 作者是 Kalai/Nachum/Vempala/Zhang，无 OpenAI 公司署名（但有官方博客）。quiz stem 靠权威锚定需精确，改「按《Why Language Models Hallucinate》(2025)」+ 正文「OpenAI 研究者的论文」。

## 没改的 P3（polish，非错，刻意留）
temperature 范围 0-2（已标"1.0+"）、"垃圾词"软化、seed 是 OpenAI-only 注记、"学界共识"→"实证研究"、MMLU 当污染案例点名、L22 五步框架补"推理维度"（关联课已提）、budget_tokens<max_tokens 关系、judge 阈值 n=2 边界、1h 写 2× 补全……均为增强，本轮 scope=修错不扩写。**可作为后续 polish 清单**。

## 复核（改完必跑）
- 5 个改动文件 div 全平衡；L23 无残留裸"50%"、"最大的两根"就位；L24 六个 Python 块 `ast.parse` 全过；**L24 tiktoken real=10=claim、金额公式吻合**；temperature 透传三处全通。

**特别教训**：subagent 自审会漏（上轮它说 Quiz 没问题，实测 L22-Q1 spread=9；这轮 reader 自己差点把真实 arXiv 误报成假源、又漏看 L24 温度透传的深层 bug）。**P1 必自证、代码必实跑、数字必重算**——不能只信"报告说没问题"。

**Why:** 用户要求对刚生成的 Phase 2 课程再深审一遍找可优化点。
**How to apply:** 内容审 = 代码 ast.parse + 关键代码实跑 + 数字重算 + 并行 reader 找茬 + **P1 亲自复核权威源**。改完必跑 div/语法/数字三复验。volatile 数字（缓存折扣、token 数、价格）给区间 + "以官方为准"，不写死。
