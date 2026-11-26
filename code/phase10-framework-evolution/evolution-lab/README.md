# Phase 10 · 框架演进与按需协作实验

配合[阶段 10 L85–L92](../../../lessons/0106-phase10-framework-evolution-outline.html)使用。Phase 6 与 Phase 8 为先修，Phase 9 可跳过。课程数据为合成客服证据与本地草稿，不调真实模型、不上传遥测、不读取真实凭据。Pages 只发布本页与课件，不发布 Python、夹具、检查点或报告；从[可信课程仓库](https://github.com/Ben-play/ai-agent-learning)检出对应版本后运行。

### 标准库本地验收（Python 3.11+）

从仓库根运行，不使用 `-O`：

```bash
python -I -X utf8 scripts/check-course-examples.py --suite evolution
```

L85–L87 的标准库实验由旧程序实际产生本地检查点。先用独立金标验证场景变化并封好准备包，再复制给两臂，核对恢复前的实际文件摘要和读回结果。分别记录兼容、当前来源、批准绑定、调用、INSERT、原稿与持久回执。阶段检查点包含 17 个同源比较案例和 11 个回退案例；一次局部练习可以只选所需案例。临时文件在退出后清理。可从 `checkpoints/` 目录运行：

```bash
python -B -X utf8 contract.py seed
python -B -X utf8 contract.py compare
python -B -X utf8 contract.py fallback
python -B -X utf8 contract.py compare --case approve --case replay
python -B -X utf8 contract.py stage
python -B -X utf8 -m unittest -v test_contract test_snapshot_boundary
```

`test_snapshot_boundary` 用标准库替身检查最新线程的选择与业务预检，不导入 LangGraph，也不读取真实 saver。

### 真实图验收单列：未实跑

L87 的部署前置要求[真实 LangGraph 兼容演练](../../../lessons/0100-L87-migration-fallback.html#stage-practice-checkpoint-compatibility)单独通过。标准库的 JSON/SQLite 合同不是 LangGraph saver 文件，也不证明 SDK 或旧版运行环境可恢复。目标组合沿用 Phase 6：Python 3.11–3.13、`langgraph==1.2.24`、`langgraph-checkpoint-sqlite==3.1.3`。在本环境未安装相关依赖、未生成 `uv.lock`，故仅有独立源码与静态检查。

在已有获准、依赖锁定的对应环境中，先通过[Phase 6 图实验](../../phase6-langgraph-mcp/graph-lab/README.md)，然后从 `checkpoints/` 使用该环境的 Python 运行 `python -B -X utf8 langgraph_rehearsal.py`。报告区分 `phase6_original_snapshots`（实际由 Phase 6 原图生成）和 `phase10_application_fixtures`（课程自建应用格式）；`--native-only` 只执行原快照对照，不代替完整演练。两臂续跑最新线程，公开检查点 ID 用于观察，不作为历史重放输入。Phase 6 原审批文件没有新版来源表，补充核验由课内固定宿主完成，不改旧 saver。

分别记录版本、准备包、最新快照与业务读回；无实跑结果还须标为待验。课程只比较应用版本，不证明 SDK 自身可升级。并发、断电、跨库事务与新版已修改后回滚另需验收。

### 架构决策与选修

- **L88–L89**：`architecture/` 在同一合成任务集上比较三个基线及按需委托。精确答复、实际行为、合成账本与预算分别核验。坏账本不改变正确答复数，但会阻止推荐；费用和延迟均保留失败试次。不把本地标签或模型替身当模型质量。
- **L90–L91**：`protocols/` 是隔离的内存替身，分别演练 A2A 任务状态与 MCP 宿主防御边界，不创建连接，不使用真实令牌或 SDK。规范与 SDK 引用是文档基线，不是互操作实测。
- **L92**：`source-study/` 判定课程自有的惰性任务及回执记录。固定 Hermes 源码只阅读，不安装、导入或执行，也不作框架安全证明。

从仓库根分别运行：

```bash
python -I -X utf8 code/phase10-framework-evolution/evolution-lab/architecture/test_architecture.py -v
python -B -X utf8 -m unittest discover -s code/phase10-framework-evolution/evolution-lab/protocols -v
python -I -X utf8 code/phase10-framework-evolution/evolution-lab/source-study/test_lab.py -v
```

交接要列出：使用版本、原快照身份、允许的恢复路径、预期和实际效果、未验项，以及保留或改变架构的理由。选修通过与否不影响 Phase 11；真实检查点前置没有通过时，不得拿这里的本地报告替代。
