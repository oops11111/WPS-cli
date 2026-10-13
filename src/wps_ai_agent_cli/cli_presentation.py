"""Presentation document commands."""

from __future__ import annotations

from .models import CommandResponse, ValidationResult
from .presentation_ops import presentation_replace
from .cli_common import BACKEND


def presentation_replace_response(
    request_id: str,
    document_id: str,
    find_text: str,
    replace_text: str,
    dry_run: bool,
    slide_index: int | None,
) -> CommandResponse:
    ok, result, errors, replayed = presentation_replace(
        document_id=document_id,
        find_text=find_text,
        replace_text=replace_text,
        request_id=request_id,
        dry_run=dry_run,
        slide_index=slide_index,
    )
    return CommandResponse(
        ok=ok,
        command="presentation-replace",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Presentation replace request replayed from idempotency record."
            if replayed
            else "Presentation replace dry-run completed."
            if dry_run and ok
            else "Presentation replace completed."
            if ok
            else "Presentation replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "matches_found",
                    "passed": bool(result.get("matches", 0) > 0),
                    "details": result.get("matches"),
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "replacement_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "remaining_find_count": result.get("remaining_find_count"),
                        "replace_count_delta": result.get("replace_count_delta"),
                    },
                },
            ],
        ),
        errors=errors,
    )
