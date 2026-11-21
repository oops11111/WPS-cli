# Stage21: native image-paragraph indentation mechanism

Base139dbd1ad0180bf2cecc5a9bd5b10f963501155d. Evidence-only, no converter,
original fixture, baseline or threshold changes. A new fidelity-image-indent
worktree preserves the stopped Stage20 and frozen6/10/12 worktrees.

## Grounding and fixed controls

Accepted report browser PDF chart x63.75pt minus body33.75pt gives30pt; WPS
chart/body both34.32pt gives0. Archived figure/img x48CSSpx versus bodyx8 explains
40px=30pt. Figure has UA margin-left40px, image margin-left0. The original image
paragraph has no w:ind; add_image calls apply_paragraph with list_item=True for
its figure holder, suppressing the ordinary measured-offset branch. Image dimensions
already match240×120pt. This establishes a narrow horizontal hypothesis without
attributing the separate1.50pt vertical residual or list differences.

Six synthetic DOCX packages reuse that exact image paragraph and package media,
with identical BEFORE/FOLLOWING paragraphs. C0/N0,C40/N40,C80/N80 represent declared
figure offsets0/40/80px; C controls retain no indent, N controls write native
left0/600/1200twips. These are DOCX controls, not six newly rendered HTML inputs.
Only w:ind/left differs; there is no image offset, font, size, line-height or
paragraph-space change. No case-specific displacement is calibrated from WPS.

## One safe WPS set

WPS12.8.2.18913, file/product12,8,2,18913. Six pre-case process probes empty;
exactly one sequential export set, own-instance release only. Raw manifest records
source/input/output SHA256, version/path, process/export metadata and geometry;
all six original PDFs and page PNGs accompany deterministic input DOCX packages in
`artifacts/image-indent-mechanism-20261121`.

| Variant | Requested relative x | Measured relative x | Required gates |
|---|---:|---:|---|
| C0 | 0pt | 0pt | all true |
| N0 | 0pt | 0pt | all true |
| C40 | 0pt | 0pt | all true |
| N40 | 30pt | 30pt | all true |
| C80 | 0pt | 0pt | all true |
| N80 | 60pt | 60pt | all true |

Absolute image x34.32/64.32/94.32pt; relative x uses BEFORE text x34.32pt.
Every image y58.32pt, dimensions240×120pt. BEFORE/FOLLOWING PDF-extracted text
coordinates remain exactly equal across cases; all cases retain both words, one
image and one page. PDF font text boxes are not ink bounds, so their absolute y
is not interpreted as visual glyph geometry; unchanged coordinates are the gate.
The page images show the text above/below the image without overlap. Geometry
errors are floating-point noise below1e-13pt, within predeclared .10pt x/.05pt
unchanged-y-and-size gates. No tuning, retries or browser render occurred.

## Interpretation and limits

Native paragraph left indentation moves this inline chart by the principled CSS
relative-container offset without changing measured size or adjacent flow in
these controls. This is mechanism evidence, not an integrated product fix or an
F2 score improvement. Wide images, alignment, tables/lists, nested inline images,
wrapping, positioned objects and arbitrary CSS are not validated. Product eligibility
and original-five regression would need a separately reviewed plan.

## Verification

Three focused groups pass: exact left values and otherwise identical XML;
deterministic full ZIP bytes with unchanged media/all other package parts;
negative x/size/page gate controls. Source/output hashes and all24 case gates
verified after export. Full Ruff/format/diff pass. Independent primary image review
and six green CI jobs are required before primary merge; agent never merges.
