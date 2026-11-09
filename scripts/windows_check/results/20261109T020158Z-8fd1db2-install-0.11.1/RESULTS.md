# Phase 14 P14-005 — Windows install check, v0.11.1

Result: **FAIL at step 2 (install)**. The existing wps-agent 0.11.0 is still installed and working; v0.11.1 was not installed.

## Machine

- Windows: Microsoft Windows 10 企业版, version 10.0.19045
- WPS Office: 12.8.2.18913 (`C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6`)
- Python on PATH: **not available** — `python --version` exits 9009 (Microsoft Store placeholder), `py` is not installed
- Python available outside PATH: `C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe` (3.12.15, used only for the MCP smoke)
- Node.js: v24.16.0
- Edge: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- Repository: `C:\Users\admin\wps cli`, commit `8fd1db2` (`v0.11.1` = `8fd1db23f5c23dc3af5b17dc7e3eb735e6fc0268`)
- Claude Desktop: running (it hosts this check session). Its config has a `wps-agent` server; no process was running from the wps-agent install directory, so the installer's process guard was not the blocker.

## Steps 0–8

| Step | Result | Summary |
|---|---|---|
| 0. Prepare | ok | `git fetch origin --tags`, `git checkout main`, `git pull` exit 0; HEAD `8fd1db2`; tag `v0.11.1` present; Release has `install.ps1`, wheel and tar.gz; no WPS processes. `before.txt` recorded. |
| 1. Download install.ps1 | ok | blob `1f990c38031ed6888a3681101b655518cf6a1951` equals `v0.11.1:scripts/install/install.ps1`; SHA-256 `62C01F8E86AE6D9757C80E15E56FF2EED008801A847E63B61D1CFE8F90CE9020` equals the Release digest; 20598 bytes. |
| 2. Install | **FAIL** | exit 1: `Python 3.10 or later was not found.` The installer stops before touching the existing install; 0.11.0 remains. Full output: `install.log`. |
| 3. After-install checks | **FAIL** (not the expected 0.11.1 state) | `install.json` still version 0.11.0; `bin\wps-agent.cmd` exists; PATH still has exactly one `...\wps-agent\bin` entry (String); NODE_PATH first entry is the old install's `node\node_modules` and `playwright` exists; Claude config still has the old entry, with an absolute `WPS_AGENT_WORKSPACE`, not `%LOCALAPPDATA%\wps-agent-data`; no new `claude_desktop_config.bak-*.json`. Details: `after-install.txt`. |
| 4. PATH + inspect-env | ok (against 0.11.0) | `(Get-Command wps-agent).Source` = `C:\Users\admin\AppData\Local\wps-agent\bin\wps-agent.cmd` (not the repo `.venv`); `inspect-env` exit 0; writer `kwps.Application`, spreadsheets `ket.Application`, presentation `kwpp.Application` all selected. Full JSON: `inspect-env.json`; summary: `path-check.txt`. |
| 5. MCP client smoke | ok (against 0.11.0) | Passed. `initialize` reports server version **0.11.0**, protocol `2025-11-25`, 87 tools; read `sales_gbk!A1:F3`; wrote `F2`; backup landed under `WPS_AGENT_WORKSPACE`; nothing written in the server start directory; no WPS process left. This tested the still-installed 0.11.0, not 0.11.1. Results: `MCP_CLIENT_SMOKE.md`, `mcp-client-smoke.json`. |
| 6. Uninstall | **SKIPPED** | Not run: step 2 failed, step 7 cannot reinstall without Python, and uninstalling would remove the only working installation. See `after-uninstall.txt`. |
| 7. Reinstall | **FAIL** | Same command, exit 1, same `Python 3.10 or later was not found.` error. `install.json` after the attempt is still 0.11.0. Full output: `reinstall.log`. |
| 8. Wheel check | **FAIL** | `python scripts\windows_check\run_windows_check.py wheel --version 0.11.1` exits 9009 with no output (`python` is the Microsoft Store placeholder). No new result directory was created. Full output: `wheel-check.log`. |

## Failure details

### Step 2 — install

Command (run in the download directory, inside a fresh PowerShell):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
```

Exit code: `1`

Key output:

```text
==> Finding Python 3.10+
Python 3.10 or later was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") or pass -Python <path to python.exe>.
```

The installer calls `Find-Python` before removing `venv`, `node` or `bin`, so the existing 0.11.0 installation was not modified.

### Step 3 — differences from the expected 0.11.1 state

- `install.json` reports `"version": "0.11.0"`, `"installed_at": "2026-10-23T11:27:49"`.
- Claude Desktop entry (unchanged, old installer output):

```json
{
  "command": "C:\\Users\\admin\\AppData\\Local\\wps-agent\\venv\\Scripts\\wps-agent.exe",
  "args": ["mcp-server"],
  "env": {
    "NODE_PATH": "C:\\Users\\admin\\AppData\\Local\\wps-agent\\node\\node_modules",
    "WPS_AGENT_WORKSPACE": "C:\\Users\\admin\\AppData\\Local\\wps-agent-data"
  }
}
```

- Expected by the task for the new install: `env.WPS_AGENT_WORKSPACE` = `%LOCALAPPDATA%\wps-agent-data`. The old entry stores the expanded absolute path instead.
- `claude_desktop_config.bak-*.json`: none. The installer failed before the client-config step.

### Step 6 — skipped

See `after-uninstall.txt`. Reason: step 2 and step 7 both fail on the missing Python, so an uninstall would leave the machine without a working wps-agent, contradicting the requirement to leave it installed for use.

### Step 7 — reinstall

Command: same as step 2. Exit code: `1`. Key output: the same `Python 3.10 or later was not found.` message. Full output: `reinstall.log`. `install.json` remains 0.11.0.

### Step 8 — wheel check

Command (in the repository root, after confirming no WPS processes):

```powershell
python scripts\windows_check\run_windows_check.py wheel --version 0.11.1
```

Exit code: `9009`. Output: empty. `python` resolves to `C:\Users\admin\AppData\Local\Microsoft\WindowsApps\python.exe`, the Microsoft Store placeholder. No `scripts\windows_check\results\...-wheel-0.11.1` directory was produced.

## Conclusion

- v0.11.1 was **not installed**. Root cause: no Python 3.10+ on PATH. The Release installer requires it and stops before changing the existing installation.
- The previous **0.11.0** installation remains in place and was verified working: PATH points to its `bin\wps-agent.cmd`, `inspect-env` detects Writer/Spreadsheets/Presentation, and the Claude-Desktop-style MCP smoke passed (read, write, backup, cleanup).
- To complete the v0.11.1 upgrade, either put Python 3.10+ on PATH or run the installer with its documented parameter, for example:

```powershell
.\install.ps1 -McpClient claude-desktop -Python "C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
```

  This was not done here because the task said not to work around a failed step.
- The wheel check could not run for the same reason and produced no result directory.

## Method notes

- The Terminal-panel wrapper interrupted two PowerShell startup attempts (`管道已被停止`). The same step scripts were then run in fresh `powershell.exe -NoProfile` processes. No Python virtual environment was activated for any command; the MCP smoke used the uv-managed base interpreter directly.
- Claude Desktop was not quit: this check session runs inside it. Its config contains a `wps-agent` entry, but no wps-agent process was running from the install directory; the installer failed earlier, at the Python check.

## Files in this directory

- `before.txt` — pre-install registry, install dir, config names, toolchain
- `install.log` — full step 2 output and exit code
- `after-install.txt` — post-install-attempt state and config entry
- `path-check.txt` — PATH resolution and inspect-env component summary
- `inspect-env.json` — full `wps-agent inspect-env` output
- `MCP_CLIENT_SMOKE.md`, `mcp-client-smoke.json`, `mcp-client-smoke.log` — step 5
- `after-uninstall.txt` — step 6 skip record
- `reinstall.log` — step 7 output and exit code
- `wheel-check.log` — step 8 output and exit code
