# Agent end-to-end evaluation

This pipeline runs fixed tasks through the real `claude -p` CLI with the `wps-agent` MCP server attached. It judges each task from the workspace state and from the tool calls in the CLI transcript, not from the agent's reply. It is the Phase 3 "真实 Agent 端到端评测" item in `docs/ROADMAP.md`.

## What it covers

Tasks are in `config/agent_eval_tasks.json`. Each task runs in its own workspace, which is also the MCP server's working directory. The default fixture is `book.xlsx`, with `seed` in A1. A task can name its own `fixture` and `component`: `report.docx` (Writer) holds the paragraphs `Quarterly report`, `Status: DRAFT` and `Owner: Finance`, `deck.pptx` (Presentation) holds one slide with `Quarterly review` and `Status: DRAFT`, and `table_report.docx` (Writer) holds the paragraph `Regional status` and one table with the rows `Region, Q1, Status`, `North, 120, DRAFT` and `South, 95, DRAFT`.

A task can list `setup` steps that prepare the workspace before the agent starts:

| Step | Effect |
| --- | --- |
| `register` | registers `book.xlsx` |
| `backup` | backs it up with request id `setup-backup` |
| `modify` | changes A1 to `changed by mistake` and saves the file |
| `html_table` | writes `table.html` with a two-column table |
| `hold` | holds the fixture the way WPS holds an open document. Must be the last step. |
| `open_in_wps` | opens the fixture in WPS on Windows and waits until WPS lists it as open (up to 45 s). With `--wps-launch default` (the default) it opens the file with its default app, as a double-click does; with `--wps-launch automation` it starts the program associated with the extension with `/Automation` and the file, without changing the system's open command. It records the WPS processes (`wps`, `et`, `wpp`) that appeared while opening. After the agent, the runner closes the document without saving, and only when WPS reports no unsaved changes; then it ends the processes it recorded, but only while WPS lists no other document for the component, so that the next `--repeat` run starts from the same state. Only `select_text` and `append_unsaved` may follow it; the task must be marked (WPS). Elsewhere the task is skipped. |
| `select_text` | after `open_in_wps`: selects the first occurrence of the task's `selection.text` in WPS (Writer or Presentation), or, with `"collapse": "end"`, puts the caret right after it (Writer). It reads the selection back; when WPS selected something else, the run is a setup failure, not an agent failure. |
| `append_unsaved` | after `open_in_wps`: appends the task's `unsaved_text` as a new paragraph in WPS (Writer) without saving, and checks that WPS reports the document as unsaved. |

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

The ten tasks without (WPS) use only offline tools and run on any machine with the `claude` CLI logged in. The thirteen (WPS) tasks need WPS on Windows; the last four, added in P6-006, write to a document open in WPS and have only been checked offline against a stand-in agent until P6-008 runs them on Windows. The first four were run in P4-007 (results below). The last five, added in P5-005, were run on Windows in P5-006 (results below); all five passed 3/3.

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

The runner needs `claude` on `PATH`. It runs the CLI with `--output-format stream-json --verbose` so that it can read each tool call. It exits with 0 when every task that ran passes, 1 when any fails, and 2 when the CLI is missing. Skipped tasks do not change the exit code.

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

## Limits

- Twenty-three tasks are still a small set, not a benchmark. Ten run offline (registration, backup, idempotent retry, restore, dry run, a held file, HTML to xlsx and docx, reading sheets); thirteen marked (WPS) need WPS on Windows and are skipped elsewhere. Together they use 24 of the 85 tools.
- The WPS tasks were run on one Windows machine with one WPS version: the first four in P4-007, the five Phase 5 tasks in P5-006, all 3/3. The P4-007 tasks pass on these commits: the three write tasks on `4999b77`, `wps-held-spreadsheet-write` on `6484151`. The first runs of the held task failed because of two server bugs, fixed in PRs #55 and #56. Those fixes change only what a failed call returns, so the three passing write tasks were not rerun.
- The open-document tools attach with `GetActiveObject`. On the P5-006 machine (WPS 12.8.2.18913), a WPS Writer started by opening a `.docx` the usual way (`wps.exe "%1"`) did not register `kwps.Application`, so `open_documents` did not list its documents; a Writer started with `/Automation` did. Since P6-003 the tools also look for the document in the Running Object Table and attach through it, and when a WPS window of the component is running but nothing can be reached they answer `WPS_INSTANCE_NOT_AUTOMATABLE` with the remedy instead of `NO_RUNNING_WPS_INSTANCE`. Whether the Running Object Table route reaches a double-clicked Writer is what P6-002 and P6-004 check on Windows. Until then, `--wps-launch automation` runs the open-document tasks without depending on it. Since P6-005 the runner ends the WPS processes it started after each run, so `--repeat` no longer needs the earlier run's Writer closed by hand.
- There is no held-file recovery task. The runner cannot make WPS open a document and block a rollback, so recovery with `restore-backup --close-in-wps` is checked by hand in P4-011 instead.
- The judge checks state and tool calls, so a correct-sounding reply with the wrong state fails. A failure to report the result accurately is not detected here.
- Results depend on the model the CLI uses. Record it with `--model` when comparing runs.
- Runs are not deterministic. A failing run should be rerun before it is treated as a regression.
- Tool call counts include calls the CLI makes on its own, such as `ToolSearch` to load deferred tools. These are counted as `other_tool_calls` and are not limited by `max_tool_calls`.
- The runner writes artifacts outside the repository by default in CI. Do not commit `artifacts/agent-eval/` runs unless they are needed as evidence.
