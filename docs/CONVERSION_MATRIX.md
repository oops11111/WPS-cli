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

## 待验证转换方向

| 方向 | 优先级 | 状态 | 说明 |
| --- | --- | --- | --- |
| XLSX 到 PDF | high | pending | 需要记录公式结果、分页和工作表选择行为 |
| PPTX 到 PDF | high | pending | 需要记录幻灯片尺寸、字体和图片保真度 |
| DOCX 到 HTML | medium | pending | 需要区分 WPS SaveAs HTML 和浏览器视觉优先模式 |
| HTML 到 PDF | medium | pending | 属于 HTML 视觉优先基线，需要单独样例 |

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
