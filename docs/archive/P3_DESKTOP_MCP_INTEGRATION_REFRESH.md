# P3-009 Desktop MCP Integration Evidence Refresh

Date: 2026-10-03

## Scope

This refresh verifies the desktop MCP configuration path against the current 38-tool surface. It covers config audit, configured `tools/list`, in-process `initialize`, `tools/list`, `tools/call`, and the remaining real desktop-client gap.

## Evidence

### Config Audit

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli mcp-config-audit --config config\mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 38 --request-id p3-009-config-audit
```

Result:

- config exists and is valid JSON
- server `wps-ai-agent-cli` found
- cwd exists
- Python command resolves
- args include `mcp-server`
- `PYTHONPATH=src` is configured
- configured `tools/list` smoke returned 38 tools

### MCP Smoke

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli mcp-smoke --expected-min-tools 38 --tool-name wps_agent_security_audit --request-id p3-009-mcp-smoke-security-fixed
```

Result:

- `initialize_protocol`: passed
- `tools_list_count`: passed with 38 tools
- `tools_call_adapter`: passed through `wps_agent_security_audit`

## Harness Fix

The refresh found and fixed a smoke-harness assumption: `mcp-smoke` always passed `phase=phase2` to `tools/call`, which only fits `wps_agent_tasks`. The harness now passes `phase` only for the tasks tool and uses only `request_id` for no-argument tools. It also treats missing adapter responses as structured failure evidence instead of raising `AttributeError`.

Regression test added:

- `test_mcp_server_smoke_passes_for_no_argument_tool`

## Real Desktop Client Gap

This refresh proves the local desktop client configuration file can launch the MCP server and retrieve the 38-tool surface through the configured command. It does not prove an external GUI MCP client has manually connected and invoked a tool in its own UI. That remains a separate live-client verification item.

## Next Work

The next production-readiness task should scope the next advanced WPS capability with fixture, dry-run, backup, validation, and WPS smoke evidence requirements before implementation.
