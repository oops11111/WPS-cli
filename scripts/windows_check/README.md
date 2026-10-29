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
python scripts/windows_check/run_windows_check.py wheel --version 0.9.0 --source pypi
python scripts/windows_check/run_windows_check.py --installed undo
```

| 子命令 | 做什么 |
| --- | --- |
| `prereq` | 只检查机器，见下表；有必需项没通过时退出码为 1 |
| `eval` | 先做 `prereq`，再逐个任务跑评测（默认 `--repeat 3 --min-passes 2`，不给 `--only` 或 `--prefix` 就跑全部任务；`--prefix wps-open-` 跑 id 以它开头的所有任务，可以和 `--only` 一起用）。每跑完一个任务就保存进度；中断后用 `--resume <结果目录>` 只跑剩下的任务 |
| `undo` | 先做 `prereq`（不问 `claude`），再检查已打开文档写入失败时在 WPS 里的撤回（P7-001，P10-005）：用注册的打开命令打开 Writer 和演示的测试文档、选中 `DRAFT`，以及一个带图表（标题和数值轴标题都是 `DRAFT`，系列引用 `B2:B3`）和文本框（文字 `DRAFT`）的工作簿、选中文本框、图表标题、数值轴标题或系列，执行选区替换（P11-006）。替换照常在 WPS 里完成并保存，只是在本进程里把它报告的读回换掉（`undo_injection.py`，产品代码没有开关），于是命令判定写入失败、在 WPS 里撤回。记录写入前、撤回前、撤回后的文件哈希，错误码，回滚结果，磁盘上的文字，以及 WPS 是否报告已保存。`--scenario writer-replace`、`presentation-replace`、`spreadsheet-shape-text-replace`、`spreadsheet-chart-title-replace`、`spreadsheet-axis-title-replace` 或 `spreadsheet-series-values-replace` 只跑一个；工作簿磁盘上的文字包括图形和图表里的文字，以及系列引用的单元格区域，撤回系列值后引用要回来 |
| `close-diag` | 先做 `prereq`（不问 `claude`），再查常规打开的工作簿为什么关不上（P8-005）：每种关法都新写一个工作簿，用注册的打开命令打开（和双击一样），再用这一种方法关：`Close()`、`Close($false)`、三个参数都给的 `Close`、先设 `Saved=$true` 再 `Close()`、经 `$app.Workbooks.Item(名字)` 拿到的对象、Running Object Table 里登记的对象本身、绕过 PowerShell COM 适配层的 `InvokeMember`、关它唯一的窗口；先在另一个进程里写入 A1 并保存、再 `Close()` 或 `Close($false)`（P7-007 关不上的工作簿就是刚被写入保存过的）；以及产品自己的路径：备份、写入并保存、再 `restore-backup --close-in-wps`，看它是否关上并恢复成功；另用 `/Automation` 启动做对照组（`Close()`、`Close($false)`）。记录脚本怎么连上的、工作簿在不在 Running Object Table 里、调用失败时最内层异常的 HRESULT 和消息、两秒后 `Workbooks` 里还有没有它、`open-documents` 还列不列出它，以及之后的 WPS 进程和命令行（命令行带 `recover` 的是恢复实例）。之后用 runner 的清理关掉剩下的、结束这次启动的进程。只动它自己写的工作簿（`workbook_close.py`）。`--method` 和 `--launch` 可以只跑一部分 |
| `wheel` | 从 Release 下载 wheel，与 Release 列出的 SHA-256 对比；在新的虚拟环境里只装它，不带 `PYTHONPATH`，在仓库以外跑 `inspect-env` 和 safe 档。`--source pypi` 改为用 pip 从 PyPI 下载同一版本的 wheel，SHA-256 仍要和 Release 列出的一致（P12-005） |

`mcp_client_smoke.py --out <目录>`（Phase 14，P14-005）不经 runner，单独运行：读 Claude Desktop 配置里的 `wps-agent` 条目，像 Claude Desktop 一样从另一个目录启动它的命令，只传 MCP SDK 默认的那几个环境变量加上条目里的 `env`（`--inherit-env` 改为传当前 shell 的全部环境变量）。然后经 stdio 做 `initialize` 和 `tools/list`，再复制 `fixtures/fidelity/book.xlsx`、登记、读一块区域、写一个单元格并读回、列出备份，检查备份在 `WPS_AGENT_WORKSPACE` 下、启动目录里没写东西。每次请求最多等 `--timeout` 秒（默认 180）。结束后删掉这次登记的工作簿在数据目录里的备份文件夹（`--keep-backup` 保留）；登记记录没有工具能删，会留着。结果写到 `<目录>/MCP_CLIENT_SMOKE.md` 和 `mcp-client-smoke.json`，服务器启动失败或中途出错时也写；报告只记 `env` 里的变量名，不记值。只用标准库。`tests/test_mcp_client_smoke.py` 在 Linux 上对着本仓库的服务器跑到写入那一步（写入要 WPS），并测超时、启动失败、非 JSON 输出和环境变量。

`odt_probe.py --out <目录>`（Phase 13，B-odt-docx）不经 runner，单独运行：把 WPS 自己写的 ODT、LibreOffice 的 `brief.odt`、去掉缩略图和设置的同一文件，以及三份手写的最小 ODT 各转一次 docx（每次 60 秒超时，之间结束 WPS），结果写到 `<目录>/odt-probe.json`，说明 WPS 打开哪些 ODT 时会弹“文件损坏提示”。

放在子命令前面的 `--installed` 让检查和评测 runner 用当前 Python 里安装的 `wps-ai-agent-cli`（比如从 PyPI 装的），不再把仓库的 `src/` 加进路径或 `PYTHONPATH`；`prereq` 会多一项 `installed package`，要求包来自 `site-packages`。`RESULTS.md` 开头的 `Package` 一行写明被测包的版本和路径。干净账户上的用法见 `docs/COMPATIBILITY_MATRIX.md` 的“干净环境”一节（P12-007）。

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

- `RESULTS.md`：日期、提交、机器、WPS 版本、前提检查，以及评测表（格式和 `docs/AGENT_E2E_EVAL.md` 一样，另有 `wrong_tool_calls` 一列和合计：已打开文档任务里调用按文件写入工具的次数；`off_path_calls` 旁边一列是其中发生在第一次写入之后的次数，P10-003；每次写入返回的 `verified_state` 记在 `results.json` 里，`passed` 不是 true 的写入列在每次运行下面，P11-004）、每次运行没通过的检查、准备失败、Agent 错误、错误码、清理结果、WPS 在任务工作区以外打开着的文档（比如它从上一次会话重新打开的；只记录，不关），最后列出跑完后还在的 WPS 进程；`undo` 列出每个场景的哈希、错误码和每个通过条件；`wheel` 则列出每个通过条件。
- `results.json`：同样的内容，供机器读取；`eval` 中断时它也是续跑的依据。
- `summary.json`：`eval` 时 runner 的原始汇总。

评测的任务工作区放在系统临时目录（`%TEMP%\wps-windows-check\<目录名>`）下，不进结果目录。

`tests/test_windows_check.py` 用假的机器测试前提检查、续跑和结果格式，`tests/test_undo_injection.py` 用假的 WPS 测试注入和 `undo` 的结果，`tests/test_workbook_close.py` 测试 `close-diag` 的记录、结果格式，并让每种关法的脚本对着假的 WPS 跑一遍；`wheel` 在 Linux 上用 `v0.3.0` 的 Release 实际跑过一次。
