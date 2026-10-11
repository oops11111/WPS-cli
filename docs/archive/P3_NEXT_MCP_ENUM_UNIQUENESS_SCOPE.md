# P3-307 MCP Enum Uniqueness Scope

## Goal

Validate MCP schema enum metadata according to JSON value equality rather than Python's cross-type equality.

## Requirements

- Reject empty enum arrays and duplicate values.
- Distinguish JSON booleans from numbers (`true` must not collide with `1`).
- Detect duplicate nested array/object values with object member order treated as irrelevant.
- Preserve valid mixed-type enums.
- Return bounded schema errors without argument values.

## Validation

- Cover duplicate scalars, nested arrays, and objects with reordered members.
- Cover `[true, 1]` as distinct JSON enum values and `[1, 1.0]` according to JSON numeric equality.
- Confirm current catalog enums remain valid.
- Run adapter/schema tests, full suite, safe regression, and package readiness.

## Completion

Completed 2026-10-09 in `mcp_adapter.py` with adapter tests covering uniqueness, membership, and catalog enums. Full suite 589 passed/66 skipped; safe regression 7/7. Package-readiness commands were removed earlier (G-07) and were not reintroduced.
