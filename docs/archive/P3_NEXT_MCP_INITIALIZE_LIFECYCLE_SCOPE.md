# P3-277 MCP initialize lifecycle ordering

Status: done. MCP tests: 36 passed; full suite: 446 passed/65 skipped.

Status: implementation and focused subprocess verification in progress.

## Goal

Enforce the MCP legacy lifecycle on persistent stdio sessions without breaking direct single-message CLI inspection.

## Acceptance

- Persistent stdio accepts initialize as the first request and tracks successful initialization.
- Normal requests before initialization and before the `notifications/initialized` transition receive deterministic protocol errors and do not invoke tools.
- Duplicate or malformed lifecycle transitions do not silently advance session state.
- A valid initialize -> initialized notification -> tools/list sequence succeeds in a live subprocess.
- If `--once-json` intentionally remains a handler-level diagnostic path, document that it does not represent a persistent MCP session.

The ordering follows the [MCP lifecycle specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle#initialization).

## Boundaries

In-memory state is scoped to one stdio process. Do not change HTTP transport, client configuration, or tool execution semantics.
