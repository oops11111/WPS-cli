# Agent end-to-end evaluation

This pipeline runs fixed tasks through the real `claude -p` CLI with the `wps-agent` MCP server attached. It then judges each task from the workspace state, not from the agent's reply. It is the Phase 3 "真实 Agent 端到端评测" item in `docs/ROADMAP.md`.

## What it covers

Tasks are in `config/agent_eval_tasks.json`. Each task runs in its own workspace, which is also the MCP server's working directory. The fixture is `book.xlsx`.

| Task | Asks the agent to | Judged by |
| --- | --- | --- |
| `register-and-backup` | register the file, then back it up with a fixed request id | document registered; operation `eval-backup-1` recorded as `backup-document`; one backup; file unchanged |
| `list-backups-readonly` | register the file and list backups without changing anything | document registered; no backups; file unchanged |
| `restore-missing-backup` | restore from a backup that does not exist | document registered; no operation recorded for `eval-restore-1`; file unchanged |

Only offline tools are used. None of these tasks needs WPS, so they run on any machine with the `claude` CLI logged in. WPS-dependent write paths are not covered here.

## How to run

```bash
python scripts/agent_eval/run_agent_eval.py --out artifacts/agent-eval
python scripts/agent_eval/run_agent_eval.py --only register-and-backup --model <model-id>
```

The runner needs `claude` on `PATH`. It exits with 0 when every task passes, 1 when any fails, and 2 when the CLI is missing. Each run writes `summary.json` under `<out>/run-<timestamp>/`. The summary holds the agent's turns, duration, cost, reply excerpt and every check result.

The offline tests in `tests/test_agent_eval.py` cover the judge and the MCP config with a stand-in agent. They do not call the CLI.

## Results

Run 2026-10-13 with `claude` 2.1.296 (CLI default model), on this repository's `main` at `4b6fdb3`:

| Task | Result | Turns | Duration | Cost (USD) |
| --- | --- | --- | --- | --- |
| `register-and-backup` | pass | 4 | 9.1 s | 0.067 |
| `list-backups-readonly` | pass | 4 | 8.2 s | 0.067 |
| `restore-missing-backup` | pass | 4 | 10.5 s | 0.068 |

Total for the three tasks: about USD 0.20.

## Limits

- Three tasks are a smoke set, not a benchmark. They check that an agent can reach the server and use the tools correctly.
- The judge checks state, so a correct-sounding reply with the wrong state fails. A failure to report the result accurately is not detected here.
- Results depend on the model the CLI uses. Record it with `--model` when comparing runs.
- Runs are not deterministic. A failing run should be rerun before it is treated as a regression.
- The runner writes artifacts outside the repository by default in CI. Do not commit `artifacts/agent-eval/` runs unless they are needed as evidence.
