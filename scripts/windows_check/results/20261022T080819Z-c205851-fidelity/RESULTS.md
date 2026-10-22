# Windows 保真度、评测和放映检查（Phase 13，第五轮）

- 日期：2026-10-22
- 提交：`c205851` on `main`（含 #124 的第四轮修复）
- 机器：Windows 10.0.19045；WPS 12.8.2.18913；Python 3.12.15（仓库 `.venv`，包 0.10.0 可编辑安装）；Node 24.16.0，Playwright 用 Microsoft Edge
- 本目录由 `python scripts/fidelity_baselines.py --renderer wps --wps --out <本目录>` 写出（`results.json`、`pages/`、`fidelity-wps.log`）；另有 `b-odt-retest.json`、超时截图和 `playback.json`。两个评测目录是相邻的 `20261022T082114Z-c205851-eval` 和 `20261022T083307Z-c205851-eval`。

## 1. 保真度（WPS 渲染）

门槛（`docs/PHASE13_PLAN.md`）：A 组版面 ≥ 0.90，B 组 ≥ 0.95，E 组 ≥ 0.85；文字、结构、格式、动画、数据按各组要求 100%。

### A 组

| 用例 | 版面 (WPS) | 页数（源 → 目标） | 结果 |
| --- | --- | --- | --- |
| A-report-docx | 0.8850 | 2 → 2 | 未达 0.90 |
| A-contract-docx | 0.8188 | 1 → 1 | 未达 0.90 |
| A-newsletter-docx | 0.8859 | 1 → 1 | 未达 0.90 |
| A-manual-docx | 0.8681 | 1 → 1 | 未达 0.90 |
| A-pdfsource-docx | 0.8827 | 2 → 2 | 未达 0.90 |
| A-budget-xlsx | — | — | 通过（无版面项） |
| A-launch-pptx | 0.9137 | 6 → 6 | 通过 |
| A-training-pptx | 0.9480 | 3 → 3 | 通过 |
| A-quarterly-pptx | 0.9573 | 3 → 3 | 通过 |
| A-brief-html / A-deck-html / A-book-html | — | — | 通过（文字、结构、格式、动画、数据 100%） |

与第四轮相比五份 docx 都提高了（report 0.8659→0.8850、contract 0.7589→0.8188、newsletter 0.8339→0.8859、manual 0.8241→0.8681、pdfsource 0.8779→0.8827），但仍低于 0.90。

### C、D、E 组

- C 组 7 项全部通过（文字、结构、数据 100%）。
- D 组 4 项全部通过；`D-deck-docx` 的结构 70%、动画 0% 是预期值（决定 8、F5）。
- E 组：`E-supplier-xlsx`、`E-supplier-pptx` 通过；`E-supplier-docx` 版面 0.8745（源 2 页、目标 2 页），达到 0.85。

### B 组（经 WPS）

| 方向 | 结果 |
| --- | --- |
| B-doc-docx | 通过，版面 1.0 |
| B-odt-docx | **`COM_OPERATION_TIMEOUT`**（180 秒，WPS was opening the input）；见下面的诊断 |
| B-xls-xlsx | 通过，版面 1.0 |
| B-ppt-pptx | 通过，版面 1.0 |
| B-docx-wps | 通过，版面 1.0 |
| B-xlsx-et | 通过，版面 1.0 |
| B-pptx-dps | 通过，版面 1.0 |
| B-docx-odt | 通过，版面 1.0 |
| B-pptx-png | 转换成功，页面已生成 |

### `B-odt-docx` 超时诊断（含截图）

错误信息原文：

```
WPS conversion timed out after 180 seconds. WPS was opening the input.
Open WPS windows: untitled Qt5QWindowIcon 440x260
(C:\Users\admin\AppData\Local\Temp\wps-agent-timeout-20261022T161356-1.png);
untitled Qt5QWindowIcon 420x240
(C:\Users\admin\AppData\Local\Temp\wps-agent-timeout-20261022T161356-2.png).
```

工具保存的两张截图（`timeout-copyfromscreen-*.png`）是用屏幕区域截的，而这两个 WPS 窗口正好被一个 Cursor 窗口盖住，所以图里显示的是 Cursor 页面，看不到 WPS 的内容。

用 `PrintWindow` 直接抓那个 420×240 的 WPS 窗口（`timeout-printwindow-420x240.png`）可以看到真正卡住的界面：

> **文件损坏提示**
> 当前文档无法正确读取，继续打开将显示乱码。
> 建议尝试下列方法解决：
> 1、查看本地文档备份：备份目录
> 2、若为云文档，可在文档详情中查看历史版本
> ［关闭］［继续打开］

也就是说 WPS 12.8.2.18913 把 `fixtures/fidelity/brief.odt` 当成损坏文件，打开时弹出这个模态框等待用户选择，转换一直等不到回应，180 秒后超时。440×260 的窗口截图是空白/黑色（`timeout-printwindow-440x260.png`）。单独复测（`b-odt-retest.json`）得到相同的窗口列表和超时。

## 2. 评测

### `--prefix convert-`（`20261022T082114Z-c205851-eval`）

**5/5 通过**，五个任务都是 3/3。`wrong_tool_calls` 0，未验证写入 0。

### `--prefix html-`（`20261022T083307Z-c205851-eval`）

**5/5 通过**。`html-table-to-xlsx`、`html-table-to-docx`、`html-complex-report-to-docx`、`html-complex-launch-to-pptx` 都是 3/3；`html-complex-budget-to-xlsx` 2/3。`wrong_tool_calls` 0，未验证写入 0。

## 3. `training.html` 放映检查

`html-editable --format pptx --fidelity appearance` 生成 `training.pptx`（3 页、6 个动画、3 个切换、1 条备注，无警告；`training-convert.json`），在 WPS 演示里读取并放映（`playback.json`）：

- 第 1 页：fade 切换；标题飞入（with previous）。
- 第 2 页：push 切换；三个列表项都是飞入，触发分别是 with previous、on click、with previous + 0.6 秒延迟（对应 `data-trigger="after"`）。
- 第 3 页：wipe 切换；`pulse` 强调效果；提示文字 exit fade，延迟 0.5 秒。
- 放映位置按 1 → 2 → 3 前进；第 2 页的单击动画需要多按一次才翻页。

## 4. 结论

- 两组评测都是 5/5；`E-supplier-docx` 和 B 组其余方向都通过。
- A 组 5 份 docx 的版面继续提高（0.819–0.886），但仍都低于 0.90。
- `B-odt-docx` 的超时原因已定位：WPS 把 `brief.odt` 判为损坏并弹出“文件损坏提示”模态框。可行的处理是换一份 WPS 能直接打开的 ODT、自动点“继续打开”，或按决定 9 把这一方向记为 WPS 不支持并写明原因。
- P13-008、P13-013、P13-018 仍不能算完成。
