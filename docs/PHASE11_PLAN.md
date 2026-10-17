# Phase 11 计划：补发选区修复、表格写入带上周围的单元格、撤回全覆盖

状态：**done**（2026-10-17 确认，2026-10-17 完成）。

L1 到 L4 都已达成，证据在下面的“P11-007 结果”和 `scripts/windows_check/results/` 里：

- L1：`v0.8.0` 从 `main@4ccd565` 发布，包含 #107 的选区修复（和 #110 的系列修复），wheel 在 Windows 上通过全部 7 个条件。
- L2：`main@20c94d8` 上 16 个已打开文档任务一条命令各 3/3，`wrong_tool_calls` 0，写入后的额外调用 3（P10-006 是 8），`verified_state.passed` 不是 true 的写入 0。
- L3：`main@4ccd565` 上 `undo` 6/6，包括新的坐标轴标题和系列值场景；系列撤回后重新引用 `Status!B2:B3`。
- L4：同 L1，`v0.8.0` 已发布并在 Windows 上检查通过。

遗留缺口（不是出口标准）：

- 剩下的 3 次写入后额外调用：Writer 替换后一次 `validate_document`，表格替换后一次 `spreadsheet_read`，另存为后一次 `operation`。
- 撤回的 Windows 场景只覆盖替换，删除（清空文字、隐藏标题、清空系列值）只有假 COM 测试。
- P7-007 的 `0x800A01A8` 原因没查清；兼容矩阵只有一个 WPS 版本（P5-010）；PRD 未做项（形状和图表几何、混合格式重建、准确页码）；没有发布到 PyPI。

## 目标

Phase 10 之后，Agent 写完基本不再自己核对，表格里的文本框和图表标题写入失败时也能在 WPS 里撤回。还剩下三件事：

1. **0.7.0 带着已知缺陷。** 让文本框和图表标题能被正确识别的修复（#107）在 `v0.7.0` 打标签之后才合并。用户装的 0.7.0 里，选中文本框或图表标题仍会被当成图表系列，写入被拒（`SELECTION_MISMATCH`）。
2. **表格写入后 Agent 还会再读一次。** P10-006 里剩下 8 次写入后的额外调用，其中 5 次是表格任务的 `spreadsheet_read`：Agent 读的是写入区域周围的单元格（`A1:D5`、`C1:D3`），想确认表头和相邻单元格没被动到。`verified_state` 只列出变了的单元格，没有给出周围的样子。另外 3 次是 Writer 插入和删除后的 `snapshot_document`、`validate_document`。评测没有记录写入工具返回了什么，所以说不清 Agent 当时看到的 `verified_state` 是什么样。
3. **撤回的 Windows 检查不全。** 坐标轴标题和系列值的撤回只有假 COM 测试。P10-006 已经说明，假 COM 和真实 WPS 的行为可能不同（缺的成员返回空值还是报错），没上机的路径不能算验证过。

Phase 11 做这三件事，最后发 0.8.0，选区修复随它一起发布。

## 输入：Phase 10 留下的缺口

| 缺口 | 出处 |
| --- | --- |
| 选区判断的修复（#107）不在 0.7.0 里 | `docs/PHASE10_PLAN.md` 开头，`CHANGELOG.md` `[Unreleased]` |
| 写入后仍有 8 次额外调用（表格 `spreadsheet_read` 5 次，Writer `snapshot_document`/`validate_document` 3 次） | P10-006 的 `results.json` |
| 评测不记录写入工具的返回内容 | `scripts/agent_eval/run_agent_eval.py` 只记录调用参数和错误码 |
| 坐标轴标题和系列值的撤回没在 Windows 上跑过 | P10-005 只加了文本框和图表标题两个场景 |
| P7-007 的 `0x800A01A8`、兼容矩阵只有一个 WPS 版本、PRD 未做项、没有发布到 PyPI | `docs/PHASE10_PLAN.md` 开头 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| L1 | 补发选区修复 | 下一个发布的版本（0.8.0）包含 #107 的修复，`CHANGELOG.md` 里该条目写明“0.7.0 有此缺陷”；随 L4 的 wheel 检查在 Windows 上验证 |
| L2 | 表格写入后不必再读 | 离线：表格选区写入和删除的 `verified_state` 带 `surroundings`：从保存后的文件读出的写入区域外扩一圈的单元格（上下左右各 1 行 1 列，并包含所在列的表头行，最多 10×10），每格写明值，以及它在写入前后是否相同；`check` 那句话写明周围没有变化；离线测试。评测的每次运行记录每个写入工具返回的 `verified_state`（`passed`、`check`、改动数），`RESULTS.md` 列出 `passed` 不是 true 的写入。Windows：全部 16 个已打开文档任务一条 `--repeat 3 --min-passes 2` 命令跑完，每个至少 2/3，`wrong_tool_calls` 合计 0，写入后的额外调用（`off_path_calls_after_write`）合计不超过 3（P10-006 是 8），所有写入的 `verified_state.passed` 都是 true |
| L3 | 撤回全覆盖 | `run_windows_check.py undo` 增加坐标轴标题替换和系列值替换两个场景（测试工作簿的图表带坐标轴标题，系列引用单元格），撤回后磁盘上图形和图表里的文字、系列引用的单元格区域都回到写入前。Windows：`undo` 6/6 |
| L4 | 发布 0.8.0 | 按 `docs/RELEASING.md` 发布 `v0.8.0`，包含 L2、L3 的改动（L2 给写入结果加字段，按规则升次版本）；在 Windows 上检查 wheel |

## 已做的决定

2026-10-17 确认：

| 决定 | 结论 | 依据 |
| --- | --- | --- |
| Phase 11 做什么 | 上面三件事，加发布 0.8.0 | 都来自 Phase 10 的实测记录 |
| 0.7.1 怎么发 | **改为不单独发 0.7.1**：选区修复（#107）随 0.8.0 发布 | 你要求本阶段的改动用一次提交完成；单独发 0.7.1 需要先有一次只升修订号的提交并打标签，再做其余改动。0.8.0 同样包含这个修复，只是晚一些 |
| 表格周围给多少 | 写入区域外扩 1 行 1 列，加上所在列的表头行（第 1 行），最多 10×10 | Agent 读的正是这个范围（`A1:D5`、`C1:D3`）；限制大小，大表上结果不会太长 |
| L2 的门槛 | 写入后的额外调用合计不超过 3，且所有写入 `verified_state.passed` 为 true | 剩下的 8 次里 5 次是表格读周围；Writer 那 3 次先靠记录下来的返回内容找原因 |
| 其余缺口 | `0x800A01A8`、第二个 WPS 版本、PRD 未做项、PyPI 留在缺口里 | 前两个没有新的复现条件；PRD 未做项各自都是一个阶段的量 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P11-001 | L1 | 选区修复的 `CHANGELOG.md` 条目归入 `[0.8.0]`，写明 0.7.0 有此缺陷（已完成：随 P11-008） | 本地 |
| P11-002 | L1 | 在 Windows 上验证修复随 0.8.0 发布（已并入 P11-009，已完成） | Windows |
| P11-003 | L2 | 表格选区写入和删除的 `verified_state` 加 `surroundings`，`check` 写明周围没变；离线测试（已完成：`verified_state.surroundings`，`tests/test_verified_state.py`） | 本地 |
| P11-004 | L2 | 评测记录每个写入工具返回的 `verified_state` 摘要，`RESULTS.md` 列出 `passed` 不是 true 的写入；离线测试（已完成：调用记录里的 `verified_state`，指标 `unverified_writes`，`RESULTS.md` 的合计和每次运行下的列表） | 本地 |
| P11-005 | L2 | 按 P11-004 记下的内容和 P10-006 的调用记录，看 Writer 插入和删除后那 3 次核对的原因；能改的就改（比如 `check` 的措辞）（已完成：见下文“P11-005 结果”） | 本地 |
| P11-006 | L3 | 测试工作簿的图表加坐标轴标题、系列引用单元格；`undo` 增加 `spreadsheet-axis-title-replace` 和 `spreadsheet-series-values-replace`；准备步骤能按名称选中坐标轴标题和系列；离线测试（已完成：`chart_note.xlsx` 的数值轴标题 `DRAFT`、系列引用 `B2:B3`；磁盘上的文字包括系列引用的区域，撤回后引用要回来） | 本地 |
| P11-007 | L2、L3 | 在 Windows 上：全部已打开文档任务一条命令各跑 3 次，再跑 `undo`（已完成：见下文“P11-007 结果”。L2 在 `20c94d8` 上达成；`undo` 第一轮 5/6，系列值场景在写入前被拒，修复（#110）后在 `4ccd565` 上重跑 6/6） | Windows |
| P11-008 | L4 | 定版本 0.8.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.8.0` 标签（已完成：`v0.8.0` 从 `main@4ccd565` 发布） | 本地 + 你 |
| P11-009 | L4 | 在 Windows 上检查 0.8.0 的 wheel（已完成：`4ccd565` 上通过，SHA-256 与 Release 一致，safe 档 7/7，结果在 `scripts/windows_check/results/20261017T163844Z-wheel-0.8.0/`） | Windows |

## P11-005 结果

P10-006 里 Writer 写入后的 3 次核对：插入第 1 次和第 3 次运行写入后调用 `validate_document contains "Owner: Finance (reviewed)"`，删除第 2 次运行写入后调用 `snapshot_document`。这几次写入的结果里，`verified_state.check` 已经写明“paragraph 3 changed from 'Owner: Finance' to 'Owner: Finance (reviewed)'”，Agent 查的正是这句话里的文字，所以缺的不是内容，而是 Agent 不知道核对工具在这里是多余的。写入工具的说明已经写了“不需要再调用”，但 Agent 读的是核对工具自己的说明。

改动：`validate_document`、`snapshot_document` 和 `spreadsheet_read` 的 MCP 说明加一句：核对已打开文档的写入不需要它们，写入结果里已有 `verified_state`。写入前的 2 次 `snapshot_document`（插入第 2、3 次运行，用来看光标所在的段落）是定位，不在 L2 的门槛里，这次不改。

P11-007 的评测会记下每次写入返回的 `verified_state`（P11-004），这次上机后能直接看出 Agent 再查时看到的是什么。

## P11-007 上机步骤

在合并了本阶段改动的 `main` 上，先 `git pull`，再按顺序运行：

```
python scripts/windows_check/run_windows_check.py eval --prefix wps-open- --repeat 3 --min-passes 2
python scripts/windows_check/run_windows_check.py undo
```

第一条对应 L2：16 个任务都至少 2/3，`wrong_tool_calls` 合计 0，写入后的额外调用合计不超过 3，`RESULTS.md` 开头那句“writes whose verified_state.passed is not true”为 0。第二条对应 L3：6 个场景都通过，其中 `spreadsheet-axis-title-replace` 和 `spreadsheet-series-values-replace` 是新的。两次的结果目录提交到 `cursor/phase11-windows-<提交号>` 分支。之后推送 `v0.8.0` 标签，再跑 `run_windows_check.py wheel --version 0.8.0`（P11-009，同时验证 L1）。

## P11-007 结果

第一轮在 `main@20c94d8` 上，结果在 `scripts/windows_check/results/20261017T062425Z-20c94d8-eval/` 和同一提交的 `undo` 目录。评测中途因会话结束停在第 10 个任务，用 `eval --resume` 接着跑完。

- **L2 达成。** 16 个任务都是 3/3，`wrong_tool_calls` 0，额外调用合计 4，写入后 3 次（P10-006 是 8），`verified_state.passed` 不是 true 的写入 0 次。剩下的写入后调用：Writer 替换后一次 `validate_document`，表格替换后一次 `spreadsheet_read`，另存为后一次 `operation`。48 次清理都让 WPS 正常退出。
- **L3 未达成：`undo` 5/6。** 前四个场景和新的 `spreadsheet-axis-title-replace` 都通过；`spreadsheet-series-values-replace` 在写入前以 `SELECTION_MISMATCH`（“The selection or its text changed between preview and write”）拒绝，什么也没写。
  - 原因：系列值写入脚本找图表时仍按“访问会不会报错”判断（P10-006 只改了选区读脚本）。WPS 里系列的父对象是图表组，没有 `ChartType` 但不报错，脚本就把图表组当成图表，取它的父对象（图表本身）的名称 `Status Chart 1`，而选区读给的是图表对象的名称 `Chart 1`，写入脚本的名称核对因此拒绝了自己的选区。你在 Windows 上复现过：同样的参数直接调用写入动作，返回 `selection_changed`，`current_object_name` 为 `Status Chart 1`。
  - 修复：系列值写入和删除脚本改为按取到的值判断（系列要求 `Values` 有值，图表要求 `ChartType` 有值，先看父对象再看父对象的父对象），名称取图表对象的名称，与选区读一致。撤回脚本沿用替换脚本的开头，一并改好。假 COM 里系列的父对象改为没有 `ChartType` 的图表组、图表本身名为 `Status Chart 1`，旧脚本在这些测试上的失败和 Windows 上一样（`selection_changed`）。
- **L3 达成（重跑）。** 修复（#110）合并后在 `main@4ccd565` 上重跑 `undo`，6 个场景都通过，结果在 `scripts/windows_check/results/20261017T163439Z-4ccd565-undo/`。系列值场景写入后被注入读回失败，撤回读回原值，磁盘上记录的文字里 `series values: Status!B2:B3` 回来了，说明系列重新引用了单元格。
- **L1、L4 达成（P11-009）。** `v0.8.0` 在 `undo` 6/6 之后从 `main@4ccd565` 发布，wheel 在 Windows 上通过全部 7 个条件，结果在 `scripts/windows_check/results/20261017T163844Z-wheel-0.8.0/`。

## 出口标准结果

| # | 结果 | 依据 |
| --- | --- | --- |
| L1 | 达成 | `v0.8.0` 包含 #107 的修复，wheel 在 Windows 上通过（P11-009） |
| L2 | 达成 | P11-003、P11-004、P11-005；P11-007 16/16 都 3/3，写入后额外调用 3，`unverified_writes` 0 |
| L3 | 达成 | P11-006；`4ccd565` 上 `undo` 6/6（系列值写入的修复在 #110） |
| L4 | 达成 | `v0.8.0` 已发布，wheel 在 Windows 上通过 |

## 建议顺序

1. 本地任务（P11-001、P11-003 到 P11-006、P11-008）在一次提交里完成。
2. 一次上机做完 P11-007。
3. 推送 `v0.8.0` 标签，做 P11-009。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| WPS 选不中坐标轴标题或系列（选区 API 和 Excel 不同） | L3 的新场景跑不起来 | 准备步骤选不中时记为准备失败并写明原因；`undo` 结果已经记录命令读到的选区，能看出读成了什么 |
| 系列写回公式后 WPS 重新计算，读回的值和原值格式不同（比如 `120` 和 `120.0`） | 撤回核对不通过 | 核对按数值比较；不一致时记下两边的原文 |
| Agent 不管结果写了什么都再读一次 | L2 的门槛达不到 | P11-004 记下每次写入返回的内容，先看 Agent 看到的是什么，再决定改结果还是改说明 |
| `surroundings` 让结果变长 | 响应变长 | 最多 10×10，单格文字超过 100 字符截断 |
