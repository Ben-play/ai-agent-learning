# L58–L59 · MCP 回环 HTTP 实验

这个实验把 Phase 4/5 的只读证据（`KB-01` 导出保留期、`KB-02` 过期后处理、`KB-03` 同步时间）搬到真实 HTTP 连接上，再单独验证本地草稿的保存边界。Python 3.11+ 标准库，无第三方依赖、模型、外部地址、发工单或文件写入。

在可信课程仓库根执行：

```bash
python -I -X utf8 code/phase6-langgraph-mcp/http-lab/test_lab.py -v
```

或分别保存 [L58](../../../lessons/0067-L58-mcp-streamable-http.html) 和 [L59](../../../lessons/0068-L59-mcp-skill-authority.html) 中的四个参考块，并从仓库根用 `python -I -X utf8 文件名.py` 运行（不要加 `-O`）。

- `l58-http-check` → `L58 ACCEPTED`
- `l58-transfer-check` → `L58 TRANSFER PASSED`
- `l59-auth-check` → `L59 ACCEPTED`
- `l59-transfer-check` → `L59 TRANSFER PASSED`

## 兼容性记录

- **标准库客户端 × 本目录只读实例（2026-07-28）**：此前实测发现、列表、调用、JSON 与 POST-SSE；还检查了镜像头与版本错误、Origin 校验、GET/DELETE 不开流。
- **标准库客户端 × 本目录受保护夹具（2026-07-28）**：此前实测凭据受众／scope、所有权、快照和批准的拒绝路径及保存正控；本轮修改未复跑。
- **官方 Python SDK 客户端 × SDK 服务端：待验收。** 这是原 Phase 6 大纲尚未交付的项。先固定两端发布版本与协议版本，再记录同一用例的响应、媒体类型和工具入口次数；没有实际结果前不标记兼容。

[Python SDK v2.3.0 的版本支持说明](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/protocol-versions.md)明示支持 `2026-07-28` 与旧版本；这是文档证据，不是本实验与该 SDK 或其他宿主、服务端的互通结果。实验选择标准库是为了在未安装 SDK 的环境里直接看到报文与失败分支，不是因为 SDK 不支持现代协议。迁移时固定双方 SDK 发布版本和协议版，再复测上表所需行为；不要用旧版 `initialize` 示例推断新版本。

## 实现范围

- `main.py` 的 `local_lab()` 在 `127.0.0.1` 的系统分配端口开一个短生命周期、单线程请求处理的 HTTP 服务；每次关闭响应连接，块退出后停止服务、关闭监听套接字并回收线程。客户端使用固定 IP、固定 `/mcp`，不跟随重定向、不走代理；有 socket 超时与 8 KiB 正文／响应读取上限。存在 `Origin` 时只允许本实例完整回环来源，其他返回 403；Host 的精确比较是附加的实验限制。不是面向不受信来流的服务。
- 每个请求自己带 `params._meta` 中的协议版和客户端能力；客户端信息建议发送，但只是自报。校验 HTTP `MCP-Protocol-Version`、`Mcp-Method` 和 `tools/call` 的 `Mcp-Name`；缺失或不一致是 HTTP 400 / `-32020`，头与正文一致但版本不支持是 HTTP 400 / `-32022`，含 `data.requested` 与 `data.supported`。正文缺必填能力是 400 / `-32602`，未实现的 RPC 方法是 404 / `-32601`。
- 默认 JSON；合法只读调用带 `progressToken` 时，本实验选择 SSE，先发关联进度再发原 ID 的最终结果并关闭。无独立 GET 流、`initialize` 握手、MCP 会话 ID 或 `Last-Event-ID` 恢复。现代订阅同样用 POST 响应流，但本实验未实现订阅。
- 这是受限的教学子集，不是通用 MCP SDK、服务或一致性声明。只支持固定工具及参数白名单、显式 `Accept` 两种媒体类型、带 `Content-Length` 的 JSON 请求、有限的 SSE 帧格式。不实现通用 JSON Schema 验证、`Mcp-Param-*`、通知 POST、MRTR、分页、完整 SSE 解析与取消生命周期、扩展或持久化。检测到流写入断开就停止；不模拟长时间作业、外部副作用或断电。

## 夹具为何不是 OAuth

`Authorization` 的值是不可解析的合成标签，不含身份或声明，也不是可用凭据。查表只确定声明受众和 scope；宿主在启动服务时独立注入不可变的当前操作者、所有者快照和批准。每条请求仍重新检查凭据与业务条件。阶段检查点的取证实例可以不注入待存草稿；它公布固定工具目录，但没有快照时不能保存。保存入口才增加计数并登记内存记录，拒绝不能进入；账本随实例销毁，不持久化、去重或处理审批撤销。只读实例不接受保存工具，受保护实例也没有请求参数能更改宿主上下文。禁止用真实凭据来运行此实验。

生产采用 MCP OAuth 要实现受保护资源元数据、发行方发现与协议流程（适用的 PKCE、回调及 `iss` 检查）、在授权与换取令牌时声明目标 `resource`、验证真实令牌的发行方／受众／有效性和最小 scope，并使用 HTTPS、安全的存储与日志脱敏。不要把入站令牌透传给下游。还要建立每个请求与业务主体的可信关联，检查租户、所有权、原意图与批准；不把 scope、Skill 或自报元数据当成批准。实验没有实现这些 OAuth 服务与 TLS 能力，也不会发现或访问任何授权服务器。

POST-SSE 是一条响应的传输方式。官方可选 Tasks 扩展（`io.modelcontextprotocol/tasks`）定义显式任务句柄与 `tasks/get` 等交互，不替代宿主的应用检查点、当前授权核对、原操作标识与效果回执。本目录不实现该扩展；持久恢复和重放仍是独立的业务验收。

一手资料：[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) · [逐请求版本协商](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) · [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) · [Authorization Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations) · [Tasks 变更](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes)。
