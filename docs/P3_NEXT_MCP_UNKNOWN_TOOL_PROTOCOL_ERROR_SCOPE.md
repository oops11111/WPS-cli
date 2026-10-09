# P3-283 Unknown MCP tool protocol errors

Status: done. MCP/server/schema/adapter tests: 64 passed; full suite: 457 passed/65 skipped.

## Goal

Distinguish malformed `tools/call` requests from failures raised while executing a known tool.

## Acceptance

- Resolve the tool name against the live MCP catalog before invoking the adapter.
- Return JSON-RPC `-32602` for an unknown tool name and do not invoke the adapter.
- Continue returning `isError: true` tool results for failures produced by a known tool's execution.
- Cover handler and live stdio behavior.

## Boundaries

Preserve the current structured result schema and adapter behavior for known tools.
