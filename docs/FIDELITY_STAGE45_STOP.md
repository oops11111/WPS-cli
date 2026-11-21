# Stage45: geometric padding effect without visible fidelity gain

Base `1ac049f87a286342e1162af59e69c0a00d9c5d2f`. Evidence-only outcome
**STOP**. Exactly one new WPS candidate export; no product change or retry.
At the STOP snapshot this work was uncommitted with no PR; later evidence
publication does not change that historical status or the failed gate.

## Immutable candidate and controls

The accepted Stage44 contract package SHA256 is
`2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa`.
Only12 body-cell paragraph spacings change before60→53 and after45→52twips,
preserving total105. Exactly24 attributes inverse to original document.xml
bytes; other payloads and ZIP metadata are identical, builds deterministic.
Five450twip AT_LEAST rows, widths, fonts, borders and flow are untouched.
Candidate SHA256:
`66c21da0a93dd65679219abba9736b35067367f6865ad3d98f98775aeb538bc1`.

Both packages passed applicable perfect/N/A-explicit semantics against the
same saved Stage44 browser snapshot. No browser/source/control re-export.
The environment and safe empty-process/version probe passed before the sole
candidate WPS12.8.2.18913 export. No user documents/settings/fonts changed.

## Registered prediction and measurements

| First-column body baseline | Before error from source row-relative baseline | Candidate error | Shift |
|---|---:|---:|---:|
| row2 |+.855000625|+.495000625|−.360000000|
| row3 |+.765000594|+.405000594|−.360000000|
| row4 |+.795000563|+.435000563|−.360000000|

All three shifts meet the registered−.35±.05pt prediction and improve each
absolute row-relative error by≥.25pt. All nine conservation/baseline identity
gates pass: rules/pitches, text/font/x/advance, origin single lines, polygon
clearance, outside-body baselines and downstream anchors remain unchanged.

However, the actual800px RGB page images are byte-identical, as are the PNG
files. Both PNG SHA256:
`a1a6f518ef057000affc49993e28f82eff4c79fa0a6ae4b73f1579ea8fb3861f`.
Candidate PDF SHA256:
`5e2e6a554c511fa73241e56ecb2fba7d7098aced806855b1156df9517e55fef7`;
baseline PDF SHA256:
`79e97679322fc7860cbfd2c1e94cfb26b623731cd220b1488cbfff29dd50080a`.
The PDFs and extracted character-matrix geometry differ. That geometric
change is not evidence of a visible rendering improvement.

| Fixed SSIM | Before | Candidate |
|---|---:|---:|
| body |.8080457116111607|.8080457116111607|
| header |.9346928545741392|.9346928545741392|
| table |.8573453587284451|.8573453587284451|
| later |.7641768045298025|.7641768045298025|
| whole |.8950000618741911|.8950000618741911|

Regions preserve Stage43's PDF-pt bounds and `int(y*800/595.92)` raster mapping,
not direct pixel bounds. No alignment, threshold, ROI or candidate was tuned.
Required body/whole increases fail; strict F2 .90 also remains failed.

## Raw field interpretation and counterevidence

Original acceptance.json is unchanged. Its `pixels_identical:false` field is
the runner's **joint zero-influence predicate**: raster equality AND complete
character/rule/table geometry equality. Geometry inequality makes it false
despite independently verified RGB equality. Consequently this is STOP rather
than the stricter ZERO_INFLUENCE category. The field must not be interpreted as
an observed raster difference. PDFium loads both PDFs independently; no cached
render or implicit WPS/browser call supplies these comparisons.

Downstream source errors remain price−.309980pt, heading3−2.230978pt,
confidentiality−3.430977pt, heading4−5.230975pt, liability−5.680974pt. The earlier
adverse anchors are preserved, not fixed by this candidate. Stage32's prior
−.24pt/failed-prediction STOP remains unchanged; new-base geometry does not
retroactively make it successful. No product recommendation or five-case
safety claim follows from this negative contract-only experiment.

## Verification and delivery

20 related/packaging tests, full Ruff/format and diff checks pass. The assessor's
archived-baseline self-test independently classifies ZERO_INFLUENCE, and the
attempt-marker test rejects retries before process probing. Original execution
manifest hashes are verified. Retained raw contains one candidate/PDF/PNG,
acceptance, export/probe/version, environment/preflight and semantic records;
baseline artifacts already exist under Stage44/Stage42. Temporary logs are
excluded. Any later evidence PR requires independent review and all CI checks;
this STOP neither authorizes another export nor product integration.
