# Stage 18: measured closed-summary disclosure marker

Base `c7e492dfe5259e7dfec040da00d03fe4bc43f22c`. The bounded integration passes
its predeclared gates. Only the existing simple, closed, plain-text details shape
with proven browser marker metadata receives a document-local inline DrawingML
triangle. This is a static editable document, without HTML interaction or an
accessibility/cross-host-settings guarantee.

## Evidence and qualification

Current Edge 157.0.4341.60 screen/print repeated snapshots agree on disclosure-closed,
inside, normal marker content, matching 16px font, and a one-line Range advance of
12.703125pt. Actual browser PDF confirms the black triangle; the Stage17 recipe
advances 12.72pt, within one twip. Raw preflight JSON/PDF/script and source SHA are
in `artifacts/closed-summary-marker-preflight-20261121`.

An initial browser collection failed with Playwright user-TEMP EPERM. The raw
failure/environment note is retained; correcting TEMP/TMP to the workspace allowed
collection. This was an environment correction before the sole WPS measurement,
not a marker-geometry retry. Missing or uncertain metadata remains fail-closed.

Unknown/custom/wrapped/RTL or modified spacing/decoration markers retain the
existing hidden-body conversion with a marker-loss warning. Author list-style:none
adds neither marker nor warning. Open details remain unchanged. Unsupported base
shapes retain expanded content with their existing warning. No input, threshold,
font, baseline or global preference is modified.

## Single original-five WPS set

WPS 12.8.2.18913 (`12,8,2,18913`), Edge 157.0.4341.60. Each pre-case WPS process
probe was empty; only the converter's own instance was released. Raw PDFs, DOCX,
input snapshots, hashes, versions, comparisons and results are under
`artifacts/closed-summary-marker-20261121`. `acceptance.json` contains the independent
coordinate/retention/image-count and five-case gates, all true.

| Case | Aggregate before → after | After page SSIM | Pages | Strict aggregate F2 |
|---|---|---|---|---|
| report | .9302 → .9307 | .8826, .9789 | 2 | pass; page 1 still below .90 |
| contract | .8492 → .8492 | .8492 | 1 | fail |
| newsletter | .9168 → .9168 | .9168 | 1 | pass |
| manual | .8959 → .8959 | .8959 | 1 | fail |
| pdfsource | .9123 → .9123 | .9000, .9246 | 2 | pass |

Every semantic component remains 1.0; page counts and every page/aggregate score
are nondecreasing. Report page 1 pixels are identical. Contract/manual remain only
historical decision10 exceptions, not strict F2 successes. Missing-font and missing
report print.css environment limitations remain recorded in the raw matrix.

Report summary x moves 34.32→47.04pt toward browser 46.4531pt (error
12.1331→.5869pt). Summary y166.91, contact y194.63 and unsafe-link y222.35pt stay
unchanged. One real black triangle measures 6.80×7.90pt; its bottom matches the
summary baseline175.85pt. Relative body-left error .03pt and size/baseline errors
meet .10pt gates. Browser triangle is 6.8027×7.9102pt. A small common horizontal
margin residual remains. The hidden body occurs once in DOCX, stays hidden and
is absent from PDF; the real chart still counts as one image. Only the explicitly
identified and structurally validated managed decoration is excluded by scoring.

The primary agent independently reviewed browser/WPS page2 and comparison images.
A later letter-spacing/text-decoration eligibility veto did not invalidate this
single WPS set: `spacing-veto-verification.json` proves original input/output hashes
and marker metadata unchanged. Offline reconstructions using original browser
snapshots and original ZIP metadata/timestamps have identical payloads AND full
DOCX bytes for all five cases; no payload substitution or WPS rerun occurred.

## Verification and limits

Focused XML/package tests cover 12/18pt, trimming, hidden-run indices, unique IDs,
unsupported metadata, spacing/decoration, none/open behavior and forged image
identities. Related HTML/fidelity checks, historical 26-case conversion/check and
Ruff/JS syntax checks accompany the PR. All historical formatting values remain
unchanged. CI must pass all six jobs before primary-agent merge.

This evidence establishes the narrow one-line mapping on this browser/WPS host;
it does not establish arbitrary marker customization, wrapping, HTML interaction,
accessibility, all-host rendering or full-case strict fidelity for every fixture.

Final post-veto targeted checks: 5 marker groups pass; HTML-wide 81 tests has
one unchanged host failure (4 skips):
`test_html_positioned.NormalLineTests.test_a_line_with_a_superscript_keeps_the_pitch_the_browser_drew`,
`assertGreater(raised.line_spacing.pt, plain.line_spacing.pt)` reports
`13.5 not greater than 15.75`. A clean detached exact-base c7e492d checkout,
same Python/Edge/NODE_PATH/workspace TEMP and UTF-8 environment, reproduces this
identical failure in 2.376s. No unrelated line-height implementation was changed.
Raw local logs remain outside the submitted evidence directories.
