# Stage29 STOP snapshot — not yet committed or in a PR at capture time

Base/actual git HEAD810f9e3ccb7ffd8dc0b37f3d3651ba6c0d07f05a;
worktree fidelity-cell-spacing, branch experiment/horizontal-cell-spacing.
Product code/original-five/baselines/thresholds unchanged; frozen stages untouched.

## Passed preflight

All three fixed source references match declared geometry: cell widths200CSSpx,
table widths400/406/412px, table height18px, V-spacing0 and identical text y.
LEFT relative body9/10.5/12pt; RIGHT159/162/165pt. All six DOCX inputs generated
from the same main converter; native variant only adds tblPr/tblCellSpacing
0/30/60dxa. Removing that child restores original document.xml bytes; every
other ZIP payload unchanged. Source/browser/all six input hashes verified.
Three focused deterministic/XML/STOP-gate tests and full Ruff passed before WPS.

## Single set stopped at H2-N

Safe order H0-C,H0-N,H2-C,H2-N; four exports completed with WPS12.8.2.18913 and
empty pre-case process probes. Immediately STOPPED on H2-N; H4-C/H4-N NOT RUN.
No retry, alternative value, indent/row/padding/global-column change or product fix.

| Case | LEFT relative x | RIGHT relative x | LEFT top | LEFT baseline | FOLLOWING top | Occupied row flow height |
|---|---:|---:|---:|---:|---:|---:|
| H0-C | 9.00 | 159.72 | 44.354 | 52.730 | 57.794 | 13.50 |
| H0-N | 9.00 | 159.72 | 44.354 | 52.730 | 57.794 | 13.50 |
| H2-C | 9.00 | 159.72 | 44.354 | 52.730 | 57.794 | 13.50 |
| H2-N | 9.00 | 158.28 | 47.354 | 55.730 | 63.794 | 19.50 |

All unitspt. All four tokens present once, one line per single-word cell and one
page for every export. H0 explicit-zero is pixel-identical to its C.

H2 N−C LEFT increment0(expected+1.5), RIGHT−1.44(expected+3): both exceed.10pt
error. Cell top/baseline moves+3pt; FOLLOWING moves+6pt; occupied flow height grows
+6pt, all exceed.05pt no-coupling thresholds. Page/retention remain okay.

Borderless table has no directly observable cell outline. Occupied single-row
flow height is FOLLOWING baseline−BEFORE baseline−fixed13.5pt paragraph pitch;
it includes any native spacing allocation and is not claimed as independently
visible cell-border height. Direct cell/FOLLOWING y shifts alone establish the
predeclared vertical failure, without relying on that derived height.

The straightforward table-level spacing attribute does NOT implement this fixed
CSS horizontal-only spacing mapping on this WPS/version/layout. This is bounded
negative evidence, not proof that every representation is impossible. No attempt
was made to halve values, compensate vertical flow or remove column allowance.

## Evidence paths (relative to this directory)

- manifest.json: source/XML gates, versions, order,4exports,STOP/not-run list.
- stop-measurements.json: exact values and independent hash/XML recheck.
- H0/H2/H4/input.html, browser.pdf, browser-page-001.png, control.docx, native.docx.
- exports/H0-C/wps-page-001.png and wps.pdf.
- exports/H0-N/wps-page-001.png and wps.pdf.
- exports/H2-C/wps-page-001.png and wps.pdf.
- exports/H2-N/wps-page-001.png and wps.pdf.
- Each export directory includes probe.json and export.json; PDF hashes verified.

At the time this STOP snapshot was captured, the work was uncommitted with no
commit/push/PR, pending primary independent image review and authorization. This
paragraph records that historical state; the final Stage29 report and PR track
subsequent evidence-only delivery.
