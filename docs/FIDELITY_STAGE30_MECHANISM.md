# Stage30: paragraph-mark font has zero observed influence

Evidence-only falsification on main `5a1137b3a830011cb765197f5fbb450fb8a616d0`.
No product conversion, HTML, font size, row height, padding, margin or baseline
was changed. This hypothesis was not an established major cause.

## Fixed candidate and result

The accepted Stage28 contract DOCX is referenced at
`artifacts/alignment-aware-print-margins-20261121/A-contract-docx`.
Its SHA256 is
`ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f`.
Only twelve paragraph-mark `w:pPr/w:rPr/w:rFonts` nodes were added to the fee
body (second table, rows 2..4, cells 0..3, zero-based). Each copies the visible
run's four Microsoft YaHei font attributes; no size or visible-run change.
Removing precisely those nodes restores complete original document.xml bytes;
all other ZIP payloads are identical. The build is deterministic.

Exactly one candidate export used WPS 12.8.2.18913 after an empty process probe.
The cached accepted baseline was not re-exported. Candidate output is
**pixel-identical**, with every character and rule coordinate identical.

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Contract aggregate SSIM | .8644 | .8644 |
| Fixed fee-body ROI SSIM | .5516460049 | .5516460049 |
| First-column baseline shifts, pt | 0/0/0 reference | 0/0/0 |
| Baseline-minus-row-center error, pt | +.7800006 each | +.7800006 each |
| Pages | 1 | 1 |
| Semantic gates | all pass | all pass |

The fixed ROI is x30..770 pixels and y395..465pt, scaled by800/595.92, with no
image alignment or crop optimization. Row centers use adjacent painted/stroked
horizontal-rule centers; baseline uses PDF character matrix translation, not
glyph bounding-box top. All independent conservation gates pass.

Conclusion: these twelve explicit mark fonts have **zero observed influence on
this contract under this WPS version**. They do not explain the fee-body
misalignment. Strict F2 .90 remains failed. There is no product recommendation,
alternate candidate, font-size/offset tuning, or additional WPS run.

## Raw evidence and execution limits

`artifacts/paragraph-mark-font-20261121/` contains candidate.docx, wps.pdf,
wps-page-001.png, comparison PNG, process probe, export response, manifest and
full acceptance geometry. Baseline browser/WPS PDFs remain immutable references
in the Stage28 directory. Manifest records input/output hashes and WPS version.

The export succeeded before the initial offline assessor failed because it
mistakenly imported uninstalled skimage. The assessor was corrected to the
repository's existing grayscale SSIM implementation. A default-sandbox offline
attempt then hit `_ctypes` DLL import failure; elevated offline measurement
worked. Repeated characters in other columns required matching both word x and
top to identify the fixed first-column anchors. These were assessor-only
corrections over the same exported PDF, with no WPS retry or candidate change.

This single-document negative result does not establish behavior in other
documents or renderers. Any future product hypothesis requires a separate plan
and original-five regression; known stopped stages remain frozen.
