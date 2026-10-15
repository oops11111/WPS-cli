# Windows check of the 0.4.0 wheel

- Date: 2026-10-15 17:07 UTC
- Commit: `1c460da` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1c460da on main |
| python | ok | C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\.venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Released wheel 0.4.0

**Passed.**

- ok: SHA-256 matches the Release
- ok: installed
- ok: version is 0.4.0
- ok: package loaded from site-packages
- ok: inspect-env ok
- ok: safe profile ok with no failures
- ok: manifest loaded from site-packages

- SHA-256: `7d50cce6c9bd7bfa95fa995370f0acc97907d407df19026c6e97444bfbacf70c` (Release: `7d50cce6c9bd7bfa95fa995370f0acc97907d407df19026c6e97444bfbacf70c`)
- Package: `0.4.0` from `C:\Users\admin\AppData\Local\Temp\wps-wheel-_wsfdsw_\venv\Lib\site-packages\wps_ai_agent_cli\__init__.py`
- inspect-env errors: []
- Safe profile: 7 of 7 passed, 0 failed; manifest `C:\Users\admin\AppData\Local\Temp\wps-wheel-_wsfdsw_\venv\Lib\site-packages\wps_ai_agent_cli\resources\regression_manifest.json`
