from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from .html_editable import convert_html_editable
from .html_render import render_html
from . import task_status


_MAX_FILES = 100
_MAX_TOTAL_INPUT_BYTES = 500 * 1024 * 1024
_MAX_REPLAY_MANIFEST_BYTES = 2 * 1024 * 1024
_MAX_REQUEST_REGISTRY_BYTES = 4 * 1024 * 1024
_MAX_REQUEST_RECORD_BYTES = 16 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request_registry_path() -> Path:
    return task_status.task_status_state_path().with_name("html_batch_requests.json")


def _request_record_path(request_id: str) -> Path:
    name = hashlib.sha256(request_id.encode("utf-8")).hexdigest() + ".json"
    return _request_registry_path().with_suffix("") / name


def inspect_batch_request(request_id: str, verify: bool = False) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    if not request_id:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "request_id is required."}]
    record_path = _request_record_path(request_id)
    legacy_path = _request_registry_path()
    if record_path.parent.is_symlink():
        return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_INVALID", "message": "Request record directory is a symlink."}]
    if record_path.exists():
        path, origin, max_bytes = record_path, "current", _MAX_REQUEST_RECORD_BYTES
    elif legacy_path.exists():
        path, origin, max_bytes = legacy_path, "legacy", _MAX_REQUEST_REGISTRY_BYTES
    else:
        return False, {}, [{"code": "BATCH_REQUEST_NOT_FOUND", "message": "Batch request record was not found."}]
    try:
        if path.is_symlink() or path.stat().st_size > max_bytes:
            raise ValueError("Request record is a symlink or exceeds its size limit.")
        stored = json.loads(path.read_text(encoding="utf-8"))
        if origin == "legacy":
            if not isinstance(stored, dict) or not isinstance(stored.get("requests"), dict):
                raise ValueError("Legacy request registry is invalid.")
            record = stored["requests"].get(request_id)
            if record is None:
                return False, {}, [{"code": "BATCH_REQUEST_NOT_FOUND", "message": "Batch request record was not found."}]
        else:
            record = stored
        if (not isinstance(record, dict) or (origin == "current" and record.get("request_id") != request_id)
                or not isinstance(record.get("arguments"), dict)
                or record.get("state") not in {"running", "succeeded", "failed", "cancelled"}):
            raise ValueError("Request record fields are invalid.")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_INVALID", "message": "Batch request record cannot be trusted."}]
    arguments = record["arguments"]
    output_directory = arguments.get("output_directory")
    manifest_path = str(Path(output_directory) / "batch-conversion-manifest.json") if isinstance(output_directory, str) else None
    guidance = {
        "running": "Inspect the manifest; retry this request only when complete output evidence can be verified.",
        "succeeded": "Retry the same request and arguments to verify the files and replay the result.",
        "failed": "Review partial outputs and start a new request after cleanup.",
        "cancelled": "Review the partial manifest and start a new request after cleanup.",
    }
    result = {
        "request_id": request_id, "state": record["state"], "arguments": arguments,
        "manifest_path": manifest_path, "record_path": str(path), "record_origin": origin,
        "recovery_guidance": guidance[record["state"]],
        "evidence_status": "not_checked",
    }
    if verify:
        result["evidence_status"] = "failed"
        try:
            source_root = Path(arguments["source_directory"]).expanduser().resolve()
            output_root = Path(arguments["output_directory"]).expanduser().resolve()
            mode = arguments["mode"]
            recursive = arguments["recursive"]
            if not isinstance(recursive, bool) or mode not in {"pdf", "png", "docx"} or not source_root.is_dir():
                raise ValueError("Request arguments no longer identify a valid batch source.")
            iterator = source_root.rglob("*") if recursive else source_root.iterdir()
            sources = sorted(
                (item.resolve() for item in iterator if not item.is_symlink() and item.is_file() and item.suffix.casefold() in {".html", ".htm"}),
                key=lambda item: str(item).casefold(),
            )
            if (not sources or len(sources) > _MAX_FILES
                    or sum(item.stat().st_size for item in sources) > _MAX_TOTAL_INPUT_BYTES):
                raise ValueError("Current source inventory exceeds replay limits or is empty.")
            manifest = output_root / "batch-conversion-manifest.json"
            if not manifest.is_file():
                raise ValueError("Batch manifest is missing.")
            verified, _, replay_errors = _replay_batch(manifest, sources, source_root, output_root, mode, recursive, request_id)
            if not verified:
                raise ValueError(replay_errors[0]["message"] if replay_errors else "Batch evidence differs from the record.")
        except (KeyError, OSError, ValueError, TypeError) as exc:
            result["evidence_summary"] = str(exc)[:500]
        else:
            result["evidence_status"] = "passed"
            result["evidence_summary"] = "Complete manifest and current source/output hashes verified."
    return True, result, []


def _store_request_record(path: Path, record: dict[str, Any]) -> bool:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(payload) > _MAX_REQUEST_RECORD_BYTES:
        return False
    if path.parent.is_symlink():
        raise ValueError("Batch request directory cannot be a symlink.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent,
                                         prefix=".html-batch-request-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def _batch_request_state(request_id: str, arguments: dict[str, Any], register: bool) -> tuple[str, dict[str, str] | None]:
    record_path = _request_record_path(request_id)
    legacy_path = _request_registry_path()
    with task_status._status_transaction("."):
        if record_path.parent.is_symlink():
            return "invalid", None
        existing = None
        if record_path.exists():
            if record_path.is_symlink() or record_path.stat().st_size > _MAX_REQUEST_RECORD_BYTES:
                return "invalid", None
            try:
                existing = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return "invalid", None
            if not isinstance(existing, dict) or existing.get("request_id") != request_id:
                return "invalid", None
        elif legacy_path.exists():
            if legacy_path.is_symlink() or legacy_path.stat().st_size > _MAX_REQUEST_REGISTRY_BYTES:
                return "invalid", None
            try:
                registry = json.loads(legacy_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return "invalid", None
            if not isinstance(registry, dict) or not isinstance(registry.get("requests"), dict):
                return "invalid", None
            existing = registry["requests"].get(request_id)
        if existing is not None:
            if not isinstance(existing, dict) or existing.get("arguments") != arguments:
                return "conflict", None
            return str(existing.get("state", "invalid")), existing
        if not register:
            return "missing", None
        record = {"request_id": request_id, "arguments": arguments, "state": "running"}
        if not _store_request_record(record_path, record):
            return "capacity", None
        return "created", record


def _finish_batch_request(request_id: str, state: str) -> None:
    path = _request_record_path(request_id)
    with task_status._status_transaction("."):
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            registry = json.loads(_request_registry_path().read_text(encoding="utf-8"))
            record = {"request_id": request_id, **registry["requests"][request_id]}
        record["state"] = state
        if not _store_request_record(path, record):
            raise ValueError("Batch request record exceeded its size limit.")


def _replay_batch(manifest_path: Path, sources: list[Path], source_root: Path,
                  output_root: Path, mode: str, recursive: bool, request_id: str) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    def reject(code: str, message: str):
        return False, {}, [{"code": code, "message": message}]

    if manifest_path.is_symlink() or manifest_path.stat().st_size > _MAX_REPLAY_MANIFEST_BYTES:
        return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch manifest cannot be trusted for replay.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch manifest is unreadable for replay.")
    if not isinstance(manifest, dict) or not manifest.get("request_id"):
        return reject("OUTPUT_ALREADY_EXISTS", "Existing batch manifest has no replay request identity.")
    expected = {
        "schema_version": "wps-agent-batch-conversion/v1",
        "request_id": request_id,
        "mode": mode,
        "source_directory": str(source_root),
        "output_directory": str(output_root),
        "recursive": recursive,
        "manifest_path": str(manifest_path),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        return reject("BATCH_REPLAY_CONFLICT", "Batch request identity or arguments differ from the existing manifest.")
    summary = manifest.get("summary")
    files = manifest.get("files")
    if (not isinstance(summary, dict) or not isinstance(files, list) or manifest.get("cancelled")
            or len(files) != len(sources) or summary.get("total") != len(sources)
            or summary.get("processed") != len(sources) or summary.get("passed") != len(sources)
            or summary.get("failed") != 0 or summary.get("cancelled")):
        return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch manifest does not describe a completed successful conversion.")
    total_output_bytes = 0
    for source, item in zip(sources, files):
        if not isinstance(item, dict):
            return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch manifest file entry is invalid.")
        relative = source.relative_to(source_root)
        destination = (output_root / relative).with_suffix(f".{mode}")
        if (item.get("source") != str(source) or item.get("relative_source") != relative.as_posix()
                or item.get("output") != str(destination) or item.get("status") != "passed"
                or destination.is_symlink() or not destination.is_file()):
            return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch file inventory or output path changed.")
        source_bytes = source.stat().st_size
        output_bytes = destination.stat().st_size
        total_output_bytes += output_bytes
        if (total_output_bytes > _MAX_TOTAL_INPUT_BYTES or item.get("source_bytes") != source_bytes
                or item.get("output_bytes") != output_bytes or item.get("source_sha256") != _sha256(source)
                or item.get("output_sha256") != _sha256(destination)):
            return reject("BATCH_REPLAY_EVIDENCE_MISMATCH", "Batch source or output evidence changed.")
    return True, {**manifest, "replayed": True}, []


def convert_html_batch(
    input_directory: str | Path,
    output_directory: str | Path,
    mode: str,
    *,
    recursive: bool = False,
    request_id: str | None = None,
    progress_callback: Callable[[int, int, str], bool] | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source_root = Path(input_directory).expanduser().resolve()
    output_root = Path(output_directory).expanduser().resolve()
    if mode not in {"pdf", "png", "docx"}:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "mode must be pdf, png, or docx."}]
    if not source_root.is_dir():
        return False, {}, [{"code": "INPUT_DIRECTORY_NOT_FOUND", "message": f"Input directory not found: {source_root}"}]
    if source_root == output_root or source_root in output_root.parents:
        return False, {}, [{"code": "INVALID_OUTPUT", "message": "Output directory must be outside the input tree."}]

    iterator = source_root.rglob("*") if recursive else source_root.iterdir()
    sources = sorted(
        (path.resolve() for path in iterator if not path.is_symlink() and path.is_file() and path.suffix.casefold() in {".html", ".htm"}),
        key=lambda path: str(path).casefold(),
    )
    if not sources:
        return False, {}, [{"code": "NO_INPUT_FILES", "message": "No .html or .htm files were found."}]
    if len(sources) > _MAX_FILES:
        return False, {}, [{"code": "BATCH_LIMIT_EXCEEDED", "message": f"Batch contains {len(sources)} files; the maximum is {_MAX_FILES}."}]
    total_bytes = sum(path.stat().st_size for path in sources)
    if total_bytes > _MAX_TOTAL_INPUT_BYTES:
        return False, {}, [{"code": "BATCH_SIZE_LIMIT_EXCEEDED", "message": "Total batch input exceeds 500 MiB."}]

    arguments = {
        "source_directory": str(source_root), "output_directory": str(output_root),
        "mode": mode, "recursive": recursive,
    }
    request_state = "missing"
    if request_id:
        try:
            request_state, _record = _batch_request_state(request_id, arguments, register=False)
        except (OSError, ValueError, KeyError):
            return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_INVALID", "message": "Batch request registry could not be read safely."}]
        if request_state == "conflict":
            return False, {}, [{"code": "BATCH_REPLAY_CONFLICT", "message": "request_id belongs to different batch arguments."}]
        if request_state == "invalid":
            return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_INVALID", "message": "Batch request registry cannot be trusted."}]
        if request_state == "capacity":
            return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_FULL", "message": "Batch request record exceeds the storage limit."}]
        if request_state in {"failed", "cancelled"}:
            return False, {}, [{"code": "BATCH_REPLAY_UNAVAILABLE", "message": f"Batch request is {request_state}; use a new request_id after review."}]

    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, {}, [{"code": "OUTPUT_DIRECTORY_UNAVAILABLE", "message": str(exc)[:500]}]
    manifest_path = output_root / "batch-conversion-manifest.json"
    if manifest_path.exists():
        if request_id and request_state == "running":
            ok, replayed, errors = _replay_batch(manifest_path, sources, source_root, output_root, mode, recursive, request_id)
            if ok:
                try:
                    _finish_batch_request(request_id, "succeeded")
                except (OSError, ValueError, KeyError):
                    return False, replayed, [{"code": "BATCH_REQUEST_REGISTRY_WRITE_FAILED", "message": "Verified batch result could not be recorded as completed."}]
            return ok, replayed, errors
        if request_id and request_state == "succeeded":
            return _replay_batch(manifest_path, sources, source_root, output_root, mode, recursive, request_id)
        return False, {}, [{"code": "OUTPUT_ALREADY_EXISTS", "message": f"Refusing to overwrite batch manifest: {manifest_path}"}]
    if request_state == "running":
        return False, {}, [{"code": "BATCH_REPLAY_UNAVAILABLE", "message": "Batch request is running without a complete manifest."}]
    if request_state == "succeeded":
        return False, {}, [{"code": "BATCH_REPLAY_EVIDENCE_MISMATCH", "message": "Completed batch manifest is missing."}]
    if request_id:
        try:
            request_state, _record = _batch_request_state(request_id, arguments, register=True)
        except (OSError, ValueError, KeyError):
            return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_WRITE_FAILED", "message": "Batch request identity could not be persisted."}]
        if request_state != "created":
            if request_state == "capacity":
                return False, {}, [{"code": "BATCH_REQUEST_REGISTRY_FULL", "message": "Batch request record exceeds the storage limit."}]
            return False, {}, [{"code": "BATCH_REQUEST_IN_PROGRESS", "message": "Batch request was already claimed."}]

    results: list[dict[str, Any]] = []
    cancelled = False
    for source in sources:
        if progress_callback and not progress_callback(len(results), len(sources), f"Converting {source.name}"):
            cancelled = True
            break
        relative = source.relative_to(source_root)
        destination = (output_root / relative).with_suffix(f".{mode}")
        item: dict[str, Any] = {
            "source": str(source), "relative_source": relative.as_posix(),
            "output": str(destination), "status": "failed",
        }
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            item["source_bytes"] = source.stat().st_size
            item["source_sha256"] = _sha256(source)
            if mode == "docx":
                ok, data, errors = convert_html_editable(source, destination)
            else:
                ok, data, errors = render_html(source, destination, mode)
            item["status"] = "passed" if ok else "failed"
            item["conversion"] = data
            item["errors"] = errors
            if ok and destination.is_file():
                item["output_bytes"] = destination.stat().st_size
                item["output_sha256"] = _sha256(destination)
        except Exception as exc:  # noqa: BLE001
            item["errors"] = [{"code": "FILE_CONVERSION_FAILED", "message": str(exc)[:500]}]
        results.append(item)
        if progress_callback and not progress_callback(len(results), len(sources), f"Processed {source.name}"):
            cancelled = True
            break

    if not cancelled and progress_callback and not progress_callback(len(results), len(sources), "Writing batch manifest"):
        cancelled = True

    manifest = {
        "schema_version": "wps-agent-batch-conversion/v1",
        "request_id": request_id,
        "manifest_path": str(manifest_path),
        "mode": mode,
        "source_directory": str(source_root),
        "output_directory": str(output_root),
        "recursive": recursive,
        "cancelled": cancelled,
        "limits": {"max_files": _MAX_FILES, "max_total_input_bytes": _MAX_TOTAL_INPUT_BYTES},
        "summary": {
            "total": len(sources),
            "processed": len(results),
            "passed": sum(item["status"] == "passed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "cancelled": cancelled,
        },
        "files": results,
    }
    payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".batch-manifest.", suffix=".tmp", dir=output_root, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.link(temporary, manifest_path)
    except OSError as exc:
        errors = [{"code": "MANIFEST_WRITE_FAILED", "message": str(exc)[:500]}]
        if request_id:
            try:
                _finish_batch_request(request_id, "failed")
            except (OSError, ValueError, KeyError):
                errors.append({"code": "BATCH_REQUEST_REGISTRY_WRITE_FAILED", "message": "Batch failure state could not be persisted."})
        return False, manifest, errors
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    succeeded = manifest["summary"]["failed"] == 0 and not cancelled
    if request_id:
        try:
            _finish_batch_request(request_id, "succeeded" if succeeded else "cancelled" if cancelled else "failed")
        except (OSError, ValueError, KeyError):
            return False, manifest, [{"code": "BATCH_REQUEST_REGISTRY_WRITE_FAILED", "message": "Batch manifest was created, but terminal request state could not be persisted."}]
    return succeeded, manifest, []
