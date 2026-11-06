# AI Agent 课程技术与教学审查

核查日期：2026-11-06。对象：当前仓库，不等同于线上部署版本。

## 结论

**保留课程主干，优先修复已有教材的工程闭环，再更新版本化接口和少量真正缺失的能力。** 不建议推倒重写，也不建议把所有新框架、新协议变成必修。

现有总纲已经覆盖 Context Engineering、Harness、缓存、评估、安全、MCP、检查点与托管部署。把这些直接列成“缺失”并不准确。主要问题是：部分先进主题仍停留在名称和规划；Phase 3 综合示例没有完全兑现“无 Key 跑通、生产级”的承诺；部分跨厂商和成本结论已不适合无条件使用。

## 范围与证据边界

- 阅读完整十一阶段总纲，核对前三阶段课程目录和既有审查记录。
- 重点抽查 L25/L26/L28/L30/L33/L36/L37/L38，以及 MCP 参考页；**没有逐字重审全部 38 课**。
- 使用官方规范、厂商文档和项目文档核验技术方向。动态网页未标日期时，不虚构其发布日期；没有把搜索未命中当成“不存在”。
- 离线执行从 HTML 提取的指定 Python 代码，验证三个局部问题；未调用模型、未使用真实密钥、未执行完整课程测试套件。
- 不修改 MISSION，不把教材审查登记成学习者已掌握的新知识。

## 一、P0：先兑现已有课程承诺

### 1. L38 无 Key 综合链路实际中断

位置：`lessons/0043-L38-phase3-capstone.html:207-243`、`:393-399`。

工具循环把 `_M` 消息对象加入历史；mock 随后对历史每一项调用 `m.get("role")`。第二轮遇到 `_M` 即失败。

离线复核：保留原始 registry、循环和 mock，注入调用 mock 的本地 fallback 接缝后，输出：

```text
L38 offline loop: AttributeError: '_M' object has no attribute 'get'
```

这是底层根因；原有多供应商 fallback 可能进一步将其包装成整体失败异常。不能把这次局部复核描述成真实 SDK/API 全链测试。

**建议：**统一请求历史表示；补 text/json/stream 各自的离线 mock 和可执行验收。修复前将项目定位为“待集成教学骨架”，而非已完成的生产调用层。

### 2. L30 上下文重组没有保持协议与预算不变量

位置：`lessons/0035-L30-context-window-management.html:123-144`。

按消息数量截取最近四条，可能将助手工具请求与工具结果切开；摘要后也没有复算预算。这里的问题不是已明确标注的“粗略 Token 计数”，而是上下文守卫缺少必要后置条件。

离线复核：使用可控长度计数和摘要 stub，构造工具调用边界及单条超长消息，得到：

```text
L30 kept body starts with: tool
L30 tool request retained: False
L30 after compaction over budget: True
```

**建议：**按完整工具交互组重组；计入工具定义、多模态和输出预留；重组后重新计数，定义仍超限时的退出/外置策略。计数采用对应厂商和模型的方法，不能把 tiktoken 泛化到所有模型。

### 3. L36 把运行时校验留成注释，执行权限需要单独建模

位置：`lessons/0041-L36-tool-robustness-registry.html:199-224`。

`tools_param(["web_search"])` 只影响展示给模型的工具清单；`dispatch` 仍查全局注册表，Pydantic 校验只写“这里可以接”。局部执行结果：

```text
L36 advertised names: ['web_search']
L36 unadvertised registered tool: {'ok': True, 'data': {'city': 'Beijing', 'temp': 22}}
L36 out-of-range parameter: {'ok': True, 'data': {'query': 'test', 'n': -1}}
```

**边界：**未展示工具不自动等于未授权工具；原示例的 `int` 注解也未声明正数约束。因此这不是凭上述输入就证明权限漏洞或违背现有取值契约，而是证明“展示子集”“执行授权”“运行时参数约束”尚未闭环。

**建议：**显式传入本次允许执行的工具集；执行前构造参数模型；失败通过结构化错误反馈，不依赖模型遵守 Schema。补未知工具、非法参数、未授权工具零执行的验收。

### 4. L38 综合验收抹掉了单课已讲的边界

位置：`lessons/0033-L28-structured-outputs.html:191-204` 对照 `lessons/0043-L38-phase3-capstone.html:263-281`、`:338-399`。

- L28 已讲 refusal；L38 却直接 `json.loads(content)` 并写“保证能 loads 成功”，未处理拒答/截断。官方也明确列出拒答和达到输出上限的例外。[S2]
- `CostTracker` 已定义，但最终 `generate()` 没有接入 `record()`；示例中 `report()` 不能据此证明已累计调用成本。缓存也主要停留在说明。

**建议：**最小验收包含正常输出、拒答、截断、工具异常、预算耗尽；在每次真实底层调用处采集 usage，并测试工具往返、重试、fallback 的累计。支持的模型/接口中，结构约束成立也不代表事实、授权和业务正确。

## 二、P1：按当前官方资料更新课程

| 主题 | 当前状态 | 建议落点与最小验收 |
|---|---|---|
| 原生 API 与能力适配 | L25 已提 Responses，但定位为“了解即可”；主体仍是 Chat Completions | L25–L28、L35/L38：保留兼容接口基础，把 Responses 加为 OpenAI 主线实践；以厂商原生 SDK 和显式 adapter 处理差异。相同任务验证工具结果关联、事件、状态与 usage，不把换 base_url 当能力等价。[S1] |
| 成本决策 | L37 要求背固定六层优先级，称 OpenAI 无额外写费 | L23/L37：改成负载驱动决策。先测任务成功率、成功任务成本、延迟，再选择缓存、Batch、effort、路由等。缓存写价、TTL、最小长度和命中边界按模型/API版本核实；语义缓存还要验证用户/租户隔离、数据时效与不可缓存动作。[S3–S4] |
| MCP 版本化 | 已有基础与权限规划；参考页代码未展示完整可运行工程 | Phase 6/10：固定规范和 SDK 版本。已核实 2026-07-28 正式发布，其握手/会话/传输有破坏性变化；不能直接混用旧版流程。做发现、调用、版本不兼容、JSON/SSE响应测试。[S5–S7] |
| 远程 MCP 授权 | “权限隔离”已有，但不是完整 OAuth 接入课程 | Phase 6/10：区分 stdio 与 HTTP 授权；HTTP 授权是协议可选能力，采用时需讲发现、PKCE、资源/audience、issuer、scope和令牌边界。验证缺令牌、错误 audience/issuer、权限不足及最小 scope。[S8] |
| Agent Skills | 总纲/参考页本次检索未见专门教学单元 | Phase 4/6 增加一个小单元：`SKILL.md`、元数据触发、渐进披露、资源/脚本和版本管理。区分 Skill 提供流程知识、工具/MCP提供操作接口；触发匹配不是权限授权。验收一项可复用业务技能及不应触发的反例。[S9–S10] |
| 大规模工具使用 | 已有 registry、工具子集与 Token 开销；没有系统性实践 | Phase 5/9：补工具搜索、按需加载、在代码执行环境聚合中间结果的模式。以小工具集基线比较选择质量、上下文量与延迟；有瓶颈才引入，不照抄旧文章的 beta/API 字段。[S11] |
| 持久执行 | Phase 9/10/11 已提检查点、Temporal、恢复 | 基础提前到 Phase 5/6。以数据库检查点完成“暂停审批→退出进程→重启→同线程恢复”；说明节点可能重放，外部副作用须幂等，不能把检查点等同 exactly-once。[S12–S13] |
| Agent 评估 | Phase 2 已有开发/测试隔离与模型评估，Phase 8 才系统讲 Agent 评估 | 在 Phase 3 最小工具循环就引入小型任务集，Phase 8再扩展。区分 task/trial/trace/outcome；优先确定性检查环境最终状态，必要时用经校准的 Judge；重复试验，避免只查固定调用顺序。[S14] |
| 企业 RAG | 有混合检索、reranking、GraphRAG、RAGAS | Phase 7：先把检索权限、证据定位、版本/删除传播、检索与生成分层评测做成验收，再扩展复杂检索。两个用户相同问题不得检索越权文档；将检索内容视为不可信输入。GraphRAG等作为需求驱动选修。[S15] |

### 缓存结论为什么需要优先修订

`lessons/0042-L37-cost-engineering.html:57-68` 给出固定落地顺序，`:80-84` 将 OpenAI 缓存写入概括为“自动，无额外写入费”。现行官方文档已按模型代际区分缓存：新代际 Responses 文档列出 `prompt_cache_options.ttl` 及不同写价；早期模型的无额外写费行为另有说明。不能把其中一种推广到所有模型/接口。[S3]

同一课 `:128` 还把两个不同问题“不命中前缀缓存”说得过满：即便用户问题不同，共同静态前缀仍可能命中；是否命中还依赖可用断点、最低长度、TTL和路由等条件。不能用“相似问题的整次答案复用”取代“共同前缀复用”的区分。

推荐学习目标从“背清单”改成“给定负载和质量门槛，测量并解释最合适的优化”，特别关注 **每个成功任务的总成本**，而非单次请求最低价。

## 三、大纲结构与教学方式的减法

1. **保留 Python 和模型基础。** 不因新技术发展而跳过学习者尚需的容器、函数、类型、异步等基础，也不把 SDK 更新散落进每个基础练习。
2. **单 Agent 作为默认基线。** 总纲有多智能体目标，但需要补“函数/工作流足够时不使用 Agent”的决策课。多 Agent 必须与单 Agent 比较质量、成本、延迟与交接损失，再决定是否采用。[S16–S17]
3. **框架只选一个深学。** Phase 6 的轻量框架、Phase 10 的生产编排维持主线+对照，不变成所有框架必修清单。Microsoft Agent Framework 是 Semantic Kernel 与 AutoGen 的共同后继，现有总纲已提后继方向，只需更新定位及按语言核实状态。[S17]
4. **强化记忆生命周期，而非再加记忆产品。** 既有记忆课程增加写入依据、来源、过期、纠正、删除、用户隔离与检索评测；用真实任务的验收判断价值。
5. **更新 Prompt 教学边界。** Phase 4 可以讲 CoT 概念，但不要教成“所有模型必须要求逐步思考”。推理模型优先明确目标/约束/输出契约，具体提示策略按模型评测。[S18]
6. **删除没有证据的冠军与永久规则。** 总纲 `:366` 的“2026生产首选”、`:401` 的规则“只增不减”，应分别改为场景化选型与回归验证后的规则增删。框架名、GitHub星数、年度口号不应代替工程能力标准。
7. **同一业务项目贯穿。** 从 API/工具到 Context/Skills、持久执行、MCP、RAG、评估部署逐层演进，避免每阶段重新造一个不相干 demo。
8. **缩小反馈单元。** 当前已有知识点决策卡、近迁移和阶段验收，应保留。55–65分钟课程拆成多个可暂停的小目标，不必重新编号；加入隔日闭卷重建和跨课变式，避免“复制答案并通过”冒充长期掌握。

建议能力主线：

**Python → 模型基础 → API/工具闭环＋小型评估 → Context/Skills → 单 Agent 可靠执行 → MCP/RAG → 工程化部署 → 按需多 Agent。**

这不是要求立刻重排课号，而是后续编写时调整能力出现的时机。

## 四、推荐实施顺序与验收

### 批次 A：修已有内容，不增加课号

- 修 L30 重组不变量、L36校验/授权分工、L38 mock与成本接线。
- 统一 L28→L38 的拒答/截断契约，收窄“保证”“生产级”等措辞。
- 改 L37 固定排序和无条件缓存结论，统一大纲、练习、Quiz与参考页。
- 验收：不需要密钥的自动测试覆盖成功、非法输入、拒答、截断、工具错误、预算和累计 usage；不得用固定 fixture 证明真实模型能力或真实降幅。

### 批次 B：更新已规划主题的技术边界

- 为 Responses 和厂商原生接口增加适配实践。
- 给 MCP 指定规范/SDK基线，区分正式核心、可选扩展与提案。2026-07-28 Tasks 已移到官方扩展；“官方扩展”不自动代表所有运行时支持或适合基础必修。[S5–S8]
- 提前最小 Agent 评估、持久恢复与执行权限边界；保留后期深化。

### 批次 C：少量新增与选修整理

- 新增 Skills小单元；工具搜索/程序化调用按需选修。
- 补企业 RAG 和记忆生命周期验收。
- 缩减框架堆叠，统一贯穿项目、版本验证日期和学习时长。

## 一手来源

以下“动态”表示本次访问的现行文档，不表示所有条目均于2026-11-06发布。

- **S1** OpenAI，Responses迁移指南（动态）：https://developers.openai.com/api/docs/guides/migrate-to-responses 。明确 Chat Completions仍受支持，新项目推荐Responses。
- **S2** OpenAI，Structured Outputs（动态）：https://developers.openai.com/api/docs/guides/structured-outputs 。明确拒答和输出截断例外。
- **S3** OpenAI，Prompt Caching（动态）：https://developers.openai.com/api/docs/guides/prompt-caching 。按模型代际、缓存模式和TTL区分命中及写价。
- **S4** Anthropic，Prompt Caching（动态）：https://platform.claude.com/docs/en/build-with-claude/prompt-caching 。型号、TTL、写入/读取价格与失效条件需分别核对。
- **S5** MCP正式发布说明，2026-07-28：https://blog.modelcontextprotocol.io/posts/2026-07-28/ 。正式发布、迁移方向与扩展定位。
- **S6** MCP变更记录，2026-07-28：https://modelcontextprotocol.io/specification/2026-07-28/changelog 。移除初始化握手、协议会话以及Tasks扩展变化。
- **S7** MCP Streamable HTTP，2026-07-28：https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http 。新版移除GET流端点和协议会话，但不等于禁止SSE响应。
- **S8** MCP授权规范，2026-07-28：https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization 。HTTP授权、stdio边界、资源与令牌约束；OAuth 2.1引用仍是IETF草案。
- **S9** Anthropic，Agent Skills，2025-10-16；开放标准更新2025-12-18：https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills 。技能组织与渐进披露。
- **S10** Agent Skills规范（动态）：https://agentskills.io/specification 。SKILL.md元数据、资源布局与渐进披露；部分字段明确标为实验性。
- **S11** Anthropic，Advanced Tool Use：https://www.anthropic.com/engineering/advanced-tool-use 。工具搜索、程序化调用和按瓶颈采用的原则；文章代码不是当前API兼容性保证。
- **S12** LangGraph Persistence（动态）：https://docs.langchain.com/oss/python/langgraph/persistence 。checkpointer、thread_id、RAM与持久后端边界。
- **S13** LangGraph Interrupts（动态）：https://docs.langchain.com/oss/python/langgraph/interrupts 。恢复时节点重跑，以及中断前副作用的幂等要求。
- **S14** Anthropic，Demystifying Evals，2026-01-09：https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents 。task/trial/grader/trace/outcome、重复试验和分层评分。
- **S15** Microsoft Foundry，RAG与索引，页面更新2026-08-21：https://learn.microsoft.com/en-us/azure/foundry/concepts/retrieval-augmented-generation 。检索时访问控制与不可信检索内容。
- **S16** Anthropic，Building Effective Agents：https://www.anthropic.com/engineering/building-effective-agents 。从最简单可行方案开始，复杂度须以效果证明。
- **S17** Microsoft Agent Framework概览（动态）：https://learn.microsoft.com/en-us/agent-framework/overview/ 。Semantic Kernel与AutoGen共同后继，以及Agent/Workflow/普通函数的选择。
- **S18** OpenAI，Reasoning Best Practices（动态）：https://developers.openai.com/api/docs/guides/reasoning-best-practices 。简单明确提示、非无条件CoT、按需示例。

## 本次产出

只新增本审查文档；不改课件、配置或个人练习；没有提交、推送、创建PR，也没有执行付费模型调用。后续实施应逐批复核，而非把建议一次性扩成更多必修课程。
