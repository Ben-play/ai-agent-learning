# Tavily 搜索接入 —— 替代降级的内置 WebSearch

## 问题
内置 `WebSearch` 工具**服务端降级**：每条查询（连"法国首都"都）返回"我无法联网/我是 Copilot"+参数知识，**无任何真实来源 URL**。同环境下 `WebFetch`、GitHub API 均正常 → **不是本机网络问题**，是 WebSearch 服务端的事，重试无用。这正是 [[verify-strong-claims-search-not-found]] 的场景：降级搜索的"搜不到"不能当证据。

## 方案
接入 **Tavily**（专为 LLM/Agent 的搜索 API，免费额度约 1000/月）作为替代搜索通道。

- key 走**环境变量**：`.mcp.json` 用 `${TAVILY_API_KEY}` 引用，不落明文；`setx` 设永久用户变量。
- **双保险**：`.gitignore` 追加 `.mcp.json`/`.env`/`*.key`，密钥不入库（该仓库会 push 到 GitHub）。
- **已验证可用**：直接 `curl` Tavily API 返回 `HTTP 200` + 真实 2026 URL（Towards AI / Sourcegraph / Medium 等）。

## 采到的坑（都记下来）
1. **`! export X=...` 只活在那一条命令的 shell** —— Claude 主进程读不到。要让 MCP server 拿到 key，必须 `setx`（永久）或在启动 claude 前就 export，然后**重启**。
2. **project 作用域 `.mcp.json` 只在从项目根启动 claude 时加载** —— 会话不是从 `Q:\Agent\ai-agent-learning` 启动，则 `/mcp` 显示 "No MCP servers configured"（尽管 `claude mcp list` 能看到）。
3. **MCP server 首次需交互 approve**（安全机制，防配置注入后门）—— 我在工具上下文里无法自我批准。
4. Windows 下 Python `print` emoji 会因 cp1252 报 `UnicodeEncodeError` —— 脚本里强制 `PYTHONIOENCODING=utf-8` 或包 `io.TextIOWrapper`。

## 结果 / 现状
- **搜索能力现已可用**：我可直接 `curl` Tavily API 做实时搜索（真实 URL），**无需重启**。已作为默认搜索通道。
- **原生 `/mcp` tavily 工具**：仍 `⏸ Pending approval`，需用户「从项目根重启 claude + approve」才点亮 —— 属锦上添花，非必需。

**Why:** WebSearch 降级，用户要求补一个能真正联网搜索的能力。
**How to apply（搜索通道优先级）**：① 优先 Tavily（MCP 工具就绪后走工具，否则 `curl` API）→ ② WebFetch 抓具体 URL / GitHub API → ③ 内置 WebSearch 仅在恢复后作补充，且**降级响应一律不采信**。安全：该 key 已明文出现在对话，跑通后建议去 Tavily 后台 rotate、`setx` 覆盖旧值。
