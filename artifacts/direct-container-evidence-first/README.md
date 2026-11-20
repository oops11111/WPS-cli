# Direct container text: WPS visual acceptance

Source fix: PR #156, commit `67b907f`; measured on merged main
`8d2bf886d827a146b69d50c651dbc89c1a54766c`.
This is the first fixed-input measurement, not a tuned fixture.

| Gate | Evidence | Result |
| --- | --- | --- |
| Full-page layout | Edge reference PDF vs WPS-exported DOCX PDF, 800 px width | **0.9835**, 1 page each; F2 >= 0.90 passed |
| Content diagnostic | Same pages, fixed rectangle `[0, 0, 800, 300]` | **0.9368**; supplementary only |
| Text / structure | Existing `fidelity_check`, original HTML vs DOCX | **1.0 / 1.0** |
| Formatting | Existing semantic checker | **1.0** |
| Visual review | Full-page pair, both color pages and top-300px pair | Content present; alignment, border, fill, bold/italic preserved |

Browser: Microsoft Edge **157.0.4341.60**, via installed Playwright.
WPS: Writer **12.8.2.18913**, `kwps.Application`, `ExportAsFixedFormat`.
The exact executable path, file/product version and SHA-256 are in
`wps-version.json`. The source, DOCX and both PDF SHA-256 values are in
`result.json`; the HTML source is `fixtures/fidelity/direct_container.html`.

The process probe found no running WPS/Spreadsheets/Presentation processes.
The existing converter therefore launched its own COM application, opened only
the generated DOCX, exported, and released its instance. No interactive document
was closed. A read-only initial lookup missed the versioned WPS installation's
LocalServer32 path; actual COM export succeeded. No installation changes were made.

## Reproduce

Install the existing project test/HTML/fidelity dependencies and Node Playwright.
On Windows with WPS/Edge, set `TEMP`/`TMP` to a writable directory and run:

```powershell
python scripts/direct_container_evidence.py --out artifacts/direct-container-rerun
```

The script refuses an existing output directory and refuses COM export if WPS
processes are already running. The report records repository paths relative to
the checkout. The JSON records, source PDFs/DOCX, original color page renders and
the paired image are retained here; no screenshots are used as substitutes for
the PDF inputs.

## Limits

This single fixed regression fixture passed the existing F2 threshold on one WPS
version and host. It establishes the repaired direct-container path, not the old
Phase 13 full-format matrix or cross-version compatibility. White page area raises
full-page SSIM, so the fixed content-region score and visual review are provided
alongside it without changing the acceptance threshold.

The WPS rendering has small vertical spacing differences in mixed blocks, and the
hyperlink is visibly smaller than the browser's link despite preservation of its
label and target. The semantic formatting scorer does not capture that hyperlink
size difference. Multi-block container box layout and arbitrary CSS remain best
effort; this result is not a lossless-conversion claim. Noto Sans CJK SC was absent;
the fixture uses Arial and does not establish Chinese font fallback fidelity.
