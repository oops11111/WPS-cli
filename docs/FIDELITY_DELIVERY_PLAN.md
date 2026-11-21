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

## Stage 18: bounded closed-summary inline marker integration

- Dependency/base: stage17 PR #168 merged after six green jobs; exact main
  `c7e492dfe5259e7dfec040da00d03fe4bc43f22c`, isolated branch
  `fix/docx-closed-summary-marker`. Primary reviewed/authorized this plan.
  Frozen stage6/10/12 and original source/baselines/thresholds stay untouched.
- FIRST, current-browser preflight BEFORE product edits: collect ::marker
  content/font/color, display/list-style-type/position/image, direction/writing-mode/
  text-indent and one-line text Range advance; actual PDF triangle must corroborate
  default shape/recipe. Record versions/source SHA/raw JSON/PDF. If default shape
  cannot be stably established, preserve evidence and stop, never guess UA defaults.
- Conditional product scope: existing simple closed details only, browser marker
  eligibility/metadata, Stage17 G DrawingML helper and narrow managed-decoration
  scorer exclusion. Require complete metadata, disclosure-closed inside/no image,
  normal marker content, matching summary/marker font, black, one-line LTR,
  horizontal, no effects/custom positioning, advance compatible within one twip.
  Author list-style:none means no marker and NO warning. Unknown/custom/wrapped/
  RTL/cascade keeps current closed-body mapping plus marker-loss warning; base
  unsupported shapes retain expanded-warning path. Open presence, even false,
  stays unchanged. No global layout/scorer policy or other format changes.
- Insert one managed drawing AFTER summary generation/trim, BEFORE first text
  run; only then take hidden-body index. Exact text/vanish preserved, unique IDs,
  no glyph/tab/numbering/offset/raise-lower. Exclude only explicitly identified,
  structurally matching managed shape from semantic image count; real/other
  drawings unchanged. Existing image/visibility scores alone cannot prove marker.
- Deliverables: negative reproduction, bounded code/helper/browser metadata,
  focused tests/changelog/report, raw preflight and five-case SHA/version/probe/
  JSON/PDF/DOCX/images with marker/retention/semantic-count/position gates.
- Tests: original report absent-marker/image-count negative;12/18/multiple summary/
  leading spaces/trim/hidden/unique ID/no prefix positives; none/custom/open false/
  wrap/RTL/cascade/missing fields/advance/ancestor negatives; retained unsupported
  content and warnings; forged names not exempted and real chart count remains1.
  Related HTML/fidelity/roundtrip/historical baseline checks, JS syntax/metadata
  tests, full Ruff/format/diff before WPS.
- Real gates: ONE original five-case safe WPS/browser set, pre-case empty-process
  probes/runtime versions, own-instance release, no preferences/user-doc closure/
  taskkill. Stage15 baseline: report aggregate>.9302/page2>.9778/page1 pixels
  identical. All five every-page/aggregate nondecreasing, semantics1/same pages.
  One real triangle, body once/hidden and PDF absent, unchanged summary text;
  native advance improves x error, triangle size/relative-left/baseline within
  .10pt, summary/following y within.05pt of baseline. Disclose shared margin-x
  residual, never add offset. No inside-wrap/interaction/accessibility/cross-host
  promise; remaining strict failures distinct from historical exceptions.
- Stop: preflight uncertainty, eligibility unproven, duplication, trim/hidden
  regression, broad image exclusion, any score/semantic/page/position failure,
  unsafe renderer or need for glyph/offset/threshold/environment change. Preserve
  raw/uncommitted work and report, no tuning retry/commit/PR without amendment.
- Success: English Conventional Commit/push/PR, primary diff/XML/image review
  and six green CI jobs before main merge; implementation agent never merges.
  A stopped verified preflight may be evidence-only, never a product claim.

## Stage 19: isolated table-column allowance mechanism

- Dependency/base: merged Stage18 #169, exact main
  a694763fdcce823876b4cc9b2cc7de7615ab3f13; branch
  experiment/table-column-width-allowance. Frozen6/10/12 untouched.
- Scope: synthetic package copies of accepted manual three-column table and
  contract fee table ordinary body rows (remove merged header for all controls).
  Six fixed variants M0/M05/M1 and C0/C05/C1 differ only in gridCol/tcW width:
  subtract original per-column15twips then add0/7.5/15twips, rounded deterministically
  to integer twips. No converter/source/threshold/baseline edits.
- Deliverables: deterministic builder, package/XML tests, original package hashes,
  six inputs/exports/probes/PDF images, vectors and per-cell text lines/row pitches,
  mechanism report with counterevidence. Existing fonts/styles/content preserved.
- Tests: deterministic bytes; non-width XML and all other package payloads identical
  across each family; correct widths; unmerged topology; all expected text retained.
- One sequential six-export real WPS set, empty process probe before every case;
  own-instance release only. No taskkill/preferences/user document closure/retry.
- Acceptance is causal evidence: measure outer/column boundaries, per-cell line
  counts and row pitches, establish whether narrower grids wrap. Text retention100%,
  one page, all non-width conditions equal. No F2/product-safety claim from controls.
- Stop immediately on non-width XML/package differences, missing text, unexpected
  page count, unsafe process, export failure or ambiguous cell attribution; preserve
  raw evidence without tuning. Do not recommend deleting allowance without a later
  original-five product safety plan. Evidence-only PR requires tests/Ruff/diff,
  independent image review and six green CI; implementation agent never merges.

## Stage21: isolated native image-paragraph indentation mechanism

- Dependency/base: exact merged main139dbd1ad0180bf2cecc5a9bd5b10f963501155d;
  branch experiment/image-paragraph-indent in new fidelity-image-indent worktree.
  Stopped Stage20 and frozen6/10/12 stay untouched; no product edits.
- Scope: six synthetic DOCX controls C0/N0,C40/N40,C80/N80 representing figure
  horizontal offsets0/40/80CSSpx, old no-indent vs native left0/600/1200twips.
  Reuse accepted report chart paragraph/image/package; add identical BEFORE and
  FOLLOWING text paragraphs for coordinate controls. Only w:ind/left may differ.
- Deliverables: deterministic builder, focused package/XML tests, source/input/
  output hashes, six PDFs/PNGs/probes/version/coordinates, mechanism report.
- Required tests before WPS: deterministic ZIP bytes, image/media and all package
  parts invariant except document XML; after removing ind every variant XML equal;
  image extent/content and control texts same. No converter/browser/scorer changes.
- One sequential six-export WPS set, empty process probe before every case,
  own-instance release only; no taskkill/preferences/user documents or retries.
- Acceptance: C cases image relative x0; N0/N40/N80 relative x0/30/60pt, error≤.10pt;
  all image y/width/height and BEFORE/FOLLOWING y within.05pt of C0, same one page,
  all control text and one image present. No SSIM/product-safety claim.
- Stop: extra XML/package change, text/image/page loss, failed geometry, unsafe
  process/export; preserve raw, no tuning. Evidence-only commit/push/PR after
  focused/Ruff/format/diff and primary image review; six CI green before primary
  merge; implementation agent never merges. Product integration is a separate plan.

## Stage22: bounded standalone figure image indentation

- Dependency/base: Stage21#171 six green and merged exact main
  6e1b237695525889f4019a69b28b4887ae316375; branch fix/docx-figure-image-indent.
  Stopped20 and frozen6/10/12 untouched. Plan first, then negative XML test.
- Scope: only newly created image paragraph with direct eligible figure holder:
  after existing apply_paragraph(list_item=True), set measured _left_offset native
  left_indent. All other paragraph styling, picture size/content and p/div/section/
  body/list/table paths unchanged. No general container/image-layout rewrite.
- Eligibility: browser measured body/figure boxes, finite nonnegative offset,
  static normal-flow LTR left alignment, one direct image plus optional plain
  figcaption/whitespace, no author auto/negative margins/effects, no ancestor list/
  table/nested figure. Measured author margins allowed; no hardcoded40px.
  Image must fit remaining page width. Missing browser/boxes, complex/wide/nested
  cases preserve old behavior (fail closed), no speculative fallback.
- Tests: original chart XML negative then left600; default/author0/40/80px,
  absent browser/boxes, wide/complex/nested/list/table negatives, other holders
  unchanged. Related HTML/fidelity/Ruff/format/diff.
- FIRST hard gate offline original-five with archived browser snapshots and original
  ZIP metadata fixed (no payload substitution): report only real chart paragraph
  adds w:ind left600, all other XML/parts identical; four other full DOCX bytes
  identical. Any deviation stops before WPS.
- If passed, ONE original-five safe WPS set with per-case empty process/version
  gates, own-instance release, no taskkill/preferences/user-doc closure/retry.
  chart relative body x30±.10pt, dimensions240×120 unchanged, chart/caption/following
  y within.05pt; same pages/semantics1, every page and aggregate SSIM nondecreasing,
  report page1 strictly improves, other four pixels identical. Preserve hashes,
  raw PDFs/DOCX/PNGs/probes/versions/JSON and explicit remaining strict failures.
- Stop on unproven eligibility, extra XML/package changes, unsafe/export failure,
  text/geometry/page/semantic/per-page/aggregate regression or no benefit; preserve
  raw without tuning. Successful English Conventional Commit/push/PR requires
  primary independent XML/image review and six green CI before primary merge;
  implementation agent never merges.

## Stage23: isolated print-margin quantization mechanism

- Dependency/base: exact merged mainab96820f1423131c68f516aa6c1d342b0d683c7d;
  new worktree fidelity-page-margins, branch experiment/print-margin-quantization.
  Preserve Stage20 and frozen6/10/12; no converter/scorer/fixture/baseline edits.
- Four fixed references: A4/Letter × default(no CSS margin, render API10mm) or
  explicit @page margin12mm with API10mm. Body8px, one full-width color bar,
  ANCHOR text, fixed near-width text (40 A-space tokens) and45 fixed lines at
  17.25pt line-height for wrapping/pagination diagnostics. No input tuning.
- FIRST browser-only gate: raw PDF stream transforms and geometry must corroborate
  predeclared content-left floor(mm*96/25.4)*.75 +6pt for each reference, ≤.10pt;
  preserve page sizes/bar/char positions/hashes/version/raw exports. If formula
  fails any reference, stop with negative evidence, NO WPS and no fitted constants.
- Conditional eight DOCX controls: each reference precise-mm vs floor-CSSpx margins,
  same page size/body inset/text/font/line-spacing; pair differs only pgMar.
  Deterministic package/XML tests, source/input hashes, literal text retained.
- One safe sequential eight-export WPS set only after browser gate/tests; per-case
  empty-process/version probes; own instance only, no taskkill/user documents/
  preference changes or retries. Measure left/right bar/text bounds, paper size,
  all line breaks/page assignment/text completeness. Quantized left error≤.10pt;
  any wrap/page/text regression forbids product-safety conclusion. Right/paper
  differences explicitly separated, not silently corrected by margin changes.
- Deliverables: bounded runner/tests, four HTML/browserPDFs and conditional eight
  DOCX/WPSPDFs, images, versions/probes/hashes/rawgeometry, mechanism report with
  counterevidence. No original-five product/F2 claim. English Conventional Commit,
  push evidence PR only when verified/reusable; primary diff/image review plus six
  green CI before primary merge; implementation agent never merges.
- Stop on unsupported browser formula, unapproved XML difference, unsafe/export
  failure or missing text. Preserve raw evidence without tuning/retry. Failed
  verified preflight may be evidence-only PR; no WPS or product recommendation.

## Stage26: isolated vertical-merge continuation width mechanism

- Dependency/base3086f60def5fe46c4c353f0c6d5f766c23e8eeb2; new clean branch
  experiment/merged-continuation-width/worktree fidelity-merged-width. Stage25
  and every frozen worktree untouched. Plan first; no converter/source edits.
- Sole candidate: accepted original contract payment table(second body table),
  second row's two vMerge continuation tcW2633→710/2729twips, matching grid columns.
  No synthetic alternatives, margin/grid/other property/content changes.
- FIRST ZIP/XML hard gate: only those two attributes differ, physical cell/merge
  identities asserted; all other package payloads identical and deterministic ZIP
  bytes. Preserve source/candidate SHA and focused tests before WPS.
- Then ONE safe candidate export vs accepted same-WPS baseline12.8.2.18913:
  empty-process probe, own-instance release/no taskkill/preferences/user-doc closure.
  Record native table rules/row pitches/merged header image/each cell text and
  wrap/full contract semantics/layout/downstream coordinates/pages/hashes/version.
- Acceptance: every semantic component1, text complete, same page count, no new
  wrap/clipping, row pitches unchanged, downstream y within.05pt, table boundary
  errors no worse, SSIM≥.8492. If all pixels/geometry identical, report only no
  visible effect on this WPS version, not product fix or margin safety.
- Stop on extra XML, version/unsafe/export failure or any text/geometry/page/
  semantic/score regression; preserve negative evidence, no tuning/retry or margin
  combination. Deliver deterministic runner/tests/raw DOCX/PDF/PNG/JSON/report.
  English evidence-only commit/push/PR only verified reusable evidence, primary
  XML/image review and six green CI before primary merge; agent never merges.

## Stage28: alignment-aware independent horizontal-margin acceptance

- Dependency/base d0dbb48efa689190d52443551d57213b20d53eab, new worktree
  fidelity-aligned-margins/branch fix/docx-alignment-aware-print-margins. Stage27
  passed=false and all raw/stopped worktrees frozen unchanged; not retroactively
  reclassifying that failed result. Persist this independent plan first.
- Reuse SAME Stage27 product code/default37CSSpx and exact runtime/CSSOM qualification,
  not new margin values/inputs/SSIM thresholds. Report remains missing-CSS failclosed.
- Offline all-five exact inverse: four pgMar left/right687→675; only additional
  two contract table[1]/row[1]/gridcol0,3 vMerge continue tcW2633→2639, exact grid/
  identity/formula; all other document bytes/parts same; report full DOCX byte same.
- PREDECLARE image semantics from source computed CSS + DOCX jc before WPS. Left
  requires consistent left/start source and jc=left, stable image/body-relative x;
  center requires consistent CSS center +jc=center, symmetric pgMar and no added
  left/right/first-line/hanging indent: absolute center and content-midline residual
  change≤.05pt, size/y stable, browser center error no worse. Unknown/contradictory/
  asymmetric/indented center rejected, never inferred from observed pixel success.
- Tests: center/left positives and asymmetric/indent/unknown/contradictory negatives,
  identity/CSSOM recursive/import/error/mode, package allowlist negatives; related
  HTML/fidelity/Ruff/JS/format/diff. Product values identical to frozen Stage27.
- After offline gates/tests, NEW ONE complete-five safe WPS set, empty process/
  version probes, own-instance release/no user docs/preferences/taskkill/retry.
  All prior semantic1/text/exact line+page assignment/pages/paper/y/left≤.10/right
  no-worse/per-page+aggregate nonregression and manual+contract improvement remain.
  Report all pixels same; contract relative boundaries/header/pitch/downstream y
  invariant; images use only above predeclared alignment-aware gates.
- Deliver source/output hashes/current qualifications/XML audit/rawPDF/DOCX/PNG/
  geometry/report explicitly distinguishing Stage27 stop from Stage28 independent
  acceptance. Strict F2/exceptions separate, no universal-browser claim.
- Stop on qualification/XML/semantic/geometry/score/flow failure or no double benefit;
  preserve raw uncommitted, no product PR/tuning/rerun. Only success English commit/
  push/PR; primary independent diff/image review and all six green CI before primary
  merge. Implementation agent never merges; frozen worktrees untouched.

## Stage29: horizontal separate-cell spacing mechanism

- Status: primary approved before implementation; source/XML preflight passed;
  the single set STOPPED at H2-N. Exact dependency/base: merged main
  810f9e3ccb7ffd8dc0b37f3d3651ba6c0d07f05a (#175 six green); clean isolated
  fidelity-cell-spacing / experiment/horizontal-cell-spacing. All frozen failed
  stages remain untouched. Same continuing implementation agent; primary reviews
  diff/images/CI and merges only after six green jobs.
- Scope: evidence-only borderless two-column, one-row synthetic HTML, no converter,
  original-five fixtures/baselines/thresholds or product behavior changes. Fixed
  H=0/2/4CSSpx, vertical border-spacing=0, two200px border-box cells, padding12px
  left/right and0 top/bottom, no border, body8px, Consolas12pt, line-height18px,
  no author row-height. Table fixed widths400/406/412px (=400+3H) preserve exact
 200px cell boxes. Text BEFORE, LEFT, RIGHT, FOLLOWING; no other content.
- Three browser references, SAME current-main converter baseline for each H;
  preserve its existing grid/column allowance rather than adjusting it. Six fixed
  DOCX inputs H0-C/H0-N/H2-C/H2-N/H4-C/H4-N: C is unmodified main output; N ONLY
  inserts table-level tblCellSpacing w:type=dxa,w:w=0/30/60twips. No indent/padding/
  grid/row-height/border/font/paragraph/margin changes to make spacing fit.
- Before WPS: current Edge157.0.4341.60/browser identity and WPS12.8.2.18913 required;
  collect source DOM/CSS and browserPDF geometry. Fixed CSS targets relative to
  BEFORE body anchor: LEFT9/10.5/12pt, RIGHT159/162/165pt for H0/2/4, tolerance.10pt;
  cell width200px and table width400+3H within.02px, one row/one line per cell.
  If references do not corroborate these declared inputs, stop, do not resize them.
- XML/package hard gate: pairwise ONLY that one tblPr/tblCellSpacing child differs;
  removing it reproduces baseline document.xml full bytes and every other ZIP
  payload identical. Deterministic package tests, exact0/30/60 values, no existing
  row/table spacing exception, unchanged grid/row properties/text/media. Capture
  source/browser/baseline/candidate SHA and actual git HEAD. No original-five run.
- ONE sequential safe WPS export set, fixed order H0-C,H0-N,H2-C,H2-N,H4-C,H4-N;
  empty process/version probe before EACH case, own-instance release only; no
  taskkill/preferences/user document closure/retry. Stop prevents remaining cases
  from exporting; record them as not-run, never resume/tune the set.
- Pre-register horizontal diagnostic: N−its C LEFT increment expected0/1.5/3pt,
  RIGHT increment0/3/6pt, each error≤.10pt. Also report absolute source-target errors
  (including the unchanged legacy column allowance); do not remove an inherited
  residual or claim exact full CSS mapping from differential success.
- HARD no-coupling/retention gates: same one page, literal BEFORE/LEFT/RIGHT/
  FOLLOWING all retained once, cell line counts1, pairwise cell text top/baseline,
  row height and FOLLOWING top change≤.05pt; bar/borderless cell geometry when
  observable and all x/y bboxes saved. H0 explicit-zero must be pixel-identical
  to its C. Source H cases must have invariant row height/y (vertical spacing0).
- STOP immediately on unexpected XML, source-preflight mismatch, unsafe/version/
  export or text/wrap/page anomaly, any y/row/FOLLOWING coupling>.05pt or failed
  horizontal increment gate. Preserve raw, no offset/indent/half-spacing variant,
  productization or threshold/input changes and no WPS rerun. Negative geometry
  is a mechanism failure, not repaired by changing row-height or global column
  allowance. A verified bounded negative report can be evidence-only PR after
  primary review; incomplete/not-run cases explicitly listed.
- Deliverables after approval: narrow runner, deterministic XML/package and gate
  tests, three original synthetic HTML/browser references and six fixed DOCX,
  actually exported PDF/PNGs, process/version/probe/rawgeometry/line counts/hashes,
  observed outcome/counterevidence/report. Focused tests, full Ruff/format/diff;
  English Conventional Commit/push/evidence PR only when reviewed/verified.
  No claim that original contract reaches strict F2 or that tblCellSpacing is a
  safe product mapping; any integration requires a separately reviewed stage.

## Stage30 PLAN ONLY: fee-body paragraph-mark font hypothesis

- Status: read-only diagnosis/plan, awaiting primary review; NO implementation,
  tests, new browser rendering or WPS export. Exact main dependency/base
  5a1137b3a830011cb765197f5fbb450fb8a616d0 (#176 six green), clean isolated
  fidelity-contract-audit / docs/contract-body-causal-audit. Frozen stages untouched.
- Diagnosis is a hypothesis, NOT an established major cause. Fee-body fixed raster
  region x30..770px, y395..465pt at800px width has SSIM.5516. Browser baselines for
  first-column 签约/验收/质保 are411/434.25/457.5pt; accepted Stage28 WPS baselines
 413.09/437.09/461.09pt. Filled-border/stroked-border center conventions give source
  body boundaries394.874984/418.124983/441.374982/464.624981pt; WPS395.81/419.81/
 443.81/467.81pt. Row center=(adjacent horizontal border centers)/2. PDF baseline=
  page.height minus first matching character matrix[5], not glyph bbox top.
  Source baseline-minus-row-center is4.50pt in each row, WPS5.28pt: constant+.78pt
  remains after separating known23.25vs24pt pitch. This does not prove mark-font
  causality; asymmetric paragraph padding and renderer metrics are countercauses.
- NEW trace: all12 ordinary body cells have one paragraph, visible run rFonts
  ascii/hAnsi/eastAsia/cs=Microsoft YaHei and size22(11pt), but no pPr/rPr.
  docDefaults retains theme minorHAnsi/minorEastAsia fonts; theme minor Latin is
  Cambria, eastAsia empty. Missing explicit mark font does not prove the effective
  rendered mark font; only a native experiment can falsify its layout influence.
  browser_defaults changes pPr defaults, not rPr fonts; apply_run styles visible
  runs, apply_paragraph does not synchronize mark rFonts. No font-size rounding
  adjustment, glyph replacement, line shift or empirical offset is proposed.
- Fixed control: current-main committed Stage28 contract converted.docx,
  SHA256 ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f,
  with its accepted WPS12.8.2.18913 PDF and source browserPDF. No baseline re-export.
  Sole candidate P adds pPr/rPr/rFonts to EXACTLY table[1](second body table),
  tr[2..4], physical tc[0..3], sole p[0]:12 mark-font nodes. Each new rFonts has
  ONLY ascii/hAnsi/eastAsia/cs=Microsoft YaHei copied from that paragraph's common
  visible run font. No sz/szCs/color/bold/lang/position/spacing or run property.
- XML/package hard gate before WPS: assert exact target topology/count12, no body
  merge/span, no preexisting paragraph-mark rPr, common visible family/size22 and
  expected baseline SHA. Inverse remove precisely the12 new pPr/rPr containers
  and reproduce ORIGINAL document.xml full bytes; all other package payloads
  identical, deterministic candidate bytes. No styles.xml/theme/font package,
  visible run, row height/AT_LEAST, vAlign, padding, border, grid/column allowance,
  continuation width, margin, flow boundary or original HTML edits. Any deviation
  stops; no broad matcher or fallback patch.
- After approval: focused positive/inverse/invalid-target/extra-property tests,
  same-file schema/package checks, full Ruff/format/diff. Record immutable source/
  candidate/PDF hashes, code/base/version and raw char/rule geometry. This is
  evidence-only; no product conversion code or original-five re-export.
- ONE safe candidate WPS export only, compared to cached accepted baseline with
  same12.8.2.18913 version; empty process probe before launch, own-instance release
  only, no taskkill/preferences/user-document closure/font install/retry. Unsafe,
  version mismatch, export failure or text/page anomaly stops immediately.
- Independent conservation gates: all visible text and line/page assignment same,
  same one page, semantic components1. Row boundaries/pitches and all table rules
  within.05pt; visible glyph x within.05pt, normalized PDF font family unchanged
  and PDF font size within.005pt; header and every character outside fee body x/y
  within.05pt (thus downstream unaffected). This explicitly refuses row-height or
  paragraph-spacing relief as evidence for mark-font causality.
- Pre-registered positive mechanism effect: each first-column body-row baseline
  offset error relative to source row-center target4.50pt reduces by≥.20pt from
  baseline+.78pt; three candidate-minus-control baseline shifts agree within.05pt.
  Full contract SSIM≥.8644 and fixed unaligned fee-body raster SSIM>.5516 using
  repository grayscale scorer/source raster window; no source/target image shifts,
  crop optimization, threshold changes or alignment. A detected effect is not a
  guarantee of reaching strict F2.90 or a safe five-case product implementation.
- Zero influence classification: pixel-identical output plus all char/rule geometry
  within.05pt means bounded negative evidence; do not claim this is the main cause
  or a product repair. Any conservation regression, measurable but non-positive/
  nonuniform shift or extra package difference is STOP/unsupported, preserve raw;
  do not try another font/size, add offsets, modify padding or reopen Stage10/12/
 19/20/26/29. No second export. Positive or verified zero evidence may get an
  evidence-only PR only after primary independent image/diff review.
- Original-five risk boundary: only this immutable contract candidate is tested;
  other four artifacts and all product code stay unchanged. Even positive mark
  influence requires a NEW reviewed product plan and complete-five semantic/flow/
  per-page/aggregate gates, not inference from this single document.
- Deliverables after approval: narrow builder/assessor/tests, immutable baseline
  references and candidate/rawPDF/PNG/probe/version/hashes/region/row-center audit,
  uncertainty/zero-or-effect report. English commit/push/evidence PR only reviewed;
  six green CI required before primary merge, implementation agent never merges.

## Stage31 READ-ONLY audit: no new isolated fee-body mechanism

- Base/dependency: merged #177, exact main
  9bdc71078dabc7178040740483277154b4ab5ff5; isolated fidelity-fee-rules /
  docs/contract-fee-rules-audit. Frozen experiments and all original inputs,
  thresholds, product code and evidence remain unchanged. No WPS/browser export.
- Scope: existing Stage28 contract browser/WPS PDFs, source CSS and DOCX XML;
  distinguish rule position/color/width, fill, text and raster representation in
  the predeclared x30..770px, y395..465pt ROI at800px page width. This is causal
  triage, not a claim that a new dominant mapping defect has been found.
- Source CSS body cells: border1px solid #555, white background, padding4px8px.
  Native body cells already contain tcBorders sz6/color555555 and no shading.
  Source PDF paints .75pt #555 filled rectangles; WPS paints .72pt stroked rules,
  RGB .333 versus source .3333. Correct native eighth-point width/color mapping
  is present. Different PDF primitive/renderer quantization is not independently
  evidence of a CSS mapping omission; no width/color adjustment is proposed.
- Source body vertical-rule centers34.125/68.625/104.625/172.125/307.875pt;
  WPS33.75/69.25/105.45/173.95/310.40pt. Increasing x residual is consistent with
  already-investigated global column allowance and collapsed-edge conventions,
  not a new mechanism. Row boundaries remain source394.875/418.125/441.375/
  464.625 versus WPS395.81/419.81/443.81/467.81pt: known pitch/vertical residual.
  Stage10/12/19/20/29/30 are not reopened. Theme mark-font hypothesis was directly
  falsified by Stage30 pixel-identical output; continuation widths by Stage26.
- Fixed-ROI diagnostic decomposition (absolute grayscale pixel error, NOT additive
  SSIM attribution): union source/native rule bounding boxes dilated3x3; union
  character bboxes; disjoint categories rule-only/text-only/overlap/other.
  Shares of summed absolute pixel error are39.31%/59.39%/.01%/1.29%; changed pixels
  >20 are5584/8838/2/251 respectively. These masks overlap geometry effects and
  antialiasing; they cannot establish causal improvement from border changes.
  Original unaligned ROI SSIM is.551646; full contract remains.8644 strict fail.
- Visible font family is MicrosoftYaHei in both PDFs; source size10.995 versus
  native11.05pt is documented renderer/size quantization, not an authorized font
  rounding score experiment. White fill matches. Rule/glyph displacement remains
  the measurable loss, but current evidence does not isolate a NEW single cause.
- Deliverable: this negative read-only audit with reproducible mask conventions
  and source trace; no synthetic variants, product patches or experimental PR.
  No focused tests or CI are needed for an uncommitted planning-only note.
  Acceptance is transparent separation of measurement from causal conjecture.
- STOP: insufficient independent mechanism; no new WPS run is authorized or
  warranted. No fixed candidate/safe-export gate can honestly be specified beyond
  already rejected directions. A future stage requires new independent source-to-
  XML evidence and a reviewed Plan with predeclared controls, XML-only allowlist,
  geometry/text/page/semantic conservation and one safe export set. Do not tune
  border width/color, fonts, row pitch, spacing, columns, offsets or thresholds.

## Stage32 PLAN ONLY: conserve padding total, isolate compensation distribution

- Status: awaiting primary review; no implementation/tests/WPS. Exact base
  9bdc71078dabc7178040740483277154b4ab5ff5, read-only fidelity-fee-rules worktree.
  Stage31 remains a negative audit; no prior STOP is reclassified or edited.
- Rechecked frozen STOPs: Stage10 reduced eligible row minimum390->375twips;
  manual pitch20.25->19.5pt but downstream content moved up and whole SSIM
  .8959->.8949, so must-improve/no-regression failed; contract unchanged because
  merged table excluded. Stage12 retained full p->heading margin: contract interval
  improved66->68.64pt (source69) but heading3 moved514.333->517.093 (source512.818),
  whole .8492->.8422/ROI .7798->.7523; newsletter/pdfsource also regressed.
  Stage19 is NOT a failed experiment: isolated widths varied with no wraps/pitch
  change, but omitted merged headers/flow. Stage20 removed global allowance and
  passed package gate, then STOPPED BEFORE WPS because merged/borderless/duplicate
  cell attribution was unproven. None varies padding distribution at fixed total.
- New source trace: contract CSS fee td padding4px top/bottom, border1px collapse,
  vertical-align middle. apply_table converts padding to paragraph before/after,
  then subtracts the entire collapsed bottom-border width from bottom only.
  Accepted fee body12 paragraphs have before60/after45twips, exact line330,
  vAlign center. Source symmetric padding becomes3pt/2.25pt. Distribution alone
  predicts a downward .375pt center bias; existing +.7800006pt baseline-relative-
  row-center residual could partly reflect this. This is a hypothesis, not proof
  or a claim it explains all ROI loss. Row height and font metrics remain separate.
- Dependency/control: immutable accepted Stage28 contract converted.docx SHA256
  ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f, cached same-version
  WPS PDF/browser PDF. Sole candidate changes only second table tr[2..4],tc[0..3],
  sole paragraph spacing before60->53 and after45->52twips, exactly24 attributes.
  Sum105twips remains EXACT per paragraph. This deterministically rounds symmetric
 52.5/52.5 to before53/after52 while preserving total; no alternative rounding run.
  Predicted baseline displacement=(53-60)/20=-.35pt, not an empirical pixel offset.
- Scope excludes row minimum/hRule, line spacing, cell margins/vAlign, visible or
  paragraph-mark fonts, borders/fill, columns/continuations, page margins, headings,
  surrounding flow, HTML/converter/scorer and original-five files. No product fix.
- Offline hard gate after approval: verify exact baseline hash/topology12, current
  before60/after45/line330 exact and center alignment; only24 approved attributes
  differ; inverse restores original document.xml bytes and every other ZIP part
  identical. Deterministic build and rejected-target/extra-difference tests; Ruff,
  format/diff and packaging-metadata test. No WPS if any mismatch.
- ONE candidate WPS export, no control re-export, current12.8.2.18913 and empty
  process/version probe; own instance release only. No taskkill/user documents,
  preference/font changes, retries or new variants. Failed safety/export stops.
- Independent conservation: one page, all text/semantic components1, same line/page
  assignment, rules/row boundaries/pitches within.05pt, all glyph x/font/size and
  chars outside fee-body y within.05pt. No row-height/downstream-flow benefit may
  substitute for these gates. Fee-body row-center uses adjacent rule centers;
  baseline uses character matrix translation as in Stage30, not bbox fitting.
- Required positive mechanism: all three first-column baselines shift-.35pt with
  absolute prediction error<=.05pt, and shifts agree within.05pt. Row-center error
  improves by>=.25pt from+.7800006. Fixed original ROI x30..770px,y395..465pt at800px
  width SSIM must exceed.5516460049 and whole contract must exceed.8644, unaligned
  and uncropped beyond the preregistered window. No strict F2 pass is promised.
- Pixel-identical output and identical geometry classify zero influence, not a
  repair. Any conservation failure, unexpected/nonpositive/nonuniform shift, or
  non-improved scores STOP with raw evidence. No row-height compensation, p-heading,
  width/spacing, font, threshold or padding-total tuning; no WPS rerun.
- Deliverables only after approval: narrow builder/assessor, focused XML/package/
  prediction tests, one candidate/rawPDF/PNG/probe/version/hashes/char-rule audit,
  report of positive/zero/STOP and counterevidence. Other four originals not tested:
  even positive result requires a separately reviewed product eligibility and full
  original-five regression plan. Evidence-only commit/PR only after primary review;
  six green CI before primary merge; implementation agent never merges.

## Stage37 PLAN ONLY: copied-contract native wrap mechanism, two fixed widths

- Await primary review; exact main ab3b548667cabbe8b09b59cc181ffd88b523b2db, isolated
  fidelity-contract-wrap / docs/contract-wrap-mechanism-plan. Frozen Stage34/36/20
  and all prior STOP records stay unchanged; no implementation/tests/WPS yet.
- Dependency: immutable Stage28 contract DOCX SHA256
  ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f, archived browser
  box widths46.328125/47.25/90.3125/180.875px. Stage19 omitted merged headers and did
  not test this tight header; Stage34 ink-bound clearance could not prove no-wrap.
  Stage36 preferred-width-only Plan was stopped as low-value, not rendered.
- Scope is evidence-only native mechanism. Exactly TWO synthetic packages C1/C0,
  retaining the FULL original fee table, rather than transplanting text into a new
  two-column layout. Preserve5rows,4logicalcols,19physicalcells,17origins,2vMerge
  continuations, original colspan/rowspan, ALL original text/runs/paragraphs/styles,
  row min heights, line spacing, padding/borders/fill, fonts and table properties.
  Same original page section/style/theme/compatibility and all non-document parts.
  Body is fixed BEFORE paragraph + copied fee table + fixed FOLLOWING paragraph;
  these two control paragraphs identical between variants. No discretionary text,
  widths, font sizes, indentation or spacing chosen after measurement.
- C1 table subtree matches immutable original after identical serializer/canonical
  namespace treatment. C0 differs ONLY in21 width attributes:4gridCol and17
  non-continuation tcW each minus15twips. Grid710/724/1370/2729->695/709/1355/2714,
  colspan-origin1370->1355 per existing setter, both continuation2639 unchanged.
  Zero allowance uses ceil(CSSbox*15), not a fitted width. No third width, scan,
  .5px candidate, origin-width normalization, row/padding/font adjustment or product.
- Pre-WPS HARD gate after approval: exact source hash/topology/text/font/rPr/pPr/
  row/tcPr matches; complete C1 fee subtree equivalent to original; C0 inverse
  reproduces C1 full document.xml bytes and all non-document parts identical;
  deterministic fullZIP bytes. Fixed controls include no section break/extra style.
  If topology or effective font/size references cannot be retained exactly, STOP
  before WPS. Focused positive/inverse/wrong-topology/font/extra-part tests,
  packaging-metadata, Ruff/format/diff pass before exports.
- This experiment does NOT require pre-certifying wrap from ink clearance: wrap
  is the experimental native-WPS observable. The source-to-synthetic fidelity gate
  above replaces no old rule; Stage34 still failed its distinct preflight and is
  not reopened. Native metrics in C1 must corroborate the copied original before
  accepting C0 inference: all17origins one line, row pitches24pt each within.05pt,
  actual PDF YaHei normalized families/sizes equal cached original within.005pt.
- ONE sequential safe export set C1 then C0, each preceded by empty process/version
  probe for WPS12.8.2.18913. Own instance release only; no taskkill/user documents,
  prefs/font install/retry or cached-original re-export. C1 topology/font/line/pitch
  mismatch stops before C0 export. Export/safety/text/page anomaly stops immediately.
- Measure independently recoverable horizontal/vertical rule SEGMENTS; corroborate
  missing header boundaries with XML merge topology, then assign glyph centers to
  unique cell polygons. Verify character streams only AFTER geometric assignment,
  never text matching to select cells; continuation geometry belongs to its origin.
  Record per-cell matrix baselines, PDF advances and ink bboxes separately. PDF adv
  is reported as observed native data, not assumed CSS line-break algorithm proof.
  Ambiguous polygon/line cluster or unassigned/duplicated char is STOP.
- Required no-wrap result: every original17origin character stream retained exactly
  (explicitly documented PDF whitespace normalization only), every origin still ONE
  baseline cluster (tolerance.05pt); amount header and stage rowspans explicit rows
  in the report. Same one page, row pitch/total table height within.05pt between
  C1/C0, glyph baseline minus table-top within.05pt, BEFORE/FOLLOWING x/y within.05pt.
  Normalized glyph font/size unchanged within.005pt, no clipped/missing glyph.
  No rule/glyph overlap; negative CSS ink-clearance is recorded separately and is
  NOT automatically treated as wrap or discarded to pass a content predicate.
- Predicted rule differential C0-C1=[0,-.75,-1.50,-2.25,-3.00]pt for5vertical rules,
  error<=.10pt, outer span change-3.00±.10pt. All horizontal y/row pitches invariant
  within.05pt; merged header spans correct, unchanged rule segment topology. No
  sourceSSIM or strictF2 acceptance is claimed for synthetic documents.
- STOP on offline mismatch, unsupported C1 metrics, ambiguity, any wrap/pitch/y/
  text/font/page/unsafe/export anomaly or prediction failure. Preserve raw negative
  evidence; no input/threshold/offset/font/width tuning or rerun. Successful two-
  point result would ONLY show this copied table under this WPS version did not
  wrap; original full-contract surrounding flow/pagination and other cases remain
  unvalidated, and no product removal of allowance follows automatically.
- Deliverables after approval: deterministic builder/assessor/tests, complete input/
  output hashes/version/process probes, two actual PDFs/PNGs (or not-run status),
  XML inverse audit, per-origin native metrics/geometry and uncertainty report.
  Evidence-only commit/PR only after primary independent image/diff review; six
  green CI before primary merge, implementation agent never merges. Product or
  original-contract validation requires another reviewed stage.

## Stage38 PLAN ONLY: full-contract fixed zero-allowance validation

- Await primary review. Exact dependency: Stage37#179 six green/merged main
  3ddbc9197753f53d8e1101ef93bdfefc42bcb4ce, clean fidelity-full-contract-width /
  docs/full-contract-width-plan. Frozen Stage34 and other stopped worktrees stay
  untouched; Stage34 preflight STOP is not reversed or reclassified.
- New risk basis: Stage37 copied the ENTIRE fee-table subtree without changing
  typography, merges, padding/borders or row properties. Its native C1/C0 WPS set
  confirmed all17origins single-line, exact widths and invariant24pt pitches at
  the two registered points. This independent native evidence justifies TESTING
  the same candidate in original flow; it does not certify full-contract safety,
  pagination, surrounding tables or any other input. Full-flow gates below are
  new empirical requirements, not inferred from synthetic success.
- Immutable control: accepted Stage28 full contract converted.docx SHA256
  ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f and cached
  WPS12.8.2.18913/browserPDFs. Exactly ONE candidate, original complete document,
  only table[1] four gridCol +17non-continuation tcW @w:w each minus15twips.
  Grid710/724/1370/2729->695/709/1355/2714; first-row middle colspan origin1370->1355
  (not normalized to a new summed width); two continuation2639 unchanged. No other
  cell/parties/sign table, margin, font, pPr/spacing, height, border/fill or flow edit.
- Offline hard gate: verify immutable hash, full5row/4logicalcol/19physicalcell/
  17origin/2continuation topology and exact original target values; exactly21
  attributes; inverse reproduces complete original document.xml bytes, all other
  package payloads and metadata retained; deterministic candidate ZIP. Same width
  arithmetic as Stage37 ceil(CSSbox*15), no fitted constants/width scan. Assert
  copied candidate fee subtree identical to Stage37 C0 table subtree so native
  wrap evidence applies to precisely the same table, including every run property.
  Any mismatch/extra difference STOP before WPS.
- Focused tests after approval: inverse/determinism/all-parts, exact Stage37 subtree
  equality, wrong-topology/font/extra-difference rejection, geometry/score/STOP
  classification; packaging metadata, Ruff/format/diff. No product converter/scorer
  edit, browser render, fixture/baseline/threshold change or other-case export.
- Exactly ONE full-contract candidate WPS export compared to cached accepted
  baseline, no old-contract re-export. Empty process/version probe before own
  instance; same12.8.2.18913 required. No taskkill/user-document closure/global
  prefs/fonts/retry/alternate .5px width. Export/safety anomaly STOP immediately.
- Pre-registered full-document five vertical fee-rule predictions:
  33.75/68.50/103.95/171.70/307.40pt; each error<=.10pt. Differential relative to
  baseline33.75/69.25/105.45/173.95/310.40 is0/-.75/-1.50/-2.25/-3pt. Source rule
  centers34.125/68.625/104.625/172.125/307.875: each absolute source error must not
  worsen by>.05pt and summed absolute error must decrease. No source-x fitting.
- Recover complete rule SEGMENTS and merge topology before glyph assignment;
  source/native stroke caps and rule centers remain distinct. All17origin streams
  match cached original by geometric polygon assignment (text only verifies),
  exactly ONE baseline cluster per origin (tolerance.05pt), no clipped/lost glyph
  or rule crossing. Normalize PDF whitespace explicitly, never discard content.
  Merged-header text, continuation topology and rule segment cardinality unchanged.
- Independent no-coupling: fee horizontal centers347.81/371.81/395.81/419.81/443.81/
  467.81pt within.05pt, all pitches24pt within.05pt, glyph y/baseline and PDF normalized
  font/size unchanged within.05/.005pt; paragraph line assignment unchanged. Every
  character OUTSIDE fee table x/y within.05pt, including total-price/later headings/
  liability/signature rows; same page count1, all original body text/structure/
  formatting/data semantics1. This directly tests original-flow safety.
- Fixed scoring convention: repository _pdf_pages800px, target.resize(source.size),
  original unaligned grayscale SSIM; x30..770px and y int(pt*800/595.92). Body395..470
  baseline.541706667 and total-table348..470 baseline.635591558 must BOTH improve;
  header348..395 baseline.814993303 must not regress (numerical1e-9 only). Whole
  baseline raw.8643611411371483/rounded.8644 must improve to rounded>.8644; no .90
  claim unless measured. Outside-table/later-text residuals must not be hidden by
  whole average. No image registration, shifted crops or threshold tuning.
- STOP on any offline/geometry/content/wrap/height/flow/page/font/semantic/safety/
  export/score gate failure. Preserve raw and state unrun outcomes, no repair to
  font/grid/height/spacing/offset/threshold/input or second export. Pixel-identical
  is zero influence, not success. No product PR follows from a failed experiment.
- Deliverables after approval: narrow full-document builder/assessor/tests, source/
  candidate/inverse/subtree/hash audit, one rawPDF/PNG/process/version/export,
  source/baseline/candidate per-origin/rule/outside-flow measurements and score
  report with residuals. Evidence-only commit/PR only after primary independent
  diff/image review, six green CI before primary merge. Even pass is only this
  full-contract candidate on this host; product eligibility and original-five
  regression require a separately reviewed stage, never blanket allowance removal.

## Stage42 PLAN ONLY: audited applicable-aspect semantic gate

- Await primary review. Exact main b083ae7cb4a95648e9c01c972dd797fc4844689c; new
  fidelity-table-width-schema / docs/table-width-aspect-schema-plan.
  Stage39/40/41 STOP/code/raw stay frozen, unpublished and unchanged. Stage40 report's
  one export is NOT part of this newly registered set; all five require NEW exports.
- Dependency/rationale: Stage37/38 support contract measured widths, not five-case
  product safety. Stage39 lacked clipping metadata; Stage40 collected complete
  metadata and71attr/browser gates but validation source reader fell back to
  cascade because NODE_PATH was omitted. Its first report semantic gate failed
  although DOCX/PDF pixels were identical. Offline diagnosis did not reverse STOP.
- Before ANY browser/WPS work: runner explicitly requires writable workspace
  TEMP/TMP, UTF8, NODE_PATH resolving installed Playwright; record resolved Node,
  Playwright module and Edge executable/version, not ambient environment guesses.
  Node require.resolve('playwright') must succeed in the actual child environment.
  Python browser_runtime must resolve both executables; missing/unknown/fallback
  errors STOP before exports. Do not install/change dependencies or global settings.
- One product variable only: browser measured column width without historical+1px
  for GENERIC qualifying tables. Others retain legacy+1/fallback. No fixture/class/
  filename/text/hash/font-family branch in product. No row height, border, margin,
  font, padding, merge normalization, scorer policy or threshold change.
- Qualification BEFORE capture: seven computed properties transform/zoom/writing-
  mode/direction/overflow-x/overflow-y/clip-path explicitly prove none/1/horizontal-
  tb/ltr/visible/visible/none on table/groups/rows/cells/DOM ancestors. Missing or
  unknown rejects. Static/no float/visible opacity1, no pseudo/nonzero radius;
  direct plaintext/normal whitespace/browser text-lines1, no descendants/images/
  br/nested tables/hidden or clipped shape. Parser document sentinel is not DOM.
- Complete accessible CSSOM/no imports/errors/adopted/shadow/declarative roots;
  collapse and uniform four-sided solid positive same border/color. All real
  boxes finite positive; every logical column measured unspanned witnesses agree
  within1/64CSSpx; colspan box sum within1/64CSSpx, rectangular nonoverlapping merge
  grid/no uncovered holes. Old/new widths fit available page without scale. Unknown
  geometry/metadata ->legacy+1. If reliable helper needs broader layout work STOP.
- Pre-browser tests: each missing seven field/ancestor transform/clip/overflow/
  radius/pseudo/RTL/vertical, malformed boxes/NaN/scale, cascade, separate/borderless/
  mixed/zero border, missing/inconsistent/spanned/ragged/overlap witnesses, complex/
  multiline/nested cases. Positive generic plain and merge cases. Environment gate
  rejects absent NODE_PATH/unresolved Playwright/loader fallback BEFORE WPS. Tests
  assert source-snapshot identity/semantic gate and forbid implicit recapture.
- NEW ONE original-five browser reference set, actual Edge157.0.4341.60, immutable
  source/assets. Reject styled.mode!=browser; capture full seven fields, CSSOM,
  source version/hashes, existing style/box/marker plus pseudo metadata for faithful
  replay. Core values/page pixels/sizes/counts match accepted Stage28 exactly;
  extra fields independently proven, never manufactured onto old caches. Failure
  STOP, no capture retry or metadata extension after set start.
- NEW semantic environment gate BEFORE ANY WPS: baseline AND candidate applicable text/
  structure/formatting/data scores1.0; explicitly N/A aspects use the audited normalized true verdict described below. Use the SAME freshly
  captured browser StyledDocument (runner-scoped injection only, not product
  scorer edits). Persist/replay styles/boxes/page/summary-marker/pseudo properties
  with exact annotation/source hash checks. Reader must consume this browser-mode
  snapshot; if loading a different source or fallback/capture is attempted STOP.
  Native assessor reuses verified snapshot; no hidden second source-browser set.
- Exact offline package allowlist71attrs: contract4grid+17noncontinue tcW -15,
 710/724/1370/2729->695/709/1355/2714, merged origin1370->1355, continuation2639
  unchanged; manual3grid+12tcW -15,1333/1909/1899->1318/1894/1884; pdfsource FIRST
  table5grid+30tcW -15,1290/810/810/810/810->1275/795/795/795/795. Other tables same.
  Report/newsletter fullZIP bytes identical. Full XML inverse and other parts
  identical, old path replay reproduces accepted ZIP. Contract matches Stage38.
- All five eligibility expectations verified, not encoded as product identities:
  contractfee/manualopts/pdfsourcegrid qualify; report separate/borderless+missing
  CSS and other borderless/separate tables remain conservative. Reliable cached
  rule segments/merge polygons assign17/12/30origins, including repeated numbers;
  character streams verify after geometric assignment, never select a cell.
  Per-cell one-line counts and manual Windows10/11 retained as explicit wrap risk.
- Run HTML/table/roundtrip/packaging/geometry/env tests, Ruff/format/JS syntax/diff;
  require source/browser/semantic/71attr/all-parts/polygon gates before WPS.
  The native command repeats environment/module/snapshot preflight before first
  probe, so a shell missing NODE_PATH cannot begin a partial native set.
- Then ONE NEW sequential safe five-case WPS set (report,contract,newsletter,
  manual,pdfsource), per-case empty processes/version12.8.2.18913, own instances
  only. No taskkill/user documents/global preferences/fonts/old-baseline export,
  retry/alternate allowance/input. Any anomaly stops, remaining explicitly not-run.
- Gates: report/newsletter all-page pixels identical; every case same text/semantic
  components1/page count/line-page assignments; all affected origins same text/
  one-line/font/size, row/pitch/glyphy/outside-table glyphx within.05pt. Images and
  summary marker unchanged. Rule differential-k*.75pt±.10, complete merge topology,
  no clipping. Contract repeats ALL Stage38 gates and exact candidate subtree.
- EACH page/aggregate no-regression vs report.9398[.9007,.9789],contract.8644,
  manual.9027,newsletter.9293,pdfsource.9190[.9123,.9258]. Contractwhole rounded>=.8719
  and >.8644; fixed body/header/tableROIs>=.595552511/.882552033/.693273755
  (numerical1e-9). Manual/pdfsource retain strict.90 aggregate; contract remains
  explicit strictfail if <.90. No overall mean or exception waives other gates.
- STOP on environment/source-reader fallback, metadata/eligibility/source/browser/
  semantic/package/polygon/wrap/flow/page/pixel/per-page/ROI/whole regression.
  Preserve raw, no field/qualification/threshold/font/row/offset/allowance tuning or
  second set; no product PR on failure, no fixture-specific narrowing.
- Deliverables after approval: narrow helper/collector/tests, environment-gated
  reproducible preflight/native assessor, full new-five raw/browser/DOCX/WPS/version/
  probe/hash/semantic/per-origin/per-page report. English commit/push/product PR
  only after primary independent diff/image review; six green CI before primary
  merge, implementation agent never merges. Evidence limits remain explicit.

- Stage42 PRIOR offline audit of all five immutable Stage28 semantic-fidelity.json
  schemas: report/contract/manual/pdfsource have text/structure/formatting/data
  score1 with corresponding raw verdict true; newsletter has three scored aspects
  and data EXACTLY {status:"not applicable"}, no raw data verdict key. All five
  animations are N/A and have no raw animation verdict key. This source audit is
  read-only and was completed before this Plan; no capture/export was needed.
- The Stage41 literal four-score predicate falsely rejected newsletter despite
  raw passed=true; Stage41 is frozen STOP_BEFORE_WPS, not recovered by this Plan.
  Its three partial browser captures are NOT reused or counted in Stage42.
- Exact Stage42 semantic predicate, runner-only: require result success, groupA,
  raw passed=true and every PRESENT raw verdict true. Text/structure/formatting
  MUST be applicable with numeric score1.0 AND explicit matching raw verdict true.
  Data with numeric score MUST equal1.0 and raw verdict.data=true. Data may instead
  be EXACTLY {status:"not applicable"} with no score and raw verdict.data absent
  or true; runner records effective_verdict.data=true with reason "explicit N/A"
  while preserving raw absence. Explicit false, mixed score+N/A, unknown status,
  missing aspect, unknown/false verdict or non1 score always rejects. Animations
  in this HTML group must match the audited explicit N/A shape; record normalized
  true separately, never invent score1 or modify scorer/historical JSON.
- BEFORE any new browser/export, deterministic offline schema audit must pass all
  five accepted raw semantic files under that predicate. Tests cover applicable
  perfect, newsletter dataN/A/raw-absent, N/A/rawtrue, N/A/rawfalse, missing/unknown
  status, contradictory score, non1/missing scores/verdict, wrong group, rawpassed
  false and environment/reader fallback. Persist raw schema/hash and effective
  verdict/reasons, preserving the distinction between actual score and N/A.
- Only after that audit and tests may the NEW single original-five browser set
  start. Require all baseline/candidate applicable aspects perfect and every
  explicitly N/A effective verdict true on the same fresh source snapshot before
  ANY native export; native process repeats those gates. All seven metadata,
 71attr/inverse/polygon/source-pixel/per-page/flow/contractROI/native-single-set
  requirements above stay unchanged. No Stage40report or Stage41capture reuse,
  threshold/eligibility/input adjustment, semantic reader recapture or product PR
  on failure. This registered N/A schema handling is not post-hoc continuation.

## Stage43 PLAN ONLY: merged-contract row-minimum accounting experiment

- Await primary review. Exact main551fe7fad79d6b96423caca73e816b4ab35aebc7, fresh
  fidelity-contract-row / docs/contract-row-mechanism-plan. Evidence-only; no product,
  fixture/threshold/baseline changes or new render/test/WPS yet. Old Stage10/12/
  32STOPs remain unchanged. Stage10 excluded this merged contract, so did NOT test it.
- Control: committed Stage42 full contract candidate.docx SHA256
 760bb182bf74f3b491ed103f8d56fc5089d99f1c22bf4ff6f8226fcd1d1dbab1, its accepted
  WPS12.8.2.18913 PDF and immutable source browser PDF/snapshot. Current whole.8719;
  source five row pitches23.25pt vs native24pt. Source boundaries348.375/371.625/
  394.875/418.125/441.375/464.625; native347.81/371.81/395.81/419.81/443.81/467.81pt.
- Source trace: every computed tr is31px tall (22px line+8px vertical padding+
  1px collapsed border), natural CSS with no author height. apply_table requests
 465twips=23.25pt AT_LEAST and native adds nominal.75pt border accounting, consistent
  with Stage9's unmerged mechanism. Ordinary cells have exact330+before60+after45
  =435twips(21.75pt); adding two .75pt border extents reaches23.25pt. This is near
  a content minimum, not proof it will shrink; effective WPS metrics may dominate.
- Both outer header rowspan origins have exact line390 (19.5pt), not330: existing
  _measured_pitch uses62px box minus10px padding/border =52px, round(52/22)=2,
  pitch26px. This unrelated line-pitch inference is recorded but NOT changed.
  Its paragraph-plus-spacing24.75pt/border26.25pt fits across two predicted rows
  (46.5pt); empty continuation paragraphs may still affect native constraints.
- Sole candidate: second table's five trHeight @w:val465->450, hRule=atLeast
  UNCHANGED. Formula=(31px source row minus1px collapsed nominal border)*15twips.
  Exactly FIVE attributes. No exact-height coercion, hideMark, line/font/padding/
  mark/merge/grid/width/margin/paragraph/flow changes, alternate heights or offsets.
  All Stage42 corrected widths preserved. Candidate may have zero/partial effect;
  do not lower height further if contents force it. Official atLeast is a minimum:
  https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.heightrulevalues?view=openxml-3.0.1
- Offline hard gate after approval: exact immutable SHA/topology5rows/19cells/
  17origins/2continuations; five original465/atLeast, borders6eighth-points, unchanged
  pPr330(or390 for two rowspan origins)/before60/after45; expected source31px boxes.
  Five-value inverse restores complete original document.xml bytes; every other
  package payload and metadata same; deterministic package. Wrong row/height/rule,
  extra content/style/part differences STOP before WPS. Content/rowspan constraints
  above must be auditable; no claim static arithmetic certifies WPS no-clipping.
- Focused inverse/determinism/negative-XML and prediction/STOP tests, relevant table/
  semantic/environment/packaging tests, Ruff/format/diff before native work. Use
  verified Stage42 source snapshot with exact hash/annotations for semantic scoring,
  applicable perfect/N/A normalized gates, no cascade fallback or implicit capture.
  Explicit Node/Playwright/workspaceTEMP/UTF8 environment check before ANY WPS.
- ONE safe full-contract candidate export against cached baseline, same12.8.2.18913,
  empty process probe/own instance release only. No browser or baseline re-export,
  taskkill/user documents/preferences/font install/retry. No other-case export.
- Registered row mechanism prediction: anchored top347.81±.05pt; five pitches
 23.25±.05pt, total116.25±.10pt; horizontal centers347.81/371.06/394.31/417.56/
 440.81/464.06±.10pt. All vertical x/width/rule segments unchanged except their y
  extent. Body glyph baseline shifts rows2/3/4 predicted-1.875/-2.625/-3.375pt,
  error<=.10pt; header single-row cells shift-(r+.5)*.75, two-row origins-.75pt.
  If rows do not follow that mechanism, classify zero/content-dominated or STOP,
  never force exact/another minimum/paragraph relief to obtain predicted height.
- Strict content/geometry: same page1, all17origin streams single-line, effective
  PDF fonts/sizes/advances/ink heights unchanged, no missing/clipped/cross-rule
  glyph; merge segments and all horizontal x positions preserved. Every character
  before table unchanged x/y≤.05; every downstream character x unchanged≤.05 and
  y shift MUST uniformly equal-3.75±.10pt, relative interparagraph intervals stable
  within.05pt. This tests real flow rather than silently accepting unrelated moves.
- Counterevidence registered: price baseline492.409 vs source488.99998 predicts
 488.659(-.341 error) after reduction. But heading3 error+1.49->-2.26 and heading4
  -1.51->-5.26pt become WORSE; a local table gain may fail global fidelity as in
  Stage10. This is not a preclaimed repair. Price absolute source error must reduce
  by>=3pt; report ALL later anchor errors including overshoot, not just improved one.
- Positive acceptance requires table body395..470 and total348..470 SSIM BOTH
  improve over Stage42.595552511/.693273755; header348..395 not below.882552033;
  later_text470..640 not below.755426525, plus whole rounded>.8719. Fixed x30..770px,
  int(y*800/595.92), repository800px grayscale/target resize, no alignment/ROI search.
  Applicable semantics perfect/N/A recorded, no page/line/content regression. The
  downstream counterevidence may cause this gate to fail; preserve that result.
- STOP on any offline/env/safety/export, mechanism/flow/content/clipping/page/
  semantic/ROI/whole failure. Pixel-identical and geometry identical =>bounded
  zero influence. Mixed or score-regressing effects remain negative evidence;
  no threshold/height/offset/font/boundary tuning or second export/product PR.
- Deliverables after approval: bounded builder/assessor/tests, source/inverse/hash/
  constraints audit, single rawPDF/PNG/probe/version/export, per-origin/rule/anchor
  coordinates and score report with counterevidence. Only independently reviewed
  reusable evidence may be committed/pushed as evidence PR; six green CI before
  primary merge, implementation agent never merges. Product/full-five separately
  reviewed only if new evidence supports it, never inferred from a local gain.
