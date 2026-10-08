# P3-044 Next Non-Destructive Capability Scope

## Selected Target

Implement a read-only `artifact-retention-summary` capability for the local-only Phase 3 workflow.

The command will summarize retained local evidence, current sync package state, cleanup candidates, and approval posture. It is intended to make continued workspace development easier without requiring remote Git, cloud upload, WPS launch, or file deletion.

## Scope

- Report the current repeatable sync package path, existence, size, and SHA256 evidence.
- Reuse `cleanup-plan` to list preserved latest regression evidence and approval-required cleanup candidates.
- Group cleanup candidates by category with counts, byte totals, and paths.
- State that deletion is not allowed without explicit user approval for exact paths or categories.
- Expose the same data through an MCP tool named `wps_agent_artifact_retention_summary`.

## Safety Constraints

- Read-only only.
- Do not delete files.
- Do not launch WPS.
- Do not create a new sync package.
- Do not contact remote Git or cloud services.
- Treat cleanup output as review evidence, not authorization.

## Validation

- Add focused unit tests for retained evidence, candidate grouping, sync package reporting, and no-deletion posture.
- Add CLI parser and MCP schema coverage.
- Add the command to the safe regression profile after implementation.
- Refresh the MCP catalog guard baseline after reviewing the new read-only tool count.
