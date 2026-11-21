# Five-case WPS evidence

See [stage-4 report](../../docs/FIDELITY_STAGE4_ACCEPTANCE.md) for strict F2,
decision-10 historical exceptions and font/input comparability as separate
columns. Strict aggregate passes: **3/5**, not five. Report page 1 is below 0.90.

`matrix.json` is the complete runtime result; each case also has `result.json`,
original input/assets and hashes, conversion/browser/export responses, both
original PDFs, generated DOCX, computed CSS and all color/paired page images.
The raw initial/per-case process probes found no running WPS instances.

Known limitations include missing `print.css` in the original report fixture,
absent Noto Sans CJK SC fallback, report list marker/detail expansion changes,
contract merged-header borders/signing spacing, manual row/vertical spacing and
other small positional differences. The old glyph explanation is historical,
not established as the sole cause by this run. No product/input/baseline/tolerance
changes were made to improve any result.
