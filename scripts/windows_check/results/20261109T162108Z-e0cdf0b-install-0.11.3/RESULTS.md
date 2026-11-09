# Phase 14 P14-005 recheck: install wps-agent 0.11.3 from the GitHub Release

- Date: 2026-11-09 (UTC) / 2026-11-10 (local)
- Commit: `e0cdf0b` on `main`
- Machine: Windows 10.0.19045; WPS 12.8.2.18913; Node v24.16.0; Microsoft Edge at
  `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- Python at the start: `python` was the Microsoft Store alias (exit 9009), `py` was
  missing, `uv` was at `C:\Users\admin\.local\bin\uv.exe`. See `python-fix.txt`.
- Python after the fix: Python 3.13.17 (`python --version` and `py --version`, both exit 0)
- wps-agent before: 0.11.1 installed in `%LOCALAPPDATA%\wps-agent`

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `git fetch origin --tags`, `main` at `e0cdf0b`; Release v0.11.3 has `install.ps1`, `wps_ai_agent_cli-0.11.3-py3-none-any.whl`, `SHA256SUMS.txt`; no WPS and no `wps-agent\venv` process; before state in `before.txt` |
| 1 | ok | `install.ps1` (23,763 bytes) downloaded; `git hash-object` = `5717b3c6d67a0d1ce5126c5c91e595b625f9b915`, equal to `v0.11.3:scripts/install/install.ps1`; SHA-256 `814973def5519913b564c332a335c51cc4c1a5977836467dfa025d3229e94044` |
| 2 | ok | exit 0; see the install log notes below |
| 3 | ok | `install.json` version 0.11.3, status installed; PATH has exactly one `...\wps-agent\bin`; NODE_PATH starts with `...\wps-agent\node\node_modules`; `wps-agent` resolves to `%LOCALAPPDATA%\wps-agent\bin\wps-agent.cmd`; `inspect-env` ok with all three ProgIDs; Claude Desktop entry and backup recorded |
| 4 | Passed | MCP client smoke through the installed venv's Python: initialize 0.11.3, 87 tools, read `sales_gbk!A1:F3`, wrote `F2`, read it back, backup under `WPS_AGENT_WORKSPACE`; nothing written where the server started |
| 5 | Passed | `wheel --version 0.11.3`; SHA-256 matches the Release; 0.11.3 from site-packages; inspect-env ok; safe profile 7/7. Results: `scripts/windows_check/results/20261109T163806Z-wheel-0.11.3/` |
| 6 | ok | results committed on `cursor/phase14-windows-e0cdf0b` (not main) |

## Step 2 (install.ps1 without -Python or -WheelPath)

```
==> Finding Python 3.10+
    C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe
==> Getting the wheel
    WARNING: The GitHub API did not answer (远程服务器返回错误: (403) 已禁止。); downloading from the release page instead.
    Downloading wps_ai_agent_cli-0.11.3-py3-none-any.whl from v0.11.3
    SHA-256 matches the Release.
...
==> Adding C:\Users\admin\AppData\Local\wps-agent\bin to your PATH
    Already on PATH.
==> Checking the environment (wps-agent inspect-env)
    WPS COM automation is registered (kwps.Application, ket.Application, kwpp.Application).
==> Connecting the MCP client (claude-desktop)
    Added to C:\Users\admin\AppData\Roaming\Claude\claude_desktop_config.json; restart Claude Desktop.
    Previous config saved as C:\Users\admin\AppData\Roaming\Claude\claude_desktop_config.bak-20261110T002346.json
exit=0
```

- Which Python was found: uv's Python 3.12
  (`C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`).
- "The GitHub API did not answer" **appeared** (403); the installer then downloaded
  the wheel from the Release page and printed **"SHA-256 matches the Release."**
- Version installed: 0.11.3.

## Step 3 details

- `install.json`: `"status": "installed"`, `"version": "0.11.3"`, node path
  `...\wps-agent\node\node_modules`, data dir `...\wps-agent-data`.
- Registry `Path` is `String`; it contains exactly one `C:\Users\admin\AppData\Local\wps-agent\bin`.
  `NODE_PATH` is `String`, first (only) entry `C:\Users\admin\AppData\Local\wps-agent\node\node_modules`.
  **Deviation:** the Python fix (requested mid-run) added
  `%LOCALAPPDATA%\Programs\Python\Python313` and its `Scripts` at the front of PATH and
  removed duplicate entries, so PATH is not byte-identical to `before.txt`. The installer
  itself did not change PATH ("Already on PATH") or NODE_PATH.
- Claude Desktop `mcpServers.wps-agent`:
  `{"command":"C:\Users\admin\AppData\Local\wps-agent\venv\Scripts\wps-agent.exe","args":["mcp-server"],"env":{"NODE_PATH":"C:\Users\admin\AppData\Local\wps-agent\node\node_modules","WPS_AGENT_WORKSPACE":"C:\Users\admin\AppData\Local\wps-agent-data"}}`
- New backup: `claude_desktop_config.bak-20261110T002346.json`.

## Step 4 details

`& "%LOCALAPPDATA%\wps-agent\venv\Scripts\python.exe" scripts\windows_check\mcp_client_smoke.py --out <this dir>`
passed (exit 0). It read the client config, initialized the server (0.11.3,
protocol 2025-11-25), listed 87 tools, registered the workbook
(`doc_ff68bb1cec9c35b8`), read `sales_gbk!A1:F3`, wrote `sales_gbk!F2`,
read back `wps-agent MCP smoke`, found one backup under
`WPS_AGENT_WORKSPACE\.wps-agent\backups\doc_ff68bb1cec9c35b8\`, and wrote
nothing where the server was started. No WPS process was left afterwards.
Full report: `MCP_CLIENT_SMOKE.md`.

## Step 5 details

`wheel --version 0.11.3` passed: downloaded wheel SHA-256 matches the
Release (`6062d5e7…91eb`), 0.11.3 from site-packages, `inspect-env` ok,
safe profile 7/7.

## Deviations from the prompt

- The install was already running when "先解决python不可用的问题" arrived; it completed
  with exit 0 using uv's Python. Python was then fixed as requested (Python 3.13.17);
  the install result above is from before that fix.
- Python 3.12 could not be repaired: its MSI registration is broken (1603/1605), and the
  fix chosen was a fresh 3.13 install rather than deleting pre-existing registry keys.
- PATH changed because of the Python fix; see Step 3. No `-Python` or `-WheelPath` was
  used for the install.
