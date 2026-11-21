# Stage 14: bounded closed-details mapping

Base `1471f521ac4c3b4c037f7dabffbf0f22ba747066`. The local mapping and five-case
regression gates pass. This does not establish full high fidelity for all HTML:
contract/manual still fail strict F2, and report page1 remains below0.90.

## Behavior and scope

Closed details with exactly one first explicit plain-text summary and one
plain-text body p retain body text as a vanished run in the summary paragraph.
The run uses the original body's computed font styling and creates no extra
paragraph or margin flow. This preserves text once, not the original hidden
paragraph structure. Open-attribute presence, including open="false", leaves
expanded conversion unchanged. Unsupported shapes retain legacy expanded content
with one explicit warning per element. Nested/cell details, missing/multiple/
complex summary/body, links and ambiguous positioning are outside this mapping.

The scorer separates actual hidden state from optional source expectations.
Only supported HTML-details to DOCX checks gain visibility expectations; unrelated
directions retain their policy. DOCX explicit run flags, document defaults and
paragraph/character style toggles are resolved; conditional table-style ancestry
stays unknown rather than guessed. Every character of an expected hidden/visible
run must match. Missing body and duplicate text cannot substitute a visible
summary for a required hidden body. Diagnostics identify text and expected/actual.

Using exact archived browser styles, the old expanded report now scores formatting
**0.9973**, with the sole problem `收入按权责发生制确认。: hidden True -> False`.
The repaired report scores text/structure/formatting/data1.0. Existing structure
scoring does not validate complete hidden paragraph semantics; independent XML
and visible-output gates are required.

## One original five-case WPS set

WPS12.8.2.18913 / Edge157.0.4341.60. All original input/assets SHA and generated
DOCX/PDF hashes are verified. Exactly one sequential five-case set used empty
pre-case process probes and only converter-owned documents/instances. No global
hidden/printing preference, font/install, source, baseline or threshold changed;
no taskkill or tuning rerun occurred. Stage6/10/12 remain frozen.

| Case | Accepted before | After | Per-page result |
| --- | ---: | ---: | --- |
| report |0.9224|0.9255|[0.8826,0.9622] -> [0.8826,0.9684] |
| contract |0.8492|0.8492|unchanged, strict failure |
| newsletter |0.9168|0.9168|unchanged |
| manual |0.8959|0.8959|unchanged, strict failure |
| pdfsource |0.9123|0.9123|[0.9000,0.9246] unchanged |

All applicable semantic scores remain1.0 and page counts unchanged. Report stays
2/2pages; page1 WPS pixels are identical. Report body phrase appears exactly once
in DOCX with vanish and is absent from every WPS PDF page. Summary top155.63pt
and x34.32pt are unchanged. Contacts/phone move from211.19 to183.35pt against
browser194.3906pt, reducing vertical error16.80 to11.04pt; unsafe-link label moves
238.91 to211.19pt against222.1406pt, error16.77 to10.95pt. Horizontal errors do not
increase. Independent review confirms the closed-body removal and closer layout.

Residuals: disclosure triangle is missing; summary/following content remain about
11pt high. The missing original print.css and missing Noto fallback remain recorded
environment/input limitations, not attributed as the sole cause. Decision10's
contract0.84/manual0.88 exceptions remain separate from strict0.90 acceptance.
No HTML interaction, accessibility, recovery UI or cross-host/settings guarantee
is made: vanished text can be displayed/printed by application preferences.

## Evidence and verification

[Raw evidence](../artifacts/closed-details-mapping-20261121/) includes original
inputs/assets, DOCX/PDF, computed styles, probes/exports, page images and hashes.
`acceptance.json` records all five-case gates plus measured report visibility,
positions and isolated old-output scoring counterexample; `passed` is true.
Archive-only -text attributes preserve source snapshot bytes on Windows checkout.

- Negative conversion reproduced three visible paragraphs before repair.
- Seven focused groups cover retained/computed styles, open values, warnings,
  deleted/wrongly visible/duplicate body and inherited/direct hidden flags.
- 110 related tests pass124.699s (four existing skips); final focused controls pass.
- All26 historical baseline conversions/checks succeed with renderer none and
  normal browser support; existing formatting baseline values are unchanged.
  A no-browser attempt could not run the existing appearance-mode training case;
  it was completed with its required browser support, without WPS.
- Full Ruff lint/format and whitespace checks pass. All six CI jobs and primary
  diff/XML/image review are required before merge.

```powershell
python scripts/html_docx_wps_matrix.py --out artifacts/closed-details-rerun
# Offline assessment only, after a completed matrix:
python scripts/closed_details_acceptance.py --out artifacts/closed-details-rerun
```
