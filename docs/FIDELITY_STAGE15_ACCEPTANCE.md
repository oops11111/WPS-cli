# Stage 15: plain-pre terminal whitespace

Base `0947a424349aaac8c5edae0503636c76a69ff486`. The bounded repair and original
five-case gates pass. Only direct-text pre with computed white-space:pre changes;
nested code, comments, overrides and ordinary paragraph whitespace retain their
existing behavior. Empty/whitespace-only pre still follows existing omission
behavior; this is not a general whitespace/layout rewrite.

## Reproduction and repair

Original report pre has an initial CRLF and ends `GROUP BY region;` plus CRLF plus
four spaces. HTML normalizes CRLF/lone CR to LF and ignores exactly one initial
LF immediately following the pre start tag ([HTML Standard](https://html.spec.whatwg.org/multipage/grouping-content.html)).
The previous converter lstripped all leading newlines and rstripped terminal
whitespace. Its DOCX had four visible SQL lines/three br, losing the terminal
indented line. The repair retains that LF and indentation, producing four br.
No empty paragraph, font, line pitch or summary-margin compensation is added.

The raw source-normalized expected pre text equals generated paragraph text.
The existing CRLF/CR normalization is retained; additional authored leading LF,
terminal spaces/tabs and internal blank lines survive in this bounded form.
Parser comment presence disqualifies the new branch because a comment before LF
breaks immediate source-start adjacency. Comment-first and terminal-comment
forms retain legacy behavior, as do nested code and whitespace overrides.

Archived browser measurement reports preheight150px/text-lines10, conflicting
with actual PDF/source evidence; it is not used for a total-height adjustment.
Potential Windows temporary-file newline translation was not repaired or relied
on. Evidence uses actual PDF coordinates, source bytes and native DOCX br/text.

## One original five-case WPS set

WPS12.8.2.18913 / Edge157.0.4341.60. Exactly one original five-case set ran with
empty pre-case process probes and converter-owned instances only. No installation,
font/global preference, original input, baseline or threshold changed; no taskkill,
user-document closure or tuning rerun occurred. Stage6/10/12 remain frozen.

| Case | Stage14 before | After | Per-page result |
| --- | ---: | ---: | --- |
| report |0.9255|0.9302|[0.8826,0.9684] -> [0.8826,0.9778] |
| contract |0.8492|0.8492|unchanged, strict failure |
| newsletter |0.9168|0.9168|unchanged |
| manual |0.8959|0.8959|unchanged, strict failure |
| pdfsource |0.9123|0.9123|[0.9000,0.9246] unchanged |

All applicable semantic scores remain1.0 and page counts unchanged. Report page1
WPS pixels are identical; SQL visible-line coordinates and subsequent x positions
are unchanged within0.05pt. Report remains2/2pages, with hidden details body
retained once in XML and absent from PDF.

| Page2 text top (pt) | Browser | Before | After | Absolute error after |
| --- | ---: | ---: | ---: | ---: |
| Summary |166.6406|155.63|166.91|0.2694 |
| Contacts/phone |194.3906|183.35|194.63|0.2394 |
| Unsafe-link label |222.1406|211.19|222.35|0.2094 |

Independent image review confirms close vertical alignment without new visible
blank text. Disclosure triangle and summary x-offset remain unresolved; no
interactivity/accessibility or cross-settings guarantee is made. Report page1
still fails0.90, contract/manual still fail strict F2 and their historical
exceptions remain separate. Small font/raster/quantization differences persist.

## Evidence and checks

[Raw evidence](../artifacts/plain-pre-whitespace-20261121/) contains original
inputs/assets, generated DOCX/PDF, styles, images, process/export/version and
SHA records. `acceptance.json` passes all report and five-case gates; its source
text, pre/br and SQL/summary/following coordinates are independently inspectable.
Archive-only -text attributes preserve source snapshot bytes on Windows checkout.

The comment veto was added after the one WPS set. Offline reconversion with exact
archived styles reproduces byte-identical document.xml for all five cases;
`pre-comment-veto-verification.json` records this equivalence and updated source
hash. Original run hashes are retained honestly rather than relabeled as a new
renderer run. No browser/WPS rerun was needed.

Negative original-report XML reproduction failed before repair. Focused controls
cover LF/CRLF/CR, one/multiple leading LF, terminal LF/tab-space, no-terminal-LF,
internal indentation/blank lines, empty/ordinary text, nested code, comment-first/
terminal and original manual controls. Initial116 related tests pass122.762s
(four existing skips); comment-veto follow-up117 tests pass125.687s (four existing
skips), full Ruff check/format585 files and whitespace checks pass. All six CI jobs and primary diff/XML/image
review are required before merge.

```powershell
python scripts/html_docx_wps_matrix.py --out artifacts/plain-pre-rerun
# Offline only, after a completed matrix:
python scripts/plain_pre_acceptance.py --out artifacts/plain-pre-rerun
```
