from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_status import build_project_status


def _step(command: str, purpose: str, launches_wps: bool = False, mutates_files: bool = False) -> dict[str, Any]:
    return {
        "command": command,
        "purpose": purpose,
        "launches_wps": launches_wps,
        "mutates_files": mutates_files,
    }


def build_validation_runbook(workspace: Path | str = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    status = build_project_status(workspace_path)
    tool_count = status["mcp_tool_count"]

    sections = [
        {
            "id": "quick-local-checks",
            "title": "Quick local checks",
            "description": "Read current local status without WPS or package creation.",
            "steps": [
                _step("python -m unittest discover -s tests", "Run the full local unit test suite."),
                _step("python -m wps_ai_agent_cli project-status", "Confirm next task, package hash, MCP count, and cleanup posture."),
                _step("python -m wps_ai_agent_cli workspace-health", "Confirm local workspace health checks pass."),
                _step("python -m wps_ai_agent_cli local-handoff-summary", "Confirm local handoff readiness."),
            ],
        },
        {
            "id": "safe-regression",
            "title": "Safe regression",
            "description": "Run CI-friendly checks that do not launch WPS.",
            "steps": [
                _step(
                    "python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\\regression\\safe",
                    "Run the safe regression profile and write a timestamped artifact.",
                ),
                _step(
                    f"python -m wps_ai_agent_cli mcp-smoke --expected-min-tools {tool_count} --tool-name wps_agent_tasks",
                    "Verify initialize, tools/list, and tools/call.",
                ),
                _step(
                    (
                        "python -m wps_ai_agent_cli mcp-config-audit --config "
                        f"config\\mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools {tool_count}"
                    ),
                    "Verify local MCP client configuration and tools/list startup.",
                ),
            ],
        },
        {
            "id": "mutation-recovery",
            "title": "Mutation recovery",
            "description": "Inspect request evidence before any decision to retry or restore.",
            "steps": [
                _step(
                    "python -m wps_ai_agent_cli mutation-request-inspect --request <request-id>",
                    "Read the main operation, derived backup, source identity, and non-destructive recovery guidance.",
                ),
            ],
        },
        {
            "id": "package-refresh",
            "title": "Package refresh",
            "description": "Refresh the repeatable local sync package after code or documentation changes.",
            "steps": [
                _step(
                    "python -m wps_ai_agent_cli cloud-sync-package --output artifacts\\cloud-sync\\wps-ai-agent-cli-phase3-sync-cli.zip",
                    "Create the local portable package.",
                    mutates_files=True,
                ),
                _step("python -m wps_ai_agent_cli project-status", "Read back the package hash and entry evidence."),
            ],
        },
        {
            "id": "optional-wps-validation",
            "title": "Optional WPS validation",
            "description": "Run only when desktop WPS validation is intended.",
            "steps": [
                _step(
                    "python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\\regression\\wps",
                    "Run WPS-required smoke scenarios.",
                    launches_wps=True,
                    mutates_files=True,
                ),
                _step("python -m wps_ai_agent_cli wps-process-audit", "Inspect WPS-related processes without terminating them."),
            ],
        },
        {
            "id": "cleanup-review",
            "title": "Cleanup review",
            "description": "Review candidates only; deletion still requires explicit user approval.",
            "steps": [
                _step("python -m wps_ai_agent_cli cleanup-plan", "Review cleanup candidates without deleting files."),
                _step(
                    "python -m wps_ai_agent_cli cleanup-approval-manifest",
                    "Review exact categories and paths before any separate approval-gated cleanup.",
                ),
                _step("python -m wps_ai_agent_cli artifact-retention-summary", "Review retained evidence and cleanup approval posture."),
            ],
        },
    ]

    checks = [
        {"name": "runbook_is_read_only", "passed": True, "details": "The runbook does not execute commands."},
        {
            "name": "remote_git_not_required",
            "passed": status["remote_git_required"] is False,
            "details": "Local-only workflow.",
        },
        {
            "name": "next_task_available",
            "passed": len(status["next_tasks"]) >= 1,
            "details": [task["id"] for task in status["next_tasks"]],
        },
        {
            "name": "wps_steps_are_optional",
            "passed": any(section["id"] == "optional-wps-validation" for section in sections),
            "details": "WPS-launching commands are isolated in an optional section.",
        },
    ]

    return {
        "workspace": str(workspace_path),
        "read_only": True,
        "commands_executed": False,
        "launches_wps": False,
        "creates_package": False,
        "deletion_performed": False,
        "runbook_status": "passed" if all(check["passed"] for check in checks) else "warning",
        "checks": checks,
        "mcp_tool_count": tool_count,
        "next_tasks": status["next_tasks"],
        "sections": sections,
        "approval_policy": {
            "cleanup_deletion_requires_user_approval": True,
            "remote_git_required": status["remote_git_required"],
        },
    }
