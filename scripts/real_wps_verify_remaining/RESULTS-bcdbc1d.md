# Phase 5 Windows results — v0.2.0 wheel

- 日期：2026-10-15
- 机器：Windows 10.0.19045；Python 3.12.14
- WPS：Writer 12.8.2.18913，表格 12.8.2.18913，演示 12.8.2.18913（`office6` 三个 exe 的 FileVersion；本机只有这一套）
- 分支：`docs/p5-windows-runbook` @ `bcdbc1d`（`main` `f2ed99e` 加上手册提交）。P5-009 装的是 Release 的 wheel，不是这个工作区。
- 操作人：desktop-k93n3p8\admin

## P5-009：只装 Release 的 wheel

安装目录是 `%TEMP%\wps-p5\wheel-clean`。第一次在 `%TEMP%\wps-p5\wheel` 里装时，进程上的 `PYTHONPATH` 还指着仓库的 `src`，解释器用的是仓库里的包。下面的数字来自清掉 `PYTHONPATH` 之后的新 venv。

- wheel SHA-256：`00102021C9D339FEAC1D778CDBB4D2EFBD2F66B3A2A8092DE315B0C1EE71E9A3`（与 Release 一致：是）
- `__version__` / `__file__`：`0.2.0` / `C:\Users\admin\AppData\Local\Temp\wps-p5\wheel-clean\.venv\Lib\site-packages\wps_ai_agent_cli\__init__.py`
- inspect-env：pass（`ok: true`，`errors` 为空；Writer `kwps.Application`、表格 `ket.Application`、演示 `kwpp.Application`，`detected` 都是 true）。`validation.status` 是 `warning`，因为 `pywin32_available` 为 false；三个 ProgID 检查是通过的。
- safe 档：pass（通过 7 / 共 7，`failed_count` 0；manifest_path：`C:\Users\admin\AppData\Local\Temp\wps-p5\wheel-clean\.venv\Lib\site-packages\wps_ai_agent_cli\resources\regression_manifest.json`）
