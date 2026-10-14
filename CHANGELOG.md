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

## [0.1.0]

Never tagged. This is the version the project carried through Phases 0 to 3, up to `main@ae8ea69` (Phase 4 activated). It covers the CLI and the stdio MCP server for WPS Writer, Spreadsheets and Presentation: document registry, backups and restore, idempotent request ids, atomic rollback of failed writes, open-document operations through COM, PDF and HTML conversion, and the regression runner. See `docs/ROADMAP.md` and the phase reports in `docs/` for the detail.
