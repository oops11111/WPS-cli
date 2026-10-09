# P3-008 Performance Baseline

Date: 2026-10-03

## Scope

This baseline captures runtime, output size, and pass/fail evidence for safe commands that do not launch WPS. It covers read-only MCP discovery, MCP smoke, MCP client config audit, security audit, batch reporting without snapshots, and the safe regression profile.

## Implemented Guard

`performance-baseline` now runs a fixed safe scenario set and records:

- command arguments
- exit code
- response status
- validation status
- duration in milliseconds
- output bytes and characters
- whether the scenario can launch WPS

The command fails if any baseline scenario fails or if a WPS-launching scenario is included.

## Evidence

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli performance-baseline --request-id p3-008-performance-baseline-001
```

Summary:

- `scenario_count`: 6
- `passed_count`: 6
- `failed_count`: 0
- `launches_wps`: false
- `total_duration_ms`: 2176.012
- `total_output_bytes`: 244981
- `max_duration_ms`: 1094.043

## Scenario Baseline

| Scenario | Duration ms | Output bytes | Validation |
| --- | ---: | ---: | --- |
| `mcp-tools` | 32.188 | 90408 | not_applicable |
| `mcp-smoke` | 61.687 | 120837 | passed |
| `mcp-config-audit` | 918.502 | 4108 | passed |
| `security-audit` | 27.551 | 20375 | passed |
| `batch-report-phase0-no-snapshots` | 42.041 | 3470 | passed |
| `regression-run-safe` | 1094.043 | 5783 | passed |

## Current Observations

- `mcp-smoke` has the largest output because it includes the full `tools/list` surface.
- `mcp-config-audit` and `regression-run-safe` are the slowest safe scenarios because they run nested smoke checks.
- `batch-report --no-snapshots` provides a cheap file inventory baseline without opening WPS.
- The current MCP tool count is 38.

## Follow-up

The next production-readiness task should refresh desktop MCP integration evidence against the 38-tool surface, including config audit, tools/list, tools/call, and any remaining real-client gap.

## 2026-10-09 Refresh

P3-264 added a 200-sample in-process pagination baseline against the current 81-tool catalog. See `docs/P3_MCP_PAGINATION_PERFORMANCE_BASELINE_20261009.md` for environment, p50/p95, response sizes, and measurement limitations.

P3-265 refreshes the safe `mcp-smoke` and `mcp-config-audit` minimum from the historical 47-tool threshold to the current 81-tool catalog. A focused unit test asserts both scenarios retain the current threshold; this makes an incomplete MCP catalog fail the performance baseline instead of silently passing.

The refreshed run (`p3-265-final-baseline`) passed all 6 scenarios with no WPS launch: total 8,114.620 ms and 316,393 output bytes. The nested safe regression scenario passed after the current next-task expectation, parity evidence, and sync package were refreshed. Timings are environment-specific.

P3-263's real-client audit remains environment-limited: Claude Code reports no MCP servers configured and Claude Desktop UI inspection was unavailable. The local in-process metrics above are not desktop integration evidence.
