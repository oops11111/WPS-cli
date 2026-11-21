# Stage 8: offline manual table geometry attribution

Base: `ebd94400baa8ca0881e102c08b5917388dd5ee30`. No product code,
original input, threshold or baseline changed; no renderer was started.
The manual still fails strict F2: 0.8959 < 0.90. This stage accepts reproducible
measurements, not a product repair or an F2 pass.

## Measured result

The [raw geometry](../artifacts/manual-geometry-20261121/geometry.json) records
source SHA-256, Python/pdfplumber versions, existing PDF vector/text coordinates,
DOCX grid/physical cell properties and computed browser table styles. It reuses
the committed Stage 7 browser/WPS evidence (Edge 157.0.4341.60, WPS 12.8.2.18913).
Original manual SHA remains
`8d8c5d540e4cd3325efdd081ee5941807850722daacb5de7caafc02c5643bf33`.

The fixed extraction window is PDF y=100..195pt, x<310pt, selected from the
original table. Browser borders are filled rectangles, WPS borders stroked
lines: compare their centerlines, not the fill edge against a stroke center.
Page origins remain unchanged. Points are physical PDF units; browser and WPS
pages are 595.91998x842.88pt and 595.3x841.9pt respectively, so raster comparisons
at 800px width include a small page-scale difference. No alignment is applied.

| Measure | Browser | DOCX request / WPS |
| --- | ---: | ---: |
| Row pitch, four rows | 19.5pt each | request 390twips=19.5pt AT_LEAST; WPS 20.25pt each |
| Five horizontal centers (pt) | 109.875,129.375,148.875,168.375,187.875 | 109.36,129.61,149.86,170.11,190.36 |
| Border thickness | filled 0.75pt | XML 6 eighth-points=0.75pt; PDF stroke 0.72pt |
| DOCX exact line + paragraph padding | browser normal 19px=14.25pt + 6px=4.5pt | 285twips + before45 + after30 =18pt |

All four WPS row pitches exceed browser by **0.75pt**. Cumulative extra height
is **3pt**, independent of the initial -0.515pt centerline offset. Existing page
images show the table's lower edge and following heading lower in WPS, consistent
with that accumulated difference. Text cross-check: browser Windows text top
135.498pt versus WPS136.624pt; WPS Office154.998 versus156.905pt; Python174.498
versus177.185pt. Their increasing error agrees with row growth and also includes
font-metric differences; these are text boxes, not guaranteed ink bounds.

## Supported hypothesis and limits

One narrow candidate is **native collapsed-border row minimum inflation**.
`docx_styling.apply_table` writes computed row height as AT_LEAST and replaces
vertical cell padding with paragraph before/after. Its existing compensation
subtracts one bottom-border width from padding. Nevertheless the native result
is exactly one nominal border thicker per row. The DOCX line/padding arithmetic
and observed pitch isolate the excess to the table boundary/native minimum,
rather than the already repaired hr or a global paragraph-margin offset.

This is an evidence-backed hypothesis, **not a demonstrated causal repair**.
AT_LEAST may expose renderer cell minima, border accounting or another native
constraint; existing data cannot distinguish them conclusively. Forcing EXACT
could clip text. Reducing padding changes cell content placement and might fail
multi-line or merged cases. PDF 0.72pt stroke versus XML0.75pt and font differences
introduce uncertainty; coordinate precision is not renderer accuracy. Horizontal
width also differs: DOCX grid66.65+95.45+94.95=257.05pt includes existing +1px per
column anti-wrap allowance. Historical comments record wrapping with smaller
allowances, so this stage neither removes it nor attributes all error to rows.
Contract is not needed and was not included. No predicted SSIM improvement or
promise to cross 0.90 follows from these measurements.

A future separately reviewed repair plan would first reproduce the native row
minimum behavior, retain text/paragraph size and column widths, and require same
manual WPS row pitch to approach19.5pt without clipping/wrapping, semantic/page
regression or worse whole/local SSIM. This stage does not authorize that work.

## Reproduction and verification

```powershell
python scripts/manual_geometry_attribution.py --out artifacts/manual-geometry-rerun/geometry.json
python -m unittest discover -s tests -p test_manual_geometry_attribution.py -v
```

Five focused tests cover twips, filled/stroked center conventions and rejection
of background rectangles. Two offline runs produced byte-identical JSON SHA-256
`d3df622455763c8a633d009093078062f85c0634234343ca85ea15cfefb5c5b0`.
Representative vectors/text were cross-checked against existing full-page images
and DOCX XML. Full Ruff check/format (573 files) and whitespace checks pass;
all six CI jobs and independent evidence review are required before merge.
