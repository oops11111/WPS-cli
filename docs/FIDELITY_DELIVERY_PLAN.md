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
