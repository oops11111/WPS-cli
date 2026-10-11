# P3-288 MCP Audit Output Bounds Scope

## Goal

Bound memory used while reading output from configured MCP server subprocesses.

## Acceptance

- Reject stdout response lines above a documented fixed character limit without parsing the full response.
- Bound queued stdout messages while preserving ordered responses and EOF behavior.
- Continue draining stderr while retaining only the existing bounded diagnostic prefix.
- On over-limit output, return a bounded audit error and terminate/reap the child process.
- Regression tests cover overlong output, queue behavior, timeout cleanup, and a successful persistent configured audit.

## Boundaries

- Preserve current MCP handshake, response ID checks, pagination, and descriptor validation.
- Do not execute tools or launch WPS.
- Run focused audit tests, the full suite, safe regression, package readiness, and documentation freshness.
