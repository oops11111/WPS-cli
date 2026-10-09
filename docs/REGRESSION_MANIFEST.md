# Regression Manifest

## Purpose

`config/regression_manifest.json` is the Phase 3 machine-readable smoke matrix. It records critical CLI, MCP, config-audit, and WPS scenarios with expected evidence so regression checks can be run by command instead of by manual checklist.

## Commands

```powershell
python -m wps_ai_agent_cli regression-manifest --profile safe
python -m wps_ai_agent_cli regression-run --profile safe
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
python -m wps_ai_agent_cli regression-manifest --profile wps --include-wps
python -m wps_ai_agent_cli regression-run --profile wps --include-wps
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps
```

## Profiles

| profile | Default | WPS required | Purpose |
| --- | --- | --- | --- |
| `safe` | yes | no | CI-friendly baseline checks for roadmap, task state, MCP catalog, and security that do not launch WPS |
| `release` | no | no | Reserved profile; the shipped manifest currently has no release scenarios |
| `wps` | no | yes | Real WPS desktop smoke scenarios for Writer, Spreadsheet, and conversion |

## Current Safe Matrix

| ID | Category | Evidence |
| --- | --- | --- |
| `cli-plan` | CLI | Phase 3 is active |
| `cli-phase3-next` | CLI | P3 next task is exposed |
| `mcp-tools-count` | MCP | At least 70 tools are listed |
| `mcp-catalog-drift` | MCP | current catalog matches the reviewed baseline with zero drift |
| `mcp-smoke` | MCP | initialize, tools/list, tools/call pass |
| `mcp-config-audit` | MCP | client config can launch server and run tools/list |
| `security-boundary-audit` | Security | mutating tool boundaries pass for at least 8 tools |

## Current Release Matrix

Empty. The reporting scenarios that used to live here (`local-handoff-summary`, `regression-evidence`, `regression-history`) and the `local-release-gates` command were removed together with the project self-reporting modules; see `docs/CODE_REVIEW_BATCH_6.md` (G-07).

## Current WPS Matrix

| ID | Component | Evidence |
| --- | --- | --- |
| `writer-com-smoke` | Writer | open/save/close validation passes |
| `spreadsheet-calc-smoke` | Spreadsheets | formula calculation validation passes |
| `writer-convert-smoke` | Writer conversion | PDF conversion validation passes |
| `writer-table-smoke` | Writer table update | output-copy table write, backup evidence, and restore dry-run validation pass |

The WPS profile is intentionally not part of the default regression run because it can launch desktop WPS and write output files under `fixtures/phase3`.

As of P3-013, the full WPS profile passes all 4 scenarios. The spreadsheet calculation smoke now disables WPS alerts, removes a pre-existing output file before `SaveAs`, and uses a manifest timeout of 30 seconds.

CI handoff, artifact retention, and pass/fail gates are documented in `docs/REGRESSION_CI_HANDOFF.md`.

## 场景命令白名单

`regression-run` 通过 `--manifest` 接受调用方提供的清单，MCP 中它被标记为非修改类工具，所以场景只能运行随仓库发布的清单已使用的只读与冒烟命令（见 `regression.REGRESSION_ALLOWED_COMMANDS`）。其他命令（例如 `restore-backup`、`regression-run`、`mcp-server`）不会被执行，该场景返回 `REGRESSION_COMMAND_NOT_ALLOWED`。给默认清单新增使用新命令的场景时，需要同步更新白名单；`tests/test_review_batch_4_5.py` 会检查两者一致。
