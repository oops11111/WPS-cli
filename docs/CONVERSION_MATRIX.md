# Phase 0 转换矩阵样例

## 已验证转换方向

| 方向 | 后端 | 输入 | 输出 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| DOCX 到 PDF | WPS Writer COM | `1-WPS_AI_Agent_CLI_PRD_v1.1.docx` | `fixtures/phase0/phase0_writer_export.pdf` | `ExportAsFixedFormat` | passed |

## DOCX 到 PDF 记录

### 前提条件

- Windows 桌面环境可用。
- WPS Writer COM ProgID `kwps.Application` 已注册。
- 输入文件可由 WPS Writer 打开。
- 目标路径可写。

### 保留能力

- 文本内容。
- 页面布局。
- 基础表格。
- WPS 支持范围内的图片和页面元素。

### 已知损失

- PDF 输出不可作为 WPS 原生文档继续编辑。
- 交互字段、目录域或其他动态字段可能被扁平化。
- 导出结果依赖本机 WPS PDF 导出能力和字体环境。

### 实测证据

- 输出文件: `fixtures/phase0/phase0_writer_export.pdf`
- 输出大小: 242418 bytes
- 页数: 5
- 首页渲染: `fixtures/phase0/pdf_render/phase0_writer_export_page1.png`
- 文本抽取: 首页可抽取到 `WPS AI Agent CLI` 和 PRD 文档内容。
- 2026-10-10：已打开 Writer 经 `export-open-document-pdf`（副本 `ExportAsFixedFormat`）写出 243541 字节 PDF，源文件仍打开且哈希未变。单机 WPS 12.0，不作跨版本结论。

## 待验证转换方向

| 方向 | 优先级 | 状态 | 说明 |
| --- | --- | --- | --- |
| XLSX 到 PDF | high | verified-local | 2026-10-09 本机 `convert-smoke --component spreadsheets` 对 disposable xlsx 走 `ExportAsFixedFormat`，输出 43219 字节 PDF。2026-10-10 已打开工作簿 `export-open-document-pdf` 写出 27913 字节 PDF，源未关闭、哈希未变。打印区域/隐藏表保真度未做矩阵 |
| PPTX 到 PDF | high | verified-local | 2026-10-09 本机对 WPS 可打开的 disposable pptx 走 `SaveAs` 32（`ExportAsFixedFormat` 失败后回退），输出非空 PDF。2026-10-10 已打开演示 `export-open-document-pdf` 走 `SaveCopyAsThenSaveAsPdf` 写出 21554 字节 PDF，源未关闭、哈希未变。残缺 OOXML 最小 pptx 可能卡住 WPS，勿用作夹具；动画/字体保真度未做矩阵 |
| DOCX 到 HTML | medium | verified-local | 已打开 Writer 文档可用 `export-open-document`（副本 `SaveAs2`/HTML）；2026-10-09 本机含只读打开验证。2026-10-10 P3-424：含标题/段落/表格标记的 disposable docx 写出 317844 字节 HTML（companion `.files`），四标记均保留，`source_unchanged`/`source_still_open`。与浏览器视觉优先 HTML→PDF 路径不同；布局/CSS/跨版本未做矩阵 |
| XLSX 到 HTML | medium | verified-local | 2026-10-09 本机已打开表格经 `export-open-document`（临时 `SaveCopyAs` + 副本 `SaveAs` HTML）写出非空 HTML。2026-10-10 P3-434：含 `P3-434-PLAIN` 与公式 `=10+5`（显示 15）的 disposable xlsx 写出 19565 字节 HTML，`source_unchanged`/`source_still_open`；去标签后纯文本标记保留，显示值 `15` 与 `x:fmla="=10+5"` 保留（WPS 可能把长文本拆成带 `display:none` 的片段）。图表/宏/跨版本未做矩阵 |
| PPTX 到 HTML | medium | verified-local | 2026-10-09 本机已打开演示经 `export-open-document` 的 `SaveCopyAs` HTML；动画保真度未做矩阵 |
| HTML 到 PDF | medium | verified-local | 2026-10-10 本机 `npm install`（`playwright`）后 `html-render` 对 `fixtures/phase3/html_visual_smoke.html` 写出 PDF 37867 字节（Edge 154.0.4258.62，`network_access=false`）与 PNG 32159 字节；`WPS_AGENT_RUN_BROWSER_INTEGRATION=1` 下 `tests.test_html_render` 4/4 通过。字体/复杂 CSS 保真度未做跨主机矩阵 |
| 已打开文档到 TXT | medium | verified-local | 2026-10-10 `export-open-document-text`：本机已打开 Writer 写出 10115 字节 txt，已打开表格写出 28 字节 txt，已打开演示 `ExtractShapeText` 写出 18 字节 txt（形状文本），源未关闭。跨版本未做矩阵 |

The PRD defines three HTML fidelity modes: visual-first rendering to PDF/image,
editable-first mapping to native objects, and controlled round-trip using an
owned HTML schema plus object IDs and mapping metadata. P3-114 and P3-115
provide the first two independent modes. Their contracts and fidelity differ;
P3-116 will prototype identity-preserving controlled round-trip.

## HTML visual-first (P3-114)

`html-render` uses headless Microsoft Edge through Playwright and writes a new
PDF or PNG without modifying the HTML source. Node.js, Playwright, and Edge are
runtime prerequisites. The Playwright package can be resolved through
`NODE_PATH`; configure non-standard executable locations with `WPS_AGENT_NODE`
and `WPS_AGENT_EDGE`.

The HTML file is limited to 10 MiB. Network and non-file protocols are blocked;
local resources must resolve inside the input directory tree, with a 20 MiB
per-resource and 100 MiB aggregate cap. JavaScript is off unless explicitly
enabled. Rendering is bounded by a 1-120 second timeout and 20,000-pixel
document height. PDF uses a selected paper size and print CSS; PNG uses the
configured browser viewport and full-page capture. Existing output paths are
never overwritten. Browser rendering provides CSS fidelity supported by the
installed Edge build; unsupported CSS, unavailable fonts, and host-dependent
font rasterization can still differ. These outputs are visual artifacts, not
editable WPS documents.

```powershell
python -m wps_ai_agent_cli html-render --input .\page.html --output .\page.pdf --format pdf --page-size A4
python -m wps_ai_agent_cli html-render --input .\page.html --output .\page.png --format png --viewport-width 1440 --viewport-height 1000
```

## HTML editable-first (P3-115)

`html-editable` maps semantic headings, paragraphs, lists, tables, hyperlinks,
and bounded local images to editable WordprocessingML in a new DOCX. Links are
real DOCX hyperlinks, not fetched during conversion. Images must resolve inside
the source directory after symlink resolution; remote images, scripts, and
unsupported embedded content are omitted with warnings. Input is limited to 10
MiB, images to 20 MiB each/50 MiB total and 100 images. CSS layout is not
preserved: inline styles, classes, embedded/linked stylesheets are reported in
`unsupported_css`. The output is structurally editable; no visual-equivalence
claim is made. Install the optional converter with `pip install .[html]`.

```powershell
python -m wps_ai_agent_cli html-editable --input .\page.html --output .\page.docx
```

`--format` chooses the Office output. `docx` (default) is the Writer mapping
above. `xlsx` maps each `<table>` to a worksheet, named by the nearest preceding
heading (later tables with no heading of their own keep the same name, with a
number added). Numbers become numeric cells, but text with leading zeros stays
text. Cells that start with `=` are written as text, not formulas, and reported
as a warning. `pptx` maps each `<section>`, and each `<h1>` or `<h2>`, to a
slide: the heading is the title, and paragraphs and list items are the body.
Tables and images are reported as not converted. The xlsx and pptx converters
run offline and do not use WPS. Their output has been opened in WPS on one
machine: the xlsx in WPS Spreadsheets and the pptx in WPS Presentation, and
both exported back to HTML with their sheet name, cell text, slide titles and
bodies kept (`scripts/real_wps_verify_remaining/RESULTS-4898428.md`, section
4). No visual-fidelity or cross-version matrix has been run.

```powershell
python -m wps_ai_agent_cli html-editable --input .\page.html --output .\page.xlsx --format xlsx
python -m wps_ai_agent_cli html-editable --input .\deck.html --output .\deck.pptx --format pptx
```

## HTML controlled round-trip identity prototype (P3-116)

Owned HTML v1 marks the root with `data-wps-schema="wps-agent-html/v1"` and
every mapped semantic object with a unique `data-wps-object-id`. The
read-only `html-roundtrip-plan` validates IDs and unsupported features and
returns deterministic object type/index, nearest mapped parent, text digest,
and bookmark mappings. P3-117 `html-controlled-import` persists IDs as DOCX
bookmarks with a `.wpsmap.json` sidecar. `html-roundtrip-verify` allows text
edits while rejecting missing, duplicate, unmapped, or same-type reordered
bookmarks. P3-118 exports verified DOCX content to owned HTML v1, preserving
stable IDs and rejecting unsupported or unmapped WordprocessingML.

```powershell
python -m wps_ai_agent_cli html-roundtrip-plan --input .\owned-page.html
python -m wps_ai_agent_cli html-controlled-import --input .\owned-page.html --output .\controlled.docx
python -m wps_ai_agent_cli html-roundtrip-verify --docx .\controlled.docx --mapping .\controlled.docx.wpsmap.json
```
