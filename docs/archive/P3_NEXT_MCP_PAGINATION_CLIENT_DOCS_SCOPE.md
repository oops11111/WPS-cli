# P3-268 MCP Pagination Client Documentation

## Objective

Make the client contract clear after `tools/list` changed from one whole-catalog response to cursor pagination.

## Required Documentation

- Distinguish the current 81-tool catalog from the 50-tool per-page maximum.
- State that `nextCursor` is opaque; clients pass it unchanged as `params.cursor` and continue until the response omits `nextCursor`.
- Explain that `mcp-server --once-json` handles one request and therefore returns one page, while `mcp-smoke` and `mcp-config-audit` traverse and aggregate all pages.
- Update both client setup and MCP tool-schema behavior references; retain the existing protocol/version and safety guidance.

## Validation

Run documentation freshness and the MCP server/smoke/config-audit tests. Do not change runtime behavior or user client configuration.
