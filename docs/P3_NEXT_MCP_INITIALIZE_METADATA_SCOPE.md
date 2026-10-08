# P3-291 MCP Initialize Metadata Scope

## Goal

Validate the initialize response metadata consumed by the configured MCP client audit.

## Acceptance

- `serverInfo` contains nonempty string `name` and `version`.
- `capabilities` is an object; when `tools` is present, it is an object with supported metadata types.
- Malformed handshakes produce bounded audit failures and reap the child process.
- The checked-in MCP server passes and a subsequent independent valid audit remains healthy.

## Boundaries

- Preserve current protocol version negotiation, stdio limits, pagination, and descriptor schema checks.
- Do not execute tools or launch WPS.
- Run focused audit tests, the full suite, safe regression, package readiness, and documentation freshness.
