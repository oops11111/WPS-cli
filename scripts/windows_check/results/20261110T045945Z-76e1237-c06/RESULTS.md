# C-06 Windows check: writer-insert-image, writer-page-setup, writer-style-apply

- Date: 2026-11-10 (UTC; local UTC+8)
- Branch: `c06-writer-tools`, commit `76e1237` ("writer-style-apply: report a held document as held")
- Machine: Windows 10 企业版 10.0.19045 build 19045; WPS Office 12.8.2.18913 (wps.exe 12,8,2,18913);
  Node v24.16.0; Microsoft Edge 157.0.4341.42. See `machine.txt`.
- Runner: the installed wps-agent 0.13.0 venv's Python
  (`%LOCALAPPDATA%\wps-agent\venv\Scripts\python.exe`), `PYTHONPATH=<worktree>\src`,
  `& $PY -m wps_ai_agent_cli ...`; working directory `work\`.
- Fonts found (`fonts.txt`, 15 families): 仿宋, 华文中宋, 华文仿宋, 华文宋体, 华文楷体, 华文细黑,
  华文行楷, 宋体, 微軟正黑體(Light), 微软雅黑(Light), 新宋体, 楷体, 黑体.
- No WPS process was running before the run (a WPS Presentation window that was open was closed per
  step 0) or after any command; those started by a step were closed and are noted below.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `c06-writer-tools` at `76e1237`; `work\通知.docx` made with WPS Writer: paragraphs 1/4/6 in Heading 1/2/3, seven text paragraphs, one 2×2 table, footer empty (only the paragraph mark); `图.png` is 800×500; document registered as `doc_8f1c3005de934f0a`. See `make-notice-log.txt`. |
| 1.1 | ok | dry-run: `after_paragraph` 3, 80×50 mm, caption 图 1 现场照片 (`img-dry-run.json`) |
| 1.2 | ok | real insert `i1`: 4/4 checks true (`img-i1.json`) |
| 1.3 | ok | `--after-text 工作目标` `i2`: inserted after paragraph 6, natural size 211.7×132.3 mm clamped to the 146.5 mm text width; 4/4 checks true (`img-i2.json`) |
| 1.4 | ok | `--at-end --width-mm 50` `i3`: 50 mm, 4/4 checks true (`img-i3.json`) |
| 1.5 | ok | opened in WPS: 3 pictures, each in its own centred paragraph (p4/p7/p18, alignment 1); first caption is centred 宋体 10.5 pt (五号) in p5 (`images.png`, `images-check.txt`) |
| 2.1 | ok | `p1`: A4 landscape, read-back 297×210 mm, top/bottom 20 mm, left/right 31.8 mm; `sections_match` true (`page-p1.json`) |
| 2.2 | ok | `p2`: portrait 210×297 mm, top 25.4 mm, left 31.8 mm; `sections_match` true (`page-p2.json`) |
| 2.3 | ok | `p3`: 16K 184×260 mm; `sections_match` true (`page-p3.json`) |
| 2.4 | ok (margins tab) | `page.png`: the 页面设置 dialog on the 页边距 tab shows 上 2.54 cm, 下 2 cm, 左/右 3.18 cm, 纵向. The 纸张 tab could not be switched by synthetic clicks (this dialog is owner-drawn, no `SysTabControl32` child); the 16K size is proven by `page-p3.json`, not by a dialog screenshot. Closed without saving. |
| 3.1 | ok | gongwen dry-run: roles title 1, heading1 1, heading2 1, heading3 1, body 4; needed fonts 仿宋_GB2312, 宋体, 方正小标宋简体, 楷体_GB2312, 黑体; missing 仿宋_GB2312, 方正小标宋简体, 楷体_GB2312 (`style-dry.json`) |
| 3.2a | ok (expected refusal) | without a font map: `FONT_NOT_INSTALLED`, exit 1, document SHA-256 unchanged (`style-refused.json`) |
| 3.2b | ok | with `--font-map 仿宋_GB2312=仿宋 --font-map 方正小标宋简体=宋体 --font-map 楷体_GB2312=楷体`, `g1`: 4/4 checks true (`style-gongwen.json`) |
| 3.3 | ok | `gongwen.png` and `gongwen-check.txt`: margins 37/35/28/26 mm; body 仿宋 16 pt (三号), fixed 28 pt, first-line indent 32 pt (2 chars); page number centred in the footer, 四号 (14 pt); 3 pages. |
| 3.4 | ok | `报告.docx` registered as `doc_b70c534e66f2a720`; `--preset report --request-id r1`: 4/4 checks true; `report.png`, `report-check.txt`: body 宋体 12 pt (小四), 1.5 line spacing, margins 25/25/28/26 mm, page number centred 五号 (10.5 pt); 2 pages |
| 3.5 | ok (expected refusal) | with `报告.docx` open in WPS: `DOCUMENT_HELD_OPEN`, exit 1, message says Open() was not called and nothing was written; WPS then closed (`style-held.json`) |
| 4 | ok | results committed on `cursor/c06-windows-76e1237` (not main, not c06-writer-tools) |

## How the two presets look in WPS

**Gongwen (`gongwen.png`, 50 % zoom shows all three pages with their page numbers)**

- Title 关于开展安全检查的通知: 宋体 22 pt (二号), centred (the preset's 方正小标宋简体 was mapped to 宋体
  because it is not installed).
- Heading 1 一、总体要求: 黑体 16 pt (三号), bold. Heading 2 （一）工作目标: 楷体 16 pt, bold.
  Heading 3 1. 具体任务: 仿宋 16 pt, bold.
- Body: 仿宋 16 pt (三号), fixed line spacing exactly 28 pt (`LineSpacingRule` 4), first-line indent 32 pt
  (2 characters at 16 pt), margins top 37 / bottom 35 / left 28 / right 26 mm — matches the checklist.
- Page numbers: footer PAGE field, centred, 14 pt (四号); pages 1, 2, 3 visible at the bottom of
  `gongwen.png`.
- Note: the doc is 3 pages after this preset (it was 2 before), because of the larger margins and 28 pt
  fixed spacing.
- The caption 图 1 现场照片 kept its centred alignment but was treated as body by the preset: it is now
  仿宋 16 pt with 28 pt fixed spacing and a 32 pt first-line indent, so it is no longer 宋体五号.

**Report (`report.png`, 50 % zoom)**

- Title: 黑体 22 pt (二号), centred.
- Heading 1: 黑体 16 pt bold; Heading 2: 黑体 14 pt bold; Heading 3: 宋体 12 pt bold.
- Body: 宋体 12 pt (小四), 1.5 line spacing (18 pt for 12 pt), first-line indent 24 pt (2 chars);
  margins top/bottom 25 mm, left 28 / right 26 mm.
- Page number: centred in the footer, 10.5 pt (五号); pages 1 and 2 visible in `report.png`.
- The caption is also body-styled (宋体 12 pt, 1.5 spacing, 24 pt indent), still centred.

The pictures keep their requested widths (80 mm, text width 146.5 mm, 50 mm), each alone in a centred
paragraph. The first picture's caption was 宋体五号 centred before the gongwen preset; see the note above
for its state afterwards. `images.png` shows the pre-preset state.

## Deviations and caveats

- `通知.docx` was produced by WPS Writer through its COM interface (`Documents.Add`, `Tables.Add`,
  `SaveAs`) rather than typed by hand in the UI; the file itself is a normal WPS-saved .docx with the
  requested paragraph/styles/table/footer structure. The footer was empty when created and is recorded as
  such.
- WPS opened its document window at 472×259 even though `WindowState` reported maximized; the screenshots
  were taken after `SetWindowPos` resized the OpusApp window to 1536×864. This is a window-state quirk of
  this session, not a document problem.
- The 页面设置 dialog has no standard tab child window, so the synthetic click could not switch to the 纸张
  tab; `page.png` shows margins and orientation, and the paper size is verified by the command's read-back
  (`page-p3.json`). `page-paper.png` is the same margins tab.
- COM `Font.NameFarEast` returned empty for fonts applied at run/style level in some paragraphs; the fonts
  listed above were confirmed with python-docx (`runs`/styles) as well as with `Font.NameFarEast` where it
  was populated.
- The gongwen dry-run exits 1 with `FONT_NOT_INSTALLED` by design (it reports the missing fonts); the
  non-dry refusal and the successful mapped run are separate files.
- A WPS Presentation window was open at the start and was closed per step 0.
