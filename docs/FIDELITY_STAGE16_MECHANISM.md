# Stage 16: negative native-vector picture-bullet result

Base `c113181c7977648294652a9e6d53b620aefbe768`. The required N mechanism gates
**fail** at both font sizes. No product repair follows; the report's disclosure
triangle remains unresolved. This is reusable negative evidence, not fidelity
acceptance. No conversion/browser/scorer, original report, fixtures, baselines,
thresholds or frozen stage6/10/12 worktrees changed.

## Predeclared controls

Exactly six deterministic synthetic DOCX controls: C/Z/N at12/18pt Arial, A4,
one-inch margins, exact1.5-font-size line pitch and zero paragraph margins.
Each retains SUMMARY plus a vanished RETAINED-BODY run, followed by FOLLOWING.
C is unnumbered. Z references a document-local numPicBullet containing a VML
filled unstroked right-pointing triangle with suff=nothing and zero indentation.
N uses the same triangle with suff=tab and left/hanging/tab A=1.06S, rounded once
to native twips. The picture square is0.66S, canonical vertices(0,0),(.86,.5),(0,1).
The numbering placeholder is X: it must be replaced by the picture, never used
as an acceptable glyph substitute. Existing numbering definitions are untouched.

Predictions were grounded in original browser vector geometry and historical
[Chromium disclosure layout](https://chromium.googlesource.com/chromium/src.git/+/cb11d5949b731a22810c46c99c4d3ad64b2e91ec%5E%21/),
plus [OOXML picture-reference behavior](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.levelpicturebulletid?view=openxml-3.0.1).
Those sources do not guarantee WPS support for this VML representation.

## Observed one-set result

| Case | PDF visible text | SUMMARY x/top (pt) | Triangle vectors/images |
| --- | --- | --- | --- |
| C12 | SUMMARY; FOLLOWING |72 /78.338 |0 /0 |
| Z12 | XSUMMARY; FOLLOWING |combined XSUMMARY starts72 /78.338 |0 /0 |
| N12 | X; SUMMARY; FOLLOWING |84.72 /78.338 |0 /0 |
| C18 | SUMMARY; FOLLOWING |72 /81.482 |0 /0 |
| Z18 | XSUMMARY; FOLLOWING |combined XSUMMARY starts72 /81.482 |0 /0 |
| N18 | X; SUMMARY; FOLLOWING |91.08 /81.482 |0 /0 |

N text advances are12.72 and19.08pt, within0.02pt of predeclared twip-rounded
12.70/19.10pt requests. SUMMARY/FOLLOWING y positions are identical to matching
C controls. Native numbering and the intended advance therefore operate, but
the fixed VML picture is not painted: visible placeholder X is present instead.
Independent review of C12/N12/N18 confirms X in N, not a triangle. With no vector,
size/left/baseline gates cannot pass or be inferred from text. Required N vector,
size, marker-left, baseline and visible-state gates fail; manifest passed=false.
Z is diagnostic only and is not needed to establish either N failure.

All six are one page, retained sentinels occur once in DOCX and body run remains
vanished; body is absent from PDF. These successful controls do not outweigh
the missing picture. No font substitution, shape/size/y-offset adjustment or
threshold change was attempted after the failure; there was no tuning rerun.

## Scope of the conclusion

This particular VML picture-bullet definition on WPS12.8.2.18913 exported as
fallback text. This does **not** establish that all image/picture numbering is
unsupported, that another encoding would work, or that the same package behaves
identically in Word/other hosts. Renderer support, accepted VML subset and package
interoperability remain possible explanations. No extra representation was tried.
There is no inside-wrap, RTL, interaction, accessibility or cross-settings claim.
A further experiment requires a separately reviewed plan; no product change is
authorized by this negative result.

## Safety, evidence and verification

[Raw evidence](../artifacts/summary-picture-bullet-mechanism-20261121/) retains all
six DOCX/PDF/page images, pre-case process/version probes, exports and manifest
with predictions, measured coordinates/baselines, vectors, images and gate outcomes.
`verification.json` verifies all input/output SHA and document/numbering XML hashes.
Exactly one sequential six-export set ran, with empty pre-case process probes,
normal120s timeout and only converter-owned document/instance release. No taskkill,
user attachment/closure, global hidden-print preference, installation or browser
conversion was used. Hidden/printing preferences remain unknown and unchanged.

Five focused test groups pass: deterministic package bytes and unrelated-part
equivalence, exact XML/text/hidden/ID/suffix/indent controls, font-relative size
predictions, shape-orientation rejection and unknown-variant rejection. Full Ruff
check/format and whitespace checks pass. An evidence-only PR requires independent
review and all six CI jobs green before merge; this is not a product PR.

```powershell
# Offline only by default; use a new directory.
python scripts/summary_picture_bullet_mechanism.py --out artifacts/picture-controls-offline
python -m unittest discover -s tests -p test_summary_picture_bullet_mechanism.py -v
# --export-wps explicitly opts into another experiment; none was retried here.
```
