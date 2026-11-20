# Stage 2: direct-container HTML to DOCX

Measured on main `8d2bf886d827a146b69d50c651dbc89c1a54766c` after
PR #156 (`67b907f`). The fixed fixture is
[`direct_container.html`](../fixtures/fidelity/direct_container.html), derived
from the original direct-text, inline-mixed and nested-container regression cases.
It was not tuned after measurement.

| Acceptance | Observed | Result |
| --- | --- | --- |
| Existing F2 full-page SSIM >= 0.90 | 0.9835; browser 1 page / WPS 1 page | Passed |
| Text / structure 100% | 1.0 / 1.0 | Passed |
| Supplemental fixed top-300px diagnostic | 0.9368 | Recorded, does not replace F2 |
| Semantic formatting | 1.0 | Recorded; see hyperlink limitation |

Microsoft Edge 157.0.4341.60 rendered the source. WPS Writer 12.8.2.18913
exported the converted DOCX using `kwps.Application` / `ExportAsFixedFormat`.
The WPS process probe was empty before export: only the instance launched for
this measurement was used. No user document was closed.

The [evidence archive](../artifacts/direct-container-evidence-first/README.md)
contains raw conversion, browser and WPS JSON, versions and SHA-256 hashes,
original PDF/DOCX files, full-page color renders and paired images. Repository
paths in JSON are relative to the checkout. The repeatable command is:

```powershell
python scripts/direct_container_evidence.py --out artifacts/direct-container-rerun
```

The script refuses an existing output directory and COM export when WPS
processes are already running. Existing HTML/test/fidelity dependencies,
Playwright, Edge, WPS and a writable TEMP are prerequisites.

Visual inspection of both color pages and the content comparison confirmed the
border, background, center/right alignment, direct text and bold/italic runs.
Small vertical spacing differences remain; the WPS hyperlink is visibly smaller
than the browser's link. The semantic formatting scorer does not detect that
hyperlink size difference. Page whitespace raises full-page SSIM, hence the
additional fixed content-area score and visual review.

This acceptance applies only to this fixed regression input on this host/WPS
version. It does not establish lossless CSS layout, Chinese font fallback,
cross-version compatibility, or acceptance of the historical full-format matrix.
Other multi-block container box layouts remain best effort.

Validation: three direct-container regression tests pass; all evidence hashes,
scores, computed container styles and version metadata were checked; full
`ruff check .`, `ruff format --check .` (558 files) and `git diff --check` pass.
PR CI remains an independent gate before merge.
