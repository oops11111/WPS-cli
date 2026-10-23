# Windows agent evaluation

- Date: 2026-10-22 23:38 UTC
- Commit: `45b0d4b` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.10.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 45b0d4b on main |
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
python scripts/windows_check/run_windows_check.py eval --prefix html- --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **5/5 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **67 off-path calls**, 0 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261022T232652Z-45b0d4b-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `html-table-to-xlsx` | 3/3 | 6.3 (6, 7, 6) | 10 | 0 |  | 7 | 0 | `register_document`, `spreadsheet_read`, `spreadsheet_sheets` |
| `html-table-to-docx` | 3/3 | 5.0 (7, 5, 3) | 7 | 0 |  | 4 | 0 | `fidelity_check`, `register_document`, `snapshot_document`, `writer_table_write` |
| `html-complex-report-to-docx` | 3/3 | 15.0 (16, 13, 16) | 22 | 2 |  | 18 | 0 | `convert`, `fidelity_check`, `inspect_env`, `register_document`, `validate_document`, `writer_structure`, `writer_table_write` |
| `html-complex-budget-to-xlsx` | 3/3 | 17.3 (20, 16, 16) | 32 | 3 |  | 26 | 0 | `convert`, `fidelity_check`, `inspect_env`, `register_document`, `spreadsheet_read`, `spreadsheet_sheets` |
| `html-complex-launch-to-pptx` | 3/3 | 13.7 (14, 16, 11) | 18 | 0 |  | 12 | 0 | `fidelity_check`, `inspect_env`, `register_document`, `scan_dir`, `snapshot_document` |

### Runs

- `html-complex-report-to-docx` run 1 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `html-complex-budget-to-xlsx` run 1 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `html-complex-budget-to-xlsx` run 2 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `html-complex-budget-to-xlsx` run 3 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
