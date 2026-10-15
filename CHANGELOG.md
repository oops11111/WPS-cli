# Changelog

All notable changes to `wps-ai-agent-cli`. The versioning rule and release steps are in `docs/RELEASING.md`.

## [Unreleased]

### Fixed

- `mcp-server` read the client's JSON-RPC requests in the system code page (GBK on Chinese Windows) instead of UTF-8, so every argument with characters outside ASCII reached the tools garbled: a Chinese document name, replacement text or path. An agent could not save the untitled document `文字文稿1`, which it named correctly. The CLI now reads stdin as UTF-8, as it already wrote stdout. 0.4.0 and earlier have this defect on Chinese Windows. Found by the P7-007 Windows evaluation; a test now runs the real `mcp-server` process with a GBK stdin.
- Closing an unchanged workbook (`restore-backup --close-in-wps` and the open-document commands' cleanup) failed on WPS 12.8 with `RPC_E_SERVERFAULT` when the workbook was reached through the Running Object Table. It now closes with no argument first, which cannot prompt because the workbook has no unsaved changes. Found by the P7-007 Windows evaluation.
- Text that WPS returns with characters outside ASCII came back garbled on Chinese Windows, for example the name of an untitled document (`文字文稿1`), so `save-as-open-document` could not be pointed at it. Windows PowerShell wrote the scripts' output in the console code page (GBK) and the CLI read it as UTF-8. Every PowerShell script and command now writes UTF-8. Found by the P7-007 Windows evaluation.
- `close_unchanged_document` (used by `restore-backup --close-in-wps`) reported `COM_OPERATION_FAILED` after closing a workbook on WPS 12.8, although the workbook was closed. When the close reports a failure, it now checks whether WPS still lists the document. Found by the P7-007 Windows evaluation.

## [0.4.0] - 2026-10-15

Phase 7: a failed write to a document open in WPS is undone inside WPS, and `validate-document` says what it needs.

### Added

- New error code `MUTATION_ROLLBACK_IN_WPS_FAILED`: the undo inside WPS did not happen or could not be confirmed. The message says what state the document is in and how to get back to the pre-write backup. The document is never closed, and it is not saved unless the undo read back as the original. Chart and shape selections in Spreadsheets are not undone this way and also return this code. (P7-001)

### Changed

- The eight open-document selection writes (Writer, Presentation and Spreadsheets selection replace, insert and delete) undo a failed write inside WPS. When WPS has saved the write but a later check rejects it, the command puts the original text or cells back in the same WPS instance with the inverse edit, reads them back, saves, and compares the saved file's content with the pre-write backup. It then returns `MUTATION_ROLLED_BACK` with `data.rollback.rolled_back_in_wps` set to `true`. Before, it tried to copy the backup over the file, which WPS holds, so these commands always ended in `MUTATION_ROLLBACK_BLOCKED` (seen in P6-008). The undo only changes the place the write changed, and only if that place still holds exactly what the write left there. (P7-001)
- `validate-document` (MCP `validate_document`) says what it needs. Agents kept calling it with only a `document_id`, as a general check, and got `INVALID_ARGUMENT` with `writer validation requires --contains.` (P6-008). The tool description now says it checks one expected value: `contains` for Writer, `cell` and `equals` for Spreadsheets. Each parameter says which component requires it, and the description says to use `snapshot_document` to read a document. The `INVALID_ARGUMENT` messages name the missing argument, give an example and point to `snapshot_document`. A cell that is not one A1 address, such as `Sheet1!B2`, is now `INVALID_ARGUMENT` instead of an unexpected error. `VALIDATION_FAILED` says what was compared: the text that was not found and that the match is exact, or the value the cell holds. (P7-006)

## [0.3.0] - 2026-10-15

Phase 6: the open-document commands work on documents the user opened in WPS the usual way, and their writes work on real WPS.

### Added

- Open-document commands (`open-documents`, selection read and edit, `save-open-document`, the exports, `restore-backup --close-in-wps`) reach a WPS that did not register its application object: when `GetActiveObject` finds nothing, they look for a document of the component in the Running Object Table and attach through its application, but only when it is WPS. Nothing is launched. The pre-open guard of the file-based write and conversion commands uses the same lookup, so it also sees a document open in such a WPS and refuses instead of opening it a second time. (P6-003)
- New error code `WPS_INSTANCE_NOT_AUTOMATABLE`. A WPS window of the component is running, but neither route reaches it, as with a WPS Writer opened by double-click on 12.8 (P5-011). The message gives the cause and the remedy: reopen the document with `wps.exe /Automation`. These commands answered `NO_RUNNING_WPS_INSTANCE` before. `open-documents` also reports such a component in `data.not_automatable` and `data.warnings` while listing the others. (P6-003)

### Fixed

- Open-document write commands (Writer, Presentation and Spreadsheets selection replace, insert and delete; `save-open-document`) always refused on real WPS with `DOCUMENT_HELD_OPEN`, in 0.2.0 too. Their backup began with the exclusive-share probe that file-based commands use. That probe always fails on a document that is open in WPS, which is what these commands work on. Their backup now only needs the file to be readable alongside WPS; WPS allows that. Found by the P6-008 Windows evaluation.
- `presentation-selection-replace` reported `VALIDATION_FAILED` on WPS 12.8 after a successful write. It read the new text back through the selection, which WPS moves after the assignment. It now checks the shape's whole text instead: the old text with exactly the selected part replaced. Found by the P6-008 Windows evaluation.

### Changed

- `writer-table-write`: a dry run also returns the table's `row_count`, `column_count` and `header_row`, so an agent can see the table in one call instead of probing cells. (P6-007)
- `writer-table-write`: the `CELL_NOT_FOUND` message gives the table's row and column counts, that rows and columns count from 1, and the header row, so an agent can correct the address in one step. (P6-007)

## [0.2.0] - 2026-10-14

First release. Phases 4 and 5 so far: in-CLI recovery for documents open in WPS, a WPS compatibility profile, an MCP failure contract for every tool, and a wheel that runs on its own.

### Added

- `restore-backup --close-in-wps` and the MCP `close_in_wps` argument: after a rollback blocked by an open document, close that document in WPS without saving and restore the backup, in one call. WPS must have no unsaved changes, otherwise the call refuses with `DOCUMENT_HAS_UNSAVED_CHANGES`. Without the flag nothing changes. (P4-009, P4-010)
- Agent evaluation: tasks can be marked `requires_wps` and are skipped without WPS; `--repeat N --min-passes M` runs each task N times; four WPS write tasks. (P4-004 to P4-006)
- Regression profile `compat`: open, save and PDF conversion for Spreadsheets and Presentation, part of the WPS compatibility matrix (`docs/COMPATIBILITY_MATRIX.md`). (P4-002)
- CI builds the wheel and the source distribution and keeps them as a workflow artifact. (P4-012)
- Pushing a tag `v<version>` publishes a GitHub Release with the wheel and the sdist, after checking the tag against the package version and running the safe regression profile from the built wheel. (P5-008)
- An installed wheel runs the safe regression profile on its own: the regression manifest, the MCP catalog guard and the MCP audit template ship inside the package and are used when the default `config/` paths do not exist. CI runs the safe profile from the installed wheel outside the repository. (P5-007)

### Changed

- The MCP `initialize` result reports the package version as `serverInfo.version`. It reported `phase2-prototype` before.
- The package version is defined only in `src/wps_ai_agent_cli/__init__.py`; `pyproject.toml` reads it from there.

### Fixed

- MCP `tools/call`: when a command fails, its error codes and messages (for example `DOCUMENT_HELD_OPEN`) are now in the tool result text and in `structuredContent.errors`. Before, both held an empty list and the codes were only in `structuredContent.mcp_call.response`, which agents do not read. Error details stay only in the nested response. Found by the P4-007 Windows evaluation.
- Commands without their own held-file check (for example `spreadsheet-read`, `spreadsheet-sheets`, `snapshot-document`, `batch-report`) raised `PermissionError` on a file held open by another handle, which MCP reported as `MCP_TOOL_EXECUTION_FAILED`. They now answer with a `DOCUMENT_HELD_OPEN` envelope. For commands that can change documents, the message points to `mutation-request-inspect` instead of saying nothing changed. Found by the P4-007 Windows evaluation.
- `batch-report` stopped at the first file held open by another handle. That file is now reported with `snapshot_status: "held"` and its `DOCUMENT_HELD_OPEN` error, the other files are reported as usual, and the summary counts it as `snapshot_held`. Validation still fails while any snapshot is missing. `snapshot-document` reports a held file as `DOCUMENT_HELD_OPEN` itself.
- `com-smoke` with pywin32 installed used a separate pywin32 branch that skipped the open and held-file checks; on real WPS it failed for presentations (`presentation-com-smoke`, P4-003). It now always runs the same PowerShell script as the other commands. pywin32 is still used to look up ProgIDs.
- MCP failure contract (P5-002, P5-003): a test now makes every one of the 85 tools fail and checks that the agent gets an error code. It found three problems, fixed here:
  - `wps-process-audit` raised when PowerShell could not be started (reported as `MCP_TOOL_EXECUTION_FAILED`); it now returns `WPS_PROCESS_AUDIT_FAILED`.
  - `MCP_CLI_ARGUMENTS_REJECTED` told the agent to read the server's stderr, which it cannot; the message now carries argparse's reason, for example that `restore_backup` needs `backup_name` or `backup_path`.
  - `writer-structure` reported a document held open by another handle as `WRITER_STRUCTURE_INVALID`; it now returns `DOCUMENT_HELD_OPEN`.

## [0.1.0]

Never tagged. This is the version the project carried through Phases 0 to 3, up to `main@ae8ea69` (Phase 4 activated). It covers the CLI and the stdio MCP server for WPS Writer, Spreadsheets and Presentation: document registry, backups and restore, idempotent request ids, atomic rollback of failed writes, open-document operations through COM, PDF and HTML conversion, and the regression runner. See `docs/ROADMAP.md` and the phase reports in `docs/` for the detail.
