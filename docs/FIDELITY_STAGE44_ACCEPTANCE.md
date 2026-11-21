# Stage44: bounded natural merged-row minima

Base `1d48d868f440a930001d4517dcb7cc57d0e44a8e`. Outcome:
**PASS_FIVE_CASE_GATE**, with contract strict F2 still **FAIL**.

## Product boundary

The existing measured collapsed-width qualification remains unchanged. A new,
independent author-height audit must additionally prove complete flat CSSOM,
no height/logical-height/animation/containment declarations, no HTML height
attributes and no unsupported rules. It does not modify the earlier page or
width qualification. Missing evidence retains the old row minimum.

The row helper requires uniform measured natural rows, opaque uniform1px
collapsed borders, contiguous row/span geometry, single-line content and a
natural unspanned witness in every row. An actual rowspan is required. This
is a restriction to the experimentally validated domain, not a claim that
rowspan causes border accounting. No fixture, class, text or hash controls
product eligibility. Author height anywhere conservatively vetoes the helper.

Only the contract fee table qualifies among the original five. Exactly five
trHeight values change465→450twips; AT_LEAST remains. Inverse restores the
original document.xml bytes; every other ZIP payload/metadata is unchanged.
The other four complete DOCX packages are byte-identical to Stage42. Manual
and pdfsource unmerged tables remain outside this rule; Stage10 is not revived.

## Fresh reference and native acceptance

One new five-case browser set preserved source pixels and previous core/style/
box metadata. All ten baseline/candidate semantic assessments passed: applicable
aspects score1 with true verdicts, and N/A aspects remain explicit N/A. The new
audit is separate from the old metadata comparison. Report's missing print.css
remains a fail-closed condition, not repaired source material.

Exactly one new sequential five-case WPS set completed with empty per-case
process probes and no not-run entries. Edge157.0.4341.60 and WPS12.8.2.18913
are recorded in the raw manifests. No user document, setting or font changed.

| Case | Before aggregate | New aggregate | New pages | Other evidence |
|---|---:|---:|---|---|
| report |.9398|.9398|.9007 / .9789|all RGB pixels identical|
| contract |.8719|.8950|.8950|Stage43 geometry and ROI gates pass|
| newsletter |.9293|.9293|.9293|all RGB pixels identical|
| manual |.9060|.9060|.9060|all RGB pixels identical|
| pdfsource |.9247|.9247|.9237 / .9258|all RGB pixels identical|

Contract candidate DOCX SHA256 is
`2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa`,
identical to Stage43. Its new WPS page PNG is also byte-identical to Stage43.
Five row pitches become23.25pt; origin text remains single-line, fonts and
horizontal positions unchanged. All fifteen Stage43 geometry/flow gates pass.
Fixed body/header/table/later SSIM are .808045712/.934692855/.857345359/.764176805;
whole .895000062 remains below .90. No threshold, alignment or crop was tuned.

## Counterevidence and limits

The downstream uniform approximately−3.72pt displacement improves total price
source error(+3.409020→−.309980pt), but worsens heading3(+1.490022→−2.230978),
confidentiality(+.290023→−3.430977), heading4(−1.509975→−5.230975) and liability
(−1.959974→−5.680974). Mean SSIM gain does not imply every anchor improved.
This remains a bounded current-host mapping, not full contract fidelity or a
claim about arbitrary CSS, author heights, renderers or merged tables.

## Reproduction and evidence

`scripts/natural_row_preflight.py` performs environment/schema checks, the sole
fresh browser set, independent qualification, exact inverse and snapshot-based
semantics. `scripts/natural_row_wps_validation.py` enforces the sole sequential
export set and registered geometry/pixel/semantic gates. Neither runner retries.

`artifacts/natural-merged-rows-20261121/` retains snapshots, preflight/semantic
results, per-case acceptance/probe/export records and the original WPS manifest.
Only the changed contract package/PDF/PNG/comparison is duplicated in Git;
unchanged inputs/references/output packages are already in Stage42. Full local
exports are preserved without deletion. The retained-file manifest distinguishes
omitted duplicate bytes and records their original execution hashes.

Final verification:48 related tests including focused XML/negative qualification,
source-height audit, conversion controls and packaging; full Ruff/format,
JavaScript syntax, diff checks and raw manifest hashes. No additional browser
or WPS execution occurred during final verification.
