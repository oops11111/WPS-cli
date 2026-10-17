# Windows agent evaluation

- Date: 2026-10-17 22:46 UTC
- Commit: `29175b1` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.9.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 29175b1 on main |
| python | ok | C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\.venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| claude answers | ok | OK |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Agent evaluation

```
python scripts/windows_check/run_windows_check.py eval --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **33/34 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **76 off-path calls**, 7 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T172608Z-29175b1-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `register-and-backup` | 3/3 | 3.0 (3, 3, 3) | 6 | 0 |  | 0 | 0 |  |
| `list-backups-readonly` | 3/3 | 3.0 (3, 3, 3) | 6 | 0 |  | 0 | 0 |  |
| `restore-missing-backup` | 3/3 | 7.3 (5, 7, 10) | 13 | 4 |  | 4 | 0 | `documents`, `operation`, `operations`, `scan_dir` |
| `idempotent-backup-retry` | 3/3 | 6.3 (8, 5, 6) | 13 | 0 |  | 4 | 0 | `list_backups`, `operation` |
| `restore-latest-backup` | 1/3 | 8.0 (8, 9, 7) | 21 | 4 |  | 7 | 0 | `open_documents`, `operation`, `snapshot_document`, `spreadsheet_read` |
| `restore-dry-run` | 3/3 | 8.7 (15, 6, 5) | 15 | 4 |  | 1 | 0 | `operation` |
| `held-document-backup` | 3/3 | 3.3 (3, 3, 4) | 7 | 4 |  | 1 | 0 | `open_documents` |
| `html-table-to-xlsx` | 3/3 | 6.7 (7, 7, 6) | 12 | 0 |  | 9 | 0 | `inspect_env`, `register_document`, `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-spreadsheet-write` | 3/3 | 5.7 (6, 7, 4) | 13 | 0 |  | 7 | 0 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-writer-replace` | 3/3 | 4.3 (4, 4, 5) | 10 | 0 |  | 2 | 0 | `validate_document` |
| `wps-presentation-replace` | 3/3 | 7.3 (7, 11, 4) | 11 | 0 |  | 2 | 0 | `operation`, `snapshot_document` |
| `wps-held-spreadsheet-write` | 3/3 | 3.0 (3, 3, 3) | 6 | 3 |  | 0 | 0 |  |
| `spreadsheet-sheets-and-read` | 3/3 | 4.0 (4, 4, 4) | 9 | 0 |  | 0 | 0 |  |
| `html-table-to-docx` | 3/3 | 9.3 (9, 10, 9) | 19 | 0 |  | 16 | 0 | `inspect_env`, `register_document`, `snapshot_document`, `validate_document`, `writer_structure`, `writer_table_write` |
| `wps-spreadsheet-rename-sheet` | 3/3 | 4.0 (3, 6, 3) | 9 | 0 |  | 1 | 0 | `spreadsheet_read` |
| `wps-spreadsheet-create-sheet` | 3/3 | 6.7 (9, 6, 5) | 15 | 0 |  | 4 | 0 | `inspect_env`, `spreadsheet_read` |
| `wps-writer-table-write` | 3/3 | 10.7 (9, 10, 13) | 27 | 1 |  | 5 | 0 | `operation`, `snapshot_document` |
| `wps-docx-to-pdf` | 3/3 | 8.7 (9, 12, 5) | 6 | 0 |  | 3 | 0 | `inspect_env`, `register_document` |
| `wps-open-document-export-text` | 3/3 | 3.7 (4, 3, 4) | 6 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 4.3 (4, 5, 4) | 10 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-insert` | 3/3 | 6.0 (8, 5, 5) | 15 | 0 | 0 | 2 | 1 | `snapshot_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 5.3 (5, 7, 4) | 13 | 1 | 0 | 1 | 0 | `operation` |
| `wps-open-save-document` | 3/3 | 4.7 (5, 5, 4) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-delete` | 3/3 | 4.7 (4, 4, 6) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-presentation-selection-insert` | 3/3 | 5.3 (7, 5, 4) | 13 | 0 | 0 | 0 | 0 |  |
| `wps-open-presentation-selection-delete` | 3/3 | 5.3 (4, 5, 7) | 13 | 1 | 0 | 1 | 0 | `operation` |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 5.0 (7, 4, 4) | 12 | 0 | 0 | 1 | 1 | `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 6.0 (5, 6, 7) | 15 | 0 | 0 | 3 | 3 | `spreadsheet_read` |
| `wps-open-save-as-untitled` | 3/3 | 5.0 (6, 4, 5) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-writer-selection-replace` | 3/3 | 4.3 (4, 5, 4) | 10 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 5.3 (6, 5, 5) | 13 | 0 | 0 | 2 | 2 | `spreadsheet_read` |
| `wps-open-zh-document-export-text` | 3/3 | 4.7 (6, 4, 4) | 7 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-save-as-untitled` | 3/3 | 5.0 (5, 5, 5) | 12 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-document-export-beyond-gbk` | 3/3 | 4.7 (6, 4, 4) | 6 | 0 | 0 | 0 | 0 |  |

### Runs

- `restore-missing-backup` run 1 (pass): error codes: BACKUP_NOT_FOUND
- `restore-missing-backup` run 2 (pass): error codes: BACKUP_NOT_FOUND, OPERATION_NOT_FOUND
- `restore-missing-backup` run 3 (pass): error codes: BACKUP_NOT_FOUND
- `restore-latest-backup` run 1 (FAIL): failed checks: max_tool_calls (7 wps-agent call(s)) | error codes: MCP_CLI_ARGUMENTS_REJECTED
- `restore-latest-backup` run 2 (FAIL): failed checks: max_tool_calls (8 wps-agent call(s)) | error codes: MCP_CLI_ARGUMENTS_REJECTED, NO_RUNNING_WPS_INSTANCE
- `restore-latest-backup` run 3 (pass): error codes: MCP_CLI_ARGUMENTS_REJECTED
- `restore-dry-run` run 1 (pass): error codes: MCP_CLI_ARGUMENTS_REJECTED, OPERATION_NOT_FOUND
- `restore-dry-run` run 2 (pass): error codes: MCP_CLI_ARGUMENTS_REJECTED
- `restore-dry-run` run 3 (pass): error codes: MCP_CLI_ARGUMENTS_REJECTED
- `held-document-backup` run 1 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: 1
- `held-document-backup` run 2 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: 1
- `held-document-backup` run 3 (pass): error codes: DOCUMENT_HELD_OPEN, NO_RUNNING_WPS_INSTANCE | cleanup: 1
- `wps-held-spreadsheet-write` run 1 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: 1
- `wps-held-spreadsheet-write` run 2 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: 1
- `wps-held-spreadsheet-write` run 3 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: 1
- `wps-writer-table-write` run 2 (pass): error codes: OPERATION_NOT_FOUND
- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 59524 (main window closed)
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 46648 (main window closed)
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 59876 (main window closed)
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 59244 (main window closed)
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 59656 (main window closed)
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 47448 (main window closed)
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 59344 (main window closed)
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 58268 (main window closed)
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 39200 (main window closed)
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 60576 (main window closed)
- `wps-open-presentation-selection-replace` run 2 (pass): error codes: OPERATION_NOT_FOUND | cleanup: fixture closed; processes exited 36116 (main window closed)
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 52196 (main window closed)
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes exited 57012 (main window closed)
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes exited 59280 (main window closed)
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes exited 42784 (main window closed)
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 61264 (main window closed)
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 57528 (main window closed)
- `wps-open-writer-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 56124 (main window closed)
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 57228 (main window closed)
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 60044 (main window closed)
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 10100 (main window closed)
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 60352 (main window closed)
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 45852 (main window closed)
- `wps-open-presentation-selection-delete` run 3 (pass): error codes: OPERATION_NOT_FOUND | cleanup: fixture closed; processes exited 25476 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 53948 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 59740 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 57200 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 53804 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 56856 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 60316 (main window closed)
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 60376 (main window closed)
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 51848 (main window closed)
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 59660 (main window closed)
- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 50276 (main window closed)
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 57628 (main window closed)
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 32736 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): cleanup: fixture closed; processes exited 57152 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): cleanup: fixture closed; processes exited 56520 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes exited 52680 (main window closed)
- `wps-open-zh-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 2872 (main window closed)
- `wps-open-zh-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 58156 (main window closed)
- `wps-open-zh-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 44496 (main window closed)
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 60024 (main window closed)
- `wps-open-zh-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 50616 (main window closed)
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 23964 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 1 (pass): cleanup: fixture closed; processes exited 59700 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 2 (pass): cleanup: fixture closed; processes exited 57288 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 3 (pass): cleanup: fixture closed; processes exited 57568 (main window closed)

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
