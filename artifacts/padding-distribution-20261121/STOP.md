# Stage32 historical STOP snapshot: then uncommitted, no PR

Base `9bdc71078dabc7178040740483277154b4ab5ff5`; fixed candidate changes exactly
24 spacing attributes in twelve fee-body paragraphs, before/after60/45->53/52
twips, total105 unchanged. XML inverse and every other ZIP payload passed.
Four focused plus six packaging tests passed; Ruff check/format passed.

Exactly one candidate WPS12.8.2.18913 export completed after empty process probe.
No baseline re-export, product edits, alternative candidate or tuning occurred.

| Measurement | Before | Candidate | Gate |
|---|---:|---:|---|
| Baseline shift in each of three rows | reference | -.24pt | FAIL: predicted -.35±.05pt |
| Baseline-minus-row-center source error | +.7800006pt | +.5400006pt | FAIL: improvement .24<.25pt |
| Fixed fee-body ROI SSIM | .5516460049 | .5537006170 | improved |
| Whole contract SSIM | .8644 | .8645 | improved, still strict F2 fail |
| Rule positions/pitches, outside-body y, glyph x/font | reference | conserved | pass |
| Semantics, text, line/page count | reference | conserved | pass |

The exact registered geometric prediction was not observed. A small directional
effect supports padding distribution influencing this text placement, but does
not establish the quantitative model or a safe repair. No threshold is relaxed.
The source/scorer still lists unavailable Noto Sans CJK SC; actual visible font
is Microsoft YaHei in both accepted and candidate PDFs, unchanged by experiment.

Raw: acceptance.json contains baseline/source/candidate characters and rules,
manifest.json hashes all outputs, candidate.docx, wps.pdf, wps-page-001.png and
pages/page-001-0.865.png; probe.json/export.json retain actual process/version/
export evidence. Baseline remains the immutable Stage28 artifact referenced in
manifest. This is a local stopped snapshot pending independent primary review;
At the STOP capture, no commit/push/PR existed. Subsequent evidence-only review and publication do not change this failed result; no second WPS run or product recommendation is authorized.
