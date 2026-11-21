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
