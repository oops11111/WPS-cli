# Stage 9: controlled WPS table-row experiment

Base `b93e2c24d3921f5b3845f14fd8856ddf05f5e88c`. This evidence-only experiment
does not change conversion code, original fixtures, thresholds or baselines.
The original manual remains strict F2 failure at0.8959<0.90.

## Fixed controls and observations

The builder copies the committed Stage7 DOCX package, retains only its first
four-row/three-column table and section properties, and makes exactly the seven
predeclared synthetic controls. Unrelated ZIP parts remain byte-identical;
stable ZIP metadata/order makes generation deterministic. Original source SHA:
`36b3a2c7d4a42e35bc85a379b4895908694a8d2f852c9d11c227ab42efb9ea44`.

| Case | Controlled change from B | Four vector row pitches (pt) | Characters/pages |
| --- | --- | --- | --- |
| B | AT_LEAST390twips, original content/borders | 20.25 each |72 /1 |
| E | EXACT390twips |19.5 each |72 /1 |
| R | AT_LEAST375twips |19.5 each |72 /1 |
| L | B, 1pt X per cell, exact1pt line, zero vertical spacing |20.25 each |12 /1 |
| LR | L, AT_LEAST375twips |19.5 each |12 /1 |
| N | B, explicit nil table/cell borders | no border vectors |72 /1 |
| NR | N, AT_LEAST375twips | no border vectors |72 /1 |

N's first-cell text top differences are19.4973,19.44,19.56pt; NR's are
18.6583,18.72,18.84pt. They support approximately19.5/18.75pt pitch with about
0.1pt text-position uncertainty, not four directly measured vector pitches.
The first/header row also has a distinct font/weight; text boxes cannot prove
the final borderless row's physical bottom. Absence of border vectors is expected,
and is explicitly retained rather than inventing measurements.

## Mechanism evidence, not a repair choice

The five bordered controls match every predeclared additive-border prediction
within0.05pt. Lowering content minimum in L does not reduce B's20.25pt pitch;
lowering the AT_LEAST request by one nominal0.75pt border reduces both B and L
by exactly0.75pt. EXACT19.5pt renders19.5pt. Together with borderless text-based
support, this isolates a native bordered AT_LEAST row-height accounting effect
for this synthetic table; ordinary manual text minimum alone cannot explain it.

This does not identify WPS's internal algorithm or establish a universally safe
conversion repair. Borderless inference is less precise, and only one font,
border width, simple one-line table and WPS version were tested. EXACT could clip
taller content; subtracting border width could under-size wrapped, merged or
explicitly constrained rows. No such product change is made or authorized here.
No predicted manual SSIM gain follows from the diagnostic result alone.

Independent review of B/E/R confirms visibly shorter E/R rows, all normal
content still visible, one page and no obvious clipping/wrapping. Text extraction
retains all72 normal characters in B/E/R/N/NR; low-content L/LR retain12 Xs by
design. Visual review and text count are diagnostic checks, not proof of no
clipping for arbitrary content. A subsequent product plan needs negative XML
reproduction, narrowly justified eligibility and fresh original-manual WPS gates.

## Safety, raw evidence and checks

Exactly one sequential seven-export set ran on WPS12.8.2.18913. Each case's
read-only probe showed no existing WPS process before its own conversion;
all exports succeeded. No taskkill, user-instance attachment, browser rendering,
HTML conversion, installation change or tuning rerun occurred. Stage6 remains
frozen. Raw probes, export JSON, deterministic synthetic DOCX, PDFs and page
images are in [the experiment directory](../artifacts/manual-row-mechanism-20261121/).
`manifest.json` records all vector/text geometry, versions and input/output SHA;
`verification.json` records original/output hash checks, first-cell text tops and
Python/pdfplumber versions. Source manual HTML bytes are unchanged.

Four package/XML test groups plus five existing geometry tests pass. Checks cover
all seven deterministic packages, identical unrelated ZIP parts, only declared
XML differences, four physical rows/12cells, text and variant attributes. Full
Ruff/format (576 files) and whitespace checks pass; six green CI jobs
and independent evidence review are required before merge.

```powershell
# Offline generation only by default; a new directory is required.
python scripts/manual_row_mechanism.py --out artifacts/manual-row-controls-offline
python -m unittest discover -s tests -p test_manual_row_mechanism.py -v
# --export-wps is the explicit opt-in to a new experiment, not part of offline checks.
```
