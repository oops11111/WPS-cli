# Windows 保真度、评测和放映检查（Phase 13，第三轮）

- 日期：2026-10-22
- 提交：`8899219` on `main`（含 #122 的第二轮修复）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `python scripts/fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`）；另有单独复测的 `b-retest.json` 和放映检查的 `playback.json`。两个评测目录是相邻的 `20261022T055711Z-8899219-eval` 和 `20261022T060727Z-8899219-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.8659 | 2 → 2 | 未达 0.90 |
| A-contract-docx | 0.7639 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | 0.8339 | 1 → 1 | 未达 0.90 |
| A-manual-docx | 0.8241 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8779 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

与第二轮（`c117637`）相比，contract 0.7505→0.7639，其余四份基本不变；五份 docx 仍都低于 0.90。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.5918（源 2 页、目标 3 页），未达 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0（1 → 1 页） |
| B-odt-docx | `COM_OPERATION_TIMEOUT`（180 秒，错误信息为 “WPS was opening the input”）；整轮和单独复测都超时 |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 整轮里 `DOCUMENT_HELD_OPEN`；单独复测通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | 整轮里 `DOCUMENT_HELD_OPEN`；单独复测通过，版面 1.0 |
| B-pptx-png | 转换成功，页面已生成 |

整轮里 `B-docx-wps` / `B-docx-odt` 仍在前一例之后撞上 WPS 占用 `brief.docx`，即使每个 B 用例已经使用自己的目录；单独复测（每一步前结束 WPS 进程，`b-retest.json`）两者都是文字、结构、格式、数据、版面 1.0。`B-odt-docx` 的 180 秒超时在单独复测里仍复现，发生在 WPS 打开输入文件时。

## 2. 评测

### `--prefix convert-`（`20261022T055711Z-8899219-eval`）

**5/5 通过**，五个任务都是 3/3（包括上一轮的 `convert-docx-to-pptx`）。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T060727Z-8899219-eval`）

4/5 通过。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`html-complex-report-to-docx` **1/3**：第 1、3 次没有调用 `convert_smoke`，而是用新的 `convert` 生成了 `report.pdf`（第 3 次还从 PDF 导出了 PNG）；任务检查仍然只认 `convert_smoke`，所以第 1、3 次判失败。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- `convert-` 评测已全部通过，P13-017 的评测任务在这台机器上稳定。
- `html-complex-report-to-docx` 的失败是检查与工具不一致：`convert` 已取代并兼容 `convert-smoke` 的 PDF 用法，但任务仍然只检查 `convert_smoke`；建议把任务检查改为接受这两个工具之一。
- 仍未达标的门槛：A 组 5 份 docx 的版面（0.764–0.878，要求 0.90）、`E-supplier-docx`（0.5918，要求 0.85）、`B-odt-docx`（WPS 打开输入时超时）。
- 整轮里 `B-docx-wps` / `B-docx-odt` 的 `DOCUMENT_HELD_OPEN` 仍会在连续 B 用例中出现；单独复测通过，说明矩阵脚本还需要在用例之间释放 WPS。
- P13-008、P13-013、P13-018 仍不能算完成。
