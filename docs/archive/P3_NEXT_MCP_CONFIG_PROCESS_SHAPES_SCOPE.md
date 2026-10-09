# P3-294 MCP Process Configuration Shape Scope

## Goal

Reject malformed configured-server process parameters before spawning the configured command.

## Acceptance

- Command is a nonempty string; args is a list containing only strings; env is a string-to-string object.
- Invalid command/args/env shapes fail audit checks and do not invoke `Popen`.
- The checked-in example configuration and valid fake-server configurations continue to pass.

## Boundaries

- Preserve process lifecycle, deadlines, output bounds, metadata and descriptor validation.
- Do not reinterpret arguments or use a shell.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
