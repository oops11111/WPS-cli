# P3-280 Reject non-standard JSON numeric constants

Status: done. MCP tests: 42 passed; full suite: 452 passed/65 skipped.

## Goal

Keep MCP stdio parsing within the JSON data model instead of accepting Python's non-standard `NaN` and infinity extensions.

## Acceptance

- Reject `NaN`, `Infinity`, and `-Infinity` at any nesting depth during MCP decoding.
- Return a bounded JSON-RPC parse error with null ID and do not dispatch the request.
- Verify a subsequent valid request succeeds in the same process.

## Boundaries

Use the MCP-only parser; unrelated CLI configuration and artifact readers are out of scope.
