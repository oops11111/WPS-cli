# P3-281 MCP request ID uniqueness

Status: done. MCP tests: 43 passed; full suite: 453 passed/65 skipped.

## Goal

Prevent ambiguous response correlation and duplicate method execution when a client reuses a JSON-RPC request ID within one persistent stdio session.

## Acceptance

- Track each syntactically valid string/integer ID received in a session, including IDs on requests that later fail method-level validation.
- Reject a reused ID before scheduling or invoking the method, with a bounded JSON-RPC error.
- Cover ID equality/type behavior, a duplicate mutating call with no side effect, and a later unique request on the same process.

## Boundaries

The registry is process/session-local. Notifications have no IDs and are not tracked; one-shot diagnostic invocations remain independent.
