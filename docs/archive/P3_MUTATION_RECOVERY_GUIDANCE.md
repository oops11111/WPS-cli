# P3-180 Mutation Recovery Guidance

`mutation-request-inspect --request <id>` and its MCP mapping now include `recovery_guidance` for every inspection status. The command remains read-only. The local `validation-runbook` includes a mutation-recovery section whose sole step inspects request evidence before any decision.

`retryable` requires an unchanged source matching the pre-mutation backup; it advises retrying only with the same request ID after checking for an external editor. `recorded_repairable` advises same-ID replay solely to repair stale registration, without repeating the mutation. `ambiguous`, `recorded_changed`, and `recorded_unverified` explicitly direct the operator to preserve and compare evidence rather than automatically overwrite or rerun. `no_evidence` does not imply that a write definitely did not happen.

Focused operation/runbook/adapter tests passed 31/31. The full default suite ran 345 tests with 27 skipped and no failures. No WPS launch or remote Git is required for this read-only guidance.
