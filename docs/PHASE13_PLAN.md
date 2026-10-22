# Phase 13 计划：全格式高保真互转

状态：**active**（2026-10-18 规划，同日你决定把全部格式并入本阶段；同日你说“phase13三个里程碑做一个提交”，按默认决定激活。三个里程碑的本地任务已在一次提交中完成，版本号 0.10.0 包含全部内容；Windows 上的三次检查 P13-008、P13-013、P13-018 于 2026-10-18 在 `4b263d9`、2026-10-22 到 10-23 在 `c117637`、`8899219`、`c55d04e`、`c205851`、`f8ed7bd`、`3095499`、`c149caf` 和 `3f82375` 上各跑过一遍，仍未全部通过，见“Windows 检查结果”）。

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
| P13-008 | 未通过 | 第九轮 2026-10-23（`3f82375`）：A 组 report 0.9236、newsletter 0.9170 通过；contract 0.8491、manual 0.8873、pdfsource 0.8980 仍低于 0.90；`convert-`/`html-` 都是 5/5；见“Windows 检查结果（第九轮）” |
| P13-009 | 完成 | pptx → HTML：每页一个定位的 section，动画转回 `@keyframes`，切换转回 `data-transition`，备注 |
| P13-010 | 完成 | HTML → xlsx 的字体、填充、边框、对齐、列宽、冻结表头，`data-formula` 还原公式；xlsx → HTML |
| P13-011 | 完成 | `tabular.py`（编码、分隔符、类型）、`markdown_convert.py`（markdown-it-py 或内置读取器） |
| P13-012 | 完成 | `cross_type.py`：docx ↔ pptx（决定 8 的分页），工作表区域 → docx/pptx 表格 |
| P13-013 | 未通过 | 第九轮：C、D 组通过；A 组还剩 3 份未达标（pdfsource 0.8980）；两组评测都是 5/5 |
| P13-014 | 完成 | `pdf_convert.py`：标题（按字号）、列表、有线框和按对齐识别的表格、图片、页眉页脚（进 docx 的页眉页脚）、页面大小和边距 |
| P13-015 | 完成 | PDF → xlsx 每个表格一个工作表；PDF → pptx 每页一张幻灯片（按阅读顺序排版，不按页面坐标定位） |
| P13-016 | 完成 | `--ocr` 和 `ocr` 可选依赖（RapidOCR）；没装或不加 `--ocr` 时报 `PDF_NEEDS_OCR`；本地扫描件字符准确率 98.5%（300 dpi） |
| P13-017 | 完成 | `convert` 统一入口（CLI、MCP `wps_agent_convert`），5 个 `convert-` 评测任务和离线判定 `fidelity`，离线测试确认判定在真实转换结果上通过 |
| P13-018 | 未通过 | 第九轮：E-supplier-docx 0.8741 达标；ODF 两个方向仍记为 `FORMAT_NOT_SUPPORTED_BY_WPS`，B-odt-docx 60 秒内结束、无残留；B 组其余方向通过；见“Windows 检查结果（第九轮）” |

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

### Windows 检查结果（第二轮，2026-10-22，`c117637`）

结果和原始输出在 `scripts/windows_check/results/20261022T031614Z-c117637-fidelity/`（保真度 `results.json`/`pages/`、B 组复测、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 5 份 docx 的版面都提高了，但仍低于 0.90：contract 0.7505、manual 0.8251、newsletter 0.8339、report 0.8659、pdfsource 0.8794；pptx 3 份通过（0.9137–0.9573）；xlsx 和 Office→HTML 没有版面项。E-supplier-docx 0.5762（源 2 页、目标 3 页，要求 0.85）。B 组 `B-doc-docx` 已到 1.0；`B-odt-docx` 仍 180 秒超时（单独复测也超时）；`B-docx-wps`、`B-docx-odt` 在整轮里仍是 `DOCUMENT_HELD_OPEN` 级联，单独复测都是 1.0。C、D 组全部通过。
- 评测：`--prefix convert-` 4/5（`convert-docx-to-pptx` 1/3；`convert-legacy-doc-with-wps` 已 3/3）；`--prefix html-` 5/5（两个任务 2/3，其余 3/3）。
- 放映：`training.html` 的外观 pptx 在 WPS 里仍然正确：fade/push/wipe，飞入、pulse 强调、延迟退出淡出、单击和“上一项之后”。
- 结论：第一轮的 `B-doc-docx` 和 `convert-legacy-doc-with-wps` 已修好；仍未达标的是 A 组 5 份 docx 的版面、`E-supplier-docx`、`B-odt-docx` 和 `convert-docx-to-pptx`。P13-008、P13-013、P13-018 仍不能算完成。

### 第二次 Windows 检查之后的修复（待第三次检查）

第二次检查（`c117637`）带回了逐页对照图，问题能直接看出来：

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| A 组 docx 0.75–0.88 | 行距、表格行高、标题间距都比浏览器高约 10%：16.5 pt 的行被拉到文档网格的 18 pt。WPS 不认文档默认里的“不对齐网格” | 每个段落自己写 `snapToGrid=0`，节里去掉文档网格 |
| 同上 | 表格比浏览器宽、左边框伸出正文边界 | 列宽不再加 6 px（只留 2 px 防止刚好放下的单元格换行）；表格按单元格边距缩进，左边框对齐正文 |
| E-supplier-docx 0.5762 | 列表挤在一起、其后空出一大段，把内容推到第 3 页；标题被加粗（PDF 里是常规体）；夹具 PDF 本身还带着旧版的双线单元格 | 按页面坐标累计计算每段起点（段前距离 + 固定行距）；表格前的空隙落到上一段的段后；表格的行高、单元格内边距和表头粗细取自 PDF；标题粗细跟随 PDF；用修好的代码重新生成夹具。本地 0.877 → 0.931 |
| B-docx-wps、B-docx-odt 在整轮里 `DOCUMENT_HELD_OPEN` | 同一用例里上一步刚关的文件 WPS 还没放开 | `DOCUMENT_HELD_OPEN` 也等待后重试（最多两次） |
| B-odt-docx 仍超时 | `ConfirmConversions=$false` 无效 | 转换脚本记录进行到哪一步，超时报告写明“WPS was opening the input / saving the output”，下次检查据此判断是打开时卡住（多半有对话框）还是另存时卡住 |
| `convert-docx-to-pptx` 1/3 | 失败的两次都先转成 `_probe.pptx`/`_candidate.pptx` 再逐页查看，16 轮用完也没写 `brief.pptx` | `convert` 的结果带 `output_summary`（幻灯片标题、标题、工作表），工具说明写明“直接写到用户要的路径，用 `check` 核对，不要先转试验副本” |

本地 LibreOffice 基线已更新。contract 在本地降到 0.785，是 LibreOffice 的替代字体比微软雅黑宽、窄列里的“30%”换了行；WPS 上两边都是雅黑。

第三次检查与第二次相同：`fidelity_baselines.py --renderer wps --wps --out <目录>`，`eval --prefix convert-` 和 `--prefix html-`。

### Windows 检查结果（第三轮，2026-10-22，`8899219`）

结果和原始输出在 `scripts/windows_check/results/20261022T054905Z-8899219-fidelity/`（保真度 `results.json`/`pages/`、B 组复测、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 5 份 docx 的版面仍是 0.7639–0.8779（contract 0.7639、manual 0.8241、newsletter 0.8339、report 0.8659、pdfsource 0.8779），都低于 0.90；pptx 3 份通过（0.9137–0.9573）；xlsx 和 Office→HTML 没有版面项。E-supplier-docx 0.5918（源 2 页、目标 3 页，要求 0.85）。B 组 `B-doc-docx` 1.0；`B-odt-docx` 仍 180 秒超时（“WPS was opening the input”，单独复测也超时）；`B-docx-wps`、`B-docx-odt` 在整轮里仍是 `DOCUMENT_HELD_OPEN` 级联，单独复测都是 1.0。C、D 组全部通过。
- 评测：`--prefix convert-` **5/5**（五个任务都是 3/3）；`--prefix html-` 4/5（`html-complex-report-to-docx` 1/3：第 1、3 次用新的 `convert` 而不是 `convert_smoke` 生成 PDF，检查仍只认旧工具；其余任务 3/3 或 2/3）。
- 放映：`training.html` 的外观 pptx 仍然正确（fade/push/wipe、飞入、pulse、延迟退出、单击和“上一项之后”）。
- 结论：`convert-` 已全过；`html-complex-report-to-docx` 是检查与工具不一致，建议任务检查接受 `convert` 或 `convert_smoke`。仍未达标的是 A 组 5 份 docx 版面、`E-supplier-docx`、`B-odt-docx`，以及 B 组连续用例的 WPS 占用。P13-008、P13-013、P13-018 仍不能算完成。

### 第三次 Windows 检查之后的修复（待第四次检查）

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| A 组 docx 0.76–0.88 | 网格已去掉，但行和表格行仍高约 1.3 倍：“最小值 16.5 pt”在 WPS 里被微软雅黑自己的行高（约 1.7 倍字号，11 pt 时约 18.7 pt）撑开 | 段落里没有图片、也没有比行高更大的字时，行距用“固定值”= 浏览器算出的 CSS 行高；否则仍用“最小值”，不裁切 |
| 同上 | `th{font-weight:normal}` 的表头仍是粗体 | 有计算样式时表头粗细跟随层叠结果，只在没有样式时默认加粗 |
| E-supplier-docx 0.5918（2 页变 3 页） | 第 2 页表格后的段落被推到第 3 页：下边距取自正文结束的位置（短页在页中结束，下边距 427 pt） | 下边距与上边距相同，除非正文比这更靠下 |
| B-docx-wps、B-docx-odt 整轮里 `DOCUMENT_HELD_OPEN` | 单独复测（每步前结束 WPS）都是 1.0 | 矩阵脚本在 B 组每一步前等 WPS 退出（最多 30 秒）；矩阵开始时没有 WPS 在运行的话，仍未退出的 WPS（卡在对话框或还占着文件）由脚本结束 |
| B-odt-docx 打开时超时 | 打开 `.odt` 时 WPS 停住，多半是隐藏窗口里的对话框 | 以只读、不进最近列表的方式打开源文件；超时时列出 WPS 当前可见窗口的标题（`wps_windows`），下次检查据此看出是哪个对话框 |
| `html-complex-report-to-docx` 1/3 | 用 `convert` 生成 PDF，检查只认 `convert_smoke` | `tool_called` 检查可以列出做同一步的其他工具（`or`，输出路径按后缀匹配）；该任务也接受 `convert` 写出 `.pdf` |

本地 LibreOffice 的版面分数基本不变（LibreOffice 本来就不按字体放大“最小值”行距；supplier 本地已是 2 页），基线已重新写入。

第四次检查与第三次相同：`fidelity_baselines.py --renderer wps --wps --out <目录>`，`eval --prefix convert-` 和 `--prefix html-`。`B-odt-docx` 若仍超时，请把错误信息里的 “Open WPS windows: …” 一并带回。

### Windows 检查结果（第四轮，2026-10-22，`c55d04e`）

结果和原始输出在 `scripts/windows_check/results/20261022T065744Z-c55d04e-fidelity/`（保真度 `results.json`/`pages/`、B 组复测、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 5 份 docx 的版面 0.7589–0.8779，仍都低于 0.90（与第三轮基本持平）；pptx 3 份通过（0.9137–0.9573）。E-supplier-docx **0.8745，2 → 2 页，已达标**（第三轮 0.5918）。B 组除 `B-odt-docx` 外全部通过（`B-docx-wps`、`B-docx-odt` 整轮也通过）；`B-odt-docx` 仍 180 秒超时。C、D 组全部通过。
- `B-odt-docx` 的超时信息没有 `Open WPS windows: …` 段：卡住时 WPS 没有带标题的可见窗口（`OpusApp` 的 `WPS文字` 是隐藏的，两个可见 Qt 窗口标题为空），`_wps_window_titles()` 只收集可见且带标题的窗口。诊断见 `b-odt-timeout.txt`。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**（报告任务现在接受 `convert`）；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：E-supplier-docx、B 组连续用例和两组评测都已修好；仍未达标的是 A 组 5 份 docx 的版面和 `B-odt-docx` 超时。P13-008、P13-013、P13-018 仍不能算完成。

### Windows 检查结果（第四轮，2026-10-22，`c55d04e`）

结果在 `scripts/windows_check/results/20261022T065744Z-c55d04e-fidelity/`（`b-odt-timeout.txt` 是超时时的窗口枚举）和相邻的两个 `*-eval` 目录。

- 保真度（WPS）：E-supplier-docx **0.8745 通过**（2 → 2 页）。B 组整轮里 `B-docx-wps`、`B-docx-odt` 都是 1.0，WPS 占用级联消失；除 `B-odt-docx` 外 B 组全过。`B-odt-docx` 仍在打开输入时超时：没有可见的带标题窗口，只有两个可见的无标题 Qt 窗口。A 组 5 份 docx 仍是 0.7589–0.8779；pptx、C、D 组通过。
- 评测：`--prefix convert-` 5/5，`--prefix html-` **5/5**（报告任务回到 3/3）。
- 结论：剩下 A 组 docx 版面和 `B-odt-docx`。

### 第四次 Windows 检查之后的修复（待第五次检查）

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| contract 表格行仍高约 7 pt | 有上下单元格边距（`tcMar` top/bottom）的行都高出一截；PDF 来的表格没有上下边距，行高与源一致 | 上下内边距改为单元格首段的段前、末段的段后，`tcMar` 只留左右；`tcPr` 子元素按架构顺序（`tcBorders` 在 `shd` 前） |
| report、manual、newsletter 的正文行距仍偏大 | 这些页面没有写 `line-height`（`normal`），docx 用“单倍”，WPS 给微软雅黑的单倍行比浏览器的 normal 高 | 浏览器布局时按字体测出 normal 的行高（`line-height-normal`），docx 按这个值用“固定值”（同样只在段内没有更高的内容时）。本地 report 0.874 → 0.890、newsletter 0.869 → 0.883、manual 0.842 → 0.857 |
| `B-odt-docx` 超时时没有带标题的窗口 | 两个可见的无标题 Qt 窗口 | 超时报告列出所有可见的 WPS 窗口（无标题的写成“untitled 类名 宽x高”），并把每个窗口截图存到 `%TEMP%\wps-agent-timeout-*.png`，路径写在错误信息里 |

第五次检查与第四次相同。`B-odt-docx` 若仍超时，请把错误信息里列出的截图一并带回。

### Windows 检查结果（第五轮，2026-10-22，`c205851`）

结果和原始输出在 `scripts/windows_check/results/20261022T080819Z-c205851-fidelity/`（保真度 `results.json`/`pages/`、超时截图、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 5 份 docx 的版面 0.8188–0.8859，比第四轮又提高，但仍都低于 0.90；pptx 3 份通过（0.9137–0.9573）。E-supplier-docx 0.8745（2 → 2 页）已达标。B 组除 `B-odt-docx` 外全部通过。C、D 组全部通过。
- `B-odt-docx` 仍 180 秒超时。错误信息列出两个无标题的 `Qt5QWindowIcon` 窗口（440×260、420×240）和 `%TEMP%\wps-agent-timeout-*.png`。工具用屏幕区域截的图被一个 Cursor 窗口盖住，看到的是 Cursor 页面；用 `PrintWindow` 直接抓 420×240 的窗口可以看到 WPS 的模态框：**“文件损坏提示——当前文档无法正确读取，继续打开将显示乱码”**，按钮为“关闭/继续打开”。WPS 把 `brief.odt` 判为损坏并在等待用户选择，所以转换超时。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：仍未达标的是 A 组 5 份 docx 的版面（0.819–0.886，要求 0.90）和 `B-odt-docx`。后者可以换一份 WPS 能直接打开的 ODT、自动点“继续打开”，或按决定 9 记为 WPS 不支持并写明原因。P13-008、P13-013、P13-018 仍不能算完成。

### Windows 检查结果（第五轮，2026-10-22，`c205851`）

结果在 `scripts/windows_check/results/20261022T080819Z-c205851-fidelity/`（含超时窗口截图）和相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 docx 继续上升但仍低于 0.90（report 0.8850、contract 0.8188、newsletter 0.8859、manual 0.8681、pdfsource 0.8827）；pptx、xlsx、Office→HTML 通过。E-supplier-docx 0.8745 通过。B 组除 `B-odt-docx` 外全部 1.0。C、D 组通过。
- `B-odt-docx`：PrintWindow 截到的对话框是“文件损坏提示”（无法正确读取文档，提供“关闭 / 继续打开”）。WPS 把 LibreOffice 写出的 `brief.odt`（ODF 1.3，带 loext 扩展）当成损坏文件。超时截图用的是屏幕复制，被其他窗口挡住。
- 评测：`--prefix convert-` 5/5，`--prefix html-` 5/5。

### 第五次 Windows 检查之后的修复（待第六次检查）

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| A 组 docx 的行比浏览器宽 | 浏览器在 10 mm 打印边距里还有 body 默认的 8 px 外边距；docx 没有，正文每边宽 8 px，换行位置不同，列表和表格整体左移 | 页边距加上 body 的左右外边距和内边距（层叠模式也按浏览器默认 8 px）。PDF 转来的 HTML 设 `body{margin:0}`（边距已从 PDF 量出）；docx → HTML 时 `@page` 边距扣掉页面自己的 24 px，往返不改变边距 |
| contract 表格比浏览器宽 8 px | 每列加 2 px 余量，4 列累计 8 px | 余量改为 1 px |
| contract 签字表前的空白缺了 | `.sign{margin-top:24pt}`：表格的上下外边距没有映射 | 表格的上外边距并入前一段的段后，下外边距并入后一段的段前（按 CSS 合并取大） |
| `B-odt-docx` 打开时弹“文件损坏提示” | WPS 不接受 LibreOffice 默认的 ODF 1.3 扩展格式 | `brief.odt` 改用 ODF 1.2（无 loext 扩展）重新生成，`--make-fixtures` 同样写 ODF 1.2；超时截图改用 PrintWindow（不会被其他窗口挡住）；ODF 文件打开超时时，错误信息说明可能是 WPS 的损坏文件提示，建议另存为 ODF 1.2 或 OOXML |

本地 LibreOffice 基线已重写（supplier 不变；report、manual、newsletter 略升）。第六次检查与第五次相同。

### Windows 检查结果（第六轮，2026-10-22，`f8ed7bd`）

结果和原始输出在 `scripts/windows_check/results/20261022T115711Z-f8ed7bd-fidelity/`（保真度 `results.json`/`pages/`、超时截图、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 5 份 docx 的版面 0.8328–0.8951，比第五轮又提高（newsletter 0.8951、report 0.8927 已接近），但仍都低于 0.90；pptx 3 份通过（0.9137–0.9573）。E-supplier-docx 0.8745（2 → 2 页）达标。B 组除 `B-odt-docx` 外全部通过。C、D 组全部通过。
- `B-odt-docx`：`brief.odt` 已是 ODF 1.2（三个 XML 的 `office:version` 都是 1.2），WPS 12.8.2.18913 **仍然弹“文件损坏提示”**（“当前文档无法正确读取，继续打开将显示乱码”，按钮“关闭/继续打开”），转换 180 秒超时。截图 `timeout-printwindow-420x240.png`。
- 本轮超时信息里没有 `Open WPS windows: …` 段：`#125` 的 C# `PrintWindow` 改动在 PowerShell 7 上 `Add-Type` 编译失败（`CS1069: System.Drawing.Graphics` 已转发到 `System.Drawing.Common`），窗口列表和截图都为空；错误原文在 `add-type-error.txt`。这是需要修掉的回归。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：仍未达标的是 A 组 5 份 docx 的版面（0.833–0.895，要求 0.90）和 `B-odt-docx`。ODF 1.2 没有消除 WPS 的损坏提示；下一步可以用 WPS 自己保存的 ODT、自动点“继续打开”，或按决定 9 记为不支持。另需修复超时窗口截图回归。P13-008、P13-013、P13-018 仍不能算完成。

### Windows 检查结果（第六轮，2026-10-22，`f8ed7bd`）

结果在 `scripts/windows_check/results/20261022T115711Z-f8ed7bd-fidelity/` 和相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 docx 0.8328–0.8951（report 0.8927、contract 0.8328、newsletter 0.8951、manual 0.8770、pdfsource 0.8853），仍都低于 0.90；其余各组和 B 组（除 `B-odt-docx`）都通过。
- `B-odt-docx`：ODF 1.2 的 `brief.odt` 仍弹“文件损坏提示”（“当前文档无法正确读取，继续打开将显示乱码”）。
- #125 的窗口截图在 PowerShell 7 上编译失败（CS1069），超时信息里没有窗口列表。
- 评测：两组都是 5/5。

### 第六次 Windows 检查之后的修复（待第七次检查）

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| 超时时没有窗口列表 | C# 类型引用 `System.Drawing.Graphics`，PowerShell 7 上找不到 | C# 只声明 `PrintWindow(hWnd, hdc, flags)`，设备上下文在 PowerShell 里取 |
| `B-odt-docx` 仍弹“文件损坏提示” | ODF 版本不是原因 | 新增 `scripts/windows_check/odt_probe.py`：WPS 自己写的 ODT、LibreOffice 的 ODT、去掉附加部件的 ODT 和手写的最小 ODT 各转一次，看 WPS 接受哪种，再决定换夹具还是按决定 9 记为这一版 WPS 不支持 |
| manual 的代码块两行之间多一空行 | Windows 上检出的夹具是 CRLF，`\r` 和 `\n` 各成一个换行 | 保留空白的文字先把 CRLF、CR 归一为一个换行 |
| manual 的代码块、注意框没有内边距 | 段落边框紧贴文字，底色只到文字 | 内边距写成段落边框与文字的距离（只有底色时用同色边框），文字按自身内边距和边框缩进，盒子左边缘留在浏览器的位置 |
| report 的项目符号列表文字偏左 16 px | 模板的列表编号在 360 缇有制表位，窄的项目符号停在那里 | 列表段落清除编号的制表位，在缩进处设一个 |
| report 的表格每行矮 2 px | 默认 `border-spacing: 2px` 没有映射 | 分离边框的表格把行间距算进行高；PDF 转来的表格标为合并边框 |
| 代码块的 normal 行高偏大 | 测量用的样本带汉字，回退字体让纯拉丁文的行变高（Consolas 17 px，浏览器 14 px） | 元素文字里有汉字才用带汉字的样本 |

本地 LibreOffice 基线已重写：newsletter 0.886 → 0.901，report 0.893 → 0.896，contract 0.791 → 0.804；manual 0.863 → 0.852（本地替代字体让窄列里的 “WPS Office” 换行，WPS 上两边都是雅黑）。

### Windows 检查结果（第七轮，2026-10-22，`3095499`）

结果和原始输出在 `scripts/windows_check/results/20261022T132620Z-3095499-fidelity/`（保真度 `results.json`/`pages/`、`odt-probe.json`、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 newsletter 首次达到 0.90（0.9217）；其余四份 report 0.8940、manual 0.8866、pdfsource 0.8822、contract 0.8488 仍未达标。pptx 3 份通过（0.9137–0.9573）。E-supplier-docx 0.8744（2 → 2 页）达标。B 组除 `B-odt-docx` 外全部通过。C、D 组全部通过。
- `odt_probe.py`：只有 `wps-written`（WPS 自己保存的 ODT）在 3.8 秒内打开；`libreoffice`、`libreoffice-trimmed`、`minimal-ascii`、`minimal-cjk`、`minimal-cjk-styles` 全部 `COM_OPERATION_TIMEOUT`（约 61 秒），都弹“文件损坏提示”。所以问题不是 ODF 版本或 LibreOffice 扩展，而是这台 WPS 只直接打开自己生成的 ODT。可选的下一步：用 WPS 保存的 ODT 作夹具、自动回答“继续打开”，或按决定 9 记为不支持并写明原因。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：仍未达标的是 A 组 4 份 docx 的版面（0.849–0.894，要求 0.90）和 `B-odt-docx`。P13-008、P13-013、P13-018 仍不能算完成。

### 第七次 Windows 检查之后的修复（待第八次检查）

| 发现 | 看到的 | 修复 |
| --- | --- | --- |
| `odt_probe.py` 里只有 “WPS 自己写的 ODT” 能打开 | 那个文件以 `D0 CF 11 E0` 开头，是 OLE 复合文档，不是 ODF：这版 WPS 的“另存为 .odt”（格式码 23）根本不写 ODF，`B-docx-odt` 读回 1.0 读的也是它自己的二进制文件。所有真正的 ODF 都弹“文件损坏提示” | 按决定 9 记为这版 WPS 不支持 ODF：ODF 源最多等一分钟，打开时超时报 `FORMAT_NOT_SUPPORTED_BY_WPS`（说明原因），并结束这次转换启动的 WPS（脚本记录它启动的进程号）；写出的 .odt/.ods/.odp 不是 ODF 包时删除并报同一错误码。矩阵把这两个方向记为“不支持”而不是失败；`CONVERSION_MATRIX.md` 记录 |
| report 的 H₂O、x² 那一行矮 3 px，下面整页上移 | 浏览器里带上下标的行比 line-height 高 | 只含文字和行内元素的段落，行距取浏览器量出的高度除以行数（带上下标时最多 1.5 倍行高，否则 1.25 倍） |
| 列表编号离文字 24 px，浏览器约 15 px | 编号悬挂固定 24 px | 悬挂约 0.95 em，多位编号每多一位加 0.55 em |
| contract 表格仍宽 5 px | 每列 1 px 余量再加上换算截断 | 列宽换算成缇时向上取整（余量仍是 1 px：本地试过 0.5 px，“Windows 10 / 11” 换行了） |

本地 LibreOffice：report 0.896 → 0.911，pdfsource 0.881 → 0.887，contract 0.804 → 0.805；newsletter 0.901 → 0.897（本地 LibreOffice 画上下标的方式与浏览器不同）。基线已重写。

第八次检查与第七次相同（`odt_probe.py` 不必再跑）。

### Windows 检查结果（第八轮，2026-10-22，`c149caf`）

结果和原始输出在 `scripts/windows_check/results/20261022T150940Z-c149caf-fidelity/`（保真度 `results.json`/`pages/`、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 report 0.9234（上下标行修复）、newsletter 0.9169 通过；contract 0.8492、manual 0.8869、pdfsource 0.8823 仍未达标。pptx 3 份通过（0.9137–0.9573）。E-supplier-docx 0.8741（2 → 2 页）达标。B 组除两个 ODF 方向外全部通过，版面 1.0。C、D 组全部通过。
- ODF 方向按决定 9 记为不支持：`B-odt-docx` 报 `FORMAT_NOT_SUPPORTED_BY_WPS`（WPS 在 60 秒内没有打开 `brief.odt`，因为它把 ODF 当损坏文件询问），`B-docx-odt` 报同一代码（WPS 写出的 `.odt` 不是 OpenDocument 包，已删除）。`B-odt-docx` 在约 60 秒内结束；整轮矩阵 5 分 53 秒，结束后没有 WPS/et/wpp 进程。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：只剩 A 组三份 docx 的版面（contract 0.8492、manual 0.8869、pdfsource 0.8823，要求 0.90）未达标。P13-008、P13-013、P13-018 仍不能算完成。

### 第八次 Windows 检查之后的修复（待第九次检查）

第八次检查（`c149caf`）：report 0.9234、newsletter 0.9169 通过；ODF 两个方向按决定 9 记为不支持（B-odt-docx 60 秒后报 `FORMAT_NOT_SUPPORTED_BY_WPS` 并结束 WPS，B-docx-odt 删除非 ODF 的输出），整轮 5 分 53 秒、没有留下 WPS 进程。剩下 contract 0.8492、manual 0.8869、pdfsource 0.8823。

| 发现 | 对照图里看到的 | 修复 |
| --- | --- | --- |
| contract、manual 的有边框表格每行高 1 px | 浏览器合并边框时相邻两行共用一条边框，WPS 把每个单元格的边框都算进行高 | 合并边框的表格，单元格下内边距减去下边框宽度 |
| manual 的分隔线低 17 px | `<hr>` 是一个带下边框的空段落，占了一整行 | 分隔线段落固定行距 1 磅，上下外边距（浏览器默认 8 px）与前后段落按 CSS 合并 |
| manual 的编号紧贴文字 | 悬挂 0.95 em 在 10.5 pt 下不够“1.”加空格 | 悬挂改为约 1.05 em |
| pdfsource 的“采购中心”在浏览器里排在页眉下面，docx 里在页脚 | 夹具用 `data-page="footer"` 标了页脚，docx 按这个放到页脚，但 HTML 没有让浏览器这样打印的 CSS，于是下面整页错开一行 | 夹具加 `[data-page="footer"] { position: fixed; bottom: 0; }`（打印页脚的常规写法），浏览器也把它印在页脚。这是夹具的改动，不是转换器的；`supplier.pdf` 没有重新生成 |

本地 LibreOffice：manual 0.852 → 0.862，pdfsource 0.887 → 0.891，其余不变或略变。基线已重写。第九次检查与第八次相同。

### Windows 检查结果（第九轮，2026-10-23，`3f82375`）

结果和原始输出在 `scripts/windows_check/results/20261022T183319Z-3f82375-fidelity/`（保真度 `results.json`/`pages/`、放映）以及相邻的两个 `*-eval` 目录。

- 保真度（WPS）：A 组 report 0.9236、newsletter 0.9170 通过；contract 0.8491、manual 0.8873、pdfsource **0.8980** 仍未达标（pdfsource 只差 0.002）。pptx 3 份通过（0.9137–0.9573）。E-supplier-docx 0.8741（2 → 2 页）达标。B 组除两个 ODF 方向外全部通过；ODF 仍按决定 9 记为 `FORMAT_NOT_SUPPORTED_BY_WPS`，`B-odt-docx` 60 秒内结束。C、D 组全部通过。
- 评测：`--prefix convert-` **5/5**、`--prefix html-` **5/5**；都是 0 `wrong_tool_calls`、0 未验证写入。
- 放映：`training.html` 的外观 pptx 仍然正确。
- 结论：只剩 A 组三份 docx 的版面（要求 0.90）未达标。P13-008、P13-013、P13-018 仍不能算完成。

### 第九次 Windows 检查之后的修复（待第十次检查）

第九次检查（`3f82375`）：report 0.9236、newsletter 0.9170 通过；pdfsource 0.8823 → 0.8980（差 0.002）；contract 0.8491、manual 0.8873 不变；ODF 仍按决定 9 记为不支持，其余各组通过，评测两组 5/5。

在提交的页面对照图上直接算 SSIM：把 WPS 一侧整体平移最合适的像素后，pdfsource 从 0.878 升到 0.923（向上 3 px），contract 只从 0.849 到 0.864、manual 从 0.887 到 0.896（都是向左 1 px）。也就是说 pdfsource 差的是整体偏移，contract 和 manual 剩下的主要是两边渲染字形的细微差别，排版位置已经基本一致。

| 发现 | 看到的 | 修复 |
| --- | --- | --- |
| pdfsource 页眉及以下整体低 3 px，页脚高 10 px | docx 用 Word 默认的半英寸页眉、页脚距离；浏览器把页眉印在打印边距加 body 上外边距处，固定页脚印在下边距上 | 页眉距离 = 上页边距 + body 上外边距，页脚距离 = 下页边距。PDF 转来的 docx 改用 PDF 里页眉、页脚的实际位置（行框按 1.32 em 计，页眉不越过正文上边距） |

本地 LibreOffice：pdfsource 0.891 → 0.900，supplier 0.930 → 0.929，其余不变。基线已重写。第十次检查与第九次相同。

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
