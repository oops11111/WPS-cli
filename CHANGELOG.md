# Changelog

All notable changes to `wps-ai-agent-cli`. The versioning rule and release steps are in `docs/RELEASING.md`.

## [Unreleased]

### Added

- `restore-backup --close-in-wps` and the MCP `close_in_wps` argument: after a rollback blocked by an open document, close that document in WPS without saving and restore the backup, in one call. WPS must have no unsaved changes, otherwise the call refuses with `DOCUMENT_HAS_UNSAVED_CHANGES`. Without the flag nothing changes. (P4-009, P4-010)
- Agent evaluation: tasks can be marked `requires_wps` and are skipped without WPS; `--repeat N --min-passes M` runs each task N times; four WPS write tasks. (P4-004 to P4-006)
- Regression profile `compat`: open, save and PDF conversion for Spreadsheets and Presentation, part of the WPS compatibility matrix (`docs/COMPATIBILITY_MATRIX.md`). (P4-002)
- CI builds the wheel and the source distribution and keeps them as a workflow artifact. (P4-012)

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
