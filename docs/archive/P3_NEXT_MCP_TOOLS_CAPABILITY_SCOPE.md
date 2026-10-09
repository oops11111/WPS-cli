# P3-292 MCP Tools Capability Scope

## Goal

Ensure configured MCP audit only performs tools/list after the server advertises the tools capability during initialize.

## Acceptance

- Missing `capabilities.tools` fails the configured audit before `notifications/initialized` or `tools/list`.
- Malformed capability values remain rejected with bounded diagnostics and child cleanup.
- The checked-in server advertises the capability and completes the paginated audit.

## Boundaries

- Preserve protocol negotiation, metadata validation, stdio bounds, and descriptor/schema validation.
- Do not execute tools or launch WPS.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
