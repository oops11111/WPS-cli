# Changelog

All notable changes to `wps-ai-agent-cli`. The versioning rule and release steps are in `docs/RELEASING.md`.

## [Unreleased]

### Fixed

- `html-editable` (docx) lays text out as the browser does, which WPS did not: without `@page` the page is A4 (the browser's print size) instead of US Letter, and the document defaults turn off WPS's extra space between Chinese and Latin text, grid snapping, and the template's 10 pt after paragraphs. Before, WPS put two of the fixtures on one more page than the browser. Table cells no longer repeat their border and shading as paragraph borders, and list text is indented where the browser puts it. (P13-008)
- PDF to docx keeps each paragraph's measured space before and line pitch (exact line spacing), so WPS paginates it like the PDF. (P13-018)
- `convert` through WPS opens Writer documents without the conversion prompt (`.odt` timed out), and retries twice when WPS rejects a call while it is still busy (`RPC_E_CALL_REJECTED`). (P13-007)
- `fidelity-check` takes `layout_source` (render another file for the layout, as a legacy `.doc` itself) and `images_dir` (each page pair side by side); `scripts/fidelity_baselines.py --out` writes the full reports and the page images, and runs each group B case in its own folder.
- docx paragraphs set `snapToGrid` off themselves and the section has no document grid: WPS ignored the document default and put the browser's 16.5 pt lines on its 18 pt grid. Table cells are no wider than the browser's (2 px slack instead of 6) and tables are indented by their cell margin, so the left border lines up with the text as in the browser. (P13-008)
- PDF to docx places each block where the PDF has it (the space before and the line pitch counted from the page top), puts the gap above a table after the block before it, takes table row heights, cell padding and header weight from the PDF, and keeps regular-weight headings regular; 2-page PDFs no longer run onto a third page in WPS. (P13-018)
- `convert` through WPS also retries when WPS has not yet let go of the previous call's file (`DOCUMENT_HELD_OPEN`), and a timeout says what WPS was doing (opening the input or saving the output).
- `convert` results include `output_summary` (slide titles, headings, sheets), and the tool description says to write straight to the requested path and check with `check`, not to convert trial copies first.
- The `convert-legacy-doc-with-wps` evaluation task writes `legacy.docx` and `legacy.pdf`: its outputs had the names of fixtures the setup copies in, so `convert` refused them.

## [0.10.0] - 2026-10-18

Phase 13: high-fidelity conversion between all formats, measured by one check. The three milestones the plan describes (0.10.0, 0.11.0, 0.12.0) were built in one change, so 0.10.0 carries all of them; their Windows checks (P13-008, P13-013, P13-018) are still to run.

### Added

- `fidelity-check` (MCP `wps_agent_fidelity_check`) compares a converted file with its source and scores text, structure (headings, list levels, tables, images, slides), character formatting, animations (effect, kind and start time), table data (by value: `1.2e4` equals `12000`) and layout (SSIM per page, with WPS on Windows or LibreOffice; LibreOffice scores count only against a `--baseline`), against the Phase 13 thresholds for that kind of conversion. Aspects that do not apply are marked. (P13-001, P13-002)
- `convert` (MCP `wps_agent_convert`) picks the converter from the two file extensions; a pair without a direct route goes through one intermediate file, and the result lists the `route`. `--check` adds the fidelity report. (P13-017)
  - DOCX, PPTX and XLSX to clean HTML with inline styles (no class names); images as data URIs or in a `<name>_files` folder. Slides become fixed-size sections with absolutely placed shapes, `@keyframes` animations, `data-transition` and speaker notes; workbook formulas keep their displayed value and the formula in `data-formula`, which the way back restores. (P13-005, P13-009)
  - CSV/TSV to and from XLSX with the encoding (BOM, UTF-8, GBK/GB18030) and delimiter detected; numbers become numbers only when they display the same (`007` stays text, `3.50` gets `0.00`); a header row is bold and frozen. (P13-011)
  - Markdown to HTML, DOCX and PPTX (markdown-it-py with the `markdown` extra, else a built-in reader), and HTML, DOCX, PPTX and XLSX to Markdown with images in a `<name>_files` folder. (P13-011)
  - DOCX to PPTX (a slide per Heading 1 or 2, a continuation slide past eight lines), PPTX to DOCX (a heading per slide, notes kept) and a worksheet range (`--sheet`, `--range`) to a DOCX or PPTX table. (P13-012)
  - PDF to DOCX, XLSX and PPTX: headings by font size, lists, ruled tables and tables found from column alignment, pictures, running headers and footers (to the page header and footer in DOCX), page size and margins. A scanned PDF is refused with `PDF_NEEDS_OCR`; with `--ocr` and the `ocr` extra RapidOCR reads it. (P13-014, P13-015, P13-016)
  - Through WPS: .doc/.xls/.ppt, .wps/.et/.dps, .odt/.ods/.odp, .rtf and templates to and from docx/xlsx/pptx, PDF, and one PNG per page or slide; a pair WPS cannot write is refused with `FORMAT_NOT_SUPPORTED_BY_WPS` before WPS starts. (P13-007)
- `html-editable --fidelity appearance` (pptx): every element is placed where the browser lays it out, with backgrounds and the boxes behind the text; it needs the browser. (P13-006)
- Optional extras `fidelity` (numpy, Pillow, pypdfium2), `markdown` (markdown-it-py), `pdf` (pdfplumber) and `ocr` (RapidOCR); `html` now includes openpyxl.
- `fixtures/fidelity/` (Writer pages, decks, a GBK CSV and a UTF-8 TSV, Markdown, a PDF with a text layer and its scanned copy, and legacy and ODF copies), `scripts/fidelity_baselines.py`, which converts them all and checks the scores, and `config/fidelity_baselines.json` with the LibreOffice baselines. (P13-003)
- Agent evaluation: `convert-pdf-to-docx`, `convert-gbk-csv-to-xlsx`, `convert-markdown-to-docx`, `convert-docx-to-pptx` and `convert-legacy-doc-with-wps`, judged offline with the new `fidelity` check. (P13-017)

### Changed

- `html-editable` reads each element's computed style from the browser (Edge, or Chromium through `WPS_AGENT_EDGE`) and falls back to a built-in CSS cascade: fonts (East Asian too), sizes, colours, highlights, letter spacing, paragraph alignment, indents and spacing, borders, cell shading and padding, column widths, image sizes, `@page` size and margins, and page header and footer blocks. `<thead>` rows repeat as table headers; blockquotes keep the Quote style; `<hr>` becomes a rule; data-URI images are embedded; image alt text is kept. The result has `style_source` and `applied_styles`. (P13-004)
- `html-editable --format pptx` places each element where the browser lays out its section on a 16:9 slide, with section backgrounds, fonts and sizes; exit and emphasis animations, click and after-previous triggers are converted. Without the browser the slides use the title-and-content layout as before. (P13-006)
- `html-editable --format xlsx` sets fonts, fills, borders, alignment and column widths from the computed styles, freezes `<thead>` rows, shows decimals and dates as written, and restores `data-formula` formulas. (P13-010)

## [0.9.0] - 2026-10-17

Phase 12: a committed inventory of the public interface with stability rules, checks that run every evaluation task and test an installed package on a clean account, complex HTML conversion tasks, and a PyPI upload that is ready but off.

### Added

- The release workflow can upload the GitHub Release's wheel and sdist to PyPI with Trusted Publishing (the `pypi` job and environment, no stored token). The job runs only when the repository variable `PUBLISH_TO_PYPI` is `true`; PyPI publishing is skipped for now, so 0.9.0 is released on GitHub only. `docs/RELEASING.md` describes the one-time pending publisher setup and how to rerun the upload. (P12-004)
- `run_windows_check.py wheel --source pypi` downloads the version's wheel from PyPI with pip and checks its SHA-256 against the one the GitHub Release lists, so both places serve the same file. The result names its source. (P12-005)
- `config/public_interface.json`, generated from the code by `scripts/public_interface.py --write`: the CLI's global options, commands and their arguments, the MCP tools and their parameters, and the error codes. `tests/test_public_interface.py` fails when the code and the file differ and lists which changes are breaking. (P12-006)
- `run_windows_check.py --installed` runs the checks and the evaluation runner against the installed `wps-ai-agent-cli` instead of the repository's `src/`; `prereq` then requires the package to come from `site-packages`. Every `RESULTS.md` names the package version and path it tested. `docs/COMPATIBILITY_MATRIX.md` has a clean-environment section with the checks, steps for a new Windows account and a record format. (P12-007)
- Agent evaluation: three complex HTML inputs in `fixtures/html_complex/` (a Chinese business report, a budget with merged headers, formulas and mixed number formats, and an animated slide deck) and three tasks, `html-complex-report-to-docx`, `html-complex-budget-to-xlsx` and `html-complex-launch-to-pptx`, that convert each with `html-editable` and then to PDF through WPS. `docs/PHASE12_PLAN.md` lists what the conversions keep and lose. (P12-011)
- Agent evaluation: file-based tasks that need WPS record the WPS processes before the run and end the ones the commands left running, reported in the cleanup result. (P12-001)

### Changed

- `html-editable` keeps much more of a complex page (P12-013):
  - docx: images and captions in `<figure>`, table captions, `<details>`, bold, italic, underline, strike-through, sub- and superscript, code, highlight and inline-style colour; `rowspan` and `colspan` become merged cells; nested lists become second- and third-level list paragraphs; source whitespace is collapsed, except in `<pre>`.
  - xlsx: merged cells for `rowspan` and `colspan`; numbers with thousands separators, signs, percent, currency or exponents become numbers with a matching number format; ISO-like dates become dates; `<br>` becomes a line break in the cell; a cell's only link becomes a hyperlink; local images are placed below the table before them. The sheet result lists `merged_ranges` per sheet and the `images` placed.
  - pptx (now in `html_slides.py`): tables (with merged cells), local images and media, speaker notes from `<aside class="notes">`, inline formatting and list levels; CSS `@keyframes` animations become entrance effects (fly in, zoom or fade, after their `animation-delay`), and `data-transition` or a CSS `transition` on the section becomes the slide transition. The result has `mapped_objects`.
  - What is still not converted (scripts, SVG, hover effects, unavailable media, nested tables in a spreadsheet, formulas) is named in `warnings`; nothing is dropped silently.
- `docs/RELEASING.md` states the stability rules before and after 1.0 (what is breaking, how long a deprecation lasts, that new fields under `data` are not breaking) and a checklist for 1.0. (P12-006)

### Fixed

- `spreadsheet-read` (and every other command and MCP reply) no longer fails on date and time cells: they are written as ISO 8601 text. Before, reading a date column failed with `MCP_TOOL_EXECUTION_FAILED` (`Object of type datetime is not JSON serializable`). (P12-012)
- `html-editable --format xlsx` also replaces the full-width forms of the characters a sheet name cannot hold (`：？／＊［］＼`), which WPS replaced with `_` when it saved the workbook, so the sheet names stay the same after a save in WPS. The warning about formulas written as text now says to leave them as text unless the user asks for working formulas. (P12-012)
- `restore-backup` (and `wps_agent_restore_backup`) accepts `backup_name` and `backup_path` together when they name the same file, as `list-backups` returns them; when they name different files it refuses with `INVALID_ARGUMENT`. Before, argparse rejected the pair with `MCP_CLI_ARGUMENTS_REJECTED`: in the full evaluation (P12-002) every run of `restore-latest-backup` and `restore-dry-run` lost its first restore call to this, and two runs of `restore-latest-backup` went over its call limit. (P12-003)

## [0.8.0] - 2026-10-17

Phase 11: the selection fix 0.7.0 lacks, spreadsheet write results that show the cells around the write, and the undo of axis titles and series values checked on Windows.

### Added

- `spreadsheet-selection-replace` and `spreadsheet-selection-delete` on cells return `data.verified_state.surroundings`: the cells around the written range in the saved file (one row and column on each side, plus the header row of those columns when the range starts below row 2; at most 10 by 10, long values cut at 100 characters), as rows of values, with the cells outside the selection that changed (`changed_outside_selection`). When none did, the `check` sentence says so. In P10-006, five of the eight calls agents still made after a write were `spreadsheet_read` of exactly these cells. (P11-003)
- Agent evaluation: each run records, per write call, the `verified_state` its result carried (`source`, `passed`, `change_count`, `other_changes`, the `check` sentence and the surroundings range), and counts `unverified_writes`, the writes whose `passed` is not true. `run_windows_check.py eval`'s `RESULTS.md` gives the total and lists those writes under each run. (P11-004)
- `run_windows_check.py undo` has two more scenarios, `spreadsheet-axis-title-replace` and `spreadsheet-series-values-replace`. `chart_note.xlsx`'s chart now has a value axis title `DRAFT`, and its series reads `B2:B3`; the setup selects the axis title or the series by name. The text compared on disk includes the cell range each series reads, so an undo of series values that leaves literal values instead of the reference fails. (P11-006)

### Changed

- The MCP descriptions of `validate_document`, `snapshot_document` and `spreadsheet_read` say they are not needed to check an open-document write, whose result already holds `verified_state`. In P10-006 agents still called them after Writer inserts and deletes, and the write's own `check` sentence already named the paragraph they then searched for. (P11-005)

### Fixed

- `spreadsheet-selection-replace` and `spreadsheet-selection-delete` on a selected chart series were refused with `SELECTION_MISMATCH`. The write scripts found the chart by whether a member access raised; in WPS a series' parent is its chart group, which has no `ChartType` but does not raise, so the scripts named the selection after the chart itself (`Status Chart 1`) instead of its chart object (`Chart 1`, as the selection read reports) and refused it. They now check for values, as the selection read does. 0.7.0 has this defect. Found by the P11-007 Windows undo check. (P11-007)
- `spreadsheet-selection-read` read a selected chart title as the chart's series values (with empty text), so `spreadsheet-selection-replace` on it was refused with `SELECTION_MISMATCH`. A selected text box was read as series values too, and the shape-text write refused a text box as a chart element. The scripts told these objects apart by whether a member access raised, and WPS returns an empty value for a member an object does not have instead of raising. They now check for a value, which holds either way. 0.7.0 has this defect. Found by the P10-006 Windows undo check on `chart_note.xlsx`. (P10-006)

## [0.7.0] - 2026-10-16

Phase 10: open-document write results show what the saved file now holds, and failed writes to worksheet shapes and charts are undone in WPS.

### Added

- Open-document writes (`writer-selection-*`, `presentation-selection-*`, `spreadsheet-selection-replace`, `spreadsheet-selection-delete`, `save-open-document`, `save-as-open-document`, `export-open-document-text`) return `data.verified_state`. For an edit, the saved file is compared with the pre-write backup: Writer by paragraph, Presentation by text box per slide, Spreadsheets by cell with its sheet. `verified_state` lists what changed, from what to what (up to 20 changes), whether that matches the write (`passed`), and a `check` sentence that is also appended to the response `summary`. A save lists what the save wrote, a save-as reads the new file back, and a text export reads the exported text back. Formats without a reader (`.doc`, `.et`, …) report `source: wps_read_back`. The MCP descriptions of these tools say the result is already verified and no snapshot, validate, read or operation call is needed. In the P9-006 Windows run, 38 of the agents' 50 off-path calls came after the write, checking it. (P10-001, P10-002)
- Agent evaluation: each run splits `off_path_calls` into the calls before and after the first write that is not a dry run (`off_path_calls_before_write`, `off_path_calls_after_write`). The summary and `run_windows_check.py eval`'s `RESULTS.md` show the calls after the write per task and in total. (P10-003)
- `run_windows_check.py undo` has two more scenarios, `spreadsheet-shape-text-replace` and `spreadsheet-chart-title-replace`, on a workbook with a chart titled `DRAFT` and a text box holding `DRAFT` (`chart_note.xlsx`). The setup selects the text box or the chart title by name. (P10-005)

### Changed

- A failed `spreadsheet-selection-replace` or `spreadsheet-selection-delete` on a worksheet shape's text, a chart title, an axis title or a series' values is now undone in WPS, as cell writes have been since 0.4.0. The undo finds the object through the selection, as the write did, checks that it still holds what the write wrote or what WPS read back, puts the original back, reads it back and saves. A series gets its `SERIES` formula back, so a series that read its values from cells reads them again. Before, these writes returned `MUTATION_ROLLBACK_IN_WPS_FAILED` with "not available for this kind of selection". (P10-004)
- `spreadsheet-selection-read` no longer suggests reading the full values with `spreadsheet-read`: its 100-cell sample covers every selection the selection writes accept. (P10-001)

## [0.6.0] - 2026-10-16

Phase 9: agents are told which tool to use on a document open in WPS, the text export keeps every character, and Windows evaluation runs end WPS normally.

### Added

- Agent evaluation: for tasks whose document is open in WPS, each run counts `wrong_tool_calls`, the calls to file-based write tools that cannot change an open document. The summary and `run_windows_check.py eval`'s `RESULTS.md` show them per task and in total. (P9-002)
- Agent evaluation: the task `wps-open-zh-document-export-beyond-gbk` exports an open Writer document holding `✅` and `𠮷`, characters outside GBK, and checks they come back and the file is UTF-8 or UTF-16 (new check kind `text_encoding`). (P9-004)
- Agent evaluation: the runner lets the WPS it started exit normally (`Quit()`, or closing its main window when WPS cannot be reached, as a WPS opened by double-click with no document left cannot) and stops only what is still running after that. A WPS stopped with a document open reopened it on the next start, so every Windows run had to begin by closing those by hand. Each run's `cleanup` says `exited <ids> (Quit())`, `exited <ids> (main window closed)` or `stopped <ids> (still running after ...)`. (P9-005)

### Changed

- `export-open-document-text` (MCP `export_open_document_text`) writes Unicode for Writer and Spreadsheets, so characters outside the system code page survive. WPS 12.8 wrote the Writer export in the code page (GBK on Chinese Windows), where a character such as `✅` or `𠮷` is already `?` in the file. Writer now asks WPS for UTF-8 (`SaveAs2`'s encoding argument, `export_method` `SaveAsUtf8Text`). When the file WPS wrote is in the code page anyway, it is re-encoded to UTF-8 if every character of the document fits the code page (`+transcoded`), and otherwise rewritten as UTF-8 from the document's text read through WPS (`+document_text`; for Spreadsheets, the active sheet's cells). A file WPS wrote as UTF-16 or UTF-8 is kept. Exports that were in GBK before are now UTF-8 with a byte order mark. (P9-003)
- A file-based write (`writer-replace`, `writer-fill-bookmark`, `writer-table-write`, `presentation-replace`, `spreadsheet-write`, `spreadsheet-formula-write` and the sheet-structure commands) that refuses because the document is open in WPS now says what to use instead: `open_documents` to get the `document_id`, then the selection tools of that component (`*_selection_read`, `_replace`, `_insert`, `_delete`) and how the arguments carry over; for sheet structure, that there is no open-document tool and the workbook has to be saved and closed first. The MCP descriptions of these tools say they are not for documents open in WPS. In P8-008 an agent called `presentation_replace` on an open presentation and was not told which tool to use. (P9-001)

## [0.5.0] - 2026-10-16

Phase 8: Chinese content works end to end on Chinese Windows, and `restore-backup --close-in-wps` is verified on a workbook opened by double-click.

### Added

- Agent evaluation: four Chinese-content tasks (`wps-open-zh-*`) with Chinese fixtures (`季度报告.docx`, `状态表.xlsx` with a sheet `汇总`) and Chinese prompts: a Writer selection replaced with Chinese text, cells on a Chinese-named sheet, the text export of an open document with a Chinese file name, and an untitled document saved under a Chinese file name. `run_windows_check.py eval --prefix wps-open-` runs every open-document task in one command. (P8-004)
- `run_windows_check.py close-diag`: opens a new workbook in WPS the usual way and closes it once per method (eight methods, plus `Close()` and `Close($false)` under `/Automation` as the control group), and records each HRESULT, whether WPS still lists the workbook and whether it started a recovery instance. It also closes a workbook just written and saved by another process, and runs `restore-backup --close-in-wps` after such a write. (P8-005)
- Agent evaluation: right after a fixture opens in WPS, the runner records the documents WPS lists outside the task workspace, such as those WPS reopened from its previous session, in each run's `documents_outside`. They are left open. `run_windows_check.py eval` shows them per run and in a section of `RESULTS.md`. (P8-007)

### Changed

- `restore-backup --close-in-wps` (MCP `close_in_wps`): when WPS refuses to close the document and still lists it, the error is now `WPS_CLOSE_REFUSED`, with the reason WPS gave and what to do (close it in WPS, then restore without the flag), instead of the script's `COM_OPERATION_FAILED`. Nothing is restored, as before. WPS 12.8 refused to close a workbook opened by double-click in the P7-007 runs; Phase 8 did not reproduce that on Windows, where `restore-backup --close-in-wps` closed such a workbook after a write and restored it (P8-005). The close itself is unchanged. (P8-006)

### Fixed

- `export-open-document-text` (MCP `export_open_document_text`) rejected a correct export of Chinese text with `EXPORT_OUTPUT_NOT_TEXT` and removed it. WPS 12.8 wrote the file in the system code page (GBK on Chinese Windows); the check tried only UTF-8 and UTF-16, and GBK bytes such as `草` (`b2 dd`) read as an invalid UTF-16 surrogate. The check now also accepts GBK, still refuses packages, PDF and binary bytes, and reports the encoding in `data.text_encoding`. A refused output's first bytes are kept in `data.output_head_hex`. 0.4.1 and earlier have this defect. Found by the P8-008 Windows evaluation (`wps-open-zh-document-export-text`, 0/3).
- The Writer structure parity check ran its PowerShell script with `-File`, so its output (headings, which may be Chinese) was written in the console code page (GBK on Chinese Windows) and read back garbled. It now runs with the same UTF-8 output setting as every other script. (P8-003)
- The CLI wrote its error messages (stderr) in the system code page, so an argparse error about a Chinese argument reached the caller garbled. stderr is now UTF-8, like stdout and stdin. (P8-003)

## [0.4.1] - 2026-10-16

Fixes for Chinese Windows found by the Phase 7 Windows evaluation: arguments and output with characters outside ASCII are no longer garbled.

### Fixed

- `mcp-server` read the client's JSON-RPC requests in the system code page (GBK on Chinese Windows) instead of UTF-8, so every argument with characters outside ASCII reached the tools garbled: a Chinese document name, replacement text or path. An agent could not save the untitled document `文字文稿1`, which it named correctly. The CLI now reads stdin as UTF-8, as it already wrote stdout. 0.4.0 and earlier have this defect on Chinese Windows. Found by the P7-007 Windows evaluation; a test now runs the real `mcp-server` process with a GBK stdin.
- Text that WPS returns with characters outside ASCII came back garbled on Chinese Windows, for example the name of an untitled document (`文字文稿1`), so `save-as-open-document` could not be pointed at it. Windows PowerShell wrote the scripts' output in the console code page (GBK) and the CLI read it as UTF-8. Every PowerShell script and command now writes UTF-8. Found by the P7-007 Windows evaluation.
- `close_unchanged_document` (used by `restore-backup --close-in-wps`) reported `COM_OPERATION_FAILED` after closing a workbook on WPS 12.8, although the workbook was closed. When the close reports a failure, it now checks whether WPS still lists the document. Found by the P7-007 Windows evaluation.
- Closing an unchanged workbook (`restore-backup --close-in-wps` and the open-document commands' cleanup) failed on WPS 12.8 with `RPC_E_SERVERFAULT` when the workbook was reached through the Running Object Table, as for a workbook the user double-clicked. It now closes with no argument first, which cannot prompt because the workbook has no unsaved changes. This does not fix it: on the P7-007 Windows runs the close still failed, with `0x800A01A8`. Phase 8 (I2) works on it. Found by the P7-007 Windows evaluation.

## [0.4.0] - 2026-10-15

Phase 7: a failed write to a document open in WPS is undone inside WPS, and `validate-document` says what it needs.

### Added

- New error code `MUTATION_ROLLBACK_IN_WPS_FAILED`: the undo inside WPS did not happen or could not be confirmed. The message says what state the document is in and how to get back to the pre-write backup. The document is never closed, and it is not saved unless the undo read back as the original. Chart and shape selections in Spreadsheets are not undone this way and also return this code. (P7-001)

### Changed

- The eight open-document selection writes (Writer, Presentation and Spreadsheets selection replace, insert and delete) undo a failed write inside WPS. When WPS has saved the write but a later check rejects it, the command puts the original text or cells back in the same WPS instance with the inverse edit, reads them back, saves, and compares the saved file's content with the pre-write backup. It then returns `MUTATION_ROLLED_BACK` with `data.rollback.rolled_back_in_wps` set to `true`. Before, it tried to copy the backup over the file, which WPS holds, so these commands always ended in `MUTATION_ROLLBACK_BLOCKED` (seen in P6-008). The undo only changes the place the write changed, and only if that place still holds exactly what the write left there. (P7-001)
- `validate-document` (MCP `validate_document`) says what it needs. Agents kept calling it with only a `document_id`, as a general check, and got `INVALID_ARGUMENT` with `writer validation requires --contains.` (P6-008). The tool description now says it checks one expected value: `contains` for Writer, `cell` and `equals` for Spreadsheets. Each parameter says which component requires it, and the description says to use `snapshot_document` to read a document. The `INVALID_ARGUMENT` messages name the missing argument, give an example and point to `snapshot_document`. A cell that is not one A1 address, such as `Sheet1!B2`, is now `INVALID_ARGUMENT` instead of an unexpected error. `VALIDATION_FAILED` says what was compared: the text that was not found and that the match is exact, or the value the cell holds. (P7-006)

## [0.3.0] - 2026-10-15

Phase 6: the open-document commands work on documents the user opened in WPS the usual way, and their writes work on real WPS.

### Added

- Open-document commands (`open-documents`, selection read and edit, `save-open-document`, the exports, `restore-backup --close-in-wps`) reach a WPS that did not register its application object: when `GetActiveObject` finds nothing, they look for a document of the component in the Running Object Table and attach through its application, but only when it is WPS. Nothing is launched. The pre-open guard of the file-based write and conversion commands uses the same lookup, so it also sees a document open in such a WPS and refuses instead of opening it a second time. (P6-003)
- New error code `WPS_INSTANCE_NOT_AUTOMATABLE`. A WPS window of the component is running, but neither route reaches it, as with a WPS Writer opened by double-click on 12.8 (P5-011). The message gives the cause and the remedy: reopen the document with `wps.exe /Automation`. These commands answered `NO_RUNNING_WPS_INSTANCE` before. `open-documents` also reports such a component in `data.not_automatable` and `data.warnings` while listing the others. (P6-003)

### Fixed

- Open-document write commands (Writer, Presentation and Spreadsheets selection replace, insert and delete; `save-open-document`) always refused on real WPS with `DOCUMENT_HELD_OPEN`, in 0.2.0 too. Their backup began with the exclusive-share probe that file-based commands use. That probe always fails on a document that is open in WPS, which is what these commands work on. Their backup now only needs the file to be readable alongside WPS; WPS allows that. Found by the P6-008 Windows evaluation.
- `presentation-selection-replace` reported `VALIDATION_FAILED` on WPS 12.8 after a successful write. It read the new text back through the selection, which WPS moves after the assignment. It now checks the shape's whole text instead: the old text with exactly the selected part replaced. Found by the P6-008 Windows evaluation.

### Changed

- `writer-table-write`: a dry run also returns the table's `row_count`, `column_count` and `header_row`, so an agent can see the table in one call instead of probing cells. (P6-007)
- `writer-table-write`: the `CELL_NOT_FOUND` message gives the table's row and column counts, that rows and columns count from 1, and the header row, so an agent can correct the address in one step. (P6-007)

## [0.2.0] - 2026-10-14

First release. Phases 4 and 5 so far: in-CLI recovery for documents open in WPS, a WPS compatibility profile, an MCP failure contract for every tool, and a wheel that runs on its own.

### Added

- `restore-backup --close-in-wps` and the MCP `close_in_wps` argument: after a rollback blocked by an open document, close that document in WPS without saving and restore the backup, in one call. WPS must have no unsaved changes, otherwise the call refuses with `DOCUMENT_HAS_UNSAVED_CHANGES`. Without the flag nothing changes. (P4-009, P4-010)
- Agent evaluation: tasks can be marked `requires_wps` and are skipped without WPS; `--repeat N --min-passes M` runs each task N times; four WPS write tasks. (P4-004 to P4-006)
- Regression profile `compat`: open, save and PDF conversion for Spreadsheets and Presentation, part of the WPS compatibility matrix (`docs/COMPATIBILITY_MATRIX.md`). (P4-002)
- CI builds the wheel and the source distribution and keeps them as a workflow artifact. (P4-012)
- Pushing a tag `v<version>` publishes a GitHub Release with the wheel and the sdist, after checking the tag against the package version and running the safe regression profile from the built wheel. (P5-008)
- An installed wheel runs the safe regression profile on its own: the regression manifest, the MCP catalog guard and the MCP audit template ship inside the package and are used when the default `config/` paths do not exist. CI runs the safe profile from the installed wheel outside the repository. (P5-007)

### Changed

- The MCP `initialize` result reports the package version as `serverInfo.version`. It reported `phase2-prototype` before.
- The package version is defined only in `src/wps_ai_agent_cli/__init__.py`; `pyproject.toml` reads it from there.

### Fixed

- MCP `tools/call`: when a command fails, its error codes and messages (for example `DOCUMENT_HELD_OPEN`) are now in the tool result text and in `structuredContent.errors`. Before, both held an empty list and the codes were only in `structuredContent.mcp_call.response`, which agents do not read. Error details stay only in the nested response. Found by the P4-007 Windows evaluation.
- Commands without their own held-file check (for example `spreadsheet-read`, `spreadsheet-sheets`, `snapshot-document`, `batch-report`) raised `PermissionError` on a file held open by another handle, which MCP reported as `MCP_TOOL_EXECUTION_FAILED`. They now answer with a `DOCUMENT_HELD_OPEN` envelope. For commands that can change documents, the message points to `mutation-request-inspect` instead of saying nothing changed. Found by the P4-007 Windows evaluation.
- `batch-report` stopped at the first file held open by another handle. That file is now reported with `snapshot_status: "held"` and its `DOCUMENT_HELD_OPEN` error, the other files are reported as usual, and the summary counts it as `snapshot_held`. Validation still fails while any snapshot is missing. `snapshot-document` reports a held file as `DOCUMENT_HELD_OPEN` itself.
- `com-smoke` with pywin32 installed used a separate pywin32 branch that skipped the open and held-file checks; on real WPS it failed for presentations (`presentation-com-smoke`, P4-003). It now always runs the same PowerShell script as the other commands. pywin32 is still used to look up ProgIDs.
- MCP failure contract (P5-002, P5-003): a test now makes every one of the 85 tools fail and checks that the agent gets an error code. It found three problems, fixed here:
  - `wps-process-audit` raised when PowerShell could not be started (reported as `MCP_TOOL_EXECUTION_FAILED`); it now returns `WPS_PROCESS_AUDIT_FAILED`.
  - `MCP_CLI_ARGUMENTS_REJECTED` told the agent to read the server's stderr, which it cannot; the message now carries argparse's reason, for example that `restore_backup` needs `backup_name` or `backup_path`.
  - `writer-structure` reported a document held open by another handle as `WRITER_STRUCTURE_INVALID`; it now returns `DOCUMENT_HELD_OPEN`.

## [0.1.0]

Never tagged. This is the version the project carried through Phases 0 to 3, up to `main@ae8ea69` (Phase 4 activated). It covers the CLI and the stdio MCP server for WPS Writer, Spreadsheets and Presentation: document registry, backups and restore, idempotent request ids, atomic rollback of failed writes, open-document operations through COM, PDF and HTML conversion, and the regression runner. See `docs/ROADMAP.md` and the phase reports in `docs/` for the detail.
