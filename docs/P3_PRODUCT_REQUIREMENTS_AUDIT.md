# Product Requirements Evidence Audit

Date: 2026-10-07. Source: user-supplied WPS_AI_Agent_CLI_PRD_v1.1.docx,
sections 4, 5, 7, 8 and 9, read from its DOCX XML. This is a capability gap
audit, not a claim that all PRD acceptance criteria are met.

| PRD requirement | Current evidence | Remaining work |
| --- | --- | --- |
| Stable document IDs, backup, recovery | sessions.py records content and file identity; source/backup checks surround COM, P3-175 serializes cooperating Agent mutations, P3-176 atomically persists shared registries, P3-177 records post-save identity for replay repair, and P3-178 blocks automatic reapplication when a derived backup exists but the unrecorded source changed; real Writer/Spreadsheet WPS writes passed | Registrations are not live COM sessions; the locks do not exclude external editors, and a changed source without a main operation record is deliberately ambiguous rather than proven successful |
| Writer structure and targeted editing | `writer-structure` reads bounded heading/style/bookmark metadata and uniquely paired same-paragraph body/table/header/footer bookmark text; current WPS parity passed 7/7 and 4/4; P3-186 adds guarded table-cell writes; P3-187 verifies table topology; P3-188/189 verify safe hyperlink/field behavior; P3-190/191 verify drawing relationships, crops, positions, and multiple inline images; P3-192 verifies multiple-anchor stacking and media targets through WPS save; P3-193 confirms pixel-identical red/blue masks in rendered PDFs before/after WPS save | Broader cross-version matrix and visual fidelity outside the tested fixture remain unverified |
| Spreadsheet read/write and real calculation | bounded range/formula operations, format and WPS display inspection; worksheet inventory covers layout, visibility, protection, names, calculations and bounded validation/formatting metadata; worksheet mutations have WPS-backed transaction tests; P3-113 verifies 1904 dates and host-locale display | Broader WPS version/locale matrix and macro-enabled WPS round-trip/data preservation still need distinct verification |
| Presentation page/object targeting | presentation_text.py resolves logical slide order; snapshots include blank/image-only slides, grouped text and tables; replacement traverses nested shapes/cells, preserves matched-range formatting and verifies per-object text; P3-088 already limits Spreadsheet write ranges to 10,000 cells before backup/WPS | Broader cross-version Presentation visual fidelity remains unverified |
| Conversion matrix and HTML modes | `html-render`, `html-editable`, controlled import/verify/export; real WPS rich-media round-trip retains stable image/link identities | Broader WPS version fidelity validation remains |
| Batch conversion with per-file results | `html-batch-convert` and `wps_agent_html_batch_convert` convert up to 100 HTML files to PDF/PNG/DOCX with isolated failures and SHA-256 provenance; `batch-template-report` and `wps_agent_batch_template_report` render validated manifests through local Markdown or DOCX templates | Broader cross-version and multipage visual fidelity evidence remains |
| Tasks, cancellation, progress | `html-batch-convert --task-id` updates per-file progress, polls shared task status between files, and retains a partial manifest on cancellation | Live progress streaming and process recovery remain |
| Structured CLI/MCP contract | cli.py, mcp_adapter.py, mcp_server.py; unit and smoke tests | Real desktop-client integration and broad Agent user-story evaluation need distinct evidence |
| Content, calculation and format verification | validators.py, snapshots.py, regression manifest | Current structural checks do not establish visual fidelity or cross-version success thresholds |

Historical Phase 0/1/2 completion refers to the implemented local milestones;
it must not be interpreted as full PRD delivery. The 123 passing unit tests on
the audit date proved their assertions, not all product requirements. Current
test totals and WPS integration evidence are maintained in
`PHASE3_RELEASE_READINESS_REFRESH.md`.

## Scheduled Work

1. P3-159 complete: safe baseline and artifact-dependent release gates are separated. The local safe run passed 15/15 and release run passed 3/3 after package refresh; old failed artifacts were retained.
2. P3-160 complete: `local-release-gates` passed the five-step local package/safe/refresh/readiness/release sequence and saved both regression artifacts.
3. P3-161 complete: bounded, read-only Writer heading/style/bookmark inspection is available via CLI/MCP. It is offline OOXML evidence, not a WPS layout claim.
4. P3-162 complete: selected-section pagination and exact bookmark lookup now report source hashes and ambiguity.
5. P3-163 complete: bounded bookmark text inspection distinguishes available, empty, missing, ambiguous, unsupported scope, and invalid range without claiming WPS validation.
6. P3-164 complete: controlled local WPS read-only observations agreed on paragraph text/order, heading levels, and bookmark text; localized style display names differed from OOXML style IDs as expected.
7. P3-165 complete: opt-in Writer parity CLI/MCP passed 6/6 checks on the controlled local fixture and retained a JSON report with source hash.
8. P3-166 complete: local handoff includes the latest Writer parity JSON; readiness checks report status, fixture/script hashes, and package byte equality without launching WPS.
9. P3-167 complete: a separate controlled fixture verified table and header/footer bookmark presence and text through read-only WPS; this was before nested offline text reads were implemented.
10. P3-168 complete: bounded same-paragraph nested bookmark reads agree with the controlled WPS fixture through CLI/MCP; cross-container and ambiguous reads remain unsupported, and Writer mutation scope stays body-only.
11. P3-169 complete: an opt-in nested-scope Writer parity command retained a passed 3/3 local WPS JSON report; local handoff readiness verifies its source/script hashes and packaged bytes.
12. P3-170 complete: revision/text-box paragraphs are rejected for bookmark reads and fills; a controlled mixed-run table bookmark matched read-only WPS with unchanged SHA-256.
13. P3-171 complete: both Writer parity reports now bind four implementation-file hashes; local readiness marks reports stale when code changes, even if file mtimes are preserved.
14. P3-172 complete: registrations bind SHA-256 and file identity; mutation backup preflight rejects stale or legacy-unverified records, detects copy-time changes, and refreshes the identity after successful local operations. See `P3_DOCUMENT_IDENTITY_AUDIT.md` for the remaining race.
15. P3-173 complete: the observed bookmark fill had correctly updated text, but WPS appended one empty paragraph after a terminal table; narrowly accepting that normalization preserved neighboring text/table checks, backup, and replay.
16. P3-174 complete: a shared guard rechecks source identity and backup bytes just before COM, then checks post-COM source identity after readback; controlled Writer and Spreadsheet replacements are rejected without starting COM.
17. P3-175 complete: a workspace/document-ID lock spans cooperating Agent mutation and registration calls; cross-process contention returns `DOCUMENT_BUSY`, and real Writer/Spreadsheet WPS writes passed under the lock.
18. P3-176 complete: shared documents/operations registry read-modify-write transactions now use bounded cross-process locks and same-directory atomic replacement. Four processes retained 48 distinct records in each registry; concurrent reads saw complete JSON; failed replacement preserved the old state. Real WPS Writer/Spreadsheet checks passed.
19. P3-177 complete: committed file identity allows safe replay repair when registration refresh failed; a changed file or failed identity capture produces explicit non-replayable evidence. Windows transient lock initialization and read sharing races found by repeated concurrency tests were fixed.
20. P3-178 complete: a derived backup with unchanged source allows retry; a changed or unreadable source without a main operation record returns `UNRECORDED_MUTATION_AMBIGUOUS` before target lookup, preventing automatic reapplication. This is not evidence that WPS saved successfully.
21. P3-179 complete: `mutation-request-inspect` and its MCP mapping report main operation, derived backup, and current file identity without writing; recorded-but-stale, changed, retryable, ambiguous, and no-evidence states are distinguished.
22. P3-180 complete: all eight mutation inspection states include non-destructive recovery guidance in CLI/MCP results, and the local validation runbook begins with read-only request evidence inspection; ambiguous states explicitly prohibit automatic overwrite or retry.
23. P3-181 complete: real WPS Writer/Spreadsheet saves on disposable files were interrupted before main ledger commit; retained current/backup artifacts and hashes show ambiguity, CLI/MCP agreed, and same-ID retry did not alter either saved source.
24. P3-182 complete: a bounded, read-only verifier checks both retained manifests and file hashes, rejects missing/malformed/redirected evidence, and reports the two-component result through local handoff; the current workspace passed.
25. P3-183 complete: package creation now rejects incomplete or changed recovery evidence before rebuilding; six valid generated files are included and compared byte-for-byte in package readiness. The current local package passed 6/6 comparisons.
26. P3-184 complete: the real portable package was extracted into a fresh in-workspace directory and its own packaged source independently verified both recovered Writer/Spreadsheet manifests and hashes; a different-root extraction test also passed.
27. P3-185 complete: real WPS filled a uniquely paired table-cell bookmark on a disposable DOCX while adjacent runs, neighbor cell, body paragraphs, and backup identity remained intact; no public mutation scope changed.
28. P3-186 complete: guarded public table-cell bookmark fill passed 356 default tests (30 skipped), one real WPS temporary-file test, and refreshed Writer parity 7/7 and 4/4; scope remains a unique same-paragraph bookmark in a direct-body cell.
29. P3-187 complete: semantic table topology readback rejects a changed merge while preserving expected text; real WPS retained horizontal/vertical merges, multiple cell paragraphs, table style, and tested adjacent/target run formatting. Default tests passed 358 (31 skipped).
30. P3-188 complete: real WPS converted a relationship hyperlink and simple merge field to complex fields; normalized target/instruction/display text survived two fills. Offline guards reject range overlap before backup and changed anchor, relationship target, or field instruction after save. Default tests passed 362 (32 skipped).
31. P3-189 complete: missing hyperlink targets, empty instructions, orphaned separators, unclosed and nested complex fields are rejected before backup/WPS; valid neighbors pass repeated WPS writes. Default tests passed 363 (32 skipped).
32. P3-190 complete: real WPS retained the inline image drawing structure, extent, object description, relationship target, and image hash beside a table bookmark; overlap rejection and relationship-change regressions passed. Default tests passed 366 (33 skipped).
33. P3-191 complete: a positioned/cropped anchor and two cropped inline images retained drawing trees, image targets, and hashes through real WPS; default tests passed 367 (34 skipped), and all five WPS table tests passed.
34. P3-192 complete: two anchors with distinct relative heights and positions retained stacking rank, crop, relationship targets, and image hashes through real WPS save; default tests passed 367 (34 skipped).
35. P3-193 complete: rendered PDF image masks before and after WPS save are pixel-identical for the overlapping red/blue anchor fixture, with overlap order verified.
36. P3-194 complete: column/paragraph and page/page anchor masks remained pixel-identical through WPS bookmark fill; page-relative coordinates were clipped at the table-cell boundary by `layoutInCell`. Character-relative positioning drifted with glyph width and is rejected before backup.
37. P3-195 complete: WPS clamps out-of-cell anchors to the cell edge; with `layoutInCell` off, negative page-relative positioning is raster-clipped to 144x108 pixels. None, square, and top-and-bottom wrapping, crop semantics, and adjacent text bounds remain stable through bookmark fill.
38. P3-196 complete: a multi-page WPS table-bookmark fixture retained page count, PREFACE/AFTER-TABLE page and character bounds, drawing semantics, and pixel-identical full-page raster images.
39. P3-197 complete: a red anchor on page one and a blue table anchor on a later page retained expected visibility, relativeHeight ranking, marker page/character bounds, full-page raster output, and per-color masks through WPS bookmark fill.
40. P3-198 complete: diamond wrapPolygon paths using tight and through modes retained DrawingML vertices, rendered page raster, extracted text, and table-bookmark read-back through real WPS save.
41. P3-199 complete: real WPS preserved left/right/largest wrapText, asymmetric four-direction distances, long wrapped paragraph text, and full-page raster output; drawing snapshots expose each distance.
42. P3-200 complete: tight/through missing polygon, too few vertices, out-of-range coordinates, and negative distances are rejected before backup/WPS with unchanged target bytes; 12 Writer WPS integrations pass.
43. P3-201 complete: concave L-shaped tight/through paths retain DrawingML, text, and WPS raster; self-intersecting and zero-area paths are rejected before backup with unchanged bytes; 13 Writer WPS integrations pass.
44. P3-202 complete: eight tight/through combinations of both winding directions and explicit/implicit closure pass real WPS bookmark fill with each input's own DrawingML, text, and raster stable before/after. WPS renders an explicitly repeated terminal start vertex differently from implicit closure, so those forms are not claimed equivalent.
45. P3-203 complete: four cyclic start vertices of a concave tight/through outline each retain their raw DrawingML sequence, text, and individual raster through WPS fill. Different starts produce different PDF rasters, so cyclic vertex normalization is unsafe.
46. P3-204 complete: adding collinear midpoints to a concave outline changes both tight and through WPS rasters; each source variant independently preserves its raw DrawingML, text, and raster through save. Collinear points must not be simplified.
47. P3-205 complete: valid one-unit adjacent points and coordinates near 1/21599 bounds pass offline checks; four tight/through real-WPS round-trips retain DrawingML, text, and PDF rasters.
48. P3-206 complete: a 120/21600 near-collinear midpoint offset is pixel-identical to a straight edge at 1.5x PDF raster; tight/through files each preserve exact vertices and their own raster through WPS save. This result is resolution-bound and does not authorize tolerant vertex normalization.
49. P3-207 complete: at 4x PDF raster, straight, 120/21600-offset, and 600/21600-offset outlines have identical page pixels in tight/through for this fixture; each exact DrawingML input remains stable through WPS. This is fixture/path-specific, not a claim of geometric semantic equivalence.
50. P3-208 complete: +10800 and whitespace/leading-zero integer lexemes normalize to one numeric snapshot and pass WPS round-trip; decimal and empty coordinates are rejected before backup/COM with unchanged DOCX bytes.
51. P3-209 complete: WPS tight/through fixtures cover valid 0/21600 endpoints; a 200-digit integer is rejected before backup/WPS with unchanged bytes.
52. P3-210 complete: coordinate snapshots and preflight share an ASCII XML integer parser; sign/leading-zero/XML whitespace spellings normalize, while Unicode digits, decimals, empty strings, and 200-digit out-of-range values reject before backup/WPS with unchanged bytes.
53. P3-211 complete: tab/newline XML attribute whitespace folds to the canonical integer snapshot; NBSP is rejected before backup/WPS with unchanged bytes.
54. P3-212 complete: -0/+00 normalize to numeric zero; four sign/leading-zero/whitespace variants preserve semantics, text, and raster through WPS bookmark fill.
55. P3-213 complete: repeated signs, sign-only values, and embedded whitespace reject before backup/WPS with unchanged target bytes.
56. P3-214 complete: -1 rejects before backup/WPS; -0 normalizes to zero and passes WPS; 0/21600 endpoints are covered by tight/through fixtures.
57. P3-215 complete: distances share the ASCII integer parser/snapshot normalizer; legal sign/leading-zero/XML-whitespace variants round-trip through WPS, while Unicode digits, decimal, empty, and negative values reject before backup.
58. P3-216 complete: distances require nonnegative twip alignment and Word signed-32 range; 2147483640 passes real WPS round-trip, while nonaligned, signed-32/UInt32 overflow, and 200-digit values reject before backup.
59. P3-217 done: omitted anchor distances normalize to measured WPS defaults (top/bottom 0, left/right 114300 EMU); all five wrap types pass real WPS save/readback with stable per-document text and raster.
60. P3-218 done: omitted distances with left/right/largest wrapText pass real-WPS bookmark fills with stable snapshot, PDF text, and raster.
61. P3-219 done: three mixed explicit/omitted distance combinations pass real WPS; explicit values remain intact and each omitted side receives its measured WPS default.
62. P3-220 done: omitted wrapText on square wrapping normalizes to explicit bothSides and passes a stable real-WPS fill/readback.
63. P3-221 done: tight/through omitted wrapText snapshots match explicit bothSides and pass real-WPS bookmark-fill text/raster checks.
64. P3-222 done: top_and_bottom omitted wrapText matches explicit bothSides and passes real-WPS bookmark-fill text/raster checks.
65. P3-223 done: WPS rewrites top_and_bottom left/right/largest to bothSides; preflight now rejects these combinations before backup/COM without changing file bytes.
66. P3-224 done: WPS preserves left/right/largest on wrapNone with stable DrawingML and PDF output.
67. P3-225 done: invalid wrapText enum on wrapNone rejects in preflight with unchanged bytes and no backup/COM.
68. P3-226 done: invalid wrapText values on all five wrap elements reject pre-backup with unchanged bytes and no COM call.
69. P3-227 done: wrong-case, padded, and empty wrapText values reject before mutation with unchanged source bytes.
70. P3-228 done: tight/through left/right/largest values all survive WPS with stable post-fill PDF output.
71. P3-229 done: wrapNone left/right/largest produce identical WPS PDF text and page rasters in the current fixture.
72. P3-230 done: wrapNone left/right/largest remain distinct in semantic snapshots despite P3-229 raster equivalence.
73. P3-231 done: omitted and explicit bothSides on wrapNone retain distinct snapshots but render to identical WPS PDF output.
74. P3-232 done: all five wrap types pass real WPS with both wrapText and four-side distances omitted.
75. P3-233 done: all five wrap types retain explicit distT=635 with omitted wrapText and normalize other distances correctly.
76. P3-234 done: explicit distB/L/R survive WPS with omitted wrapText; omitted sides use directional defaults.
77. P3-235 done: a 30-case matrix covers five wrap types and omitted/legal/invalid wrapText values.
78. P3-236 done: square+tight multiple anchors with omitted defaults normalize and pass real WPS bookmark fill.
79. P3-237 done: square/tight anchors independently preserve explicit distT=635 and distL=1270 with other distances defaulted.
80. P3-238 done: square:left and tight:largest remain distinct per drawing through real-WPS bookmark fill.
81. P3-239 done: one unsupported second anchor blocks the whole multi-anchor mutation before backup/COM.
82. P3-240 done: multi-anchor preflight details identify drawing 1 and its unsupported top_and_bottom wrapText.
83. P3-241 done: CLI/MCP responses retain drawing_index and unsupported wrap reason details.
84. P3-242 done: drawing diagnostic indices match snapshot order including preceding inline drawings.
85. P3-243 done: multiple unsupported drawings are all listed with distinct indices and wrapText reasons.
86. P3-244 done: CLI/MCP preserve the complete ordered multi-error list with inline-adjusted indices.
87. P3-245 done: unsupported-wrap diagnostics consistently use BOOKMARK_SCOPE_UNSUPPORTED with structured details; CLI/MCP retain code, details, and failed validation, and pre-backup rejection leaves source bytes unchanged. Full suite 409 passed/65 skipped; local release gates passed 5/5 without remote Git.
88. P3-246 done: all unresolved drawing diagnostic branches include stable zero-based drawing_index; invalid-wrap detail survives CLI/MCP and source remains unchanged. Default suite 410 passed/65 skipped; real-WPS structure/nested parity 7/7 and 4/4; local release gates 5/5.
89. P3-247 done: a 13-case diagnostic matrix checks drawing_index and reason-specific schema fields, including relationship failures. Default suite 411 passed/65 skipped.
90. P3-248 done: missing-image relationship ID, package-relative target, and drawing index survive preflight/CLI/MCP; no workspace path or package contents leak, and source bytes remain unchanged. Default suite 412 passed/65 skipped.
91. P3-249 done: external image links remain metadata-only, produce no network calls, and leave the source unchanged. Default suite 413 passed/65 skipped.
92. P3-250 done: missing, malformed, and 64 KiB external targets plus internal ../ target are handled without network access or package-external reads; external targets do not trigger media-part reads. Default suite 414 passed/65 skipped.
93. P3-251 done: omitted/Internal targets read package media, External targets do not, and unknown TargetMode returns indexed invalid_relationship_target_mode without media reads. Default suite 415 passed/65 skipped; WPS parity 7/7 and 4/4.
94. P3-252 done: relative/rooted package targets resolve, missing targets have stable indices, and normalized package-root escapes are rejected without reading even a matching malicious ZIP entry. Default suite 416 passed/65 skipped; real-WPS parity 7/7 and 4/4.
95. P3-253 done: unknown TargetMode and package-root escape diagnostics preserve code/reason/index/details across direct preflight, CLI, and MCP; backup/COM are not called and source bytes remain unchanged. Default suite 417 passed/65 skipped.
96. P3-254 done: mixed unknown-mode and package-root relationship failures remain ordered by drawing index and complete across preflight/CLI/MCP; backup/COM are not called. Default suite 418 passed/65 skipped.
97. P3-255 done: relationship ID, target, and mode values in unresolved diagnostics are capped at 256 characters with explicit truncation markers; repeated parses are identical and short/valid values retain existing semantics. Default suite 419 passed/65 skipped; real-WPS parity 7/7 and 4/4.
98. P3-256 done: truncated relationship ID/target/mode values and markers survive direct preflight, CLI, and MCP unchanged; backup/COM are not called. Default suite 420 passed/65 skipped.
99. P3-257 done: multi-drawing mixed long/short relationship failures preserve order, per-index truncation flags, and exact details through direct/CLI/MCP. Default suite 421 passed/65 skipped.
100. P3-258 done: 150 oversized relationship diagnostics are capped at 127 detailed entries plus one omitted-count summary (128 total), under 120 KB and deterministic. Default suite 422 passed/65 skipped; real-WPS parity 7/7 and 4/4.
101. P3-259 done: the 128-entry details list and omitted-count summary survive direct preflight/CLI/MCP, while validation remains failed and backup/COM are not invoked. Default suite 423 passed/65 skipped.
102. P3-260 done: exact 127/128/129 issue boundaries retain all details at or below cap and report omitted_count=2 above it. Default suite 424 passed/65 skipped.
103. P3-261 next: verify worst-case serialized diagnostic byte size through CLI/MCP.
45. Later: broaden visual/semantic fidelity and WPS version coverage while preserving independent failures and artifact provenance.

These milestones are actionable entirely in the local workspace. Offline parsing fixes
must remain labelled as file-library behavior; WPS end-to-end validation is a
separate gate, not implied by offline tests.
