# P3-278 Reject duplicate JSON object keys

Status: done. MCP tests: 38 passed; full suite: 448 passed/65 skipped.

## Goal

Ensure each MCP stdio JSON line has one unambiguous interpretation at every object nesting level.

## Acceptance

- Detect duplicate JSON object member names recursively before dispatch.
- Return a bounded JSON-RPC invalid-request response with null ID; do not dispatch ambiguous requests.
- Cover duplicate top-level method/ID and nested tool arguments, including a real stdio process that remains usable for a subsequent valid request.

## Boundaries

Apply the rule to the MCP stdio JSON parser. Do not change unrelated project JSON file readers or non-MCP CLI JSON parsing.
