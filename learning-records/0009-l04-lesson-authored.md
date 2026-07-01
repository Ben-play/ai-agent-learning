# L04 课程已编写（流程控制、字符串与 Prompt 构造）

应用户要求，把 Phase 1 的 L04 从「大纲条目」落地为完整课程 `lessons/0008-L04-control-flow-and-prompt.html`（此前只有 L01–L03 三节内容课，L04 是空的）。

## 内容与设计
- 覆盖大纲 L04 全部知识点：流程控制（if/elif/else、for/while、break/continue/for-else、match-case）、字符串与 f-string 高级用法（格式化、`!r`、`=`、多行）、字符串方法、**Prompt 构造三模式**（变量替换 / 条件拼接 / 上下文注入）。
- 全程 Agent 导向：用「Agent 是循环里的决策机器」串起流程控制；match-case 用于分发 LLM 动作；Prompt 构造作为 Phase 4/5 的雏形。
- 实战练习 = 大纲指定的「Prompt 模板引擎」；含 4 道 Quiz、5 道面试题、参考资源、知识图谱、总结，结构与 L03 完全一致。
- 已注册进 bottom-nav.js / course-bar.js，并在大纲页 0002 给 L04 标题加了链接。

## 验证（按审核清单）
- **所有代码示例实跑通过**（Python 3.14）：match-case 解构、f-string 各格式、字符串方法、for-else（quiz q1 答案=不执行）、练习参考实现产出与课程展示的输出逐字一致。
- HTML 标签平衡、4 quiz/4 正确答案、5 个脚本齐全；两个 nav 脚本 node --check 通过。

**Why:** 用户先说「审核 L04」，但 L04 尚不存在；确认后改为「现在动手写」。
**How to apply:** L04 已可用，是 L01–L03 之后的第 4 节。后续 L05+ 可照此结构继续；Prompt 构造部分到 Phase 4/5 会进阶，可回链本课。参见 [[0008-phase1-outline-v7-1]]。
