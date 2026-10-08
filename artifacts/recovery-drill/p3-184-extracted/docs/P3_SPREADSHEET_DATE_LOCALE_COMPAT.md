# Spreadsheet Date and Locale Compatibility

P3-113 verifies the distinction between saved workbook values and WPS-rendered
text. `spreadsheet-read` preserves dates, numeric values and stored number
formats; it does not claim to render locale-specific strings. The cached-value
comparison uses the workbook's own epoch, including the 1904 date system.

The opt-in WPS integration fixture uses a 1904-epoch workbook, leap-day dates,
a formula-produced date, and locale-tagged percentage/number formats. It checks
that dates resolve to 2024, numeric values do not overflow the selected column
width, percentage display is present, formulas recalculate, and the workbook
hash remains unchanged after inspection.

Observed on the current Windows/WPS environment: the `[$-407]` locale marker
remained in the stored number format, but displayed text followed the host's
regional presentation (for example, the 12.5% sample displayed as 13% and the
number used the host's separators). The display text returned by WPS is
authoritative for that machine; locale tags are not treated as a guarantee of
identical rendering across host locales. Broader WPS versions/locales still
need a compatibility matrix.

Offline tests separately verify 1900- and 1904-epoch serial comparisons. They
are file-library evidence, not a substitute for the opt-in WPS check.
