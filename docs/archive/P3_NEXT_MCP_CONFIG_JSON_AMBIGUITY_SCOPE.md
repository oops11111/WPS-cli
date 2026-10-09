# P3-299 MCP Config JSON Ambiguity Scope

## Goal

Reject JSON configuration whose meaning depends on permissive parser behavior.

## Requirements

- Detect duplicate object member names at every nesting level.
- Reject non-standard numeric constants such as `NaN`, `Infinity`, and `-Infinity`.
- Return bounded `MCP_CONFIG_AUDIT_FAILED` diagnostics without echoing config contents.
- Never spawn the configured MCP process for rejected input.
- Preserve behavior for valid standard JSON configurations, including exact-limit input.

## Validation

- Add table-driven duplicate-member and numeric-constant cases, including nested values.
- Assert each malformed configuration fails before `subprocess.Popen`.
- Run the MCP configuration audit tests, full default suite, safe regression, documentation freshness, and package readiness.
