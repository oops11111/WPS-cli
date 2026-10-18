# Windows agent evaluation

- Date: 2026-10-18 01:16 UTC
- Commit: `1fdbcfb` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.9.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1fdbcfb on main |
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
python scripts/windows_check/run_windows_check.py eval --prefix html-complex- --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **2/3 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **63 off-path calls**, 0 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T010801Z-1fdbcfb-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `html-complex-report-to-docx` | 3/3 | 13.7 (17, 13, 11) | 21 | 1 |  | 15 | 0 | `html_roundtrip_plan`, `inspect_env`, `register_document`, `snapshot_document`, `validate_document`, `writer_structure` |
| `html-complex-budget-to-xlsx` | 0/3 | 16.0 (16, 16, 16) | 43 | 6 |  | 39 | 0 | `inspect_env`, `mcp_tools`, `register_document`, `snapshot_document`, `spreadsheet_formula_write`, `spreadsheet_inspect`, `spreadsheet_read`, `spreadsheet_sheets` |
| `html-complex-launch-to-pptx` | 3/3 | 14.7 (13, 17, 14) | 15 | 0 |  | 9 | 0 | `inspect_env`, `register_document`, `snapshot_document` |

### Runs

- `html-complex-report-to-docx` run 1 (pass): error codes: ROUNDTRIP_SCHEMA_REQUIRED
- `html-complex-budget-to-xlsx` run 1 (FAIL): failed checks: xlsx_sheets (['部门费用预算', '人员编制', '部门费用预算 2', '一个名字很长很长很长很长的汇总表_包含 非法字符 以及 方括号']); tool_called (0 matching call(s)); pdf_file (file missing) | error codes: MCP_TOOL_EXECUTION_FAILED, SHEET_NOT_FOUND
- `html-complex-budget-to-xlsx` run 2 (FAIL): failed checks: xlsx_sheets (['部门费用预算', '人员编制', '部门费用预算 2', '一个名字很长很长很长很长的汇总表_包含 非法字符 以及 方括号']) | error codes: MCP_TOOL_EXECUTION_FAILED, SHEET_NOT_FOUND
- `html-complex-budget-to-xlsx` run 3 (FAIL): failed checks: xlsx_sheets (['部门费用预算', '人员编制', '部门费用预算 2', '一个名字很长很长很长很长的汇总表_包含 非法字符 以及 方括号']); tool_called (0 matching call(s)); pdf_file (file missing) | error codes: MCP_TOOL_EXECUTION_FAILED

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
