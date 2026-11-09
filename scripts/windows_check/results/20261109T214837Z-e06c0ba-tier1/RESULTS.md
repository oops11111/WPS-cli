# Tier 1 capability check on real WPS: charts, template merge, new documents, PDF

- Date: 2026-11-09 (UTC) / 2026-11-10 (local)
- Branch: `capability-tier1`, commit `e06c0ba`
- Machine: Windows 10.0.19045; WPS 12.8.2.18913; wps-agent 0.11.3 installed at
  `%LOCALAPPDATA%\wps-agent`; commands run with that venv's Python
  (`...\wps-agent\venv\Scripts\python.exe`, Python 3.12) and `PYTHONPATH=<repo>\src`
- All commands ran in `work\`; `pypdf` 7.0.0 installed into the venv for the PDF commands.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `inspect-env` ok; no WPS process before or after each step |
| 1.1 | ok | `document-new --component spreadsheets --path 销售.xlsx --title "Sales Q3"` → `doc_d8d84e33ba92fc52` |
| 1.2 | ok | `spreadsheet-write` A1:C4 wrote and read back the 4×3 table |
| 1.3 | **ok, all four** | column/bar/line/pie; each `ok: true`, all four `data.checks` true, `charts_after` 1, 2, 3, 4 |
| 1.4 | — | no failure, so no rollback/read-back diagnostics were needed |
| 1.5 | ok | `--range A1:A4 --chart-type column --dry-run` → `INVALID_RANGE` ("holds no numbers to chart") |
| 1.6 | ok | workbook copied to the result dir; opened in WPS at 40% zoom; four charts visible in `charts.png`; types/titles/series match (see below) |
| 2.1 | ok | `合同.docx` created in WPS Writer with the five placeholders, `{{客户}}` bold, header `{{客户}}`, footer `{{未提供}}` |
| 2.2 | ok | dry run lists 5 names; counts 合同编号 1, 客户 2 (document + header), 未提供 1, 联系人 1, 金额 1; `unfilled: ["未提供"]` |
| 2.3 | ok | merge `m1`: `ok: true`, `validation_passed: true`, `replaced: 5`, `readback_matches_expected: true`, `remaining_filled_placeholders: 0` |
| 2.4 | ok | `merge.png`: values filled, `甲公司` bold (Font.Bold = -1), header `甲公司`, footer still `{{未提供}}` |
| 2.5 | ok | with the document open in WPS, merge `m2` returned `DOCUMENT_HELD_OPEN` (exit 1) and wrote nothing; WPS then closed |
| 3.1 | ok | `周报.docx` opens with paragraph `第45周周报`; `汇报.pptx` opens with title `季度汇报`, slide 960×540 pt = 16:9 (ratio 1.7778); `new-docs.png` |
| 3.2 | ok | `convert 合同.docx 合同.pdf` (1 page A4, text layer); `pdf-info`; `pdf-watermark` (45°, 48 pt, opacity 15, text found); `pdf-merge` 2 pages; `pdf-split` 2 files |
| 3.3 | ok | `watermark.png`: watermark in the page centre, 45°, semi-transparent, Chinese `内部资料 草稿` renders correctly (not boxes) |

## Charts in WPS (step 1.6)

`charts-wps.txt` (read through WPS COM) and `charts.png` (WPS window at 40% zoom):

| # | Type added | WPS chart type | Title | Series read back |
| --- | --- | --- | --- | --- |
| 1 | column | 51 (xlColumnClustered) | 季度销售 | 华东 120/135/150, 华南 90/98/110 |
| 2 | bar | 57 (xlBarClustered) | 条形 | 华东 120/135/150, 华南 90/98/110 |
| 3 | line | 4 (xlLine) | 趋势 | 华东 120/135/150, 华南 90/98/110 |
| 4 | pie | 5 (xlPie) | 华东占比 | 华东 120/135/150 (three slices: 7月/8月/9月) |

In the screenshot all four charts are visible and look correct: two clustered
column series, horizontal bars, a two-line trend with markers, and a pie with
three slices; titles and legend entries are in Chinese and match the request.

## Deviations and notes

- The contract was created through WPS COM automation rather than typed by hand.
  The placeholders were inserted in pieces, but WPS saved each placeholder as a
  single part (`placeholder_parts` reports 1 part per location); the split-run
  case the prompt describes was therefore not reproduced.
- `new-docs.png` is two screenshots (Writer and Presentation) stacked vertically;
  the intermediate files are `_new-writer.png` and `_new-ppt.png`.
- `charts-wps.txt` and `contract-created.txt` were captured through the console in
  GBK and rewritten as UTF-8 for review.
- No WPS process was running at the start or left after any step.
