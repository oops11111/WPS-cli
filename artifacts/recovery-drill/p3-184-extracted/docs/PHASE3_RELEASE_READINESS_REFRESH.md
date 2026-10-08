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

P3-151 through P3-160 established request evidence, safe/release regression gates, and ordered local package checks. P3-161 through P3-169 established bounded offline Writer structure/bookmark inspection, real read-only WPS corroboration, and two packaged parity reports. P3-170 rejects revision/text-box paragraphs and unreachable bookmark offsets; a controlled table-cell bookmark across ordinary, hyperlink, and tab runs matched read-only WPS, CLI, and MCP without changing its fixture. P3-171 binds both parity reports to current implementation hashes; real WPS structure and nested runs passed 7/7 and 4/4. P3-172 adds registration identity evidence and mutation backup preflight against file replacement or external changes. P3-173 fixes false Writer bookmark fill readback failure when WPS appends an empty paragraph after a terminal table. P3-174 extends source/backup identity checks to all Writer, Spreadsheet, and Presentation COM mutations, before COM and after readback. P3-175 adds cooperative workspace/document-ID locking across Agent mutation and re-registration; real WPS Writer/Spreadsheet/Presentation writes passed. P3-176 adds bounded state locks and atomic replacement for shared document/operation JSON, with 48-record cross-process tests. P3-177 records post-save file identity for safe replay repair after registration refresh failures and fixes transient Windows lock/read contention exposed by 10 stress runs. P3-178 blocks automatic reapplication of a changed source when only a derived backup exists. The full default suite ran 353 tests (29 skipped, no failures), and opt-in real WPS Writer/Spreadsheet checks passed 2/2. The MCP catalog has 81 tools (21 document-mutating, 18 WPS-required, 60 non-document-mutating). P3-179 adds read-only CLI/MCP inspection of main operation, derived backup, and current file identity; the 81-tool stdio MCP smoke passed. P3-180 adds state-specific non-destructive recovery guidance to CLI/MCP inspection and the validation runbook. P3-181 retained two real WPS disposable-file interruption drills with matching current/backup hashes and blocked same-ID retry; both opt-in tests passed. P3-182 verifies retained Writer/Spreadsheet manifests and bytes through a bounded local handoff check; current evidence passed. P3-183 includes and verifies all six generated recovery-drill files in the local portable package; current readiness passed. P3-184 is next: verify the evidence after extraction into a clean workspace. These gates do not certify full PRD completion or exclude external editors.
