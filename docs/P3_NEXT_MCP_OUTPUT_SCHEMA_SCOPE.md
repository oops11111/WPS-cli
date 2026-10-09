# P3-282 MCP output schema alignment

Status: done. MCP-related tests: 54 passed; full suite: 455 passed/65 skipped.

## Goal

Ensure the output schema advertised by every MCP tool describes the actual `structuredContent` returned from `tools/call`.

## Acceptance

- Define the shared structured result schema for the `{mcp_call, errors}` envelope.
- Ensure all catalog entries expose that schema.
- Test both successful adapter results and tool-execution errors against the required fields and JSON types.

## Boundaries

Preserve the existing `structuredContent.mcp_call` API shape; update its schema contract rather than changing downstream response structure.

The server conformance requirement is specified in the [MCP Tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#output-schema).
