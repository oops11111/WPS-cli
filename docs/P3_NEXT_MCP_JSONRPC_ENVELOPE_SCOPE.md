# P3-275 MCP JSON-RPC request envelope validation

## Goal

Make the local MCP stdio server's accepted JSON-RPC request envelope behavior explicit and regression-tested.

## Acceptance

- Review validation of `jsonrpc`, `method`, `id`, and `params` types against the supported MCP stdio contract.
- Cover malformed envelopes and notification behavior at the handler boundary.
- Exercise representative invalid and valid requests through a subprocess, proving invalid input does not terminate later valid exchanges.
- Keep errors bounded and avoid changing tool execution semantics outside the validated contract.

## Boundaries

Local protocol behavior only. Do not modify desktop client configuration or require remote Git/WPS.
