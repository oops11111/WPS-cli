# Windows 保真度、评测和放映检查（Phase 13，第四轮）

- 日期：2026-10-22
- 提交：`c55d04e` on `main`（含 #123 的第三轮修复）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `python scripts/fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`）；另有 `b-odt-retest.json`（单独复测）和 `playback.json`（放映）。两个评测目录是相邻的 `20261022T071021Z-c55d04e-eval` 和 `20261022T072124Z-c55d04e-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.8659 | 2 → 2 | 未达 0.90 |
| A-contract-docx | 0.7589 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | 0.8339 | 1 → 1 | 未达 0.90 |
| A-manual-docx | 0.8241 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8779 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

行高修复没有改变这五份 docx 的 WPS 版面分数（与第三轮基本相同）。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；**`E-supplier-docx` 版面 0.8745，源 2 页、目标 2 页，达到 0.85**（第三轮 0.5918、目标 3 页）。边距修复生效。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0 |
| B-odt-docx | **`COM_OPERATION_TIMEOUT`**（180 秒，WPS was opening the input）；见下面的诊断 |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 通过，版面 1.0（整轮里也通过；WPS 释放修复生效） |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | 通过，版面 1.0（整轮里也通过） |
| B-pptx-png | 转换成功，页面已生成 |

### `B-odt-docx` 超时诊断

错误信息原文：

```
WPS conversion timed out after 180 seconds. WPS was opening the input.
```

**没有** `Open WPS windows: …` 段。`wps_convert._wps_window_titles()` 只收集可见且有标题的窗口；卡住时没有这样的窗口，所以该段为空（代码已经有这段，不是缺失）。详见 `b-odt-timeout.txt`：卡住的 `wps.exe`（PID 25992）没有任何带标题的可见窗口；`OpusApp` 的 `WPS文字` 窗口是隐藏的，两个可见的 `Qt5QWindowIcon` 窗口标题为空。也就是说 WPS 在打开 `.odt` 时无可见对话框地卡住了。

## 2. 评测

### `--prefix convert-`（`20261022T071021Z-c55d04e-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T072124Z-c55d04e-eval`）

**5/5 通过**。`html-complex-report-to-docx` 已回到 3/3（`tool_called` 现在接受 `convert`）；`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- 本轮修好了 `E-supplier-docx`（0.8745，2 → 2 页）和 B 组连续用例的 WPS 占用（`B-docx-wps`、`B-docx-odt` 整轮通过）；两组评测都是 5/5。
- 仍未达标：A 组 5 份 HTML→docx 的版面（0.759–0.878，要求 0.90）和 `B-odt-docx`（WPS 打开输入时无可见窗口地超时）。
- P13-008、P13-013、P13-018 仍不能算完成。
