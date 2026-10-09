# P3-304 MCP Config Server Name Scope

## Goal

Bound the selected `mcpServers` key consistently at every configured-audit entry point.

## Requirements

- Require a nonempty server name with a maximum length of 256 characters.
- Enforce the same rule in CLI parsing, MCP input schema, and direct Python API.
- Reject invalid values before config reads and process spawn.
- Do not include user-supplied names in validation error messages.

## Validation

- Cover empty, whitespace-only, exact-limit, and over-limit names.
- Assert invalid API names do not call the config loader or `Popen`.
- Run config audit, CLI/schema tests, full suite, safe regression, and package readiness.
