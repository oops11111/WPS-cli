# Spreadsheet Worksheet Inventory

P3-089 adds `spreadsheet-sheets` and the read-only MCP tool
`wps_agent_spreadsheet_sheets`. It returns worksheets in stored workbook order
with a 1-based index, name, visibility state (`visible`, `hidden` or
`veryHidden`), used dimension, maximum row/column, normalized tab color
(`none` or `#RRGGBB`), and worksheet protection metadata.
The view metadata also includes frozen-pane position and autofilter range.
Print metadata includes normalized print area/title ranges and stored page
orientation/paper-size code.
Manual row/column page-break positions are sorted and capped at 1,000 each;
their full counts and truncation flags are returned separately.
Data-validation rules are returned per worksheet as sorted target ranges, rule
types, operators and blank-cell policy. At most 1,000 rules are listed, with
the total count and truncation flag supplied separately.
Conditional-formatting rules are summarized in sorted order by target range,
rule type, operator and priority, also capped at 1,000 with a full count and
truncation flag.
OOXML ignored-error settings are read per worksheet as target ranges and their
stored flags. The parser streams worksheet XML, caps returned records at 1,000,
and reports the full count/truncation status.
Merged-cell metadata includes a stable row/column-sorted `merged_ranges` list,
the full `merged_range_count`, and `merged_ranges_truncated`; at most 1,000
ranges are returned per worksheet.
Workbook- and worksheet-scoped defined names are exposed in stable scope/name
order through `defined_names`, with `defined_name_count` and
`defined_names_truncated`; at most 1,000 names are returned. Targets are
reported as stored formula/reference text, not evaluated values.
The workbook-level `calculation` object reports stored calculation mode,
full-calculation-on-load, force-full-calculation, calculate-on-save and
iteration flags as-is; inventory does not recalculate or alter them.
Macro-enabled `.xlsm` packages are opened with VBA preservation enabled for the
in-memory read and the auxiliary VBA archive is explicitly closed. The
inventory still never saves the workbook; a macro-enabled fixture verifies the
source hash remains unchanged.

Protection metadata includes `protection_enabled`, `protected_cell_count` (the
number of locked cell positions in the used rectangle) and
`protection_scan_truncated`. Inventory also reports `populated_cell_count`,
`formula_count` and `inventory_scan_truncated`. These counts are based on the
used rectangle and are only calculated when it contains at most 100,000 cells.
Larger rectangles return null for populated/formula counts and for the
protected-cell count when protection is active. No full-sheet scan is attempted
past the cap. Password material is never returned.

The command parses the workbook package in memory through openpyxl. It does not
launch WPS or save the workbook. Tests cover visible, hidden and very-hidden
sheets, tab colors, formula/populated/locked-cell counts, protected and
unlocked cells, scan truncation, and unchanged file bytes.
