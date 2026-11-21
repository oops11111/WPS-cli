# Stage43: merged-contract row minimum follows the border-accounting model

Base `551fe7fad79d6b96423caca73e816b4ab35aebc7`. Evidence-only outcome
**PASS_MECHANISM**, not a product repair or strict F2 success.

## Fixed change and constraints

The Stage42 contract control SHA256 is
`760bb182bf74f3b491ed103f8d56fc5089d99f1c22bf4ff6f8226fcd1d1dbab1`.
Exactly five second-table trHeight values change465->450twips, with AT_LEAST
unchanged. Formula: (31px source row minus1px nominal collapsed border)*15.
Inverse restores complete original document.xml bytes; other ZIP payloads and
metadata match, builds deterministic. Candidate SHA256:
`2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa`.

Ordinary paragraph line/before/after remains330/60/45twips. The two header
rowspan origins retain their existing390 line request; continuations, all fonts,
widths, padding, borders, page margins and surrounding paragraphs are untouched.
No EXACT coercion, empirical offset, second candidate or tuning occurred.

Stage10 modified the manual only and excluded this merged table; its failed
product result is unchanged. Stage12's failed p-heading candidate is not used.
This newly bounded native experiment tests content/merge constraints directly.

## One native export

One safe candidate export used WPS12.8.2.18913 after an empty process probe.
No browser/control re-export or user-document/global-setting/font change.
Environment and baseline/candidate browser-snapshot semantic gates passed before
WPS; no fallback or implicit source capture. Applicable semantics remain perfect.

Six native horizontal centers are347.81/371.06/394.31/417.56/440.81/464.06pt,
exactly the registered model. Five pitches are23.25pt, height116.25pt versus120pt.
All vertical x positions are unchanged. Seventeen origin streams remain single
line with unchanged fonts/size/advance/ink heights, no rule-crossing glyph.
The two-row header origin baseline shifts-.72pt (prediction-.75), first header
single-row-.36(prediction-.375), second header-1.081(prediction-1.125); all body
cell predictions meet the declared.10pt tolerance. Downstream displacement is
approximately-3.72pt versus registered-3.75±.10; relative intervals are preserved.
Pre-table content and horizontal text positions remain unchanged; page count1.
All15 measurement gates pass, separately from semantic/environment preflight.

| Fixed unaligned SSIM | Stage42 | Candidate |
|---|---:|---:|
| Body395..470pt |.595552511|.808045712|
| Header348..395pt |.882552033|.934692855|
| Table348..470pt |.693273755|.857345359|
| Later text470..640pt |.755426525|.764176805|
| Whole |.871879676|.895000062|

The800px repository grayscale/resize algorithm and fixed x30..770px windows
were registered before export. No alignment, crop search or threshold changes.
Strict F2 .90 remains **FAIL** at rounded.8950.

## Counterevidence must remain visible

| Downstream baseline source error, pt | Before | Candidate |
|---|---:|---:|
| Total price |+3.409020|-.309980|
| Heading3 |+1.490022|-2.230978|
| Confidentiality body |+.290023|-3.430977|
| Heading4 |-1.509975|-5.230975|
| Liability body |-1.959974|-5.680974|

Price becomes closer, while the other listed source errors become worse, as
predeclared. The later-region SSIM mean still increases slightly; it does not
mean every line improved. These positional residuals prevent a general product
safety claim. Only this contract/host was tested; any integration needs a new
reviewed eligibility and original-five gate, with the adverse anchors retained.

## Evidence and verification

`artifacts/contract-row-minimum-20261121/` contains the unique candidate, rawPDF/
PNG, full baseline/candidate char/rule/anchor measurements and scores, actual
probe/export/version, source constraints, environment and semantic preflight.
Derived source/candidate comparison is generated offline from those same PDFs.
Final hashes cover all raw bytes; a narrow gitattributes rule affects only this
new evidence prefix. No frozen-stage files or temporary logs are included.

Four focused plus related row/environment/packaging tests total20 pass. Ruff/
format/diff and final exported-input rebuild/hash checks are required before
review. Primary independent image/diff and six green CI precede any evidence PR
merge; implementation agent does not merge or change product code.
