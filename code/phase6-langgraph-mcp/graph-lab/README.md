# Phase 6 · LangGraph 迁移练习

配合 L55 和 L56。只处理合成政策与本地 SQLite 草稿；不请求模型、不读取真实工单、不配置 LangSmith 上传。L55 替换 Phase 5 的只读调度，不改证据查询。L56 把暂停、恢复交给 LangGraph，保存仍调用 Phase 5 的业务接口。

## 环境和当前验证状态

`pyproject.toml` 给出目标组合：Python 3.11–3.13、LangGraph 1.2.24、`langgraph-checkpoint-sqlite` 3.1.3。版本与接口按发布元数据和官方文档核对；**当前未生成 `uv.lock`，也未实跑第三方 SDK**。安装获准后先同步项目，生成锁文件，再进行下面的离线验收；不要把静态检查当成兼容测试。

在仓库根执行：

```bash
uv sync --project code/phase6-langgraph-mcp/graph-lab --python 3.11
uv run --offline --locked --project code/phase6-langgraph-mcp/graph-lab python -I -X utf8 scripts/check-course-examples.py --suite langgraph
```

在项目目录中运行测试（它会用同一解释器启动新子进程）：

```bash
cd code/phase6-langgraph-mcp/graph-lab
uv run --offline --locked python -X utf8 -m unittest discover -s tests -v
```

## 验收边界

- 只读阶段对照 Phase 5 和独立预期：固定路径失败一次、动态路径完成两次、额度为一时只分派一次并耗尽。计数来自真实分派入口，不是模型用量。
- L56 分三个 SQLite 文件：`graph.sqlite` 持久化修订版、摘要、编排状态和操作 ID；中断值只有任务名和修订版。`reviews.sqlite` 保存可信测试驱动按身份、任务、动作和版本摘要绑定的合成决定。原始标题、正文和来源 ID 存在 `business.sqlite` 的 Phase 5 检查点，批准后也保存在草稿行中。返回给调用者的完整结果不写回图状态。
- `stage` 暂停，`inspect` 在新解释器中只凭宿主选定的线程与业务绑定重新读取预览，并逐字段比较第 2 版的标题、正文、来源 ID 和修订版。绑定不符则不显示另一版。`thread_id` 仅用于定位，不是授权。驱动显式选择 `resume`（审批中断）或 `recover`（提交后丢响应）；本课用 `snapshot.next` 的节点名限制调用阶段，不用它判定停止原因。
- 保存矩阵对照原 Phase 5 `store.resume` 与图宿主 `run_step`：无审批、错人/错租户/错任务/错动作、拒绝、旧版批准、有效保存、提交后丢响应与重放。无匹配决定时，Phase 5 直接调用返回 `rejected`，图宿主返回编排状态 `pending` 并不调用保存；两者只比较业务效果，不把返回标签当成相等。每步从草稿 `INSERT` 前的钩子数尝试，并另开业务连接查已提交行数；重放要保留原操作 ID 和完整草稿（标题、正文、来源 ID）。
- 矩阵中，Phase 5 在同一解释器内重开 SQLite 连接，图宿主命令由独立解释器调用；这是业务合同对照，不是同环境下的运行时对照。真实认证、并行审批、强杀/断电、网络对端、生产部署和升级兼容不在验收内。实验只允许固定的宿主身份和任务，测试夹具不是用户操作接口。**L56 SDK 验收：待实跑。**
