# Windows 保真度、评测和放映检查（Phase 13）

- 日期：2026-10-18
- 提交：`4b263d9` on `main`
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由检查命令的输出整理而成；两个评测的结果目录由 `run_windows_check.py` 写出，是相邻的 `20261018T140444Z-4b263d9-eval` 和 `20261018T141717Z-4b263d9-eval`。

## 1. 保真度矩阵（WPS 渲染）

`python scripts/fidelity_baselines.py --renderer wps --wps`，原始输出 `fidelity-wps.log`。

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 结果 |
| --- | --- | --- |
| A-report-docx | 0.8532 | 未达 0.90 |
| A-contract-docx | 0.3690 | 未达 0.90 |
| A-newsletter-docx | 0.8228 | 未达 0.90 |
| A-manual-docx | 0.8123 | 未达 0.90 |
| A-pdfsource-docx | 0.8551 | 未达 0.90 |
| A-budget-xlsx | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 通过 |
| A-training-pptx | 0.9481 | 通过 |
| A-quarterly-pptx | 0.9573 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | 通过（文字、结构、格式、动画、数据 100%） |

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.5626，未达 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 版面 0.8687，未达 0.95（单独复测同分，`b-doc-retest.json`） |
| B-odt-docx | `COM_OPERATION_TIMEOUT`（180 秒），单独复测仍超时 |
| B-xls-xlsx | 通过，版面 0.9843 |
| B-ppt-pptx | 通过，版面 0.9955 |
| B-docx-wps | 首次运行 `RPC_E_CALL_REJECTED`；单独复测通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | 首次运行 `DOCUMENT_HELD_OPEN`；单独复测通过，版面 1.0 |
| B-pptx-png | 转换成功，页面已生成 |

说明：首次整轮里 `B-docx-wps` / `B-docx-odt` 的失败是前一步 WPS 仍占用 `brief.docx` 导致的级联；在每一步开始前结束 WPS 进程后单独复测（`b-retest.json`），两者都通过。`B-odt-docx` 的 180 秒超时在干净进程下仍复现，是真实问题（WPS 把 `.odt` 另存为 `.docx` 时卡住）。

`fidelity-wps.log` 里另有 “layout … fell below the baseline …” 的 FAIL；那是对 WPS 分数仍去比 LibreOffice 基线造成的噪声，同一提交里已改成只在 LibreOffice 渲染时比较基线。官方判定按上表的门槛。

## 2. 评测

### `--prefix convert-`（`20261018T140444Z-4b263d9-eval`）

4/5 通过。`convert-pdf-to-docx`、`convert-gbk-csv-to-xlsx`、`convert-markdown-to-docx`、`convert-docx-to-pptx` 都是 3/3。`convert-legacy-doc-with-wps` **0/3**：三次都只生成了 `brief.docx`，没有在同一目录生成 `brief.pdf`；运行里出现 `OUTPUT_DIRECTORY_NOT_FOUND` 和 `OUTPUT_ALREADY_EXISTS`，Agent 把回合花在临时目录的探测上，16 轮用完。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261018T141717Z-4b263d9-eval`）

5/5 通过。两个 `html-table-*` 3/3；复杂 HTML：报告 2/3（第 3 次因为 `OUTPUT_DIRECTORY_NOT_FOUND` 没有调用 `convert_smoke`，仍达到 2/3）、预算 3/3、演示 3/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 这次检查发现并修掉的脚本问题

- `TemporaryDirectory` 清理时 WPS 还占用临时文件，导致 `WinError 32` 中断整轮；两处临时目录改为 `ignore_cleanup_errors=True`。
- `compare()` 在 WPS 渲染时仍拿 LibreOffice 基线比较；改为只在 `layout_renderer == "libreoffice"` 时比较。
