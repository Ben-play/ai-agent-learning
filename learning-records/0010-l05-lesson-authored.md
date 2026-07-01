# L05 课程已编写并审核（函数定义与参数）

把 Phase 1 的 L05 从大纲条目落地为完整课程 `lessons/0009-L05-functions-and-parameters.html`（Phase 1 现有 L01–L05 五节内容课）。

## 内容与设计
- 覆盖大纲 L05 全部知识点：位置/关键字/默认参数、仅关键字(`*`)/仅位置(`/`)、`*args`/`**kwargs`、调用处解包(`*`/`**`)、多值返回(元组)、可变默认参数陷阱(回链 L03)、类型注解签名。
- Agent 导向主线：「函数签名 = 工具契约」，明确指向 L11(@tool 自动从签名生成 Schema)与 L14(Pydantic)，让基础课服务于后面的工具工程。
- 实战练习 = 大纲指定的「设计 Agent 搜索工具函数」(query/max_results/filters → 结构化 dict，含空值校验、max_results 夹紧、filters 仅关键字)。
- 结构与 L03/L04 一致：3 Quiz、5 面试题、知识图谱、参考资源、总结。

## 审核优化（用户明确要求「生成完别忘了审核」）
- **代码全部实跑通过**（Python 3.14，按 HTML 内实际代码校验）：位置/关键字默认、`f(1,2)` 对仅关键字参数抛 TypeError、`call_llm` 的仅位置/仅关键字双向报错、`**d` 解包、可变默认参数陷阱复现、练习参考实现(含 max_results 夹到 50、空 query 抛 ValueError)全部符合课程所述。
- **Quiz 质量**：3 题各恰 1 个正确答案；发现 Q1 选项长度不均(6–10 字)有轻微泄露风险，已改成等长的平行短语(仍是默认值 5 / 因缺参报错 / 被置为 None / 取值为 False)。
- 结构平衡(div/details/pre/ol/ul 全对称)、5 脚本齐全、进度条 31%、两个 nav 脚本 node --check 通过、已在 bottom-nav/course-bar/大纲 0002 三处登记并加链接。

**Why:** 延续 L04 的做法把大纲落地为可交互课程，并按用户要求做生成后审核。
**How to apply:** L05 可用，是 L01–L05 的第 5 节。下一节 L06(作用域、闭包与 Lambda)可照此结构继续；本课已为 L11 装饰器铺垫 `*args/**kwargs`。参见 [[0009-l04-lesson-authored]]。
