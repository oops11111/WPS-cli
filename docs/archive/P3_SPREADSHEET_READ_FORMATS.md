# Spreadsheet Read Format Metadata

P3-081 extends `spreadsheet-read` without changing its existing `values`
matrix. A parallel `cell_metadata` matrix reports each cell's A1 address,
stored value type, Excel number format, date-format recognition, and broad
format category (`empty`, `text`, `number`, `date`, `percentage`, or
`currency`). Both matrices have the same shape and order.

The reader remains offline and reads saved workbook values. It does not produce
locale-specific display strings or evaluate formulas. Date values remain
Python date/datetime values where the workbook format identifies them;
percentage and currency values remain their underlying numeric values. Use
`spreadsheet-inspect` when actual WPS recalculation and displayed text are
needed. In particular, WPS may display hashes when a formatted value does not
fit the current column width; that is a layout state, not a value conversion.

Unit tests cover date, percentage, currency and blank cells while asserting the
legacy raw-value matrix is unchanged. Opt-in WPS tests compare the metadata
categories with actual date, percent, currency and empty-cell display text.
