# P3-285 Persistent stdio configured-client audit

## Goal

Make the configured MCP client audit verify the same persistent stdio lifecycle used by real clients instead of launching a new one-shot process for every page.

## Acceptance

- Start one configured server process and perform initialize, initialized notification, then all tools/list pages over its stdin/stdout.
- Verify every response ID and JSON-RPC shape, pagination cursor uniqueness, tool catalog audit, and deadline.
- Close stdin, wait for clean process exit, and retain bounded stderr diagnostics.
- Cover successful traversal, protocol error, timeout/termination, and cleanup behavior with deterministic fake servers.

## Boundaries

Honor the configured executable, args, cwd, and environment. Do not edit client configuration or launch WPS.
