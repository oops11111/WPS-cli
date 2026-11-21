# Stage22: bounded figure image indentation

Base6e1b237695525889f4019a69b28b4887ae316375. The approved narrow product
integration passes all predeclared offline and original-five gates. Only a
standalone image whose direct holder is an eligible measured figure receives
native paragraph left_indent after the existing apply_paragraph path. No other
paragraph property, image size, content or container path is changed.

## Cause and qualification

Original report browser chart x63.75pt minus body33.75pt =30pt; old WPS image/body
both34.32pt =0. Figure has computed x48CSSpx versus bodyx8 and margin-left40px.
add_image applied its figure holder with list_item=True, which suppresses ordinary
paragraph offsets. The repair restores measured _left_offset only after conservative
figure eligibility: browser boxes, ordinary static LTR left alignment, one direct
image plus optional plain caption, no list/table/nested figure, effects/auto or
negative margins, horizontal padding/borders, complex content or over-wide image.
Unsupported/no-browser cases retain their old behavior. Author offsets use measured
boxes, not a hardcoded30pt constant. This is not a general container-image repair.

## Before WPS: package hard gate

Negative test reproduced0 versus requested30pt. Rebuilding original-five with their
archived browser styles gives exactly one report document.xml difference: chart
paragraph w:ind left600. All other XML and package parts are identical. Contract,
manual, newsletter and pdfsource full DOCX bytes are identical after fixing only
ZIP metadata/timestamps to the original, never substituting payloads. The offline
JSON/candidate DOCX live in artifacts/figure-image-indent-offline-20261121.

## Single original-five real WPS set

WPS12.8.2.18913 (file/product12,8,2,18913), Edge157.0.4341.60. Empty process probe
before every export; only own-instance release. One sequential five-case set,
no retry, taskkill, settings, fixture/font/threshold/baseline change. Raw inputs,
PDF/DOCX/PNGs, hashes, versions/probes and acceptance are in
artifacts/figure-image-indent-20261121. All source/assets/output hashes verified.

| Case | Aggregate before→after | After pages SSIM | Strict aggregate F2 |
|---|---|---|---|
| report | .9307→.9398 | .9007, .9789 | pass, now both pages≥.90 |
| contract | .8492→.8492 | .8492 | fail |
| newsletter | .9168→.9168 | .9168 | pass |
| manual | .8959→.8959 | .8959 | fail |
| pdfsource | .9123→.9123 | .9000, .9246 | pass |

Report chart x34.32→64.32pt, relative to body exactly30pt. Browser x63.75pt retains
the known common page/body horizontal residual .57pt. Chart y690pt and240×120pt
size unchanged; caption and following text coordinates identical. Page2 pixels
identical. The other four cases have every page pixel-identical; all semantics1
and page counts unchanged. acceptance.json passes all case/geometry gates.
Primary independently reviewed page1 source/WPS/comparison and geometry.

Contract/manual still fail strict F2, notwithstanding existing decision10 exceptions.
Report nested list markers retain their visible shape differences; missing-font
and original missing print.css limitations remain in raw results. No claim that
all HTML layouts or all document hosts have lossless conversion follows.

## Verification

Focused tests cover measured author0/40/80px, legacy holder/no-browser/wide cases,
and missing box/nested/list/table/auto/transform/RTL/center/complex/negative vetoes.
Related38 HTML/fidelity/baseline tests passed; focused3 groups passed. Full Ruff,
format/diff and staged input-blob SHA checks accompany the PR. The offline assessor
independently checks hashes, pixels, semantic/page/score and chart/caption/following
coordinates. All six CI jobs and primary independent diff/image review required
before merge; implementation agent never merges.
