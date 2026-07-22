# AI Agent 开发工程师学习资源

## Knowledge（知识来源）

### 核心指南
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
  Anthropic 官方的 Agent 构建指南，涵盖 prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer 五种核心模式。必读。
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  2025 年 11 月发布。定义了 Agent Harness 范式：Initializer Agent + Coding Agent 双模式，跨上下文窗口工作。必读。
- [Anthropic: Harness Design for Long-Running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
  Harness 设计深度文章，涵盖长时间运行 Agent 的架构设计。必读。
- [Addy Osmani: Agent Harness Engineering](https://addyosmani.com/blog/agent-harness-engineering/)
  2026 年最全面的 Harness Engineering 综述。"好模型 + 好 harness > 好模型 + 差 harness"。必读。
- [AI Agent Protocol Ecosystem Map 2026](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp)
  MCP/A2A/ACP/UCP 四层协议栈全景图。Use for: 理解 2026 Agent 协议生态。
- [OpenAI Cookbook](https://cookbook.openai.com/)
  OpenAI 官方示例库，包含 Agent 模式、函数调用、RAG 等实战代码。Use for: API 最佳实践和代码参考。
- [Lilian Weng: LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
  非常详尽的 Agent 技术综述，覆盖 ReAct、Tool Use、Memory 等核心概念。Use for: 理解 Agent 架构全貌。

### Python 进阶 & 软件工程
- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
  Python 官方代码风格指南，覆盖布局、命名、注释与接口一致性。Use for: Python 工程最佳实践与代码可读性的一手依据。
- [Python Packaging User Guide](https://packaging.python.org/)
  Python Packaging Authority 维护的打包与依赖管理指南。Use for: 项目依赖、环境与可分发包的规范做法。
- [uv: Working on projects](https://docs.astral.sh/uv/guides/projects/)
  uv 官方项目指南，涵盖依赖声明、<code>uv.lock</code> 可复现锁定与 <code>uv sync</code> 环境同步。Use for: Phase 1 L01 的现代项目与锁文件实践。
- [Real Python](https://realpython.com/)
  高质量 Python 教程，涵盖 async/await、装饰器、类型提示等进阶主题。Use for: Python 基础到进阶。
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
  现代 Python Web 框架，Agent 服务部署必备。Use for: API 服务开发。
- [ruff 文档](https://docs.astral.sh/ruff/)
  超快的 Python linter 和 formatter。Use for: 代码质量工具链。
- [mypy 文档](https://mypy.readthedocs.io/)
  Python 静态类型检查器。Use for: 类型安全保证。
- [httpx 文档](https://www.python-httpx.org/)
  现代 HTTP 客户端，原生支持同步与异步、HTTP/2、流式响应。Use for: Agent 调用 LLM/工具 API 的传输层（Phase 1 L15）。
- [tenacity 文档](https://tenacity.readthedocs.io/)
  通用重试库，支持指数退避、条件重试、超时。Use for: LLM API 调用的重试策略（别手写轮子）。
- [Python logging 官方文档](https://docs.python.org/3/library/logging.html)
  标准库结构化日志。Use for: 生产 Agent 的日志与可观测性基础（替代 print 调试）。
- [Python asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)
  标准库异步框架（事件循环、gather、超时、Semaphore）。Use for: 并发 LLM 调用、事件循环理解（Phase 1 L16）。

### LLM 原理与 API
- [3Blue1Brown: Neural Networks / Transformers](https://www.youtube.com/c/3blue1brown)
  可视化讲解神经网络和 Transformer 架构，直觉理解 LLM 工作原理。Use for: 建立 LLM 底层直觉。
- [Andrej Karpathy: Let's build GPT from scratch](https://www.youtube.com/watch?v=kCc8FmEb1nY)
  从零实现 GPT，深入理解 Transformer。Use for: 深入理解 LLM 原理。
- [Anthropic API 文档](https://docs.anthropic.com/)
  Claude API 使用指南，包含 tool use、streaming、vision 等。Use for: Claude API 开发。
- [OpenAI API 文档](https://platform.openai.com/docs)
  GPT API 使用指南，函数调用、structured output 等。Use for: OpenAI API 开发。
- [Why Language Models Hallucinate（arXiv 2509.04664）](https://arxiv.org/abs/2509.04664)
  OpenAI 2025 论文一手源（[博客版](https://openai.com/index/why-language-models-hallucinate/)）。核心论点：幻觉是**校准/评估激励**问题——训练与评分奖励「猜」而非「弃权」，故为通用模型的数学必然，而非单纯数据噪声。**Phase 2.2 幻觉「为什么」首选一手来源，2026 面试高频**。
- [OpenAI: Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices)
  官方决策规则：速度+成本+任务明确 → 标准模型；准确+可靠+难任务 → 推理模型。Use for: Phase 2.2 推理模型 vs 标准「何时用哪个」。
- [Claude Models Overview](https://docs.anthropic.com/en/docs/about-claude/models/overview) · [Pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)
  厂商一手的模型能力矩阵与逐 token 价格（避开 SEO 榜单的失真版本号）。Use for: Phase 2.2/2.3 选型与 Token 经济学的**可核实**锚点；版本号以此为准、不写死。

### Prompt Engineering
- [Anthropic Prompt Engineering 指南](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering)
  Claude 官方 Prompt 工程指南。Use for: 系统级 Prompt 设计。
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
  GPT 官方 Prompt 工程指南。Use for: 对比不同模型的 Prompt 策略。

### 数据处理管线
- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
  高性能 PDF 解析库。Use for: PDF 文档提取（文本、表格、图片）。
- [BeautifulSoup 文档](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
  Python HTML/XML 解析库。Use for: 网页数据提取和清洗。
- [Unstructured](https://github.com/Unstructured-IO/unstructured)
  统一的文档解析框架，支持 PDF/HTML/Markdown/图片等。Use for: 多格式文档处理管线。
- [Crawl4AI](https://github.com/unclecode/crawl4ai)
  面向 AI 的网页爬虫框架。Use for: 为 RAG 系统采集网页数据。
- [LangChain Document Loaders](https://python.langchain.com/docs/integrations/document_loaders/)
  LangChain 文档加载器集合。Use for: 统一的文档加载接口。

### 数据库基础
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
  最强大的开源关系型数据库。Use for: SQL 语法、数据库设计、索引优化。
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
  Python 最流行的 ORM 框架。Use for: 数据库建模、查询构建、迁移管理。
- [Redis 官方文档](https://redis.io/docs/)
  内存数据库，Agent 缓存层首选。Use for: 缓存策略、会话存储、速率限制。
- [SQLite 文档](https://www.sqlite.org/docs.html)
  轻量级嵌入式数据库，适合原型和小项目。Use for: 快速原型开发。

### 向量数据库
- [Chroma 文档](https://docs.trychroma.com/)
  轻量级开源向量数据库，Python 友好。Use for: 本地开发和原型验证。
- [Pinecone 文档](https://docs.pinecone.io/)
  托管向量数据库服务，生产级。Use for: 生产环境向量检索。
- [Weaviate 文档](https://weaviate.io/developers/weaviate)
  开源向量数据库，支持混合检索。Use for: 需要向量+关键词混合检索的场景。
- [Milvus 文档](https://milvus.io/docs)
  高性能开源向量数据库，适合大规模部署。Use for: 大规模向量检索场景。
- [Sentence Transformers 文档](https://www.sbert.net/)
  Python 嵌入模型库，生成文本向量。Use for: Embedding 生成和模型选型。

### RAG
- [LangChain RAG 文档](https://python.langchain.com/docs/tutorials/rag/)
  LangChain 官方 RAG 教程。Use for: RAG 基础实现。
- [LlamaIndex 文档](https://docs.llamaindex.ai/)
  专注数据连接和 RAG 的框架。Use for: 高级 RAG 架构。
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
  基于知识图谱的 RAG 方案。Use for: 结构化知识检索。

### Agent 框架
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
  LangChain 团队的 Agent 编排框架，支持状态机、循环、持久化。Use for: 复杂 Agent 工作流。2026 年生产级成熟度最高。
- [CrewAI 文档](https://docs.crewai.com/)
  基于角色的多智能体协作框架。Use for: 多 Agent 团队协作。
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io)
  Anthropic 推出的 Agent 工具连接标准协议，被称为"AI 的 USB-C"。Use for: 工具集成和互操作性。
- [A2A (Agent-to-Agent Protocol)](https://github.com/google/A2A)
  Google 推出的 Agent 间通信协议。Use for: 多 Agent 系统间通信。
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
  OpenAI 官方 Agent 框架（Swarm 后继）。Use for: 轻量级 Agent 开发。
- [Pydantic AI](https://ai.pydantic.dev/)
  类型安全的 Agent 框架。Use for: 注重类型安全的 Agent 开发。
- [Google ADK (Agent Development Kit)](https://google.github.io/adk-docs/)
  Google 官方 Agent 开发套件，与 Gemini 深度集成。Use for: Google 生态 Agent 开发。
- [Smolagents (HuggingFace)](https://huggingface.co/docs/smolagents)
  代码优先的轻量级 Agent 框架。Use for: 快速原型和代码驱动的 Agent。

### Agent Harness & Context Engineering
- [Agent Harness: The Architecture that will Dominate 2026](https://www.linkedin.com/pulse/agent-harness-architecture-dominate-2026-bassel-haidar-sczfe)
  Agent Harness 架构详解，2026 年主导架构模式。Use for: 理解 Harness 设计原则。
- [Harness Engineering: Why the Way You Wrap AI Matters More Than Your Prompts](https://www.aimagicx.com/blog/harness-engineering-replacing-prompt-engineering-2026)
  Harness Engineering 取代 Prompt Engineering 的趋势分析。Use for: 理解 2026 工程范式转变。
- [Building AI Coding Agents: Scaffolding, Harness, Context Engineering](https://arxiv.org/html/2603.05344v1)
  学术论文，详解 Agent 的四层架构：推理、上下文工程、工具、持久化。Use for: 深入理解 Harness 架构。

### Agent Memory 系统
- [Mem0](https://mem0.ai/)
  AI Agent 记忆层框架，支持长期记忆管理。Use for: Agent 记忆系统实现。
- [Memory vs Context Window for LLM and AI Agents 2026 (Mem0)](https://mem0.ai/blog/context-window-is-ram-not-storage-why-most-agent-failures-happen-how-to-fix-them-in-2026)
  2026 年 5 月文章，区分 Context Window（RAM）和 Memory（Storage）。Use for: 理解记忆系统设计哲学。
- [The 6 Best AI Agent Memory Frameworks (2026)](https://machinelearningmastery.com/the-6-best-ai-agent-memory-frameworks-you-should-try-in-2026/)
  2026 年 6 大 Agent 记忆框架横评。Use for: 记忆框架选型。
- [Memory Systems for AI Agents: Beyond Context Windows](https://levelup.gitconnected.com/memory-systems-for-ai-agents-beyond-context-windows-967b39ce9896)
  Agent 记忆系统综述，超越上下文窗口的长期记忆方案。Use for: 记忆架构设计。

### RAG 进阶
- [Agentic RAG Survey (arXiv)](https://arxiv.org/html/2501.09136v4)
  Agentic RAG 学术综述，涵盖架构分类和演进路线。Use for: 理解 Agentic RAG 全貌。
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
  基于知识图谱的 RAG 方案。Use for: 结构化知识检索。

### Agent Harness & Context Engineering（2026 新兴）
- [arXiv:2603.05344 - Building AI Coding Agents: Scaffolding, Harness, Context Engineering](https://arxiv.org/html/2603.05344v1)
  2026 年 3 月论文，定义 Agent Harness 四层架构（Agent Reasoning、Context Engineering、Tooling、Persistence）。**必读** — Harness Engineering 正在取代 Prompt Engineering 成为核心技能。
- [Taskade: What Is an AI Agent Harness?](https://www.taskade.com/blog/agent-harness-explained)
  2026 年 Harness Engineering 入门指南，解释脚手架设计如何让 Agent 可靠工作。
- [Harness Engineering: Why the Way You Wrap AI Matters More Than Your Prompts](https://www.aimagicx.com/blog/harness-engineering-replacing-prompt-engineering-2026)
  2026 年文章，论证 Harness Engineering 取代 Prompt Engineering 的趋势。
- [LangChain: State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
  1300+ 专业人士调研，揭示 AI Agent 工程现状和趋势。
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Anthropic 官方一手文（2025 末）。固化 2026 面试高频术语：context rot、attention budget、compaction、structured note-taking（agentic memory）、sub-agent 架构、just-in-time / progressive-disclosure 检索。**Phase 4/5 Context Engineering 首选一手来源**。

### MCP & A2A 协议（2026 标准化）
- [Google: Developer's Guide to AI Agent Protocols](https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/)
  2026 年 3 月 Google 官方指南，详解 MCP、A2A 等六大 Agent 协议。**必读**。
- [arXiv:2505.02279 - A Survey of Agent Interoperability Protocols](https://arxiv.org/html/2505.02279v1)
  MCP、ACP、A2A、ANP 四大协议综述。Use for: 理解协议全景。
- [Auth0: MCP vs A2A](https://auth0.com/blog/mcp-vs-a2a/)
  MCP 和 A2A 对比指南，解释何时使用哪个协议。
- [A2A (Agent-to-Agent) Protocol](https://github.com/google/A2A)
  Google 推出的 Agent 间通信协议标准。

### Agentic RAG（2026 标准）
- [arXiv:2501.09136v4 - Agentic RAG: A Survey](https://arxiv.org/html/2501.09136v4)
  2026 年 4 月综述，定义 Agentic RAG 架构分类法。**必读** — 传统 RAG 已过时。
- [Neo4j: What is Agentic RAG?](https://neo4j.com/blog/agentic-ai/what-is-agentic-rag/)
  Agentic RAG 概念解释，结合知识图谱。
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
  基于知识图谱的 RAG 方案，Agentic RAG 重要组件。

### Agentic Coding（2026 生产级）
- [Anthropic: 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
  Anthropic 官方报告，编码 Agent 从实验到生产。**必读**。
- [Best AI Coding Agents in 2026, Ranked](https://mightybot.ai/blog/coding-ai-agents-for-accelerating-engineering-workflows/)
  2026 年编码 Agent 排名：Codex、Claude Code、Gemini CLI 等。

### Agent 测试与评估
- [LangSmith Evaluation](https://docs.smith.langchain.com/evaluation)
  LangChain 官方评估框架。Use for: Agent 自动化评估和回归测试。
- [RAGAS](https://github.com/explodinggradients/ragas)
  RAG 评估框架，衡量 faithfulness、relevance 等指标。Use for: RAG 质量评估。
- [DeepEval](https://github.com/confident-ai/deepeval)
  LLM 应用测试框架，支持多种评估指标。Use for: Agent 端到端测试。
- [pytest-httpx](https://github.com/Colin-bin/pytest-httpx)
  HTTP 请求 Mock 工具。Use for: Mock LLM API 调用。
- [Maxim AI](https://www.getmaxim.ai/)
  2026 年新兴的 AI Agent 评估平台。Use for: Agent 评估和测试自动化。

### Agent 安全
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
  LLM 应用安全风险清单。Use for: 了解 Agent 安全威胁全景。
- [Guardrails AI](https://www.guardrailsai.com/)
  LLM 输出安全护栏框架。Use for: 输出验证和安全防护。
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
  NVIDIA 的 LLM 安全框架。Use for: 对话安全和行为约束。
- [Rebuff](https://github.com/protectai/rebuff)
  Prompt Injection 检测框架。Use for: Prompt Injection 防御。
- [Learn Prompting: Prompt Injection](https://learnprompting.org/docs/basics/prompt_injection)
  Prompt Injection 攻击原理详解。Use for: 安全攻防学习。

### 工程优化
- [LangSmith](https://smith.langchain.com/)
  LangChain 生态的 Agent 追踪和评估平台。Use for: Agent 可观测性、链路追踪。
- [Langfuse](https://langfuse.com/)
  开源 LLM 应用可观测性平台。2026 年主流选择之一。Use for: 成本追踪、性能监控、Prompt 版本管理。
- [MLflow Agent Tracing](https://mlflow.org/top-5-agent-observability-tools/)
  MLflow 新增的 Agent 追踪能力。Use for: 与 ML 生态集成的 Agent 可观测性。
- [Phoenix (Arize)](https://phoenix.arize.com/)
  开源 LLM 可观测性工具。Use for: 嵌入分析、检索质量评估。
- [GPTCache](https://github.com/zilliztech/GPTCache)
  LLM 语义缓存框架。Use for: 降低 LLM 调用成本和延迟。
- [LLMLingua](https://github.com/microsoft/LLMLingua)
  Prompt 压缩工具，减少 Token 用量。Use for: 成本优化、长上下文处理。

### 生产部署
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
  现代 Python Web 框架，Agent 服务部署首选。Use for: API 服务开发和部署。
- [Docker 官方文档](https://docs.docker.com/)
  容器化部署标准。Use for: 应用容器化和部署。

### 在线课程
- [DeepLearning.AI: AI Agentic Design Patterns with AutoGen](https://www.deeplearning.ai/short-courses/)
  Andrew Ng 团队的 Agent 设计模式课程。Use for: 系统学习 Agent 设计模式。
- [DeepLearning.AI: Building Agentic RAG with LlamaIndex](https://www.deeplearning.ai/short-courses/)
  Agentic RAG 实战课程。Use for: RAG 进阶。
- [DeepLearning.AI: Multi AI Agent Systems with CrewAI](https://www.deeplearning.ai/short-courses/)
  CrewAI 多智能体课程。Use for: 多 Agent 系统。

### 2026 行业报告 & 框架对比
- [Anthropic: 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
  Anthropic 发布的 2026 年 Agentic Coding 趋势报告。Use for: 了解行业趋势和技术方向。
- [LangChain: State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
  LangChain 对 1300+ 专业人士的 Agent 工程调研报告。Use for: 了解 Agent 开发实践现状。
- [Developer's Guide to AI Agent Protocols (Google)](https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/)
  Google 官方的 Agent 协议开发者指南，涵盖 MCP、A2A 等六大协议。Use for: 理解 Agent 协议全景。
- [Stackone: 120+ Agentic AI Tools Mapped Across 11 Categories](https://www.stackone.com/blog/ai-agent-tools-landscape-2026/)
  2026 年 Agentic AI 工具全景图，120+ 工具跨 11 类别。Use for: 了解工具生态。
- [Agentic AI Frameworks 2026: Production Comparison (uvik.net)](https://uvik.net/blog/agentic-ai-frameworks/)
  2026 年 Agent 框架生产级对比（LangGraph vs CrewAI vs OpenAI SDK），含基准测试数据。Use for: 框架选型决策。
- [LangGraph vs CrewAI vs OpenAI Agents: Ship Test (techsy.io)](https://techsy.io/en/blog/langgraph-vs-crewai-vs-openai-agents-sdk)
  2026 年 6 月框架实测对比。Use for: 框架实际使用体验对比。

### v7 新增（2026 实战补强 · 资深审核）

#### 工具工程 / Function Calling
- [OpenAI: Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
  Tool 定义、strict mode、并行调用、多轮循环最佳实践。Use for: 工具工程实战（Phase 3.4）。**面试必考**。
- [Anthropic: Tool Use (Function Calling)](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
  Claude 工具调用规范，含工具定义与结果回填。Use for: 对照不同厂商的工具调用差异。
- [OpenAI: Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs)
  官方一手。**约束解码（constrained decoding）在 token 级<em>保证</em>输出符合 JSON Schema**（[原理博客](https://openai.com/index/introducing-structured-outputs-in-the-api/)）。**面试关键区分：Structured Outputs ≠ 旧 JSON mode**（后者只保证是合法 JSON，不保证符合你的 schema）。Use for: Phase 3.2 结构化输出。
- [Anthropic: Increase output consistency (Structured Outputs)](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency)
  Claude 侧「保证 JSON schema 一致性用 Structured Outputs」。Use for: 对照两厂商的 schema 保证机制。

#### 成本工程（原生缓存优先）
- [OpenAI: Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching)
  自动前缀缓存，≥1024 token 生效，输入成本最高降 ~90%。Use for: 2026 降本第一杠杆。
- [Anthropic: Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
  `cache_control` 原生支持，5min / 1h 保留策略。Use for: 「静态前缀 + 动态后缀」缓存键设计。
- [LiteLLM](https://github.com/BerriAI/litellm)
  100+ 提供商统一接口 + Fallback + 成本追踪 + 虚拟密钥。Use for: AI Gateway / 模型路由（替代手写路由）。

#### Agent 评估（Agentic Metrics + 基准）
- [promptfoo](https://github.com/promptfoo/promptfoo)
  评估 + CI/CD + 红队，已被 OpenAI 收购。Use for: 把评估接进流水线。
- [Braintrust](https://www.braintrust.dev/)
  端到端 Evals / Datasets / Experiments 平台。Use for: 数据集驱动的迭代评估。
- [SWE-bench](https://github.com/princeton-nlp/SWE-bench)
  真实软件工程任务基准，含 Verified 子集（500 题）。Use for: 编码类 Agent 评估。
- [τ-bench (tau-bench)](https://github.com/sierra-research/tau-bench)
  工具-用户交互场景的 Agent 基准。Use for: 评估多轮工具调用可靠性。
- [GAIA Benchmark](https://huggingface.co/datasets/gaia-benchmark/GAIA)
  通用助理能力基准。Use for: 通用 Agent 能力评估。

#### 可观测性标准化
- [OpenTelemetry: Semantic Conventions for GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
  `gen_ai.*` span 语义约定（模型、token、工具调用）。Use for: 厂商无关的标准化追踪方向。
- [OpenLLMetry (Traceloop)](https://github.com/traceloop/openllmetry)
  基于 OTEL，自动接入 LangChain/CrewAI/LlamaIndex/OpenAI Agents。Use for: 一行接入标准化追踪。
- [Helicone](https://www.helicone.ai/)
  100+ 提供商代理、成本路由、HQL 查询。Use for: 成本可视化 + 网关式可观测性。

#### 云托管 Agent 服务 / 持久执行（生产部署）
- [AWS Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
  托管 Agent 运行时（含 action groups、knowledge base）。Use for: 免运维生产部署。
- [Google Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
  Vertex 上的 Agent 编排与托管。Use for: GCP 生态生产部署。
- [Azure AI Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/)
  托管 Agent + 知识库 + 控制平面 + AI Red Teaming。Use for: Azure 生态生产部署 + 安全测试。
- [Temporal](https://github.com/temporalio/temporal)
  开源持久执行引擎，长流程自动重试 / 检查点。Use for: 长时运行 / 有状态 Agent 工作流。

#### Agent 安全（深度）
- [LLMLingua / LLMLingua-2](https://github.com/microsoft/LLMLingua)
  提示压缩 + 抵御 jailbreak（微软）。Use for: 固定提示词的被动安全 + 降本。
- [Simon Willison: Prompt injection（持续更新）](https://simonwillison.net/tags/prompt-injection/)
  间接注入 / 工具滥用的最新实例与防御讨论。Use for: 跟踪真实攻击模式。

#### 真实开源 Agent 案例（已用 GitHub API 核实 · 替换早期失真案例）
- [OpenClaw](https://github.com/openclaw/openclaw)
  协调型 Agent，本地优先 Gateway 控制平面 + 多 Agent 路由（hub-and-spoke），TypeScript，~381K★。Use for: 「协调型」架构剖析。
- [Hermes Agent (NousResearch)](https://github.com/NousResearch/hermes-agent)
  自主型 Agent，"grows with you"（自我进化 / Learning Loop），~205K★。Use for: 「自主型」架构剖析。
- [OpenHands](https://github.com/All-Hands-AI/OpenHands)
  开源编码 Agent，可读到完整 Agent 循环与工具调度源码。Use for: 「编码型」架构剖析 + Agentic Coding。
- [SWE-agent (Princeton)](https://github.com/princeton-nlp/SWE-agent)
  解决 GitHub issue 的软件工程 Agent。Use for: 编码 Agent 设计参考。

## Wisdom（社区）

- [r/LangChain](https://reddit.com/r/LangChain)
  LangChain/LangGraph 用户社区。Use for: 框架使用问题、最佳实践讨论。
- [LangChain Discord](https://discord.gg/langchain)
  LangChain 官方 Discord。Use for: 实时技术交流。
- [Hugging Face 社区](https://huggingface.co/community)
  全球最大的 AI 开源社区。Use for: 模型、数据集、技术讨论。
- [AI Engineer 社区](https://www.ai.engineer)
  AI 工程师社区，有大会和 Discord。Use for: Agent 工程实践交流。

## Gaps（待补充）

- 国内大模型 Agent 开发资源（通义千问、文心一言等）
- ACP (Agent Communication Protocol) 和 ANP (Agent Network Protocol) 的落地情况 —— **注意：ANP/AGNTCY 等协议 2026 年生态仍未定型，部分早期资料夸大其重要性；学习时以 MCP（已成事实标准）+ A2A（了解）为主，其余协议「关注即可」，不要投入过多。**
- 生产级 Agent 监控与运维最佳实践（SRE 视角）
- Extended Thinking 和 Computer Use 的更多实战教程（browser-use 已补入 RESOURCES）
