# Windows 保真度、评测和放映检查（Phase 13，第十轮）

- 日期：2026-10-23
- 提交：`45b0d4b` on `main`（含 #129 的第九轮修复和决定 10）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`），另有 `playback.json`。两个评测目录是相邻的 `20261022T231525Z-45b0d4b-eval` 和 `20261022T232652Z-45b0d4b-eval`。

## 1. 保真度（WPS 渲染）：全部通过

矩阵退出码 **0**，没有 FAIL 行。门槛：A 组版面 ≥ 0.90（决定 10 的两份按下限），B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.9236 | 2 → 2 | 通过 |
| A-contract-docx | 0.8491 | 1 → 1 | **通过（known deviation，下限 0.84）** |
| A-newsletter-docx | 0.9170 | 1 → 1 | 通过 |
| A-manual-docx | 0.8873 | 1 → 1 | **通过（known deviation，下限 0.88）** |
| A-pdfsource-docx | **0.9123** | 2 → 2 | **通过（首次越过 0.90）** |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

矩阵输出对两份已知偏差的标注：

```
A-contract-docx … "layout": 0.8491 … (known deviation: glyph rendering differs from the browser; layout aligned (decision 10))
A-manual-docx   … "layout": 0.8873 … (known deviation: glyph rendering differs from the browser; layout aligned (decision 10))
```

与第九轮相比：pdfsource 0.8980→**0.9123（通过）**；contract 0.8491、manual 0.8873 保持在下限以上；report 0.9236、newsletter 0.9170 保持通过。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.8746（2 → 2 页），达到 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0 |
| B-odt-docx | `FORMAT_NOT_SUPPORTED_BY_WPS`（60 秒内结束） |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | `FORMAT_NOT_SUPPORTED_BY_WPS` |
| B-pptx-png | 转换成功，页面已生成 |

`B-odt-docx` 的错误信息（只保留文本）：

```
FORMAT_NOT_SUPPORTED_BY_WPS: WPS did not open brief.odt within 60 seconds: this WPS build asks
whether to open ODF files as damaged ones (文件损坏提示) instead of opening them. Save the file as
.docx, .xlsx or .pptx in the program that made it.
Open WPS windows: untitled Qt5QWindowIcon 440x260 (…-1.png); untitled Qt5QWindowIcon 420x240 (…-2.png).
```

矩阵用时 6 分 03 秒，结束后没有 WPS/et/wpp 进程。

## 2. 评测

### `--prefix convert-`（`20261022T231525Z-45b0d4b-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T232652Z-45b0d4b-eval`）

**5/5 通过**。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-report-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- **保真度矩阵本轮全部通过**：pdfsource 0.9123 越过 0.90；contract 0.8491（下限 0.84）和 manual 0.8873（下限 0.88）都在下限以上，输出标注 known deviation（决定 10）。
- 两组评测都是 5/5；ODF 两个方向按决定 9 记为 WPS 不支持；放映正确。
- P13-008、P13-013、P13-018 的 Windows 检查部分已经通过；这三个任务还包含各自的发布步骤（0.10.0 / 0.11.0 / 0.12.0），发布尚未做。
