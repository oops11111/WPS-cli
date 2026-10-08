# P3-272 Reject Blank MCP Tool Names

## Objective

Ensure catalog audits do not accept empty or whitespace-only tool names as valid string names.

## Contract

- `mcp-smoke` and `mcp-config-audit` count a missing, non-string, empty, or whitespace-only name as invalid.
- Invalid names fail the catalog check even when the total number of tool objects meets the minimum.
- Duplicate-name checks continue to run for catalogs whose names are all valid.

## Validation

Test empty and whitespace-only names through both audit paths, and retain the existing full traversal and duplicate-name tests.
