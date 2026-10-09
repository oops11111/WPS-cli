# Spreadsheet Formula, Cache and Display Inspection

P3-080 adds the read-only `spreadsheet-inspect` command and
`wps_agent_spreadsheet_inspect` MCP tool. It reports four distinct layers for
each cell: the formula stored in the file, the saved cached value read from the
file, the value recalculated by WPS in memory, and the text WPS displays.

The workbook is opened read-only and closed without saving. Formula caches are
not rewritten. `formula_matches_file` compares WPS's formula with the formula
read from the package; `cache_matches_recalculated` compares a saved formula
result with the in-memory calculation. A missing cache is reported as `null`
and therefore does not silently appear current. `recalculated_type` identifies
empty, text, boolean, number and displayed spreadsheet error cells. Date values
are reported as WPS's raw serial alongside the number format and displayed
date text.

Example:

```powershell
wps-agent spreadsheet-inspect --document-id <id> --sheet Calculation --range A1:F8
```

The selected range must be a finite A1 cell range. WPS/COM must be installed;
the existing `spreadsheet-read` remains the offline saved-value reader.

Local WPS integration on 2026-10-07 verified numeric and date display, formulas
and recalculation, a division-by-zero error, an empty cell, missing saved
formula cache behavior, and unchanged workbook bytes after inspection.
