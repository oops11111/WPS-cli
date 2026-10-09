# P3-270 MCP Smoke Malformed-Response Handling

## Objective

Keep the smoke command diagnostic even when a JSON-RPC handler returns a malformed response shape.

## Cases

- `initialize`, `tools/list`, or `tools/call` has no `result`, a null result, or a non-object result.
- A malformed tools/list page is summarized without dereferencing `None` or an unexpected type.
- The command returns `ok=false` with failed checks and useful compact response summaries, not an uncaught exception.

## Boundaries

Use mocked in-process JSON-RPC responses only. Do not launch WPS, call external services, or modify client configuration or documents.
