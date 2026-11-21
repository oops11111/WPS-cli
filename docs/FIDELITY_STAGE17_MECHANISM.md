# Stage 17: inline DrawingML marker mechanism

Base `9a33efd851b4e00bca3d21d8ec600518828cf637`. All predeclared mechanism
gates pass at12/18pt on WPS12.8.2.18913. This is synthetic evidence only: no
product/browser/scorer/report, fixture, baseline or threshold changed. Original
report integration requires a separately reviewed Stage18 plan. Stage6/10/12
stopped worktrees remain untouched.

## Representation and fixed controls

Native wp:inline contains a:graphicData/wps:wsp/a:custGeom with a black filled,
unstroked right triangle, inside an MCE Choice requiring wps. No fallback,
VML, numbering, font glyph, literal gap text/tab, anchor offset or run raise/lower
is used. The [official Word shape integration](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-odrawxml/1ba79d37-c640-41dc-ba4e-9180ed31651e)
and [DrawingML geometry](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.customgeometry?view=openxml-3.0.1)
define the representation; host behavior is established by this experiment.

Six deterministic synthetic controls use A4/one-inch margins/Arial S, exact1.5S
line pitch and zero paragraph margins. Each retains SUMMARY plus vanished
RETAINED-BODY in the first paragraph and FOLLOWING in the second. C has no
drawing. I has a0.66S square inline canvas; G has1.06S by0.66S canvas, including
the UA-derived0.4S end gap as intrinsic advance. Both triangles have physical
width0.5676S/height0.66S. Path canvases6600/10600 by6600 with identical points
(0,0),(5676,3300),(0,6600) preserve physical geometry. Extent/shape transform
match with origin0, effects0 and one EMU quantization. This is not a case-specific
text or y offset. Existing stage15 browser geometry and Chromium's font-relative
recipe ground the prediction; no new browser reference was generated.

## One-set observed result

| Case | SUMMARY x/top (pt) | Ink width/height (pt) | Baseline error |
| --- | --- | --- | --- |
| C12 |72 /78.338 |none |reference |
| I12 |79.92 /78.338 |6.8 /7.9 |within0.10pt |
| G12 |84.72 /78.338 |6.8 /7.9 |-0.05pt |
| C18 |72 /81.482 |none |reference |
| I18 |83.88 /81.482 |10.201 /11.85 |within0.10pt |
| G18 |91.08 /81.482 |10.201 /11.85 |-0.05pt |

I/G vectors start at x72pt, the matching C text origin. G12 vertices are
(72,78.5),(78.8,82.45),(72,86.4); G18 vertices are
(72,81.75),(82.201,87.675),(72,93.6). Native SUMMARY baselines are86.45/93.65pt.
Text advances I=7.92/11.88pt, G=12.72/19.08pt and G-I=4.8/7.2pt match predictions.
SUMMARY/FOLLOWING y positions are unchanged from C, all cases one page. Each
DOCX retains body exactly once/hidden and every PDF shows only SUMMARY/FOLLOWING.

All required size/orientation/left/baseline/advance/gap/y and common visibility/
retention/page gates pass. Four non-control outputs contain one black vector
and zero images; there is no placeholder glyph. Independent C12/G12/G18 image
and manifest review confirms the real triangle and measured geometry. This
contrasts with stage16's fixed VML picture-bullet failure, without changing or
relabeling that evidence.

## Limits and verification

This proves this particular inline DrawingML representation on this host, at two
sizes, for one-line synthetic text. It does not establish report F2, current UA
metadata capture, inside wrapping, RTL/custom markers, editing recovery UI,
accessibility, interaction or cross-settings/host behavior. Hidden display/print
preferences remain unknown and unchanged. No product recommendation is implemented.

[Raw evidence](../artifacts/inline-summary-marker-mechanism-20261121/) contains
six DOCX/PDF/page images, empty pre-case process/version probes, raw exports,
runner/input/output SHA, text baselines and vector paths plus all gate values.
`verification.json` verifies every input/output hash, document XML hashes, shared
measurement-helper SHA and actual black vector colors. Exactly one sequential
six-export set ran with normal120s timeout and only converter-owned instance
release; no taskkill, user-document attachment/closure, installation/preference
changes or tuning rerun occurred.

Four focused test groups pass, covering deterministic packages/unrelated parts,
exact MCE/path/extent/text/hidden controls, positive geometry and adverse advance/
y/orientation cases, missing shape and body leak. Full Ruff check/format and
whitespace checks pass. Six CI jobs plus independent review are required before
an evidence-only PR merge; product integration is outside this PR.

```powershell
python scripts/inline_summary_marker_mechanism.py --out artifacts/inline-controls-offline
python -m unittest discover -s tests -p test_inline_summary_marker_mechanism.py -v
# --export-wps opts into a real experiment; no experiment was retried here.
```
