# P3-300 MCP Config JSON Depth Scope

## Goal

Bound nesting in MCP client configuration before recursive JSON object construction.

## Requirements

- Define and document a conservative maximum JSON container depth.
- Detect depth while respecting quoted strings, escapes, and braces/brackets inside string values.
- Reject over-depth input before `json.loads` and before process spawn.
- Keep diagnostics bounded and avoid exposing config contents.
- Preserve ordinary JSON and the existing exact 1 MiB valid-config case.

## Validation

- Cover nested arrays/objects at the limit and one level over.
- Cover braces, brackets, and escaped quotes inside strings.
- Assert over-depth input fails before parsing/spawn using a parser spy and `Popen` spy.
- Run config audit tests, full default suite, safe regression, and package readiness.
