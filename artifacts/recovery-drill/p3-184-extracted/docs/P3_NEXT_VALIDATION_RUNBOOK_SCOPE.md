# P3-047 Next Non-Destructive Capability Scope

## Selected Target

Implement a read-only `validation-runbook` capability for the local-only Phase 3 workflow.

The command will return a structured local validation playbook that an agent or user can follow before handoff, packaging, optional WPS regression, or approval-gated cleanup.

## Scope

- Report quick local checks for unit tests, project status, workspace health, and local handoff.
- Report safe regression and MCP checks with current tool-count expectations.
- Report local package refresh and verification commands.
- Report optional WPS validation commands separately, clearly marked as WPS-launching.
- Report cleanup review commands and state that deletion still requires explicit user approval.
- Expose the same data through MCP as `wps_agent_validation_runbook`.

## Safety Constraints

- Read-only only.
- Do not execute validation commands.
- Do not launch WPS.
- Do not create packages.
- Do not delete files.
- Do not contact remote Git or cloud services.

## Validation

- Add unit tests for runbook sections, safety flags, and current project-state references.
- Add CLI parser and MCP schema coverage.
- Add the command to the safe regression profile after implementation.
- Refresh the MCP catalog drift baseline after reviewing the new read-only tool.
