# Windows 保真度、评测、ODT 探测和放映检查（Phase 13，第七轮）

- 日期：2026-10-22
- 提交：`3095499` on `main`（含 #126 的第六轮修复和 `scripts/windows_check/odt_probe.py`）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`），另有 `odt-probe.json`/`odt-probe.log` 和 `playback.json`。两个评测目录是相邻的 `20261022T133529Z-3095499-eval` 和 `20261022T134558Z-3095499-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.8940 | 2 → 2 | 未达 0.90 |
| A-contract-docx | 0.8488 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | **0.9217** | 1 → 1 | **通过** |
| A-manual-docx | 0.8866 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8822 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9475 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

与第六轮相比，五份 docx 的版面是：report 0.8927→0.8940、contract 0.8328→0.8488、newsletter 0.8951→**0.9217（通过）**、manual 0.8770→0.8866、pdfsource 0.8853→0.8822。现在只剩四份低于 0.90。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.8744（2 → 2 页），达到 0.85。

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

`B-odt-docx` 的错误信息（本轮窗口列表和截图路径恢复正常，按你的要求不附截图）：

```
COM_OPERATION_TIMEOUT: WPS conversion timed out after 180 seconds. WPS was opening the input.
Open WPS windows: untitled Qt5QWindowIcon 440x260 (…-1.png); untitled Qt5QWindowIcon 420x240 (…-2.png).
WPS may be asking whether to open a file it reads as damaged; ODF 1.3 files with LibreOffice
extensions do this, so save the file as ODF 1.2 or as .docx/.xlsx/.pptx.
```

## 2. ODT 探测（`scripts/windows_check/odt_probe.py`）

`python scripts/windows_check/odt_probe.py --out <本目录>`，输出 `odt-probe.json`：

| 变体 | 结果 | 用时 |
| --- | --- | --- |
| wps-written（WPS 自己保存的 `.odt`） | **打开成功** | 3.8 秒 |
| libreoffice（`fixtures/fidelity/brief.odt`，ODF 1.2） | `COM_OPERATION_TIMEOUT` | 61.3 秒 |
| libreoffice-trimmed（去掉缩略图、设置、manifest.rdf、Configurations2） | `COM_OPERATION_TIMEOUT` | 61.3 秒 |
| minimal-ascii（手写的最小 ODT，一段 ASCII） | `COM_OPERATION_TIMEOUT` | 61.3 秒 |
| minimal-cjk（最小 ODT，一段中文） | `COM_OPERATION_TIMEOUT` | 61.3 秒 |
| minimal-cjk-styles（上面加 styles.xml 和 meta.xml） | `COM_OPERATION_TIMEOUT` | 66.8 秒 |

结论：在这台机器上，WPS 12.8.2.18913 只直接打开 **它自己保存的** ODT；所有其他来源的 ODT（包括手写的最小有效 ODT）都会弹“文件损坏提示”并等待，转换在 60/180 秒后超时。问题不在 `brief.odt` 是否 ODF 1.2 或是否带 LibreOffice 扩展，而是这台 WPS 对非自己生成的 ODT 的打开提示（可能是 WPS 设置、注册或版本行为）。可选的下一步：把夹具改为 WPS 保存的 ODT、自动回答“继续打开”，或按决定 9 记为 WPS 不支持并写明原因。

## 3. 评测

### `--prefix convert-`（`20261022T133529Z-3095499-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T134558Z-3095499-eval`）

**5/5 通过**。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-report-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 4. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 5. 结论

- `A-newsletter-docx` 首次达到 0.90（0.9217）；A 组还剩 report 0.8940、manual 0.8866、pdfsource 0.8822、contract 0.8488 四份未达标。
- 两组评测都是 5/5；E-supplier-docx 和 B 组其余方向通过。
- `B-odt-docx` 的原因由 `odt_probe` 定位：WPS 只打开自己保存的 ODT，其他 ODT 一律触发“文件损坏提示”。
- P13-008、P13-013、P13-018 仍不能算完成。
