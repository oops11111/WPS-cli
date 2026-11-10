# Release check: install wps-agent 0.13.0 on Windows from the GitHub Release

- Date: 2026-11-10 (UTC; local UTC+8)
- Commit: `dd8e229` on `main`
- Machine: Windows 10 企业版 10.0.19045 build 19045; WPS Office 12.8.2.18913 (wps.exe 12,8,2,18913);
  Node v24.16.0; Microsoft Edge 157.0.4341.42. See `machine.txt`.
- Python at the start: `python` was the Microsoft Store alias (exit 9009); `py` was
  `C:\Users\admin\AppData\Local\Programs\Python\Launcher\py.exe`; `uv` was
  `C:\Users\admin\.local\bin\uv.exe`; no Python virtual environment was activated and no uv Python was
  added to PATH. See `before.txt`.
- wps-agent before: 0.12.0 installed in `%LOCALAPPDATA%\wps-agent`
- Installed with the Release `install.ps1` exactly as documented: no `-Python`, no `-WheelPath`.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `git fetch origin --tags`, `main` at `dd8e229`; Release v0.13.0 carries `install.ps1`, `wps_ai_agent_cli-0.13.0-py3-none-any.whl` and `SHA256SUMS.txt`; one WPS Presentation window was running and was closed per this step; no process from `%LOCALAPPDATA%\wps-agent\venv`; before state in `before.txt` |
| 1 | ok | `install.ps1` (23,966 bytes) downloaded; `git hash-object` = `70292179ba0ef4aeabb7490021b8bc67e865fb54`, equal to `v0.13.0:scripts/install/install.ps1`; SHA-256 `9C3071EE5D739ADCCAF5C1C13ED52E94CF6941E660D9F1B72D93B20E63CCC543` |
| 2 | ok | exit 0; see the install log notes below |
| 3 | ok | `install.json` version 0.13.0, status installed; PATH has exactly one `...\wps-agent\bin`; `NODE_PATH` first entry is `...\wps-agent\node\node_modules`; `wps-agent` resolves to `%LOCALAPPDATA%\wps-agent\bin\wps-agent.cmd`; `inspect-env` ok with all three ProgIDs; Claude Desktop entry and backup recorded in `after-install.txt` |
| 4 | Passed | MCP client smoke through the installed venv's Python: initialize 0.13.0, **98 tools**, read `sales_gbk!A1:F3`, wrote `F2`, read it back, backup under `WPS_AGENT_WORKSPACE`; nothing written where the server started; no WPS process left behind (`mcp-cleanup.txt`) |
| 5 | Passed | `wheel --version 0.13.0` on the first run; SHA-256 matches the Release; safe profile 7/7. Results: `scripts/windows_check/results/20261110T013101Z-wheel-0.13.0/` (`RESULTS.md`, `results.json`) |
| 5b.1 | ok | `document-new` created `c.xlsx` (sheet 数据, `doc_4c372a4510f757a3`); `A1:B5` written; all write checks true (`v013-document-new.json`, `v013-write.json`) |
| 5b.2 | ok | `spreadsheet-sort --key 销量:desc`: `ok: true`, checks `header_kept`/`ordered`/`same_rows` true, `order_check` = `strict` (`v013-sort-desc.json`) |
| 5b.3 | ok | `spreadsheet-conditional-format --kind data-bar` on B2:B5: `ok: true`, checks true; **stderr is 0 bytes**, no openpyxl "extension is not supported" warning (`v013-cf-databar.json`, `v013-cf-databar.err.txt`) |
| 5b.4 | ok | `spreadsheet-data-validation --type list` with 是/否 on C2:C5: `ok: true`, all four checks true (`v013-dv-list.json`) |
| 5b.5 | ok | dry-run succeeded; with `c.xlsx` open in WPS the same sort was refused with `DOCUMENT_HELD_OPEN` (exit 1, nothing written); after closing WPS the same sort succeeded **without re-registering** (`ok: true`, `order_check: strict`) — `v013-sort-dryrun.json`, `v013-sort-held.json`, `v013-sort-after-close.json` |
| 5b.6 | ok | `tools/list` is **98** tools (step 4 smoke) |
| 6 | ok | results committed on `cursor/release-0.13.0-windows-dd8e229` (not main) |

## Step 2: install.ps1 without -Python or -WheelPath

Python found: `C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`.

- "The GitHub API did not answer" did **not** appear. The installer downloaded
  `wps_ai_agent_cli-0.13.0-py3-none-any.whl` from the v0.13.0 Release page directly.
- "SHA-256 matches the Release." did appear.
- Exit code 0. Full log: `install.log`.
- Note: this `install.ps1` is byte-identical to the one on v0.12.0 (same blob and SHA-256); only its
  version lookup changed by running against v0.13.0.

## Step 3: after-install state

All details in `after-install.txt`; summary:

- `install.json`: `version` 0.13.0, `status` installed; executable and Python point at the new venv.
- `HKCU\Environment` `Path [String]`: unchanged apart from the single `...\wps-agent\bin` entry that was
  already there — exactly one such entry, everything else identical to `before.txt`.
- `NODE_PATH [String]` = `C:\Users\admin\AppData\Local\wps-agent\node\node_modules`. The installer log also
  confirms "NODE_PATH starts with ...\wps-agent\node\node_modules". Caveat: the agent's long-lived shell
  inherits `NODE_PATH=C:\Program Files\nodejs\node_modules` from its parent process; the registry value and
  the Claude Desktop entry are correct, and a freshly opened window reads the registry value.
- `(Get-Command wps-agent).Source` = `C:\Users\admin\AppData\Local\wps-agent\bin\wps-agent.cmd`.
- `wps-agent inspect-env` (`inspect-env.json`): `ok: true`, validation passed; `kwps.Application`,
  `ket.Application`, `kwpp.Application` all selected.
- Claude Desktop config: only the `wps-agent` entry was read/recorded (`after-install.txt`); the new backup is
  `claude_desktop_config.bak-20261110T092957.json`.

## Step 4: MCP client smoke (like Claude Desktop)

Command: `& "$env:LOCALAPPDATA\wps-agent\venv\Scripts\python.exe" scripts\windows_check\mcp_client_smoke.py --out $R`

Passed on the first run; no `--inherit-env` needed. See `MCP_CLIENT_SMOKE.md` / `mcp-client-smoke.json`:

- initialize: `wps-ai-agent-cli` 0.13.0, protocol `2025-11-25`
- `tools/list`: 98 tools
- read `sales_gbk!A1:F3`, write `sales_gbk!F2`, read the cell back
- backup under `WPS_AGENT_WORKSPACE`; nothing written where the server was started
- after the run: 0 WPS processes (`mcp-cleanup.txt`)

## Step 5: released wheel

Command: `& "$env:LOCALAPPDATA\wps-agent\venv\Scripts\python.exe" scripts\windows_check\run_windows_check.py wheel --version 0.13.0`

Passed on the first run (exit 0). The anonymous GitHub API quota had 39 calls left at the time, so no
rate-limit retry was needed this time. See `wheel-check.log` and the separate result directory:

- SHA-256 `25ae681ecfaa7895bfb7f00761fd67ec8c8991faa3079f5e7310b029f763d013` matches the Release
- installed; version is 0.13.0; package loaded from site-packages; `inspect-env` ok with no errors
- safe profile 7 of 7 passed, 0 failed; manifest loaded from site-packages
- no WPS process was running before or after the run

## Step 5b details

Working directory `$R\work`, PATH `wps-agent`, `PYTHONPATH` unset.

1. `wps-agent document-new --component spreadsheets --path c.xlsx --title 数据` → ok, sheet `数据`,
   `document_id` `doc_4c372a4510f757a3`. The JSON values were passed with the `--%` form through the
   `.cmd` wrapper; `spreadsheet-write` returned `ok: true` with `range_shape_valid`, `backup_created` and
   `write_validated` true; the read-back shows the five rows.
2. Sort by `销量:desc`: WPS order 西北 150, 华东 120, 华南 90, 华北 60; strict.
3. Conditional format data-bar on B2:B5: two checks true; both stdout JSON and stderr were saved, stderr is
   empty — the openpyxl extension warning seen on 0.12.0 is gone.
4. Data validation list 是/否 on C2:C5: `one_rule_on_range`, `operator_matches`, `type_matches`,
   `values_match` all true.
5. Held-open behaviour: `--dry-run` first (ok); opening `c.xlsx` in WPS 表格 and running the same sort was
   refused with `DOCUMENT_HELD_OPEN` (exit 1, message says Open() was not called and nothing was written).
   WPS was closed, and the same sort ran again **without `register-document`** and returned `ok: true`
   (`order_check: strict`, order 华北 60, 华南 90, 华东 120, 西北 150). This confirms a refusal does not
   require re-registration.
6. The step-4 smoke reported 98 tools.

## Deviations and caveats

- A WPS Presentation window was already open when the check started; it was closed as step 0.3 requires.
- CLI commands were run by the agent in PowerShell 7.6.9, using the `--%` form for the JSON argument; the
  installer itself was invoked with `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
  -McpClient claude-desktop`, i.e. Windows PowerShell 5.1, exactly as documented.
- The agent's shell has a non-registry `NODE_PATH` inherited from its parent (see step 3); the persisted
  registry value and the Claude Desktop entry are correct.
- No step failed; the wheel check did not hit the GitHub API rate limit this time (39 calls were available).
