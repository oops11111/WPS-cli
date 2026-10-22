# Windows agent evaluation

- Date: 2026-10-22 08:43 UTC
- Commit: `c205851` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.10.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | c205851 on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **5/5 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **50 off-path calls**, 0 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261022T083307Z-c205851-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `html-table-to-xlsx` | 3/3 | 6.0 (6, 6, 6) | 10 | 0 |  | 7 | 0 | `register_document`, `spreadsheet_read`, `spreadsheet_sheets` |
| `html-table-to-docx` | 3/3 | 3.7 (4, 3, 4) | 6 | 0 |  | 3 | 0 | `fidelity_check` |
| `html-complex-report-to-docx` | 3/3 | 14.0 (16, 10, 16) | 21 | 1 |  | 15 | 0 | `convert`, `fidelity_check`, `inspect_env`, `register_document`, `snapshot_document`, `validate_document`, `writer_structure` |
| `html-complex-budget-to-xlsx` | 3/3 | 14.7 (16, 16, 12) | 28 | 0 |  | 22 | 0 | `fidelity_check`, `inspect_env`, `register_document`, `spreadsheet_formula_write`, `spreadsheet_inspect`, `spreadsheet_read`, `spreadsheet_sheets`, `wps_process_audit` |
| `html-complex-launch-to-pptx` | 3/3 | 9.3 (9, 7, 12) | 9 | 0 |  | 3 | 0 | `fidelity_check` |

### Runs

- `html-complex-report-to-docx` run 3 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
