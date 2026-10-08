# Spreadsheet Write Range Guardrails

P3-088 applies the same finite A1-range validation to `spreadsheet-write` and
`spreadsheet-formula-write` before backup creation or WPS COM launch. Both
reject malformed, reversed, unbounded, out-of-worksheet and larger-than-10,000
cell ranges. Valid ranges still require exact matrix dimensions; shape mismatch
continues to return `RANGE_SHAPE_MISMATCH`.

Offline tests cover both write commands with whole-column and oversized ranges
and assert backup and WPS functions are never called. Existing single-cell and
finite-range write preflight behavior remains supported.
