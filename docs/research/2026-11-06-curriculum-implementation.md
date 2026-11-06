# 2026-11-06 课程优化实施与验证

依据：[课程审查](2026-11-06-curriculum-audit.md)。本次是教材建设，不是学习者掌握记录。

## 已实施

- 保留11阶段、L01–L38与Python基础；总纲/README明确38课已编写，Phase4–11仅规划。
- L25增加Responses主线、Messages原生接口、Chat兼容边界与离线辨认；L26增加Responses事件/终态实践；L28补拒答/截断、业务授权边界、Responses格式对照和失败分支验收。
- L30重写完整用户轮次分组、工具ID闭合、信任边界、输出预留和压缩后复算；不支持的输入明确失败。
- L35增加Responses工具循环对照，与L36统一先授权再解析的dispatch契约；前移小型Agent评估。
- L36参数模型真正接入注册与分发，区分展示和授权；非法/越权/未知工具零执行，受控错误回填。
- L37改为负载驱动成本决策，先质量/延迟门槛再比较成功任务成本；明确缓存模型/API/TTL/写读价和语义缓存隔离。
- L38重写为无Key、标准库可运行的fixture执行骨架；正常/拒答/截断、text/json/本地流消费、授权、参数、工具失败、重试/fallback、尝试和轮数预算、已知/未知usage、缓存计费算法均有断言。固定fixture不是厂商适配、真实缓存或网络流的证据。
- L33默认元数据、正文显式授权脱敏；OTel版本和映射非零迁移保证。L23缓存数值限定为给定练习参数。
- 更新MCP参考基线为2026-07-28，增加非编号Skills参考页；总纲前移持久恢复目标，补RAG/记忆生命周期与单Agent基线。
- 同步第三阶段大纲、目录标题、Q&A、术语、RESOURCES、历史审查提示与NOTES；Phase3估算545min，Phase1/2仍625/430，总计1600min。
- 新增 `scripts/check-course-examples.py`，只执行显式白名单自检，不执行联网SDK示例。

## 实际验证

1. 使用现有 `code/phase1-python/part-a-basics/agent-hello/.venv/Scripts/python.exe`（Python 3.11.15、Pydantic 2.13.4）运行：

```bash
code/phase1-python/part-a-basics/agent-hello/.venv/Scripts/python.exe -I -X utf8 scripts/check-course-examples.py
```

结果：L25/L26/L28/L30/L36/L37/L38 **7/7 PASS**，每个子进程仅输出对应 `Lxx ACCEPTED`。全局Python的Pydantic环境缺typing_extensions，未安装或更改配置；选用了已有完备虚拟环境。

2. 修改/新增的17个HTML页面：嵌套、唯一ID检查通过；29道Quiz均单一正确项且正确项不唯一最长；19个标记为Python的代码块编译检查通过（编译不等于在线执行）。
3. L25–L38时长header/Phase3大纲/lesson-times.json一致；阶段545min与总计1600min求和一致。
4. `node --check assets/course-catalog.js` 通过。
5. `git -c core.whitespace=cr-at-eol,trailing-space diff --check` 通过；保留仓库CRLF约定，不把CRLF误报当真实尾随空格。
6. 现有 `scripts/build-pages.py` 在新建系统临时目录构建完整 `/ai-agent-learning/` 站点成功：77个白名单文件，本地精确大小写链接通过。没有部署或上传站点；临时目录在检查后清理。
7. 独立只读复审识别两项真实课间边界问题并已修复：L35在dispatch前解析非法JSON导致错误无法受控回填；L38非重试异常没有入账。后者新增不重试、不fallback、未知usage的断言，并重跑7/7通过。

## 修正过程中出现的失败

- 初次L38自检的缓存成本预期写成0.00086，实际应为0.00088；已更正并复验。
- 初次Pages构建因L30/L36链接未发布的docs目录失败；改为注明合并后可访问的仓库源码URL后，全站构建通过，不扩大Pages白名单。
- 初次Quiz检查发现L23/L33两处正确项唯一最长（L33另有一题旧选项同类问题），已统一选项并复验29题通过。

## 明确未实施 / 未验证

- 没有编写Phase4–11完整课程、真实MCP Server、持久工作流或RAG实现；这些仍为明确标注的规划/验收目标。
- 没有付费模型调用、SDK在线联调、真实Token精度/模型质量/缓存收益或网络SSE测试。
- 没有浏览器视觉、移动端、打印、离线Service Worker交互验证；本次复用既有组件，不改共享视觉系统。
- 没有执行所有38课代码或全仓既有项目测试，验证范围是上述新增白名单、结构和构建。
- 未修改MISSION、用户L03/L04个人练习、settings或gitignore；这些原有改动保持不动。未创建学习完成记录。
- 已按工作流同步main后创建 `feat/curriculum-reliability-update`；没有暂存、提交、推送、PR或部署。
