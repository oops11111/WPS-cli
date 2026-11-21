# Stage46 read-only visible-residual audit: STOP

Base f3cb1a8a989b40ee0676dbf97481fd6d270f9193; no candidate, browser, WPS or
product change. At the read-only STOP snapshot there was no commit or PR and
only the Plan was tracked-modified. Later evidence publication does not change
that historical state or the negative conclusion. Frozen stages remain intact.
Raw measurements: artifacts/visible-residual-audit-20261121/audit.json.
Reproduce with scripts/visible_residual_audit.py --out <new-audit.json>; the
extractor reads archived artifacts only, without conversion/browser/WPS.

Whole SSIM reproduced twice exactly .8950000618741911. Stage44/45 RGB and gray
negative-control pixels agree exactly; PNG hash a1a6f518...fb3861f. Gray/RGB
partition masses each sum exactly to full-page mass. PDFium/Pillow/NumPy versions
and immutable input hashes are recorded in JSON.

| Disjoint PDF region | Raster rows | Full-width SSIM | Gray difference mass fraction |
|---|---|---:|---:|
| before348pt |0..467|.935534|27.4264%|
| header348..395 |467..530|.939628|4.1811%|
| body395..470 |530..630|.822551|14.6094%|
| later470..640 |630..859|.781997|41.6723%|
| after640 |859..1132|.932416|12.1109%|

These are disjoint full-width regions, not additive SSIM contributions or causal
repair ceilings. The unchanged original x30..770px ROIs separately reproduce
header .934692855 / body .808045712 / table .857345359 / later .764176805.

Actual first-glyph dark-ink rows (threshold160, fixed char-size x window and
PDF-line bbox+2pt y window; approximate at800px, not a fitted registration):
price645..658 source/native identical; h3 source686..707/native685..705;
confidentiality738..750/734..747; h4 779..800/774..794;
liability829..842/822..835; signing909..922/901..914.
Thus the growing lower-flow displacement is visible, not merely a PDF matrix
artifact. Pixel-row quantization/font shapes introduce uncertainty of at least
one raster pixel; do not infer exact offsets from these ink windows.

Source CSS body11pt/line1.5, p margins14.6667px, h2 font22px/line33px and
margins18.26px; saved source DOM p/h2 boxes and order are in raw JSON. Current
XML price p exact330 before220/after220; subsequent h2 exact495 before54/after274;
body p exact330 before0/after220 (last body after480 due signing gap). Source
p->h2 native-spacing double-collapse is a known mapping problem already tested
by Stage12; the later residual is not a NEW mechanism. Pure per-anchor offsets
would be empirical tuning. Current baseline errors price-.309980/h3-2.230978/
confidentiality-3.430977/h4-5.230975/liability-5.680974pt remain explicit.

Table vector check: browser has46 filled #555 rule rectangles (linewidth0),
5 header fill rectangles #dde6f0; native has10 stroked rules width.72pt color
(.333,.333,.333) and5 fill rectangles (.867,.902,.941). This is a renderer
representation distinction; the source border and fill colors are already
mapped, not a missing color. Different primitives/cap/overlap/rasterization
prevent exact ink-mass separation into rule versus glyph causes from this
simple fixed-window audit. It does not justify border or font tuning. Remaining
row/body raster mismatch is mixed with known metrics/raster behavior and Stage45
already falsifies baseline movement as a visible gain for its candidate.

STOP: no independent new single-variable CSS->DOCX mapping with a reliable visible
prediction was isolated. Largest local pixel loss is lower flow, but its grounded
source trace overlaps the failed Stage12 mechanism. Table style/raster differences
do not supply a new safe candidate; signing separate-border spacing overlaps
Stage29's vertical-coupling negative result. No next WPS experiment is proposed.
This is a negative audit, not a claim that strict .90 is unattainable. Further
work needs new causal evidence or a separately reviewed broader design; neither
is authorized here. Preserve local evidence, do not revive frozen stages.

Evidence packaging verification:4 focused audit tests plus6 packaging metadata
tests pass (10 total). They reproduce the accepted raw measurements, fixed
regions, visible-ink distinction, negative control and partition conservation.
Full Ruff/format/diff pass. The raw JSON SHA256 remains
041761d4832a8cb8c97fe8ebb5e8eeb2391a9c1e0b7e2ce55541cbc5cba36401;
Git's staged blob matches those exact bytes. No duplicate PDF/PNG or temporary
file is included; existing immutable artifacts supply all inputs.
