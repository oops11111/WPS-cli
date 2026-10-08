# MCP 工具契约草案

## 目标

P2-004 将当前 CLI 能力整理成可复用的 Agent/MCP 工具契约草案。P2-005 在此基础上新增本地 adapter：它可以把 MCP 风格的工具名和 JSON 参数映射到现有 CLI response 层。P2-006 新增本地 MCP server 原型，通过 JSON-RPC/stdout 暴露 `initialize`、`tools/list` 和 `tools/call`。

P2-007 新增本地 client 配置示例与 repeatable smoke harness，P2-008 新增 desktop config audit，详见 `docs/MCP_SERVER_CLIENT_CONFIG.md`。

## 已暴露入口

```powershell
python -m wps_ai_agent_cli mcp-tools
python -m wps_ai_agent_cli mcp-tools --category spreadsheet --mutates-document true
python -m wps_ai_agent_cli mcp-tool-schema --name wps_agent_spreadsheet_write
python -m wps_ai_agent_cli mcp-tool-schema --name wps_agent_writer_fill_bookmark
python -m wps_ai_agent_cli mcp-catalog-snapshot
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli mcp-call --name wps_agent_tasks --arguments-json "{\"phase\":\"phase2\"}"
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
python -m wps_ai_agent_cli mcp-server
python -m wps_ai_agent_cli mcp-smoke --expected-min-tools 81 --tool-name wps_agent_tasks
python -m wps_ai_agent_cli mcp-config-audit --config config/mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 81
python -m wps_ai_agent_cli security-audit
python -m wps_ai_agent_cli performance-baseline
```

两个命令都返回现有 `CommandResponse` envelope：

- `ok`
- `command`
- `request_id`
- `backend`
- `summary`
- `data`
- `validation`
- `errors`

## 工具命名规则

- MCP 工具名使用 `wps_agent_<domain>_<action>`。
- `cli_command` 保留原始 CLI 命令名，便于 adapter 直接映射。
- 支持用 MCP 工具名或 CLI 命令名查询单个 schema。
- 所有 schema 带 `schema_version = draft-2026-10-03`。

## 契约字段

每个工具 schema 包含：

- `name`: MCP 工具名。
- `cli_command`: 对应 CLI 命令。
- `title`: 人类可读标题。
- `description`: 工具用途。
- `category`: 能力分组。
- `mutates_document`: 是否会修改文档或创建恢复性文件状态。
- `requires_wps`: 是否需要真实 WPS COM 能力。
- `idempotency`: request_id 与幂等策略说明。
- `input_schema`: JSON Schema 风格的输入草案。
- `output_contract`: 统一 `CommandResponse` 输出契约。
- `cli_example`: 等价 CLI 示例。
- `safety_notes`: 安全注意事项。

## 当前分组

| category | 代表工具 |
| --- | --- |
| `environment` | `wps_agent_inspect_env`, `wps_agent_wps_process_audit` |
| `project` | `wps_agent_plan`, `wps_agent_project_status`, `wps_agent_workspace_health`, `wps_agent_local_handoff_summary`, `wps_agent_validation_runbook`, `wps_agent_documentation_freshness`, `wps_agent_tasks` |
| `smoke` | `wps_agent_com_smoke`, `wps_agent_calc_smoke`, `wps_agent_convert_smoke`, `wps_agent_writer_table_smoke` |
| `documents` | `wps_agent_register_document`, `wps_agent_documents` |
| `safety` | `wps_agent_backup_document`, `wps_agent_list_backups`, `wps_agent_restore_backup` |
| `writer` | `wps_agent_writer_replace`, `wps_agent_writer_table_write` |
| `spreadsheet` | `wps_agent_spreadsheet_read`, `wps_agent_spreadsheet_write`, `wps_agent_spreadsheet_formula_write`, `wps_agent_spreadsheet_sheets`, `wps_agent_spreadsheet_rename_sheet`, `wps_agent_spreadsheet_create_sheet`, `wps_agent_spreadsheet_set_sheet_visibility`, `wps_agent_spreadsheet_delete_sheet`, `wps_agent_spreadsheet_copy_sheet`, `wps_agent_spreadsheet_set_sheet_tab_color` |
| `presentation` | `wps_agent_presentation_replace` |
| `validation` | `wps_agent_validate_document`, `wps_agent_snapshot_document` |
| `operations` | `wps_agent_operation`, `wps_agent_operations`, `wps_agent_mutation_request_inspect` |
| `tasks` | `wps_agent_task_status_create`, `wps_agent_task_status_update`, `wps_agent_task_status`, `wps_agent_task_statuses` |
| `recovery` | `wps_agent_task_recovery`, `wps_agent_task_recovery_playbooks` |
| `security` | `wps_agent_security_audit` |
| `performance` | `wps_agent_performance_baseline` |
| `batch` | `wps_agent_scan_dir`, `wps_agent_batch_report` |
| `maintenance` | `wps_agent_cleanup_plan`, `wps_agent_cleanup_approval_manifest`, `wps_agent_artifact_retention_summary` |
| `mcp` | `wps_agent_mcp_tools`, `wps_agent_mcp_tool_schema`, `wps_agent_mcp_catalog_snapshot`, `wps_agent_mcp_catalog_drift`, `wps_agent_mcp_call`, `wps_agent_mcp_server`, `wps_agent_mcp_smoke`, `wps_agent_mcp_config_audit` |
| `sync` | `wps_agent_cloud_sync_package`, `wps_agent_sync_package_inspect`, `wps_agent_sync_package_summary`, `wps_agent_sync_package_manifest`, `wps_agent_sync_package_coverage`, `wps_agent_sync_package_readiness` |

`spreadsheet-sheets` / `wps_agent_spreadsheet_sheets` is a read-only, no-WPS
inventory. It reports worksheet order, visibility, dimensions, tab color,
protection, bounded cell/formula counts, frozen panes, filters, print settings,
page breaks, merged ranges, data validations, conditional formatting,
ignored-error flags, plus workbook defined names and calculation properties.
Large collections have explicit total counts and truncation flags.

## Adapter 行为

`mcp-call` 是本地 adapter 的命令行入口。它执行以下步骤：

1. 用 `name` 查找 MCP 工具 schema，支持 MCP 工具名或 CLI 命令名。
2. 校验 `arguments_json` 是否为 JSON object。
3. 校验必填参数和未知参数。
4. 将 snake_case 参数转换成 CLI flag，例如 `operation_request_id` → `--operation-request-id`。
5. 对布尔 flag 只在值为 true 时传入，例如 `dry_run` → `--dry-run`。
6. 捕获现有 CLI `CommandResponse` JSON，并放入 `data.mcp_call.response`。

递归保护：`mcp-call` 不允许调用自身，避免 adapter 嵌套执行失控。

示例返回结构：

```json
{
  "command": "mcp-call",
  "data": {
    "mcp_call": {
      "tool_name": "wps_agent_tasks",
      "cli_command": "tasks",
      "cli_argv": ["tasks", "--phase", "phase2"],
      "exit_code": 0,
      "response": {
        "command": "tasks",
        "ok": true
      }
    }
  }
}
```

## Server 原型行为

`mcp-server` 是本地 JSON-RPC/stdin/stdout 原型入口：

- `initialize`: 返回 `protocolVersion = 2026-07-28`、server info 和 tools capability。
- `notifications/initialized`: 作为 notification 处理，不返回响应。
- `tools/list`: 返回 81 个工具，包含 `name`、`title`、`description`、`inputSchema`、`outputSchema`、`annotations` 和 `_meta`。
- `tools/call`: 调用 `mcp_adapter.call_mcp_tool`，并返回 `content` 与 `structuredContent`。
- `--once-json`: 处理一个 JSON-RPC 请求后退出，便于 CLI smoke 与单元测试。

当前原型是单进程、无会话状态的 stdio server。P2-007 已补充可复制的 client 配置和 smoke harness。

## Adapter 实现约束

1. MCP server 应复用 `mcp_adapter.call_mcp_tool`，不重新实现 WPS 操作。
2. 修改类工具必须保留 `request_id`、备份、验证和 task status 语义。
3. 对 `mutates_document = true` 的工具，adapter 应优先要求 Agent 传入稳定 `request_id`，并允许 `dry_run` 时先预览。
4. 对 `requires_wps = true` 的工具，adapter 应在调用失败时返回结构化错误，不吞掉 COM 后端的诊断信息。
5. 长任务工具应继续使用 `task_id`、`task-status` 和 `task-recovery` 构成恢复闭环。

## 验证证据

- 单元测试：`python -m unittest discover -s tests`，当前测试集通过数以实际运行输出为准。
- `mcp-tools --category spreadsheet --mutates-document true` 可返回表格写入与公式写入工具契约。
- `mcp-tool-schema --name wps_agent_spreadsheet_write` 可返回必填参数、WPS 依赖、修改属性和统一输出契约。
- `mcp-call --name wps_agent_tasks --arguments-json "{\"phase\":\"phase2\"}"` 可通过 adapter 调用现有 `tasks` CLI response 层。
- `mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}"` 可返回 server capabilities。
- `mcp-catalog-snapshot` 可返回当前 81-tool MCP 目录摘要，包含分类计数、修改类工具、WPS-required 工具和 safety-note 覆盖情况。
- `mcp-catalog-drift` 可对比当前目录和 `config\mcp_catalog_guard.json` baseline，输出结构化 drift 清单。
- `mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}"` 当前返回 81 个工具。
- `mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"wps_agent_tasks\",\"arguments\":{\"phase\":\"phase2\"}}}"` 可通过 server 调用 adapter。
- `mcp-smoke --expected-min-tools 81 --tool-name wps_agent_tasks` 可重复验证 initialize、tools/list 和 tools/call。
- `mcp-config-audit --config config/mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 81` 可验证 client 配置并通过配置启动 `tools/list` smoke。
- `security-audit` 可审计 8 个修改类工具的 request_id、task_id、dry-run、备份和 WPS/文件系统边界。
- `performance-baseline` 可采集 6 个不启动 WPS 的核心命令耗时和输出规模。
