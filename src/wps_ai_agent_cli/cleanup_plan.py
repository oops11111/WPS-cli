from __future__ import annotations

from pathlib import Path
from typing import Any


PROBE_FIXTURE_NAMES = {
    "phase0_calculation_smoke_after_profile.xlsx",
    "phase0_calculation_smoke_inprocess_probe.xlsx",
    "phase0_calculation_smoke_timeout_probe.xlsx",
}

PROTECTED_PATHS = [
    "src",
    "tests",
    "config",
    "docs",
    "fixtures/phase0",
    "fixtures/phase3/phase0_calculation_smoke.xlsx",
    "fixtures/phase3/writer_smoke_copy.docx",
    "fixtures/phase3/writer_smoke.pdf",
    "fixtures/phase3/writer_table_fixture.docx",
    "fixtures/phase3/writer_table_regression_smoke.docx",
    "artifacts/cloud-sync/wps-ai-agent-cli-phase3-sync-cli.zip",
]


def _file_item(
    path: Path,
    workspace: Path,
    category: str,
    reason: str,
    default_action: str,
    requires_user_approval: bool = True,
) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.relative_to(workspace)),
        "category": category,
        "reason": reason,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
        "requires_user_approval": requires_user_approval,
        "default_action": default_action,
    }


def _existing_files(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted((path for path in root.glob(pattern) if path.is_file()), key=lambda item: (item.stat().st_mtime, item.name))


def build_cleanup_plan(workspace: Path | str = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    candidates: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []

    phase3_fixtures = workspace_path / "fixtures" / "phase3"
    for path in _existing_files(phase3_fixtures, "*.xlsx"):
        if path.name in PROBE_FIXTURE_NAMES:
            candidates.append(
                _file_item(
                    path,
                    workspace_path,
                    "probe_fixture",
                    "Investigation probe output superseded by the stable Phase 3 spreadsheet smoke fixture.",
                    "keep_until_approved",
                )
            )

    for profile in ("safe", "wps"):
        profile_dir = workspace_path / "artifacts" / "regression" / profile
        artifacts = _existing_files(profile_dir, "regression-run-*.json")
        if artifacts:
            latest = artifacts[-1]
            preserved.append(
                _file_item(
                    latest,
                    workspace_path,
                    f"latest_{profile}_regression_artifact",
                    f"Latest {profile} regression evidence retained for local handoff.",
                    "keep",
                    False,
                )
            )
        for path in artifacts[:-1]:
            candidates.append(
                _file_item(
                    path,
                    workspace_path,
                    f"superseded_{profile}_regression_artifact",
                    f"Older {profile} regression artifact superseded by the latest retained artifact.",
                    "keep_until_approved",
                )
            )

    cloud_sync_dir = workspace_path / "artifacts" / "cloud-sync"
    for path in _existing_files(cloud_sync_dir, "*.zip"):
        if path.name != "wps-ai-agent-cli-phase3-sync-cli.zip":
            candidates.append(
                _file_item(
                    path,
                    workspace_path,
                    "superseded_sync_package",
                    "Older manually generated sync package superseded by the repeatable CLI package.",
                    "keep_until_approved",
                )
            )

    backups_dir = workspace_path / ".wps-agent" / "backups"
    backup_files = _existing_files(backups_dir, "**/*")
    if backup_files:
        total_size = sum(path.stat().st_size for path in backup_files)
        candidates.append(
            {
                "path": ".wps-agent/backups",
                "category": "backup_retention_review",
                "reason": "Recoverability evidence should be reviewed as a set before deleting individual backups.",
                "file_count": len(backup_files),
                "size_bytes": total_size,
                "requires_user_approval": True,
                "default_action": "keep_until_approved",
            }
        )

    total_candidate_bytes = sum(int(item.get("size_bytes", 0)) for item in candidates)
    return {
        "workspace": str(workspace_path),
        "read_only": True,
        "deletion_performed": False,
        "approval_required": True,
        "retention_policy": [
            "Never delete files unless the user explicitly approves the exact candidate path or category.",
            "Always keep source, tests, config, docs, required fixtures, and the latest safe and WPS regression evidence.",
            "Keep WPS recovery backups by default; review them as a group before any removal.",
            "Prefer regenerating cleanup candidates through this read-only plan before asking for deletion approval.",
        ],
        "protected_paths": PROTECTED_PATHS,
        "preserved_evidence": preserved,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "total_candidate_bytes": total_candidate_bytes,
        "dry_run_commands": [
            "python -m wps_ai_agent_cli cleanup-plan",
            "Get-ChildItem fixtures\\phase3 -File",
            "Get-ChildItem artifacts\\regression -Recurse -File",
            "Get-ChildItem .wps-agent\\backups -Recurse -File",
        ],
    }
