# P3-295 MCP Process Character Validation Scope

## Goal

Reject process configuration strings that the operating system cannot safely use before attempting process creation.

## Acceptance

- Reject NUL in command, any argument, environment key, or environment value.
- Reject empty environment keys and keys containing `=`.
- Invalid values fail with bounded diagnostics and do not invoke `Popen`.
- Valid configured and fake servers continue to pass.

## Boundaries

- Preserve no-shell execution, process deadlines, and existing type validation.
- Do not log environment values.
- Run focused audit tests, full suite, safe regression, package readiness, and documentation freshness.
