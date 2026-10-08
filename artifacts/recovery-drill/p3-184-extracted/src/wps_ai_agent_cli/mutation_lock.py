from __future__ import annotations

import functools
import hashlib
import inspect
import os
from contextlib import ExitStack
from pathlib import Path
import time
from typing import Any, Callable


DEFAULT_TIMEOUT_SECONDS = 30.0


class DocumentBusyError(Exception):
    pass


def _try_lock(stream) -> bool:
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(stream) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class document_mutation_lock:
    def __init__(self, document_id: str, workspace: str | Path = ".", timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:32]
        self.path = Path(workspace).resolve() / ".wps-agent" / "locks" / f"{digest}.lock"
        self.timeout_seconds = timeout_seconds
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            deadline = time.monotonic() + self.timeout_seconds
            while not _try_lock(stream):
                if time.monotonic() >= deadline:
                    raise DocumentBusyError("Document mutation is already active in this workspace.")
                time.sleep(0.05)
            self.stream = stream
            return self
        except BaseException:
            stream.close()
            raise

    def __exit__(self, exc_type, exc, traceback):
        if self.stream is not None:
            try:
                try:
                    _unlock(self.stream)
                except OSError:
                    pass
            finally:
                self.stream.close()
                self.stream = None


def coordinated_mutation(operation: Callable[..., Any]) -> Callable[..., Any]:
    signature = inspect.signature(operation)

    @functools.wraps(operation)
    def wrapped(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        document_id = bound.arguments.get("document_id")
        if document_id is None:
            return operation(*args, **kwargs)
        workspace = bound.arguments.get("workspace", ".")
        request_id = bound.arguments.get("request_id")
        try:
            with ExitStack() as locks:
                if request_id is not None:
                    locks.enter_context(document_mutation_lock(f"request:{request_id}", workspace, DEFAULT_TIMEOUT_SECONDS))
                locks.enter_context(document_mutation_lock(str(document_id), workspace, DEFAULT_TIMEOUT_SECONDS))
                return operation(*args, **kwargs)
        except DocumentBusyError as exc:
            return False, {"document_id": document_id}, [{"code": "DOCUMENT_BUSY", "message": str(exc)}], False

    return wrapped


def coordinated_request(operation: Callable[..., Any]) -> Callable[..., Any]:
    signature = inspect.signature(operation)

    @functools.wraps(operation)
    def wrapped(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        request_id = bound.arguments.get("request_id")
        if request_id is None:
            return operation(*args, **kwargs)
        workspace = bound.arguments.get("workspace", ".")
        try:
            with document_mutation_lock(f"request:{request_id}", workspace, DEFAULT_TIMEOUT_SECONDS):
                return operation(*args, **kwargs)
        except DocumentBusyError as exc:
            return False, {"request_id": request_id}, [{"code": "DOCUMENT_BUSY", "message": str(exc)}], False

    return wrapped
