# P3-298 MCP Config JSON Shape Scope

## Goal

Reject syntactically valid JSON whose root or `mcpServers` section does not match the expected configuration structure.

## Acceptance

- The configuration root must be an object.
- `mcpServers` must be an object before server lookup.
- Arrays, strings, scalars, null, and malformed `mcpServers` return bounded check failures without raising.
- No malformed-shape case invokes `Popen`; valid example and fake configs continue to pass.

## Boundaries

- Preserve the 1 MiB file limit, process input validation, and persistent MCP behavior.
- Do not log configuration contents.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
