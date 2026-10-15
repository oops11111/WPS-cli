# Phase 7 计划：已打开文档的写入可撤回、全覆盖

状态：**active**（2026-10-15 确认，五项决定均按默认建议）。

## 目标

Phase 6 让已打开文档的命令能看到用户打开的文档，并证明 Agent 能在 Writer 和演示里替换、插入、保存。还有三件事没有做完：

1. **写入失败时的撤回。** 已打开文档的写入如果改了文档，但校验没通过，现在的回滚是用备份文件覆盖原文件。WPS 正开着这个文件，所以回滚一定被挡住（`MUTATION_ROLLBACK_BLOCKED`），改动留在 WPS 里。P6-008 里演示选区替换就是这样失败的。撤回应该在 WPS 里完成。
2. **评测没覆盖的写入命令。** 已打开文档的写入命令里，还有 6 个没有评测：Writer 选区删除、演示选区插入和删除、表格选区替换和删除、未命名文档另存为。P6-008 说明，这类命令只有在真实 WPS 上跑过才知道能不能用：两个缺陷都是在那里发现的。
3. **Windows 上机全靠手动。** Phase 6 在 Windows 上跑了五轮，每轮都要照着手册一条条执行，再手写结果。出过的问题包括：标签打在了错误的提交上，API 余额不足没有提前发现，runner 留下的进程要靠人去结束。

## 输入：Phase 6 留下的缺口

| 缺口 | 出处 |
| --- | --- |
| 已打开文档的写入校验失败时，回滚用备份文件覆盖，被 WPS 持有的文件挡住 | P6-008 第三次重跑的复核，`docs/AGENT_E2E_EVAL.md` |
| 6 个已打开文档写入命令没有评测：`writer_selection_delete`、`presentation_selection_insert`、`presentation_selection_delete`、`spreadsheet_selection_replace`、`spreadsheet_selection_delete`、`save_as_open_document` | 工具列表与 `config/agent_eval_tasks.json` 对比 |
| Windows 上机每步都靠手动，结果靠手写 | Phase 6 的五轮上机 |
| Agent 多次用错 `validate_document` 的参数，拿到 `INVALID_ARGUMENT` | P6-008 各次运行的 off-path 调用 |
| 兼容矩阵只有一个 WPS 版本；安装检查不是在干净机器上做的 | P5-010 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| H1 | 已打开文档的写入失败时，在 WPS 里撤回 | 8 个已打开文档写入命令里，WPS 已改动文档、但后续检查失败的，命令在同一个 WPS 实例里把改动撤回，并读回确认。结果写明 `rolled_back_in_wps`，不再因为 WPS 持有文件而返回 `MUTATION_ROLLBACK_BLOCKED`。撤回本身失败时，返回专门的错误码，写明文档现在的状态和用户该怎么做，不关闭也不保存用户的文档。每个组件都有离线测试（假 COM）；Windows 上至少验证 Writer 和演示各一次（在进程内注入读回失败，生产代码不加开关），结果写进仓库 |
| H2 | 评测覆盖全部已打开文档写入命令 | 新增至少 5 个任务，覆盖上面 6 个命令中的至少 5 个，每个任务写明预期工具。所有需要 WPS 的已打开文档任务（现有 5 个加新任务）在 Windows 上用一条 `--repeat 3 --min-passes 2` 命令跑完，每个至少 2/3 通过，不改系统打开命令 |
| H3 | Windows 检查一条命令完成 | 一个脚本完成 Windows 上的检查和记录：先查前提（`claude` 能回答、没有残留的 WPS 进程、打开命令没被改过、提交号），再跑指定的评测或 wheel 检查，最后按仓库的格式写出结果文件。H1、H2、H4 的 Windows 结果都由它生成 |
| H4 | 发布 0.4.0 | 按 `docs/RELEASING.md` 发布 `v0.4.0`，包含 H1 和 H2 的改动；标签前先确认 `__version__` 和 `CHANGELOG.md` 已在 `main` 上；Windows 上只装这个 wheel，`inspect-env` 和 safe 档通过（用 H3 的脚本） |

## 已做的决定

2026-10-15 确认，均按默认建议：

| 决定 | 结论 | 依据 |
| --- | --- | --- |
| 在 WPS 里怎么撤回 | 做反向操作：把选区原来的文字写回去（插入的删掉，删掉的插回），然后保存并读回核对。不用 WPS 的 `Undo()` | `Undo()` 撤销的步数和范围在 WPS 上没有验证过，可能把用户自己的编辑也撤掉；反向操作只碰命令自己改过的那段文字 |
| 撤回之后要不要保存 | 要。命令在写入后已经保存过，撤回后再保存一次，文件和备份一致，并用哈希核对 | 不保存的话，磁盘上留着失败的那次写入 |
| 表格评测怎么准备选区 | runner 用 COM 选中给定的单元格区域（`Range.Select()`），读回地址核对 | 和 Writer、演示的 `select_text` 一样，把准备失败和 Agent 失败分开 |
| H3 的脚本用什么写 | Python（`scripts/windows_check/`），调用现有的 runner 和 CLI，PowerShell 只用来查进程和打开命令 | runner 和判定都是 Python；结果文件格式和测试也在 Python 里 |
| 第二个 WPS 版本 | 仍然不作为出口标准；P5-010 拿到条件时再做 | 同 Phase 5、6 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P7-001 | H1 | 8 个已打开文档写入命令在 WPS 改动后失败时，改为在 WPS 里做反向操作撤回、保存、读回核对；结果写明 `rolled_back_in_wps`；撤回失败时返回新错误码。每个组件补假 COM 测试（已完成：`open_documents._undo_in_wps` 和 `open_document_scripts/revert.py`；撤回失败的错误码是 `MUTATION_ROLLBACK_IN_WPS_FAILED`。WPS 重新保存的文件和备份的字节不会相同，所以核对的是文件内容：Writer 和演示比文字，表格比每个非空单元格；表格里的图表和图形选区没有记录原值，不撤回，返回这个错误码并说明怎么恢复） | 本地 |
| P7-002 | H1 | 写进程内注入脚本：让读回校验失败，触发撤回，记录前后哈希。Writer 和演示各一个场景（已完成：`scripts/windows_check/undo_injection.py`，由 `run_windows_check.py undo` 运行并写出结果） | 本地 |
| P7-003 | H2 | runner 的 `select_text` 支持表格（单元格区域）；新增 `untitled_document` 准备步骤（在 WPS 里新建一个未命名文档并写入文字），供另存为任务使用（已完成：表格按 `selection.range` 和 `selection.sheet` 选中并读回地址；未命名文档的名字由 WPS 决定，任务的提示里写 `{untitled_name}`，runner 在开始前填入；新增表格测试文档 `status.xlsx`） | 本地 |
| P7-004 | H2 | 编写至少 5 个新任务，每个补离线判定测试（已完成：6 个任务，6 个命令都覆盖：`wps-open-writer-selection-delete`、`wps-open-presentation-selection-insert`、`wps-open-presentation-selection-delete`、`wps-open-spreadsheet-selection-replace`、`wps-open-spreadsheet-selection-delete`、`wps-open-save-as-untitled`；runner 的 `select_text` 也能在演示里放插入点） | 本地 |
| P7-005 | H3 | `scripts/windows_check/`：前提检查、调用评测或 wheel 检查、生成结果文件；离线测试覆盖前提检查和结果格式（已完成：`scripts/windows_check/run_windows_check.py`，子命令 `prereq`、`eval`、`wheel`，用法见同目录 README） | 本地 |
| P7-006 | 缺口 | 查清 Agent 为什么常用错 `validate_document`，改进它的参数说明和 `INVALID_ARGUMENT` 的错误信息 | 本地 |
| P7-007 | H1、H2 | 在 Windows 上用 P7-005 的脚本：跑 P7-002 的注入场景，再把所有已打开文档任务各跑 3 次 | Windows |
| P7-008 | H4 | 定版本 0.4.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.4.0` 标签 | 本地 + 你 |
| P7-009 | H4 | 在 Windows 上用 P7-005 的脚本检查 Release 的 wheel | Windows |

P5-010 仍留在 Phase 5 的缺口里，不在这里重复列出。

## 建议顺序

1. 先做 P7-005：后面所有 Windows 结果都用它来生成，越早有越省事。
2. 本地任务可以并行：P7-001 和 P7-002，P7-003 和 P7-004，P7-006。
3. 一次上机做完 P7-007。
4. 最后做 P7-008 和 P7-009。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 写入后选区已经变了（P6-008 见过），撤回找不准位置 | H1 的撤回改错地方 | 撤回按写入前记下的位置和原文做，写回前先核对那个位置上现在的文字正是这次写入的内容；对不上就不撤回，返回撤回失败的错误码 |
| 用户在命令执行期间自己编辑了文档 | 撤回覆盖用户的编辑 | 同上：核对不上就不动，报告给用户 |
| 表格选区的读写在 WPS 上和 Excel 行为不同 | H2 的表格任务不稳定 | 表格任务先在 P7-007 里单独试一轮；准备步骤读回地址核对 |
| 一条命令跑 10 多个任务、每个 3 次，时间长、API 花费高 | 上机时间和余额不够 | H3 的脚本先检查 `claude` 能回答；评测按任务分组记录进度，中断后可以只重跑没跑完的任务 |
| 上机次数多 | 阶段拖长 | 本地任务先做完，争取一次上机完成 P7-007 |
