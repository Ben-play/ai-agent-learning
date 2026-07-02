# Part C 全部落地 —— Phase 1 完结（L12–L16）

一次性把 Part C（Agent 导向工程技能）5 节课从大纲落地为完整课程。**至此 Phase 1（L01–L16，16 节）全部写完**，Python 基础阶段结束。

## 本批新增
| 文件 | 课 | 核心 |
|------|-----|------|
| 0016 | L12 生成器与 Streaming | yield/生成器表达式/迭代器协议/send、LLM 逐 token 流；练习=streaming 模拟器 |
| 0017 | L13 类型提示 | Optional/Union/Literal/Callable/TypeAlias/mypy（Generic/Protocol 明确留到 Phase 5） |
| 0018 | L14 Pydantic | BaseModel/Field/field_validator/嵌套、model_dump(_json)、**model_json_schema 导出 Tool Schema**；闭合 L11 @tool 线 |
| 0019 | L15 httpx | HTTP 组成/状态码策略(429/5xx 重试、4xx 不重试)、Client/AsyncClient、SSE；练习=迷你 LLM 客户端 |
| 0020 | L16 async 并发 | GIL、协程vs线程vs进程、async/await、gather/Semaphore/wait_for；练习=并发调 LLM。**Phase 1 收官** |

## 设计要点
- 全课把前面知识串成一条河：L16 的 SSE/并发用到 L04 字符串、L09 流解析、L10 tenacity、L12 生成器、L15 httpx；L14 闭合 L11 的 @tool→Schema。
- L13 严格执行 v7.1 决定：不讲 Generic/Protocol（留 Phase 5），聚焦最常用类型。
- L16、L11 末尾各有里程碑提示；L16 额外标注「Phase 1 完结，下一站 Phase 2」。

## 验证
- **可运行代码开工前集中跑通**（Python 3.14）：L12 生成器/迭代器/send、L13 typing 语义、L16 asyncio(gather 并发提速、Semaphore 限流峰值≤2、wait_for 超时、async 上下文)——全绿。
- **L16 课内「可直接运行」的批量练习实测**：7/7 成功、0.62s（限流 3、并发，vs 串行 1.4s），claim 属实。
- **L14 Pydantic / L15 httpx**：代码按 Pydantic v2 / httpx 正确 API 编写，标注需 `pip install`，RESOURCES 附官方文档。<br>
  ~~（编写当时未在本机运行）~~ **更正（2026-07-02）**：本机其实可安装——`python -m ensurepip` 引导出 pip 后，`pip install pydantic httpx` 成功（pydantic 2.13.4 / httpx 0.28.1），已用真实库把 L14 全部代码 + L15（用 httpx MockTransport 走真实 API）跑通验证，claimed 输出全部一致。此前"本机装不了"的判断有误。
- 结构：5 课标签平衡、6 脚本齐全(含 back-to-top)、进度条 75→100%；nav L01–L16 连续；各 3/3 登记；node --check 通过。
- **Quiz 审核**：初检出 L14q2/L15q1 两处"正确答案最长"泄露，已改到 0 泄露（沿用审核清单规则）。

**Why:** 用户要求继续生成 Part C。
**How to apply:** **Phase 1 完结**。下一步可进 Phase 2（AI 知识与模型选型）。注意 Phase 5 要补 L13 留下的泛型 Generic/Protocol。参见 [[0012-partb-lessons-authored]]、[[0013-l06-l11-audit-fixes]]。
