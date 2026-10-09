# P3-177 Operation Commit and Identity Consistency

An operation record and a document registration are separate JSON transactions. The operation ledger now retains the file identity captured after save and before its record is committed. If identity refresh fails after the operation record is durable, replay compares the current file with both the registration and the committed identity. It repairs a stale registration only when the current file still has the committed identity. A different file produces `OPERATION_SOURCE_CHANGED` instead of silently blessing it.

If post-save identity capture itself fails, the operation still receives a durable `identity_capture_error` marker. Its replay returns `OPERATION_IDENTITY_UNVERIFIED`, preventing an automatic second write. The caller must inspect the file and re-register before another mutation. Legacy records without these fields retain their previous replay behavior.

Focused tests inject refresh and identity-capture failures, verify the saved operation evidence, and check both safe repair and refusal after external change. The full default suite ran 342 tests (27 skipped, no failures); opt-in real WPS Writer/Spreadsheet checks passed 2/2. Ten repeated cross-process registry tests passed after fixing transient Windows lock initialization and read sharing conflicts.

This does not make the two JSON files one atomic transaction. A process crash after WPS saves but before the operation record is durable remains an ambiguous-write window; P3-178 addresses its recovery contract.
