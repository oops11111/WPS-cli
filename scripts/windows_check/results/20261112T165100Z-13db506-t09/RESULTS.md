# T-09 Windows check: performance-baseline --include-wps (CLI fixed cost)

- Date: 2026-11-12 (UTC; local UTC+8)
- Branch: `perf-wps-baseline`, commit `13db506` ("T-09: performance-baseline --include-wps; ROADMAP after the 2026-11-12 review")
- Machine: Windows 10 企业版 10.0.19045 build 19045; WPS Office 12.8.2.18913;
  Intel Xeon E5-2666 v3 @ 2.90 GHz (10 cores / 20 logical); 31.86 GB RAM;
  SSD 1 TB (SATA, MediaType SSD); desktop with no battery (mains power);
  power plan 卓越性能 (Ultimate Performance). Full details in `machine.txt`.
- Runner: installed wps-agent 0.14.0 venv's Python with `PYTHONPATH=<worktree>\src`, run from the repository
  root; commands were `& $PY -m wps_ai_agent_cli ...`. Nothing was compiled or downloaded during the
  measurements, and no other heavy work ran in parallel.
- No WPS process was running before any run; after every run the count of `wps`/`et`/`wpp` processes was 0
  (the warm run started one on purpose and it was closed afterwards).

## Steps

| # | Result | Notes |
| --- | --- | --- |
| 0 | ok | `perf-wps-baseline` at `13db506`; result dir created; machine info in `machine.txt` |
| 1 | ok | `performance-baseline` without flags: `ok: true`, `launches_wps: false`, `passed_count` 6 of 6, `failed_count` 0; no WPS process appeared |
| 2 | ok | three cold runs, 60 s apart, WPS not running before each; all exit 0, `ok: true`; no `et` process left after any run |
| 3 | ok | warm run with WPS 表格 open on a blank workbook: exit 0, `ok: true`, `spreadsheet_processes_before/after` = 1/1; WPS closed without saving |
| 4 | ok | results committed on `cursor/t09-windows-13db506` (not main, not perf-wps-baseline) |

## Measurements

`wps_calls` is an array of 5 call records (`repeat 5`); the first entry is `wps_first_call_ms`, the median
of the five is `wps_call_median_ms`. `cli_call_fixed_cost_ms` = median new-process start + median WPS call.

| Run | wps_calls | wps_first_call_ms | wps_call_median_ms | process_start_median_ms | cli_call_fixed_cost_ms | c10_threshold_exceeded | WPS left |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cold-1 (`t09-cold-1.json`) | 5 (all ok) | 20631.117 | 5884.936 | 2391.445 | **8276.381** | true | 0 |
| cold-2 (`t09-cold-2.json`) | 5 (all ok) | 11868.089 | 5457.951 | 1206.055 | **6664.006** | true | 0 |
| cold-3 (`t09-cold-3.json`) | 5 (all ok) | 11524.937 | 5457.927 | 1252.710 | **6710.637** | true | 0 |
| warm (`t09-warm.json`) | 5 (all ok) | 8874.259 | 2628.170 | 1210.070 | **3838.240** | true | 1 (closed) |

- `spreadsheet_processes_before/after`: 0/0 in all three cold runs; 1/1 in the warm run.
- Process-start samples in cold-1 were 1907.071, 2382.534, 2391.445, 2580.427, 2504.920 ms; later runs had a
  warm OS file cache and settled around 1.2 s per process start.
- Raw per-call durations and the full JSON are in the four `t09-*.json` files.

## Conclusion

**One CLI call's fixed cost exceeds 2 seconds in every measurement**: 8.28 s, 6.66 s and 6.71 s cold, and
3.84 s warm, while the threshold is 2 s (`c10_threshold_exceeded: true` for all four runs). The warm result
shows that keeping WPS open cuts the WPS-call median roughly in half (5.46 s cold → 2.63 s warm) but does not
remove the new-process start (~1.2 s) or bring the total under 2 s.

## Deviations and caveats

- The warm run used a blank workbook created for the test (`work\空白.xlsx`, registered by `document-new`),
  not the workbook the baseline writes into.
- The first cold run includes the first WPS cold start of the session (20.6 s first call); the second and
  third are the more representative cold numbers, and the warm run shows the resident-WPS case.
- The machine is a desktop without a battery, so "on mains power" is reported from `Win32_Battery` returning
  nothing and the active plan being Ultimate Performance (`machine.txt`), not from a battery status flag.
- No failures and no residual WPS processes in any step; the only WPS instance started was the blank one for
  the warm run, and it was closed without saving.
