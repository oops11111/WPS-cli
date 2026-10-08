# P3-183 Recovery Drill Package Handoff

The local portable package now includes the six generated Writer and Spreadsheet recovery-drill files (manifest, current, backup for each) only when workspace evidence verifies. If the evidence directory exists but is incomplete or changed, package creation returns `RECOVERY_DRILL_EVIDENCE_INVALID` before rebuilding the archive. If no drill directory exists, the optional evidence is absent rather than required.

After packaging, all six ZIP entries are compared by SHA-256 with the current workspace files. `sync-package-readiness` repeats this byte comparison and fails if a required entry is missing, duplicated, oversized, or changed. A focused test proves that changed workspace evidence cannot overwrite a previously valid package.

The real local archive at `artifacts/cloud-sync/wps-ai-agent-cli-phase3-sync-cli.zip` included all six entries with matching bytes; package readiness passed. The full default suite ran 353 tests (29 skipped, no failures). No remote Git or WPS launch was used for packaging.
