# Stage 4: five existing HTML-to-DOCX WPS cases

This stage records evidence, not a product repair. Measurements used main
`95f2947c2e10780067ab30749b8a4c1bf474f30b`, WPS Writer **12.8.2.18913**,
Edge **157.0.4341.60**, and the five original fixtures/assets. No input, conversion
implementation, configured baseline or tolerance was changed.

## Results: three distinct columns

The existing F2 layout score is the mean of paired-page SSIM values (including
missing-page penalties), not a requirement that every individual page exceeds
0.90. The raw page values are retained so the mean cannot conceal a weaker page.
All five cases have matching browser/WPS page counts and applicable semantic
text, structure, formatting and table-data scores of **1.0**.

| Case | Strict F2, aggregate layout >= 0.90 | Existing decision-10 rule | Font/input/comparability limits |
| --- | --- | --- | --- |
| A-report-docx | **Pass**, 0.9224; 2/2 pages: **0.8826**, 0.9622 | No exception | Original `print.css` reference is missing; Noto Sans CJK SC missing |
| A-contract-docx | **Fail**, 0.8491; 1/1 page | Eligible known deviation: layout only, >= 0.84; **not** a strict F2 pass | Noto Sans CJK SC missing; glyph-only explanation not established by this run |
| A-newsletter-docx | **Pass**, 0.9168; 1/1 page | No exception | Noto Sans CJK SC missing; small positional differences remain |
| A-manual-docx | **Fail**, 0.8872; 1/1 page | Eligible known deviation: layout only, >= 0.88; **not** a strict F2 pass | Noto Sans CJK SC missing; glyph-only explanation not established by this run |
| A-pdfsource-docx | **Pass**, 0.9123; 2/2 pages: **0.9000**, 0.9246 | No exception | Noto Sans CJK SC missing; first page is on the recorded 0.90 boundary |

Thus **3/5 pass the strict aggregate threshold**, while two remain below it and
qualify only under the repository's existing decision-10 exception. In addition,
report page 1 is below 0.90 despite its aggregate pass. This is not evidence that
all five inputs, or all individual pages, meet the original 0.90 threshold.

The fallback font's absence does not prove the effective font is absent:
Microsoft YaHei is available and is the preferred CSS family. Computed CSS,
versions and missing-font probes are recorded, but effective per-glyph font use
was not instrumented. No fonts were installed or substituted to improve scores.
Report was measured with its original missing stylesheet, not a fabricated CSS
replacement; that limits what can be inferred about an intended styled design.

## Visual review and unresolved differences

Paired page images were reviewed by both implementation and primary agents:

- **Report page 1:** nested list markers change from hollow circles to solid
  bullets; table/chart and other block positions differ. Page 2 expands the
  source's collapsed `<details>`, exposing an extra visible explanation and
  shifting later contact content. The high aggregate score is not lossless layout
  or preservation of interactive state.
- **Contract:** merged table-header borders/line segments differ, and the signing
  block spacing differs. Text is present and major section starts are close,
  but this run cannot attribute the full deficit solely to glyph rasterization.
- **Newsletter:** chart/caption and later paragraph positions differ slightly.
- **Manual:** table row dimensions differ slightly and the third section starts
  about 10 image pixels higher in WPS. This is not solely a proven glyph effect.
- **PDF-source:** table geometry/line strokes and subsequent text positions
  differ; page 1 is exactly 0.9000 at the recorded four-decimal precision.

The decision-10 `historical_reason` in JSON is explicitly a historical rationale,
not a new root-cause finding. Investigating/repairing these differences needs a
separate reviewed product stage; no repair is included here.

## Historical comparison without crossing renderers

| Case | Earlier WPS, tenth Windows check | Current WPS | Configured LibreOffice reference |
| --- | --- | --- | --- |
| report | 0.9236 | 0.9224 | 0.9109 |
| contract | 0.8491 | 0.8491 | 0.8060 |
| newsletter | 0.9170 | 0.9168 | 0.8972 |
| manual | 0.8873 | 0.8872 | 0.8618 |
| pdfsource | 0.9123 | 0.9123 | 0.8998 |

Earlier WPS values come from `docs/PHASE13_PLAN.md`; historical host/version
conditions were not revalidated. LibreOffice values come from the unchanged
`config/fidelity_baselines.json` and are reference-only, not this run's scores.
The LibreOffice baseline-minus-0.02 rule is **not applied to WPS**. These small
numeric differences do not by themselves prove a product regression or an
improvement across changed browser/host conditions.

## Evidence and reproduction

[`artifacts/html-docx-wps-matrix-20261121`](../artifacts/html-docx-wps-matrix-20261121/README.md)
retains the initial/per-case WPS process probes, input copies/manifests with
SHA-256 values and missing references, generated DOCX, original browser/WPS PDFs,
all seven page pairs and both sets of color renders, computed CSS, conversion/export responses,
semantic reports, hashes and three-column results. Repository-local JSON paths
are relative. `matrix.json` records runtime git HEAD and runner SHA-256.
The raw input snapshots are exempted from Git text normalization only within this
evidence directory, preserving the measured CRLF bytes and their SHA-256 hashes.

The initial and all five pre-export probes found no WPS processes. Only the
converter's own instances/documents were used. The runner does not call the old
matrix's release/taskkill functions and refuses existing WPS processes. There
were no COM/browser failures and no unmeasured cases.

```powershell
python scripts/html_docx_wps_matrix.py --out artifacts/html-docx-wps-matrix-rerun
python -m unittest discover -s tests -p test_html_docx_wps_matrix.py
```

Use the existing project HTML/fidelity/test dependencies, Playwright, Edge, WPS
and a writable `TEMP`/`TMP`. The output directory must be new. The runner is
restricted to these five cases; it does not run group B or the full 26-case set.
Do not infer all-format, cross-host, cross-version or lossless-CSS acceptance.

Focused tests cover exact case scope, separate strict/exception verdicts,
unavailable/wrong renderers, the original missing CSS, and WPS process blocking.
Related hyperlink/container/conversion regressions and full Ruff/diff checks
are run before PR handoff; all PR CI jobs and primary-agent review are required
before an evidence PR can merge. Merging evidence does not convert its recorded
strict failures into passes.
