# Stage26: merged-continuation width negative mechanism

Base3086f60def5fe46c4c353f0c6d5f766c23e8eeb2, isolated fidelity-merged-width
worktree/experiment/merged-continuation-width branch. No converter, original HTML,
page margin, table grid, baseline or threshold changed. Frozen/stopped worktrees
(including Stage25) remain untouched.

## Fixed candidate and exact package gate

Accepted original contract payment table grid is710/724/1370/2729twips. Its second
row has two physical vMerge continuation cells with template tcW2633. The sole
candidate changes exactly those two attributes to710/2729, corresponding to their
grid columns0/3. No alternate widths, synthetic controls or margin combination.

The builder asserts table/grid/physical merge identity and old values, preserves
original ZIP entry metadata/order and every other package payload. Reverting the
two attributes reproduces the original document.xml FULL BYTES, establishing that
namespace/serialization or other XML changes did not slip into the experiment.
Two focused groups verify that inverse, reject already-modified input and prove
deterministic full DOCX bytes with all other parts identical.

## Single safe WPS export and result

WPS12.8.2.18913(file12,8,2,18913), identical to the accepted Stage22 contract
baseline version. Empty process probe before the only candidate export; own-instance
release only, no taskkill/preferences/user document interaction or retry. Baseline
was reused, not re-exported. Full raw candidate DOCX/PDF/PNG, probe/version/export,
source/output hashes and acceptance geometry live in
artifacts/merged-continuation-width-20261121.

- All page pixels are identical to baseline at the established800px render width.
- Every extracted PDF line/rectangle rule, row pitch and character text/bbox is
  exactly equal. This covers payment boundaries/header, text wrapping and all
  downstream content positions, not only a local crop.
- One page unchanged; text/structure/formatting/data semantic components all1.
- Original contract layout SSIM remains.8492, still strict F2 failure.

The primary agent independently reviewed candidate and accepted baseline original
pages and found the merged header and full content visually identical.

## Bounded conclusion

This WPS version displays no rendering difference from these two continuation
width changes, consistent with ignoring their tcW for layout in this particular
vMerge table. It does NOT establish that all renderers, merge forms or edits ignore
continuation widths. It is not a product fix, visual improvement or proof of safe
page-margin integration. Stage25's pgMar-only gate remains unsatisfied; this stage
does not alter its uncommitted candidate or weaken that gate. Product safety and
any future integration need a separate reviewed plan, never combined implicitly.

## Verification

Source/candidate/PDF hashes verified. Two focused test groups, full Ruff/format
and diff checks pass. This evidence-only PR requires primary independent diff/image
review and all six CI green before primary merge; agent never merges.

Offline build: python scripts/merged_continuation_width_mechanism.py --out NEW_DIR.
--export-wps performs the single guarded candidate experiment; the recorded set
was not rerun or tuned.
