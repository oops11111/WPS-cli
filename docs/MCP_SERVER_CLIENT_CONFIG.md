# MCP Server Client 配置与 Smoke Harness

## Client 配置

本地 MCP server 原型使用 stdio transport。示例配置见：

```text
config/mcp_client_config.example.json
```

通用配置形态：

```json
{
  "mcpServers": {
    "wps-ai-agent-cli": {
      "command": "C:\\Users\\admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe",
      "args": ["-m", "wps_ai_agent_cli", "mcp-server"],
      "cwd": "C:\\Users\\admin\\Documents\\wps cli",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

如果 Windows `python` 指向 Microsoft Store 占位符，应把 `command` 替换成本机可用解释器。本轮验证使用：

```powershell
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

## Repeatable Smoke

`mcp-smoke` 会在进程内重复跑三类请求：

1. `initialize`
2. `tools/list`
3. `tools/call`，默认调用 `wps_agent_tasks`

推荐命令：

```powershell
$env:PYTHONPATH = "src"
python -m wps_ai_agent_cli mcp-catalog-snapshot
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli mcp-smoke --expected-min-tools 85 --tool-name wps_agent_tasks
python -m wps_ai_agent_cli mcp-config-audit --config config/mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 85
```

也可以逐条检查 JSON-RPC：

```powershell
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}"
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}"
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"wps_agent_tasks\",\"arguments\":{\"phase\":\"phase2\"}}}"
```

## Expected Results

- `initialize` 返回 `protocolVersion`、`serverInfo` 和 `capabilities.tools`。
- `tools/list` 当前返回 85 个工具。
- `mcp-catalog-snapshot` 返回当前 MCP 工具目录摘要，包含分类计数、修改类工具数、WPS-required 工具数和 safety-note 覆盖情况。
- `mcp-catalog-drift` 会对比当前 MCP 工具目录和 `config\mcp_catalog_guard.json` baseline；无 drift 时返回 passed。
- `tools/call` 返回 `isError = false`，并在 `structuredContent.mcp_call.response` 中包含原始 CLI `CommandResponse`。
- `mcp-smoke` 返回 `ok = true`，validation 中包含 `initialize_protocol`、`tools_list_count`、`tools_call_adapter` 三个 passed check。
- `mcp-smoke --arguments-json` 接受 JSON 对象，可验证需要必填参数的本地只读查询工具；批转换和打包等写入命令会被拒绝。
- `mcp-config-audit` 返回 `ok = true`，validation 中包含 config、cwd、command、env 和 configured tools/list smoke 检查。
- P3-009 额外验证 `mcp-smoke --expected-min-tools 38 --tool-name wps_agent_security_audit`，覆盖无参工具的 `tools/call` adapter 路径；当前工具面为 85 个工具。

## Current Limits

批转换完成后会立即写出响应，即使客户端继续保持 stdin 打开且不发送下一条请求。
worker 与主循环共用输出锁，JSON 行不会交错；响应通过请求 ID 对应，可能乱序。
P3-145 已通过真实子进程连续两次 DOCX 批转换验证这一行为。
P3-146 对任务状态读改写增加线程锁与跨进程文件锁，并原子替换 JSON。
Windows 上已验证并发进度与取消的终态保护、4 个进程创建 48 条记录均保留，
以及替换失败时原文件不变。POSIX 锁分支尚未在本机验证；外部程序直接改写状态文件不受此锁保护。

- 当前 server 原型是单进程、无会话状态的 stdio JSON-RPC handler。
- `wps_agent_html_batch_convert` 在独立 worker 中运行，stdio 主循环仍可处理后续状态请求；同一会话只允许一个在途批转换，重叠请求以 JSON-RPC `-32000` 返回 busy，客户端可在收到该错误后重试。
- 可用 `task_id` 跟踪批任务，并通过 `wps_agent_task_status_update` 将其置为 `cancelled`。取消是协作式的：当前文件处理结束后停止，已完成文件保留在 manifest，任务结果带有取消状态。
- EOF 到达时 server 会等待活动批请求结束并写出其响应，然后关闭 worker；意外 worker 异常返回不含内部细节的 JSON-RPC `-32603`，不影响其他请求响应。
- 当前 client 配置是本地示例，不包含远程部署、权限隔离或 secret 管理。
- 修改类工具仍应传入稳定 `request_id`，并优先使用 `dry_run`。
