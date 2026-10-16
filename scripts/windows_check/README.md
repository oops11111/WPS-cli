# 一条命令完成 Windows 检查（P7-005）

Phase 6 在 Windows 上跑了五轮，每轮都照着手册一条条执行，结果再手写。这几轮里的问题都是手册事先防不住的：标签打在错误的提交上，API 余额用完，runner 留下 WPS 进程，控制台代码页。`run_windows_check.py` 在开始前先检查这些，然后跑检查，最后按仓库的格式写出结果。

## 用法

在仓库根目录、项目环境里运行（`pip install -e ".[test,wps]"`）：

```powershell
python scripts/windows_check/run_windows_check.py prereq
python scripts/windows_check/run_windows_check.py eval --only wps-open-writer-selection-replace --only wps-open-save-document
python scripts/windows_check/run_windows_check.py eval --resume scripts\windows_check\results\<目录>
python scripts/windows_check/run_windows_check.py eval --prefix wps-open- --repeat 3 --min-passes 2
python scripts/windows_check/run_windows_check.py undo
python scripts/windows_check/run_windows_check.py close-diag
python scripts/windows_check/run_windows_check.py wheel --version 0.4.0
```

| 子命令 | 做什么 |
| --- | --- |
| `prereq` | 只检查机器，见下表；有必需项没通过时退出码为 1 |
| `eval` | 先做 `prereq`，再逐个任务跑评测（默认 `--repeat 3 --min-passes 2`，不给 `--only` 或 `--prefix` 就跑全部任务；`--prefix wps-open-` 跑 id 以它开头的所有任务，可以和 `--only` 一起用）。每跑完一个任务就保存进度；中断后用 `--resume <结果目录>` 只跑剩下的任务 |
| `undo` | 先做 `prereq`（不问 `claude`），再检查已打开文档写入失败时在 WPS 里的撤回（P7-001）：用注册的打开命令打开 Writer 和演示的测试文档、选中 `DRAFT`，执行选区替换。替换照常在 WPS 里完成并保存，只是在本进程里把它报告的读回换掉（`undo_injection.py`，产品代码没有开关），于是命令判定写入失败、在 WPS 里撤回。记录写入前、撤回前、撤回后的文件哈希，错误码，回滚结果，磁盘上的文字，以及 WPS 是否报告已保存。`--scenario writer-replace` 或 `presentation-replace` 只跑一个 |
| `close-diag` | 先做 `prereq`（不问 `claude`），再查常规打开的工作簿为什么关不上（P8-005）：每种关法都新写一个工作簿，用注册的打开命令打开（和双击一样），再用这一种方法关：`Close()`、`Close($false)`、三个参数都给的 `Close`、先设 `Saved=$true` 再 `Close()`、经 `$app.Workbooks.Item(名字)` 拿到的对象、Running Object Table 里登记的对象本身、绕过 PowerShell COM 适配层的 `InvokeMember`、关它唯一的窗口；另用 `/Automation` 启动做对照组（`Close()`、`Close($false)`）。记录脚本怎么连上的、工作簿在不在 Running Object Table 里、调用失败时最内层异常的 HRESULT 和消息、两秒后 `Workbooks` 里还有没有它、`open-documents` 还列不列出它，以及之后的 WPS 进程和命令行（命令行带 `recover` 的是恢复实例）。之后用 runner 的清理关掉剩下的、结束这次启动的进程。只动它自己写的工作簿（`workbook_close.py`）。`--method` 和 `--launch` 可以只跑一部分 |
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

每次运行写到 `scripts/windows_check/results/<时间>-<提交号>-eval/`（`undo` 是 `<时间>-<提交号>-undo`，`close-diag` 是 `<时间>-<提交号>-close-diag`，`wheel` 是 `<时间>-wheel-<版本>`），可以直接提交：

- `RESULTS.md`：日期、提交、机器、WPS 版本、前提检查，以及评测表（格式和 `docs/AGENT_E2E_EVAL.md` 一样）、每次运行没通过的检查、准备失败、Agent 错误、错误码、清理结果，最后列出跑完后还在的 WPS 进程；`undo` 列出每个场景的哈希、错误码和每个通过条件；`wheel` 则列出每个通过条件。
- `results.json`：同样的内容，供机器读取；`eval` 中断时它也是续跑的依据。
- `summary.json`：`eval` 时 runner 的原始汇总。

评测的任务工作区放在系统临时目录（`%TEMP%\wps-windows-check\<目录名>`）下，不进结果目录。

`tests/test_windows_check.py` 用假的机器测试前提检查、续跑和结果格式，`tests/test_undo_injection.py` 用假的 WPS 测试注入和 `undo` 的结果，`tests/test_workbook_close.py` 测试 `close-diag` 的记录、结果格式，并让每种关法的脚本对着假的 WPS 跑一遍；`wheel` 在 Linux 上用 `v0.3.0` 的 Release 实际跑过一次。
