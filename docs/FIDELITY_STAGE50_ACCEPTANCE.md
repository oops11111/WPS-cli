# Stage50: bounded native spacing after measured row compensation

Base `c1d605ec0482b7d846ca9549c29114e43c29cad2`. Outcome
**PASS_FIVE_CASE_GATE** on the recorded Windows/Edge/WPS host. All five fixed
HTML→DOCX cases and every measured page exceed strict layout .90 in this set.
This is a bounded regression result, not universal format/CSS fidelity.

## Qualification and product boundary

The collector adds exactly four raw computed properties: break-after,
page-break-after, break-inside and page-break-inside, without inferred defaults.
Missing/unsupported/explicit/contradictory break values retain legacy output.
Stage49's missing-proof STOP remains valid and unchanged.

The local body-flow state starts only after apply_table actually applies the
complete Stage44 measured natural merged-row compensation. Lists, tables,
containers, images, roles, raw inline flow or unsupported/unknown block styles
clear that state. Recursive/cell/header/footer flows cannot inherit it.

A boundary additionally proves an immediate ordinary p→h2 source relationship:
static visible single-line finite boxes, unchanged inline line metrics, no
unsupported effects/breaks on the relevant nodes/ancestors, positive resolved
margins, measured gap matching CSS max margin within1/64px, and an actual prior
native after request plus residual-before that understates the source boundary.
Only then retain the full computed heading-before. No string/class/hash or fixed
table-size whitelist exists in product code. A merged table does not cause the
CSS defect: it limits this integration to the upstream-flow interaction supported
by Stage44/48 evidence. Other contexts deliberately retain legacy behavior.

## One fresh browser set and exact package gates

Exactly one new five-case browser set ran with Edge157.0.4341.60. After removing
only the four new fields, prior snapshot core/style/box/page/marker/runtime/CSSOM
metadata match; known copied-input file URI prefixes are normalized without
changing resource names, loaded/error status or qualification. Source paper
sizes and800px RGB pages are identical. All real DOM elements report auto for
the four new fields (report94/contract64/newsletter29/manual44/pdfsource78).

Only contract boundaries49→51 and52→55 qualify. The actual package changes
exactly TWO h2 before54→274twip attributes, with inverse/other members/metadata
identical. Candidate SHA256:
`63a6dde9780ebc15dcc2b1c73c6cd25627ad550ad8f37384d8a0788192772738`,
identical to the Stage48 experimental package. Other four complete DOCX files
remain byte-identical. All ten legacy-control/candidate semantic assessments
consume the same fresh source snapshot: applicable score1/rawtrue, explicit N/A
effective true without raw mutation. No fallback source capture is used.

## One new safe sequential five-case native set

Five attempts/exports, no not-run cases, no retries. Each empty-process probe
confirmed WPS12.8.2.18913; owned instances only, no user document/settings/font
change. Environment/schema/snapshot semantics and sealed input/reference hashes
were verified before any native work, with immediate pre-call input hashes.

| Fixed original case | Before aggregate | New aggregate | New page scores |
|---|---:|---:|---|
| report |.9398|.9398|.9007 / .9789|
| contract |.8950|.9236|.9236|
| newsletter |.9293|.9293|.9293|
| manual |.9060|.9060|.9060|
| pdfsource |.9247|.9247|.9237 / .9258|

The other four native PDFs have identical RGB page pixels, page sizes, text,
line assignments, fonts and positions. Contract independently passes the frozen
Stage48 eleven gates, with one page and unchanged source content/fonts/table/
pre-heading pixels. h3/confidentiality shift+2.761pt, h4/liability/signing/date
shift+5.400pt, price0; these match the registered response tolerances.

Contract whole .8950000618741911→.923567325326432; fixed Stage12 region
.8267341075516954→.9410309661333276 and later region
.7641768045298025→.8923698040367637. Header/body/table scores and pixels remain
unchanged. No alignment, crop search, threshold or fixture tuning occurred.

## Counterevidence and limitations

h3 actual first-character ink midpoint source error worsens−1.5→+2.5 raster px.
Confidentiality/h4/liability improve−3.5/−5.5/−7→−.5/+1.5/+1; price stays0.
Higher SSIM and improved PDF baseline errors do not mean every visible anchor
is closer. The raw measurements retain the h3 adverse effect explicitly.

Stage12's prior whole/region and newsletter/pdfsource regressions remain failed;
this restricted domain does not reclassify them or authorize a global spacing
toggle. Report's missing print.css stays missing and fail-closed, with unchanged
output. Noto Sans CJK SC is reported missing; the recorded fallback/font host is
part of the evidence, not a cross-font/renderer guarantee. Wider qualification,
other renderers, complex layouts or additional formats require separate review.

## Evidence and final verification

`scripts/qualified_flow_preflight.py` and `qualified_flow_wps_validation.py`
provide explicit one-shot browser/native gates with persisted attempt records.
`artifacts/complete-qualified-flow-20261122/` retains the actual snapshots,
qualification/package/semantic records, probes, export results, seals/manifests,
and the changed contract package/PDF/PNG/comparison. Duplicate unchanged packages,
references and large page images remain local; existing committed controls and
the retained-file manifest provide their byte identities. Original execution
manifests remain unchanged.

54 focused/related/packaging tests, full Ruff/format, JS syntax and diff checks
pass. Final saved-snapshot package replay proves all five actual WPS input DOCX
bytes unchanged. Original execution/reference hashes and staged raw bytes are
verified. No further browser/WPS execution occurred during packaging. Product
PR publication and merge still require independent review and six green CI jobs.
