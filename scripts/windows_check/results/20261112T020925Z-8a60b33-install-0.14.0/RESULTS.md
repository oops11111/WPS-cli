# Release check: install wps-agent 0.14.0 on Windows from the GitHub Release

- Date: 2026-11-12 (UTC; local UTC+8)
- Commit: `8a60b33` on `main`
- Machine: Windows 10 企业版 10.0.19045 build 19045; WPS Office 12.8.2.18913 (wps.exe 12,8,2,18913);
  Node v24.16.0; Microsoft Edge 157.0.4341.46. See `machine.txt`.
- Python at the start: `python` was the Microsoft Store alias (exit 9009); `py` was
  `C:\Users\admin\AppData\Local\Programs\Python\Launcher\py.exe`; `uv` was
  `C:\Users\admin\.local\bin\uv.exe`. See `before.txt`.
- wps-agent before: 0.13.0 installed in `%LOCALAPPDATA%\wps-agent`
- Installed with the Release `install.ps1` exactly as documented: `-Version 0.14.0 -McpClient
  claude-desktop`, no `-Python`, no `-WheelPath`.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `main` at `8a60b33`; Release v0.14.0 has `install.ps1`, `wps_ai_agent_cli-0.14.0-py3-none-any.whl`, `wps_ai_agent_cli-0.14.0.tar.gz` and `SHA256SUMS.txt`; no WPS process and no process from `%LOCALAPPDATA%\wps-agent\venv`; before state in `before.txt`, machine info in `machine.txt` |
| 1 | ok | `install.ps1` downloaded to `work\install.ps1`, 23,966 bytes; `git hash-object` = `70292179ba0ef4aeabb7490021b8bc67e865fb54`, equal to `git rev-parse v0.14.0:scripts/install/install.ps1`; SHA-256 `9C3071EE5D739ADCCAF5C1C13ED52E94CF6941E660D9F1B72D93B20E63CCC543` (`install-ps1-info.txt`) |
| 2 | ok | exit 0; **"The GitHub API did not answer" appeared** (HTTP 403), then it downloaded the wheel from the Release page and printed "SHA-256 matches the Release."; Python found: uv cpython-3.12; see `install.log` |
| 3 | ok | `install.json` version 0.14.0, status installed; PATH has exactly one `...\wps-agent\bin`; `NODE_PATH` is `...\wps-agent\node\node_modules`; `wps-agent` resolves to `...\bin\wps-agent.cmd`; `inspect-env` ok (three ProgIDs); Claude Desktop entry and backup recorded (`after-install.txt`, `inspect-env.json`) |
| 4 | Passed | MCP client smoke: initialize 0.14.0, **105 tools**, read `sales_gbk!A1:F3`, wrote `F2`, read it back, backup under `WPS_AGENT_WORKSPACE`; nothing written where the server started; no WPS process left (`mcp-cleanup.txt`) |
| 5 | Passed | `wheel --version 0.14.0`: SHA-256 matches the Release, safe profile 7/7, package from site-packages; results in `scripts/windows_check/results/20261112T021534Z-wheel-0.14.0/` |
| 5b.1 | ok | `通知.docx` (`doc_54df6d83e1baabb8`) and `数据.xlsx` (`doc_481f73525649b67e`, sheet 销售); `A1:B3` written, all write checks true |
| 5b.2 | ok | `batch` b1: `ok: true`, `ran` 3, all three `ok: true`; the third command read `C2` = `已核` after the WPS write; replay with the same `--request-id b1`: second item summary "Spreadsheet write request replayed from idempotency record.", file SHA-256 identical before/after |
| 5b.3 | ok (expected failure) | `calls-bad.json` (first document_id `doc_missing`): `ok: false`, exit 1, `BATCH_COMMAND_FAILED`, `stopped_at` 1, `skipped` 2, `ran` 1; the following two commands were not run |
| 5b.4 | ok | `get /paragraph[1]` → text 关于开展安全检查的通知, style Title; `get /sheets` → 销售, A1:C3; `get /paragraph[99]` → `PATH_TARGET_NOT_FOUND`, exit 1 |
| 5b.5 | ok | `spreadsheet-create-sheet --name 空表` ok; `document-check` on the workbook: `ok: true`, one **info** issue `SHEET_EMPTY` (where 空表); writer check: no problems; `document-view`: 2 sheets, 销售 A1:C3 and 空表 A1:A1 |
| 5b.6 | ok (readable while open) | with `数据.xlsx` open in WPS, `document-view` still returned `ok: true` with both sheets; **no `DOCUMENT_HELD_OPEN`** for this read-only command; WPS then closed without saving |
| 5b.7 | ok | `tools/list` = 105 (step 4) |
| 6 | ok | results committed on `cursor/release-0.14.0-windows-8a60b33` (not main) |

## Step 2 notes

- Python found: `C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`.
- "The GitHub API did not answer (远程服务器返回错误: (403) 已禁止。); downloading from the release page
  instead." **did appear**, and the fallback downloaded `wps_ai_agent_cli-0.14.0-py3-none-any.whl` from the
  v0.14.0 Release page.
- "SHA-256 matches the Release." **did appear**.
- Exit code 0; new Claude Desktop backup `claude_desktop_config.bak-20261112T101146.json`.
- The anonymous GitHub API quota was exhausted (`remaining: 0`) after this step; it recovered at 02:15Z,
  after which the wheel check ran once and passed.

## Step 5b details

All commands ran in `$R\work` with the installed `wps-agent` from PATH and no `PYTHONPATH`. JSON arguments
were passed with the `--%` form through the `.cmd` wrapper (`calls.json` / `calls-bad.json` are UTF-8 files).

- Batch b1 sent three commands: `document-view` (writer), `spreadsheet-write` (`数据.xlsx`, sheet 销售,
  `C1:C2` = `[["备注"],["已核"]]`), and `get` of `/sheet["销售"]/cell["C2"]`. All three succeeded; the get
  returned `已核`, proving the WPS write was visible to the following command.
- Replaying b1: item 2's summary says "Spreadsheet write request replayed from idempotency record." and the
  workbook SHA-256 was identical before and after. Its `data.backup_replayed` field is `false` (it is the
  stored first-run response), so the replay is evidenced by the summary and the unchanged file, not by that
  field.
- Batch b2 stopped at command 1 (`doc_missing`): `BATCH_COMMAND_FAILED`, `stopped_at` 1, `skipped` 2.
- `document-check` reports `SHEET_EMPTY` as severity `info` and keeps `ok: true`; the writer document has no
  issues.
- With the workbook open in WPS, `document-view` (read-only) still read the saved file; unlike the mutating
  commands checked in the previous releases, it did not report `DOCUMENT_HELD_OPEN`.

## Deviations and caveats

- The installer printed the GitHub API 403 warning and used the Release-page fallback; the SHA-256 line
  confirms the downloaded wheel. This is expected behaviour, recorded because the step asks about it.
- `install.ps1` is byte-identical to the previous releases' script (same blob and SHA-256); the version is
  selected with `-Version 0.14.0`.
- The wheel check was delayed until the anonymous API quota reset (it was 0 right after the install); the
  same command then passed on the first try.
- The agent's long-lived shell inherits `NODE_PATH=C:\Program Files\nodejs\node_modules`; the HKCU registry
  value and the Claude Desktop entry both carry `...\wps-agent\node\node_modules`.
- CLI commands were run in PowerShell 7.6.9; the installer was invoked with Windows PowerShell 5.1 exactly
  as documented.
- No WPS process remained before or after any step; the one opened for 5b.6 was closed without saving.
