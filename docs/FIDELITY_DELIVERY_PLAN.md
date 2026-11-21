# Conversion fidelity delivery

Acceptance source: the user's request to preserve conversion fidelity and ROADMAP A-04.
Base: `b7cf9d8` on `main`. HTML directions remain frozen; this work fixes the
HTML-to-DOCX main path. PPTX remains best effort. No full-format matrix reopening.

## Stage 1: direct container text

- Dependency: current `main`; isolated branch preserving the original worktree.
- Scope: `html_editable.py`, related `docx_styling.py` behavior, focused tests,
  this plan and changelog. Direct text and inline content inside a block currently
  use a copied node whose computed styles are lost, and omit paragraph styling.
- Deliverables: preserve alignment, indentation, line height, spacing, shading,
  borders and character styles; preserve text, links and inline formatting.
  Mixed blocks must not repeat outer margins or page breaks.
- Boundary: this restores the existing style mapping for anonymous text, not a
  complete CSS box-layout engine. A container whose first/last content is a child
  block still uses the existing child-block spacing; transferring outer margins
  to that child and exact multi-block backgrounds/borders remain best effort.
- Verification: `python -m unittest discover -s tests -p test_html_container_fidelity.py`,
  HTML regression tests, `python -m unittest discover -s tests`, `ruff check .`,
  `ruff format --check .`.
- Gates: primary-agent diff review and all PR CI jobs green (lint, Python 3.10/3.12
  unit tests, fake-COM PowerShell tests, Windows installation, build).
- Merge target: `main`. Stop for missing dependencies/credentials or a fix that
  requires adding conversion directions; report evidence rather than widening scope.

## Stage 2: visual evidence for the same fix

- Dependency: stage 1 accepted and merged; no new product scope.
- Scope/deliverables: the same representative fixture, browser/WPS rendering
  evidence and limitations. Record raw JSON, input/output hashes, renderer/WPS
  versions, per-page scores, text and structure results.
- Verification: browser computed styles and DOCX properties; HTML reference
  versus WPS-rendered DOCX PDF, using existing F2 acceptance (SSIM >= 0.90,
  text and structure 100%). Local structural tests and CI do not replace WPS
  evidence. Any evidence PR also requires all CI green before merging to `main`.
- Stop: missing browser, WPS, credentials or external service. Record the exact
  failed probe and mark visual acceptance unverified; do not claim fidelity based
  only on offline tests.

## Responsibility and handoff

One continuing implementation agent implements, tests, commits in English with
a Conventional Commit subject, pushes a dedicated branch and opens one PR per
stage. It reports branch, SHA, changed files, tests, limitations and PR URL.
The primary agent reviews diffs, follows live CI handles, requests fixes on the
same branch, and merges only after all CI passes. Each handoff records stage,
authoritative status, commit/PR/run evidence, blockers and exact next action.

## Stage 3: hyperlink formatting and honest scoring

- Dependency: stages 1/2 merged, latest main `ed872808625cf620d2c77772f303e8021584922d`.
  Stage 2's fixed WPS fixture reveals an undersized hyperlink while the semantic
  formatting score incorrectly reports 1.0.
- Scope: `html_editable.py` hyperlink run creation, `fidelity.py` DOCX run reading
  and missing-run formatting checks, focused tests, changelog and same-fixture
  evidence. No new directions, unsafe-link exceptions, or environment repairs.
- Deliverables: computed hyperlink font/size/color/decoration and nested inline
  styles, retaining external relationships and existing target filtering; read
  normal and hyperlink runs in document order in body/cells/headers/footers;
  report absent styled source runs as failed checks instead of skipping them.
- Verification: `python -m unittest discover -s tests -p test_html_hyperlink_fidelity.py`,
  existing container/editable/conversion tests, `ruff check .`,
  `ruff format --check .`. Negative tests deliberately shrink/change/remove a
  hyperlink run: formatting must fail; matching runs must pass.
- WPS acceptance: reuse `direct_container.html` unchanged, new output directory,
  record hashes/versions/raw JSON and color page comparison; F2 full-page SSIM
  >= 0.90, text/structure/formatting 1.0, fixed 300px content diagnostic, and
  visual confirmation that the hyperlink size matches surrounding text.
- CI/merge: all six PR jobs green plus primary-agent diff/evidence review before
  merge to `main`. One dedicated branch/PR, English Conventional Commit.
- Stop: browser/WPS/credentials unavailable, original fixture misses a gate,
  or scoring exposes losses requiring unrelated conversion-direction changes.
  Historical baseline regressions exposed by honest scoring must be reported,
  never hidden by lowered thresholds or rewritten passing baselines.

## Stage 4: formal five-case HTML-to-DOCX WPS evidence

- Dependency: stage 3 merged at main `95f2947c2e10780067ab30749b8a4c1bf474f30b`;
  existing HTML/test/fidelity dependencies, Playwright/Edge, WPS and writable TEMP.
- Scope: only existing A-report/contract/newsletter/manual/pdfsource HTML-to-DOCX
  cases, with original local CSS/images. No product changes, fixture tuning,
  additional directions, group B or full 26-case execution.
- Deliverables: narrow runner, focused case/gate tests, original input asset
  hashes, generated DOCX/browser and WPS PDFs, raw JSON, per-page scores/color
  images/pairs, versions/process probes and `FIDELITY_STAGE4_ACCEPTANCE.md`.
- Acceptance is three separate columns: strict F2 layout >= 0.90 plus applicable
  text/structure/formatting/data 1.0; existing decision-10 exceptions only for
  contract >= 0.84/manual >= 0.88 with WPS and layout the only failed aspect;
  and missing-font/renderer/version comparability limits. Known deviations are
  not strict F2 passes. Reinspect page evidence before attributing gaps to glyphs.
- Historical comparison: configured LibreOffice scores are reference-only; do
  not apply their baseline-minus-0.02 rule to WPS. Show prior WPS evidence with
  version/source caveats, without updating thresholds or configured baselines.
- Verification: `python scripts/html_docx_wps_matrix.py --out <new-directory>`
  (exactly five cases); `python -m unittest discover -s tests -p
  test_html_docx_wps_matrix.py`; existing hyperlink/container/conversion tests;
  full Ruff lint/format. All six PR CI jobs and primary-agent diff/image review
  are required before merging the dedicated evidence PR to `main`.
- Stop: refuse export if any WPS process is already running; never use the old
  `_release_wps`/taskkill cleanup or close user documents. Preserve raw errors
  for browser/WPS/credential failures. Report each strict threshold failure as
  measured, retain decision-10 status separately, and do not change inputs,
  installation, product behavior or tolerance to obtain acceptance. Any needed
  product repair requires a new reviewed stage plan.

## Stage 5: vertical-merged contract cell borders and shading

- Dependency/base: stage 4 PR #159 merged with all six CI jobs green; exact main
  `edefb7a885dd32af92eeb84bf499f29a9b75e612`. Work in the existing isolated
  worktree on a dedicated branch. This section is submitted for review before
  any product edit, test or WPS run; implementation needs primary-agent go-ahead.
- Acceptance source: stage-4 contract WPS comparison and existing DOCX XML.
  The two vertically merged fee-table headers have styled restart cells but
  continuation cells without explicit borders/shading. `apply_table` skips the
  covered HTML grid slots after merges. This is a testable defect hypothesis,
  not a claim that it explains the whole 0.8491 layout score.
- Scope: merged-cell physical `w:tc` border/shading mapping in `docx_styling.py`;
  `html_editable.py` only if passing the existing merge rectangles is necessary;
  focused regression tests, changelog and same-input evidence. Do not change
  column widths, row heights, pagination, glyphs, signing-block spacing, other
  conversion directions, original fixtures/assets, thresholds or baselines.
- Deliverables: correct perimeter borders on vertical merge restart/continuation
  cells (continuous exterior edges, no interior horizontal seams), consistent
  shading, no duplicate `tcBorders`/`shd`, unchanged text and merge structure.
  Tests inspect physical `tr/tc` XML rather than `table.cell` origin aliases.
- Verification after approval: first reproduce missing continuation formatting;
  `python -m unittest discover -s tests -p test_docx_merged_cell_borders.py`,
  with simple rowspan, combined rowspan/colspan and unmerged controls; existing
  HTML/editable/conversion/hyperlink/container regressions; full Ruff lint/format
  and diff whitespace checks. No test or WPS execution during plan review.
- WPS acceptance after approval: reuse original `contract.html` bytes in a new
  evidence directory, retaining input/output SHA-256, versions/probes, DOCX,
  Edge/WPS PDFs, full-page and fixed fee-table-region color comparisons and
  per-page SSIM. Verify continuous merged-header perimeter, complete shading,
  no extra internal line, semantic text/structure/formatting/data 1.0 and 1/1
  pages. Record the whole-case score against stage-4 0.8491 without changing the
  strict 0.90 or existing decision-10 floor 0.84. A remaining strict failure is
  still a failure; local border repair is not whole-case high-fidelity acceptance.
- Integration: one English Conventional Commit and dedicated PR to `main`;
  all six CI jobs green plus primary-agent diff/XML/image review before merge.
- Stop: hypothesis cannot be reproduced, WPS/browser/credentials unavailable,
  border/shading remains wrong, semantic loss or new visual/score regression,
  or repair requires unrelated layout changes. Preserve raw evidence and report
  before revising scope. Never tune inputs/tolerances, change the installation,
  terminate user processes or close user documents to obtain a pass.

## Stage 7: hr-to-following-block spacing in the manual

- Dependency/base: clean separate worktree on exact main
  `f1ca25fe0da8af4dfe5701f3d5d50b86c921714d`, after stage 5 PR #160 merged
  with six green CI jobs. Stage 6 remains stopped/uncommitted in its original
  worktree with all three raw candidates preserved; none of its edits are used.
  This is plan-only until primary-agent review and implementation go-ahead.
- Acceptance source: original stage-4 manual CSS/DOM, DOCX and WPS PDF. The hr
  bottom margin is 7px; the following h2 top margin is 17.43px and DOM gap 17.42px.
  DOCX hr after is 105twips/5.25pt, but h2 before is reduced to 156twips/7.8pt
  instead of retaining its full approximately 261twips/13.07pt margin. The
  current mapper subtracts the prior after-spacing although native paragraph
  spacing already takes the maximum of adjacent requests. Original WPS third-
  section title is about 7pt above the browser reference. This supports a local
  spacing hypothesis, not a claim that all remaining differences are explained.
- Scope: only `docx_styling.Context`, `apply_rule` and the immediate following
  `apply_paragraph` boundary, if needed with narrowly scoped flow reset wiring.
  Preserve the computed full top margin after a rule, without subtracting that
  rule's after-spacing again. No global margin algorithm change, non-hr paragraph
  rewrite, table sizing, font/size, signing block, list, details or other format
  changes; no original fixture/asset, baseline, environment or tolerance changes.
- Deliverables after approval: first reproduce the reduced before-spacing in
  XML, then a boundary-local repair; focused `test_docx_rule_spacing.py`,
  changelog and fresh same-manual raw JSON/PDF/DOCX/hash/version evidence.
  Tests cover rule-to-heading/paragraph, different relative margins, non-rule
  controls and intervening-table reset so the boundary state cannot leak.
- Verification after approval: new focused tests plus existing rule, paragraph,
  table-spacing, HTML/conversion/roundtrip regressions; full Ruff lint/format
  and diff whitespace checks. Tests check CSS-derived spacing, not a manual-only
  pixel correction. Original contract has no hr and must retain its behavior.
- WPS acceptance after approval: only the original manual in a new directory,
  same source bytes, 1/1 pages and semantic text/structure/formatting/data 1.0.
  Record title/QA y coordinates, full-page SSIM and fixed source-defined lower
  region `[40,495,760,625]`, without alignment/resampling. Third-section and QA
  positions and local SSIM must improve toward the browser; earlier page content
  must not move. Whole-page SSIM must improve over 0.8872; the strict target stays
  >= 0.90, with any remaining failure reported as such. Existing decision-10
  floor 0.88 is unchanged and cannot be relabeled strict success.
- Integration: same continuing agent, dedicated English Conventional Commit/PR
  to main only after acceptance; all six CI jobs green and primary-agent
  diff/XML/image review before merge.
- Stop: hypothesis not reproducible, WPS spacing response contradicts it,
  browser/WPS/credential failure, semantic/page-count/other-layout regression,
  local/whole scores fail to improve, or repair needs global/non-hr margin or
  unrelated product/environment changes. Preserve raw evidence and report before
  changing scope; never adjust inputs, alignment or thresholds to obtain a pass.

## Stage 8: read-only attribution of remaining manual geometry

- Dependency/base: stage 7 PR #161 merged with six green CI jobs; exact main
  `ebd94400baa8ca0881e102c08b5917388dd5ee30`. Use the clean stage-7 worktree
  on `docs/manual-geometry-attribution`, preserving its untracked local logs.
  The separate stopped stage-6 worktree and all raw candidates remain frozen.
  This section is plan-only pending primary-agent approval; no scripts, tests
  or measurement runs precede that approval.
- Scope: original manual only, using committed stage-7 browser/WPS PDFs,
  converted DOCX, browser computed styles and original stage-4 reference.
  Read existing PDF vector line rectangles/widths, text bounding boxes and
  DOCX table grid/row/cell/paragraph dimensions. Map measurements in PDF points
  and CSS pixels using page dimensions, retaining original page origins.
  Focus on the four-row options table and its immediately following heading;
  separate horizontal width, row pitch, border stroke and text baseline deltas.
  Contract is excluded initially: consult its existing evidence only if needed
  to distinguish a shared implementation rule, and explain that dependency first.
- Deliverables after approval: a narrow offline extraction script, focused
  extraction/unit-conversion tests, machine-readable measurements with source
  SHA-256/page/tool versions and a report linking every attribution to existing
  source code and OOXML properties. Include a coordinate overlay or compact
  measurement table where useful, keeping original images/PDFs immutable.
  Quantify uncertainty from stroke bounds, rounding and font metrics. Distinguish
  observed mismatch, supported causal hypothesis and unresolved explanation.
- Verification after approval: run the focused extraction tests, rerun the
  offline extractor twice and require identical normalized geometry JSON;
  cross-check representative PDF vectors/text positions against existing page
  images and DOCX twip-to-point values. Run full Ruff check/format and diff
  whitespace checks. No conversion or new browser/WPS process is required.
- Acceptance: reproducible attribution rather than an F2 pass. Identify at most
  one remaining implementation cause with a measurable predicted geometric
  effect, a source/XML trace and explicit counterevidence/regression risks;
  otherwise report that no single cause is established. A prediction must
  explain the observed region without arbitrary offsets, image alignment or
  threshold tuning. Existing manual whole-page 0.8959 remains strict F2 failure
  at the unchanged 0.90 threshold; the 0.88 historical exception stays separate.
  No promise that attribution alone closes the score gap is permitted.
- Boundaries: no product edits, fixture/input/asset/baseline/threshold changes,
  font or software installation, global margin/width tuning, new renderer run,
  or expansion to other formats. A subsequent product repair needs a separately
  reviewed plan with negative reproduction and real WPS acceptance.
- Integration: an evidence-only PR to main is appropriate if the extraction and
  report provide reusable, verified measurements, including a grounded negative
  conclusion. Avoid duplicating existing large binaries. Same continuing agent
  implements only after approval, then English Conventional Commit, push and PR;
  primary-agent diff/evidence review and all six required CI jobs green before
  merge. A local exploratory dead end need not become a PR.
- Stop: missing/corrupt evidence, incompatible PDF coordinate interpretation,
  irreproducible extraction, inability to isolate a cause, or need for new WPS,
  font/environment changes or broader product work. Preserve the measurements,
  state what is unresolved and report; do not silently broaden or tune.

## Stage 9: isolated WPS row-minimum mechanism experiment

- Dependency/base: stage 8 PR #162 merged with six green CI jobs, exact main
  `b93e2c24d3921f5b3845f14fd8856ddf05f5e88c`. Stage-8 evidence establishes
  manual browser row pitch19.5pt versus WPS20.25pt for DOCX AT_LEAST19.5pt.
  Use a clean branch `docs/manual-row-mechanism` in the stage-7 worktree;
  preserve prior evidence/logs and the separate frozen stage-6 worktree.
  This is plan-only until review: no generation, tests or WPS execution yet.
- Scope/input: create synthetic experiment DOCX files by copying the committed
  stage-7 manual DOCX package, retaining only its first four-row/three-column
  table plus section properties in the body. Preserve table widths, text,
  styles, borders, cell alignment and paragraph formatting unless explicitly
  varied below. Do not call or edit the product HTML converter; original HTML,
  DOCX/PDF evidence and baselines remain byte-identical. Retain a package manifest
  and original SHA plus per-variant DOCX SHA and exact XML differences. Generate
  stable ZIP metadata/order so identical inputs produce identical package bytes.
- Fixed seven variants (all rows changed uniformly, no arbitrary offsets):
  B = original table, AT_LEAST390twips (19.5pt), nominal6/8pt borders;
  E = B with hRule EXACT only;
  R = B with AT_LEAST375twips (18.75pt), one nominal border less;
  L = B with cell content minimum lowered: replace each cell's text by one
  ASCII X run at1pt and exact1pt line, paragraph before/after0, vertical cell
  margins0; retain row request/borders/widths;
  LR = L with AT_LEAST375twips;
  N = B with physical table/cell borders explicitly nil, all content unchanged;
  NR = N with AT_LEAST375twips. E is a diagnostic only: clipping or compression
  cannot be interpreted as an acceptable repair. L/LR are synthetic probes, not
  alternate manual fixtures, and never enter fidelity baselines.
- Discriminating expectations: additive native border accounting predicts
  B/L20.25pt, R/LR19.5pt, N19.5pt and NR18.75pt. Content-limited behavior predicts
  a plateau in B/R that drops when content is lowered in L/LR. A rule-dependent
  difference in E localizes the AT_LEAST path; borderless comparisons distinguish
  border involvement from a content-only constraint. Mixed or different outcomes
  must be reported as unresolved, not forced into either model. Measure all four
  row pitches, not only total table height. Treat agreement within0.05pt as PDF
  measurement precision, separate from unchanged product F2 thresholds.
- Safety/process gate: record read-only WPS process/version probe before every
  export; any existing WPS process, failed probe or unexpected process state stops
  without COM. Export each generated DOCX via the existing isolated converter,
  sequentially with its normal120s timeout, releasing only its own instance.
  Never use taskkill/_release_wps, attach to a user instance or close user docs.
  Preserve raw timeout/COM/credential errors; no installation or font changes,
  broad retry, browser run or HTML conversion.
- Deliverables after approval: narrow deterministic variant builder/runner,
  focused XML-difference/package-determinism tests, source/variant/output SHA,
  WPS/version/probe/export JSON, seven generated DOCX/PDF files, PDF vector/text
  measurements and selected page images, plus root-cause report with predictions,
  observed table, uncertainty/counterevidence and any diagnostic clipping.
  Avoid copying unchanged large source binaries into the new evidence directory.
- Verification: focused tests prove each variant changes only its declared XML,
  four physical rows remain, unrelated package parts are identical, original
  hashes unchanged and generation is deterministic. Reuse the reviewed offline
  centerline extractor with fixed coordinates or explicitly recorded section-
  derived synthetic table window. Run focused tests, full Ruff lint/format and
  whitespace checks; one sequential WPS experiment set, no tuning reruns.
- Acceptance: reproducible mechanism evidence, not manual high-fidelity success.
  Raw results must distinguish additive-border from content-minimum behavior
  or explicitly establish that these controls do not identify one cause. Inspect
  diagnostic text/vector preservation and explain page count/geometry changes.
  Manual strict F2 remains0.8959<0.90; no conversion repair is authorized here.
- Stop: unexpected fixture/source mutation, unisolated WPS, missing/corrupt
  source, unsafe lifecycle, failed export, ambiguous/noisy vector extraction,
  uncontrolled XML differences, need for more variants or environment/product
  changes. Preserve completed evidence and report before expanding/retrying.
- Integration: verified reusable evidence, including a negative result, may be
  an evidence-only English Conventional Commit/PR to main by this same continuing
  agent. Primary-agent code/XML/image review plus all six CI jobs green before
  merge. Any product repair needs a subsequent separately reviewed plan.

## Stage 13: closed-details retained-text mechanism experiment

- Dependency/base: exact merged main
  `5779f84c258aa1dc9690e8a88240b5f53b7b9e59`, clean separate worktree
  `.codex-build/fidelity-details`, branch `docs/report-details-triage`. Preserve
  frozen stage6/10/12 worktrees and all original report/evidence bytes. Source
  report details has no open attribute; existing browser PDF shows summary only,
  but DOCX/WPS shows summary plus body. Existing semantic scoring retains text
  without testing visibility. This stage is plan-only pending review.
- Scope: synthetic DOCX only, no HTML conversion or product/scorer change.
  Build deterministic packages with A4 page, fixed1inch margins, explicit12pt
  font, exact18pt paragraph pitch and zero paragraph before/after. Use unique
  ASCII sentinels SUMMARY, RETAINED-BODY and FOLLOWING to avoid ambiguity in PDF
  extraction; this isolates hiding/paragraph behavior rather than CJK/font/layout
  reproduction. No triangle marker, interactive controls or original report edit.
- Exact four predeclared controls:
  V: visible SUMMARY paragraph, visible RETAINED-BODY paragraph, FOLLOWING paragraph;
  H: SUMMARY and RETAINED-BODY in separate runs of one paragraph, with w:vanish
  on body run only; then FOLLOWING paragraph;
  P: V with w:vanish on body run and on body paragraph-mark rPr;
  C: SUMMARY paragraph then FOLLOWING paragraph, no body, as closed-layout-only
  reference (intentionally does not retain content and cannot be product output).
  V is the visible/open-state reference; no fifth duplicate open control is needed.
  Preserve sections/styles/fonts/relationships and other package parts across
  controls; record exact document.xml changes. Use stable ZIP order/metadata and
  fixed package properties so regeneration yields identical bytes/SHA-256.
- Safe execution after approval: exactly one sequential four-export WPS set,
  record process/version probe before each case; existing process or failed probe
  stops before COM. Use existing converter with120s timeout and release only its
  own document/instance. No taskkill, user-instance attachment or document closure,
  installation/font changes, HTML/browser render, retries or tuning reruns.
  Do not modify application global hidden-text/printing preferences. Record any
  safely queryable setting only through the owned export instance; if unavailable,
  report unknown rather than attach elsewhere or expand the converter.
- Deliverables: narrow deterministic builder/offline XML/package tests and opt-in
  WPS runner; four DOCX/PDF/page images, source/script/package/output SHA/version/
  raw probe/export records and vector/text coordinates. Report retained underlying
  text separately from visible PDF text and spacing; include limitations and any
  failed controls. Original report stays untouched and is not newly rendered.
- Tests: V/H/P retain each sentinel exactly once in underlying document XML;
  C deliberately lacks body. H hides only body run and creates no body paragraph;
  P additionally hides its paragraph mark, preserving its physical paragraph;
  V has no hidden text. Assert exact declared XML differences, identical unrelated
  package parts, deterministic regeneration, correct page/font/spacing settings.
  Run focused tests, full Ruff/format and whitespace checks; no renderer in tests.
- Mechanism acceptance: all cases export to one page; V PDF contains all three
  sentinels in order, C contains SUMMARY/FOLLOWING only. H/P must preserve body
  in DOCX yet omit it from PDF. Measure SUMMARY/FOLLOWING text tops/baselines:
  H FOLLOWING must match C within0.05pt to establish no hidden-body flow footprint.
  P is a diagnostic: record its FOLLOWING offset from C and any blank line as its
  own result; P need not pass and its spacing must not be altered. H must satisfy
  retained-text plus visible/layout gates for a
  grounded simple closed-details candidate. This is not report F2 acceptance,
  not an accessibility result and not HTML interaction support.
- Uncertainty/counterevidence: OOXML vanish normally hides runs, but applications
  can force display and printing of hidden text; WPS support/settings are not
  assumed. A successful default-host result does not prove other hosts/settings,
  screen-reader behavior, nested/complex details, editable recovery UI or roundtrip
  semantics. No metadata/comments workaround or scorer threshold change may be
  introduced to mask failure. A later product plan needs explicit visibility and
  retained-content checks in addition to existing semantic scores.
- Stop: unsafe/unavailable WPS, source/package scope drift, failed export, absent
  sentinels, unreliable PDF extraction, H fails hidden-text/layout gates, need for
  global preference changes or extra variants. Preserve complete raw evidence,
  state negative/unknown conclusions and report before expansion. Expected P
  paragraph-flow failure alone is informative, not permission to tune it.
- Integration: verified reusable positive/negative mechanism evidence may form
  an evidence-only English Conventional Commit/push/PR to main by this same agent;
  primary-agent XML/image review plus all six CI jobs green before merge. No
  product fix or subsequent experiment is authorized by this evidence stage.

## Stage 14: bounded closed-details static mapping

- Dependency/base: stage13 PR #164 merged after six green CI jobs; exact main
  `1471f521ac4c3b4c037f7dabffbf0f22ba747066`, clean fidelity-details worktree
  on `fix/docx-closed-details`. Stage13 H demonstrated retained body XML with no
  visible PDF text or extra flow on WPS12.8.2.18913. Preserve all original inputs,
  baselines and stopped stage6/10/12 worktrees. Plan-only pending primary review.
- Supported shape: details without any open attribute, exactly one explicit
  first summary containing nonempty direct plain text, exactly one subsequent p
  containing nonempty direct plain text, and only whitespace between them. Reject
  nested/extra nodes, pseudo-content, nonstandard visibility/positioning or other
  uncertainty rather than silently flatten it. A shared pure shape helper may
  identify this exact form for conversion and source scoring.
- Product scope: html_editable details dispatch renders summary with its current
  computed paragraph/run styles, then appends body text using its own original
  node's computed run styles and explicit w:vanish in that same paragraph. Do not
  create a body paragraph or carry its margins into following flow. Retain each
  original text exactly once in XML. No summary marker/indent or global spacing
  repair; existing triangle and approximately11pt summary-y mismatch are disclosed
  residuals. Static preservation is not disclosure interaction or accessibility.
- Open/unsupported behavior: presence of open, including open="false" or empty
  value, retains existing expanded conversion/XML behavior. Unsupported closed
  shapes (missing/multiple/complex summary, multiple/empty/complex body, nested
  details, links/images/tables/forms/inline elements or ambiguous styles) keep
  legacy expanded content and emit explicit collapsed-state-not-preserved warning.
  Never remove body text or claim the warning path preserved closed appearance.
- Scorer scope: add optional hidden expectation to run model, default unspecified
  for unrelated content. Source reader reuses supported-details identification:
  closed body expects hidden, summary expects visible; corresponding supported
  open content expects visible. DOCX reader reads effective hidden state for these
  checks, including explicitly styled runs. Formatting scorer checks hidden only
  when source has an expectation, without new thresholds or a general visibility
  policy. The original committed expanded report must fail this new check; repaired
  output must pass. Expose the mismatch in diagnostics, not just an opaque score.
  If effective style inheritance cannot be safely determined locally, stop/report
  rather than silently treating unknown as visible or widening the reader overhaul.
- Deliverables after approval: negative old-report conversion/scoring reproduction,
  narrow mapping/shared helper/scorer change, focused tests, changelog and fresh
  original five-case raw evidence, input/output SHA/version/probe records, summary/
  body/following-text PDF coordinates, before/after visibility and score report.
  Record original paragraph-body structure now represented as retained run text;
  current structure score does not validate full hidden paragraph semantics.
- Tests: supported closed shape retains exact summary/body text once, hides only
  body, creates no flow paragraph and preserves computed run formatting; old
  expanded DOCX fails hidden-state scoring, fixed output passes, missing/deleted
  body still fails text retention. Open attribute values retain expanded XML and
  visible expectations. Unsupported-shape matrix preserves all original content
  with warning. Controls cover unrelated p, links and existing hr/p-spacing paths,
  inherited hidden formatting and duplicated text ambiguity. Run focused and
  related HTML/conversion/fidelity/roundtrip tests, historical baseline checks
  for new hidden-state revelations, full Ruff/format and whitespace checks.
- Real acceptance: exactly one original five-case safe WPS/browser set after
  tests; per-case no-existing-process probe and own-instance lifecycle, no global
  hidden/print setting changes. Compare latest committed accepted evidence:
  report/newsletter/pdfsource Stage4, contract Stage5, manual Stage7. All source
  bytes unchanged; applicable semantic scores1.0, page counts unchanged, every
  page and aggregate SSIM nondecreasing. Original report must remain2/2pages,
  page1 WPS pixels identical, body phrase absent from all WPS PDF pages while
  retained in DOCX. Summary stays visible with unchanged WPS top/x within0.05pt;
  contacts/unsafe-link label remain visible, and each following-text position error
  against browser must not increase. Record page2 and aggregate improvement or
  remaining limitations honestly; unchanged strict0.90 and historical exceptions
  must not be conflated. No alignment, fixture edits or threshold tuning.
- Stop: shape/state ambiguous, retained text missing/duplicated, old output passes
  hidden check incorrectly, unsupported path drops content, hidden body prints,
  summary/following-state gates or any five-case semantic/page/per-page/aggregate
  gate fails, or safe renderer unavailable. Preserve raw outputs and uncommitted
  work; report without tuning reruns/commit/PR or broader policy/layout changes.
  No cross-settings/cross-host promise or screen-reader/interactive claim.
- Integration: same continuing agent; English Conventional Commit/push/PR to main
  only after gates and primary-agent evidence review. All six CI jobs must pass
  before merge; implementation agent does not merge.

## Stage 15: plain-pre boundary whitespace semantics

- Dependency/base: stage14 PR #165 merged after updated-head six green CI jobs,
  exact main `0947a424349aaac8c5edae0503636c76a69ff486`. Clean branch
  `fix/docx-plain-pre-whitespace` in fidelity-details worktree; preserve local
  logs and all frozen stage6/10/12 worktrees. Plan-only until primary review.
- Grounded source/XML: original report pre begins CRLF and ends
  `GROUP BY region;` plus CRLF plus four spaces. HTML normalizes CRLF/lone CR to
  LF and ignores only one LF immediately after the pre start tag. Current
  add_paragraph preserve branch lstrips all leading newlines and rstrips terminal
  HTML whitespace; generated SQL has four text lines/three br and no terminal
  blank/indented line. Browser PDF SQL line pitch11.25pt matches WPS approximately
  11.25pt, but following summary is about11pt early. Pre CSS after13px=9.75pt
  already matches XML195twips. Do not add a compensating paragraph margin.
- Scope: only pre with direct string children, default/preformatted whitespace
  behavior and no nested nodes. Preserve existing raw-CRLF/lone-CR normalization;
  remove exactly one source-initial LF, preserving any additional leading LF and
  all terminal LF/indentation/tab-space text. Preserve internal indent and blank
  lines. No nested code behavior, rich pre/inline runs, global whitespace policy,
  paragraph/list/table/summary margin, font/line pitch, triangle or scorer changes.
  Ambiguous author white-space overrides retain existing behavior rather than
  entering this narrow mapping. No fixture/baseline/threshold edits.
- Evidence limits: archived browser measurement preheight150px/text-lines10
  conflicts with actual PDF/source line evidence and may reflect Windows
  temporary-file newline translation. Do not use it to derive a total-height
  adjustment or change the browser annotation pipeline in this stage. Use original
  source bytes, native br/text XML and actual PDF coordinates for attribution.
- Deliverables after approval: first failing original-report XML/text test,
  minimal plain-pre normalization repair, focused tests, changelog and fresh
  original-five-case raw source/output SHA/version/probe/PDF/DOCX/image evidence.
  Record exact preserved pre text, br count, SQL line coordinates and summary/
  contacts/unsafe-label coordinates, existing hidden-body retention/visibility
  gates, unchanged marker residual and any remaining font/position uncertainty.
- Tests: original report must retain terminal LF plus four spaces after its
  initial HTML-ignored LF. Cover LF/CRLF/lone CR equivalence, exactly one versus
  multiple leading LF, empty/whitespace-only pre, terminal LF plus space/tab,
  no-terminal-LF control and internal indent/blank lines. Negative controls keep
  nested pre/code XML/text unchanged and ordinary paragraph whitespace collapse;
  retain existing Windows CRLF-no-extra-blank-line and complex report indentation
  tests. Verify python-docx w:br/text/xml:space serialization rather than inserting
  empty paragraphs. Run focused/related HTML/conversion/roundtrip/fidelity tests,
  full Ruff/format and whitespace checks before WPS.
- Original-report acceptance: latest accepted stage14 WPS summarytop155.63pt
  versus browser166.6406pt; contacts/phone183.35 versus194.3906pt, unsafe label
 211.19 versus222.1406pt. New absolute vertical errors for all must decrease;
  x positions, SQL visible-line positions and prior content must not drift beyond
  native0.05pt quantization without an explanation reviewed before acceptance.
  Report page1 WPS pixels identical; page2 SSIM must improve above0.9684 and
  aggregate above0.9255, with2/2pages and semantic scores1.0. Hidden details body
  remains exactly once in XML and absent from PDF, summary/following text visible.
  Missing disclosure triangle stays outside scope; no interaction/accessibility
  claim. Any needed general layout compensation triggers stop.
- Five-case regression: exactly one safe original five-case WPS/browser set,
  no-existing-process probes and converter-owned instances only. Latest accepted
  stage14 evidence is the reference for all five. Each page and aggregate SSIM
  nondecreasing, page counts unchanged, applicable semantic scores1.0. Manual's
  only pre contains nested code/no terminal LF and must retain old behavior;
  contract/newsletter/pdfsource have no pre. Strict0.90 and existing exceptions
  remain separate; no source edits, alignment or tuning reruns.
- Stop: source/XML hypothesis not reproducible, ambiguity in initial-LF handling,
  nested-code/global behavior changes, real output does not improve declared
  report gates, any five-case regression, hidden body leak/content loss, unsafe/
  unavailable renderer, or repair needs browser-pipeline/font/marker/global spacing
  changes. Preserve raw evidence and uncommitted work; report before expansion,
  commit or PR. Never terminate user processes or alter global preferences.
- Integration: same continuing agent; English Conventional Commit/push/PR to main
  only after acceptance, primary-agent diff/XML/image review and all six CI jobs
  green before merge. Implementation agent does not merge.

## Stage 16: native vector picture-bullet mechanism

- Dependency/base: stage15 PR #166 merged with six green CI jobs; exact main
  `c113181c7977648294652a9e6d53b620aefbe768`, clean fidelity-details worktree
  on `docs/summary-picture-bullet-mechanism`. Preserve all prior evidence/logs
  and frozen stage6/10/12 worktrees. Plan-only pending review; no product conversion
  or browser style-reader edits, tests or WPS execution before approval.
- Grounding: original report browser filled triangle vertices approximately
  (33.7500,167.5898),(40.5527,171.5449),(33.7500,175.5000)pt, summary text
  starts46.4531pt. Chromium's documented disclosure implementation uses0.66em
  symbol square,0.4em end gap and bottom aligned to text baseline, consistent
  with observed symbol height7.9102pt and advance12.7031pt at12pt font. These are
  font-relative predictions, not a fixture-specific text shift. Existing UA
  marker is inside; this single-line experiment does not claim inside wrapping.
  Sources: [Chromium disclosure layout](https://chromium.googlesource.com/chromium/src.git/+/cb11d5949b731a22810c46c99c4d3ad64b2e91ec%5E%21/)
  (historical implementation, corroborated by current PDF, not proof of every UA),
  [OOXML picture reference](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.levelpicturebulletid?view=openxml-3.0.1)
  and [VML picture container](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.picture?view=openxml-3.0.1).
- Synthetic input only: deterministic A4 DOCX,1inch margins, Arial font S,
  exact1.5S line pitch and zero paragraph before/after. SUMMARY plus vanished
  RETAINED-BODY runs in the first paragraph, FOLLOWING in the second, identical
  underlying text across controls. No source report, fixture, baseline, threshold,
  fonts/install, global display/printing preferences or scorer/product changes.
- Exactly six predeclared variants: C12/Z12/N12 and C18/Z18/N18, S=12/18pt.
  C has plain unnumbered SUMMARY and no new numbering definition. Z adds one
  document-local w:numPicBullet with w:pict/VML black filled unstroked triangle,
  one abstractNum/num referencing it via lvlPicBulletId, suff=nothing and zero
  level indentation; it diagnoses support/default intrinsic advance. N uses
  the identical vector definition but suff=tab, left indent A and hanging A,
  with a numbering tab stop at A, where A=1.06S rounded once to native twips.
  Marker origin is the original C text origin, N summary text is advanced by A.
  No arbitrary offset, glyph substitution, raster fallback or iterative variants.
- Vector definition: square side0.66S, canonical normalized right-pointing
  triangle vertices(0,0),(.86,.5),(0,1), black fill/no stroke; expected painted
  width0.86*0.66S and height0.66S. Normalized geometry is corroborated by observed
  browser PDF, with historical-UA uncertainty recorded. Use native picture-bullet
  baseline behavior; do not add VML top/y nudges or run raise/lower adjustments.
  lvlText has a single placeholder X, replaced by picture per OOXML; if X is
  painted, that is failed picture support, never permission to substitute a glyph.
  Allocate fresh IDs without changing existing template numbering definitions.
- Deliverables after approval: narrow synthetic builder/opt-in runner, deterministic
  XML/package tests, six input DOCX/PDF/page images, input/output/script SHA and
  tool/WPS versions, raw pre-case probes/exports, vector vertices/bounds/size,
  summary/FOLLOWING text tops/x and text-matrix baselines. Record hidden-body
  retention versus PDF visibility, original predictions and all mismatches.
- Tests: deterministic ZIP metadata/order/properties; only document.xml and
  numbering.xml differ as declared, all unrelated parts byte-identical; fresh
  IDs/references, one closed filled vector, dimension scaling, exact native
  indent/tab/suffix controls, no marker characters/tabs in paragraph text, retained
  body exactly once/hidden and plain controls unnumbered. Run focused tests plus
  full Ruff/format and whitespace checks before the real experiment.
- Safe execution: exactly one sequential six-export WPS set, pre-case no-existing-
  process/version probes,120s normal export timeout and own-instance release.
  Existing processes/probe failure stop before COM. No taskkill, user-document
  closure/attachment, preference changes, browser/HTML conversion or tuning rerun.
- Acceptance as mechanism evidence: each case1page with SUMMARY/FOLLOWING visible
  and RETAINED-BODY present once in DOCX but absent in PDF. For both N sizes require
  a measurable filled right-pointing vector (not placeholder X), painted width/
  height within0.10pt of predictions, marker left within0.10pt of C text left,
  marker bottom within0.10pt of SUMMARY native text baseline, N text advance within
 0.10pt of twip-rounded A, and SUMMARY/FOLLOWING y positions within0.05pt of C.
  Compare font-relative scaling across12/18 rather than accepting one-size luck.
  Z outcomes are diagnostic, not required to match N advance. No F2 score or
  original report success claim follows from synthetic support alone.
- Uncertainty/stop: WPS may ignore VML vector picture bullets, paint placeholder,
  rescale them, apply native baseline/indent rules differently or produce geometry
  not reliably measurable as vectors. Any required N/retention/page/position gate
  failure or unsafe/export error stops without tuning/retry or product PR. Preserve
  all completed raw evidence, label unsupported/ambiguous outcomes. No inside-wrap,
  RTL, custom-marker, interaction, accessibility or cross-host/settings claim.
- Integration: reusable verified positive/negative mechanism evidence may form an
  evidence-only English Conventional Commit/push/PR to main by the same agent;
  primary XML/image review and all six CI jobs green before merge. A product
  mapping or broader experiment needs a separately reviewed plan afterward.

## Stage 17: inline DrawingML marker mechanism

- Dependency/base: stage16 PR #167 merged with six green CI jobs; exact main
  `9a33efd851b4e00bca3d21d8ec600518828cf637`, isolated branch
  `docs/inline-summary-marker-mechanism`. Frozen stage6/10/12 remain untouched.
  Primary agent reviewed and authorized this plan before implementation.
- Scope: synthetic DOCX only, no product/browser/scorer/report/fixture/baseline
  changes. Native wp:inline/a:graphicData(wps namespace)/wps:wsp/a:custGeom,
  black fill/no stroke, MCE Choice requiring wps and no picture/text fallback.
  No VML/numbering/font glyph/anchor offsets/run raise-lower/literal gap text.
- Six fixed controls C12/I12/G12/C18/I18/G18: A4/1inch margins/Arial S,
  exact1.5S paragraph pitch and zero margins. SUMMARY plus vanished RETAINED-BODY
  in first paragraph, FOLLOWING in second. C has no drawing. I inline extent
  .66S square, path6600x6600; G extent1.06S by.66S, path10600x6600. Both use
  path points(0,0),(5676,3300),(0,6600), yielding identical physical triangle
  width.5676S/height.66S. G's extra.4S canvas is the source UA gap, not a pixel
  offset. Shape transform origin0, extent equals wp extent, effectExtent0;
  quantize once to EMU. Marker run font S matches SUMMARY. No additional variants.
- Grounding: reuse stage15 PDF geometry and the documented Chromium .66em symbol/
  .4em gap; no new browser run required. Native inline flow and custom geometry:
  https://learn.microsoft.com/en-us/openspecs/office_standards/ms-odrawxml/1ba79d37-c640-41dc-ba4e-9180ed31651e
  and https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.customgeometry?view=openxml-3.0.1.
  These establish a representation, not WPS support or inside-wrap fidelity.
- Deliverables: deterministic builder/opt-in runner and focused tests; six
  DOCX/PDF/page images, source/script/package/output SHA, tool and actual WPS
  executable versions, per-case probes/exports, vector vertices/bounds and text
  x/top/baselines, retained/visible text and explicit required-gate report.
- Tests: stable ZIP/properties, only document.xml changes, unrelated parts equal;
  C zero/I/G one drawing, valid MCE/IDs/namespaces/path/fill/extents, no fallback,
  numPr/VML/glyph/tab/extra text. Exact retained sentinels/hidden body and scaling;
  negative gate controls for absent/wrong vector, advance, y and body leaks.
  Focused tests plus full Ruff/format and whitespace checks precede WPS.
- Real execution: exactly one sequential six-export set, pre-case empty-process
  and executable/version probes, normal120s timeout, converter-owned instance
  release only. Never change global hidden/print preferences, taskkill or attach
  to/close user documents. No tuning retry or browser/HTML conversion.
- Required acceptance at BOTH sizes: all six1page, SUMMARY/FOLLOWING visible and
  body retained once/hidden in DOCX but absent in PDF. I/G each produce measurable
  filled right triangle, width/height and marker left relative C text-left within
  .10pt of predictions, marker bottom relative SUMMARY baseline within.10pt;
  native text advances I=.66S/G=1.06S within.10pt and G-I=.4S within.10pt.
  SUMMARY/FOLLOWING y changes from C at most.05pt. No original-report F2,
  inside-wrap, RTL, interaction/accessibility or cross-settings claim.
- Stop: any required gate failure, missing/ignored/raster-unmeasurable shape,
  unsafe process/export failure or need for offset/glyph/variant/environment
  changes. Preserve raw evidence and stop without retry/product recommendation.
  Verified negative evidence may be an evidence-only PR, never a product fix.
- Integration: same continuing agent, English Conventional Commit/push/PR to main,
  primary XML/image review and six green CI jobs before merge; agent never merges.
