# Phase 6 automation diagnostic (P6-001, P6-002)

`automation-diagnostic.ps1` records how the running WPS processes register for automation. It answers the question behind P5-011: when WPS Writer is opened by double-clicking a file, `GetActiveObject("kwps.Application")` finds nothing, so what does it register instead?

It writes one JSON report with three parts:

| Part | What it holds |
| --- | --- |
| `prog_ids` | For each of the nine WPS ProgIDs: the CLSID, whether `GetActiveObject` returns an application (with the HRESULT), and the application's name, path, version and open documents when it does |
| `running_object_table` | Every Running Object Table entry by display name. For names ending with a WPS document extension, the registered object's `FullName` and its application's name, path and version |
| `processes` | Every `wps*`, `et*`, `wpp*`, `ksolaunch*` and `wpscloud*` process: id, session, whether it has a main window, the window title and the command line |

It is read-only: it never opens, saves, closes or activates a document, never starts WPS (`GetActiveObject` and the Running Object Table only hand out objects that are already registered) and never ends a process. `tests/test_automation_diagnostic.py` checks the script for calls that would do any of these.

How to run it on Windows is in `docs/PHASE6_WINDOWS_RUNBOOK.md`, section 1.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_wps_verify_p6\automation-diagnostic.ps1 -Out $env:TEMP\wps-p6\diag-writer-doubleclick.json
```
