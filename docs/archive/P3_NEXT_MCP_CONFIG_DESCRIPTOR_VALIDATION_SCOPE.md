# P3-287 Configured MCP Descriptor Validation Scope

## Goal

Strengthen the configured MCP client audit so a successful paginated `tools/list` traversal confirms usable tool descriptors, not only valid names and cursors.

## Acceptance

- Every listed descriptor has a valid MCP tool name, nonempty description/title where required by the local contract, and object `inputSchema` with `type: object`.
- Optional `outputSchema`, when present, is an object schema with `type: object`.
- Every page is checked; malformed descriptors fail the audit with bounded, page/index-specific diagnostics.
- Fake-server tests cover malformed fields on a later page; the checked-in configured server passes.

## Boundaries

- Preserve one persistent stdio process, handshake, request IDs, cursor checks, and deadline behavior.
- Do not execute tools or launch WPS.
- Run focused audit tests, the full suite, safe regression, package coverage/readiness, and documentation freshness.
