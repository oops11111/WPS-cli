# Ecosystem extension evaluation

This is the written evaluation for the second half of Phase 3 item 4 in `docs/ROADMAP.md` (生态扩展评估). It records which MCP clients the `wps-agent` server has been run with, what each run proved, and what remains unverified. Only results that were actually observed are listed as verified.

## Scope

- Server: `python -m wps_ai_agent_cli mcp-server`, on the `main` branch.
- Transport: stdio only. The server has no HTTP or SSE transport, so clients that need a remote transport cannot use it yet.
- Protocol: `2025-11-25`, the only version in `SUPPORTED_MCP_PROTOCOL_VERSIONS`.

## Client matrix

| Client | Status | Evidence |
| --- | --- | --- |
| Claude Code CLI 2.1.296 | **Verified** | Runs `claude -p` with `--mcp-config` and `--strict-mcp-config`. Three fixed tasks pass, each calling `wps-agent` tools and judged from workspace state. See `docs/AGENT_E2E_EVAL.md`. |
| Codex CLI | **Not verified** | Not installed on the evaluation machine, so it could not be run. Its MCP support is the follow-up item for Phase 3. |
| Claude Desktop (Windows) | **Not verified** | P3-263 audit (2026-10-09): the desktop process was present, but no MCP server was configured and the UI handshake could not be observed. The integration gate is still open. |
| Other MCP clients | **Not evaluated** | No run with any other client. |

## Protocol and catalog checks

These were run against the server directly, not through a client.

- `initialize`: the server returns the negotiated protocol version, `serverInfo` and `capabilities.tools`. Missing or malformed `clientInfo` gets `-32602`.
- `tools/list`: 85 tools, returned in two pages of 50 and 35. The cursor is opaque and the last page has no `nextCursor`. Checked today with `handle_mcp_json`.
- `tools/call`: exercised by the claude CLI runs above, and by `mcp-smoke`.
- Catalog drift: `mcp-catalog-drift` matches the committed baseline (`config/mcp_catalog_guard.json`, 85 tools).

## Known gaps

1. **Desktop client integration is unverified.** The P3-263 gate needs a configured server, a working desktop inspection channel, and a real `initialize`, paginated `tools/list` and a safe `tools/call` from the desktop client. None of this has been observed.
2. **Only stdio.** Clients that need HTTP or SSE cannot connect.
3. **Three evaluation tasks are a smoke set.** The agent evaluation does not show how a client behaves across the full tool surface.

## What would close the gaps

- For Claude Desktop: configure the server in `claude_desktop_config.json`, then repeat the P3-263 audit with the desktop inspection channel working. Record client version, transport, negotiated protocol, full pagination and one safe `tools/call`.
- For HTTP clients: a transport decision is needed first. It is not a documentation change.
- For other clients: pick the clients that matter and run the same checks.

## Follow-up

The follow-up for Phase 3 item 4 is Codex integration: run the server with the Codex CLI as an MCP client, on a machine where Codex is installed. Use the same checks as the Claude Code run: `initialize`, paginated `tools/list`, and a safe `tools/call`. Claude Desktop remains unverified, but it is no longer the follow-up.

## Decision still needed

Whether the desktop-client check is a condition for closing Phase 3 item 4, or whether the Claude Code CLI evidence is enough for this phase.
