# Stage23: print-margin quantization mechanism

Baseab96820f1423131c68f516aa6c1d342b0d683c7d. Evidence-only experiment;
no converter/scorer/original fixture/baseline/threshold change. New isolated
fidelity-page-margins worktree preserves stopped20 and all earlier frozen work.

## Predeclared references and native controls

Four fixed HTML references: A4/Letter × default(no CSS margin, API10mm) or explicit
CSS @page size plus margin12mm(API10mm). All have body8px, cyan full-width bar,
ANCHOR,40 A-space tokens and45 numbered lines at17.25pt pitch. The explicit cases
also state the same intended paper size in CSS; consequently their paper-width
change cannot be attributed to margin alone. No source/number changes or reruns.

Before WPS, all four PDF stream transforms confirm the predeclared formula:
left=floor(mm×96/25.4)×.75+6pt. Default content origin27.7499988pt plusbody6pt gives
33.7499986pt; CSS12 origin33.7499986 plusbody6 gives39.7499983pt. Cyan rectangles
and ANCHOR corroborate, independent of glyph-ink detection. Edge157.0.4341.60.

Each reference then has two deterministic synthetic DOCX controls: precise-mm vs
floor-CSSpx margins; only pgMar attributes differ. Fonts/text/line spacing/paper
and package content identical. Native cyan paragraph shading represents the bar;
body horizontal inset6pt is included in margins, initial vertical inset6pt in
first-paragraph before-spacing. This tests a mechanism, not a general HTML mapper.

## One safe eight-export WPS set

WPS12.8.2.18913(file/product12,8,2,18913). Each pre-case probe empty, own instance
released; exactly eight sequential exports. No taskkill/user documents/settings,
font install, numeric tuning or retry. All text retained and every output2pages.
Raw geometry, sources, PDFs/PNGs, DOCX, hashes, export/probe/version metadata live
in artifacts/print-margin-mechanism-20261121.

| Reference | Precise left error | Floor left error | Precise right error | Floor right error |
|---|---:|---:|---:|---:|
| A4 default10mm | +.5700pt | −.0300pt | −1.5500pt | −.9500pt |
| A4 CSS12mm | +.2090pt | −.0300pt | −.4500pt | −.2000pt |
| Letter default10mm | +.5700pt | −.0300pt | −.6000pt | +.000024pt |
| Letter CSS12mm | +.2090pt | −.0300pt | −.2500pt | +.000024pt |

All four floor left≤.10pt, no-more-lines/pages and identical3pt bar-height gates
pass. Floor's complete line/page text arrays match each browser reference. A4
default precise has44/3 lines per page instead of browser/floor45/2; all other
precise line/page arrays also match their references. Thus no wrap/pagination
regression in these fixed controls, not proof for arbitrary HTML or original-five.

## Paper-width counterevidence and limits

Browser A4 default595.91998×842.88pt; CSS-size A4594.95996×841.91998pt. Native WPS
A4 is595.3×841.9pt. Letter browser/native both612×792pt. A4 right-edge residuals
remain despite corrected left origin. CSS-size and API-size paths differ in these
references; this experiment does not identify their full paper/layout quantization
algorithm and does not modify paper sizes to compensate. Numeric floor formula
is supported for these two margins/two sizes on this exact Edge version, not a
universal cross-version/browser rule. Native twip serialization/font placement
also explains small remaining left differences; no ad-hoc correction was applied.

Product safety is explicitly NOT proven. Original-five semantic/per-page/F2 and
broader @page/author-margin behavior would need a separately reviewed stage.
Primary independently reviewed A4-default/Letter-css12 browser/precise/floor page1,
confirming intact bars/anchors, closer floor left and visible A4 page assignment.

## Verification

Three focused groups verify fixed deterministic sources, PDF transform parsing
with unsupported-transform rejection, deterministic native ZIP bytes and only
pgMar differences across all four pairs. Source/four PDF/eight DOCX/eight PDF
hashes verified, full Ruff/format/diff clean. Evidence PR requires independent
primary review and six green CI before primary merge; agent never merges.

Reproduce browser-only: python scripts/print_margin_mechanism.py --out NEW_DIR.
--wps-from-existing requires a fresh passed browser manifest, refuses existing
native set, probes each export and stops on missing text or failed floor gates.
The recorded set was not rerun.
