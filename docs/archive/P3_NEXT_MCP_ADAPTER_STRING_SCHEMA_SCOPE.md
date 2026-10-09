# P3-305 MCP Adapter String Schema Scope

## Goal

Ensure the MCP adapter enforces every supported string constraint advertised by the tool catalog.

## Requirements

- Support `minLength`, `maxLength`, and `pattern` in adapter argument validation.
- Treat malformed schema patterns as bounded schema errors, not uncaught exceptions.
- Keep diagnostics limited to argument names and never echo argument values.
- Preserve existing type, enum, and numeric bound behavior.

## Validation

- Cover each string constraint at lower/upper and mismatch boundaries.
- Cover malformed regex metadata through a schema test seam.
- Confirm the catalog contains no unsupported property keywords.
- Run MCP adapter/schema tests, full suite, safe regression, and package readiness.
