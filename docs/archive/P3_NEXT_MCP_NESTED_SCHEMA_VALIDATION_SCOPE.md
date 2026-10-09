# P3-290 Nested MCP Schema Validation Scope

## Goal

Validate the nested JSON Schema structure advertised by configured MCP tools, extending the current top-level schema checks.

## Acceptance

- Recursively validate property schemas and array `items` schemas.
- Validate `required` lists and supported keyword value shapes at each schema path.
- Report at most 20 diagnostics containing page, tool index, and bounded schema path/field, without echoing untrusted values.
- The checked-in configured MCP server's complete paginated catalog continues to pass.

## Boundaries

- Preserve current persistent stdio, response/line/queue bounds, and descriptor checks.
- Do not execute tools or launch WPS.
- Run focused audit tests, the full suite, safe regression, package readiness, and documentation freshness.
