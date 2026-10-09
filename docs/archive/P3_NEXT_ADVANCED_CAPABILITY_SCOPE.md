# P3-030 Next Advanced Capability Selection

## Selected Target

Next non-destructive Phase 3 target:

```text
MCP tool catalog snapshot
```

## Why This Target

The project now has 46 MCP-facing tools. A compact, read-only catalog snapshot will make future local development easier by exposing:

- total tool count
- categories
- mutating tool count
- WPS-required tool count
- read-only maintenance/status tools
- current safety posture for mutating tools

This target is useful before adding more WPS automation because it gives a quick way to audit the tool surface without reading the full schema list.

## Scope

Add a read-only command:

```powershell
python -m wps_ai_agent_cli mcp-catalog-snapshot
```

Expected output:

- `tool_count`
- `category_counts`
- `mutating_tool_count`
- `requires_wps_tool_count`
- `read_only_tool_count`
- `maintenance_tools`
- `safety_notes_missing_count`
- `schema_version`

## Out of Scope

- No WPS launch.
- No document mutation.
- No cleanup execution.
- No remote Git, upload, or cloud synchronization.
- No changes to MCP transport behavior.

## Validation

Minimum validation:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli mcp-catalog-snapshot
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

Acceptance for the future implementation task:

- Snapshot command passes.
- Tool count matches `mcp-tools`.
- Mutating tools with `mutates_document=true` still expose safety notes.
- Safe regression remains 6/6.
