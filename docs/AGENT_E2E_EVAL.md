# Agent end-to-end evaluation

This pipeline runs fixed tasks through the real `claude -p` CLI with the `wps-agent` MCP server attached. It judges each task from the workspace state and from the tool calls in the CLI transcript, not from the agent's reply. It is the Phase 3 "真实 Agent 端到端评测" item in `docs/ROADMAP.md`.

## What it covers

Tasks are in `config/agent_eval_tasks.json`. Each task runs in its own workspace, which is also the MCP server's working directory. The default fixture is `book.xlsx`, with `seed` in A1. A task can name its own `fixture` and `component`: `report.docx` (Writer) holds the paragraphs `Quarterly report`, `Status: DRAFT` and `Owner: Finance`, and `deck.pptx` (Presentation) holds one slide with `Quarterly review` and `Status: DRAFT`.

A task can list `setup` steps that prepare the workspace before the agent starts:

| Step | Effect |
| --- | --- |
| `register` | registers `book.xlsx` |
| `backup` | backs it up with request id `setup-backup` |
| `modify` | changes A1 to `changed by mistake` and saves the file |
| `html_table` | writes `table.html` with a two-column table |
| `hold` | holds `book.xlsx` the way WPS holds an open document. Must be the last step. |

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

Only offline tools are used. None of these tasks needs WPS, so they run on any machine with the `claude` CLI logged in. WPS-dependent write paths are not covered here.

`held-document-backup` needs a machine that can hold the file. On Windows the runner opens it with no sharing. On other systems it removes all permissions, which does not work for root. When the file cannot be held, the task is reported as skipped, not as passed or failed.

## Check kinds

State checks: `document_registered`, `operation_recorded`, `no_operation`, `backup_count`, `file_unchanged` (the file as the agent received it, after setup), `file_matches_seed` (the file before setup), `xlsx_cell`, `file_text` (text that a `.docx` or `.pptx` must contain, and text it must not).

Transcript checks, read from the tool calls, not from the reply: `tool_called` (optionally with `input` values and a `min` count), `tool_not_called`, `tool_error_seen` (an error code in a tool result), `max_tool_calls` (calls to `wps-agent` tools only).

## How to run

```bash
python scripts/agent_eval/run_agent_eval.py --out artifacts/agent-eval
python scripts/agent_eval/run_agent_eval.py --only register-and-backup --model <model-id>
python scripts/agent_eval/run_agent_eval.py --repeat 3 --min-passes 2
```

The runner needs `claude` on `PATH`. It runs the CLI with `--output-format stream-json --verbose` so that it can read each tool call. It exits with 0 when every task that ran passes, 1 when any fails, and 2 when the CLI is missing. Skipped tasks do not change the exit code.

`--repeat N` runs each task N times, each in its own workspace under `run-<n>/`. A task passes when at least `--min-passes` runs pass; by default every run must pass. The summary records each run, the number of passes and the pass rate. Phase 4 judges WPS write tasks with `--repeat 3 --min-passes 2`.

A task with `"requires_wps": true` runs only when this machine has a registered WPS ProgID for the task's component, found with the project's own capability probe. Otherwise it is reported as skipped with the reason. A skip ends the task after the first attempt, because it does not depend on the run.

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

## Limits

- Twelve tasks are still a small set, not a benchmark. Eight run offline (registration, backup, idempotent retry, restore, dry run, a held file, HTML conversion); four marked (WPS) need WPS on Windows and are skipped elsewhere. They do not cover the 85-tool surface.
- The WPS tasks have only been checked offline, against a stand-in agent. Their first real runs are P4-007.
- The held-file recovery task (a rollback blocked by an open document, then recovered from the CLI) is added with the opt-in close-and-restore, P4-010.
- The judge checks state and tool calls, so a correct-sounding reply with the wrong state fails. A failure to report the result accurately is not detected here.
- Results depend on the model the CLI uses. Record it with `--model` when comparing runs.
- Runs are not deterministic. A failing run should be rerun before it is treated as a regression.
- Tool call counts include calls the CLI makes on its own, such as `ToolSearch` to load deferred tools. These are counted as `other_tool_calls` and are not limited by `max_tool_calls`.
- The runner writes artifacts outside the repository by default in CI. Do not commit `artifacts/agent-eval/` runs unless they are needed as evidence.
