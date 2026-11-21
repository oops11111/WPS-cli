# Stage 5: contract vertical-merge border continuity

Base: stage 4 merged at `edefb7a885dd32af92eeb84bf499f29a9b75e612`.
Only the planned merged-cell border/shading mapping was repaired. Original
contract bytes, column widths, row heights, paragraph spacing, thresholds and
configured baselines were not changed.

## Reproduction and repair

After `python-docx` merges table cells, `table.cell` aliases continuation slots
to the origin. The HTML grid marks covered slots as `None`, so the styling loop
skipped the physical `vMerge` continuation cells. The contract's fee-table headers
had borders/shading on their restart cells but none explicitly on continuations.

Four tests inspect physical `tr/tc` XML: original contract, a three-row/two-column
merge, unmerged cells and a borderless merge. Before the repair two fail; after
the repair all four pass. The mapping now carries the original exterior border
and shading to every physical row, marks only internal horizontal edges `nil`,
and maintains schema order with one borders/shading element. A single call-site
change passes the already computed merge rectangles. No layout-sizing logic was
changed.

## Same-input WPS evidence

The narrow command calls only the original contract through the existing stage-4
case function, with a fresh output directory and the same WPS process gate:

```powershell
python scripts/contract_merge_evidence.py --out artifacts/contract-merge-rerun
```

The input SHA-256 is unchanged from stage 4:
`cceac9bfb6a531b10cf8f4fc3ccd01e7bd97d159c099ae558f87046c639215ed`.
WPS Writer **12.8.2.18913** / Edge **157.0.4341.60**; process probe empty before
export. Only the converter's generated document/instance was used.

| Measure | Stage 4 | Stage 5 |
| --- | --- | --- |
| Whole-page SSIM, strict threshold 0.90 | 0.8491 | **0.8492**, still strict failure |
| Decision-10 historical rule | Known deviation, floor 0.84 | Same rule, not strict F2 acceptance |
| Text / structure / formatting / data | 1.0 / 1.0 / 1.0 / 1.0 | **1.0 / 1.0 / 1.0 / 1.0** |
| Browser / WPS pages | 1 / 1 | **1 / 1** |
| Fixed fee-region diagnostic SSIM | 0.3129 | **0.3141**, diagnostic only |

The diagnostic rectangle `[40, 460, 425, 640]` at 800px page width was fixed from
the stage-4 browser image before measuring the repair. Both sides use the same
rectangle, with no target realignment. Its low absolute score reflects remaining
text/border-position differences; it is not a new acceptance threshold.

The before/after WPS page comparison changes only **134 pixels**, inside bounding
box **`[45, 499, 419, 533]`**, on the second row of the two vertically merged
headers. At the left exterior edge, rows 500/505/515/525 previously sampled the
fill (minimum channel 221) and now contain the line (130). Outside this region
the WPS page is pixel-identical to stage 4. The full-page score did not regress.
Color region and full-page review confirms continuous exterior header edges and
no added internal seam. Explicit continuation shading is also verified in XML;
its visual color was already inherited by WPS and did not need to change.

This is acceptance of a local edge-continuity repair, **not** a claim that the
contract now meets strict 0.90. Existing glyph/stroke, sizing/spacing differences
and the historical signing-block discrepancy remain outside this stage. Missing
Noto Sans CJK SC remains recorded; no font/installation changes were made.

## Retained evidence and validation

[`artifacts/contract-merge-borders-20261121`](../artifacts/contract-merge-borders-20261121/README.md)
contains original input snapshot/hash, DOCX, browser/WPS PDFs, computed CSS and
raw responses/probes, page/crop PNGs, before/after physical-cell properties,
versions, runtime HEAD/product-diff hash and comparison scores. The raw input
snapshot alone is exempted from Git text normalization to preserve its hash.

- Focused XML tests: 4 pass (1.279 s), versus 2 failures before repair.
- Related merged-cell/HTML/editable/conversion/hyperlink/container/roundtrip
  regressions: 79 tests pass, 4 skips (38.724 s).
- Full Ruff lint/format and diff whitespace checks pass before PR handoff.
- All six PR CI jobs plus primary-agent diff/XML/image review are required before
  merge. No new direction, unsafe link behavior or baseline/tolerance change.
