# Phase 13 计划：全格式高保真互转

状态：**active**（2026-10-18 规划，同日你决定把全部格式并入本阶段；同日你说“phase13三个里程碑做一个提交”，按默认决定激活。三个里程碑的本地任务已在一次提交中完成，版本号 0.10.0 包含全部内容；Windows 上的三次检查 P13-008、P13-013、P13-018 已于 2026-10-18 在 `4b263d9` 上跑过，未全部通过，见“Windows 检查结果”）。

## 目标

Phase 12 之后，HTML 转换为 WPS 三种格式已经保留语义、行内格式、合并单元格、数字格式、动画和切换，三个复杂输入在 WPS 上 3/3，动画放映正确。但：

- 没有统一的保真度度量，只有逐项断言；
- 字体、字号、颜色以外的 CSS（行距、间距、对齐、缩进、底纹、边框、列宽、背景、元素位置）都不转换；
- 反方向（Office → HTML）只有 WPS 另存的 HTML；
- 很多常见格式根本没有：旧格式和 WPS 原生格式、ODF、CSV、Markdown、图片、跨类型转换、PDF 转可编辑文档。

2026-10-18 你定下：**做好格式互转，要求高保真**（`docs/DEVELOPMENT_SUMMARY.md` 第 7 节，D5 到 D9），并且**把全部格式并入 Phase 13**。本阶段覆盖下面的全部方向，用同一个保真度检查判定。

“高保真”按 D7 量化判定，HTML 的标准外观按 D8 以 Edge/Chromium 渲染为准，保真与可编辑冲突时按 D9 默认可编辑优先。

## 转换方向一览

| 组 | 方向 | 现在 | 本阶段要做到 |
| --- | --- | --- | --- |
| A | HTML → docx | 语义、行内格式、合并单元格、图片 | CSS 的字符、段落、表格、图片、页面属性（见 F2 表），按浏览器计算样式 |
| A | docx → HTML | WPS 另存；owned HTML v1 只保留结构 | 干净的语义 HTML 加内联样式，无损往返 |
| A | HTML → pptx | 标题加正文的固定版式、表格、图片、备注、进入动画、切换 | 按浏览器位置摆放，背景、字体、退出和强调动画、动画顺序 |
| A | pptx → HTML | WPS 另存 | 每页一个 section，元素绝对定位，动画转回 CSS `@keyframes`，切换转回 `data-transition` |
| A | HTML → xlsx | 合并单元格、数字格式、日期、链接、图片 | 字体、颜色、底纹、边框、对齐、列宽、行高、冻结表头、条件格式的静态结果；公式见决定 7 |
| A | xlsx → HTML | WPS 另存 | 每个工作表一个表格，合并单元格、显示值、样式、列宽 |
| B | .doc / .xls / .ppt ↔ docx / xlsx / pptx | 无 | 经 WPS 另存 |
| B | .wps / .et / .dps ↔ docx / xlsx / pptx | 无 | 经 WPS 另存 |
| B | .odt / .ods / .odp ↔ docx / xlsx / pptx | 无 | 经 WPS 另存（WPS 打不开的报告原因） |
| B | docx / xlsx / pptx → PNG（每页一张） | 无（只有 HTML → PNG） | 经 WPS 导出 PDF 再渲染，指定分辨率 |
| B | Office → PDF | WPS 导出（已有） | 不变，作为“WPS 里的样子”的基准，加入保真度检查 |
| C | CSV / TSV ↔ xlsx | 无 | 自动识别编码（UTF-8、带 BOM 的 UTF-8、GBK）和分隔符，数字、日期、前导零按类型；导出时按工作表或指定工作表 |
| C | Markdown ↔ docx / HTML | 无 | CommonMark 加 GFM 表格、任务列表、代码块；转 docx 走 A 组的 HTML 链路；docx → Markdown 走 docx → HTML 再降级 |
| D | docx → pptx | 无 | 每个一、二级标题一页，正文为要点，表格和图片放到对应页；不做内容摘要改写 |
| D | pptx → docx | 无 | 每页一节：标题、正文、表格、图片、备注作为讲稿 |
| D | xlsx 表格 → docx / pptx 表格 | 无 | 指定工作表和区域，保留合并单元格、数字格式显示值、样式 |
| E | PDF → docx | 无 | 有文字层的 PDF：恢复段落、标题、列表、表格、图片、页眉页脚和版式；扫描件：OCR（决定 5） |
| E | PDF → xlsx | 无 | 识别表格（有线框和无线框），每个表格一个工作表 |
| E | PDF → pptx | 无 | 每页一张幻灯片，文字为可编辑文本框，图片和矢量图形按位置放置 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。各组的门槛不同，因为比较的对象不同。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| F1 | 保真度检查 | 离线：新命令 `fidelity-check` 比较任意源文件和转换结果，给出文字、结构、格式、版面、动画、数据六项结果（不适用的项标为不适用）和总判定；版面检查把两边都渲染成图（HTML 用 Chromium，Office 用 WPS 或 LibreOffice 导出 PDF，PDF 直接渲染），逐页计算 SSIM；每项都有离线测试 |
| F2 | A 组：HTML ↔ Office 高保真 | 每个方向至少 3 份输入（文字类至少 5 份）；文字、结构、格式、动画 100%；HTML → Office 在 WPS 上 SSIM ≥ 0.90；Office → HTML 在 Chromium 里与 WPS 导出的 PDF 比较 SSIM ≥ 0.90；HTML → Office → HTML 往返后两次 HTML 渲染 SSIM ≥ 0.95；LibreOffice 上记录基线并防回退 |
| F3 | B 组：经 WPS 的格式家族 | 新命令 `convert`（取代并兼容 `convert-smoke` 的 PDF 用法），支持 B 组全部方向；每种格式至少 2 份输入；文字、结构 100%，转换前后在 WPS 上导出 PDF 的 SSIM ≥ 0.95 |
| F4 | C 组：CSV 和 Markdown | CSV：中文 GBK 和 UTF-8 各至少 2 份，值和类型 100% 一致，往返无损；Markdown：至少 3 份（含表格、代码、任务列表），文字和结构 100%，Markdown → docx → Markdown 往返结构一致 |
| F5 | D 组：跨类型 | 每个方向至少 2 份输入；源中全部文字、表格、图片都出现在结果中（数据项 100%），按规则分页；在 WPS 上打开并导出 PDF 成功 |
| F6 | E 组：PDF 转可编辑 | 有文字层的 PDF 至少 5 份（公文、论文、合同、财报表格、演示导出）：文字 100%，表格单元格 ≥ 98%，转出的 Office 文件在 WPS 上导出 PDF 与原 PDF 的 SSIM ≥ 0.85；扫描件至少 2 份：字符准确率 ≥ 98% |
| F7 | Agent 评测 | 每组至少 1 个评测任务（Agent 转换后自己跑 `fidelity-check`），加上现有 3 个复杂 HTML 任务；Windows 上一条 `eval --prefix convert- --repeat 3 --min-passes 2` 加 `--prefix html-`，每个任务至少 2/3 |
| F8 | 发布 | 每个里程碑发布一个版本（0.10.0、0.11.0、0.12.0，见决定 2），按 `docs/RELEASING.md` 发布 GitHub Release，在 Windows 上检查 wheel |

### F2 中 HTML → docx 要转换的 CSS 属性

| 类别 | 属性 |
| --- | --- |
| 字符 | `font-family`（带中文回退）、`font-size`、`font-weight`、`font-style`、`color`、`background-color`（高亮）、`text-decoration`、`letter-spacing`、`vertical-align` |
| 段落 | `text-align`、`line-height`、`margin-top`/`margin-bottom`（段前段后）、`margin-left`/`text-indent`（缩进、首行缩进）、`background-color`（底纹）、`border`（段落边框）、`page-break-before`/`break-before` |
| 表格 | 列宽（`width`、`<col>`）、单元格 `background-color`、`border`、`padding`、`vertical-align`、`text-align`，表格整体宽度和对齐 |
| 图片 | `width`/`height`，`float` 映射为环绕（可编辑优先时为嵌入加对齐） |
| 页面 | `@page` 的纸张大小和页边距，`<header>`/`<footer>` 映射为页眉页脚 |

## 里程碑

| 里程碑 | 内容 | 版本 |
| --- | --- | --- |
| M13-1 | F1 保真度检查；A 组的文字和演示方向（HTML ↔ docx、HTML → pptx）；B 组（经 WPS 的格式家族和 PNG） | 0.10.0 |
| M13-2 | A 组其余方向（pptx → HTML、HTML ↔ xlsx、xlsx → HTML）；C 组（CSV、Markdown）；D 组（跨类型） | 0.11.0 |
| M13-3 | E 组（PDF 转可编辑，含 OCR）；F7 全部评测；收尾 | 0.12.0 |

每个里程碑结束都上一次机，做该里程碑的 Windows 检查和评测，然后发布。

## 决定

2026-10-18 按默认确认。决定 2 随“三个里程碑做一个提交”调整：本地工作一次提交，版本 0.10.0 包含三个里程碑的全部内容；Windows 检查仍按里程碑做三次，检查中发现的修复各发一个补丁版本，F8 相应改为“0.10.0 发布并在 Windows 上检查 wheel，之后的修复随补丁版本发布”。决定 3 中没有浏览器时不是退回纯语义转换，而是用内置的 CSS 层叠计算样式，结果的 `style_source` 写明 `browser` 或 `cascade`（比 `fidelity: semantic` 保留得更多）。

| 决定 | 默认建议 | 依据 |
| --- | --- | --- |
| 1. 版面检查的正式门槛用谁 | WPS（Windows）结果为准；LibreOffice 只做 CI 回归，每份输入记录基线，回退超过 0.02 即失败 | WPS 是目标环境；LibreOffice 渲染和 WPS 不同，不能用同一个绝对门槛 |
| 2. 怎么发布 | 一个阶段，三个里程碑，各发一个次版本（0.10.0、0.11.0、0.12.0） | 范围大，分批发布能早点把能用的交出去，也让每次上机的量可控 |
| 3. 样式和位置从哪里来 | 有浏览器（Playwright + Chromium/Edge）时取计算样式和元素位置；没有时退回语义转换，结果写明 `fidelity: semantic` | 自己解释 CSS 追不上浏览器；退回保证没有浏览器的环境仍能用 |
| 4. 新增依赖 | 都是可选依赖：`fidelity`（numpy，SSIM）、`markdown`（markdown-it-py）、`pdf`（pdfplumber，文字和表格提取）、`ocr`（RapidOCR，纯 pip 安装，支持中文）；PDF 渲染用已有的 pypdfium2 | 不让基础安装变重；OCR 不依赖系统安装的 Tesseract |
| 5. 扫描件 PDF | 用 `ocr` 可选依赖识别；没装时报告“扫描件需要 OCR”而不是输出空文档 | 扫描件很常见，但 OCR 依赖较重 |
| 6. 字体 | 测试输入统一用“Microsoft YaHei, Noto Sans CJK SC, sans-serif”；缺字体时列出缺的字体，版面检查标记为不可比 | 版面相似度对字体最敏感 |
| 7. xlsx 里的公式 | HTML → xlsx 仍写成文本（D3）；xlsx → HTML 输出计算后的显示值，公式放在 `data-formula` 属性里，往返时还原 | 防止 HTML 带入公式；往返不丢公式 |
| 8. 跨类型的分页规则 | docx → pptx 按一、二级标题分页，每页正文超过 8 条时自动续页；不做摘要改写 | 规则可预测、可测试；改写内容属于 Agent 的工作，不属于转换 |
| 9. B 组格式中 WPS 不支持的 | 报告 `FORMAT_NOT_SUPPORTED_BY_WPS` 并列出 WPS 能另存的格式，不尝试别的转换器 | 本项目以 WPS 为后端 |

## 进展

2026-10-18：本地任务全部完成，Windows 任务待做。

| 任务 | 状态 | 实现 |
| --- | --- | --- |
| P13-001 | 完成 | `fidelity.py`，CLI `fidelity-check`、MCP `wps_agent_fidelity_check`；文字、结构（标题、列表层级、表格、图片、幻灯片）、字符格式、动画（效果、类型、开始时间）、表格数据（按值比较） |
| P13-002 | 完成 | 版面：HTML 用 Chromium 截图（演示按 section），Office 经 WPS（`wps_convert`）或 LibreOffice 导出 PDF，pypdfium2 渲染，逐页 SSIM；缺字体时列出 |
| P13-003 | 完成 | `fixtures/fidelity/`：文字类 5 份（`report`、`contract`、`newsletter`、`manual`、`pdf_source`），演示 3 份（`launch`、`training`、`quarterly`），GBK CSV、UTF-8 TSV、3 份 Markdown、带文字层的 PDF 和它的扫描件、`.doc`/`.xls`/`.ppt`/`.odt`；`scripts/fidelity_baselines.py` 和 `config/fidelity_baselines.json` |
| P13-004 | 完成 | `html_styles.py`（浏览器计算样式，没有浏览器时内置层叠）、`docx_styling.py`：F2 表中的字符、段落、表格、图片、页面属性；`<thead>` 为重复表头，`<hr>`、引用、data URI 图片、图片替代文字 |
| P13-005 | 完成 | `office_html.py`：docx → 内联样式的干净 HTML，往返 100% |
| P13-006 | 完成 | `html_slides.py`：有浏览器时按 section 的布局摆放到 16:9 幻灯片，背景、字体、退出和强调动画、单击和“上一项之后”；`--fidelity appearance` 画出装饰框 |
| P13-007 | 完成 | `wps_convert.py`：SaveAs 格式码（doc 0、docx 16、odt 23、xls 56、xlsx 51、ods 60、ppt 1、pptx 24、odp 35，.wps/.et/.dps 按扩展名）、PDF、每页 PNG；`FORMAT_NOT_SUPPORTED_BY_WPS`；用假 COM 测试 |
| P13-008 | 未通过 | Windows 检查 2026-10-18（`4b263d9`）：A 组 5 份 docx 的版面低于 0.90；`--prefix convert-` 4/5、`--prefix html-` 5/5；见“Windows 检查结果” |
| P13-009 | 完成 | pptx → HTML：每页一个定位的 section，动画转回 `@keyframes`，切换转回 `data-transition`，备注 |
| P13-010 | 完成 | HTML → xlsx 的字体、填充、边框、对齐、列宽、冻结表头，`data-formula` 还原公式；xlsx → HTML |
| P13-011 | 完成 | `tabular.py`（编码、分隔符、类型）、`markdown_convert.py`（markdown-it-py 或内置读取器） |
| P13-012 | 完成 | `cross_type.py`：docx ↔ pptx（决定 8 的分页），工作表区域 → docx/pptx 表格 |
| P13-013 | 未通过 | 同一次 Windows 检查：C、D 组通过；A 组版面未达标；`convert-legacy-doc-with-wps` 0/3 |
| P13-014 | 完成 | `pdf_convert.py`：标题（按字号）、列表、有线框和按对齐识别的表格、图片、页眉页脚（进 docx 的页眉页脚）、页面大小和边距 |
| P13-015 | 完成 | PDF → xlsx 每个表格一个工作表；PDF → pptx 每页一张幻灯片（按阅读顺序排版，不按页面坐标定位） |
| P13-016 | 完成 | `--ocr` 和 `ocr` 可选依赖（RapidOCR）；没装或不加 `--ocr` 时报 `PDF_NEEDS_OCR`；本地扫描件字符准确率 98.5%（300 dpi） |
| P13-017 | 完成 | `convert` 统一入口（CLI、MCP `wps_agent_convert`），5 个 `convert-` 评测任务和离线判定 `fidelity`，离线测试确认判定在真实转换结果上通过 |
| P13-018 | 未通过 | 同一次 Windows 检查：E-supplier-docx 版面 0.5626（要求 0.85）、B-doc-docx 0.8687（要求 0.95）、B-odt-docx 超时；见“Windows 检查结果” |

### 离线转换矩阵

`python scripts/fidelity_baselines.py`（有 Chromium，版面用 LibreOffice，只作回归基线），26 项全部达到本组门槛。LibreOffice 的版面分数不计入判定（决定 1），正式门槛看 WPS。

| 用例 | 路径 | 文字 | 结构 | 格式 | 动画 | 数据 | 版面 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A-report-docx | html-editable | 100% | 100% | 100% | — | 100% | 0.88 |
| A-contract-docx | html-editable | 100% | 100% | 100% | — | 100% | 0.74 |
| A-newsletter-docx | html-editable | 100% | 100% | 100% | — | — | 0.86 |
| A-manual-docx | html-editable | 100% | 100% | 100% | — | 100% | 0.83 |
| A-pdfsource-docx | html-editable | 100% | 100% | 100% | — | 100% | 0.88 |
| A-budget-xlsx | html-editable | 100% | 100% | — | — | 100% | — |
| A-launch-pptx | html-editable | 100% | 100% | 100% | 100% | 100% | 0.92 |
| A-training-pptx | html-editable | 100% | 100% | 100% | 100% | — | 0.95 |
| A-quarterly-pptx | html-editable | 100% | 100% | 100% | 100% | 100% | 0.95 |
| A-brief-html | office-to-html | 100% | 100% | 100% | — | 100% | — |
| A-deck-html | office-to-html | 100% | 100% | 100% | 100% | 100% | — |
| A-book-html | office-to-html | 100% | 100% | 100% | — | 100% | — |
| C-gbk-csv-xlsx | csv-to-xlsx | 100% | 100% | — | — | 100% | — |
| C-utf8-tsv-xlsx | csv-to-xlsx | 100% | 100% | — | — | 100% | — |
| C-book-csv | xlsx-to-csv | 100% | 100% | — | — | 100% | — |
| C-guide-docx | markdown-to-office | 100% | 100% | — | — | 100% | — |
| C-api-html | markdown-to-html | 100% | 100% | — | — | 100% | — |
| C-notes-docx | markdown-to-office | 100% | 100% | — | — | — | — |
| C-brief-md | to-markdown | 100% | 100% | — | — | 100% | — |
| D-brief-pptx | docx-to-pptx | 100% | 100% | — | — | 100% | — |
| D-deck-docx | pptx-to-docx | 100% | 70% | — | 0% | 100% | — |
| D-book-docx | xlsx-range-to-table | 100% | 100% | — | — | 100% | — |
| D-book-pptx | xlsx-range-to-table | 100% | 100% | — | — | 100% | — |
| E-supplier-docx | pdf-to-office | 100% | 100% | — | — | 100% | 0.87 |
| E-supplier-xlsx | pdf-to-office | 100% | 100% | — | — | 100% | — |
| E-supplier-pptx | pdf-to-office | 100% | 100% | — | — | 100% | — |

D 组只考核文字和数据（F5）：pptx → docx 的结构 70% 和动画 0% 是预期的，文档里没有幻灯片和动画。没有浏览器时（`--no-browser`），除外观模式（需要浏览器，报 `BROWSER_BACKEND_UNAVAILABLE`）外其余 25 项同样达标。

### Windows 上要做的（P13-008、P13-013、P13-018，可以一次做完）

1. `pip install -e ".[html,fidelity,pdf,test]"`，`npm install`，WPS 设为默认应用。
2. `python scripts/fidelity_baselines.py --renderer wps --wps --out <结果目录>`：A、C、D、E 组用 WPS 测版面，加上 B 组经 WPS 的 9 个方向（.doc、.odt、.xls、.ppt 转 OOXML，OOXML 转 .wps、.et、.dps、.odt，pptx 转 PNG）。看 F2、F3、F6 的门槛。
3. `python scripts/run_windows_check.py eval --prefix convert- --repeat 3 --min-passes 2` 和 `--prefix html-`：F7。
4. 在 WPS 演示里放映 `training.html` 转出的 pptx（外观模式），确认退出、强调、单击和“上一项之后”的动画。
5. 结果按惯例提交并推送到 `cursor/phase13-windows-<commit>`。

### Windows 检查结果（2026-10-18，`4b263d9`）

结果和原始输出在 `scripts/windows_check/results/20261018T133723Z-4b263d9-fidelity/`（保真度、放映）以及相邻的两个 `*-eval` 目录（评测）。

- 保真度（WPS）：A 组 5 份 docx 的版面都低于 0.90（contract 0.369、manual 0.812、newsletter 0.823、report 0.853、pdfsource 0.855）；pptx 3 份都通过（0.914–0.957）；xlsx 和 Office→HTML 没有版面项。E-supplier-docx 0.5626（要求 0.85）。B 组 `B-doc-docx` 0.8687（要求 0.95），`B-odt-docx` 180 秒超时；其余 B 方向通过，单独复测 `B-docx-wps`、`B-docx-odt` 的版面都是 1.0。C、D 组全部通过。
- 评测：`--prefix convert-` 4/5（`convert-legacy-doc-with-wps` 0/3，没有生成 `brief.pdf`）；`--prefix html-` 5/5（报告 2/3，其余 3/3）。
- 放映：`training.html` 的外观 pptx 在 WPS 里确认了退出、强调、单击和“上一项之后”的动画（第 2 页的单击动画需要多按一次才翻页）。
- 结论：F2 的 A 组版面、F3 的 B-doc-docx/B-odt-docx、F6 的 E-supplier-docx 和 F7 的一个评测任务未达标，P13-008、P13-013、P13-018 不能算完成。检查还修掉了保真度脚本的两处 Windows 问题（临时目录清理、WPS 分数比 LibreOffice 基线）。

### 第一次 Windows 检查之后的修复（待第二次检查）

| 发现 | 原因 | 修复 |
| --- | --- | --- |
| contract 0.369、E-supplier-docx 0.5626 | 分数正好是“少一页”的样子：WPS 把 docx 排成了比浏览器或 PDF 多一页（缺页按 0 分计）。HTML 没写 `@page` 时浏览器按 A4 打印，docx 却用模板的 US Letter（矮 18 mm）；WPS 还在中文和西文、数字之间自动加空（`autoSpaceDE/DN`），并按文档网格对齐，浏览器都不做 | 没有 `@page` 时 docx 用 A4；文档默认段落关掉自动加空和网格对齐，段后 0、单倍行距（浏览器的默认） |
| HTML → docx 版面普遍在 0.81–0.86 | 表格单元格的边框和底纹又被当成段落边框画了一遍（每格多一条线）；列表文字没有按浏览器缩进 40 px | 单元格的边框和底纹只给单元格；列表项的左缩进取浏览器里 `<li>` 的位置，编号悬挂在前 |
| E-supplier-docx | PDF 的行距和段距没有带过来，WPS 按字体的自然行高排 | PDF → docx 每段带上页面上量到的段前距离和行距（固定值） |
| B-doc-docx 0.8687 | 拿 WPS 渲染的 `.docx` 结果和 `brief.docx`（`.doc` 的来源，由 LibreOffice 另存）比，比的是两个不同的文件 | 版面改为比较 WPS 渲染的 `.doc`/`.odt` 源文件本身和转换结果（F3 的原意），文字和结构仍和来源 OOXML 比 |
| B-odt-docx 超时 | 推测 WPS 打开 `.odt` 时弹出“转换文件”确认 | 文字的 `Documents.Open` 传 `ConfirmConversions=$false`；待复测 |
| B-docx-wps、B-docx-odt 级联失败 | 上一例超时后 WPS 仍占用文件、拒绝调用 | 每个 B 用例用自己的目录；`RPC_E_CALL_REJECTED` 时等待后重试两次 |
| `convert-legacy-doc-with-wps` 0/3 | `fidelity_fixtures` 把 `brief.docx` 也复制进工作目录，任务要的输出已存在，`convert` 拒绝覆盖 | 任务改为输出 `legacy.docx`、`legacy.pdf`；新测试保证任务输出不和夹具重名 |

本地 LibreOffice 基线随之更新（contract 0.739 → 0.806，其余小幅上升）。LibreOffice 的替代字体和 Chromium 不同，本地分数上不去，WPS 上两边都是微软雅黑。

第二次检查：`python scripts/fidelity_baselines.py --renderer wps --wps --out <结果目录>`，`--out` 会写出每例的完整报告（含页数、逐页分数）和每页的对照图（左源右结果，文件名带分数），一并提交；再跑 `eval --prefix convert-`。

## 任务拆分

| 任务 | 里程碑 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- | --- |
| P13-001 | 1 | F1 | `fidelity-check` 的文字、结构、格式、动画、数据比较，CLI 和 MCP 工具，离线测试 | 本地 |
| P13-002 | 1 | F1 | 版面检查：各格式渲染成图、按页配对、SSIM；`fidelity` 可选依赖 | 本地 |
| P13-003 | 1 | F2 | 文字类至少 5 份、演示类至少 3 份输入，记录 LibreOffice 基线 | 本地 |
| P13-004 | 1 | F2 | HTML → docx 的 CSS 属性映射（按浏览器计算样式） | 本地 |
| P13-005 | 1 | F2 | docx → 干净 HTML 和往返 | 本地 |
| P13-006 | 1 | F2 | HTML → pptx 按位置摆放、背景、字体、退出和强调动画、动画顺序；外观优先模式 | 本地 |
| P13-007 | 1 | F3 | `convert` 命令：旧格式、WPS 原生格式、ODF 互转和每页 PNG，经 WPS；输入和测试 | 本地 |
| P13-008 | 1 | F2、F3、F7 | Windows：里程碑 1 的输入跑 `fidelity-check`，评测，放映；发布 0.10.0 | Windows + 你 |
| P13-009 | 2 | F2 | pptx → HTML（绝对定位、动画转回 CSS） | 本地 |
| P13-010 | 2 | F2 | HTML ↔ xlsx 的样式、列宽、冻结，xlsx → HTML，公式往返（决定 7） | 本地 |
| P13-011 | 2 | F4 | CSV/TSV ↔ xlsx（编码、分隔符、类型）；Markdown ↔ docx/HTML | 本地 |
| P13-012 | 2 | F5 | 跨类型：docx ↔ pptx，xlsx 区域 → docx/pptx 表格 | 本地 |
| P13-013 | 2 | F2、F4、F5、F7 | Windows：里程碑 2 的检查和评测；发布 0.11.0 | Windows + 你 |
| P13-014 | 3 | F6 | PDF → docx：文字层、段落、标题、列表、表格、图片、页眉页脚 | 本地 |
| P13-015 | 3 | F6 | PDF → xlsx 表格识别；PDF → pptx 每页可编辑 | 本地 |
| P13-016 | 3 | F6 | 扫描件 OCR（`ocr` 可选依赖） | 本地 |
| P13-017 | 3 | F7 | 每组的评测任务和离线判定测试 | 本地 |
| P13-018 | 3 | F6、F7、F8 | Windows：里程碑 3 的检查和全部 `convert-`、`html-` 评测；发布 0.12.0 | Windows + 你 |

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 范围很大，一个阶段可能拖得很长 | 迟迟发不出版本 | 三个里程碑各自发布；里程碑之间可以按需要调整顺序 |
| Office 的版面模型和 CSS 不对应 | 某些页面达不到 0.90 | 按浏览器计算结果落位；达不到的输入写明原因，外观优先模式兜底 |
| PDF 没有段落和表格的结构信息 | PDF → Office 的结构恢复不准 | 门槛分开（版面 0.85、表格 98%）；输入覆盖常见版式；结果里给出每页的置信度 |
| WPS 和 LibreOffice 渲染差异 | CI 通过但 WPS 不达标 | 正式门槛只认 WPS；LibreOffice 只看回退 |
| WPS 对 ODF 和旧格式的支持因版本而异 | 部分方向在某些机器上不可用 | 报告不支持的原因（决定 9），兼容矩阵记录 |
| 字体缺失或替换 | 版面相似度失真 | 固定字体，缺字体时标记不可比 |
| OCR 和浏览器依赖让环境变重 | 安装和 CI 变慢 | 全部做成可选依赖，没装时明确报告 |
