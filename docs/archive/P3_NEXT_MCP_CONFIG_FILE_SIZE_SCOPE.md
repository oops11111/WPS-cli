# P3-297 MCP Config File Size Scope

## Goal

Bound memory consumed while loading the MCP client configuration file before JSON parsing.

## Acceptance

- Reject configuration files larger than a documented fixed byte limit before full-file decoding/parsing.
- Return a bounded `config_json_valid` or dedicated size check failure.
- Do not launch the configured command for oversized configuration.
- Valid UTF-8 configuration at/below the limit continues to work.

## Boundaries

- Preserve command/env validation, process limits, and persistent MCP audit behavior.
- Do not log file contents.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
