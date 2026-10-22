# Windows agent evaluation

- Date: 2026-10-22 07:21 UTC
- Commit: `c55d04e` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.10.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | c55d04e on main |
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
python scripts/windows_check/run_windows_check.py eval --prefix convert- --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **5/5 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **48 off-path calls**, 0 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261022T071021Z-c55d04e-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `convert-pdf-to-docx` | 3/3 | 7.0 (3, 9, 9) | 12 | 0 |  | 7 | 0 | `register_document`, `snapshot_document`, `writer_structure`, `writer_table_write` |
| `convert-gbk-csv-to-xlsx` | 3/3 | 10.3 (9, 9, 13) | 15 | 1 |  | 11 | 0 | `inspect_env`, `open_documents`, `register_document`, `spreadsheet_inspect`, `spreadsheet_read`, `validate_document` |
| `convert-markdown-to-docx` | 3/3 | 16.3 (15, 18, 16) | 19 | 3 |  | 8 | 0 | `inspect_env`, `register_document`, `snapshot_document`, `writer_structure` |
| `convert-docx-to-pptx` | 3/3 | 11.0 (8, 13, 12) | 21 | 1 |  | 12 | 0 | `register_document`, `snapshot_document`, `writer_structure` |
| `convert-legacy-doc-with-wps` | 3/3 | 16.7 (16, 16, 18) | 23 | 4 |  | 10 | 0 | `inspect_env`, `register_document`, `snapshot_document`, `validate_document`, `writer_structure` |

### Runs

- `convert-gbk-csv-to-xlsx` run 3 (pass): error codes: NO_RUNNING_WPS_INSTANCE
- `convert-markdown-to-docx` run 1 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `convert-markdown-to-docx` run 2 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `convert-markdown-to-docx` run 3 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `convert-docx-to-pptx` run 2 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND
- `convert-legacy-doc-with-wps` run 1 (pass): error codes: OUTPUT_DIRECTORY_NOT_FOUND, UNSUPPORTED_FORMAT
- `convert-legacy-doc-with-wps` run 2 (pass): error codes: UNSUPPORTED_FORMAT
- `convert-legacy-doc-with-wps` run 3 (pass): error codes: UNSUPPORTED_FORMAT

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
