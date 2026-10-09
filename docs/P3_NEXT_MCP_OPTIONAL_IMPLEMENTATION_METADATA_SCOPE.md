# P3-293 Optional MCP Implementation Metadata Scope

## Goal

Validate optional fields in the MCP initialize `serverInfo` implementation object without making optional metadata mandatory.

## Acceptance

- Optional `title` and `websiteUrl` fields are type/format checked when present.
- Optional icons are an array of valid icon records with required URI and supported optional field types.
- Missing optional fields remain valid; malformed values fail before `notifications/initialized` with bounded diagnostics and process cleanup.
- The checked-in server and valid external-style fake server pass.

## Boundaries

- Preserve required name/version and tools capability checks.
- Do not fetch icon URLs or make network requests.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
