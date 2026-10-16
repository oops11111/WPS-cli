# Phase 8 计划：中文内容和常规打开的工作簿

状态：**active**（2026-10-16 确认，五项决定均按默认建议）。

## 目标

Phase 7 在 Windows 上一共跑了四轮才全部通过。中间暴露的问题有两类，Phase 7 只修到能让评测通过：

1. **中文内容从来没有被测过。** 评测和回归里的文字全是 ASCII（`DRAFT`、`FINAL`、`(v2)`）。中文 Windows（cp936）是本项目的目标平台，但非 ASCII 文本经过的三条路径里，有两条在 0.4.0 里是坏的：PowerShell 脚本的输出、MCP 服务器读 stdin。直到唯一一个带中文参数的任务（未命名文档 `文字文稿1`）连续失败，才被发现。修复在 `[Unreleased]`，还没发布；而且只修了被碰到的路径，其余路径（中文文件名、中文工作表名、写入中文文字、中文错误信息）仍然没有任何测试。
2. **常规打开的工作簿关不上。** 经 Running Object Table 拿到的工作簿，`Close()` 报 `0x800A01A8`（之前 `Close($false)` 报 `RPC_E_SERVERFAULT`），第四轮 6 次全是。评测靠结束整个 `et` 进程绕过；但产品里的 `restore-backup --close-in-wps` 对用户双击打开的工作簿仍然会失败，而 Phase 4 做这个功能，就是为了让用户不必自己去关。

Phase 8 把这两件事做完，先尽快把已经修好的发出去（0.4.1），最后发布 0.5.0。

## 输入：Phase 7 留下的缺口

| 缺口 | 出处 |
| --- | --- |
| 0.4.0 带着 PowerShell 输出和 MCP stdin 的编码缺陷，修复在 `[Unreleased]` 未发布 | P7-007 第一、二轮，`CHANGELOG.md` |
| 中文文件名、中文工作表名、写入中文、中文错误信息没有任何测试；评测任务全是 ASCII | P7-007 第三轮复核 |
| 经 Running Object Table 拿到的工作簿关不上（`0x800A01A8`），`restore-backup --close-in-wps` 对常规打开的工作簿失败 | P7-007 第四轮，`docs/PHASE7_PLAN.md` 开头 |
| WPS 启动时重新打开上一次会话的文档，评测结果里混进别的文档，要靠人记得先关掉 | P7-007 第三轮 |
| 表格里的图表和图形选区写入失败时不能在 WPS 里撤回 | P7-001 |
| 兼容矩阵只有一个 WPS 版本 | P5-010 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| I1 | 中文内容端到端可用 | 离线：用真实进程、GBK 区域设置（`PYTHONIOENCODING=gbk`）测试 CLI 的参数、stdin、stdout 和 MCP 服务器，中文路径、中文文档名、中文写入文字、中文工作表名原样到达并原样返回；每个经 PowerShell 的组件（Writer、表格、演示）至少一个假 COM 测试让中文在脚本里往返。Windows：至少 4 个新评测任务带中文内容（中文写入文字、中文文件名、中文工作表名、中文的未命名文档另存），用一条 `--repeat 3 --min-passes 2` 命令跑完，每个至少 2/3 |
| I2 | 常规打开的工作簿能关 | `close_unchanged_document` 对常规打开（经 Running Object Table）的工作簿关闭成功并确认 WPS 不再列出它；在 Windows 上 `restore-backup --close-in-wps` 对双击打开的工作簿关闭并恢复成功，结果写进仓库。做不到时，返回专门的错误码，写明原因和用户该怎么做，并在 Windows 上验证这个错误码 |
| I3 | 发布 0.4.1 和 0.5.0 | 先按 `docs/RELEASING.md` 发布 `v0.4.1`（只含 `[Unreleased]` 里已有的修复）；Phase 8 最后发布 `v0.5.0`，包含 I1 和 I2 的改动。两次都用 `run_windows_check.py wheel` 在 Windows 上检查 wheel |

## 已做的决定

2026-10-16 确认，均按默认建议：

| 决定 | 结论 | 依据 |
| --- | --- | --- |
| 0.4.1 什么时候发 | Phase 8 第一个任务，立刻发，不等 I1、I2 | 0.4.0 里所有经 MCP 的中文参数都是乱码，修复已经在 `main` 上 |
| 中文评测任务选哪些 | 4 个：Writer 选区替换成中文、表格写入中文工作表名的单元格、导出中文文件名的已打开文档、把中文内容的未命名文档另存为中文文件名 | 覆盖参数、文件名、工作表名、文档名四条路径；每条在 0.4.0 里都可能坏 |
| 工作簿关不上怎么修 | 先写一个只读的 Windows 诊断脚本，在一个常规打开的工作簿上依次试几种关法（`Close()`、`Close($false)`、`Saved=$true` 后 `Close()`、经 `$app.Workbooks.Item(名字)` 拿到的对象、`/Automation` 启动的对照组），记录每种的 HRESULT；按结果选一种实现。都不行就返回专门的错误码 | 原因没查清就改，Phase 7 已经试了两次都没对 |
| WPS 重开上一次会话的文档怎么处理 | runner 在每次运行开始时记录 WPS 列出的、不在任务工作区里的文档，写进结果；`prereq` 不负责清理 | 这是机器状态，不该由脚本去关用户的文档；记录下来复核时能看出来 |
| 第二个 WPS 版本、图表和图形选区的撤回 | 都不作为出口标准，留在缺口里 | P5-010 仍然没有条件；图表和图形选区的撤回没有评测任务，也没有用户反馈 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P8-001 | I3 | 定版本 0.4.1，把 `[Unreleased]` 改成 `[0.4.1]`，合并后由你推送 `v0.4.1` 标签（已准备：`__version__` 为 `0.4.1`，`CHANGELOG.md` 有 `[0.4.1] - 2026-10-16` 一节；标签待推送） | 本地 + 你 |
| P8-002 | I3 | 在 Windows 上用 `run_windows_check.py wheel --version 0.4.1` 检查 Release 的 wheel（已完成：`4731b04` 上通过，SHA-256 与 Release 一致，safe 档 7/7，结果在 `scripts/windows_check/results/20261016T021230Z-wheel-0.4.1/`） | Windows |
| P8-003 | I1 | 查遍所有进出 Python 进程的文本：CLI 参数、stdin、stdout、stderr、子进程、文件读写的默认编码；补齐 GBK 区域设置下的真实进程测试，以及每个组件的中文假 COM 往返测试（已完成：`tests/test_chinese_text.py`；查出并修了两处：Writer 结构校验脚本用 `-File` 运行、没有 UTF-8 输出设置，CLI 的 stderr 不是 UTF-8） | 本地 |
| P8-004 | I1 | runner 支持中文测试文档（中文文件名、中文文字、中文工作表名）；编写 4 个中文评测任务，每个补离线判定测试（已完成：`季度报告.docx`、`状态表.xlsx`（工作表 `汇总`）两个中文测试文档，4 个 `wps-open-zh-*` 任务，提示也是中文；纯文本导出按 GBK 回退读取；`run_windows_check.py eval --prefix wps-open-` 一条命令跑全部已打开文档任务） | 本地 |
| P8-005 | I2 | 只读的 Windows 诊断脚本：在常规打开的工作簿上试几种关法并记录 HRESULT，`/Automation` 启动作为对照组；由 `run_windows_check.py` 运行并写出结果（本地部分已完成：`run_windows_check.py close-diag`，`scripts/windows_check/workbook_close.py`，8 种关法加 2 个对照。第一次上机见下文“P8-005 结果”：未改动的工作簿 10 种关法全部关上，没复现；第二次上机加了“先写入保存再关”和 `restore-backup --close-in-wps` 两类，也都关上，见下文。已完成） | 本地 + Windows |
| P8-006 | I2 | 按 P8-005 的结果修 `close_unchanged_document`（以及 runner 的清理）；修不了就加专门的错误码。补假 COM 测试（错误码部分已完成：WPS 拒绝关闭且仍列出文档时返回 `WPS_CLOSE_REFUSED`，说明原因和处理办法，两种结局都需要它兜底；换哪种关法等 P8-005 上机结果。已完成：两次上机所有关法都关上，产品从 0.4.1 起用的 `Close()` 不用换；`WPS_CLOSE_REFUSED` 留作兜底） | 本地 |
| P8-007 | 缺口 | runner 在每次运行开始时记录 WPS 列出的、不在任务工作区里的文档，写进 `RESULTS.md`（已完成：fixture 在 WPS 里打开后、后续准备步骤之前列一次，记在每次运行的 `documents_outside`；`RESULTS.md` 每次运行一行，另有一节按文档汇总） | 本地 |
| P8-008 | I1、I2 | 在 Windows 上：4 个中文任务和现有 11 个已打开文档任务一条命令各跑 3 次；`restore-backup --close-in-wps` 对双击打开的工作簿验证一次（后一半已由 P8-005 第二次上机的 `restore_close_in_wps` 完成；剩下评测） | Windows |
| P8-009 | I3 | 定版本 0.5.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.5.0` 标签 | 本地 + 你 |
| P8-010 | I3 | 在 Windows 上检查 0.5.0 的 wheel | Windows |

## P8-005 结果

### 第一次上机（`4731b04`，2026-10-16）

结果在 `scripts/windows_check/results/20261016T021338Z-4731b04-close-diag/`。

- **没复现。** 双击方式打开（经 Running Object Table 连上）的工作簿，8 种关法全部关上：调用都正常返回，两秒后 `Workbooks` 里没有它，`open-documents` 也不再列出，没有出现恢复实例。`/Automation` 对照组的 2 种也都关上。产品从 0.4.1 起先用的 `Close()` 就在其中，所以未改动的工作簿不需要换关法。
- **和 P7-007 的差别在于写入。** P7-007 关不上的工作簿，在关之前刚被 Agent 的选区替换在另一个进程里写入并保存过；这次的工作簿没被改过。所以第二次上机加了三行：先在另一个进程里写入 A1 并保存，再用 `Close()` 或 `Close($false)` 关（`write_then_close`、`write_then_close_false`）；以及产品自己的路径：备份、写入并保存、再 `restore-backup --close-in-wps`（`restore_close_in_wps`），这正是 I2 要验证的。
- **WPS 每次启动都重新打开一个 `status.xlsx`。** 第一次尝试之后 `et.exe` 40128 一直列着它，runner 的清理因此不结束进程（“WPS still lists status.xlsx”），后面 7 种关法都在这个进程里跑（打开命令把文件交给已在运行的 WPS，和用户双击一样，不影响结论）；`/Automation` 新启动的 47744 也重新打开了它。它很可能是 Phase 7 评测留下的工作簿：runner 结束 `et.exe` 时它还开着，WPS 当成异常退出，此后每次启动都恢复它（结果里只有名字，没有路径）。P8-008 之前要在 WPS 表格里把它正常关掉、再正常退出 WPS，否则评测的每次运行都会混进它（P8-007 会把它记在 `documents_outside` 里）。

### 第二次上机（`aed06e6`，2026-10-16）

结果在 `scripts/windows_check/results/20261016T033122Z-aed06e6-close-diag/`。上机前在 WPS 里关掉了每次启动都重新打开的 `status.xlsx`，这次每种关法都在自己新启动的 `et.exe` 里跑。

- **`restore_close_in_wps`：`restored`。** 双击打开的工作簿，先在另一个进程里写入 A1 并保存，再执行产品的 `restore-backup --close-in-wps`：WPS 里关掉了（`close_in_wps: closed`），A1 恢复成备份里的 `seed`。**I2 达成**：这正是出口标准要的“对双击打开的工作簿关闭并恢复成功”，由脚本执行，结果在仓库里。
- **`write_then_close`、`write_then_close_false`：都关上了。** 调用正常返回，两秒后脚本经它手里的应用对象查 `Workbooks`，已经没有这个工作簿。表里写成“returned, still open”是 `close-diag` 的判定错了：双击启动的 WPS 关掉最后一个工作簿后，Running Object Table 里就没有它的任何东西，`open-documents` 只能报 `WPS_INSTANCE_NOT_AUTOMATABLE`，列不出结果（`listed_by_cli` 为 `null`），判定把“不知道”当成了“还开着”。已改为这时以脚本自己对 `Workbooks` 的检查为准。WPS 并没有失去响应，只是没有文档可供连上它。第一次上机没出现这个现象，是因为恢复出来的 `status.xlsx` 一直在 Running Object Table 里。
- **P7-007 的 `0x800A01A8` 两次上机都没复现。** 未改动的、刚写入保存过的工作簿，各种关法都关上。当时和现在的差别只剩机器状态：P7-007 那几轮 `et.exe` 被反复结束，WPS 起了恢复实例并恢复上次的文档。产品的关法不改；万一再遇到，`WPS_CLOSE_REFUSED` 会说明原因和处理办法。

## 建议顺序

1. 先做 P8-001，你推送 `v0.4.1` 后做 P8-002。
2. 本地任务可以并行：P8-003 和 P8-004，P8-005，P8-007。
3. P8-005 的诊断要上机一次，结果回来后做 P8-006。
4. 一次上机做完 P8-008。
5. 最后做 P8-009 和 P8-010。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 工作簿关不上的原因在 WPS 本身，换哪种关法都不行 | I2 只能以专门错误码收尾 | I2 的标准已经允许这种结局；诊断脚本先跑，尽早知道 |
| 中文任务暴露更多编码问题（比如 WPS 自己按 GBK 存的文件名） | P8-008 要上机多轮 | P8-003 先在本地用 GBK 区域设置把能想到的路径都测一遍，再上机 |
| 上机轮次多（Phase 7 跑了四轮） | 阶段拖长 | 本地任务先做完；诊断脚本和评测分开上机，诊断那次很短 |
| WPS 重开上一次会话的文档影响评测 | 结果里混进别的文档 | P8-007 记录它们；上机前在 WPS 里关掉 |
