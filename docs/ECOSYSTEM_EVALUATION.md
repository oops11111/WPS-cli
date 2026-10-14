# Ecosystem extension evaluation

This is the written evaluation for the second half of Phase 3 item 4 in `docs/ROADMAP.md` (生态扩展评估). It records which MCP clients the `wps-agent` server has been run with, what each run proved, and what remains unverified. Only results that were actually observed are listed as verified.

## Scope

- Server: `python -m wps_ai_agent_cli mcp-server`, on the `main` branch.
- Transport: stdio only. The server has no HTTP or SSE transport, so clients that need a remote transport cannot use it yet.
- Protocol: `2025-11-25`, the only version in `SUPPORTED_MCP_PROTOCOL_VERSIONS`.

## Client matrix

| Client | Status | Evidence |
| --- | --- | --- |
| Claude Code CLI 2.1.296 | **Verified** | Runs `claude -p` with `--mcp-config` and `--strict-mcp-config`. Eight fixed tasks, judged from workspace state and tool calls; seven pass and the held-file task still needs a Windows or non-root run. See `docs/AGENT_E2E_EVAL.md`. |
| Codex CLI 0.162.1 | **Verified** | stdio. 2026-10-14, commit `12c1577`, Windows 10.0.19045. Client `codex-mcp-client` / Codex `0.162.1` requested `2025-06-18`; negotiated `2025-11-25`. Two `tools/list` pages (50 then 35), `tools_listed` 85, `all_pages_read` true. One `wps_agent_tasks` call answered, `is_error` false. See “Codex CLI run”. |
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
3. **Twelve evaluation tasks are still a small set.** Eight run offline; four exercise WPS write paths (spreadsheet write, Writer and presentation replace, a held file) but need WPS on Windows and have not been run there yet. The full tool surface is not covered.

## What would close the gaps

- For Claude Desktop: configure the server in `claude_desktop_config.json`, then repeat the P3-263 audit with the desktop inspection channel working. Record client version, transport, negotiated protocol, full pagination and one safe `tools/call`.
- For HTTP clients: a transport decision is needed first. It is not a documentation change.
- For other clients: pick the clients that matter and run the same checks.

## Codex CLI run

- Date: 2026-10-14
- Commit: `12c1577` (`p4-008-codex-mcp-check`)
- Machine: Windows 10.0.19045. The server was started with the Codex primary-runtime `python.exe`, not the WindowsApps alias.
- Codex version: `0.162.1` (`codex --version` and the session banner). Session model: `gpt-6.1-sol`.
- Transport: stdio (`codex mcp get wps-agent`).
- Protocol: requested `2025-06-18`, negotiated `2025-11-25`. `initialized_notification` is true. The versions differ, and the server accepted the negotiation; `errors` is empty.
- `/mcp`: not shown. The temp directory is not a trusted Codex directory, so the session was `codex exec` in a new empty git repo under `%TEMP%\wps-p4\codex-session`, as the runbook allows when the interactive UI is not used. Handshake evidence is the recorder log.
- Pages: 50 tools (`next_cursor` `YzkzZjlhZTEzNjc4NWMwYjo1MA`), then 35 with that cursor and no further cursor. `tools_listed` 85, matching `config/mcp_catalog_guard.json`. `all_pages_read` true.
- Call: `wps_agent_tasks` with `phase` `phase4`, `answered` true, `is_error` false. Codex said it returned 14 tasks.
- `errors`: `[]`

```json
{
  "client_info": {"name": "codex-mcp-client", "title": "Codex", "version": "0.162.1"},
  "requested_protocol": "2025-06-18",
  "negotiated_protocol": "2025-11-25",
  "server_info": {"name": "wps-ai-agent-cli", "version": "0.1.0"},
  "initialized_notification": true,
  "tools_list_pages": [
    {"cursor": null, "tools": 50, "next_cursor": "YzkzZjlhZTEzNjc4NWMwYjo1MA"},
    {"cursor": "YzkzZjlhZTEzNjc4NWMwYjo1MA", "tools": 35, "next_cursor": null}
  ],
  "tools_listed": 85,
  "all_pages_read": true,
  "tool_calls": [{"name": "wps_agent_tasks", "answered": true, "is_error": false}],
  "errors": []
}
```

The raw JSONL log stayed on this machine and is not in the repository.

Note for P4-014: Codex asked for `2025-06-18` and the server, which supports only `2025-11-25`, answered with that version. Codex accepted it and continued, as the MCP version negotiation allows. A client that refuses a newer version than it asked for would not connect; supporting `2025-06-18` as well is a decision for P4-014, not a fix for this run.

## Follow-up

Codex CLI over stdio has been run. Claude Desktop remains unverified.

## Decision still needed

Whether the desktop-client check is a condition for closing Phase 3 item 4, or whether the Claude Code CLI evidence is enough for this phase.
