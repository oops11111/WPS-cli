# C-05 Windows check: spreadsheet-sort, spreadsheet-conditional-format, spreadsheet-data-validation

- Date: 2026-11-09 23:43–23:57 UTC / 2026-11-10 local (UTC+8)
- Branch: `c05-sheet-tools`, commit `fd1d64a` ("C-05: spreadsheet sort, conditional formatting and data validation")
- Machine: Windows 10 企业版 10.0.19045; WPS Office 12.8.2.18913 (et.exe 12,8,2,18913)
- Runner: the installed wps-agent 0.12.0 venv's Python
  (`%LOCALAPPDATA%\wps-agent\venv\Scripts\python.exe`), with
  `PYTHONPATH=<worktree>\src`, invoked as `& $PY -m wps_ai_agent_cli ...`
- Working directory: `work\`; workbook `work\数据.xlsx`, document id `doc_6b91b86a6440bcbf`
- No WPS process was running before the run, after any command, or after step 4.

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | Branch `c05-sheet-tools` at `fd1d64a`; workbook created and `A1:D7` written (after the recovery described below); `write.json` ok |
| 1.1 | ok | `--key B:desc --key C:asc`: B column 150,135,120,90,90,60; the two 90s in date order (华南 45931 before 华北 45933); `order_check` = `strict`; all checks true (`sort-s1.json`, `sort-s1-readback.json`) |
| 1.2 | ok | `--key 地区:asc`: `order_check` = `text keys: grouping only`; WPS order 东北, 华北, 华东, 华南, 西北, 西南 (pinyin order); checks all true (`sort-s2.json`, `sort-s2-readback.json`) |
| 1.3 | ok | Formula in F1 written, then sort of `A1:F7` refused with `SORT_RANGE_HAS_FORMULAS` (exit 1); SHA-256 of the workbook identical before and after (`sort-formula-refused.json`) |
| 1.4 | ok | `spreadsheet-read A1:D7` saved as `after-sort.json`; matches the step 1.2 order |
| 2.1 | ok | B2:B7 cell-value > 100: `one_rule_added`, `rule_matches` true (`cf-f1.json`) |
| 2.2 | ok | B2:B7 between 80 and 120 with `#C6EFCE`/`#006100`: checks true (`cf-f2.json`) |
| 2.3 | ok | D2:D7 equal 完成 (text): checks true (`cf-f3.json`) |
| 2.4 | ok | C2:C7 color-scale: checks true (`cf-f4.json`) |
| 2.5 | ok | B2:B7 data-bar: checks true (`cf-f5.json`) |
| 2.6 | ok | A2:A7 duplicates: checks true (`cf-f6.json`) |
| 2.7 | ok | B2:B7 data-bar `--replace`: `one_rule_on_range` and `rule_matches` true; `data.read_back.rules_on_range` has exactly 1 entry (dataBar) (`cf-f7.json`) |
| 3.1 | ok | D2:D7 list 完成/进行中/未开始 + input/error messages: all four checks true (`dv-v1.json`) |
| 3.2 | ok | E2:E7 whole between 1 and 100: checks true (`dv-v2.json`) |
| 3.3 | ok | C2:C7 date >= 2025-01-01: checks true (`dv-v3.json`) |
| 3.4 | ok | G2:G7 text-length <= 10, no blanks: checks true (`dv-v4.json`) |
| 3.5 | ok | H1:H3 written 甲/乙/丙, then I2:I7 list `=$H$1:$H$3`: checks true (`dv-v5.json`, `write-h1h3.json`) |
| 4.1 | ok | Workbook copied to `数据.xlsx` and opened in WPS 表格; `sheet.png` shows the sorted values, data bars, colour scale, 完成 highlights and the formula result |
| 4.2 | ok | D2 selected: dropdown arrow and the input message 请选择状态 are visible in `dropdown.png` |
| 4.3 | ok | Typing 200 in E2 was refused: WPS showed 错误提示 / 您输入的内容，不符合限制条件。 (`reject.png`); the edit was cancelled and the workbook closed without saving (`step4-log.txt`) |
| 5 | ok | Results committed on `cursor/c05-windows-fd1d64a` (not main, not c05-sheet-tools) |

## Step 0 details and the write recovery

The first `spreadsheet-write` of `A1:D7` (exit 1) timed out after 120 seconds in the COM backend:

```
COM_OPERATION_TIMEOUT: WPS operation timed out after 120 seconds; the document may still be open in WPS and its state is unknown.
MUTATION_ROLLED_BACK: the document file was restored from the pre-write backup and its hash matches it.
```

The full JSON is `write-attempt1.json`. The rollback restored the file from the backup, which changed the
file identity, so the next attempt failed immediately with `DOCUMENT_IDENTITY_CHANGED` (`write-attempt2.json`).
`register-document` re-registered the unchanged file (`register.json`), after which the same write succeeded
(`write.json`, all three checks true). A retry script of mine once passed an empty `--document-id`
(`write-attempt3.json`, argparse exit 2); that was my scripting error, not a product result.

A standalone COM probe then opened the same workbook in about 1 second, so the timeout was not reproducible;
no WPS process survived the timed-out attempt or any later command.

## Step 2 notes

From `cf-f5.json` to `cf-f7.json` the CLI's own openpyxl read-back printed these warnings to stderr (merged
into the saved files before the JSON):

```
UserWarning: Unknown extension is not supported and will be removed
UserWarning: Conditional Formatting extension is not supported and will be removed
```

They are openpyxl warnings about WPS's conditional-formatting extension; the commands still returned
`ok: true` and the rules are visible in WPS (`sheet.png`), so nothing was actually lost.

## Step 4 details: what WPS showed

- `sheet.png` / `sheet-crop.png`: 地区 sorted 东北, 华北, 华东, 华南, 西北, 西南; B column has proportional
  data bars (60 no bar … 150 full); C column shows the green→red colour scale with 45934 (max) green and
  45929 (min) red; D column highlights all three 完成 cells in pink and leaves 未开始/进行中 plain; A column
  has no highlight (no duplicates); F1 shows 2 from `=1+1`.
- `dropdown.png`: D2 is selected (name box `D2`), the list arrow is shown, and the input message
  请选择状态 appears next to the cell. The list itself was not expanded for the shot; the arrow and input
  message are visible.
- `reject.png`: E2 is in edit mode with 200 typed; WPS shows 错误提示 / 您输入的内容，不符合限制条件。
  The edit was then cancelled with ESC and the workbook closed with `Close($false)`; nothing was saved.

## Deviations and caveats

- `spreadsheet-formula-write` in this branch requires `--expected-values-json`; the step's command omitted it.
  I passed `[[2]]` for `=1+1`. The command's help (`--help`) shows the required argument.
- The JSON arguments were passed as PowerShell variables to the venv's `python.exe` directly. The `--%` form
  with a trailing `>` redirection sends the redirection to the CLI as literal arguments (it failed that way
  once), so it was not used. Quotes reached the CLI intact (evidenced by the successful dry-run and write).
- CLI commands were run from PowerShell 7.6.9; the UI script in step 4 was run with Windows PowerShell 5.1
  (System.Drawing needs explicit `-ReferencedAssemblies`).
- The first write timeout and its rollback are an observed environmental failure, recorded above; the retry
  used the same command once the document was re-registered.
