# Phase 8 · Agent 工程实验

配合[第八阶段 L70–L79](../../../lessons/0091-phase8-agent-engineering-outline.html#lesson-plan)。继续用客服知识问答与本地草稿：怎样观测、按什么证据验收、何时拒绝分发，以及如何交给别人复跑。默认只使用 Python 3.11+ 标准库、合成资料和临时 SQLite；不联网调用模型、工具或后端，不读取真实业务数据。

### 从可信课程仓库根运行

若从 Pages 阅读，实验的 Python 与夹具不会发布到站点。使用已有的可信课程检出；可从[课程源码仓库](https://github.com/Ben-play/ai-agent-learning)取得对应课程版本，再从仓库根运行。不要在陌生目录中执行同名脚本，不要使用 `-O`。

```bash
python -I -X utf8 scripts/check-course-examples.py --suite engineering
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/gate.py
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/handoff.py
```

### 每段实验独立验证什么

- **L70–L71，`telemetry/`**：用接收器核对同一试验的 span 关联、字段、单位、未知用量、允许读取的角色和过期行为；用固定时钟对照审批 SLA 与执行超时。主线为本地教学接收器，不是 OTLP/Collector。
- **L72–L74，`evaluation/`**：开发集与验收集分离；每轮重建环境。同一主体的当前证据先核对再展示或保存草稿，待审或重放前来源变化会挡住内容。开放措辞只在来源和证据包硬门通过后进入脚本 Judge，另用手工标注校准。见 [L74 检查点](../../../lessons/0085-L74-judge-calibration.html#stage-practice-eval-foundations)。
- **L75，`authority.py`**：普通资料可改变建议内容，不授予执行权。禁止路径分发、业务 INSERT 尝试和数据库全表的提交行均为零；正控核对唯一一行的作用域、内容与回执。附独立的 Phase 6 本机回环 MCP scope 对照，不使用真实 OAuth 或生产凭据。
- **L76／L78，`design/`**：同一合成负载，先比任务成功与隔离，再比账本与端到端时长；另按场景核验函数、workflow 和有界只读单 Agent 的设计记录。它们不等于真实缓存性能，也不是工作流部署。
- **L77／L79，`gate.py` 与 `handoff.py`**：使用 `acceptance-v2` 和 `fixture-metrics-v2`，按实际发生的本地事件计合成积分和毫秒。基线 6/6、49 积分、约 8.17 积分／成功任务、最近秩 p95 100 ms；旧 `acceptance-v1.json` 只留作对照，不是当前输入。交接附 12 次独立评估、独立遥测、workflow 决策和清单内 SHA-256，轨迹不是这次门禁的运行轨迹。见 [L79 检查点](../../../lessons/0090-L79-engineering-baseline-handoff.html#stage-practice-engineering-handoff)。

### 验证失败确实会阻断

```bash
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/gate.py --variant drop-citation
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/gate.py --variant extra-proposal
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/gate.py --variant extra-read
```

三条命令都应退出 `1` 并输出合法 JSON。第一条丢 `retention.citations`，触发引用与成功率门槛；第二条只触发多余建议；第三条的实际额外读取将合成账本增到 53 积分、p95 增到 124 ms，只触发延迟门，恢复仍不再写。基线退出 `0`。不要用放宽阈值消除红灯。PR 工作流不安装项目依赖、不调用外部 API、不部署；合并阻挡还需仓库规则配置。

### 独立本地测试

```bash
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/telemetry/test_telemetry.py -v
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/evaluation/test_evaluation.py -v
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/design/test_design.py -v
python -I -X utf8 code/phase8-agent-engineering/engineering-lab/tests/test_gate.py -v
```

L75 的独立 MCP 对照可直接复跑 `python -I -X utf8 code/phase6-langgraph-mcp/skill-bridge/checkpoint.py`，仅使用本机回环和合成授权。

**未覆盖：**真实模型与 Judge、实际工具授权与反复故障、分布式一致性、实际账单和线上负载；另有未实跑的 OTel SDK 示例。本地通过不是生产准入。日志仅保留演练所需的合成标识、阶段和计数。
