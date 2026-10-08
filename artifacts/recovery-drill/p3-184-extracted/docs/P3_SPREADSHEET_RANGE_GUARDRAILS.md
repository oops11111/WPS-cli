# Spreadsheet Range Read Guardrails

P3-082 applies shared A1 range validation to `spreadsheet-read` and
`spreadsheet-inspect` before the workbook is opened or WPS is probed. Both
commands reject malformed, reversed, whole-row, whole-column, out-of-worksheet
and larger-than-10,000-cell ranges with structured `INVALID_RANGE` or
`RANGE_TOO_LARGE` errors.

Single cells and finite rectangles up to the limit remain supported. Rejected
requests do not iterate workbook cells, launch WPS, create backups, or modify
the source file. This limit is deliberately scoped to read/inspect operations;
write operations retain their separate shape and mutation validation.
