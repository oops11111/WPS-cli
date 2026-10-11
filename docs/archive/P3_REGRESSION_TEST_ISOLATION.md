# Regression test isolation and output capture

P3-147 replaces accidental dependencies on mutable workspace release state with
explicit test inputs. It does not relax production regression requirements.

- `tests/fixtures/regression_contract.json` executes actual tasks and MCP catalog
  commands through the real regression runner. It asserts response fields.
- Artifact tests execute this manifest in temporary directories and inspect the
  written JSON. A failing-check variant must retain failed counts and errors.
- Performance aggregation uses fixed command-result fixtures. A separate test
  executes a real CLI command and checks captured JSON and duration. A negative
  test preserves regression-command failures in the performance summary.
- Production manifest loading and WPS filtering remain covered separately.

P3-148 changes regression/performance helpers to pass an explicit output stream
to CLI run. A blocked command in one thread must not redirect process stdout;
another thread's output is asserted independently for both helpers.

Verification: full unittest discovery, with no exclusions, ran 267 tests:
245 passed and 22 opt-in integrations skipped. Focused CLI/regression/performance/
server tests ran 44 tests successfully before full discovery.

The default production manifest still inspects real failed history and package
freshness. Tests use deliberate fixtures and therefore do not certify a clean
release workspace. Historical failed artifacts are retained. Local package
readiness remains a separate content-coverage check.

Next, P3-149 reviews task ownership: create_task_status currently replays any
existing task_id without comparing command/request, and the CLI wrapper still
executes its operation factory for a terminal record. Tests must distinguish
legitimate same-operation replay from attaching an unrelated mutation to old
status. This inspection identifies work, not proof of its completion.
