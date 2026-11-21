# Stage28: alignment-aware qualified horizontal print margins

Base d0dbb48efa689190d52443551d57213b20d53eab. This independent product acceptance
passes all pre-registered gates. Stage27 remains a separate frozen FAILED result:
its body-relative-image rule did not distinguish native centering. No Stage27
file/result was rewritten, and no margin value, original input or SSIM threshold
was adjusted. Four product files have identical bytes to that stopped candidate.

## Bounded product scope

Only Windows/editable HTML conversion with current runtime CDP product
Edg/157.0.4341.60, matching executable/browser version and complete recursive
CSSOM(no page/import/error/inaccessible sheet) uses37CSSpx for the API10mm default
left/right print margins. Body inset remains; paper/top/bottom/header/footer remain.
Other engines/versions/modes/custom page rules and unknown metadata preserve old
behavior. This is not the final universal mapping for all browsers or HTML.

Source report's missing print.css makes CSSOM incomplete, so report correctly
fails closed. The other four current inputs have complete readable inline CSSOM.
Raw engine identity, rule audit and original source image alignments are in
artifacts/alignment-aware-margins-preflight-20261121.

## Exact offline and actual-output package audit

Complete-five preflight: report DOCX full bytes identical using original ZIP
metadata/timestamps; four others ONLY pgMar left/right687→675twips, except the two
explicitly preapproved contract payment-table continuation tcW2633→2639. Their
physical row/columns/vMerge identity and grid710/724/1370/2729 are checked; default
width formula(11906−2×675)/4=2639 explains the derived values. No standardization or
other table repair is added. Exact inverse of allowed attributes reproduces original
document.xml BYTES; every other package part identical. The same inverse/package
audit also passes on all five actual DOCX files sent to WPS(actual-package-audit.json).
No exported DOCX/PDF was rewritten to obtain these results.

## Pre-registered image semantics

Before the new WPS round, source computed CSS and DOCX paragraph jc are recorded
in preregistered-image-contracts.json. Newsletter source figure/image=center,
jc=center, no direct/inherited indent, symmetric margins. Its content midline is
297.65pt before/after; image center297.6pt remains, residual−.05pt stable. Dimensions
240×120pt and y241.2pt unchanged. Browser center298.50pt retains the existing .90pt
error; no claim of perfect source centering. Absolute native centering, not distance
from the moving left body edge, is the correct invariant for this qualified case.

Left/start images require source/jc agreement and stable body-relative x. Report
chart remains left/ind600, body-relative30pt; report's entire output page pixels
are unchanged. Other three cases have no pictures. Unknown/conflicting alignment,
asymmetric margins or inherited/direct indentation on centered images reject the
gate. Center/left/unknown/asymmetric/indent/size/y/browser-error tests were fixed
and passed BEFORE this new WPS set; no post-hoc exception was applied to Stage27.

## New single original-five WPS acceptance

Edge157.0.4341.60; WPS12.8.2.18913(file/product12,8,2,18913). Empty pre-case probes,
own-instance release only. Exactly one new complete five-case round under this
independent plan, no retry/tuning/taskkill/settings/user-document interaction.
Raw source snapshots, PDFs/DOCX/PNGs, hashes, identity/probes/styles/semantic/geometry
and acceptance are in artifacts/alignment-aware-print-margins-20261121.

| Case | Aggregate before→after | After per-page SSIM | Strict F2 |
|---|---|---|---|
| report | .9398→.9398 | .9007,.9789 | pass; fail-closed pixels identical |
| contract | .8492→.8644 | .8644 | FAIL, only historical decision10 exception |
| manual | .8959→.9027 | .9027 | pass on this host/fixture |
| newsletter | .9168→.9293 | .9293 | pass |
| pdfsource | .9123→.9190 | .9123,.9258 | pass |

All available semantic components remain1, all text/line/page assignments and page
counts identical. Every page/aggregate nondecreasing and both required cases improve.
All character y boxes and paper dimensions unchanged. Four qualified left anchors
have error about−.03pt rather than+.57pt; selected matching right-edge geometry is
no worse. A4 paper/right residual remains(e.g.newsletter right error−.95pt); no
paper-width or ad-hoc offset compensation is introduced. Contract relative table
rules/merged-header rectangles and row pitches/downstream y remain unchanged,
verifying the new-margin interaction rather than assuming Stage26's old-margin
negative mechanism result proves safety.

Primary independently reviewed the NEW manual/contract/newsletter comparison pages:
closer text/boundaries, no new contract table seam and stable newsletter center.
Contract still fails strict F2; list/font/paper residuals and the original missing
report CSS remain limitations. This bounded five-case evidence does not guarantee
arbitrary content, future Edge versions or other document hosts.

## Verification and delivery gate

42 related tests passed18.856s before WPS, including actual recursive CSSOM page/
import/missing cases, exact package allowlist rejection, and alignment invariants.
Source/assets/output hashes and seven staged source/asset blob hashes verified.
Final related/focused, full Ruff/format, JS syntax and diff checks accompany PR.
Primary independent diff/image review plus all six green CI required before main
merge; implementation agent never merges.
