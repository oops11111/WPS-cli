# Hyperlink fidelity evidence

See [stage-3 acceptance](../../docs/FIDELITY_STAGE3_ACCEPTANCE.md) for the fixed
fixture, versions, results and limitations.

`result.json` records the first measurement after the hyperlink fix: full-page
SSIM 0.9834, fixed content-region 0.9365, text/structure/formatting 1.0, one page
on each side. Input hash matches the original stage-2 fixture exactly.
`previous-docx-rechecked.json` demonstrates that the corrected scorer rejects
the old missing hyperlink formatting (0.9697). The original old artifact is not
overwritten. Browser/WPS PDFs, DOCX and color/paired PNGs are retained for review.

`historical-semantic-regression.json` records the existing conversion CASES
without layout, alongside their original configured baseline values. It is
diagnostic evidence, not a rewrite of any baseline or a claim of WPS coverage
for those other directions.
