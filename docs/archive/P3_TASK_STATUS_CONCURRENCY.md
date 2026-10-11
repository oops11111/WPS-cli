# Concurrent task status persistence

P3-146 protects each create/update read-check-write transaction with a process
thread lock and a stable sibling file lock. Windows uses msvcrt byte-range locks;
POSIX uses flock. Locks are released in finally blocks and by OS handle closure.
The lock file is intentionally retained so waiting processes share one identity.

Readers of existing state take the same lock. Writes serialize to a temporary
file in the state directory, flush and fsync it, then replace the JSON atomically.
A failed replacement removes the temporary file and preserves prior state.
Create/update use unlocked helpers only while the transaction lock is held.

## Verified on Windows

- A paused progress transaction blocks cancellation until commit. Cancellation
  then commits and later progress updates reject the terminal task.
- Four real Python processes create 12 tasks each, with an intentional delay
  after reading state: all 48 task IDs remain present.
- An injected replacement failure leaves original JSON bytes unchanged, removes
  the temporary file, and permits a subsequent successful cancellation.
- Status, server, and adapter focused suite: 41 tests passed.
- Full discovery without exclusions: 262 total, 237 passed, 22 skipped, 3 failed.

## Follow-up: P3-147

The three failures are regression-run artifact generation, safe-manifest success,
and the performance baseline. Their inputs include actual historical failed
regressions and a package made stale by current source changes. Detailed failed
scenarios include local-handoff-summary, regression-evidence, regression-history,
sync-package-coverage, and sync-package-readiness. These are valid release
diagnostics, but cannot serve as deterministic unit-test success fixtures.
Provide explicit fixtures for the tests and keep production gate semantics.

POSIX locking was not exercised on this Windows host. External writers that
bypass this module do not honor the lock. This does not establish crash recovery
of running document operations or power-loss durability of directory metadata.
