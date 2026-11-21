# Stage37: copied contract table retains single lines at two widths

Base `ab3b548667cabbe8b09b59cc181ffd88b523b2db`. This is an evidence-only
mechanism experiment, not an original-contract or product acceptance result.
Stage34's pre-WPS STOP remains unchanged: PDF ink bounds did not prove native
no-wrap. This experiment measures native wrapping directly in two fixed controls.

## Controls and package checks

Both packages copy the full immutable Stage28 contract fee table: five rows,
four logical columns, nineteen physical cells, seventeen origins and two merge
continuations. All original table text, fonts, paragraph/row properties, padding,
borders, fill and merge topology remain unchanged. The original section, styles,
theme and non-document ZIP payloads remain intact. Identical BEFORE/FOLLOWING
paragraphs replace the original surrounding document flow.

C1 table subtree is identical to the original. C0 differs from C1 in exactly
21 attributes: four grid widths and seventeen non-continuation cell widths each
minus15twips. Grid710/724/1370/2729 becomes695/709/1355/2714; merged-origin1370
becomes1355 per existing alias assignment, and both continuation2639 remain2639.
Inverse restores full C1 document.xml bytes. Builds are deterministic; all other
ZIP payloads are identical. Source SHA256 is
`ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f`.

## Native measurements

Exactly one sequential export set ran C1 then C0 using WPS12.8.2.18913, with an
empty process probe before each. C1 first passed comparison with cached original
fee-table text/font/line/pitch metrics. The old contract was not re-exported.

| Measurement | C1 | C0 |
|---|---|---|
| Vertical rule centers, pt |33.75/69.25/105.45/173.95/310.40|33.75/68.50/103.95/171.70/307.40|
| Per-edge differential, pt |reference|0/-.75/-1.50/-2.25/-3.00|
| Five row pitches, pt |24 each|24 each|
| All17origin line counts |1 each|1 each|
| Amount header baseline relative table top, pt |41.38|41.38|
| Amount header PDF font |MicrosoftYaHei-Bold11.05|same|
| BEFORE/FOLLOWING coordinates |reference|identical|
| Pages |1|1|

Rule segments independently corroborate missing merged-header boundaries;
XML topology defines union polygons. Glyph centers select cells geometrically,
then ordered character streams are compared. Repeated strings do not select a
cell. All glyphs remain inside rule polygons, with no missing text or observed
clipping; normalized font/size and relative baselines remain unchanged. PDF
character advance, matrix and ink bbox are preserved separately in measurements.

WPS stroke endpoints extend by up to half the .72pt line width around rule
centers. Offline attribution explicitly distinguishes painted end caps from
center coordinates. An initial cached-original topology check exposed this
convention; it was corrected before either export, without changing controls or
registered geometric tolerances. No WPS retry or fitted offset occurred.

Outcome: **PASS_MECHANISM_ONLY**. The copied merged table at the two declared
widths did not wrap on this WPS version. No score/F2 claim applies to synthetic
pages. This does not certify original surrounding flow, pagination, other source
content, other renderers, or safe removal of the product allowance. Any next
original-contract/product stage needs a separate reviewed Plan and gates.

## Evidence and validation

`artifacts/copied-contract-wrap-20261121/` contains manifest/acceptance and C1/C0
input.docx, wps.pdf, page PNG, measurement.json, probe.json and export.json.
The manifest records hashes, executable path/version, actual export order and
not-run status. No browser or original contract export was needed.

Four focused tests plus six packaging tests passed; Ruff check/format and diff
checks passed. Focused tests cover table identity,21-attribute inverse, package
determinism, changed font/topology rejection and control mismatch. No product,
fixture, baseline, threshold or frozen-stage files were modified.
