# Windows 保真度、评测和放映检查（Phase 13，第六轮）

- 日期：2026-10-22
- 提交：`f8ed7bd` on `main`（含 #125 的第五轮修复）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `python scripts/fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`）；另有 `b-odt-retest.json`、超时截图、`add-type-error.txt` 和 `playback.json`。两个评测目录是相邻的 `20261022T120934Z-f8ed7bd-eval` 和 `20261022T122227Z-f8ed7bd-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.8927 | 2 → 2 | 未达 0.90 |
| A-contract-docx | 0.8328 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | 0.8951 | 1 → 1 | 未达 0.90 |
| A-manual-docx | 0.8770 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8853 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

与第五轮相比五份 docx 又都提高了（report 0.8850→0.8927、contract 0.8188→0.8328、newsletter 0.8859→0.8951、manual 0.8681→0.8770、pdfsource 0.8827→0.8853）；newsletter 和 report 已经接近 0.90，但仍未达到。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.8745（2 → 2 页），达到 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0 |
| B-odt-docx | **`COM_OPERATION_TIMEOUT`**（180 秒，WPS was opening the input） |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | 通过，版面 1.0 |
| B-pptx-png | 转换成功，页面已生成 |

### `B-odt-docx`：ODF 1.2 仍弹“文件损坏提示”

`brief.odt` 已按 #125 重新生成为 ODF 1.2（`content.xml`、`styles.xml`、`meta.xml` 的 `office:version` 都是 `1.2`），但 WPS 12.8.2.18913 仍然把它当成损坏文件。

本轮的错误信息只有：

```
WPS conversion timed out after 180 seconds. WPS was opening the input.
WPS may be asking whether to open a file it reads as damaged; ODF 1.3 files
with LibreOffice extensions do this, so save the file as ODF 1.2 or as
.docx/.xlsx/.pptx.
```

**没有** `Open WPS windows: …` 段。原因是 #125 把窗口截图改成 C# `PrintWindow` 后，`Add-Type` 在 PowerShell 7 上编译失败（`CS1069: System.Drawing.Graphics` 已转发到 `System.Drawing.Common`），`_wps_windows()` 返回空，所以既不列窗口也不写截图。错误原文在 `add-type-error.txt`。

为了确认界面，我在单独复测卡住时用自己的 `PrintWindow`（ctypes）抓了那个 420×240 的 WPS 窗口（`timeout-printwindow-420x240.png`），仍然是同一个模态框：

> **文件损坏提示**
> 当前文档无法正确读取，继续打开将显示乱码。
> 建议尝试下列方法解决：
> 1、查看本地文档备份：备份目录
> 2、若为云文档，可在文档详情中查看历史版本
> ［关闭］［继续打开］

440×260 的窗口是空白（`timeout-printwindow-440x260.png`）。单独复测（`b-odt-retest.json`）同样超时。

## 2. 评测

### `--prefix convert-`（`20261022T120934Z-f8ed7bd-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T122227Z-f8ed7bd-eval`）

**5/5 通过**。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-report-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- 两组评测都是 5/5；`E-supplier-docx` 和 B 组其余方向通过。
- A 组 5 份 docx 的版面继续提高（0.833–0.895），但都还差一点到 0.90。
- `B-odt-docx`：ODF 1.2 没有解决问题，WPS 仍然弹“文件损坏提示”。下一步可以：(a) 用 WPS 自己保存一份 ODT 作为夹具；(b) 自动点“继续打开”；(c) 按决定 9 记为 WPS 不支持并写明原因。
- 另外需要修掉 #125 的窗口截图回归（`Add-Type` 引用 `System.Drawing.Common`，或改用 IntPtr HDC 避免 C# 引用 Graphics），否则超时诊断又会丢失窗口列表和截图。
- P13-008、P13-013、P13-018 仍不能算完成。
