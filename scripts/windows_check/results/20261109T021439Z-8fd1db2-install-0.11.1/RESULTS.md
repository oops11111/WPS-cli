# P14-005: Install wps-agent 0.11.1 from GitHub Release, check, MCP smoke, uninstall, reinstall, wheel check

- Date: 2026-11-09
- Commit: `8fd1db2` (origin/main, tag v0.11.1)
- Branch: `cursor/phase14-windows-8fd1db2`

## Machine

| Item | Value |
| --- | --- |
| OS | Microsoft Windows 10 企业版 10.0.19045 |
| WPS Office | 12.8.2.18913 (`C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6`) |
| Python | 3.12.15 (`C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`); `python` on PATH is the non-functional WindowsApps stub; no `py` launcher |
| Node | v22.22.2 |
| Edge | exists (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`) |

## Notes

- The first install attempt (without `-Python`) failed: the installer could not find Python 3.10+ because `python` on PATH resolves to the WindowsApps stub and there is no `py` launcher. The second attempt used `-Python` to point at the uv-managed Python 3.12.15.
- The GitHub API was rate-limited, so the installer's `Get-ReleaseWheel` (which calls `api.github.com`) failed. The wheel was downloaded directly from the release download URL and passed via `-WheelPath`, bypassing the API call. The SHA-256 was verified by the wheel check (Step 8).
- Claude Desktop was running (13 processes) during the install. The installer did not refuse to upgrade — it proceeded and replaced the 0.11.0 installation in place.
- All commands were run in PowerShell without activating any Python virtual environment. The uv-managed Python is a standalone install, not a venv.

## Steps

| Step | Result | Key points |
| --- | --- | --- |
| 0. Prepare | ok | `git fetch origin --tags`, checked out origin/main (8fd1db2). v0.11.1 tag exists. No WPS processes. Claude Desktop running (13 procs). Pre-existing install: wps-agent 0.11.0. Registry PATH has `wps-agent\bin`, NODE_PATH has `wps-agent\node\node_modules`. Claude config has only `wps-agent` server. |
| 1. Download install.ps1 | ok | `irm` downloaded install.ps1 (20598 bytes). `git hash-object` = `1f990c38...` matches `v0.11.1:scripts/install/install.ps1` = `1f990c38...`. |
| 2. Install | ok (after retry) | First attempt without `-Python`: FAIL (exit 1, "Python 3.10 or later was not found"). Second attempt with `-Python <uv python>` and `-WheelPath <local wheel>`: exit 0. Upgraded 0.11.0 → 0.11.1. Playwright installed, PATH already had `wps-agent\bin`, Claude config updated with backup. |
| 3. Check install result | ok | install.json: version 0.11.1, status installed. wps-agent.cmd exists (relative path shim). PATH: 1 `wps-agent\bin` entry, type String. NODE_PATH: `wps-agent\node\node_modules`, type String. Playwright in node_modules. Claude config: `wps-agent` with args `["mcp-server"]`, env.WPS_AGENT_WORKSPACE = data dir. 2 backup files. |
| 4. Simulate new terminal | ok | `(Get-Command wps-agent).Source` = `C:\Users\admin\AppData\Local\wps-agent\bin\wps-agent.cmd`. inspect-env: writer=kwps.Application, spreadsheets=ket.Application, presentation=kwpp.Application. All checks passed. |
| 5. MCP smoke test | ok (Passed) | 87 tools listed. Registered workbook, read sales_gbk!A1:F3, wrote F2="wps-agent MCP smoke", read back confirmed. Backup under WPS_AGENT_WORKSPACE. Nothing written in start dir. No WPS processes left after. |
| 6. Uninstall | ok | exit 0. `wps-agent` dir removed. PATH: no `wps-agent\bin` (other entries unchanged, type String). NODE_PATH: deleted entirely (was only wps-agent entry). `wps-agent-data` still exists with documents.json. Claude config: `wps-agent` entry still present (by design). |
| 7. Reinstall | ok | exit 0. Reinstalled 0.11.1 with same command. NODE_PATH recreated. PATH entry re-added. Claude config updated with new backup. |
| 8. Wheel check | ok (Passed) | Run with venv Python and WPS_AGENT_USE_INSTALLED=1. SHA-256 matches Release. Package 0.11.1 from site-packages. inspect-env ok. Safe profile 7/7 passed. Results in `20261109T023917Z-wheel-0.11.1/`. |
