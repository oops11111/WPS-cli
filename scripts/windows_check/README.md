# 一条命令完成 Windows 检查（P7-005）

Phase 6 在 Windows 上跑了五轮，每轮都照着手册一条条执行，结果再手写。这几轮里的问题都是手册事先防不住的：标签打在错误的提交上，API 余额用完，runner 留下 WPS 进程，控制台代码页。`run_windows_check.py` 在开始前先检查这些，然后跑检查，最后按仓库的格式写出结果。

## 用法

在仓库根目录、项目环境里运行（`pip install -e ".[test,wps]"`）：

```powershell
python scripts/windows_check/run_windows_check.py prereq
python scripts/windows_check/run_windows_check.py eval --only wps-open-writer-selection-replace --only wps-open-save-document
python scripts/windows_check/run_windows_check.py eval --resume scripts\windows_check\results\<目录>
python scripts/windows_check/run_windows_check.py wheel --version 0.4.0
```

| 子命令 | 做什么 |
| --- | --- |
| `prereq` | 只检查机器，见下表；有必需项没通过时退出码为 1 |
| `eval` | 先做 `prereq`，再逐个任务跑评测（默认 `--repeat 3 --min-passes 2`，不给 `--only` 就跑全部任务）。每跑完一个任务就保存进度；中断后用 `--resume <结果目录>` 只跑剩下的任务 |
| `wheel` | 从 Release 下载 wheel，与 Release 列出的 SHA-256 对比；在新的虚拟环境里只装它，不带 `PYTHONPATH`，在仓库以外跑 `inspect-env` 和 safe 档 |

必需项没通过时，脚本不跑任何检查，只写出前提检查的结果。确实需要照跑时加 `--force`，结果里会照实记录哪一项没通过。

## 前提检查

| 检查 | 通过条件 | 防的是 |
| --- | --- | --- |
| `commit` | 跟踪的文件没有改动，记下提交号和分支 | 结果对不上提交 |
| `python` | 解释器不是 WindowsApps 下的商店别名 | Phase 4 遇到过 |
| `windows` | 在 Windows 上 | — |
| `claude answers` | `claude -p` 能正常回答（`eval` 才检查） | 跑到一半 `402 Insufficient Balance` |
| `no WPS process running` | 没有 `wps`、`et`、`wpp` 进程 | 上一轮留下的进程干扰这一轮 |
| `open command .docx/.xlsx/.pptx` | 注册的打开命令里没有 `/Automation`；同时记下 WPS 程序的 FileVersion | P5-006 临时改过打开命令 |
| `inspect-env` | `ok: true`，三个组件都选到了 ProgID | — |

## 结果

每次运行写到 `scripts/windows_check/results/<时间>-<提交号>-eval/`（`wheel` 是 `<时间>-wheel-<版本>`），可以直接提交：

- `RESULTS.md`：日期、提交、机器、WPS 版本、前提检查，以及评测表（格式和 `docs/AGENT_E2E_EVAL.md` 一样）、每次运行没通过的检查、准备失败、Agent 错误、错误码、清理结果，最后列出跑完后还在的 WPS 进程；`wheel` 则列出每个通过条件。
- `results.json`：同样的内容，供机器读取；`eval` 中断时它也是续跑的依据。
- `summary.json`：`eval` 时 runner 的原始汇总。

评测的任务工作区放在系统临时目录（`%TEMP%\wps-windows-check\<目录名>`）下，不进结果目录。

`tests/test_windows_check.py` 用假的机器测试前提检查、续跑和结果格式；`wheel` 在 Linux 上用 `v0.3.0` 的 Release 实际跑过一次。
