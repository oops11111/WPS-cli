from __future__ import annotations


COM_BACKEND_UNAVAILABLE = "COM_BACKEND_UNAVAILABLE"
INPUT_FILE_NOT_FOUND = "INPUT_FILE_NOT_FOUND"
UNSUPPORTED_COMPONENT = "UNSUPPORTED_COMPONENT"
COM_OPERATION_FAILED = "COM_OPERATION_FAILED"
COM_OPERATION_TIMEOUT = "COM_OPERATION_TIMEOUT"


class OperationRecordError(OSError):
    """The mutation was applied, but its idempotency record could not be completed."""
