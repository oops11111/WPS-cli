# P3-303 MCP Config Audit Expected Tools Scope

## Goal

Bound the expected configured-server tool count consistently across public entry points.

## Requirements

- Choose a positive lower bound and a conservative maximum count.
- Enforce the same bounds in CLI parsing, MCP input schema, and direct Python API.
- Reject invalid values before reading the config or launching a configured process.
- Preserve the existing default expected count.
- Keep normal paginated tool discovery behavior unchanged.

## Validation

- Cover zero, negative, maximum, and maximum-plus-one at each boundary.
- Assert invalid direct API values do not load config or invoke `Popen`.
- Run config audit, CLI/schema tests, full suite, safe regression, and package readiness.
