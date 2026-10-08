# Regression Manifest

## Purpose

`config/regression_manifest.json` is the Phase 3 machine-readable smoke matrix. It records critical CLI, MCP, config-audit, and WPS scenarios with expected evidence so regression checks can be run by command instead of by manual checklist.

## Commands

```powershell
python -m wps_ai_agent_cli regression-manifest --profile safe
python -m wps_ai_agent_cli regression-run --profile safe
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
python -m wps_ai_agent_cli regression-manifest --profile release
python -m wps_ai_agent_cli regression-run --profile release
python -m wps_ai_agent_cli local-release-gates
python -m wps_ai_agent_cli regression-manifest --profile wps --include-wps
python -m wps_ai_agent_cli regression-run --profile wps --include-wps
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps
```

## Profiles

| profile | Default | WPS required | Purpose |
| --- | --- | --- | --- |
| `safe` | yes | no | CI-friendly baseline checks for roadmap, task state, MCP, package, documentation, and security that do not depend on a prior successful safe regression artifact |
| `release` | no | no | Local handoff, regression evidence, and regression history gates that depend on current safe and WPS artifacts |
| `wps` | no | yes | Real WPS desktop smoke scenarios for Writer, Spreadsheet, and conversion |

## Current Safe Matrix

| ID | Category | Evidence |
| --- | --- | --- |
| `cli-plan` | CLI | Phase 3 is active |
| `cli-phase3-next` | CLI | P3 next task is exposed |
| `mcp-tools-count` | MCP | At least 85 tools are listed |
| `artifact-retention-summary` | Maintenance | artifact retention summary is passed and performs no deletion |
| `validation-runbook` | Project | validation runbook is passed and executes no commands |
| `documentation-freshness` | Project | current docs and config references are fresh |
| `mcp-catalog-drift` | MCP | current catalog matches the reviewed baseline with zero drift |
| `sync-package-inspect` | Sync | existing local sync package is readable and includes expected roots plus package-time safe/WPS regression artifacts |
| `sync-package-summary` | Sync | existing local sync package content distribution is summarized without mutation |
| `sync-package-manifest` | Sync | existing local sync package entries are listable with prefix filtering |
| `sync-package-coverage` | Sync | existing local sync package covers package-time workspace sync roots |
| `sync-package-readiness` | Sync | existing local sync package has consolidated handoff readiness |
| `mcp-smoke` | MCP | initialize, tools/list, tools/call pass |
| `mcp-config-audit` | MCP | client config can launch server and run tools/list |
| `security-boundary-audit` | Security | mutating tool boundaries pass for at least 8 tools |

## Current Release Matrix

| ID | Category | Evidence |
| --- | --- | --- |
| `local-handoff-summary` | Project | local handoff summary is passed |
| `regression-evidence` | Regression | latest safe and WPS regression artifacts are summarized and passing |
| `regression-history` | Regression | latest safe and WPS regression history is summarized and passing |

Build the local package, run the safe profile with an artifact directory, refresh the package to include that artifact, then run the release profile. Failed historical artifacts remain available for inspection; a new passed safe artifact is required before the release gates can pass.

`local-release-gates` performs this sequence and checks package readiness between the refresh and release stages. It stops on the first failed gate and reports each completed step with its artifact path. It writes only local package and regression artifacts; it does not launch WPS or use remote Git.

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
