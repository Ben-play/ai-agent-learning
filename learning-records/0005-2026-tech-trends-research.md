# 0005: 2026 AI Agent 技术趋势研究

**Date:** 2026-06-27  
**Status:** Accepted  
**Deciders:** 用户 + AI 教学助手

## Context

用户要求搜索 2026 年 AI Agent 最新技术发展，确保学习大纲紧跟技术潮流，避免学习过时技术浪费时间。

## Research Method

使用 firecrawl-search 进行 4 次并行搜索：
1. AI Agent 2026 总体趋势
2. Agent Harness 技术细节
3. MCP vs A2A 协议
4. RAG 2026 进展

搜索结果来源包括：
- Anthropic 官方报告
- Google 开发者指南
- arXiv 学术论文
- LangChain 行业调研
- 技术博客和社区讨论

## Key Findings

### 1. Agent Harness 成为 2026 主流架构

**定义**：围绕 LLM 的脚手架系统，决定 Agent 如何运行、何时停止、如何处理错误。

**四层架构**：
- Layer 1: Agent Reasoning（推理层）
- Layer 2: Context Engineering（上下文工程）
- Layer 3: Tooling（工具层）
- Layer 4: Persistence（持久化层）

**核心观点**：
- "Harness Engineering" 正在取代 "Prompt Engineering" 成为核心技能
- 关注整体运行环境设计，而非单个 Prompt 优化

**权威来源**：
- arXiv:2603.05344 (2026-03)
- LangChain State of Agent Engineering 调研

### 2. MCP vs A2A 协议生态成熟

**MCP (Model Context Protocol)**：
- Anthropic 推出的开放标准
- Agent 访问外部工具和数据的统一接口
- 类比：USB-C（统一接口）

**A2A (Agent-to-Agent Protocol)**：
- Google 推出的 Agent 间通信标准
- 实现不同框架 Agent 的互操作
- 类比：HTTP（通信协议）

**关键洞察**：
- 两者解决不同问题，需要同时掌握
- 不是竞争关系，而是互补关系

**权威来源**：
- Google Developer's Guide (2026-03-18)
- arXiv:2505.02279 综述

### 3. Agentic RAG 成为标准

**演进路径**：
- 2023-2024: 简单 RAG 管道
- 2025: 多步骤 RAG
- 2026: Agentic RAG（Agent 控制检索过程）

**核心特点**：
- Agent 自主决定何时检索、检索什么
- 结合 GraphRAG 实现知识图谱增强
- 传统 RAG 管道已过时

**权威来源**：
- arXiv:2501.09136v4 (2026-04-01)

### 4. Agentic Coding 进入生产阶段

**演进**：
- 2024: 实验性编码助手
- 2025: 单 Agent 编码工具
- 2026: 生产级编码 Agent 系统

**2026 趋势**：
- 单 Agent 演进为协调团队
- 长期运行 Agent 构建完整系统
- 人类监督通过智能协作扩展

**权威来源**：
- Anthropic 2026 Agentic Coding Trends Report

### 5. Agent 协议标准化

**六大协议**：
1. MCP - 工具集成
2. A2A - Agent 间通信
3. ACP - 消息传递语义
4. ANP - 网络发现
5. AEP - 执行协议
6. AMP - 管理协议

**权威来源**：
- Google Developer's Guide (2026-03-18)

## Consequences

### 课程更新需求

1. **新增模块**：Agent Harness & Context Engineering
2. **新增模块**：MCP & A2A 协议
3. **更新模块**：RAG → Agentic RAG
4. **更新模块**：Prompt Engineering → Harness Engineering
5. **新增参考**：Agent Harness 架构参考
6. **新增参考**：MCP & A2A 协议参考

### 技术优先级调整

**高优先级（必须掌握）**：
- Agent Harness 四层架构
- Context Engineering
- MCP 协议
- A2A 协议
- Agentic RAG

**中优先级（了解）**：
- ACP、ANP 等补充协议
- Agentic Coding 最佳实践
- Extended Thinking
- Computer Use

**低优先级（可选）**：
- 传统 RAG 管道（已被 Agentic RAG 取代）
- 纯 Prompt Engineering（已被 Harness Engineering 取代）

## References

- [arXiv:2603.05344 - Building AI Coding Agents](https://arxiv.org/html/2603.05344v1)
- [Google Developer's Guide to AI Agent Protocols](https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/)
- [arXiv:2501.09136v4 - Agentic RAG Survey](https://arxiv.org/html/2501.09136v4)
- [Anthropic 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [LangChain: State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
- [Auth0: MCP vs A2A](https://auth0.com/blog/mcp-vs-a2a/)
