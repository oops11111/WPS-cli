# Windows check of the 0.14.0 wheel

- Date: 2026-11-12 02:16 UTC
- Commit: `8a60b33` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.14.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 8a60b33 on main |
| python | ok | C:\Users\admin\AppData\Local\wps-agent\venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Released wheel 0.14.0 (from the GitHub Release)

**Passed.**

- ok: SHA-256 matches the Release
- ok: installed
- ok: version is 0.14.0
- ok: package loaded from site-packages
- ok: inspect-env ok
- ok: safe profile ok with no failures
- ok: manifest loaded from site-packages

- SHA-256: `7e1b9c8b2cc5cbd5b8006fd2a7d80eac94516a0a8ca53161627ddddaa761a9ac` (Release: `7e1b9c8b2cc5cbd5b8006fd2a7d80eac94516a0a8ca53161627ddddaa761a9ac`)
- Package: `0.14.0` from `C:\Users\admin\AppData\Local\Temp\wps-wheel-k260hzlp\venv\Lib\site-packages\wps_ai_agent_cli\__init__.py`
- inspect-env errors: []
- Safe profile: 7 of 7 passed, 0 failed; manifest `C:\Users\admin\AppData\Local\Temp\wps-wheel-k260hzlp\venv\Lib\site-packages\wps_ai_agent_cli\resources\regression_manifest.json`
