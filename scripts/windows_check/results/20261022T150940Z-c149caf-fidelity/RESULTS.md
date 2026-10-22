# Windows 保真度、评测和放映检查（Phase 13，第八轮）

- 日期：2026-10-22
- 提交：`c149caf` on `main`（含 #127 的第七轮修复）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`），另有 `playback.json`。两个评测目录是相邻的 `20261022T151600Z-c149caf-eval` 和 `20261022T152737Z-c149caf-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | **0.9234** | 2 → 2 | **通过**（上下标行修复） |
| A-contract-docx | 0.8492 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | **0.9169** | 1 → 1 | **通过** |
| A-manual-docx | 0.8869 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8823 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

与第七轮相比：report 0.8940→**0.9234（通过）**、newsletter 0.9217→0.9169（仍通过）、contract 0.8488→0.8492、manual 0.8866→0.8869、pdfsource 0.8822→0.8823。现在只剩三份 docx 低于 0.90。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.8741（2 → 2 页），达到 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0 |
| B-odt-docx | **`FORMAT_NOT_SUPPORTED_BY_WPS`（记为不支持）**，约 60 秒内结束 |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | **`FORMAT_NOT_SUPPORTED_BY_WPS`（记为不支持）** |
| B-pptx-png | 转换成功，页面已生成 |

`B-odt-docx` 的错误信息（只保留文本，不附截图）：

```
FORMAT_NOT_SUPPORTED_BY_WPS: WPS did not open brief.odt within 60 seconds: this WPS build asks
whether to open ODF files as damaged ones (文件损坏提示) instead of opening them. Save the file as
.docx, .xlsx or .pptx in the program that made it.
Open WPS windows: untitled Qt5QWindowIcon 440x260 (…-1.png); untitled Qt5QWindowIcon 420x240 (…-2.png).
```

`B-docx-odt` 的错误信息：

```
FORMAT_NOT_SUPPORTED_BY_WPS: This WPS build does not write ODF: asked for .odt, it wrote a file
that is not an OpenDocument package, which was removed. Save as .docx, .xlsx or .pptx.
```

核对你的三点要求：

1. **B-odt-docx 和 B-docx-odt 都按预期记为“不支持”**（矩阵不再把它们算作失败）；`B-odt-docx` 在 60 秒上限内结束。整轮矩阵用时 5 分 53 秒（第七轮约 8 分 40 秒），结束后 `tasklist` 检查没有 WPS/et/wpp 进程。
2. **report 带上下标那一行**：版面从 0.8940 提高到 **0.9234**，通过 0.90。
3. **contract 和其余 A 组 docx**：contract 0.8492、manual 0.8869、pdfsource 0.8823，仍低于 0.90。

## 2. 评测

### `--prefix convert-`（`20261022T151600Z-c149caf-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T152737Z-c149caf-eval`）

**5/5 通过**。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-report-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- `B-odt-docx` / `B-docx-odt` 已按决定 9 稳定记为 WPS 不支持，`B-odt-docx` 约一分钟结束且不留 WPS 进程，不再阻塞 B 组。
- A 组已有两份 docx（report 0.9234、newsletter 0.9169）通过；剩 contract 0.8492、manual 0.8869、pdfsource 0.8823 三份未达标。
- 两组评测都是 5/5，放映正确。
- P13-008、P13-013、P13-018 仍不能算完成：还差 A 组三份 docx 的版面。
