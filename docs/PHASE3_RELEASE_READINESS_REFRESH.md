# Phase 3 Release Readiness Refresh

## Current Status

This file records the earlier P3-094 checkpoint. P3-114 is now implemented locally; final regression and package evidence is regenerated during this task.

Evidence:

- Unit tests: 185 passed; 11 opt-in integrations skipped by default discovery.
- Safe regression: 18/18 scenarios passed on 2026-10-07 after P3-094.
- MCP catalog drift: P3-165 adds opt-in Writer structure parity audit; current surface is 81 tools (21 document-mutating, 18 WPS-required, 60 non-document-mutating).
- Documentation freshness: passed with no stale current-state references.
- Local sync package readiness: verified after P3-094; local archive only, no remote upload.
- Latest safe artifact: `artifacts\regression\safe\regression-run-20261007T114633742276Z-a4d725f8-ae5b-49eb-9612-64e176d3de87.json`.
- The latest local sync package SHA-256 is available from `project-status` to avoid embedding a self-changing archive hash in this document.
- WPS regression: 4/4 scenarios passed.
- MCP tool surface: 81 tools.
- Mutating tool security audit: 21 mutating tools covered.
- Additional local Writer WPS integration: six replacement cases and one bookmark fill passed on 2026-10-07.
- Spreadsheet worksheet rename, create, visibility/delete and copy WPS integrations: 4/4 passed on 2026-10-07.
- P3-080 adds read-only spreadsheet inspection that reports formulas, saved cached values, in-memory recalculated values, and WPS-displayed text separately.
- P3-081 keeps spreadsheet-read values unchanged and adds a parallel per-cell format metadata matrix for dates, percentages, currency and empty cells; see `P3_SPREADSHEET_READ_FORMATS.md`.
- P3-082 adds pre-open finite-range validation and a 10,000-cell read/inspect cap; see `P3_SPREADSHEET_RANGE_GUARDRAILS.md`.
- P3-083 adds table and grouped-shape text objects to presentation snapshots; see `P3_PRESENTATION_TEXT_OBJECT_COVERAGE.md`.
- P3-084 adds WPS replacement traversal for grouped shapes and table cells with exact slide read-back; see `P3_PRESENTATION_NESTED_REPLACE.md`.
- P3-085 preserves replacement character formatting and P3-086 verifies read-back per object/paragraph/cell; see `P3_PRESENTATION_FORMAT_PRESERVATION.md` and `P3_PRESENTATION_OBJECT_READBACK.md`.
- P3-087 binds tracked mutation request IDs to commands and arguments; see `P3_MUTATION_IDEMPOTENCY.md`.
- P3-088 applies finite range and cell-count limits to spreadsheet writes before backup/WPS; see `P3_SPREADSHEET_WRITE_GUARDRAILS.md`.
- P3-089 adds read-only worksheet inventory and P3-090 adds transactional worksheet rename; see `P3_SPREADSHEET_SHEETS.md` and `P3_SPREADSHEET_RENAME_SHEET.md`.
- P3-091 adds transactional worksheet creation through CLI/MCP with Excel title validation, insertion order, backup, WPS save and ordered read-back.
- P3-092 adds transactional worksheet visibility changes through CLI/MCP, preserving at least one visible worksheet and validating ordered state read-back.
- P3-093 adds transactional worksheet deletion through CLI/MCP with final-sheet protection, backup and ordered read-back.
- P3-094 adds transactional worksheet copying through CLI/MCP with validated names and order, backup, WPS native copy and sampled cell read-back.
- P3-095 adds transactional worksheet tab color set/clear through CLI/MCP with strict hex validation, backup and WPS plus independent read-back.
- P3-096 adds normalized worksheet tab colors to the existing read-only inventory without launching WPS or changing the workbook.
- P3-097 adds read-only protection state and a bounded locked-cell count; oversized protected sheets report a truncated scan instead of doing unbounded work.
- P3-098 documents and tests the worksheet inventory's 100,000-cell protection scan limit and explicit truncation result.
- P3-099 adds bounded populated-cell and formula counts to that same inventory scan contract.
- P3-100 adds frozen-pane and autofilter range metadata to the no-WPS worksheet inventory.
- P3-101 adds a stable, capped merged-range list with total count and truncation status.
- P3-102 exposes capped workbook- and worksheet-scoped defined names with stable ordering and stored targets.
- P3-103 exposes stored workbook calculation flags without recalculating or saving.
- P3-104 verifies macro-enabled workbook inventory with VBA preservation and explicit auxiliary archive close.
- P3-105 adds print area/title, page orientation and paper-size metadata to worksheet inventory.
- P3-106 adds sorted, bounded manual page-break positions and truncation counts.
- P3-107 adds an end-to-end CLI envelope check and confirms the spreadsheet inventory MCP tool remains read-only and WPS-free.
- P3-108 adds bounded data-validation rule summaries with total counts and truncation flags.
- P3-109 adds bounded conditional-formatting summaries with range, type, operator and priority.
- P3-110 streams OOXML ignored-error metadata into a capped read-only inventory with total count/truncation.
- P3-111 verifies deterministic end-to-end CLI inventory output for xlsx/xlsm and unchanged source hashes.
- P3-112 reconciles inventory CLI/MCP contracts and corrects the PRD gap audit for completed worksheet management.
- P3-113 verifies 1900/1904 date handling, locale-tagged formats and actual WPS display behavior; host-locale variation is documented separately from file-library evidence.

## Latest Artifacts

Safe regression:

```text
artifacts\regression\safe\regression-run-20261007T045203762023Z-regression-p3-070-package-refresh-safe.json
artifacts\regression\safe\regression-run-20261007T102453019354Z-regression-p3-079-safe-final.json
```

WPS regression:

```text
artifacts\regression\wps\regression-run-20261003T105030651877Z-regression-writer-table-p3-013-wps-003.json
```

Key WPS outputs:

- `fixtures\phase3\phase0_calculation_smoke.xlsx`
- `fixtures\phase3\writer_smoke_copy.docx`
- `fixtures\phase3\writer_smoke.pdf`
- `fixtures\phase3\writer_table_regression_smoke.docx`

## Completed Since P3-011

- Added Writer table cell update: `writer-table-write`.
- Added Writer table MCP tool: `wps_agent_writer_table_write`.
- Added repeatable Writer table WPS smoke: `writer-table-smoke`.
- Added Writer table smoke MCP tool: `wps_agent_writer_table_smoke`.
- Hardened `regression-run` so subcommand exceptions become structured scenario failures.
- Hardened `calc-smoke` with timeout control, structured timeout errors, output overwrite protection, and input/output same-path rejection.
- Added read-only WPS process diagnostics: `wps-process-audit`.
- Added read-only local cleanup planning: `cleanup-plan`.
- Added read-only local project status summary: `project-status`.
- Added read-only MCP tool catalog summary: `mcp-catalog-snapshot`.
- Added read-only MCP catalog drift guard: `mcp-catalog-drift`.
- Added read-only regression evidence summary: `regression-evidence`.
- Added read-only regression history summary: `regression-history`.
- Added read-only local handoff summary: `local-handoff-summary`.
- Added read-only artifact retention summary: `artifact-retention-summary`.
- Added read-only local validation runbook: `validation-runbook`.
- Added read-only documentation freshness guard: `documentation-freshness`.
- Added read-only sync package inspection: `sync-package-inspect`.
- Added read-only sync package content summary: `sync-package-summary`.
- Added read-only sync package manifest listing: `sync-package-manifest`.
- Added read-only sync package coverage check: `sync-package-coverage`.
- Added read-only sync package readiness summary: `sync-package-readiness`.

## Remaining Risks

- WPS COM behavior is still local-desktop dependent.
- Process audit found WPS-related processes can remain after desktop automation; the project now reports them but does not automatically terminate them.
- Real third-party desktop MCP client integration still needs user-side import of `config\mcp_client_config.example.json`.
- The user confirmed development should continue in the current local workspace without remote Git.

## Handoff Steps

1. Preserve `src`, `tests`, `config`, `docs`, `fixtures`, `scripts`, and latest `artifacts\regression` outputs.
2. For CI-style validation, run the safe profile:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

3. For local Windows desktop validation with WPS installed, run:

```powershell
$env:PYTHONPATH='src'
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps
python -m wps_ai_agent_cli wps-process-audit
```

4. For local handoff, regenerate the portable archive with `cloud-sync-package`, then inspect, summarize, list, coverage-check, and readiness-check it with `sync-package-inspect`, `sync-package-summary`, `sync-package-manifest`, `sync-package-coverage`, and `sync-package-readiness`; remote Git is not required for the current workflow.

## Next Task

2026-10-09 update: P3-255 bounds relationship diagnostic ID/target/mode fields at 256 characters with explicit truncation markers; 419 default tests passed/65 skipped and real-WPS parity passed 7/7 and 4/4. P3-256 is next for preflight/CLI/MCP propagation of the bounded diagnostic fields.
2026-10-09 follow-up: P3-256 confirms truncated relationship IDs, targets, modes, and markers remain unchanged through direct preflight, CLI, and MCP; 420 default tests passed/65 skipped. P3-257 is next for multi-drawing ordering and index isolation.
2026-10-09 follow-up: P3-257 confirms truncation metadata stays attached to the correct drawing index across multiple errors through direct/CLI/MCP; 421 default tests passed/65 skipped. P3-258 is next for total diagnostic payload bounds.
2026-10-09 follow-up: P3-258 caps unresolved drawing diagnostics at 128 entries (127 details plus omission summary); a 150-error stress fixture stayed under 120 KB. Default suite 422 passed/65 skipped; WPS parity 7/7 and 4/4. P3-259 is next for summary propagation through mutation interfaces.
2026-10-09 follow-up: P3-259 confirms the 128-entry details/summary response survives direct/CLI/MCP and remains a failed validation; 423 default tests passed/65 skipped. P3-260 is next for exact cap-boundary counts.
2026-10-09 follow-up: P3-260 verifies 127/128/129 diagnostics with exact omission counts; 424 default tests passed/65 skipped. P3-261 is next for worst-case serialized byte bounds.
2026-10-09 MCP hardening continuation: P3-275 validates JSON-RPC envelopes (33 MCP tests; full 443/65); P3-276 aligns legacy initialize to `2025-11-25` (35; full 445/65); P3-277 enforces initialize lifecycle (36; full 446/65); P3-278 rejects duplicate JSON members (38; full 448/65); P3-279 bounds stdio lines (40; full 450/65); P3-280 rejects non-standard numeric constants (42; full 452/65); P3-281 enforces unique request IDs (43; full 453/65); P3-282 aligns outputSchema (54; full 455/65); P3-283 maps unknown tools to protocol errors (64; full 457/65); P3-284 validates MCP arguments against the live catalog schema (67; full 460/65); P3-285 audits configured MCP clients through one persistent stdio lifecycle session, with all 81 tools discovered over two pages (8 audit tests; full 462/65); P3-286 implements legacy ping with an empty result, invalid-param handling, and initialized persistent-stdio coverage (43 MCP server/config audit tests; full 464/65). P3-287 is next: validate configured-client tool descriptors and their schemas.
P3-286 release checks: safe regression passed 15/15; sync package coverage/readiness, documentation freshness, project status, and workspace health passed. Package SHA256: `3A1DED1C75D4E93E024DCBF2C88B5296C89FECD5620831BCEBABEAA7D56E88BC`.
P3-287 adds per-page MCP descriptor/schema validation with capped field diagnostics; configured audit tests: 10 passed; full suite: 466 passed/65 skipped. P3-288 is next: bound stdout line and response queue buffering for configured MCP audit subprocesses.
P3-287 safe regression passed 15/15 with the next-task manifest check aligned to P3-288.
P3-288 bounds configured audit stdout lines to 1 MiB, stdout queue capacity to 8 responses, and retained stderr to 8,192 characters; over-limit subprocess cleanup, stderr flood drain, and normal audit tests passed. Audit tests: 12; full suite: 468/65. P3-289 is next for malformed JSON/UTF-8/deep response handling.
P3-288 release checks: safe regression passed 15/15; package coverage/readiness, documentation freshness, and workspace health passed.

2026-10-08 addendum: P3-213 rejects repeated signs, sign-only coordinates, and embedded whitespace before backup with unchanged DOCX bytes. P3-214 rejects negative coordinates while retaining negative zero and inclusive endpoints. P3-215 applies strict numeric lexical handling to floating distances. P3-216 enforces 635-EMU/twip alignment and Word signed-32 range; the maximum aligned value passes WPS and overflow rejects before backup. P3-217 normalizes omitted WPS defaults (distT/B=0, distL/R=114300 EMU) and passes real WPS round trips for all five wrap types. P3-218 verifies omitted distances with left/right/largest wrapText through real-WPS bookmark fills. P3-219 verifies three mixed explicit/omitted directional combinations through WPS. P3-220 normalizes square-wrap omitted wrapText to bothSides and passes real WPS. P3-221 verifies tight/through omitted wrapText through WPS. P3-222 verifies top_and_bottom omitted wrapText through WPS. P3-223 found WPS rewrites top_and_bottom left/right/largest to bothSides; preflight now rejects these before backup/COM. P3-224 confirms WPS preserves left/right/largest on wrapNone. P3-225 rejects invalid wrapText enums on wrapNone. P3-226 rejects invalid enum values across all five wrap types. P3-227 rejects wrong-case, padded, and empty wrapText values before backup. P3-228 verifies all tight/through x left/right/largest combinations through WPS. P3-229 confirms wrapNone left/right/largest export identical text and page rasters. P3-230 confirms snapshots retain all three distinct values. P3-231 confirms omitted and explicit bothSides on wrapNone have distinct snapshots but identical PDF output. P3-232 verifies combined omitted wrapText and four distances for all five wrap types through WPS. P3-233 verifies all five wrap types retain explicit distT=635 with omitted wrapText; P3-234 verifies explicit distB/L/R similarly and defaults the other sides. P3-235 adds a 30-case wrapText/wrap-type acceptance matrix. P3-236 verifies per-drawing defaults for two anchors with different wrap types. P3-237 verifies independently mixed explicit distances across square/tight anchors. P3-238 verifies square:left and tight:largest remain isolated per drawing through WPS. P3-239 verifies an unsupported second anchor rejects the whole DOCX pre-mutation. P3-240 exposes offending drawing index and wrap reason; P3-241 confirms CLI/MCP preserve diagnostic details. P3-242 confirms indices match snapshot order with a preceding inline drawing. P3-243 confirms every unsupported drawing is listed with its own index. P3-244 verifies CLI/MCP preserve ordered multiple errors with inline-adjusted indices. P3-245 confirms error code/details, CLI/MCP failed status, and pre-backup byte preservation. P3-246 adds drawing_index to every unresolved drawing diagnostic; real-WPS structure/nested parity passed 7/7 and 4/4. P3-247 covers 13 unresolved reasons and reason-specific fields; default suite: 411 passed/65 skipped. P3-248 confirms missing-image relationship context survives CLI/MCP without leaking workspace/package data; source remains unchanged and 412 tests pass (65 skipped). P3-249 confirms external image targets are metadata-only with no network calls; default suite 413 passed/65 skipped. P3-250 covers missing, malformed, 64 KiB external, and internal ../ targets with no network or package-external reads; default suite 414 passed/65 skipped. P3-251 validates omitted/Internal/External/unknown TargetMode with WPS parity 7/7 and 4/4 and default suite 415/65. P3-252 confirms relative/rooted resolution, stable missing-target diagnostics, and package-root escape rejection without reading malicious ZIP entries; 416 tests passed/65 skipped, WPS parity 7/7 and 4/4. P3-253 verifies unknown-mode and package-root error serialization across preflight/CLI/MCP; default suite 417 passed/65 skipped. P3-254 verifies ordered aggregation of mixed relationship errors through preflight/CLI/MCP; default suite 418 passed/65 skipped. P3-255 is next: audit relationship diagnostic field bounds and determinism.

Latest local evidence (2026-10-08): P3-202 through P3-212 show that winding/closure variants individually round-trip through WPS, but explicit closure, cyclic start vertices, and collinear intermediate vertices can change rendered wrap output. Raw vertex sequences must not be normalized or simplified. P3-205 passed four near-degenerate/boundary round-trips. P3-206/207 found 120/600-unit near-collinear offsets pixel-identical through 4x for this fixture while exact DrawingML remains stable; this does not prove semantic equivalence. P3-208 normalized integer coordinate lexemes and rejected malformed coordinates; P3-209 confirmed endpoints and huge-integer preflight; P3-210 enforces ASCII XML integer syntax; P3-211 folds XML whitespace and rejects NBSP; P3-212 normalizes signed zero through WPS. The default suite most recently passed 386 tests (48 skipped); P3-211 local release gates passed 5/5 with remote Git unused. P3-213 is next for malformed sign combinations.

P3-151 through P3-160 established request evidence, safe/release regression gates, and ordered local package checks. P3-161 through P3-169 established bounded offline Writer structure/bookmark inspection, real read-only WPS corroboration, and two packaged parity reports. P3-170 rejects revision/text-box paragraphs and unreachable bookmark offsets; a controlled table-cell bookmark across ordinary, hyperlink, and tab runs matched read-only WPS, CLI, and MCP without changing its fixture. P3-171 binds both parity reports to current implementation hashes; real WPS structure and nested runs passed 7/7 and 4/4. P3-172 adds registration identity evidence and mutation backup preflight against file replacement or external changes. P3-173 fixes false Writer bookmark fill readback failure when WPS appends an empty paragraph after a terminal table. P3-174 extends source/backup identity checks to all Writer, Spreadsheet, and Presentation COM mutations, before COM and after readback. P3-175 adds cooperative workspace/document-ID locking across Agent mutation and re-registration; real WPS Writer/Spreadsheet/Presentation writes passed. P3-176 adds bounded state locks and atomic replacement for shared document/operation JSON, with 48-record cross-process tests. P3-177 records post-save file identity for safe replay repair after registration refresh failures and fixes transient Windows lock/read contention exposed by 10 stress runs. P3-178 blocks automatic reapplication of a changed source when only a derived backup exists. The full default suite ran 377 tests (41 skipped, no failures), and opt-in real WPS Writer/Spreadsheet checks passed 2/2. The MCP catalog has 81 tools (21 document-mutating, 18 WPS-required, 60 non-document-mutating). P3-179 adds read-only CLI/MCP inspection of main operation, derived backup, and current file identity; the 81-tool stdio MCP smoke passed. P3-180 adds state-specific non-destructive recovery guidance to CLI/MCP inspection and the validation runbook. P3-181 retained two real WPS disposable-file interruption drills with matching current/backup hashes and blocked same-ID retry; both opt-in tests passed. P3-182 verifies retained Writer/Spreadsheet manifests and bytes through a bounded local handoff check; current evidence passed. P3-183 includes and verifies all six generated recovery-drill files in the local portable package; current readiness passed. P3-184 extracted the real local package into a clean in-workspace directory and independently verified both recovery evidence sets using the extracted source. P3-185 confirmed a bounded table-cell bookmark fill with real WPS on a disposable DOCX without widening the public command. P3-186 added bounded direct-table-cell bookmark fill with backup, readback, replay, and real WPS verification; the default suite passed 356 tests (30 skipped), and current Writer parity passed 7/7 and 4/4. P3-187 added semantic table topology readback; real WPS horizontal/vertical merge, multi-paragraph, and styled table tests passed, with 358 default tests (31 skipped) and current parity 7/7 and 4/4. P3-188 verified normalized hyperlink and merge-field semantics through two real WPS table bookmark fills; 362 default tests passed (32 skipped), with current Writer parity 7/7 and 4/4. P3-189 rejects missing hyperlink targets, empty instructions, orphaned separators, unclosed fields, and nested fields before backup; valid neighbors pass repeated real-WPS writes. Default tests passed 363 (32 skipped), Writer parity 7/7 and 4/4. P3-190 added drawing subtree, image target, and image-byte readback; a real-WPS inline image fixture passed, and drawing overlap is rejected before backup. Default tests passed 366 (33 skipped), current Writer parity 7/7 and 4/4. P3-191 verified positioned/cropped anchor drawings and two cropped inline images through real WPS; 367 default tests passed (34 skipped), all five WPS table tests passed, and Writer parity passed 7/7 and 4/4. P3-192 verified two floating anchors retain relative stacking rank, crop, position, media targets, and hashes through real WPS; 367 default tests passed (34 skipped), current Writer parity 7/7 and 4/4. P3-193 compares rendered PDF image masks before and after WPS save for overlapping floating drawings; fixture masks are pixel-identical and overlap order is verified. P3-194 verified pixel-identical WPS raster masks for column/paragraph and page/page anchors; page-relative coordinates clip at the table-cell boundary under layoutInCell, while character-relative anchors drift with preceding glyph width and are rejected before backup. P3-195 through P3-200 completed with 12/12 Writer table WPS integrations: cell-relative out-of-bounds anchors clamp to the cell edge, while layoutInCell=0 page-relative negative offsets produce a measured 144x108 raster clip. None, square, and topAndBottom wraps plus crop metadata retain drawing semantics and pixel masks; adjacent text bounds remain identical before/after fill. P3-196 preserved multi-page count, PREFACE/AFTER-TABLE marker page/character bounds, drawing semantics, and pixel-identical full-page rasters through bookmark fill. P3-197 verified a red first-page and blue later-page anchor retain visibility, stacking rank, marker geometry, full-page raster, and per-color masks through WPS bookmark fill. P3-198 retained tight/through diamond wrapPolygon geometry, page rasters, text, and bookmark read-back through WPS save. P3-199 verified WPS preservation of left/right/largest wrapText, asymmetric four-direction distances, long wrapped text, and full-page rasters; drawing snapshots expose all distances. P3-200 rejects missing/underspecified tight/through polygons, out-of-range vertices, and negative distances before backup with unchanged target bytes; all 12 WPS integrations and five local release gates pass. P3-201 next audits concave and self-intersecting wrap geometry. These gates do not certify full PRD completion or exclude external editors.
