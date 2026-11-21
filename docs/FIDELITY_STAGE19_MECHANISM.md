# Stage 19: table column-width allowance mechanism

Base a694763fdcce823876b4cc9b2cc7de7615ab3f13. This evidence-only experiment
changes no converter, original HTML, baseline or threshold. Frozen6/10/12 stay
untouched. Six deterministic synthetic packages reuse accepted Stage18 manual
and contract DOCX styles/text. Manual retains its first three-column table;
contract retains only the fee table's three ordinary body rows, removing both
merged header rows identically from every control. Source package hashes are in
`artifacts/table-width-mechanism-20261121/manifest.json`.

## Fixed controls and observations

Each family differs ONLY in gridCol/tcW column widths. Starting with the accepted
1px allowance, subtract15twips per column and add0/7.5/15twips; Python round-to-even
produces integer twips deterministically for the half-pixel controls. No paragraph,
font, padding, border, row-height rule or table position changes.

| Variant | Per-column allowance | WPS outer centerline span | Row pitches | Cell line counts |
|---|---:|---:|---|---|
| M0 | 0px | 254.80pt | four ×20.25pt | all1 |
| M05 | .5px | 256.00pt | four ×20.25pt | all1 |
| M1 | 1px | 257.05pt | four ×20.25pt | all1 |
| C0 | 0px | 273.65pt | three ×24pt | all1 |
| C05 | .5px | 275.10pt | three ×24pt | all1 |
| C1 | 1px | 276.65pt | three ×24pt | all1 |

Every expected cell string is retained100% (whitespace-insensitive comparison),
every case is one page. Raw character bboxes, each cell bounds/expected/actual text,
line-top values, horizontal/vertical rules and row pitches are preserved. These
controls contain no superscript/mixed-size text, so distinct text tops reliably
represent lines here. Boundary cardinality is checked before cell attribution.

WPS12.8.2.18913 (file/product12,8,2,18913), six pre-case process probes empty.
Exactly one sequential six-export set; no taskkill, global setting or retry.
Every own instance was released by the existing converter. Raw export metadata,
PDFs/PNGs, source/output SHA256 and version paths accompany the manifest.

## Interpretation and counterevidence

Column allowance causally widens these native tables without changing their text
wraps or row pitches. The manual span difference M1−M0=2.25pt equals three columns
×.75pt; contract C1−C0=3pt equals four columns×.75pt. Browser original centerline
spans were255pt and273.75pt; M0/C0 are closer, with native rounding/border residuals.
No new browser render was needed for this DOCX mechanism experiment.

The code's historical warning that .5px caused Windows10/11 to wrap was NOT
reproduced by these isolated controls. That is counterevidence to treating the
old observation as universal, not evidence that all author content is safe.
Contract merged headers and original surrounding flow are deliberately absent;
font fallback, new text, narrow widths and page constraints remain untested.
There is no SSIM/F2 or safe-product-repair claim, and no recommendation to delete
allowance without a separately reviewed original-five regression stage. The
manual's independent .75pt-per-row inflation remains unchanged.

## Verification

Two focused test groups verify deterministic full ZIP bytes, all non-document
package parts unchanged, exact width arithmetic/topology and identical normalized
non-width XML across all three controls of each family. Input/output hashes are
independently checked after export. Full Ruff, format and diff checks and six CI
jobs are required before primary review/merge; implementation agent never merges.

Reproduce offline: `python scripts/table_width_mechanism.py --out NEW_DIRECTORY`.
`--export-wps` starts the safe synthetic experiment; the recorded set is not rerun
or tuned as part of this delivery.
