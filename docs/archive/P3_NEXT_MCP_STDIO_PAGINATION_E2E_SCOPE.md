# P3-266 MCP Stdio Pagination End-to-End Contract

## Objective

Verify that the CLI MCP server preserves protocol behavior across one live stdio process, beyond direct in-process handler tests and per-page config-audit subprocesses.

## Scenario

- Start `python -m wps_ai_agent_cli mcp-server` as a child process.
- Send `initialize`, first `tools/list`, second `tools/list` using the first page's exact `nextCursor`, and a read-only `wps_agent_tasks` call.
- Keep stdin open between requests and verify each response is available with its matching JSON-RPC ID.
- Assert cache metadata, complete ordered catalog traversal without duplicates, and clean process exit after stdin closes.
- Send an invalid cursor through the same process and assert JSON-RPC `-32602` while later requests still succeed.

## Safety and Acceptance

The test uses no WPS launch, user documents, remote service, or mutating tool. Acceptance requires the complete response sequence, process liveness while stdin remains open, and exit code zero after EOF.
