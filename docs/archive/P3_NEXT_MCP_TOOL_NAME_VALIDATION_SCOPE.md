# P3-273 MCP Tool Name Validation

## Objective

Apply the MCP tool-name recommendations consistently to the project's catalog smoke and configured-server audit.

## Rules

- Name length is 1-128 characters inclusive.
- Allowed ASCII characters: letters, digits, underscore, hyphen, and dot.
- Count invalid names separately from duplicate valid names so diagnostics remain useful when both occur.
- Keep case-sensitive uniqueness behavior.

## Validation

Test the lower/upper length boundaries and representative invalid values (space, special character, non-ASCII, and overlength) through both audit paths. Confirm the current 81-tool catalog still passes.

The naming recommendation is described in the [MCP Tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#tool-names).
