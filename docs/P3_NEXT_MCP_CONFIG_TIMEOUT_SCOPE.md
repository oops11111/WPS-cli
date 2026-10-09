# P3-302 MCP Config Audit Timeout Scope

## Goal

Keep configured-client audit subprocess execution bounded regardless of entry point.

## Requirements

- Choose and document a positive maximum timeout suitable for local MCP startup and paginated tools/list.
- Enforce the same minimum and maximum in the CLI, MCP input schema, and Python API.
- Reject invalid timeouts before any configured command is spawned.
- Preserve the existing 15-second default.
- Keep timeout failures structured and ensure child cleanup remains reliable.

## Validation

- Cover zero, negative, maximum, and maximum-plus-one values at each public boundary.
- Assert invalid values do not invoke `subprocess.Popen`.
- Retain an integration-style timeout case proving the child is reaped.
- Run config audit tests, full suite, safe regression, and package readiness.
