# Phase 13 计划：高保真格式互转（HTML ↔ 文字、HTML → 演示）

状态：**planned**（2026-10-18 规划，等你确认下面“待确认的决定”后激活）。

## 目标

Phase 12 之后，HTML 转换为 WPS 三种格式已经保留语义、行内格式、合并单元格、数字格式、动画和切换，三个复杂输入在 WPS 上 3/3，动画放映正确。但“保留了什么”只靠逐项断言，没有统一的保真度度量；字体、字号、颜色以外的 CSS（行距、间距、对齐、缩进、底纹、边框、列宽、背景、元素位置）都不转换；反方向只有 WPS 另存的 HTML。

2026-10-18 你定下 Phase 13 的方向：**做好格式互转，要求高保真**（`docs/DEVELOPMENT_SUMMARY.md` 第 7 节，D5 到 D9）。按 D6，本阶段先做三个方向：

1. **HTML → 文字（docx）**：版面和样式与浏览器里的样子一致，仍可编辑。
2. **文字（docx）→ HTML**：干净的 HTML，再转回 docx 不丢东西。
3. **HTML → 演示（pptx）**：元素按浏览器算出的位置摆放，背景、字体、动画顺序与原页面一致。

表格方向（HTML ↔ xlsx）和演示、表格 → HTML 放在下一阶段（见“待确认的决定”第 1 条）。

“高保真”按 D7 量化判定，标准外观按 D8 以 Edge/Chromium 渲染为准，保真与可编辑冲突时按 D9 默认可编辑优先。

## 输入：现状和缺口

| 缺口 | 出处 |
| --- | --- |
| 没有统一的保真度度量，只有逐项断言（`tests/test_html_complex.py`） | P12-013 |
| docx 不转换行距、段前段后、对齐、缩进、底纹、边框、表格列宽和单元格底纹、图片尺寸、分页 | `src/wps_ai_agent_cli/html_editable.py`，`unsupported_css` |
| pptx 按标题加正文的固定版式排列，不按原页面位置；不转换背景、字体、字号；只有进入动画，全部“与上一动画同时”加延迟 | `src/wps_ai_agent_cli/html_slides.py` |
| docx → HTML 只有 WPS 另存（WPS 自己的格式）和受控往返（owned HTML v1，只保留结构） | `export-open-document`，`html-export` |
| 版面没有在 WPS 上和浏览器对比过 | P12-012 只检查文字和导出 PDF |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| F1 | 保真度检查 | 离线：新命令 `fidelity-check` 比较源 HTML 和转换结果，给出文字、结构、格式、版面、动画五项结果和总判定；版面检查把源 HTML 用 Chromium 渲染成图、把结果用 WPS（Windows）或 LibreOffice（Linux、CI）导出 PDF 再渲染成图，逐页计算结构相似度（SSIM）；每项都有离线测试 |
| F2 | HTML → docx 高保真 | 离线：`html-editable` 转换下文列出的 CSS 属性；全部文字类输入（至少 5 份）在 LibreOffice 上文字、结构、格式 100%，SSIM 达到每份输入记录的基线且不回退。Windows：同样的输入在 WPS 上 SSIM ≥ 0.90 |
| F3 | HTML → pptx 高保真 | 离线：元素按浏览器计算出的位置和尺寸放进幻灯片，转换背景、字体、字号、颜色、退出和强调动画、动画顺序；全部演示类输入（至少 3 份）在 LibreOffice 上文字、结构、格式、动画 100%，SSIM 达到基线。Windows：WPS 上 SSIM ≥ 0.90，你放映确认动画顺序 |
| F4 | docx → HTML 和往返 | 离线：新命令（或 `html-export` 扩展）把 docx 转为干净的 HTML（语义标签加内联样式，保留 F2 的全部属性）；HTML → docx → HTML 往返后，文字、结构、格式 100%，两次 HTML 的渲染 SSIM ≥ 0.95；WPS 另存的 docx 原件转出的 HTML 在 Chromium 里与 WPS 导出的 PDF 比较 SSIM ≥ 0.90 |
| F5 | Agent 评测 | Windows：新增的保真度评测任务（Agent 转换后自己跑 `fidelity-check`）和现有 3 个复杂 HTML 任务，一条 `eval --prefix html- --repeat 3 --min-passes 2` 每个任务至少 2/3 |
| F6 | 发布 0.10.0 | 按 `docs/RELEASING.md` 发布 `v0.10.0`（GitHub Release），在 Windows 上检查 wheel |

### F2 要转换的 CSS 属性

| 类别 | 属性 |
| --- | --- |
| 字符 | `font-family`（带中文回退）、`font-size`、`font-weight`、`font-style`、`color`、`background-color`（高亮）、`text-decoration`、`letter-spacing`、`vertical-align` |
| 段落 | `text-align`、`line-height`、`margin-top`/`margin-bottom`（段前段后）、`margin-left`/`text-indent`（缩进、首行缩进）、`background-color`（底纹）、`border`（段落边框）、`page-break-before`/`break-before` |
| 表格 | 列宽（`width`、`<col>`）、单元格 `background-color`、`border`、`padding`、`vertical-align`、`text-align`，表格整体宽度和对齐 |
| 图片 | `width`/`height` 属性和样式，`float` 映射为环绕（可编辑优先时为嵌入加对齐） |
| 页面 | `@page` 的纸张大小和页边距，`<header>`/`<footer>` 映射为页眉页脚 |

样式来源：内联 `style`、`<style>` 里的类和标签选择器、继承。复杂选择器（后代、伪类）不解释 CSS，而是用浏览器算出的计算样式（见“待确认的决定”第 3 条）。

## 待确认的决定

按惯例给出默认建议，你说“OK”即按默认激活。

| 决定 | 默认建议 | 依据 |
| --- | --- | --- |
| 1. 本阶段范围 | 只做 HTML ↔ docx 和 HTML → pptx；HTML ↔ xlsx、pptx/xlsx → HTML 放到 Phase 14 | D6 的顺序；三个方向的版面模型各不相同，一次只做两种文档类型才能把保真度做实 |
| 2. 版面检查的正式门槛用谁 | WPS（Windows）结果为准，≥ 0.90；LibreOffice 只做 CI 回归，每份输入记录基线，回退超过 0.02 即失败 | WPS 是目标环境；LibreOffice 渲染和 WPS 不同，不能用同一个绝对门槛 |
| 3. 样式和位置从哪里来 | 有浏览器（Playwright + Chromium/Edge，`html-render` 已在用）时取浏览器的计算样式和元素位置；没有时退回现在的语义转换，并在结果里写明 `fidelity: semantic` | 自己解释 CSS 永远追不上浏览器；退回保证没有浏览器的环境仍能用 |
| 4. SSIM 的实现 | 新增可选依赖 `fidelity`（numpy），PDF 渲染用已有的 pypdfium2；不装时 `fidelity-check` 只做文字、结构、格式、动画四项并说明版面未检查 | 不让基础安装变重 |
| 5. 字体 | 输入统一用“Microsoft YaHei, Noto Sans CJK SC, sans-serif”；缺字体时结果列出缺的字体，版面检查标记为不可比 | 版面相似度对字体最敏感 |
| 6. 版本号 | 0.10.0 | 新命令和新参数，按规则升次版本 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P13-001 | F1 | `fidelity-check` 的文字、结构、格式、动画四项比较（HTML 一侧取浏览器的计算样式，Office 一侧读文件），CLI 和 MCP 工具，离线测试 | 本地 |
| P13-002 | F1 | 版面检查：Chromium 渲染 HTML、LibreOffice 或 WPS 导出 PDF、pypdfium2 渲染、按页配对、SSIM；`fidelity` 可选依赖 | 本地 |
| P13-003 | F2、F3 | 输入：文字类至少 5 份（带页眉页脚和目录的公文、编号条款的合同、带图表和脚注的论文、两栏简历、现有报告），演示类至少 3 份（按设计稿绝对定位的营销页、现有发布会、图表为主的汇报）；每份记录 LibreOffice 基线 | 本地 |
| P13-004 | F2 | HTML → docx 的 CSS 属性映射（上表），用浏览器计算样式 | 本地 |
| P13-005 | F3 | HTML → pptx 按浏览器位置摆放、背景、字体、退出和强调动画、动画顺序（同时、之后、单击） | 本地 |
| P13-006 | F4 | docx → 干净 HTML，往返测试，WPS 原件测试 | 本地 |
| P13-007 | F2、F3 | 外观优先模式（`--fidelity appearance`）：无法可编辑表达的版面用文本框和固定位置 | 本地 |
| P13-008 | F5 | 保真度评测任务和离线判定测试 | 本地 |
| P13-009 | F2、F3、F4、F5 | Windows：全部输入用 WPS 跑 `fidelity-check`，跑评测，放映演示 | Windows |
| P13-010 | F6 | 定版本 0.10.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.10.0` | 本地 + 你 |

## 建议顺序

1. P13-001、P13-002（先有尺子），P13-003（输入和基线）。
2. P13-004 和 P13-006（文字双向），P13-005（演示），P13-007。
3. P13-008，然后一次上机做 P13-009。
4. 修复上机发现的问题后 P13-010，发布 0.10.0。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Office 的版面模型（流式段落、固定版式幻灯片）和 CSS（盒模型、flex、grid）不对应 | 某些页面达不到 0.90 | 按浏览器计算结果落位，不解释 CSS；达不到的输入写明原因，外观优先模式兜底 |
| WPS 和 LibreOffice 渲染差异 | CI 通过但 WPS 不达标 | 正式门槛只认 WPS；LibreOffice 只看回退 |
| 字体缺失或替换 | 版面相似度失真 | 固定字体，缺字体时标记不可比 |
| 转换依赖浏览器后变慢、环境要求变高 | 没有 Node/Playwright 的用户受影响 | 没有浏览器时退回语义转换，结果写明 |
| 往返时 Office 特有的属性（样式名、编号定义）在 HTML 里无处安放 | 往返丢信息 | 用 `data-` 属性保存，HTML 里不可见，转回时还原 |
