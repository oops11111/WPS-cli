# P3-296 MCP Config Diagnostic Privacy Scope

## Goal

Ensure configured process validation errors provide useful bounded diagnostics without exposing sensitive configuration values.

## Acceptance

- Environment variable values and full argument strings are absent from serialized validation results.
- Command and working-directory summaries are capped at 256 characters.
- Tests cover valid and malformed command/args/env values and assert exact privacy/length properties.
- Normal configured-client audits remain successful.

## Boundaries

- Preserve existing strict shape and invalid-character checks.
- Do not change process execution behavior or log environment values.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
