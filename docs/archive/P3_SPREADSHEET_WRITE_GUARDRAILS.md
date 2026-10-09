# Spreadsheet Write Range Guardrails

P3-088 applies the same finite A1-range validation to `spreadsheet-write` and
`spreadsheet-formula-write` before backup creation or WPS COM launch. Both
reject malformed, reversed, unbounded, out-of-worksheet and larger-than-10,000
cell ranges. Valid ranges still require exact matrix dimensions; shape mismatch
continues to return `RANGE_SHAPE_MISMATCH`.

Offline tests cover both write commands with whole-column and oversized ranges
and assert backup and WPS functions are never called. Existing single-cell and
finite-range write preflight behavior remains supported.

## Value guardrails

`spreadsheet-write` also validates cell values before backup creation or WPS
COM launch, including in `--dry-run`:

- Each cell must be `null`, a string, a number or a boolean. Nested arrays and
  objects, and `NaN` or infinite numbers, return `INVALID_ARGUMENT`.
- Strings starting with `=`, `+`, `-` or `@` return `FORMULA_PREFIX_REJECTED`.
  WPS would evaluate such text as a formula, so formulas must go through
  `spreadsheet-formula-write`, which validates the recalculated values.
- Booleans are written as booleans instead of the text `True` or `False`.

This is a behavior change for callers that relied on writing formulas or
signed-number text through `spreadsheet-write`. That the spreadsheet engine
evaluates such strings is the documented behavior of Excel-compatible
applications; it was not re-verified against a live WPS installation here.
