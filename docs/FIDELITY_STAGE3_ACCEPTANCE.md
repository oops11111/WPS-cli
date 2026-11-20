# Stage 3: hyperlink styles and honest formatting scores

Base: merged stages 1/2, main `ed872808625cf620d2c77772f303e8021584922d`.
The stage-2 visual review found a smaller WPS hyperlink despite a formatting
score of 1.0. This stage fixes that mismatch without adding conversion directions.

## Fix and negative evidence

HTML links now use the existing computed-style run mapping, including nested
bold/italic runs and line breaks, then place those runs inside the original
external hyperlink relationship. Target filtering is unchanged. The DOCX reader
includes hyperlink runs in XML order in paragraphs, table cells, headers and
footers. A missing styled source run is counted as a failed formatting check
instead of being skipped; unformatted plain text stays outside this check.

Six new tests reproduced seven failing subcases before the fix. After the fix
all six pass, including wrong size, wrong color and a removed hyperlink run.
The unchanged stage-2 DOCX now scores **0.9697** for formatting, correctly failing:

- `us: color '0000EE' -> '0563C1'`
- `us: size 15.0 -> None`

That old artifact and its original report remain untouched. The new
[`previous-docx-rechecked.json`](../artifacts/direct-container-hyperlink-20261121/previous-docx-rechecked.json)
records the corrected check; no baseline or threshold was lowered.

## Same-fixture WPS acceptance

The original fixture bytes are unchanged: SHA-256
`e8283229fa183ab4b1c029c5506e8f1cac6748439c35be694ffe275d3d5081f8`.
WPS Writer **12.8.2.18913** / `kwps.Application` / `ExportAsFixedFormat` and
Edge **157.0.4341.60** were used. The process gate was empty before WPS export;
only the conversion's own instance and generated DOCX were used.

| Measure | Stage 2 | Stage 3 |
| --- | --- | --- |
| Full-page SSIM, F2 >= 0.90 | 0.9835 | **0.9834**, passed |
| Fixed top-300px diagnostic | 0.9368 | **0.9365**, supplementary only |
| Pages, source / WPS | 1 / 1 | 1 / 1 |
| Text / structure | 1.0 / 1.0 | **1.0 / 1.0** |
| Formatting | 1.0 with omitted link runs | **1.0 with link runs included** |

Visual inspection of the color page and content comparison confirms that the
WPS link now matches the surrounding text's size and blue browser appearance.
The very small SSIM decrease is recorded as measured, not tuned away. Residual
mixed-block vertical spacing differences remain; page whitespace still raises
the full-page score. This is evidence for this fixed regression input on one
host/version, not a lossless-CSS or all-format/cross-version claim.

The [evidence directory](../artifacts/direct-container-hyperlink-20261121/) retains
the original generated DOCX, both PDFs, version/probe/conversion JSON, source and
output hashes, full-page color renders and paired images. Reproduce in a new
directory with the existing command:

```powershell
python scripts/direct_container_evidence.py --out artifacts/direct-container-stage3-rerun
```

The script now explicitly requires formatting 1.0 as well as the existing
text/structure/layout gates. Prior stage-2 reports are historical and unchanged.

## Verification

- 68 tests across hyperlink, container, editable and conversion modules: passed,
  4 skips (30.021 s).
- 44 controlled-roundtrip, review-fix, complex-HTML and HTML-Office tests: passed
  (12.230 s).
- Full Ruff lint/format and diff whitespace checks pass.
- Existing historical fixture conversions are also checked without layout;
  their exact scores and prior baseline values are recorded in
  `historical-semantic-regression.json`: all 26 CASES converted and passed their
  applicable semantic gates, with no score regression against configured values.
  `D-deck-docx` retains its existing structure 0.7 / animation 0.0; group D's
  applicable text/data gates both pass. No thresholds/baselines are changed.
- All PR CI jobs and primary-agent review remain required before merge.
