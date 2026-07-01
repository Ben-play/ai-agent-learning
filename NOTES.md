# 学习偏好

- 教学语言：中文
- 参考资料：可以是英文
- 学习风格：注重实战和项目驱动
- 目标：成为 AI Agent 高级开发工程师
- 开始日期：2026-06-24
- 课程目录：/Users/yemengyu/Junior-to-Senior/AI-Agent学习/
- Python 水平：有简单基础，不够深入（从基础开始，不跳过）
- 用户明确要求：不要跳过基础，系统性学习
- 教学风格：所有课程以实战为导向，每课必须有动手练习
- 搜索工具：使用 /firecrawl-search 技能搜索最新资料

# 更新日志

- 2026-07-01: **回到顶部浅色配色调浅** — 用户反馈浅色下太深。静止态从深森林绿盘改为"纸片"感：白→奶油微渐变 + 森林绿箭头 + 细边框(与奶油页分离)；**hover 才填森林绿盘+奶油箭头**(浅→彩的满足感)+琥珀光晕。深色模式维持深绿盘+薄荷箭头(含 hover token)。node --check + DOM 模拟通过。

- 2026-07-01: **回到顶部按钮配色优化** — 圆盘改森林绿渐变+奶油箭头+内高光，进度环轨道改暖色 --accent-subtle+琥珀微光，hover 由绿→琥珀换色改为保持绿盘+琥珀光晕。**并修复深色模式对比度 bug**(原 --accent 深色下变浅薄荷、白箭头看不清 → 覆盖为深绿盘+薄荷箭头)。node --check + DOM 模拟复跑通过。

- 2026-07-01: **「回到顶部」共享组件** — 新增 `assets/back-to-top.js`(自注入 CSS+DOM)，挂到全部 15 页。森林绿圆盘+向上箭头+**外圈滚动进度环**(兼作阅读进度)，滚动>400px 弹入、点击平滑滚顶(reduced-motion 降级)，叠在主题切换按钮之上、不与 TOC 冲突，无障碍+深浅色。node --check + DOM 模拟(显隐/进度环/滚顶)全通过。学习记录 0014。

- 2026-07-01: **L06–L11 审核 + 优化** — 三轴自查：代码(HTML 内实抽取逐一核对，全部正确)、交叉链接(内部全有效、外部除 realpython 被 curl 拦外全 200)、Quiz。**发现 5 道 Quiz 选项长度不均且正确答案最长(答案泄露)，已全部重写选项使无一道正确项为唯一最长**(复检 0 道泄露)。L08 多态示意片段加"完整版见练习"说明。审核清单新增 Quiz 等长规则。学习记录 0013。

- 2026-07-01: **Part B 剩余课程 L06–L11 全部落地**（6 节课）— L06 闭包/0010、L07 类与@dataclass/0011、L08 继承与__call__/0012、L09 文件JSON/0013、L10 异常日志上下文/0014、L11 装饰器/0015。Agent 主线贯穿(闭包→装饰器→@tool 闭环)。**所有代码开工前集中跑通(Python 3.14)再落地**，结构平衡、每课 2 Quiz、进度条 37→69%、L01–L11 nav 连续、各 3/3 登记。至此 Phase 1 内容课 = Part A(L01–L04)+Part B(L05–L11) 共 11 节写完，仅剩 Part C(L12–L16)。学习记录 0012。

- 2026-07-01: **Quiz v3（去确认步骤 + 配色升级）** — 按用户二次反馈，移除「核对答案」两步确认，点选项即判分；手滑补救交给「再试一次」。配色改编辑风克制表达：柔色底 + 左侧强调条 + 字母徽章变 ✓/✗、非答案项淡出、暖赭代替刺眼红、hover 暖琥珀。node --check + DOM 模拟验证通过。仍不改任何课程 HTML。学习记录 0011 追加 v3 段。

- 2026-07-01: **Quiz 交互重设计（考卷批改式 v2）** — 纯改 `assets/quiz.js`，不动任何课程 HTML，自动作用于所有含 Quiz 的课程页。把「点选即锁+答案直接冒出」改为「选择(可改)→核对答案→批改揭晓(✓/✗图章+暖色反馈)+解析批注滑入+结果语+再试一次」。解决用户反馈的"不友好"。含 A/B/C/D 标记、无障碍(radiogroup/aria/方向键)、深浅色、reduced-motion。node --check + 自建 DOM shim 完整逻辑跑通。学习记录 0011。

- 2026-07-01: **L05 课程编写 + 审核**（`lessons/0009-L05-functions-and-parameters.html`）— 函数定义与参数（位置/关键字/默认、`*` 仅关键字 / `/` 仅位置、`*args`/`**kwargs`、解包、多值返回、可变默认参数陷阱、类型注解签名），Agent 主线「函数签名=工具契约」。已注册 nav + 大纲 0002 链接。审核：全部代码 Python 3.14 实跑通过、Q1 选项等长化消除泄露、结构平衡、node --check 通过。学习记录 0010。
- 2026-06-30: **L04 课程编写**（`lessons/0008-L04-control-flow-and-prompt.html`）— 流程控制 + f-string + Prompt 构造三模式，实战=Prompt 模板引擎。同时补齐缺失的 `assets/quiz.js`/`toc.js`（此前 Quiz 点不动）。代码实跑通过、已注册 nav。学习记录 0009。
- 2026-06-24: 初始学习路径创建（8 阶段）
- 2026-06-24: 用户要求新增数据库基础、向量数据库、工程优化 → 扩展为 10 阶段
- 2026-06-24: 从资深工程师视角审视，新增数据处理管线、Agent调试测试、安全攻防 → 扩展为 12 阶段
- 2026-06-24: 融入 2025-2026 最新技术：Agent Loop、Agent Harness、Extended Thinking、Computer Use、Agentic Coding、A2A → v3
- 2026-06-24: 创建 `code/` 目录，按阶段-课程组织代码练习，Phase 1 已建好 Part A/B/C 子目录
- 2026-06-27: v4 升级 — 搜索 2026 最新技术，新增 Context Engineering、Agentic RAG、ANP 协议、Google ADK、Smolagents
- 2026-06-27: v4.1 修复 — 压缩 Phase 1（22→15课）、修复死链、消除 Phase 6/8/10/11 重叠、Phase 9 精简+新增 9.5 选修
- 2026-06-27: v5 结构性重构 — 12 阶段连续编号（消除 9.5）、可观测性/评估/安全前移至 Phase 9、新增成本工程、工具设计哲学、Agent 迭代方法论、Phase 1 增强为 Agent 导向
- 2026-06-27: v6 学习顺序优化 — AI/LLM/Prompt 前移紧接 Python、新增 Phase 6 框架入门（立即实战）、数据基础+RAG 合并为 Phase 7、框架分层（轻量→生产级）、总数精简为 11 阶段
- 2026-06-27: v6.1 Phase 2/3 增强 — Phase 2 扩展为 AI 知识与模型选型（8课，新增幻觉/推理模型/Token经济学）、Phase 3 扩展为 LLM API 工程实践（10课，新增重试/Fallback/AI Gateway/可观测性）、覆盖 15+ 道面试高频题
- 2026-06-27: v6.2 Phase 10 新增 Agent 产品架构分析模块 — OpenClaw（协调型，250K+ Stars）vs Hermes Agent（自主型，Learning Loop），对比分析两种 Agent 设计哲学
- 2026-06-27: v6.3 Phase 1 大纲优化 — 新增 @dataclass（L07）、Dict/JSON 深度操作（L09）、Prompt 构造模式（L04）、GIL 概念（L15）、dataclass vs Pydantic 对比（L14）；压缩 OOP 继承和生成器；每课新增 Agent 场景实战练习
- 2026-06-27: L02 全面重写 — 使用 firecrawl-search 搜索最新资料，新增循环导入、__all__、__init__.py 最佳实践、虚拟环境对 sys.path 的影响；对齐 L03 结构标准
- 2026-06-27: L03 审核优化 — 修复 Quiz Q2 答案错误、练习改为折叠式、新增 Counter/setdefault/update/dict|、扩展面试题至 6 题、添加参考资源链接
- 2026-06-27: 建立课程审核流程 — NOTES.md 中新增审核清单，每次生成课程后必须执行
- 2026-06-27: 深色/浅色模式切换 — 新增 theme-toggle.js 组件，支持 localStorage 持久化、系统偏好检测、所有页面已注入
- 2026-06-30: 资深视角审核（v7 建议）— 联网调研对照 2026 技术/面试/JD，产出审核报告 lessons/0007-curriculum-audit-2026.html + 学习记录 0007。最大实战缺口为 Function Calling/Tool Schema 专章与 LLM/Agent 系统设计模块；成本工程应改以原生 Prompt Caching 为第一杠杆；评估升级 Agentic Metrics；部署补云托管 Agent 服务、安全补间接注入/过度代理/MCP 权限。**尚未改大纲本体，待用户指定起点。**
- 2026-06-30: **更正** — 审核第一版曾误判 Phase 10 案例 OpenClaw/Hermes 为「虚构」，经用户提醒用 GitHub API 重新核实：`openclaw/openclaw`（381k★）、`NousResearch/hermes-agent`（205k★）**均真实且热门**，与大纲描述吻合，案例保留无需替换。误判根因：第一轮 WebSearch 返回降级响应，把「搜不到」误当「不存在」。已在审核清单加入「强声明必须用权威源验证 + 搜不到≠不存在」铁律。
- 2026-06-30: **Phase 1 大纲优化（v7.1，仅改大纲页 0002，未写课程）** — ① 新增 L15「网络请求与 HTTP(httpx)」(新模块 3.3，async 顺延 L16/模块 3.4)；② L10 折入 logging + tenacity，模块 2.3 更名；③ L13 类型提示瘦身(聚焦 Optional/Union/Literal/Callable+mypy，Generic/Protocol 后移 Phase 5)；④ 修 total-bar 计数(8→实为9→新增后 10 模块·16 课)，同步 0001 总览(Phase 1 课时 22→16、Part B/C 描述)与 README(→16)；⑤ RESOURCES 补 httpx/tenacity/logging/asyncio 文档。结构校验通过(div 平衡、L01–L16 连续)，新增 URL 已验证。详见学习记录 0008。**遗留提醒：Phase 5 需补讲泛型 AgentState[T]/Protocol，因 L13 已移除。**
- 2026-06-30: **v7 大纲骨架落地（按审核结论，scope=只更新骨架）** — ① 修复 bug：补齐缺失的 `assets/quiz.js` + `assets/toc.js`（此前所有课程引用但文件不存在，Quiz 点不动 / TOC 不生成，现已修复并通过 node --check）；② 总览页 0001 升级 v7：Phase 3 新增「工具工程与 Function Calling」(3.4)+成本工程重排(原生缓存优先)、Phase 8 新增「LLM/Agent 系统设计」+评估升级 Agentic Metrics+安全加深、Phase 9 补 browser-use/OpenHands、Phase 10 案例订正(真实仓库链接+OpenHands 对照+AutoGen 降级+协议去噪)、Phase 11 补云托管 Agent 服务+Temporal、模型版本去硬编码、技术栈表全面更新、新增 v7 变更日志与设计原则、面试题覆盖 15+→30+、修死链 claude-code-harness、链入审核报告 0007；③ RESOURCES.md 新增「v7 新增」整段（Function Calling/原生缓存/Agentic 评估+基准/OTEL GenAI/云托管/安全/真实案例 4 个），Gaps 标注 ANP/AGNTCY 生态未定；④ README 同步 Phase 3/8 课时。**所有新增 URL 已 curl 验证 200，HTML 标签结构平衡校验通过。未写整节新课程（按用户选择的 scope）。**

# 课程审核清单（每次生成课程后必须执行）

### 内容正确性
- [ ] 所有代码示例能正确运行
- [ ] 知识点因果关系正确（不可混淆原因和结果）
- [ ] 面试问题答案准确、完整
- [ ] **强声明必须当场验证来源** — 凡涉及「项目名 + Star 数 + 具体版本号 + arXiv 编号」，须用 WebFetch 打开来源核实；无法证实的具体数字只写方向、不写数字（教训：OpenClaw/Hermes 虚构案例）

### 教学质量
- [ ] 练习先给任务，再给答案（用 `<details>` 折叠）
- [ ] Quiz 选项长度一致，不泄露答案线索
- [ ] Quiz 解释清晰，讲清原理而非只说"对/错"
- [ ] 每个知识点都有 Agent 开发关联说明

### 内容完整性
- [ ] 覆盖大纲中该课的所有知识点
- [ ] 包含参考资源链接（官方文档、Real Python 等）
- [ ] 面试题覆盖高频考点（≥4 题）
- [ ] 知识图谱与实际内容一致

### 结构与导航
- [ ] 上一课/下一课链接正确
- [ ] 大纲中该课标题有链接
- [ ] 代码风格一致（safe_get 实现方式统一等）

### Agent 实战关联
- [ ] 每个知识点有 Agent 场景说明
- [ ] 练习题目模拟真实 Agent 开发场景
- [ ] 至少 1 个"陷阱"类知识点（面试常考）
- [ ] **Quiz 四个选项字数相近、句式平行；正确答案不能是唯一最长/最详细项**（防止靠长度猜答案 —— L06–L11 审核教训）

### 课前引导
- [ ] 学习目标之前有"为什么这课重要？"引导模块
- [ ] 引导内容说明该课在 Agent 开发中的实际应用场景
