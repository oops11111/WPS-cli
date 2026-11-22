# HTML to PPTX final acceptance: best-effort, full fidelity not met

Base and merge target: `main` at `8df12982bb5984fba18dbee92ece17bfd8166f9d`. This report covers only the three fixed HTML→PPTX demonstrations. It makes no converter, fixture, media, scoring-threshold or other-format change. The [Stage3 plan](HTML_PPTX_STAGE3_PLAN.md) and merged [delivery plan](HTML_PPTX_FIDELITY_DELIVERY_PLAN.md) define the gates.

## Fresh 2026-11-22 static run

On this Windows host, `scripts/html_pptx_full_canvas_audit.py` reconverted all three HTML sources, used Edge/Playwright for 1280×720 browser slide viewports and WPS Presentation for full-slide rendering, and wrote one [raw run](../artifacts/html-pptx-stage3-20261122/manifest.json) plus source/PPTX/image artifacts. `scripts/html_pptx_stage3_summary.py` checked it and wrote the [final manifest](../artifacts/html-pptx-stage3-20261122/final_manifest.json), which records the actual Stage3 base SHA, source/package/renderer hashes, legacy scores and the residual gates. The reused Stage1A runner's internal `product_base` field names its original implementation baseline (`dd0d1ea`); the final manifest's `executed_main_base` is the commit actually checked out for this fresh run.

| Case | New full-slide SSIM by page | Aggregate | Lowest page |
| --- | --- | --- | --- |
| launch (6) | .9865, .9852, .9862, .9822, .9475, .9981 | .9809 | .9475 |
| training (3) | .9713, .9603, .9472 | .9596 | .9472 |
| quarterly (3) | .9802, .9349, .9849 | .9667 | .9349 |

All 12 pages exceed the planned per-page .90 static score; the three aggregates exceed the historical .90 aggregate gate. Applicable text, structure, formatting, animation-inventory and data semantic scores are 1.0. Legacy section-crop scores remain separate in the manifest; they do not measure equal canvases. The fresh PPTX byte hashes differ from Stage2 because of ZIP container metadata, while every uncompressed PPTX member is byte-identical to its Stage2 COM-tested package (`changed_uncompressed_pptx_members_vs_stage2: []` for all three). This supports carrying forward the Stage2 OOXML/COM observations for the same package contents; it is not a new WPS slideshow test.

## Unmet gates

The new [launch page 5 pair](../artifacts/html-pptx-stage3-20261122/A-launch-pptx/pages/page-005-0.948.png) visibly shows a browser video control and no corresponding WPS object. The source refers to `teaser.mp4`, which is absent; the fresh conversion reports zero mapped media and warns that the video was omitted. Its .9475 whole-page score cannot override this visible-object failure. The source's inline `span.fade` is also mapped to its whole paragraph, widening the animation target.

The merged [Stage2 evidence](HTML_PPTX_STAGE2_STOP.md) matched all 13 source effects to OOXML targets, along with 12 transitions and 3 notes. WPS COM exposed effect, trigger, order, delay, duration and transition properties for the same package contents, and training page advancement was observed. Its screen captures were covered by a pre-existing unrelated error dialog; window-targeted capture returned black frames. Clean visual proof of movement, timing and transitions for all three decks remains **unverified**. This final stage did not retry the blocked desktop path or treat the old 2026-10-22 playback record as new evidence.

**Decision: retain `best-effort` HTML→PPTX support. Complete high-fidelity acceptance is not achieved.** The static score gate passed; the visible media gate failed; clean WPS animation playback remains unverified. A future acceptance run needs lawful source media and an unobstructed device capture of actual animation behavior. CI for this documentation/evidence PR is a separate merge gate and does not change this product conclusion.
