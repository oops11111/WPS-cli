# Phase 13 计划：全格式高保真互转

状态：**planned**（2026-10-18 规划，同日你决定把全部格式并入本阶段；等你确认下面“待确认的决定”后激活）。

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

## 待确认的决定

按惯例给出默认建议，你说“OK”即按默认激活。

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
