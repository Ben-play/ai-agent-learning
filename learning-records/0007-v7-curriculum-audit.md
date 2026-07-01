# 大纲 v6 资深视角审核（v7 建议）

以资深 Agent 工程师视角、结合 2026 年 6 月联网调研，对 v6 大纲（11 阶段）做了一轮审核。整体判断：**基础与中段教学骨架很扎实，方向正确；主要问题是「实战缺口」与「个别内容失真」**，不需要推倒重来，按 v7 增补即可。

## 高价值发现（会改变后续教什么）

1. **Phase 10 的两个旗舰案例 `OpenClaw` 和 `Hermes Agent` 已（经二次核实）确认真实且热门，原「疑似虚构」判断是误判，已撤回。** 用 GitHub 官方 API 核实：`openclaw/openclaw`（TypeScript，**381k★ / 79.8k forks**，2025-11 创建、仍活跃，homepage openclaw.ai）README 自述为「本地优先 Gateway 控制平面 + 多 Agent 路由（hub-and-spoke）」，与大纲「协调型 Agent」描述吻合；`NousResearch/hermes-agent`（**205k★**，标语「The agent that grows with you」）对应「自主型 / Learning Loop」，且有完整生态（self-evolution、中文《橙皮书》实战指南等）。**案例可保留，无需替换。**
   - **真正的教训（高价值，必须记住）：** 我第一版审核错误地把它们判为虚构。根因是第一轮 `WebSearch` 返回了「模型声称无法搜索」的**降级响应**，我把「搜不到」误当成「不存在」的证据，甚至推翻了一个本来报对了 381k★ 的子代理。→ 纪律：**① 强声明（项目名 + Star + 版本号 + arXiv 编号）必须用权威源当场验证（GitHub API、官网），不能只信 WebSearch；② 「搜不到 ≠ 不存在」，搜索失败是「无信号」而非「负信号」；③ 子代理给出的可验证具体数字，优先去验证而不是凭直觉否定。** 已写进课程审核清单。

2. **最大的「实战/面试」缺口是 Function Calling / Tool Schema 没有独立模块。** 这是所有厂商 API 的 Agent 基础能力、面试必考、手撕高频，但目前散落在 Phase 1（装饰器）和 Phase 3，没有「工具工程」专章。→ v7 在 Phase 3 后新增「工具工程与 Function Calling」。

3. **缺少「LLM/Agent 系统设计」专章。** 2026 年面试已从「设计推荐系统」转向「设计 RAG 系统 / 设计多 Agent 客服 / 设计 LLM 网关 / 设计长时运行 Agent」。这类 system-design 题目前无处承接。→ v7 新增系统设计模块（建议并入 Phase 8 或独立）。

4. **成本工程的「优先级」过时。** 大纲主推 GPTCache / LLMLingua，但 2026 年第一杠杆是**三大厂原生 Prompt Caching**（零改动、输入成本最高降 ~90%）。→ 重排为「原生缓存 > 模型路由(LiteLLM) > 提示压缩 > 蒸馏 > Batch API」，强调「静态前缀 + 动态后缀」的缓存键设计。

5. **可观测性只讲 LangSmith 一家，且缺标准化视角。** 应讲生态（Langfuse / Phoenix / Helicone / OpenLLMetry）+ **OpenTelemetry GenAI 语义约定**作为标准化方向；评估应升级为 **Agentic Metrics**（Tool Correctness / Plan Quality / Step Efficiency）+ 工具（promptfoo、Braintrust、DeepEval）+ 公开基准（SWE-bench Verified、τ-bench、GAIA）。

6. **部署栈过单薄 + 安全深度不足。** 部署只提 FastAPI+Docker+Serverless，缺**云托管 Agent 服务**（Bedrock AgentCore / Vertex AI Agent Engine / Azure AI Foundry Agent Service）与 Temporal 这类持久执行；安全缺**间接 Prompt Injection、过度代理(excessive agency)、MCP 工具权限链、人类在环审批**。

7. **若干工程化硬技能在 JD 高频但大纲弱/缺**：Git/版本控制（几乎缺失）、系统性的测试（pytest + Mock LLM）、可观测性与容器化「太靠后」（建议工程习惯从 Phase 3 起就渗透，而非堆到 Phase 11）。

## 结构性建议（v7 草案）

- 框架选型更新：LangGraph（生产首选）/ CrewAI（多 Agent）/ Pydantic AI（类型安全）保留；**AutoGen 降级为历史案例**，提示其后继 Microsoft Agent Framework；MCP 从「前沿协议」**升级为必修基础设施**（含自建 MCP Server + 安全）。
- 协议去噪：A2A 作为了解；**删除来路不明的 ANP/AGNTCY 强声明**，改为「关注，生态未定」。
- 模型版本：把「GPT-5 / Claude 4 / Gemini 2.5」改为「以课程时点最新为准」并给出**选型决策框架**，不把易过时的具体版本号写死进大纲正文。
- 术语：`Agent Harness`、`Context Engineering`、`Ratchet` 仍可用（Anthropic 工程博客确有相关论述），但要标注「概念/术语仍在演化」，不要包装成已固化的行业标准。

**Why:** 用户明确要求课程「贴近实战、紧跟最新、对齐面试与工作」。审核发现骨架达标但有实战盲区；过程中我一度误判 Phase 10 案例为虚构，经用户提醒后用 GitHub API 证实其真实并已更正 —— 这本身成为最重要的方法论教训。
**How to apply:** ① 优先增补 Function Calling、系统设计、原生缓存、Agentic 评估、云托管部署、安全深度（按 Top 改项）；② Phase 10 案例保留，仅链接真实仓库 + 补编码类对照；③ 建立「强声明必须用权威源当场验证、搜不到 ≠ 不存在」的纪律，已写进课程审核清单。详见 lessons/0007-curriculum-audit-2026.html。
