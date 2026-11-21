# Stage38: full-contract width candidate improves layout, remains below F2

Base `3ddbc9197753f53d8e1101ef93bdfefc42bcb4ce`. Evidence-only result:
**PASS_FULL_CONTRACT_ONLY**, not product acceptance or strict F2 success.

## Fixed package and risk basis

The complete accepted Stage28 contract DOCX is immutable SHA256
`ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f`.
Only its second table's four gridCol and seventeen non-continuation tcW values
are reduced15twips each. Grid710/724/1370/2729 becomes695/709/1355/2714;
merged-origin1370 becomes1355 and continuation2639 stays2639. Exact21-attribute
inverse restores the full original document.xml bytes; other package payloads
are identical and builds deterministic. The resulting fee-table subtree exactly
matches the natively verified Stage37 C0 subtree.

Stage37 justified testing original flow without assuming its safety. Stage34
failed its distinct ink-clearance preflight and remains unchanged. This stage
directly tests the full contract; no frozen stage, converter, fixture, baseline,
threshold, font, paragraph spacing, height, margin or border was changed.

## Single native export and measurements

Exactly one candidate export used WPS12.8.2.18913 after an empty process probe.
The accepted original WPS PDF was cached, not re-exported. Five vertical centers
are33.75/68.50/103.95/171.70/307.40pt, matching registered predictions; differential
against baseline is0/-.75/-1.50/-2.25/-3pt. Sum of source-edge absolute residuals
decreases6.175->2.075pt, with no individual residual regression.

All seventeen origin character streams remain one line. Font/size/baselines,
horizontal rule positions and five24pt pitches remain invariant within declared
tolerances. Every outside-table character keeps x/y, including subsequent text,
headings and signatures. Page count stays1; all semantic gates pass. Rule segment
topology and geometric glyph assignment preserve rowspan/colspan identities;
repeated text is not used to select a cell.

| Fixed unaligned SSIM | Accepted baseline | Candidate |
|---|---:|---:|
| Body395..470pt |.5417066672|.5955525107|
| Header348..395pt |.8149933027|.8825520332|
| Whole table348..470pt |.6355915576|.6932737552|
| Whole page |.8643611411|.8718796762|

ROI x30..770px and y converted by int(pt*800/595.92) were registered before
export. Repository800px grayscale rendering, target resize to source size and
the existing SSIM implementation are unchanged. No image shift, registration,
crop search, threshold change or tuning rerun occurred. All ten gates pass.

Strict F2 .90 still fails. Remaining vertical/row-centered glyph and downstream
flow residuals were conserved rather than repaired. This result is limited to
this original contract on this host; it does not establish safe product removal
of allowance, other documents/engines or the original-five regression gate.

## Evidence and verification

`artifacts/full-contract-width-20261121/` contains candidate.docx, wps.pdf,
wps-page-001.png, source/candidate comparison under pages/, acceptance.json,
manifest.json, process probe and export response. Manifest records input/output
hashes, exact base and executable version. Baseline references remain immutable
under `artifacts/alignment-aware-print-margins-20261121/A-contract-docx/`.

Four focused tests plus four Stage37-related and six packaging tests pass.
Coverage includes exact inverse, deterministic package/parts, copied-subtree
identity, changed font/topology rejection and strict score-stop predicates.
Ruff check/format, diff checks and output-hash verification pass. An independent
primary image/diff review and six green CI jobs precede any evidence-only merge;
product implementation requires a separately reviewed stage.
