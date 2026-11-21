# Stage 7: spacing after horizontal rules

Base: `f1ca25fe0da8af4dfe5701f3d5d50b86c921714d`. The local repair is accepted;
the complete manual still fails strict F2 layout (0.8959 < 0.90).

Only the immediate following block consumes a horizontal-rule spacing boundary.
Previously the mapper subtracted the rule's after-spacing from the following
paragraph's before-spacing, although native DOCX already uses adjacent spacing's
maximum ([OOXML spacing documentation](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.spacingbetweenlines?view=openxml-3.0.1)).
No general margin algorithm, text indent, fixture, threshold or baseline changed.
Tables clear the boundary and ordinary paragraph sequences retain their behavior.

## Original-input evidence

The original `fixtures/fidelity/manual.html` SHA-256 remains
`8d8c5d540e4cd3325efdd081ee5941807850722daacb5de7caafc02c5643bf33`.
Raw input, DOCX, browser/WPS PDFs, render/probe JSON, hashes, computed styles and
comparison images are in [the evidence directory](../artifacts/manual-rule-spacing-20261121/).
The runner is `scripts/manual_rule_evidence.py`; it uses only the original manual
case and refuses to run while an existing WPS instance is present.

Environment: Edge 157.0.4341.60; WPS 12.8.2.18913. The missing Noto Sans CJK SC
fallback remains recorded; it does not establish which effective font rendered.
Browser/WPS rendering and original Stage 4 baseline are compared without alignment
or resampling, using the fixed region `[40,495,760,625]` on the 800px-wide page.

| Measure | Before | After |
| --- | ---: | ---: |
| Whole-page SSIM | 0.8872 | 0.8959 |
| Fixed lower-region SSIM | 0.7294 | 0.8171 |
| Third heading vertical error (px) | 8.92 | 1.83 |
| Question vertical error (px) | 8.99 | 1.89 |
| Answer vertical error (px) | 8.83 | 1.90 |

All six local gates pass: whole/region SSIM improve, each measured position
improves, the first 495 WPS image rows are byte-identical, page count stays 1,
and text/structure/formatting/data remain 1.0. Independent review confirms the
third section and Q/A move toward the browser without earlier-content movement.
Remaining approximately 2px vertical offsets and table/font/stroke differences
are visible. This is a bounded improvement, not complete manual fidelity.
Decision 10's existing 0.88 exception remains separately recorded; neither it nor
the strict 0.90 requirement was changed.

## Validation

- Negative XML reproduction: five tests, four failing subcases before repair.
- Five focused rule-spacing tests pass.
- 84 related tests pass in 34.593s (four existing skips).
- Ruff check and format pass (570 files); `git diff --check` passes.
- Real WPS evidence: all six predeclared local gates pass; strict F2 remains failed.

CI must pass all required jobs before merge. Stage 6's stopped worktree and its
three raw marker experiments remain untouched and are not part of this change.
