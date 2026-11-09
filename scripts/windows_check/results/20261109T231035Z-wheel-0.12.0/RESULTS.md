# Windows check of the 0.12.0 wheel

- Date: 2026-11-09 23:11 UTC
- Commit: `800b1ba` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.12.0 (this repository's src/), `C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\src\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 800b1ba on main |
| python | ok | C:\Users\admin\AppData\Local\wps-agent\venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Released wheel 0.12.0 (from the GitHub Release)

**Passed.**

- ok: SHA-256 matches the Release
- ok: installed
- ok: version is 0.12.0
- ok: package loaded from site-packages
- ok: inspect-env ok
- ok: safe profile ok with no failures
- ok: manifest loaded from site-packages

- SHA-256: `323a34151a5418e8cddbc07237adba373d1dd61e403636014cb6e916e4315344` (Release: `323a34151a5418e8cddbc07237adba373d1dd61e403636014cb6e916e4315344`)
- Package: `0.12.0` from `C:\Users\admin\AppData\Local\Temp\wps-wheel-iv9m7j9s\venv\Lib\site-packages\wps_ai_agent_cli\__init__.py`
- inspect-env errors: []
- Safe profile: 7 of 7 passed, 0 failed; manifest `C:\Users\admin\AppData\Local\Temp\wps-wheel-iv9m7j9s\venv\Lib\site-packages\wps_ai_agent_cli\resources\regression_manifest.json`
