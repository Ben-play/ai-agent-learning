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
- 搜索工具：**内置 WebSearch 现服务端降级（返回无来源的参数知识），一律不采信**。改用 **Tavily**（key 走环境变量 TAVILY_API_KEY，.mcp.json 已 gitignore）；MCP 工具就绪后走工具，否则直接 curl Tavily API。fallback：WebFetch 抓 URL + GitHub API。详见学习记录 0017。

# 更新日志

- 2026-07-02: **course-bar 坐标:去菱形点 + 阶段名中文化** — 用户:菱形点不要 + 阶段名中文显示。坐标读数从 `P3◇L30` 改为 **`第三阶段 │ L30`**:①删菱形分隔点,换成**细竖线 rule**(1px,editorial 利落);②阶段号 `P3` → 中文全名(直接用 `cur.phase`,如"第三阶段",body 字体+森林绿,不用 mono——中文 mono 难看);③`L30` 课号保留 mono+ink 色。坐标盒去掉整体 mono(只 L## 用 mono)。未来 11 阶段最长"第十一阶段"(5 字)坐标盒可容纳。深浅色同步(暗色 phase-name/rule 用 accent-bright)。改 course-bar.js(cur.phase + rule span)+ style.css(phase-num/coord-sep → phase-name/coord-rule)。node --check 过、CSS 括号 216/216、无死类引用、DOM 模拟确认中文阶段名正常。仅动 2 共享 asset。（顶栏第四次迭代。）
- 2026-07-02: **course-bar 精致化 + 去掉百分比数字** — 用户:不显示百分比 + 整条更美观。**① 去 %**:进度条已视觉表达进度,裸数字冗余,删掉 `.course-bar-pct`。**② 精装书页眉质感重塑**:坐标读数 `P3·L30` 做成 chapter-mark(浅底圆角小盒 + `P3` 森林绿),分隔符从"·"换成细菱形小点(rotate 45°);进度条改凹槽(inset 阴影)+ 更细(3px)+ 游标加发光环 + 静止时极轻呼吸光晕(courseCursorPulse);左/中/右三区加细分割线(border-left/right,像杂志栏规)把中区框成字段;prev/next 药丸 hover **定向微位移**(上一课向左 2px、下一课向右,箭头同步)+ 箭头默认 0.65 透明度 hover 提亮;栏背景 blur 10→14px+saturate、半透明 color-mix。深浅色(暗色游标 card-bg 描边、分隔点/P号用 accent-bright)+ 移动端(窄屏去分割线+隐藏 track)+ reduced-motion(关全部动画+hover 位移)。改 course-bar.js(去%+分隔符空 span)+ style.css(全量重写 .course-bar-* 块)。node --check 过、CSS 括号 216/216、无死类引用、DOM 模拟确认不渲染 %。仅动 2 共享 asset,不碰课程 HTML,全 40+ 页生效。（顶栏第三次迭代:dot→seg→连续条→本次精致化。）
- 2026-07-02: **course-bar 二次重设计（面向 11 阶段可扩展）** — 用户指出：分段进度条现在 3 段还行，但课程规划 **11 个阶段**，全生成后会碎成 11 个小方块（和"38 点"同类病）。**改为单一连续进度条 + 坐标读数**：`P3·L30`（阶段号·课号，mono）+ 一根连续总进度条（游标标当前位置，森林绿→琥珀渐变）+ `79%` 百分比。核心：进度只需一根连续条，"第几阶段"用文字读数表达，不给每阶段各画一段——**占位恒定，阶段再多也不变乱**。DOM 模拟验证：现 3 阶段 `P1·L01 3%`→`P3·L38 100%` 正确；合成 **11 阶段/100 课**未来场景，坐标读数封顶 8 字符（`P11·L100`）、始终【坐标+一条+百分比】三件套、零布局退化。载入 scaleX 展开 + 游标淡入动画（reduced-motion 降级），深浅色（暗色用 accent-bright + card-bg 描边游标）+ 移动端（窄屏隐藏 track 保留坐标）。改 `course-bar.js` 中段渲染 + `style.css`（删 .course-bar-seg/phase/count/total 换 .course-bar-coord/phase-num/track/track-fill/track-cursor/pct）。node --check 过、无死类引用。仅动 2 共享 asset，不碰课程 HTML，自动全 40+ 页生效。（本次与前一次 dot→seg 改动同日，此为 seg→连续条的再优化。）
- 2026-07-02: **顶部 course-bar 进度指示重设计（去掉 38 点 swarm）** — 用户反馈"章节中间的点太多了"。根因:`course-bar.js` 每课渲一个进度点,38 课=38 点挤中间,数不清、无意义。**改为分阶段进度计**:`L##/38` 计数(mono,像书页码)+ 3 段 proportional 进度条(段宽按各阶段课时 16:8:14,当前阶段精确 fill%、过去阶段满、未来阶段淡轨)+ 阶段徽章(森林绿药丸)。信息量反升(一眼看出:哪个阶段/总进度/精确到第几课),占位反降。森林绿→琥珀渐变 fill + 载入 scaleX 动画(reduced-motion 降级),深浅色 + 移动端(窄屏隐藏 meter/phase)都覆盖。改 `course-bar.js`(中段渲染逻辑)+ `style.css`(删 .course-bar-dot* 换 .course-bar-meter/seg/phase + 移动端 + 深色规则)。node --check 过、DOM 模拟 L01/L17/L30/L38 阶段数学全对(如 L30=阶段三 43%=6/14)、大纲页 isCourse=false 不渲 meter。仅动 2 个共享 asset,不改任何课程 HTML,自动作用于全部 40+ 页。
- 2026-07-02: **Phase 3 P3 打磨（择优 9 处）** — 处理内容审(0023)剩下的 ~30 条 P3/低优 P2，**择优改 9 处、跳其余**（P3 是打磨，避免过度 specify/加啰嗦）。**采纳**：L26「[DONE] 是 OpenAI-specific，Anthropic 用 message_stop」；L32「OpenAI 全线 529」→「OpenAI 常见 503、Anthropic 常见 529」（529 是 Anthropic 的码）+「同厂共享配额」误据 →「限流常按模型算，跨厂真正价值是故障独立」；L33 去掉非标准的 `gen_ai.tool.call.arguments`（3 处：树/速查卡/表，注明工具参数在消息部件里非顶层属性）+ 去 `v1.42`/「VS Code 都在发」的过时版本号硬编码（4 处，改「仍在演进、以官方最新版为准」）；L34 §6 例子 `detail_level` 默认值 + `strict:True` 自相矛盾 → 改 `Literal|None`（strict 下可选字段的正确表达，含解释同步）；L25「代码零改动」→「业务代码基本不动」；L29 补「图片块结构厂商特定，Anthropic 用 image/source 形状、无 detail」；L30 硬编码 cl100k 注释诚实化 + fill-ratio↔lost-in-middle 混淆改「上下文越长中间越易被淹没」。**跳过**：L25 仓库自指（其实为真）、L34 strict 位置（Responses vs Chat 形态，太细）等。复核：7 文件 div 平衡、改动代码 ast 过、9 needle 在位（含 2 处确认已移除）。至此 Phase 3 内容审的 P1/P2/P3 全部处理完毕。
- 2026-07-02: **Phase 3 内容深审 + 修复（读内容 + 追代码逻辑）** — 对刚生成的 L25–L38 深审（真 SDK 核 API + 3 并行 reader 追代码）。报告 4 P1+17 P2+25 P3，**P1 全部独立实证后修 4 P1 + 4 高价值 P2**。**P1**：① L36 `{"type":str.__name__}` 生成非法 JSON Schema（str≠string，tiktoken/JSON-Schema 实证）→ 加 `_JSON_TYPE` 映射；② L30 `count_tokens` 对 content=None 崩溃（`enc.encode(None)` 实测 TypeError，本课全 tool 消息）→ `m.get("content") or ""`；③ L38 `generate()` text 路径双调模型 + final_msg 被弃 → run_tool_loop append 最终轮、text 直接返回不再调；④ L38 Anthropic base_url 标"OpenAI 兼容层"误导（Tavily 查官方：/v1/ 兼容 shim 存在但有限，reader 说必 404 是过度声明）→ 注释改"有限兼容、生产走 LiteLLM 网关"。**P2**：⑤ L27 回填漏 append 助手 tool_calls 消息（会 400，FC 基础课）→ 补 append+改"三个点"；⑥ L31 wait_exponential 注释"1→2→4→8s"实为 2→4→8→8s → 改 multiplier=1+"以 tenacity 为准"。**未改 ~30 条低 ROI P2/P3**（多厂商 vision 形状/[DONE] sentinel/529 归属/gen_ai.tool.call.arguments/strict+optional 等，留 polish 清单；系统性弱点=代码教 OpenAI surface 却把 Anthropic 当同级源）。复核：5 文件 div 平衡、改动代码 ast 全过、7 needle 在位。**教训：reader 会过度声明，P1 必自证（代码类追逻辑、事实类查官方）。** 学习记录 0023。
- 2026-07-02: **Phase 3 全部课程落地 L25–L38 + 大纲 0044（Tavily + SDK 实证 + 并行 subagent）** — 按已审大纲写完「LLM API 工程实践」14 课（文件 0030–0043）。5 模块：3.1 API基础(L25 messages心智/多厂商/base_url兼容、L26 流式SSE)、3.2 核心能力(L27 FC原理"只出意图不执行"、L28 **Structured Outputs约束解码≠JSON mode**、L29 多模态+图片token成本)、3.3 生产级(L30 context管理、L31 **退避+full jitter+幂等键**、L32 Fallback/AI Gateway、L33 **OTel GenAI可观测**)、3.4 工具工程(L34 Tool Schema description、L35 **FC循环=Agent Loop骨架**、L36 健壮性+@tool Registry闭合L11)、3.5(L37 前缀vs语义缓存分层、L38 收官客户端)。**方式**：L25 自写(装 openai2.44/anthropic0.115 introspect 核对真实 API)，L26–L38 派 13 并行 subagent(分2波)。**导航**：nav 两文件各注册14课(第三阶段)+大纲button扩第三阶段→0044，node --check过、TOTAL=38、L24→L25桥接、L##自动对；大纲页0044与0002/0029对称；总览0001 Phase3卡片加大纲链接。**独立审核**：14课div平衡、代码全ast通过；**揪出6个broken交叉链接(subagent猜错兄弟课文件名)已全修**；Quiz去标签查15flag仅L30-Q3真泄露已修。遗留：Phase5补L13的Generic/Protocol。学习记录0022。
- 2026-07-02: **Phase 3 大纲 Tavily 联网复审** — 进 Phase 3 前按 Phase 2 那套审「LLM API 工程实践」大纲（14 课/5 模块）。Tavily 核对后**主体全部经得起 2026 检验**（退避/429、Fallback/LiteLLM、FC 循环、strict mode、原生 Prompt Caching、可观测性、成本分层）。**结构过关，四处增强非重构（仍 14 课）**：① P1 Structured Output 补「**约束解码/strict mode 在 token 级保证符合 Schema ≠ 旧 JSON mode**」（OpenAI 博客+docs guide+Anthropic consistency 文实锤，面试必考）；② P2 可观测性点名 **OTel GenAI 语义约定（`gen_ai.*` span，厂商无关）+ Langfuse**；③ P2 成本工程加**语义缓存**为独立杠杆②（按 embedding 相似度命中，GPTCache/Redis，与前缀缓存互补；interview-box 早就问这个区别却没进清单）；④ P2 重试补 **full jitter（防重试风暴）+ 幂等键（有副作用工具调用可安全重试）**。面试题 12+→14+；RESOURCES「工具工程」补 Structured Outputs 两条一手源（OpenAI guide + Anthropic）。div 96/96、5 新术语在页、新增 URL curl 200。学习记录 0021。
- 2026-07-02: **Phase 2 P3 打磨（择优采纳 12/17）** — 处理内容深审(0020)列出的 17 条 P3。P3 是 polish 非错，**择优改 12 条、刻意跳 5 条**（避免为凑数增啰嗦）。**采纳**：L17「长尾垃圾词→低概率词」+「T=0 退化为 argmax(接第6节)」+「seed 是 OpenAI-only，Anthropic 无」；L18「学界共识→有实证研究支持(该论文本是初步研究)」+「中文字 3 字节→常用字3、生僻4」；L19「数学下界→统计学习固有误差」+「自陈置信度不可靠(幻觉本就自信)」；L22「MMLU 点名为饱和/污染典型案例」+「领先一个身位→前沿常暂时领先、差距快速收窄」；L23 表格「1h 写约 2×」补全；L20「简单任务用推理模型还不免疫幻觉+可能 overthink 降准确率」；L24 judge「set 精确匹配对格式敏感→先归一化再比」。**跳过**：budget_tokens<max_tokens 关系（已三处"以官方为准"，再写过度specify）、成本拐点"量级"锚点（会写死 volatile 数）、0029「9+道」含糊（无害，题在课里已列举）等。复验：7 文件 div 全平衡、L24 代码 ast 全过、tiktoken=10 与温度透传未受影响、12 处 needle 全在。至此 Phase 2 内容审计的 P1/P2/P3 全部处理完毕。
- 2026-07-02: **Phase 2 内容深审 + 修复（读内容层，非结构层）** — 用户要求对刚生成的 L17–L24 再审。区别上轮结构检查，这轮**读内容 + 代码实证**：ast.parse 全部代码块、tiktoken 代码用真库跑核对、httpx/async 骨架逐行审；并派 3 个 subagent 当资深工程师深读找茬。**共 2 P1 + 8 P2 + 17 P3**。**P1 我独立复核后确认真实并修**：① L24 tiktoken 示例 token 数 12≠真实 10（课程说"数是真的"却穿帮，已改 10 + 金额 + 软化措辞）；② L23 OpenAI 缓存"约省 50%"已过时（官方 gpt-5 缓存输入 = 省 90%，仅老 gpt-4o 是 50%；5 处统一改"50%~90%，视模型代次，以官方为准"）。**修 6 条高 ROI P2**：L24 self_consistency 温度无法透传（注释承诺代码没实现→加 temperature 形参、Step2 仍默认 0）、L23「只有两根杠杆」→「最大的两根」、0029「59~70%」口径（缓存59~70%/路由40~85%分开）、L20「少说」标题→「别替它安排思考步骤」、L19 Self-Consistency「提高temperature」→「适中0.5~0.7」、L19 Quiz stem「按 OpenAI 论文」→「按《Why LM Hallucinate》(2025)」。**P3 未改**（polish 非错，留作后续清单）。改完复验：5 文件 div 平衡、L24 代码 ast 全过、tiktoken real=10=claim、温度透传三处通。**教训：subagent 自审会漏，P1 必自证、代码必实跑、数字必重算。** 学习记录 0020。
- 2026-07-02: **补 Phase 2 独立大纲页（与 Phase 1 的 0002 对称）** — 新增 `lessons/0029-phase2-ai-knowledge-outline.html`，沿用 0002 的 module/lesson-item/exercise 版式，含 L17–L24 全部课程链接 + 每课练习 + 一手参考源（HF 解码 / tiktoken cookbook / arXiv 2509.04664 / OpenAI reasoning / Anthropic caching+models）。配套：① style.css 补 `.badge-llm`（用已有 --llm 变量，之前 0029 用了未定义的 badge-llm）；② bottom-nav.js + course-bar.js 的 LESSONS 各注册 0029（phase='' → 可达但不计入 L## / 不占进度点，TOTAL 仍 24）；③ **bottom-nav「大纲」按钮改为按当前课 phase 动态选**（第二阶段→0029，否则→0002），并补回 bottom-nav 缺失的 `const cur`（原文件只有 prev/next，我的新代码引用了 cur）；④ 总览 0001 的 Phase 2 卡片加「📋 查看 Phase 2 详细大纲」链接。全部 node --check 过、div 平衡（0029=60/60、0001=96/96）、大纲按钮分阶段验证正确、0029 不污染 L## 编号。
- 2026-07-02: **Phase 2 全部课程落地 L17–L24（Tavily 佐证 + 并行 subagent）** — 按已审大纲写完「AI 知识与模型选型」8 课（文件 0021–0028）。L17 LLM本质+生成参数（含 temp=0≠可复现）、L18 Token/BPE/tiktoken（**中文更费token取决于分词器**，本机 tiktoken 实测"我喜欢学习语言。"cl100k=11→o200k=5）、L19 幻觉（校准视角 arXiv 2509.04664）、L20 推理模型/Extended Thinking、L21 能力边界+Base vs Instruct、L22 看懂Benchmark+选型、L23 Token经济学+两杠杆（Caching读~0.1×/写~1.25×、Routing）、L24 综合实战（模型体检报告）。**方式**：L17/L18 自写（有最新 tiktoken 实测），L19–L24 派 6 并行 subagent（喂文件名+L18样板+Tavily核过的事实+引用URL+铁律）。**导航**：bottom-nav.js + course-bar.js 各补 8 行（phase='第二阶段'），node --check 过、TOTAL=24、L16→L17 桥接、L17→L24 连续。**独立审核**（非仅信 subagent 自述）：8 课 div 全平衡、6脚本+单style齐、全部内部交叉链接解析成功；Quiz 去标签查泄露，修 L22-Q1（spread 9→2），余为等长并列无线索。遗留：Phase 2 未建独立大纲页（Phase1 有 0002，本次未扩建）。学习记录 0019。
- 2026-07-02: **Phase 2 大纲 Tavily 联网复审** — 用户要求进 Phase 2 前用 **Tavily 实搜**再审 Module 2。**Tavily 现已可用**（`TAVILY_API_KEY` 对 bash 可见、curl 200 真实 2026 URL；`/mcp` 仍空因会话启动目录非项目子目录，不阻塞）。Tavily top 多为 SEO 站、堆不可核实版本号/跑分（GPT-5.4/Opus 4.6/Elo 1548）→ 按铁律**只取一手源**（arXiv/厂商 docs），反向印证「版本号不写死」原则正确。结论：**结构过关，三处增强非重构（仍 8 课）**：① P1 幻觉「为什么」补**校准视角**（OpenAI/arXiv 2509.04664：奖励猜而非弃权）；② P2 新增「看懂 Benchmark」（MMLU-Pro/GPQA/SWE-bench/ARC-AGI 各测什么+榜单失真+开源vs闭源拐点）；③ P2 Token 经济学点名两杠杆 **Prompt Caching(读~0.1×/写~1.25×)+Model Routing**、真实降本 59–70%、输出 3–5×输入。面试题 7+→9+；实战补 Caching 前后成本对比；RESOURCES `LLM 原理与 API` 加 3 条一手源。div 96/96、"8 课"未 desync。学习记录 0018。
- 2026-07-02: **Phase 2 前大纲复审（对照 2026 最新资料）** — 用户要求进 Phase 2 前再审一次。**WebSearch 又降级**（结果全是"我无法联网"+参数知识），故弃搜索、改从权威源直取：Anthropic 工程博客 / Chip Huyen / MCP 官网 / GitHub API。核实结论：① Phase 10 案例 OpenClaw(381K★)/Hermes(207K★)/LangGraph(36K★) **今日仍在推送**、未 archived → 无需动；② MCP 官网证实已成事实标准（Claude/ChatGPT·OpenAI/VS Code/Cursor 全支持）→ 定位正确；③ Building Effective Agents 五大模式 & 工具工程、Chip Huyen planning/失败模式 → 均已被 Phase 3.4/5 覆盖。**唯一 P1 缺口**：Anthropic 2025 末官方文《Effective Context Engineering》固化了 2026 面试高频术语（context rot / attention budget / compaction / structured note-taking·agentic memory / sub-agent 架构 / just-in-time·progressive-disclosure 检索），我 Phase 4/5 讲得松、未点名。**已补**：Phase 4「基础」补 context rot+attention budget+right-altitude、Phase 5「进阶」补 compaction+agentic memory+sub-agent+JIT 检索；RESOURCES 加该文为 Phase 4/5 首选一手源。属增强非重构（不改阶段结构）。学习记录 0016。
- 2026-07-02: **订正"本机装不了 pydantic/httpx"的错误 + 实跑验证 L14/L15** — 此前判断有误：本机 `python -m ensurepip` 可引导出 pip，随后 `pip install pydantic httpx` 成功(pydantic 2.13.4 / httpx 0.28.1)。**用真实库把 L14 全部代码 + L15(httpx MockTransport 走真实 API)跑通**，claimed 输出全部一致——L14/L15 从"手工复核"升级为"实跑验证"。已改正 NOTES/学习记录里"装不了"的表述。课程本就是机器无关的(pip/uv 安装即可)，与本机能否装无关。

- 2026-07-02: **Part C 审核（L12–L16）** — 三查基本清白：① 内部交叉链接全有效、外部真实文档 URL 全 200(api.example.com 是代码内占位、Real Python 被 curl 拦属浏览器正常)；② L14 Pydantic v2 / L15 httpx 的 API 正确性(方法名 model_dump/model_dump_json/model_json_schema、Field 约束、field_validator+classmethod、httpx 异常类与捕获顺序，无 v1/v2 混用)——**后已用真实库实跑确认**；③ Quiz 已在编写时修至 0 泄露。修复：L15 SSE 片段补 `import json`；L14/L15 安装说明补 uv。结论：Part C 质量过关。

- 2026-07-01: **Part C 全部落地 L12–L16 → Phase 1 完结**（5 节课）— L12 生成器/0016、L13 类型提示/0017、L14 Pydantic/0018(闭合 @tool→Schema 线)、L15 httpx/0019、L16 async 并发/0020(收官)。可运行代码(L12/13/16 stdlib)开工前跑通；L16 课内批量练习实测 7/7、0.62s；L14 Pydantic / L15 httpx 代码按 v2/httpx 正确 API 写、标注 pip install + RESOURCES 链接（后于 2026-07-02 用真实库跑通验证，见下）。结构/6脚本/nav L01–L16 连续/各3-3 登记；Quiz 修掉 2 处答案泄露(0 剩余)。至此 Phase 1(L01–L16,16 节)全部完成，仅剩 Phase 2+。学习记录 0015。**遗留：Phase 5 补 L13 留下的 Generic/Protocol。**

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
