# P3-262 MCP tools/list Cursor Pagination

## Selected Target

Add cursor pagination to the MCP `tools/list` response. The Phase 3 production-readiness risk register already identifies catalog growth as a client-load and response-size risk; the server currently returns every tool definition in one response.

## Protocol Contract

- Follow MCP 2026-07-28 pagination semantics: accept an optional cursor and return `nextCursor` only when another page exists.
- Cursors are opaque to clients and stable for the static catalog. The server chooses a fixed page size of 50.
- Invalid, malformed, empty, or out-of-range cursors return JSON-RPC error code `-32602`; an empty cursor parameter is not treated as an omitted cursor.
- Preserve the current result fields, including `resultType`, `ttlMs`, and `cacheScope`, on every page.
- Full traversal returns every catalog tool exactly once and in the original catalog order.

## Scope

- Add deterministic cursor parsing and page selection to `mcp_server.py`.
- Update local MCP smoke and configured-client audit paths to follow `nextCursor` when they need a total tool count.
- Keep CLI `mcp-tools`, catalog snapshots, and schema counts as whole-catalog views.
- Add protocol-level tests for first, middle, final, malformed, empty, and out-of-range cursors.

## Out of Scope

- Pagination for prompts, resources, or resource templates.
- Changing tool schemas, tool ordering, or per-tool behavior.
- WPS launch, document mutation, remote services, or user configuration changes.

## Validation

- Traverse all pages and assert stable order, no duplicates, no omissions, and correct `nextCursor` termination.
- Assert every page retains cache metadata and full-page result shape.
- Assert invalid cursors produce `-32602` without a partial success response.
- Run MCP server, MCP smoke, configured-client audit tests, documentation freshness, and the complete unit suite.

Protocol references:

- https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- https://modelcontextprotocol.io/specification/2026-07-28/server/tools
