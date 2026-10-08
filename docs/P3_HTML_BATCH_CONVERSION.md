# P3-119 HTML Batch Conversion

`html-batch-convert` converts local `.html` and `.htm` files to PDF, PNG, or
editable DOCX. It processes at most 100 files and 500 MiB total input, can
preserve nested folders with `--recursive`, and isolates a file failure so
later files continue. Existing batch manifests are never overwritten; each
file conversion also uses the existing no-overwrite conversion behavior.

```powershell
python -m wps_ai_agent_cli html-batch-convert --input-dir .\pages --output-dir .\converted --mode docx --recursive
```

The output directory receives `batch-conversion-manifest.json` with per-file
status, source and output SHA-256 digests, byte sizes, conversion details, and
errors. The command exits unsuccessful if any file fails, while retaining the
completed per-file results and manifest. With `--task-id`, status progress is
updated between files. Request cooperative cancellation with:

```powershell
python -m wps_ai_agent_cli task-status-update --task-id batch-1 --state cancelled --message "Cancel requested"
python -m wps_ai_agent_cli task-status --task-id batch-1
```

Cancellation is checked at file boundaries; the current file finishes and all
completed results remain in the partial manifest. MCP tool
`wps_agent_html_batch_convert` exposes the same task-tracking contract. The
template report commands can render the partial manifest and disclose planned
versus processed counts.

With a stable `--request-id`, a completed successful batch can be replayed
without converting files again. The workspace records the request's input
directory, output directory, mode, and recursive setting. Replay verifies the
manifest, current source inventory, source hashes, and output hashes; changed
arguments or files are rejected. The returned data has `replayed: true`.
Existing manifests without a recorded request ID remain non-replayable.
Failed and cancelled requests require review before reuse. If a request remains
`running` after an interruption, a retry can recover it only when the complete
successful manifest and every current source/output hash verify. A missing or
damaged manifest remains unavailable for replay. New request identities use
individual records of at most 16 KiB under `.wps-agent/html_batch_requests/`.
Existing `html_batch_requests.json` registries remain readable and are not
modified; a verified legacy completion writes a new per-request record.
Oversized or damaged records block replay without removing manifest evidence.
Registry write failures return structured errors. If terminal state persistence
fails after the manifest is created, a retry may recover from intact evidence;
it does not reconvert the files. P3-155 verified replay and argument conflict
across independent CLI processes; the DOCX artifact was not modified. P3-156
adds read-only request inspection and recovery guidance:

```powershell
python -m wps_ai_agent_cli html-batch-request --batch-request-id cross-process-request
```

The `wps_agent_html_batch_request` MCP tool exposes the same record by
`batch_request_id`. Neither command modifies registry or manifest files.
The returned state is the recorded state. Add `--verify` (or MCP `verify: true`)
to check the current manifest and source/output hashes without changing files.
`evidence_status` reports `passed`, `failed`, or `not_checked` separately from
the recorded request state.
