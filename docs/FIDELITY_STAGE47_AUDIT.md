# Stage47 read-only reassessment: a changed-context hypothesis, not a repair

Exact base dfebac646eb75ab4219c281032dd6ce6641c6f1c. At this audit snapshot there was no candidate, browser/WPS,
product edit, commit or PR. Later Stage48 evidence is a separately approved experiment;
this historical audit status and Stage12 failure remain unchanged.
Raw table/hashes: artifacts/spacing-reassessment-20261121/audit.json.
This is the accepted historical read-only audit; frozen Stage12 input paths
and their hashes are retained as provenance. No frozen inputs are modified.

## Reproduced failure and local request identity

Stage12 old/candidate whole .8491995786057626/.8422329795269962;
fixed region[40,640,765,825] .7797756115852866/.7523433352006862.
Failure remains valid. Source original five HTML bytes all match Stage12.

| Paragraph | Old baseline/current spacing (line/before/after twips) | Old candidate |
|---|---|---|
| price |330/220/220|same|
| h3 |495/54/274|495/274/274|
| confidentiality |330/0/220|same|
| h4 |495/54/274|495/274/274|
| liability |330/0/480|same|

All five paragraphs' rPr XML hashes are individually identical across old,
old candidate and current. Native fonts/sizes are identical (body MicrosoftYaHei
11.05pt; heading MicrosoftYaHei-Bold16.45pt). Text line strings and local
paragraph baselines show no wrap change. Current versus old baseline shifts
approximately-3.72pt; local baseline intervals differ by at most.002pt. Page
margin/column/row changes do not alter this local spacing request. This supports
a conditional response prior, but cannot prove new native response or pixels.

CSS source p margin-bottom14.6667px (11pt), h2 margin-top18.26px (13.695pt);
source p/h2 line22/33px. Native preceding after220 and heading before54 imply
max11pt, rather than full13.7pt native request. The source mapping gap is the
same Stage12 defect, not a new cause. Its context has changed: upstream current
row minimum reduces flow height and changes which side of the reference the
headings lie on. Old measured shifts are +2.76pt at h3/body and +5.40pt at h4/body.

## Definition-safe comparison

| Anchor | Source top / baseline | Old baseline top / baseline | Old candidate top / baseline | Current top / baseline |
|---|---|---|---|---|
| price |480.882578/488.999980|484.176750/492.409|same|480.457750/488.690|
| h3 |512.818338/524.999978|514.333450/526.490|517.093450/529.250|510.612450/522.769|
| confidentiality |549.882575/557.999977|550.057750/558.290|552.817750/561.050|546.336750/554.569|
| h4 |581.818335/593.999975|580.333450/592.490|585.733450/597.890|576.612450/588.769|
| liability |618.132572/626.249974|616.057750/624.290|621.457750/629.690|612.336750/620.569|

Applying old response only as an algebraic prediction, baseline errors would
be h3+.529022, confidentiality-.670977, h4+.169025, liability-.280974pt;
actual top errors would instead be +.554112/-.785825/+.194115/-.395822pt.
Neither set predicts SSIM or native pixels. Do not mix top errors and baselines.

| Anchor | Source actual ink rows | Old→old candidate ink rows | Current ink | Conditional old pixel-shift forecast |
|---|---|---|---|---|
| price |645..658|650..663 unchanged|645..658|unchanged|
| h3 |686..707|690..710→694..714 (+4)|685..705|about689..709, possibly WORSE|
| confidentiality |738..750|739..752→742..755 (+3)|734..747|about737..750|
| h4 |779..800|779..799→786..806 (+7)|774..794|about781..801|
| liability |829..842|827..840→835..848 (+8)|822..835|about830..843|

Ink windows use archived PDF first-character x..x+font-size and line bbox±2pt,
threshold160 at800px; they are approximate glyph bounds, not fitted alignment.
At least one raster-pixel uncertainty remains, and subpixel phase can change
rounding. h3 visibly warns against an all-anchor improvement claim even though
its matrix error is predicted to shrink. Stage45 additionally proved geometric
movement alone may not produce raster change.

## All-five boundary inventory

report0, manual0. Contract2: price→h3, confidentiality→h4, both above CSS.
Newsletter1: intro→head headline; p-after17.3333px vs h2-before18.26px, line normal.
Pdfsource2: intro→section1 and scoring paragraph→section3; p-after16px versus
h2-before17.7067px, line normal. These are different spacing/font/line contexts.
Stage12 newsletter .9168→.9026 and pdfsource .9123→.9045 regressions remain direct
counterexamples to a global product toggle. No eligibility rule has been proven
that makes a product-wide change safe; a contract string/class exception is forbidden.

## Conclusion / possible separately reviewed experiment

There is grounded changed-context evidence for a CONTRACT-ONLY falsification:
the same source-derived native request on an unchanged local XML/font/line
configuration, with upstream flow now about3.72pt earlier. This is not new
product safety evidence or a reclassification of Stage12. If primary considers
it worthwhile, a new Plan could allow exactly two existing h2 before values
54→274, inverse/other parts identical, one native export against current baseline,
all text/font/line/page/table and pre-boundary flow conserved, and independently
measure response/actual ink/fixed ROI/whole. It must predeclare possible adverse
h3 ink, require actual ROI/whole gains, retain strict.90 as separate, and stop
on unexpected wrap/flow/safety or failure. Current evidence cannot promise a
score gain, all-anchor improvement or general product integration. No experiment
is authorized until that separate Plan is reviewed. Otherwise stop here with
this bounded audit rather than tune offsets or revive Stage12 globally.
