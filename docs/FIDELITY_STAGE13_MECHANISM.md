# Stage 13: retained hidden text in a static DOCX

Base `5779f84c258aa1dc9690e8a88240b5f53b7b9e59`. This is an accepted,
bounded mechanism experiment, not an implemented report conversion fix or F2
acceptance. No product/scorer, original report, fixture, threshold or baseline
changed. Stage6/10/12 stopped worktrees remain untouched.

The original report has a closed details element. Its browser PDF shows summary
only, while current DOCX/WPS shows summary and body. Both source/target semantic
readers retain body text without representing closed visibility. Thus text1.0
does not validate the closed state. Nonzero descendant browser boxes and computed
visibility do not independently establish that a closed details body is painted.

## Fixed controls and measured results

All controls are synthetic: A4, one-inch margins, Arial12pt, exact18pt paragraph
pitch, zero before/after margins. They isolate hiding from source fonts, summary
markers and existing report positioning. Stable ZIP metadata/order and fixed
package defaults permit deterministic regeneration. Only document.xml differs;
all unrelated package parts remain byte-identical.

| Case | XML control | Underlying DOCX text | PDF text | FOLLOWING top |
| --- | --- | --- | --- | ---: |
| V | three visible paragraphs | all three sentinels | SUMMARY, RETAINED-BODY, FOLLOWING |114.34pt |
| H | summary and vanished body runs in same paragraph | all three sentinels | SUMMARY, FOLLOWING |96.34pt |
| P | separate vanished body run and paragraph mark | all three sentinels | SUMMARY, FOLLOWING |96.34pt |
| C | no body, two visible paragraphs | SUMMARY, FOLLOWING | SUMMARY, FOLLOWING |96.34pt |

SUMMARY top is78.34pt in all controls; all are one page. H satisfies all six
required gates, including retained body, no body in PDF and FOLLOWING offset
from C0.00pt (predeclared tolerance0.05pt). P is diagnostic only; it also has
offset0.00pt on this host. V provides the visible/open-state control; C deliberately
loses body and must never be used as a content-preserving product mapping.
Independent image review confirms H matches C's two-line layout and V includes
the additional visible body line. These are text tops, not ink/accessible bounds.

## Limits and next decision

WPS12.8.2.18913 on this host omitted vanished text during these four exports.
Hidden display/printing preferences were neither queried nor changed and remain
unknown. OOXML specifies that applications can force hidden text to be displayed;
Word also exposes hidden-text printing settings ([vanish documentation](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.vanish?view=openxml-3.0.1),
[PrintHiddenText](https://learn.microsoft.com/en-us/office/vba/api/word.options.printhiddentext)).
This experiment does not verify other settings, WPS versions, screen readers,
user recovery/editing UI, nested/complex details, images, links or roundtrip.
Retained XML is not a claim of accessibility or HTML disclosure interaction.

A separately approved product stage could consider narrowly supported closed
details with explicit summary and simple text body. It would need independent
retained-content and visible-output assertions, open-state controls and original
report WPS layout/semantic gates. No product choice is authorized by this result;
the existing scorer alone cannot establish visibility correctness.

## Evidence and checks

[Raw evidence](../artifacts/details-hidden-mechanism-20261121/) contains four
DOCX/PDF/page images plus per-case process probes and raw exports. Exactly one
sequential four-export set ran. Each pre-case probe found no WPS process;
only converter-owned instances/documents were used. No taskkill, user-instance
attachment, browser/HTML conversion, installation or tuning rerun occurred.

`manifest.json` contains versions, runner/input/output SHA, retained sentinel list,
PDF word coordinates and required/diagnostic gates. `verification.json` records
verified package/PDF hashes, underlying text nodes, XML SHA and python-docx
version. Original report SHA remains
`40f9b6732ca6f13a1f56eda36f3b8318bec35d30d2be26fcee19134c2bb832e1`.
Three focused test groups pass (deterministic/package controls, exact declared
XML differences and required-H/diagnostic-P gate behavior). Full Ruff check and
format pass578 files, and whitespace checks pass. Six green CI jobs and primary
review are required before merge.

```powershell
# Offline only by default; use a new output directory.
python scripts/details_hidden_mechanism.py --out artifacts/details-controls-offline
python -m unittest discover -s tests -p test_details_hidden_mechanism.py -v
# --export-wps explicitly opts into another experiment, not offline validation.
```
