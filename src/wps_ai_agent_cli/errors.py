from __future__ import annotations

COM_BACKEND_UNAVAILABLE = "COM_BACKEND_UNAVAILABLE"
INPUT_FILE_NOT_FOUND = "INPUT_FILE_NOT_FOUND"
UNSUPPORTED_COMPONENT = "UNSUPPORTED_COMPONENT"
COM_OPERATION_FAILED = "COM_OPERATION_FAILED"
COM_OPERATION_TIMEOUT = "COM_OPERATION_TIMEOUT"
ROLLED_BACK = "MUTATION_ROLLED_BACK"
ROLLBACK_FAILED = "MUTATION_ROLLBACK_FAILED"
ROLLBACK_BLOCKED = "MUTATION_ROLLBACK_BLOCKED"
ROLLBACK_IN_WPS_FAILED = "MUTATION_ROLLBACK_IN_WPS_FAILED"
DOCUMENT_IDENTITY_UNAVAILABLE = "DOCUMENT_IDENTITY_UNAVAILABLE"
DOCUMENT_HELD_OPEN = "DOCUMENT_HELD_OPEN"
# WPS refused to close a document with no unsaved changes, and still lists it (P8-006).
WPS_CLOSE_REFUSED = "WPS_CLOSE_REFUSED"

# Shared with wps_script_snippets.Assert-WpsFileNotHeld and file_hold, so a refusal raised on either side maps to
# DOCUMENT_HELD_OPEN.
HELD_OPEN_MARKER = "is held open by another handle"


class OperationRecordError(OSError):
    """The mutation was applied, but its idempotency record could not be completed."""


class DocumentHeldOpenError(OSError):
    """The document could not be read because another handle, usually WPS, holds it open."""


def identity_error(exc: BaseException) -> dict[str, str]:
    """Error entry for a failed identity read: DOCUMENT_HELD_OPEN when the file is held, else unavailable."""
    code = DOCUMENT_HELD_OPEN if isinstance(exc, DocumentHeldOpenError) else DOCUMENT_IDENTITY_UNAVAILABLE
    return {"code": code, "message": str(exc)}
