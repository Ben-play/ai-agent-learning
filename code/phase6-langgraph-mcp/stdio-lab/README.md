# L57：本地 MCP stdio 取证实验

标准库，Python 3.11+。从**仓库根**运行，不装依赖、不配置密钥。每个验收命令只打印对应的标记，不调用模型：

```bash
python -I -X utf8 code/phase6-langgraph-mcp/stdio-lab/lab.py worked
python -I -X utf8 code/phase6-langgraph-mcp/stdio-lab/lab.py transfer
python -I -X utf8 code/phase6-langgraph-mcp/stdio-lab/test_lab.py -v
```

前两条的唯一输出分别是 `L57 ACCEPTED`、`L57 TRANSFER PASSED`。想看带方向的实测帧及子进程读取审计，另用 `python -I -X utf8 code/phase6-langgraph-mcp/stdio-lab/lab.py trace`；带方向标签的显示不是线上帧。也可复制[课页](../../../lessons/0066-L57-mcp-stdio.html)内两个 Python 验收块，保存后分别以 `python -I -X utf8 路径到脚本.py` 从仓库根运行。

## 怎么走一遍

- `lab.py` 的父进程是宿主，`StdioClient` 是其中的客户端。客户端通过当前 Python 的绝对解释器路径和固定的本文件路径、不经 shell，启动 `--serve` 子进程。不把完整宿主环境、请求中的路径或命令传给子进程。子进程仅公布并运行只读的 `read_evidence`，证据来自内存夹具。
- 走 `server/discover → tools/list → tools/call`：UTF-8 字节、单行 JSON-RPC、按 ID 对齐。发现和列表成功结果按规范提供 `ttlMs: 0`、`cacheScope: "public"`；夹具不缓存目录。`stderr` 单独排空与取证。每次交换限 3 秒；结束时先关闭 `stdin`，收尾按阶段限时等待，必要时终止、强杀并等待回收。Windows 的终止不依赖 POSIX 信号。
- `worked`：KB-01 提供「生成后保留 7 天」；已知工具参数不合法是 `isError: true`，未知工具和不合法的调用外壳是 JSON-RPC 错误。只有有效调用在读入口留下审计。宿主仅把经形状、范围和任务绑定校验的来源与摘录投影成模型侧数据。
- `transfer`：北、南校区各有 `PICKUP-01`。两条真实响应单独用于各自任务；把南区响应当作北区候选时，形状校验仍成功，绑定却拒绝。比较的是两道门对同一份有效响应的处理，不是伪造坏 JSON，也没有做第三次读取。

## 版本依据与边界

按 MCP `2026-07-28` [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)、[版本规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)、[元数据](https://modelcontextprotocol.io/specification/2026-07-28/basic/index#_meta)、[发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)和[工具](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)构造示例。请求逐条使用 `params._meta`；不混用 `2025-11-25` 的 [`initialize` / `notifications/initialized`](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)。官方 Python SDK [v2.3.0 稳定发布](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)的[版本支持说明](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/protocol-versions.md)确认支持现代版本与旧握手模式；本环境不允许安装外部 SDK 验证 Windows 实跑，实验选用已实测的标准库教学子集，不是通用 SDK，也不作完整合规声明。

**本地实测：** Windows 11 / Python 3.11.15，7 项标准库测试通过。覆盖真实子进程、UTF-8、发现与列表的 `ttlMs` / `cacheScope`、调用、错误分层、读取审计、作用域和协议版本负例。请求未送达时观察父端读超时及 EOF 后的回收；未发出 EOF 时观察逾时终止与回收。

**未覆盖：** SDK 或第三方服务互操作、其他操作系统实跑、终止后再强杀的升级分支、旧版降级、并发、通知或请求级取消、分页、完整 JSON Schema 解释器、资源／提示、HTTP／远端授权或真实身份、模型回答质量。分区只是合成任务范围；不认证调用者，不充当 OS 沙箱。运行无外网、模型、秘密和上传。
