# P3-006 Recovery Hardening Drill

Date: 2026-10-03

## Scope

This drill verifies the recovery path for a failed document-mutating operation before any retry is attempted. The target scenario is a simulated failed `writer-replace` task on a registered Writer document.

## Target Document

- `document_id`: `doc_df251804dc8654c0`
- Component: `writer`
- Path: `C:\Users\admin\Documents\wps cli\smoke_writer_copy.docx`

## Drill Steps

1. Create a fresh backup for the target document.
2. Create a tracked task status for a simulated `writer-replace` operation.
3. Mark the task terminal `failed`.
4. Run `task-recovery` for the failed task.
5. Inspect operation ledger, backup inventory, and document snapshot before retry.

## Evidence

| Evidence | Result |
| --- | --- |
| Backup request | `p3-006-backup-before-failure-drill` |
| Backup path | `.wps-agent\backups\doc_df251804dc8654c0\smoke_writer_copy.20261003T100535958147Z.docx` |
| Failed task id | `p3_006_failed_writer_replace` |
| Failed task request | `p3-006-failed-writer-replace` |
| Recovery playbook request | `p3-006-task-recovery` |
| Recovery scenario | `failed` |
| Safe to retry | `false` |
| Backup inventory | 5 backups returned for `doc_df251804dc8654c0` |
| Snapshot request | `p3-006-snapshot-document` |
| Snapshot result | Writer snapshot passed with 141 paragraphs and 140 non-empty paragraphs |

The operation ledger check for `p3-006-failed-writer-replace` returned `OPERATION_NOT_FOUND`. This is expected for this simulated terminal failure and is useful evidence: recovery must not assume a missing operation record means it is safe to retry. The recovery playbook correctly points the agent to `list-backups` and `snapshot-document` before retry.

## Recovery Decision

Do not retry immediately. The failed task is terminal and `safe_to_retry` is `false`. A retry should only happen after an operator or agent verifies one of these states:

- The document snapshot matches the expected pre-retry structure.
- A known-good backup has been selected for restore if partial mutation is suspected.
- No WPS process is still acting on the same document.
- The retry uses a new `request_id` after the previous attempt is accounted for.

## Follow-up Hardening

- Add operation-ledger correlation for simulated or preflight task failures when a mutating task fails before creating an operation record.
- Consider a first-class recovery drill command once multiple failure patterns are covered.
- Add a destructive-operation permission audit as the next Phase 3 production-readiness task.
