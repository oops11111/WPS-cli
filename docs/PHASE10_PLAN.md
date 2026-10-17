# Phase 10 计划：写入结果自证、图表和图形可撤回

状态：**done**（2026-10-16 确认，2026-10-17 完成）。

K1 到 K3 都已达成，证据在下面的“P10-006 结果”和 `scripts/windows_check/results/` 里：

- K1：`main@ab92a42` 上 16 个已打开文档任务一条命令各 3/3，`wrong_tool_calls` 0，`off_path_calls` 11（P9-006 是 50）。
- K2：`main@9c5a009` 上 `undo` 四个场景都通过，包括新的文本框和图表标题两个：注入读回失败后在 WPS 里撤回，文件内容与写入前的备份一致。
- K3：`v0.7.0` 从 `main@ab92a42` 发布，wheel 在 Windows 上通过全部 7 个条件。

遗留缺口（不是出口标准）：

- 让 K2 在 Windows 上通过的选区判断修复（#107）在 `v0.7.0` 之后合并，在 `[Unreleased]`；0.7.0 里选中文本框或图表标题时仍会被当成系列而拒绝写入。下一个版本（0.7.1）应尽快发布。
- 剩下的 8 次写入后额外调用：Writer 插入后的 `snapshot_document`、`validate_document`，表格写入后的 `spreadsheet_read`。
- 坐标轴标题和系列值的撤回只有假 COM 测试，`undo` 没有这两种场景。
- P7-007 的 `0x800A01A8` 原因没查清；兼容矩阵只有一个 WPS 版本（P5-010）；PRD 未做项（形状和图表几何、混合格式重建、准确页码）；没有发布到 PyPI。

## 目标

Phase 9 之后，16 个已打开文档任务在 Windows 上都是 3/3，Agent 不再用错工具，上机也不用手工清理。剩下最明显的两个问题：

1. **Agent 写完还要自己再查一遍。** P9-006 的 48 次运行里有 50 次不在预期路径上的调用（`off_path_calls`），其中 38 次发生在写入之后（按 P10-001 的分类，见下文）：`spreadsheet_read` 10 次、`snapshot_document` 9 次、`validate_document` 8 次、`operation` 5 次等。选区写入其实已经保存并读回核对过（`read_back_text`、`validation_passed`），但结果只给了选区本身，没有说明“文档里现在是什么样”，Agent 就自己再读一次。每次多读一次就多一轮、多一次 WPS 调用，还可能读到用户正在改的内容。
2. **表格里的图表和图形选区写入失败时不能在 WPS 里撤回。** P7-001 让 8 个已打开文档写入命令失败时在 WPS 里撤回，但表格的形状文字、图表标题、坐标轴标题和系列值没有记录原值，失败时只返回 `MUTATION_ROLLBACK_IN_WPS_FAILED` 和恢复说明，要用户自己处理。

Phase 10 做这两件事，最后发布 0.7.0。

## 输入：Phase 9 留下的缺口

| 缺口 | 出处 |
| --- | --- |
| Agent 写入后再调用读取和核对工具，`off_path_calls` 合计 50，38 次在写入之后 | P9-006 的 `results.json` |
| 表格的图表和图形选区写入失败时不能在 WPS 里撤回 | P7-001 |
| P7-007 的 `0x800A01A8` 原因没查清 | `docs/PHASE8_PLAN.md` 开头 |
| 兼容矩阵只有一个 WPS 版本 | P5-010 |
| PRD 未做项：形状和图表的几何、选区替换的混合格式重建、准确页码 | `docs/PRD_V1_2_OPEN_DOCUMENT_OPERATIONS.md` |
| 没有发布到 PyPI | `docs/RELEASING.md` |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| K1 | 写入结果自证，Agent 不再自己核对 | 离线：每个已打开文档写入命令（Writer、演示、表格的选区替换、插入、删除，保存、另存为和文本导出）的结果带 `verified_state`：从保存后的文件读回的、足以判断写对了的内容（Writer 和演示是所在段落或文本框的全文，表格是所在工作表名和写入区域的值），以及一句说明核对了什么；这些工具的 MCP 说明写明结果已经核对过，不需要再调用读取或快照工具；离线测试。Windows：全部 16 个已打开文档任务用一条 `--repeat 3 --min-passes 2` 命令跑完，每个至少 2/3，`wrong_tool_calls` 合计 0，`off_path_calls` 合计不超过 20（P9-006 是 50） |
| K2 | 图表和图形写入失败可在 WPS 里撤回 | 离线：表格的形状文字、图表标题、坐标轴标题和系列值的选区替换和删除，在写入前记录原值，读回失败时写回原值、保存、再读回核对，结果写明 `rolled_back_in_wps`；撤回失败才返回 `MUTATION_ROLLBACK_IN_WPS_FAILED`；每种对象有假 COM 测试。Windows：`run_windows_check.py undo` 增加形状文字和图表标题两种情形，注入读回失败后 WPS 里的内容和文件都回到写入前 |
| K3 | 发布 0.7.0 | 按 `docs/RELEASING.md` 发布 `v0.7.0`，包含 K1、K2 的改动；用 `run_windows_check.py wheel` 在 Windows 上检查 wheel |

## 已做的决定

2026-10-16 确认，均按默认建议：

| 决定 | 结论 | 依据 |
| --- | --- | --- |
| Phase 10 做什么 | 上面两件事加发布 0.7.0 | 一件来自 P9-006 的实测数据，一件是 P7-001 明确留下的；都能离线做完，一次上机验证 |
| 怎么减少核对调用 | 写入结果带 `verified_state`，MCP 说明写明已核对；不禁止、不拦截读取工具 | 50 次额外调用里 38 次在写入之后，说明 Agent 缺的是“写对了”的证据；拦截会妨碍正常的读 |
| K1 的门槛 | `off_path_calls` 合计不超过 20 | 写入之后的 38 次如果大部分消失，剩下的主要是写入之前的 12 次 |
| 图表和图形怎么撤回 | 写入前经 COM 读出原值（文字、标题是否显示、系列值），失败时写回 | 和 P7-001 的单元格撤回同一个思路；WPS 的撤销栈经 COM 不可靠 |
| 版本号和其余缺口 | 0.7.0（K1 给写入结果加字段，K2 改变失败时的行为，按 `docs/RELEASING.md` 升次版本）；`0x800A01A8`、第二个 WPS 版本、PRD 未做项和 PyPI 留在缺口里 | 前两个没有新的复现条件；PRD 未做项各自都是一个阶段的量 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P10-001 | K1 | 按 P9-006 的工具调用记录，把 50 次额外调用逐个归类（写入前定位、写入后核对、其他），写进本文件，确定 `verified_state` 每个组件要给什么（已完成：见下文“P10-001 结果”） | 本地 |
| P10-002 | K1 | 已打开文档写入命令的结果加 `verified_state`；MCP 说明加一句“结果已核对”；离线测试（已完成：`verified_state.py`，11 个命令；`check` 接在 `summary` 后面；`tests/test_verified_state.py`） | 本地 |
| P10-003 | K1 | 评测汇总区分写入前和写入后的 `off_path_calls`，`RESULTS.md` 显示；离线测试（已完成：`off_path_calls_before_write` 和 `off_path_calls_after_write`，`RESULTS.md` 多一列和一句合计；用在 P9-006 的记录上得到 12 和 38） | 本地 |
| P10-004 | K2 | 表格形状文字、图表标题、坐标轴标题和系列值的写入记录原值，失败时在 WPS 里写回；假 COM 测试（已完成：`open_document_scripts/object_revert.py`。原值就是写入前读到的选区文字，系列另外记录写入前的 `SERIES` 公式，撤回时先写回公式，让系列重新引用单元格。撤回沿用写入脚本找对象的方式（经当前选区，并核对对象名）；对象里是本次写入的文字或 WPS 读回的文字才写回，否则不动；选区已经换了的，记为 `revert_target_missing`；`tests/test_object_undo_powershell.py`、`tests/test_undo_in_wps.py`） | 本地 |
| P10-005 | K2 | `run_windows_check.py undo` 增加形状文字和图表标题两种情形（测试工作簿带一个形状和一个图表）；离线测试（已完成：场景 `spreadsheet-shape-text-replace` 和 `spreadsheet-chart-title-replace`，测试工作簿 `chart_note.xlsx`：图表 `Chart 1` 标题 `DRAFT`、文本框 `Note 1` 文字 `DRAFT`；准备步骤按名称选中文本框或图表标题；磁盘上的文字包括图形和图表里的文字，撤回后要和写入前一样） | 本地 |
| P10-006 | K1、K2 | 在 Windows 上：全部已打开文档任务一条命令各跑 3 次，再跑 `undo`（已完成：见下文“P10-006 结果”。K1 在 `ab92a42` 上达成；`undo` 第一轮两个新场景在写入前被拒，修复后在 `9c5a009` 上重跑 4/4） | Windows |
| P10-007 | K3 | 定版本 0.7.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.7.0` 标签（已完成：`v0.7.0` 从 `main@ab92a42` 发布） | 本地 + 你 |
| P10-008 | K3 | 在 Windows 上检查 0.7.0 的 wheel（已完成：`ab92a42` 上通过，SHA-256 与 Release 一致，safe 档 7/7，结果在 `scripts/windows_check/results/20261017T044542Z-wheel-0.7.0/`） | Windows |

## P10-001 结果

按 P9-006 的 `results.json` 逐次归类。“写入”指第一次不是 `dry_run` 的已打开文档写入调用（选区替换、插入、删除，保存、另存为、文本导出）；之前的算写入前，之后的算写入后。P10-003 的评测用同一条规则。

| 位置 | 次数 | 工具（次数） | 看上去在做什么 |
| --- | --- | --- | --- |
| 写入后 | 38 | `spreadsheet_read` 10、`snapshot_document` 9、`validate_document` 8、`operation` 5、`spreadsheet_sheets` 2、`export_open_document_text`、`spreadsheet_inspect`、`mutation_request_inspect`、`list_backups` 各 1 | 核对写入：Writer 用 `validate_document contains` 查新文字在不在，表格读回写入区域所在的整片单元格，演示和保存后用 `snapshot_document` 看整个文档，按 `request_id` 用 `operation` 查操作记录 |
| 写入前 | 12 | `spreadsheet_read` 5、`spreadsheet_sheets` 4、`snapshot_document` 2、`scan_dir` 1 | 定位：表格任务先看有哪些工作表、选区周围是什么。`spreadsheet_selection_read` 的说明写着“完整的值请用 spreadsheet-read”，也在引导这一步 |

由此确定 `verified_state` 给什么（P10-002 已按此实现）：

- 写入后的核对都在问“文件里现在是不是我要的样子、别处有没有被改”。所以 `verified_state` 不是再读一遍选区，而是把保存后的文件和写入前的备份逐项比较：Writer 按段落，演示按幻灯片上的文本框，表格按单元格（含工作表名）。结果列出每处改动的前后内容（最多 20 处）、`passed`，和一句 `check` 说明；这句话也接在 CLI 和 MCP 的 `summary` 后面。
- 判定：Writer 和演示要求有一个段落或文本框的改动正是这次写入（含写入的文字、不再含删掉的文字，长度变化等于两者之差）；WPS 保存时若还改了别处，照样列出并写明写入解释不了的改动有几处（`other_changes`），不算失败；表格要求改动的单元格都在选区内（删除时都变为空）；表格的图形和图表写入要求没有单元格变化，并写明 WPS 保存后读回的文字。保存和文本导出读回文件，另存为读出新文件的概况。
- 读不了的格式（`.doc`、`.et` 等）不比较，`source` 写 `wps_read_back`，说明只在 WPS 里读回过。
- 这些工具的 MCP 说明加一句：结果已核对，不需要再调用 `snapshot_document`、`validate_document`、`spreadsheet_read`、`export_open_document_text` 或 `operation`。
- 写入前的定位：`spreadsheet_selection_read` 的说明改为“选区读最多取 100 格，已覆盖选区写入允许的全部范围，写入前不需要另读”；不另加字段。

## P10-006 上机步骤

在合并了本阶段改动的 `main` 上，先 `git pull`，再按顺序运行（上机前不需要手工清理 WPS，Phase 9 起 runner 会让 WPS 正常退出）：

```
python scripts/windows_check/run_windows_check.py eval --prefix wps-open- --repeat 3 --min-passes 2
python scripts/windows_check/run_windows_check.py undo
```

第一条对应 K1：看 `RESULTS.md` 里 16 个任务是否都至少 2/3、`wrong_tool_calls` 合计是否为 0、`off_path_calls` 合计是否不超过 20（新的一列是其中写入之后的次数）。第二条对应 K2：四个场景都要通过，其中 `spreadsheet-shape-text-replace` 和 `spreadsheet-chart-title-replace` 是新的；如果准备步骤选不中文本框或图表标题，结果里会写成准备失败和原因。两次的结果目录都提交到 `cursor/phase10-windows-<提交号>` 分支。

## P10-006 结果

第一轮在 `main@ab92a42` 上，结果在 `scripts/windows_check/results/20261016T221731Z-ab92a42-eval/` 和 `20261017T042304Z-ab92a42-undo/`。评测中途因会话结束停在第 9 个任务，用 `eval --resume` 接着跑完，同一个结果目录。

- **K1 达成。** 16 个任务都是 3/3，`wrong_tool_calls` 合计 0，`off_path_calls` 合计 11（写入前 3、写入后 8），P9-006 是 50（12、38）。剩下的写入后调用是 Writer 插入后的 `snapshot_document`、`validate_document`，和表格写入后的 `spreadsheet_read`。48 次清理都让 WPS 正常退出，`documents_outside` 都为空。
- **K2 未达成。** `writer-replace` 和 `presentation-replace` 照旧通过；两个新场景 `spreadsheet-shape-text-replace` 和 `spreadsheet-chart-title-replace` 在写入前就以 `SELECTION_MISMATCH`（“The current series values do not match expected_selection_text.”）拒绝，什么也没写。
  - 原因：表格选区读脚本用“访问某个成员会不会报错”来分辨选中的是什么。真实 WPS 对对象没有的成员返回空值、不报错，于是图表标题被当成系列（读的是它的父对象图表的 `Values`，读回空字符串），文本框也走进了系列和坐标轴的判断。形状写入脚本判断“是不是图表的一部分”（`$sel.Parent.HasTitle`）也有同样的问题，对文本框会拒绝。
  - 修复：这几处改为检查取到的值是否为空（系列要求 `Values` 有值且父对象有 `ChartType`；坐标轴要求 `HasTitle` 和 `AxisTitle` 都有值；图表部件要求 `Parent.HasTitle` 有值），在报错和返回空值两种行为下都成立。撤回脚本沿用写入脚本的开头，一并改好。假 COM 测试按 WPS 的这种行为写（缺的成员返回空值），旧脚本在这些测试上的失败和 Windows 上一样。
  - `undo` 的结果现在记下命令读到的选区（类型、对象名、文字和 `has_*`），写入前被拒时也能看出原因。
- **K2 达成（重跑）。** 修复（#107）合并后在 `main@9c5a009` 上重跑 `undo`，四个场景都通过，结果在 `scripts/windows_check/results/20261017T054506Z-9c5a009-undo/`。两个新场景都在写入后被注入读回失败，命令报告 `VALIDATION_FAILED` 和 `MUTATION_ROLLED_BACK`，撤回读回 `DRAFT`，保存后的文件内容与写入前的备份一致，WPS 报告已保存。`v0.7.0` 已在修复之前从 `ab92a42` 发布，所以这个修复在 `[Unreleased]`，随下一个版本发布；K2 看的是 `undo` 在 `main` 上的结果。
- **K3 达成（P10-008）。** `v0.7.0` 从 `main@ab92a42` 发布，wheel 在 Windows 上通过全部 7 个条件（SHA-256 与 Release 一致，safe 档 7/7），结果在 `scripts/windows_check/results/20261017T044542Z-wheel-0.7.0/`。

## 出口标准结果

| # | 结果 | 依据 |
| --- | --- | --- |
| K1 | 达成 | P10-002、P10-003；P10-006 16/16 都 3/3，`wrong_tool_calls` 0，`off_path_calls` 11 |
| K2 | 达成 | P10-004、P10-005；`9c5a009` 上 `undo` 4/4（选区判断的修复在 #107） |
| K3 | 达成 | `v0.7.0` 已发布，wheel 在 Windows 上通过（P10-008）；#107 的修复在 0.7.0 之后，待下一个版本 |

## 建议顺序

1. 先做 P10-001，再做 P10-002 和 P10-003；P10-004 和 P10-005 可以同时做。
2. 一次上机做完 P10-006。
3. 最后做 P10-007 和 P10-008。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Agent 不管结果怎么写都习惯再查一遍 | K1 的 `off_path_calls` 降不到 20 | P10-003 区分写入前后，先看剩下的是哪一类；再看是说明没被读到，还是 `verified_state` 不够 |
| `verified_state` 读回整段或整片区域，结果变大或变慢 | 响应变长，大文档上变慢 | 每处改动的前后文字超过 500 字符时截断，最多列 20 处并写明 `changes_truncated`；只读文件，不经 WPS |
| WPS 经 COM 写回图表系列值或标题显示状态的行为和读出的不一致 | K2 的撤回核对不通过 | 核对按读出的原值比较；写回仍不一致时返回 `MUTATION_ROLLBACK_IN_WPS_FAILED`，并在 `undo` 结果里记录差异 |
| 测试工作簿里的图表在 WPS 里打开后选不中 | `undo` 的新情形跑不起来 | runner 已能经 COM 选中单元格，图表和形状改为经 `Shapes(name).Select()` 选中；选不中时该情形记为跳过并写明原因 |
