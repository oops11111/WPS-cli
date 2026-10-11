# P3-284 MCP input schema validation

## Goal

Validate tool arguments against the input schemas advertised by `tools/list` before executing a tool.

## Acceptance

- Validate the JSON types used by the catalog, plus required and additional-property rules.
- Enforce enum values, integer bounds, and array item types wherever those constraints appear.
- Return JSON-RPC `-32602` before adapter dispatch for invalid arguments.
- Preserve `isError` tool results for failures from known tools with valid arguments.

## Boundaries

Implement only the JSON Schema subset present in the current MCP tool catalog; catalog-wide tests must fail if an unsupported constraint is introduced.

MCP requires servers to validate tool inputs; see the [MCP Tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#security-considerations).
