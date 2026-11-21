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
