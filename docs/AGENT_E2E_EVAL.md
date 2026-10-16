# Agent end-to-end evaluation

This pipeline runs fixed tasks through the real `claude -p` CLI with the `wps-agent` MCP server attached. It judges each task from the workspace state and from the tool calls in the CLI transcript, not from the agent's reply. It is the Phase 3 "真实 Agent 端到端评测" item in `docs/ROADMAP.md`.

## What it covers

Tasks are in `config/agent_eval_tasks.json`. Each task runs in its own workspace, which is also the MCP server's working directory. The default fixture is `book.xlsx`, with `seed` in A1. A task can name its own `fixture` and `component`: `report.docx` (Writer) holds the paragraphs `Quarterly report`, `Status: DRAFT` and `Owner: Finance`, `deck.pptx` (Presentation) holds one slide with `Quarterly review` and `Status: DRAFT`, and `table_report.docx` (Writer) holds the paragraph `Regional status` and one table with the rows `Region, Q1, Status`, `North, 120, DRAFT` and `South, 95, DRAFT`. `status.xlsx` (Spreadsheets) holds the same rows in A1:C3 of a sheet named `Status`, with the Q1 values as numbers. Two Chinese fixtures, for the Chinese-content tasks (P8-004), have Chinese file names and the same layout: `季度报告.docx` (Writer) holds `季度报告`, `状态：草稿` and `负责人：财务部`, and `状态表.xlsx` (Spreadsheets) holds the rows `地区, 一季度, 状态`, `华北, 120, 草稿` and `华南, 95, 草稿` on a sheet named `汇总`. Their prompts are in Chinese too.

A task can list `setup` steps that prepare the workspace before the agent starts:

| Step | Effect |
| --- | --- |
| `register` | registers `book.xlsx` |
| `backup` | backs it up with request id `setup-backup` |
| `modify` | changes A1 to `changed by mistake` and saves the file |
| `html_table` | writes `table.html` with a two-column table |
| `hold` | holds the fixture the way WPS holds an open document. Must be the last step. |
| `open_in_wps` | opens the fixture in WPS on Windows and waits until WPS lists it as open (up to 45 s). It runs the open command registered for the extension (for example `wps.exe "%1"`), the command a double-click runs, rather than going through the shell, which on some machines shows the "Open with" chooser instead. `--wps-launch automation` adds `/Automation` to that command. Neither changes the system's open command. When the agent left the fixture with unsaved changes, the runner closes it without saving: it is the runner's own file. It records the WPS processes (`wps`, `et`, `wpp`) that appeared while opening. After the agent, the runner closes the document without saving, and only when WPS reports no unsaved changes; then, when it started a process, it ends every process of the component (`wps`, `et` or `wpp`), but only while WPS lists no other document for the component, so that the next `--repeat` run starts from the same state. It repeats this up to three times, because WPS can start a process in place of a stopped one: in P7-007 stopping `et.exe` made WPS start `et.exe recover1`, which reopened the workbook without registering for automation. Ending every process of the component is safe only because the Windows check's prerequisites require that no WPS process runs when a check starts; run the runner directly only on a machine with no WPS document of your own open. Only `select_text`, `append_unsaved` and `untitled_document` may follow it; the task must be marked (WPS). Elsewhere the task is skipped. |
| `select_text` | after `open_in_wps`: selects the first occurrence of the task's `selection.text` in WPS (Writer or Presentation), or, with `"collapse": "end"`, puts the caret right after it (Writer and Presentation). In Spreadsheets it selects the cells `selection.range` (for example `C2:C3`) on the sheet `selection.sheet`, or on the first sheet, through COM (`Range.Select()`). It reads the selection back (the text, or the cell address and sheet); when WPS selected something else, the run is a setup failure, not an agent failure. |
| `append_unsaved` | after `open_in_wps`: appends the task's `unsaved_text` as a new paragraph in WPS (Writer) without saving, and checks that WPS reports the document as unsaved. |
| `untitled_document` | after `open_in_wps`: makes a new document of the task's component in the same WPS, never saved, holding the task's `untitled_text` (default `Draft notes`): the body text in Writer, A1 in Spreadsheets, a text box on a blank slide in Presentation. WPS names it itself (for example `文字文稿2`), so the prompt writes `{untitled_name}` and the runner puts the name in before the agent starts; the run records it as `untitled_name`. After the agent, the runner closes that document without saving if it is still untitled, and closes any other document WPS lists inside the task workspace (the file it was saved as), before it releases the fixture. |

| Task | Asks the agent to | Judged by |
| --- | --- | --- |
| `register-and-backup` | register the file, then back it up with a fixed request id | document registered; operation `eval-backup-1` recorded as `backup-document`; one backup; file unchanged |
| `list-backups-readonly` | register the file and list backups without changing anything | document registered; no backups; file unchanged |
| `restore-missing-backup` | restore from a backup that does not exist | document registered; no operation recorded for `eval-restore-1`; file unchanged |
| `idempotent-backup-retry` | back up, then resend the same call with the same request id | operation recorded; at least two `backup_document` calls with that request id; still one backup; file unchanged |
| `restore-latest-backup` | restore a file that was changed after its backup | operation `eval-restore-2` recorded as `restore-backup`; file matches the seed again; at most 6 `wps-agent` calls |
| `restore-dry-run` | preview a restore without changing the file | a `restore_backup` call with `dry_run: true`; file unchanged; still one backup (a real restore adds a safety backup) |
| `held-document-backup` | back up a file that another handle holds | `DOCUMENT_HELD_OPEN` seen in a tool result; no operation recorded; no backup; no `restore_backup` call; file unchanged |
| `html-table-to-xlsx` | convert `table.html` into `table.xlsx` | an `html_editable` call with `format: "xlsx"`; `table.xlsx` has `Region` in A1 and `120` in B2; `book.xlsx` unchanged |
| `wps-spreadsheet-write` (WPS) | write 42 into B2 of `book.xlsx` | operation `eval-write-1` recorded as `spreadsheet-write`; a `spreadsheet_write` call with that request id; B2 is 42 and A1 still `seed`; one backup (taken before the write) |
| `wps-writer-replace` (WPS) | replace DRAFT with FINAL in `report.docx` | operation `eval-writer-1` recorded as `writer-replace`; a `writer_replace` call; the text has `Status: FINAL` and the other two paragraphs, and no `DRAFT`; one backup |
| `wps-presentation-replace` (WPS) | replace DRAFT with FINAL in `deck.pptx` | operation `eval-presentation-1` recorded as `presentation-replace`; a `presentation_replace` call; the text has `Quarterly review` and `Status: FINAL`, and no `DRAFT`; one backup |
| `wps-held-spreadsheet-write` (WPS) | write into a held `book.xlsx` | `DOCUMENT_HELD_OPEN` seen; no operation recorded; no backup; no `restore_backup` call; file unchanged |
| `spreadsheet-sheets-and-read` | list the sheets of `book.xlsx` and read A1 | document registered; `spreadsheet_sheets` and `spreadsheet_read` calls; no backup; file unchanged |
| `html-table-to-docx` | convert `table.html` into `table.docx` | an `html_editable` call; `table.docx` has every cell of the table; `book.xlsx` unchanged |
| `wps-spreadsheet-rename-sheet` (WPS) | rename the sheet `Sheet` to `Summary` | operation `eval-rename-1` recorded as `spreadsheet-rename-sheet`; a `spreadsheet_rename_sheet` call; the only sheet is `Summary`; A1 still `seed`; one backup |
| `wps-spreadsheet-create-sheet` (WPS) | add a sheet `Q4` after the existing one | operation `eval-create-1` recorded as `spreadsheet-create-sheet`; a `spreadsheet_create_sheet` call; the sheets are `Sheet`, `Q4` in that order; A1 of `Sheet` still `seed`; one backup |
| `wps-writer-table-write` (WPS) | set the Status of the North row to FINAL in `table_report.docx` | operation `eval-table-1` recorded as `writer-table-write`; a `writer_table_write` call; that cell is `FINAL`, the South row and the header unchanged; one backup |
| `wps-docx-to-pdf` (WPS) | convert `report.docx` to `report.pdf` | a `convert_smoke` call with `format: "pdf"`; `report.pdf` starts with `%PDF-` and has at least 1000 bytes; `report.docx` unchanged |
| `wps-open-document-export-text` (WPS) | find `report.docx`, opened in WPS by the `open_in_wps` step, and export its text to `report.txt` | `open_documents` and `export_open_document_text` calls; `report.txt` has the three paragraphs; no `save_open_document` call; `report.docx` unchanged |
| `wps-open-writer-selection-replace` (WPS) | replace the selected word DRAFT in the open `report.docx` with FINAL | operation `eval-selection-1` recorded as `writer-selection-replace`; a `writer_selection_replace` call; the saved file has `Status: FINAL` and the other two paragraphs, and no `DRAFT`; one backup; no `writer_replace` call |
| `wps-open-writer-selection-insert` (WPS) | insert ` (reviewed)` at the caret, which is at the end of `Owner: Finance` | operation `eval-insert-1` recorded as `writer-selection-insert`; a `writer_selection_insert` call; the saved file has `Owner: Finance (reviewed)` and the other two paragraphs; one backup |
| `wps-open-presentation-selection-replace` (WPS) | replace the selected word DRAFT on the open slide with FINAL | operation `eval-slide-selection-1` recorded as `presentation-selection-replace`; a `presentation_selection_replace` call; the saved file has `Quarterly review` and `Status: FINAL`, and no `DRAFT`; one backup; no `presentation_replace` call |
| `wps-open-save-document` (WPS) | save the open `report.docx`, which has an unsaved paragraph `Reviewed in WPS` added by `append_unsaved` | operation `eval-save-1` recorded as `save-open-document`; a `save_open_document` call; the file now has `Reviewed in WPS` and the original paragraphs; one backup (taken before the save); no `save_as_open_document` call |
| `wps-open-writer-selection-delete` (WPS) | delete the selected word DRAFT in the open `report.docx` | operation `eval-delete-1` recorded as `writer-selection-delete`; a `writer_selection_delete` call; the saved file has `Status: ` and the other two paragraphs, and no `DRAFT`; one backup; no `writer_replace` call |
| `wps-open-presentation-selection-insert` (WPS) | insert ` (v2)` at the caret, which is at the end of `Status: DRAFT` on the open slide | operation `eval-slide-insert-1` recorded as `presentation-selection-insert`; a `presentation_selection_insert` call; the saved file has `Quarterly review` and `Status: DRAFT (v2)`; one backup; no `presentation_replace` call |
| `wps-open-presentation-selection-delete` (WPS) | delete the selected word DRAFT on the open slide | operation `eval-slide-delete-1` recorded as `presentation-selection-delete`; a `presentation_selection_delete` call; the saved file has `Quarterly review` and `Status: `, and no `DRAFT`; one backup; no `presentation_replace` call |
| `wps-open-spreadsheet-selection-replace` (WPS) | set the selected cells C2:C3 of the open `status.xlsx` (sheet `Status`) to FINAL | operation `eval-cells-1` recorded as `spreadsheet-selection-replace`; a `spreadsheet_selection_replace` call; C2 and C3 are `FINAL`, B2 is still 120 and C1 still `Status`; one backup; no `spreadsheet_write` call |
| `wps-open-spreadsheet-selection-delete` (WPS) | clear the selected cell C3 of the open `status.xlsx` | operation `eval-clear-1` recorded as `spreadsheet-selection-delete`; a `spreadsheet_selection_delete` call; C3 is empty, C2 still `DRAFT` and B3 still 95; one backup; no `spreadsheet_write` call |
| `wps-open-save-as-untitled` (WPS) | save the untitled Writer document that `untitled_document` made (its name is in the prompt) as `notes.docx` | operation `eval-save-as-1` recorded as `save-as-open-document`; a `save_as_open_document` call; `notes.docx` has `Meeting notes: budget approved`; `report.docx`, also open, unchanged; no `save_open_document` call |
| `wps-open-zh-writer-selection-replace` (WPS) | replace the selected `草稿` in the open `季度报告.docx` with `定稿` | operation `eval-zh-selection-1` recorded as `writer-selection-replace`; a `writer_selection_replace` call; the file has `季度报告`, `状态：定稿` and `负责人：财务部` and no `草稿`; one backup; no `writer_replace` call |
| `wps-open-zh-spreadsheet-sheet-cells` (WPS) | set the selected cells C2:C3 of the open `状态表.xlsx` (sheet `汇总`) to `已完成` | operation `eval-zh-cells-1` recorded as `spreadsheet-selection-replace`; a `spreadsheet_selection_replace` call; C2 and C3 on `汇总` are `已完成`, B2 still 120 and C1 still `状态`; one backup; no `spreadsheet_write` call |
| `wps-open-zh-document-export-text` (WPS) | export the text of the open `季度报告.docx` to `季度报告.txt` | `open_documents` and `export_open_document_text` calls; `季度报告.txt` (Unicode text, or GBK when WPS falls back to plain text) has the three paragraphs; no `save_open_document` call; the document unchanged |
| `wps-open-zh-save-as-untitled` (WPS) | save an untitled Writer document holding `会议纪要：预算已批准` as `会议纪要.docx` | operation `eval-zh-save-as-1` recorded as `save-as-open-document`; a `save_as_open_document` call; `会议纪要.docx` has the text; `季度报告.docx`, also open, unchanged; no `save_open_document` call |

The ten tasks without (WPS) use only offline tools and run on any machine with the `claude` CLI logged in. The (WPS) tasks need WPS on Windows. The first four were run in P4-007 (results below). The five added in P5-005 were run on Windows in P5-006 (results below); all five passed 3/3. The four added in P6-006, which write to a document open in WPS, were run on Windows in P6-008 (results below). The four `wps-open-zh-*` tasks added in P8-004 put Chinese text through each path it takes: written text, a sheet name, the file name of an open document and the name WPS gives an untitled document; `run_windows_check.py eval --prefix wps-open-` runs them with the other open-document tasks.

`held-document-backup` needs a machine that can hold the file. On Windows the runner opens it with no sharing. On other systems it removes all permissions, which does not work for root. When the file cannot be held, the task is reported as skipped, not as passed or failed.

## Check kinds

State checks: `document_registered`, `operation_recorded`, `no_operation`, `backup_count`, `file_unchanged` (the file as the agent received it, after setup), `file_matches_seed` (the file before setup), `xlsx_cell` (the first sheet, or the one named by `sheet`), `xlsx_sheets` (the exact sheet names, in order), `docx_table_cell` (the text of one cell, 1-based table, row and column), `pdf_file` (a file that starts with `%PDF-`, with an optional `min_bytes`), `file_text` (text that a `.docx`, `.pptx` or `.txt` must contain, and text it must not; a `.txt` from WPS is read as UTF-16 when it has a byte order mark, otherwise as UTF-8).

Each task also lists `expected_tools`: the `wps-agent` tools a correct run needs, without the `wps_agent_` prefix. The runner counts calls to any other `wps-agent` tool as off-path calls and reports them for each run (`off_path_calls`, `off_path_tools`), for each repeated task and in the summary. Off-path calls are reported only; a task passes or fails on its checks. The task-file test requires every task to list its expected tools, and every `tool_called` check to name one of them.

Transcript checks, read from the tool calls, not from the reply: `tool_called` (optionally with `input` values and a `min` count), `tool_not_called`, `tool_error_seen` (an error code in a tool result), `max_tool_calls` (calls to `wps-agent` tools only).

## How to run

```bash
python scripts/agent_eval/run_agent_eval.py --out artifacts/agent-eval
python scripts/agent_eval/run_agent_eval.py --only register-and-backup --model <model-id>
python scripts/agent_eval/run_agent_eval.py --repeat 3 --min-passes 2
```

The runner needs `claude` on `PATH`. It runs the CLI with `--output-format stream-json --verbose` so that it can read each tool call. It exits with 0 when every task that ran passes, 1 when any fails, and 2 when the CLI is missing. Skipped tasks do not change the exit code. A run where the CLI itself failed, for example with an API error, is marked `agent_error`; it still counts as a failed run.

`--repeat N` runs each task N times, each in its own workspace under `run-<n>/`. A task passes when at least `--min-passes` runs pass; by default every run must pass. The summary records each run, the number of passes and the pass rate. Phase 4 judges WPS write tasks with `--repeat 3 --min-passes 2`.

A task with `"requires_wps": true` runs only when this machine has a registered WPS ProgID for the task's component, found with the project's own capability probe. Otherwise it is reported as skipped with the reason. A skip on the first attempt ends the task, because it does not depend on the run. When setup fails only on a later attempt (for example `open_in_wps` timing out after an earlier run passed), that attempt counts as a failed run with `setup_failed` and the reason, and the earlier runs are kept.

Each run writes `summary.json` under `<out>/run-<timestamp>/`. For each task it holds the agent's turns, duration, cost, reply excerpt, every tool call with its input and error codes, the tool metrics and every check result. The summary also totals `wps-agent` calls and calls that returned an error.

The tool metrics count every call that returned an error code. Some of those errors are the expected outcome: in `restore-missing-backup` and `held-document-backup`, the refusal is what the task tests.

The offline tests in `tests/test_agent_eval.py` cover the transcript parser, the setup steps, the judge for every task and the MCP config with a stand-in agent. They do not call the CLI.

## Results

Run 2026-10-13 with `claude` 2.1.296 (CLI default model), on a Linux container as root, on this repository's `main` at `42cc54f` plus this change:

| Task | Result | Turns | `wps-agent` calls | Tool errors | Duration | Cost (USD) |
| --- | --- | --- | --- | --- | --- | --- |
| `register-and-backup` | pass | 4 | 2 | 0 | 9.7 s | 0.070 |
| `list-backups-readonly` | pass | 4 | 2 | 0 | 8.6 s | 0.066 |
| `restore-missing-backup` | pass | 4 | 2 | 1 (expected refusal) | 11.3 s | 0.068 |
| `idempotent-backup-retry` | pass | 5 | 3 | 0 | 13.3 s | 0.078 |
| `restore-latest-backup` | pass | 4 | 2 | 0 | 10.7 s | 0.071 |
| `restore-dry-run` | pass | 4 | 2 | 0 | 11.7 s | 0.071 |
| `held-document-backup` | skipped | | | | | |
| `html-table-to-xlsx` | pass | 4 | 1 | 0 | 9.1 s | 0.069 |

7 of 7 tasks that ran passed. Total: 14 `wps-agent` calls, 1 error (the expected one), about USD 0.49.

`held-document-backup` was skipped because the run was as root. It still needs a run on Windows or as a non-root user.

### P4-007 Windows WPS write tasks (2026-10-14)

Outcome: all four tasks pass, 3/3 each; the held-file task passes on the second rerun below. P4-007 is done.

Commit `4999b77` on `p4-007-wps-eval-runs`. Windows 10.0.19045. Claude Code CLI 2.1.295, model left as the CLI default (no `--model`). Command: `--repeat 3 --min-passes 2` for `wps-spreadsheet-write`, `wps-writer-replace`, `wps-presentation-replace`, and `wps-held-spreadsheet-write`. Artifact: `%TEMP%\wps-p4\eval-wps\run-20261014T070755399357Z\summary.json`. None skipped. **3 of 4 tasks passed.** The pass bar is at least 2 of 3 runs.

| Task | Passes | Mean turns | `wps-agent` calls | Tool errors |
| --- | --- | --- | --- | --- |
| `wps-spreadsheet-write` | 3/3 | 4.7 (4, 4, 6) | 11 | 0 |
| `wps-writer-replace` | 3/3 | 4.3 (5, 3, 5) | 10 | 0 |
| `wps-presentation-replace` | 3/3 | 4.0 (4, 4, 4) | 9 | 0 |
| `wps-held-spreadsheet-write` | 0/3 | 18.3 (16, 16, 23) | 33 | 16 |

Each passing run recorded the expected command (`spreadsheet-write`, `writer-replace`, or `presentation-replace`), kept one backup, and matched the expected cell or text. Spreadsheet A1 read back `42` and the untouched cell stayed `seed`.

`wps-held-spreadsheet-write` failed the same check on all three runs: `tool_error_seen` did not find `DOCUMENT_HELD_OPEN`. The other checks passed (no operation, no backup, `restore_backup` not called, file unchanged). `spreadsheet_write` was marked `is_error` true, but the parsed tool result had an empty `error_codes` list, so the judge did not see the code. Later calls in those runs included `MCP_TOOL_EXECUTION_FAILED` and `MCP_ADAPTER_CALL_REJECTED`, not `DOCUMENT_HELD_OPEN`.

### P4-007 rerun of `wps-held-spreadsheet-write` (2026-10-14)

Same branch, still `3d9c831` (`git pull` was already up to date). Claude Code CLI 2.1.295, CLI default model. `--repeat 3 --min-passes 2`. Artifact: `%TEMP%\wps-p4\eval-held-rerun\run-20261014T131756639971Z\summary.json`.

**0/3, not passed.** Turns 16, 16, 16. `wps-agent` calls 34, tool errors 15. No skip.

Each run failed only `tool_error_seen` (`DOCUMENT_HELD_OPEN` not seen). `no_operation`, `backup_count` 0, `restore_backup` not called, and `file_unchanged` passed. `spreadsheet_write` was `is_error` true with an empty `error_codes` list. Codes that did appear: run 1 `MCP_ADAPTER_CALL_REJECTED` (`mcp_call`) and `MCP_TOOL_EXECUTION_FAILED` (`spreadsheet_read`, `spreadsheet_sheets`); run 2 `MCP_TOOL_EXECUTION_FAILED` (`spreadsheet_read`); run 3 `MCP_TOOL_EXECUTION_FAILED` (`spreadsheet_sheets`, `spreadsheet_read`).

### P4-007 second rerun of `wps-held-spreadsheet-write` (2026-10-14)

This is the run that counts for P4-007. `6484151` includes PRs #55 (failed tool calls report their error codes to the agent) and #56 (read commands on a held file answer `DOCUMENT_HELD_OPEN`). The first rerun above was still on code without either fix.

After `git pull` to `6484151`. Claude Code CLI 2.1.295, CLI default model. `--repeat 3 --min-passes 2`. Artifact: `%TEMP%\wps-p4\eval-held-rerun2\run-20261014T133257997329Z\summary.json`.

**3/3, passed.** Turns 5, 4, 3 (mean 4.0). `wps-agent` calls 9, tool errors 6 (each a `DOCUMENT_HELD_OPEN` refusal, which is what the task tests). No skip.

Every run saw `DOCUMENT_HELD_OPEN` on `spreadsheet_write` (run 1 also on `spreadsheet_sheets` and `spreadsheet_read`). `no_operation`, `backup_count` 0, `restore_backup` not called, and `file_unchanged` all passed.

### P5-006 Windows runs of the Phase 5 tasks (2026-10-15)

Branch `docs/p5-windows-runbook` at `bcdbc1d` (the runbook commit on `main` `f2ed99e`). Windows 10.0.19045. WPS Writer, Spreadsheets and Presentation file version 12.8.2.18913. Claude Code CLI 2.1.295, CLI default model. No `--model`.

The seven-task command was:

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-spreadsheet-rename-sheet --only wps-spreadsheet-create-sheet `
  --only wps-writer-table-write --only wps-docx-to-pdf --only wps-open-document-export-text `
  --only spreadsheet-sheets-and-read --only html-table-to-docx `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p5\eval
```

Artifact: `%TEMP%\wps-p5\eval\run-20261014T232138695884Z\summary.json`. Six tasks passed there. `wps-open-document-export-text` was skipped, so it is not one of those runs.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `spreadsheet-sheets-and-read` | 3/3 | 4.0 (4, 4, 4) | 9 | 0 | 0 | |
| `html-table-to-docx` | 3/3 | 11.0 (8, 13, 12) | 20 | 0 | 17 | `register_document`, `snapshot_document`, `validate_document`, `writer_structure`, `writer_table_write` |
| `wps-spreadsheet-rename-sheet` | 3/3 | 5.0 (5, 3, 7) | 12 | 0 | 3 | `spreadsheet_read` |
| `wps-spreadsheet-create-sheet` | 3/3 | 5.3 (5, 5, 6) | 13 | 0 | 1 | `spreadsheet_read` |
| `wps-writer-table-write` | 3/3 | 15.3 (15, 16, 15) | 41 | 2 | 1 | `operation` |
| `wps-docx-to-pdf` | 3/3 | 9.0 (16, 7, 4) | 7 | 0 | 4 | `inspect_env`, `register_document`, `snapshot_document` |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | |

`spreadsheet_read` after a rename or a new sheet was a read of the workbook. On `html-table-to-docx` the extra tools registered the new docx, validated it, read its structure, took a snapshot, and wrote table cells in addition to `html_editable`. On `wps-docx-to-pdf` the extra tools probed the environment, registered the docx and took a snapshot before `convert_smoke`. On `wps-writer-table-write` run 2 called `operation` once. Run 1 of that task called `writer_table_write` twice and got `CELL_NOT_FOUND` both times; a later call passed the checks. The other two runs had no tool error.

`wps-open-document-export-text` did not pass inside the command above. `.docx` is `Word.Document.12`, and that open command is `wps.exe "%1"`. `os.startfile` did open `report.docx` in WPS 文字, but that process does not register `kwps.Application`, so `open-documents` reported no running Writer within 45 s. Launching the same file as `wps.exe /Automation "%1"` does register, and the document is listed. For the rerun, the current user's open command was set to that form, then removed. The stock `wps.exe "%1"` command is back.

One `--repeat 3` with that open command still skipped. The first run's Writer stayed registered after the document was closed, the second `startfile` started another `wps.exe`, and `GetActiveObject` kept the first process, which did not have the new file. The runner treats that skip as the whole task and drops the earlier run. The three runs that count were therefore separate `--repeat 1 --min-passes 1` invocations, with that test Writer closed between them:

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-open-document-export-text --repeat 1 --min-passes 1 --out $env:TEMP\wps-p5\eval-open-1
python scripts/agent_eval/run_agent_eval.py --only wps-open-document-export-text --repeat 1 --min-passes 1 --out $env:TEMP\wps-p5\eval-open-2
python scripts/agent_eval/run_agent_eval.py --only wps-open-document-export-text --repeat 1 --min-passes 1 --out $env:TEMP\wps-p5\eval-open-3
```

Artifacts: `%TEMP%\wps-p5\eval-open-1\run-20261014T233956946366Z\summary.json`, `%TEMP%\wps-p5\eval-open-2\run-20261014T234027391555Z\summary.json`, `%TEMP%\wps-p5\eval-open-3\run-20261014T234056048453Z\summary.json`. Each run was 4 turns, 2 `wps-agent` calls (`open_documents`, `export_open_document_text`), 0 tool errors, 0 off-path calls. `report.txt` had the three paragraphs, `save_open_document` was not called, and `report.docx` was unchanged. No `report.docx` window was left open.

**Accepted with an exception (2026-10-15).** P5-006 counts these three runs: the task passes 3/3, so F2 is met. The exception is how they were run: the current user's `.docx` open command was changed to `wps.exe /Automation "%1"` for the runs and then restored, and each run was its own invocation. A run that skipped after an earlier one had passed no longer drops the earlier run: the runner now records it as a failed run with `setup_failed`.

What this found about the product is in Limits below: the open-document tools cannot see a Writer that the user opened normally on this machine.

### P6-008 Windows runs of the open-document tasks (2026-10-15)

`main` at `655d76c`. Windows 10.0.19045. WPS 12.8.2.18913. Claude Code CLI 2.1.295, CLI default model. No `--model`. The runner was started with `claude` resolved to `claude.CMD` and UTF-8 stdout, because a bare `claude` launch and the console code page fail on this machine. The system open command was not changed.

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-open
```

Artifact: `%TEMP%\wps-p6\eval-open\run-20261015T013214070478Z\summary.json`. This is the default launch (`--wps-launch default`). G2 is judged on this command. It is not met: three tasks are 0/3 and one was skipped. The skip is `NO_RUNNING_WPS_INSTANCE`, not `WPS_INSTANCE_NOT_AUTOMATABLE`, so it was not rerun with `--wps-launch automation`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.3 (5, 4, 4) | 7 | 0 | 0 | |
| `wps-open-writer-selection-replace` | 0/3 | 16, 16, 16 | 46 | 10 | 30 | `backup_document`, `inspect_env`, `list_backups`, `mcp_call`, `mcp_tool_schema`, `mcp_tools`, `operation`, `operations`, `regression_manifest`, `save_open_document`, `scan_dir`, `snapshot_document`, `task_recovery_playbooks`, `wps_process_audit`, `writer_structure` |
| `wps-open-writer-selection-insert` | 0/3 | 16, 16, 16 | 41 | 12 | 24 | `backup_document`, `export_open_document_text`, `inspect_env`, `list_backups`, `mcp_tool_schema`, `mutation_request_inspect`, `operation`, `operations`, `save_open_document`, `security_audit`, `snapshot_document`, `task_recovery_playbooks`, `tasks`, `wps_process_audit`, `writer_selection_replace`, `writer_structure` |
| `wps-open-presentation-selection-replace` | skipped | | | | | |
| `wps-open-save-document` | 0/3 | 16, 16, 16 | 32 | 10 | 19 | `backup_document`, `list_backups`, `mcp_tool_schema`, `mcp_tools`, `operation`, `operations`, `snapshot_document`, `task_recovery_playbooks`, `wps_process_audit` |

`wps-open-document-export-text` passed all three runs. Each run called `open_documents` and `export_open_document_text`, wrote the three paragraphs to `report.txt`, did not call `save_open_document`, and left `report.docx` unchanged.

`wps-open-writer-selection-replace` failed the same checks on all three runs: `operation_recorded` (no record), `file_text` (`Status: FINAL` missing, `DRAFT` still present), `backup_count` 0. `tool_called` for `writer_selection_replace` passed. The `wps-agent` errors were `DOCUMENT_HELD_OPEN` on `writer_selection_replace` (every run; request id `eval-selection-1`, text `FINAL`, expected selection `DRAFT`) and on `backup_document`. Run 1 also had `MCP_TOOL_SCHEMA_NOT_FOUND` for `writer_selection_replace`. Run 2 also had `OPERATION_NOT_FOUND` and `MCP_ADAPTER_CALL_REJECTED` on `mcp_call` for `writer-selection-replace`. The other errors were shell and file-lock probes, not `wps-agent` calls.

`wps-open-writer-selection-insert` failed the same way on all three runs: no operation, `Owner: Finance (reviewed)` missing, `backup_count` 0. `writer_selection_insert` returned `DOCUMENT_HELD_OPEN` (request id `eval-insert-1`, text ` (reviewed)`). Each run also had `OPERATION_NOT_FOUND`. Runs 1 and 2 then called `writer_selection_replace` and got `SELECTION_EMPTY`. Run 3 also got `DOCUMENT_HELD_OPEN` from `backup_document` and `SELECTION_EMPTY` from `writer_selection_replace`.

`wps-open-presentation-selection-replace` was skipped on the first run: `WPS did not list deck.pptx as open within 45 s (launch mode default): NO_RUNNING_WPS_INSTANCE: No running WPS instance was found for the probed components; nothing was launched.` Opening a `.pptx` with the shell on this machine starts `OpenWith.exe -Embedding` and does not start `wpp.exe` (see `RESULTS-655d76c.md`). That is not (b).

`wps-open-save-document` failed all three runs: no operation, `Reviewed in WPS` missing, `backup_count` 0. `save_open_document` with request id `eval-save-1` returned `DOCUMENT_HELD_OPEN` (runs 2 and 3 twice). Each run also had `OPERATION_NOT_FOUND`. Runs 2 and 3 also got `DOCUMENT_HELD_OPEN` from a dry-run `backup_document`.

After the command, one Writer was still open: pid 2608, title `report.docx * - WPS 文字`, command line the run-1 export fixture. It was ended before the table comparison. No `et.exe` or `wpp.exe` was left.

**Review (2026-10-15).** The run is recorded above as it happened. Findings:

- **Every write failed for one product reason, not because of the agent.** The open-document write commands (selection replace, insert and delete; `save_open_document`) take a backup first. Since `6e941d7` (2026-10-12) the backup has started with an exclusive-share probe (`FileShare.None`). A document these commands work on is open in WPS by definition, so the probe always failed with `DOCUMENT_HELD_OPEN`. The bug was released in 0.2.0. It went unnoticed because no real-WPS run had covered these commands before this one. The probe protects file-based commands from calling `Open()` on a document the user has open; open-document commands never do that. Their backup now skips the probe and only needs the file to be readable alongside WPS. P6-004 shows WPS allows that: registering the open documents read and hashed them.
- **The Presentation skip came from the runner.** It opened the file through the shell, which on this machine shows the "Open with" chooser for `.pptx` and `.xlsx`. The runner now runs the registered open command directly, the command a double-click runs. It also starts `claude.CMD` by its full path and reads the transcript as UTF-8, which this run had to work around.
- The off-path calls (`backup_document`, `wps_process_audit`, `mcp_call`, ...) are the agent trying to get past `DOCUMENT_HELD_OPEN`. They are not a tool-choice problem.
- G2 is not met yet. It is judged on a rerun with these fixes.

### P6-007 comparison: `wps-writer-table-write`

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-writer-table-write --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-table
```

Artifact: `%TEMP%\wps-p6\eval-table\run-20261015T015418345259Z\summary.json`. Same CLI and model as above.

**2/3, passed the 2-of-3 bar.** Turns 16.0 (16, 20, 12). `wps-agent` calls 31, tool errors 2, `off_path_calls` 7 (`mcp_tools`, `operation`, `snapshot_document`). P5-006 on the same task was 3/3, mean 15.3 turns (15, 16, 15), 41 calls, 2 tool errors.

Run 1 failed: `operation_recorded` no record, `tool_called` 0 (the only `writer_table_write` was `dry_run: true`, row 2 column 3, text `FINAL`, and `is_error` was false), North status still `DRAFT`, `backup_count` 0. No `CELL_NOT_FOUND`.

Run 2 passed after probing cells. Two dry-run `writer_table_write` calls returned `CELL_NOT_FOUND`: row 4 column 1, and row 5 column 1, both `dry_run: true`, text `x`. The summary stores the code only, not the error message. The real write (request id `eval-table-1`, row 2 column 3, `FINAL`) passed, with one backup.

Run 3 passed. One off-path `operation` call. No tool error.

No `wps.exe` was left after this command.

**Review (2026-10-15).** The `CELL_NOT_FOUND` calls were deliberate dry-run probes of rows 4 and 5. The agent was looking for the edge of the table, because no tool reported the table's size. So the cause of the P5-006 out-of-range calls is the same. The P6-007 message only helps after the agent goes out of range. `writer_table_write`'s dry run now also returns `row_count`, `column_count` and `header_row`, and the tool description says so, so one dry run shows the whole table. Run 1's failure (it stopped after the dry run) is a separate issue. The comparison is rerun together with P6-008.

### P6-008 rerun on 174f04e (2026-10-15)

`main` at `174f04e` (the open-document write fix and the runner launching the registered open command). Windows 10.0.19045. WPS 12.8.2.18913. Claude Code CLI 2.1.295, CLI default model. No `--model`. The system open command was not changed. G2 is judged on this default-launch command. It is not met.

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-open-174f04e
```

Artifact: `%TEMP%\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\summary.json`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | |
| `wps-open-writer-selection-replace` | 3/3 | 5.3 (5, 6, 5) | 12 | 0 | 0 | |
| `wps-open-writer-selection-insert` | 2/3 | 7.3 (13, 7, 2) | 15 | 1 | 3 | `export_open_document_text`, `validate_document` |
| `wps-open-presentation-selection-replace` | skipped | | | | | |
| `wps-open-save-document` | 0/3 | 1, 1, 1 | 0 | 0 | 0 | |

`wps-open-document-export-text` and `wps-open-writer-selection-replace` passed every run. Replace recorded `writer-selection-replace`, left `Status: FINAL`, and kept one backup.

`wps-open-writer-selection-insert` passed runs 1 and 2. Run 1 also called `export_open_document_text` (`INVALID_ARGUMENT`; output `…\wps-p6-eval-scratch-insert1\report_before.txt`) and `validate_document` with `contains` `Owner: Finance (reviewed)`. Run 2 called `validate_document` the same way. Run 3 made one `open_documents` call (`register: true`, not an error) and then stopped. The reply was `API Error: 402 Insufficient Balance (request_id: 78d2c758-80e6-40e3-8cd3-3ae58091a4e3)`. Failed checks: `operation_recorded` no record, `tool_called` 0 for `writer_selection_insert`, `Owner: Finance (reviewed)` missing, `backup_count` 0.

`wps-open-presentation-selection-replace` was skipped on the first run, before the agent. The reason is not `WPS_INSTANCE_NOT_AUTOMATABLE`, so the command was not repeated with `--wps-launch automation`:

`select_text: script_failed [{'code': 'COM_OPERATION_FAILED', 'message': 'OperationStopped: …\tmpu189mt4l.ps1:206 | $hit = $shape.TextFrame.TextRange.Find([string]$params.text) | Unexpected HRESULT has been returned from a call to a COM component.'}]`

`wps-open-save-document` did not reach a tool call. Each run is one turn and the reply is `API Error: 402 Insufficient Balance`, request ids `b5368d85-48a7-4118-ba2d-5328356343d5`, `7ad472de-4869-4d73-a356-e912f35faf82`, `453ed9a7-5f1e-434b-a9f4-bef2a0350b04`. Failed checks on every run: no operation, `tool_called` 0, `Reviewed in WPS` missing, `backup_count` 0. `tool_not_called` for `save_as_open_document` passed.

After the command, Writer pid 46568 was still open, title `report.docx * - WPS 文字`, command line the run-2 export fixture. It was ended before the table comparison. No `et.exe` or `wpp.exe` was left.

**Review (2026-10-15).**

- **The write fix works.** Writer selection replace passed 3/3 at 5.3 turns with no off-path calls. Before the fix it was 0/3 at 16 turns. Selection insert passed runs 1 and 2. Its run 3 never reached the tools: the Claude API answered `402 Insufficient Balance`.
- **The save task and the P6-007 table rerun below were not evaluated.** Every run is one turn with the same 402 and no tool call. The judge failed them, but they say nothing about the tools. The runner now marks such a run with `agent_error` and prints it, so they stand out.
- **The presentation skip came from the runner's own setup.** `TextRange.Find` fails on WPS 12.8 with an unexpected HRESULT. `select_text` now finds the text in PowerShell and selects it with `TextRange.Characters(start, length)`.
- **The Writer left open was the runner's own fixture.** It had unsaved changes from a run that stopped early, and the runner only closed unchanged documents. It now closes its own fixture without saving in that case, then ends the WPS process it started.
- G2 is still open. The five tasks are rerun in one command once the API balance is restored.

### P6-007 rerun on 174f04e

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-writer-table-write --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-table-174f04e
```

Artifact: `%TEMP%\wps-p6\eval-table-174f04e\run-20261015T022924523541Z\summary.json`.

**0/3.** Turns 1, 1, 1. `wps-agent` calls 0, tool errors 0, off-path calls 0. No `CELL_NOT_FOUND`. Each reply is `API Error: 402 Insufficient Balance`, request ids `5dea3130-a0db-4117-a8c7-44f163620706`, `c3444403-7c54-4184-9f26-cb5efb5681f1`, `721cc47d-ec76-43c4-b4cc-194b6aea0df7`. Failed checks: no operation, `tool_called` 0, North status still `DRAFT`, `backup_count` 0. The South status and the header checks passed. No `wps.exe` was left. This run does not replace the P5-006 comparison (3/3, mean 15.3 turns, 41 calls); the agent never called a tool.

### P6-008 rerun on 98d8dcd (2026-10-15)

`main` at `98d8dcd`. Windows 10.0.19045. WPS 12.8.2.18913. Claude Code CLI 2.1.295, CLI default model. `claude -p "hi"` succeeded before the run. No `--model`. The system open command was not changed. G2 is judged on this default-launch command. It is not met: presentation is 0/3. The task was not skipped, and the code was not `WPS_INSTANCE_NOT_AUTOMATABLE`, so it was not rerun with `--wps-launch automation`.

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-open
```

Artifact: `%TEMP%\wps-p6\eval-open\run-20261015T024523453952Z\summary.json`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | |
| `wps-open-writer-selection-replace` | 3/3 | 5.7 (5, 6, 6) | 14 | 0 | 0 | |
| `wps-open-writer-selection-insert` | 3/3 | 13.7 (16, 9, 16) | 24 | 2 | 9 | `export_open_document_text`, `operation`, `validate_document` |
| `wps-open-presentation-selection-replace` | 0/3 | 16.3 (16, 16, 17) | 37 | 8 | 16 | `export_open_document_text`, `inspect_env`, `mcp_tools`, `mutation_request_inspect`, `operation`, `operations`, `presentation_replace`, `snapshot_document`, `wps_process_audit`, `writer_selection_read` |
| `wps-open-save-document` | 3/3 | 9.0 (6, 10, 11) | 16 | 1 | 4 | `operation`, `validate_document`, `writer_structure` |

Export, selection replace, selection insert, and save passed at least 2/3. Insert run 3 called `export_open_document_text` and got `INVALID_ARGUMENT` (output outside the workspace) and `validate_document` with `contains` `Finance  (reviewed)` and got `VALIDATION_FAILED`; the required insert still passed. Save run 3 called `validate_document` with only a `document_id` and got `INVALID_ARGUMENT`.

`wps-open-presentation-selection-replace` failed every run. The summary stores error codes, not the message text.

- Run 1: `operation_recorded` no record. `file_text`, `backup_count` 1, and `tool_not_called` passed. `presentation_selection_replace` with request id `eval-slide-selection-1`, text `FINAL`, expected `DRAFT`, returned `VALIDATION_FAILED` and `MUTATION_ROLLBACK_BLOCKED`. A dry run with request id `eval-slide-selection-1-dryrun` was not an error. `operation` then returned `OPERATION_NOT_FOUND`.
- Run 2: no operation, `Status: FINAL` missing and `DRAFT` still present, `backup_count` 0, `tool_not_called` saw 1 `presentation_replace` call. The dry-run `presentation_selection_replace` (request id `eval-slide-selection-1`) returned `SELECTION_SPANS_STRUCTURE`. The dry-run `presentation_replace` (`find` `DRAFT`, `replace` `FINAL`) returned `DOCUMENT_HELD_OPEN`.
- Run 3: no operation, and `tool_not_called` saw 1 `presentation_replace` call. `file_text` and `backup_count` 1 passed. `presentation_selection_replace` with request id `eval-slide-selection-1` returned `VALIDATION_FAILED` and `MUTATION_ROLLBACK_BLOCKED`. A dry-run `presentation_replace` returned `DOCUMENT_HELD_OPEN`. `writer_selection_read` returned `UNSUPPORTED_COMPONENT`. `operation` returned `OPERATION_NOT_FOUND`.

After the command, two runner processes were still up: Writer pid 7376, title `report.docx * - WPS 文字`, command line the run-1 export fixture; Presentation pid 44480, title `deck.pptx - WPS 演示`, command line the run-1 deck. Both were ended before the table comparison.

**Review (2026-10-15).**

- Four of the five tasks now pass, with no API errors this time. Selection insert passed 3/3 but needed 13.7 turns. Run 3's extra `validate_document` used two spaces (`Finance  (reviewed)`); that call failed, but the file itself was right.
- **Presentation selection replace failed on a product bug in its read-back.** In runs 1 and 3, `file_text` and `backup_count` passed. WPS made the change and saved it, but the tool reported `VALIDATION_FAILED`. After assigning `TextRange.Text`, the script read the text back through the selection. On WPS 12.8 the selection then covers other text, for example the whole shape, so the read-back did not match. The tool then tried to roll back by restoring the backup file. WPS holds that file, so the rollback was blocked (`MUTATION_ROLLBACK_BLOCKED`) and the operation was not recorded.
- **Fix:** the replace script now records the shape's text and the selection's start before the write. After the write, the shape's text must equal the old text with exactly the selected part replaced. If the position does not match the text, it falls back to the old read-back. A fake-COM test reproduces the moved selection and fails on the old script. Selection insert already read back this way, which is why it passed.
- **Run 2's `SELECTION_SPANS_STRUCTURE`** means the selection was not a text selection when the agent looked. The runner's `select_text` now checks the selection type (3) as well as its text. A non-text selection becomes a setup failure, not an agent failure.
- **Remaining gap:** when an open-document write does fail validation, rollback restores the backup file, and WPS holds that file. So the rollback is blocked and the change stays in WPS. Undoing it inside WPS would be the right fix; it is not done here.
- G2 is not met yet. All five tasks are rerun in one command on a `main` that has this fix.

### P6-007 rerun on 98d8dcd

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-writer-table-write --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-table
```

Artifact: `%TEMP%\wps-p6\eval-table\run-20261015T030032883900Z\summary.json`.

**3/3.** Turns 13.7 (10, 14, 17). `wps-agent` calls 38, tool errors 5, `off_path_calls` 2 (`validate_document`, `wps_process_audit`). P5-006 was 3/3, mean 15.3 turns (15, 16, 15), 41 calls, 2 tool errors. No `CELL_NOT_FOUND`.

**P6-007 is done:** 3/3, fewer turns than P5-006 (13.7 against 15.3) and no `CELL_NOT_FOUND`. The dry runs now show the table's size. Run 2 reused request id `eval-table-1` on four dry-run `writer_table_write` calls (row 2 column 2, and row 3 columns 1, 2, and 3, text `FINAL`) and each returned `IDEMPOTENCY_CONFLICT`. The real write still passed, with one backup. Run 1's error was `validate_document` with `INVALID_ARGUMENT` (`request_id` `verify-eval-table-1` and no `contains`). No `wps.exe` was left.

### P6-008 rerun on 4ba838b (2026-10-15)

`main` at `4ba838b`. Windows 10.0.19045. WPS 12.8.2.18913. Claude Code CLI 2.1.295, CLI default model. `claude -p "hi"` returned a normal reply before the run. No `--model`. The system open command was not changed. G2 is judged on this default-launch command. It is met: 5/5 tasks passed 3/3, none skipped. Not rerun with `--wps-launch automation`. The table comparison was not rerun.

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p6\eval-open-4ba838b
```

Artifact: `%TEMP%\wps-p6\eval-open-4ba838b\run-20261015T031958934859Z\summary.json`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | |
| `wps-open-writer-selection-replace` | 3/3 | 6.0 (6, 8, 4) | 15 | 1 | 1 | `mcp_tool_schema` |
| `wps-open-writer-selection-insert` | 3/3 | 10.7 (16, 7, 9) | 21 | 0 | 5 | `export_open_document_text`, `validate_document`, `writer_structure` |
| `wps-open-presentation-selection-replace` | 3/3 | 7.3 (5, 8, 9) | 18 | 0 | 1 | `export_open_document_text` |
| `wps-open-save-document` | 3/3 | 6.0 (5, 5, 8) | 15 | 0 | 2 | `operation`, `snapshot_document` |

Every run recorded the expected operation, kept one backup, and matched the expected text. Presentation recorded `presentation-selection-replace` and did not call `presentation_replace`. The one tool error was run 2 of selection replace: `writer_selection_read` with request id `eval-selection-read` had `is_error` true and an empty `error_codes` list. The run still passed.

After the command, two runner processes were still up: Writer pid 22416, title `report.docx - WPS 文字`, command line the run-2 export fixture; Presentation pid 50020, title `deck.pptx - WPS 演示`, command line the run-1 deck. They were closed after the run. No `et.exe` was left.

**Review (2026-10-15).** **G2 is met.** All five open-document tasks passed 3/3 in one default-launch command, with the system open command unchanged. Presentation selection replace went from 0/3 to 3/3 at 7.3 turns, which confirms the shape-based read-back.

- The one tool error is a JSON-RPC argument error. The agent passed a `request_id` to `writer_selection_read`, which takes none, and an unknown argument is refused that way (`MCP_ARGUMENTS_UNKNOWN`), with no error code in the result text. The F1 contract allows this.
- **Two WPS processes the runner started were still running afterwards.** The summary does not say why, so the runner now records what its cleanup did in each run's `cleanup` field: how the fixture was closed, and which processes were stopped or why they were left. A leftover process is harmless for the results, because each run opens its own fixture.

## Limits

- Twenty-three tasks are still a small set, not a benchmark. Ten run offline (registration, backup, idempotent retry, restore, dry run, a held file, HTML to xlsx and docx, reading sheets); thirteen marked (WPS) need WPS on Windows and are skipped elsewhere. Together they use 24 of the 85 tools.
- The WPS tasks were run on one Windows machine with one WPS version: the first four in P4-007, the five Phase 5 tasks in P5-006, all 3/3. The P4-007 tasks pass on these commits: the three write tasks on `4999b77`, `wps-held-spreadsheet-write` on `6484151`. The first runs of the held task failed because of two server bugs, fixed in PRs #55 and #56. Those fixes change only what a failed call returns, so the three passing write tasks were not rerun.
- The open-document tools attach with `GetActiveObject`, and since P6-003 also through the Running Object Table. On this machine (WPS 12.8.2.18913) a Writer started by `wps.exe "%1"` does not register `kwps.Application`; P6-004 still listed that document with `attached_via` `running_object_table`. The same was true for Spreadsheets and Presentation when those processes were started with their registered open command. A Writer started with `/Automation` lists the document with `attached_via` `active_object`. P6-008's first writes into an open document returned `DOCUMENT_HELD_OPEN` because of the backup's exclusive-share probe; that is fixed (see the P6-008 review). On the `174f04e` rerun, selection replace passed 3/3 and selection insert passed 2/3 before the Claude API returned 402 Insufficient Balance. On the `98d8dcd` rerun, export, selection replace, selection insert, and save passed, and the table comparison passed 3/3; presentation selection replace was 0/3 (`VALIDATION_FAILED` with `MUTATION_ROLLBACK_BLOCKED`, and `SELECTION_SPANS_STRUCTURE`). On the `4ba838b` rerun all five open-document tasks passed 3/3. Since P6-005 the runner ends the WPS processes it started after each run; one Writer from the P6-008 command was still open afterward and was ended before the table comparison.
- There is no held-file recovery task. The runner cannot make WPS open a document and block a rollback, so recovery with `restore-backup --close-in-wps` is checked by hand in P4-011 instead.
- The judge checks state and tool calls, so a correct-sounding reply with the wrong state fails. A failure to report the result accurately is not detected here.
- Results depend on the model the CLI uses. Record it with `--model` when comparing runs.
- Runs are not deterministic. A failing run should be rerun before it is treated as a regression.
- Tool call counts include calls the CLI makes on its own, such as `ToolSearch` to load deferred tools. These are counted as `other_tool_calls` and are not limited by `max_tool_calls`.
- The runner writes artifacts outside the repository by default in CI. Do not commit `artifacts/agent-eval/` runs unless they are needed as evidence.
