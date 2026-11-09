# Release check: install wps-agent 0.12.0 on Windows from the GitHub Release

- Date: 2026-11-09 (UTC) / 2026-11-10 (local, UTC+8)
- Commit: `800b1ba` on `main`
- Machine: Windows 10 企业版 10.0.19045 build 19045; WPS Office 12.8.2.18913 (wps.exe 12,8,2,18913);
  Node v24.16.0; Microsoft Edge 157.0.4341.42
- Python at the start: `python` was the Microsoft Store alias (exit 9009); `py` was
  `C:\Users\admin\AppData\Local\Programs\Python\Launcher\py.exe`; `uv` was
  `C:\Users\admin\.local\bin\uv.exe`; no Python virtual environment was activated and no uv Python was
  added to PATH. See `before.txt` and `machine.txt`.
- wps-agent before: 0.11.3 installed in `%LOCALAPPDATA%\wps-agent`
- Installed with the Release `install.ps1` exactly as documented: no `-Python`, no `-WheelPath`.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `git fetch origin --tags`, `main` at `800b1ba`; Release v0.12.0 carries `install.ps1`, `wps_ai_agent_cli-0.12.0-py3-none-any.whl` and `SHA256SUMS.txt`; no WPS process and no process from `%LOCALAPPDATA%\wps-agent\venv`; before state in `before.txt` |
| 1 | ok | `install.ps1` (23,966 bytes) downloaded; `git hash-object` = `70292179ba0ef4aeabb7490021b8bc67e865fb54`, equal to `v0.12.0:scripts/install/install.ps1`; SHA-256 `9C3071EE5D739ADCCAF5C1C13ED52E94CF6941E660D9F1B72D93B20E63CCC543` |
| 2 | ok | exit 0; see the install log notes below |
| 3 | ok | `install.json` version 0.12.0, status installed; PATH has exactly one `...\wps-agent\bin`; `NODE_PATH` first entry is `...\wps-agent\node\node_modules`; `wps-agent` resolves to `%LOCALAPPDATA%\wps-agent\bin\wps-agent.cmd`; `inspect-env` ok with all three ProgIDs; Claude Desktop entry and backup recorded in `after-install.txt` |
| 4 | Passed | MCP client smoke through the installed venv's Python: initialize 0.12.0, 95 tools, read `sales_gbk!A1:F3`, wrote `F2`, read it back, backup under `WPS_AGENT_WORKSPACE`; nothing written where the server started; no WPS process left behind (`mcp-cleanup.txt`) |
| 5 | FAIL, then Passed on retry | First run exited 1 with `HTTP Error 403: rate limit exceeded` from the unauthenticated GitHub API quota; see `wheel-check-attempt1.txt`. Re-run of the same command after the quota reset: PASSED, results under `scripts/windows_check/results/<wheel dir>/` (see below) |
| 5b | ok | 0.12.0 changes verified: strict/lenient exit codes, `pdf-info`, chart create, 95 MCP tools; details below |
| 6 | ok | results committed on `cursor/release-0.12.0-windows-800b1ba` (not main) |

## Step 2: install.ps1 without -Python or -WheelPath

Python found: `C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`.

- "The GitHub API did not answer" did **not** appear. The installer downloaded
  `wps_ai_agent_cli-0.12.0-py3-none-any.whl` from the v0.12.0 Release page directly.
- "SHA-256 matches the Release." did appear.
- Exit code 0. Full log: `install.log`.

## Step 3: after-install state

All details in `after-install.txt`; summary:

- `install.json`: `version` 0.12.0, `status` installed; executable and Python point at the new venv.
- `HKCU\Environment` `Path [String]`: unchanged apart from the single `...\wps-agent\bin` entry that was
  already there — exactly one such entry, everything else identical to `before.txt`.
- `NODE_PATH [String]` = `C:\Users\admin\AppData\Local\wps-agent\node\node_modules` (single entry, the
  wps-agent one). The installer log also confirms "NODE_PATH starts with ...\wps-agent\node\node_modules".
  Note: the agent's own long-lived shell had an inherited `NODE_PATH` (`C:\Program Files\nodejs\node_modules`)
  that exists outside the registry value; a freshly opened window reads the registry value shown above, and
  the Claude Desktop entry carries the wps-agent path explicitly.
- `(Get-Command wps-agent).Source` = `C:\Users\admin\AppData\Local\wps-agent\bin\wps-agent.cmd`.
- `wps-agent inspect-env` (`inspect-env.json`): `ok: true`, validation passed; `kwps.Application`,
  `ket.Application`, `kwpp.Application` all selected.
- Claude Desktop config: only the `wps-agent` entry was read/recorded (`after-install.txt`); the new backup is
  `claude_desktop_config.bak-20261110T070035.json`.

## Step 4: MCP client smoke (like Claude Desktop)

Command: `& "$env:LOCALAPPDATA\wps-agent\venv\Scripts\python.exe" scripts\windows_check\mcp_client_smoke.py --out $R`

Passed on the first run; no `--inherit-env` needed. See `MCP_CLIENT_SMOKE.md` / `mcp-client-smoke.json`:

- initialize: `wps-ai-agent-cli` 0.12.0, protocol `2025-11-25`
- `tools/list`: 95 tools
- read `sales_gbk!A1:F3`, write `sales_gbk!F2`, read the cell back
- backup under `WPS_AGENT_WORKSPACE`; nothing written where the server was started
- after the run: 0 WPS processes (`mcp-cleanup.txt`); none were started that outlived the run

## Step 5: released wheel

First attempt (exit 1) is recorded verbatim in `wheel-check-attempt1.txt`: the repository's wheel check
asks the **unauthenticated** GitHub API for the Release asset, and the shared hourly core quota for this IP
was exhausted (`HTTP Error 403: rate limit exceeded`, remaining 0, reset 2026-11-09T23:25:09Z). No results
directory was created by that attempt.

Second run (same command, after the quota recovered at 23:10Z): **exit 0, passed**. Results:
`scripts/windows_check/results/20261109T231035Z-wheel-0.12.0/` (`RESULTS.md`, `results.json`).

- SHA-256 `323a34151a5418e8cddbc07237adba373d1dd61e403636014cb6e916e4315344` matches the Release
- installed; version is 0.12.0; package loaded from site-packages; `inspect-env` ok with no errors
- safe profile 7 of 7 passed, 0 failed; manifest loaded from site-packages
- no WPS process was running before or after the run

## Step 5b: what changed in 0.12.0

Working directory `$R\work`, PATH `wps-agent`, `PYTHONPATH` unset.

1. Exit-code contract: `wps-agent mcp-tool-schema --name does-not-exist` → **exit 1**, `ok: false`,
   `MCP_TOOL_SCHEMA_NOT_FOUND` (`v012-schema-missing.json`); adding `--lenient-exit` → **exit 0** with the
   same JSON (`v012-schema-lenient.json`). As specified.
2. New commands shipped with the installer: `document-new --component writer --path a.docx --title 测试`
   → ok (`v012-document-new-writer.json`), `convert --input a.docx --output a.pdf` → ok
   (`v012-convert-pdf.json`), `pdf-info --input a.pdf` → **ok: true**, 1 page, PDF 1.7, text layer present
   (`v012-pdf-info.json`); no `CONVERTER_UNAVAILABLE`, so pypdf came with the install.
3. `document-new --component spreadsheets --path b.xlsx --title 数据` → ok
   (`v012-document-new-xlsx.json`, `doc_75142bb61f9db968`); `spreadsheet-write --range A1:B3` with
   `[["月","值"],["7月",1],["8月",2]]` → ok, validation `range_shape_valid`/`backup_created`/`write_validated`
   all true (`v012-spreadsheet-write.json`); `spreadsheet-chart-create --sheet-name 数据 --range A1:B3
   --chart-type column --title 测试` → **ok: true**, `data.checks` = `one_chart_added`,
   `series_inside_range`, `title_matches`, `type_matches`, all true (`v012-chart-column.json`).
   Quoting note: the first write attempt passed the JSON without escaping the inner quotes; PowerShell →
   `cmd.exe` → the C runtime stripped them, and the CLI correctly answered `INVALID_JSON`. The re-run used
   `wps-agent --% ... --values-json [[\"月\",\"值\"],[\"7月\",1],[\"8月\",2]]` so the quotes reach the CLI.
4. `tools/list` is **95** tools, from the same `mcp_client_smoke.py` result as step 4.
5. Every JSON and the exit codes are saved as `v012-*.json` / `v012-exit-codes.txt` in this directory.

## Deviations and caveats

- The wheel check needed a second run because of the anonymous GitHub API rate limit (see step 5); the
  command was not changed.
- The supplied step-5b spreadsheet values JSON needs escaped inner quotes when invoked through a Windows
  shell/`.cmd` wrapper (see step 5b.3); the product's rejection of the unescaped form is correct behaviour.
- CLI commands were run by the agent in PowerShell 7.6.9; the installer itself was invoked with
  `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop`, i.e. Windows
  PowerShell 5.1, exactly as documented. The agent's long-lived shell also has a non-registry `NODE_PATH`
  inherited from its parent (see step 3); the persisted registry value and the Claude Desktop entry are correct.
