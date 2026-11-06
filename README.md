# AI Agent 高级开发工程师学习课程

从 Python 基础到可验收的单 Agent 系统，再按需求扩展到生产与协作。

当前已编写 **38 节正式课（Phase 1–3，L01–L38）**；Phase 4–11 为规划，不代表正文或生产能力已经实现。参考页不计入正式课数。保留基础课号，以 Responses / 厂商原生 adapter、工具闭环和小型评估为主线，优先函数/workflow 与单 Agent，只选一个框架深学。

- [11 阶段学习路径总纲](lessons/0001-ai-agent-learning-path-overview.html)
- [Agent Skills 参考小单元（非正式课）](reference/0004-agent-skills.html)
- [2026-11-06 课程可靠性审查与官方来源](docs/research/2026-11-06-curriculum-audit.md)

## 课程概览

周数按学习负载分阶段估算，不承诺固定完成时间；规划数量与总纲同步，正式课以现有 L01–L38 为准。

| 阶段 | 主题 | 已编写 / 规划课数 | 分阶段估算 | 状态 |
|------|------|-----------------|------------|------|
| 1 | Python 基础（Agent 导向：含 httpx/异步/Pydantic/装饰器） | 16 课 | 2-3 周 | 已编写 |
| 2 | AI 知识与模型选型 | 8 课 | 1.5 周 | 已编写 |
| 3 | LLM API 工程实践（含工具闭环、小型评估、成本工程） | 14 课 | 3 周 | 已编写 |
| 4 | Prompt / Context / Skills | 6-8 课 | 2 周 | 规划 |
| 5 | Agent 核心架构与持久执行 | 10-12 课 | 3-4 周 | 规划 |
| 6 | 主线框架入门 + MCP | 5-6 课 | 1-2 周 | 规划 |
| 7 | 数据基础 + 企业 RAG | 10-12 课 | 3-4 周 | 规划 |
| 8 | 工程化实践（可观测性/评估/安全/成本/系统设计） | 10-12 课 | 3 周 | 规划 |
| 9 | 按需高级能力 | 5-6 课 | 1-2 周 | 规划 |
| 10 | 编排深化 + 按需多 Agent | 8-10 课 | 2-3 周 | 规划 |
| 11 | 部署与持续迭代 | 6-8 课 | 2 周 | 规划 |

## 目录结构

```text
.
├── lessons/              # 课程页面（HTML）
│   ├── 0001-ai-agent-learning-path-overview.html   # 学习路径总览
│   ├── 0002-phase1-python-outline.html             # 第一阶段大纲
│   ├── 0004-L01-dev-environment-setup.html         # L01 开发环境搭建
│   ├── 0005-L02-python-runtime-and-modules.html    # L02 运行机制与模块
│   └── 0006-L03-variables-types-data-structures.html # L03 变量与数据结构
├── assets/               # 共享组件
│   ├── style.css         # 统一样式（支持深色/浅色）
│   ├── theme-toggle.js   # 主题切换
│   ├── course-bar.js     # 顶部导航栏
│   └── bottom-nav.js     # 底部课程导航
├── reference/            # 参考资料
│   ├── 0001-glossary.html        # 术语表
│   ├── 0002-agent-harness.html   # Agent Harness
│   ├── 0003-mcp-a2a-protocols.html # MCP/A2A 协议（版本化参考）
│   └── 0004-agent-skills.html      # Skills 参考（非正式课）
├── best-practices/       # 非编号的阶段级工程实践综合页
│   └── phase1-python-engineering-practices.html
├── code/                 # 代码练习与离线综合项目
│   └── phase1-python/phase1-practices-capstone/
├── learning-records/     # 学习记录
└── NOTES.md              # 课程笔记与审核清单
```

## 快速开始

- 本地预览：在仓库根目录运行 `python -m http.server 8000`，再访问 `http://localhost:8000/`；也可直接打开 HTML 进行只读浏览，但不同 `file://` 页面之间不保证共享学习记录。
- GitHub Pages：推送到 `main` 后，由 `.github/workflows/pages.yml` 构建白名单站点并部署；首次使用需在仓库 Settings → Pages 中将 Source 设为 **GitHub Actions**。
- 移动端：通过 Pages 地址访问后，可使用浏览器“添加到主屏幕”；访问过的课程可在网络不可用时继续打开。

学习记录仅保存在当前站点和浏览器中；离线缓存可能被浏览器回收，不替代源码或笔记备份。

每个课程页面包含：
- 💡 **为什么这课重要** — 课前引导
- 🎯 **学习目标** — 明确的知识点清单
- 📖 **知识点** — 带 Agent 开发关联的讲解
- ✅ **知识点级最佳实践** — 给出场景、正反对照、照做步骤、运行自检与结果解释
- ❓ **交互测验** — 即时反馈
- 🏋️ **实战练习** — 动手实践
- 📋 **单课级最佳实践** — 用可操作验收任务收束本课执行纪律
- 🧭 **阶段实践检查点与最终复盘** — 学完相关知识后立即完成跨课检查点，避免拖到阶段末遗忘；Phase 1 的 8 个检查点分布在 L01/L02/L04/L07/L11/L12/L14/L16，[Phase 1 复盘页](best-practices/phase1-python-engineering-practices.html)用于最终索引与验收；Phase 2 的 5 个检查点分布在 L18/L19/L21/L22/L23，[Phase 2 复盘页](best-practices/phase2-model-selection-practices.html)汇总模型评测与选型决策
- 💼 **面试常见问题** — 高频考点
- 📚 **参考资源** — 延伸阅读

## 第三阶段离线验收

在已有依赖环境中执行 `python -I scripts/check-course-examples.py`，脚本只抽取明确白名单内的 L25/L26/L28/L30/L36/L37/L38 自检，不执行联网示例。L36 需要 Pydantic v2；可使用课程项目现有虚拟环境的 Python。禁止用 `-O` 禁用断言。

通过只证明指定控制路径，不代表真实模型质量、缓存命中或生产准入。在线实验应另行确认调用预算，并记录模型/API/SDK版本、配置和未测项。

## 特性

- 🌓 **深色/浅色模式** — 右下角切换，自动跟随系统偏好
- 📍 **课程导航** — 顶部粘性导航栏 + 底部卡片式切换
- 📊 **学习进度** — 手动标记完成课程，首页与顶部进度条同步显示完成度
- 📱 **响应式设计** — 移动端友好
- 🖨️ **打印友好** — 支持打印为 PDF

## 面向人群

- 想转型 AI Agent 开发的 Python 开发者
- 准备 AI Agent 岗位面试的工程师
- 想系统学习 Agent 开发的后端工程师

## 技术栈

- 纯 HTML/CSS/JS，无需构建工具
- 浏览器直接打开即可学习
- 无外部依赖，离线可用
