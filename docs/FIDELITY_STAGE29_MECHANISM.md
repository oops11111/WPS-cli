# Stage29: horizontal cell-spacing negative mechanism

Base/actual main810f9e3ccb7ffd8dc0b37f3d3651ba6c0d07f05a. Evidence only;
no product, original-five fixture, baseline or threshold changes. Same continuing
agent, isolated fidelity-cell-spacing worktree; frozen failed stages untouched.

## Fixed inputs and passed preflight

Three HTML references use horizontal border-spacing0/2/4CSSpx and vertical0,
two200px border-box cells,12px horizontal padding, Consolas12pt/18px line height,
one row and unique BEFORE/LEFT/RIGHT/FOLLOWING labels. Table widths400/406/412px
preserve200px cells. Source DOM/PDF independently confirms LEFT relative x9/10.5/12pt,
RIGHT159/162/165pt, height18px and invariant y.

Six DOCX files were generated before WPS: each current-main control and one copy
with ONLY table-level tblCellSpacing0/30/60dxa added. Existing3015/3015twip grid
(including unchanged main column allowance), margins, row properties, padding,
fonts and text remain. Removing the single child restores original document.xml
bytes; every other ZIP payload is identical. All source/reference/six-input hashes
and these package gates were independently rechecked after STOP.

## One set, stopped after four exports

Current Edge157.0.4341.60, WPS12.8.2.18913; all four pre-case probes empty. Own
instance release only. Fixed order H0-C,H0-N,H2-C,H2-N completed; H2-N immediately
triggered predeclared STOP. H4-C/H4-N remain generated but NOT EXPORTED. No retry,
half-spacing, offset, row-height or column-allowance adjustment was attempted.

| Case | LEFT relative x | RIGHT relative x | LEFT top/baseline | FOLLOWING top | Occupied row flow height |
|---|---:|---:|---:|---:|---:|
| H0-C | 9.00 | 159.72 | 44.354/52.730 | 57.794 | 13.50 |
| H0-N | 9.00 | 159.72 | 44.354/52.730 | 57.794 | 13.50 |
| H2-C | 9.00 | 159.72 | 44.354/52.730 | 57.794 | 13.50 |
| H2-N | 9.00 | 158.28 | 47.354/55.730 | 63.794 | 19.50 |

Unitspt. H0 pair pixels identical. All labels retained once, one line per single-word
cell, every export one page. H2 pair increments LEFT0(expected+1.5), RIGHT−1.44
(expected+3) fail.10pt tolerance. Cell y+3pt and following/occupied-flow+6pt fail
.05pt no-coupling gates. The occupied height is FOLLOWING baseline−BEFORE baseline
−fixed13.5pt paragraph pitch; borderless cells have no visible outline, so this is
not an independently measured cell-border height. Direct y changes alone prove
failure without relying on that derived value.

Primary independently reviewed H2-C/H2-N original PNGs and raw measurements,
confirming visible downward movement and reversed RIGHT displacement. The STOP
is accepted as a bounded negative mechanism result, not product acceptance.

## Conclusion and limits

Adding this native table-level attribute alone does not reproduce the fixed CSS
horizontal-only spacing: it couples vertical flow and changes horizontal placement
in the wrong direction for RIGHT. This does not establish that all native table
representations are incapable of separate spacing. No original-contract F2 score
was measured or improved by this stage, and no product mapping is proposed.

## Evidence and verification

[Manifest](../artifacts/horizontal-cell-spacing-20261121/manifest.json) records
source geometry, pair hashes, exact base, versions, four exports and remaining
not-run cases. [STOP measurements](../artifacts/horizontal-cell-spacing-20261121/stop-measurements.json)
contain exact y/x, source/input/export hash rechecks. H0/H2/H4 directories contain
sources/browser references/all six DOCX; exports/H0-C,H0-N,H2-C,H2-N contain raw
PDF/PNG/probe/export metadata. The original STOP.md is preserved as a dated-stage
state note; this final report follows independent review, not a reclassification.

Three focused deterministic/package/STOP tests and full Ruff/format/diff pass.
Evidence-only commit/PR requires primary staged-diff review; all six CI jobs must
pass before primary merge. The implementation agent never merges.
