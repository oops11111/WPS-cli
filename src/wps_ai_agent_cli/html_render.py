from __future__ import annotations

import json
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
import shutil
from typing import Any


_RENDERER = Path(__file__).with_name("html_render_playwright.cjs")
_EDGE_CANDIDATES = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
)
_MAX_HTML_BYTES = 10 * 1024 * 1024


def _resolve_browser_runtime() -> tuple[str | None, str | None]:
    node = os.environ.get("WPS_AGENT_NODE") or shutil.which("node")
    browser = os.environ.get("WPS_AGENT_EDGE") or shutil.which("msedge")
    if not browser:
        browser = next((str(path) for path in _EDGE_CANDIDATES if path.is_file()), None)
    return node, browser


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill Node and any Edge children left behind after a render timeout."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            check=False,
            capture_output=True,
            text=True,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except OSError:
            pass


def _run_renderer(
    node: str,
    request: dict[str, Any],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True
    process = subprocess.Popen(
        [node, str(_RENDERER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        text=True,
        env={**os.environ, "WPS_AGENT_RENDER_FORMAT": request["format"]},
        start_new_session=start_new_session,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(
            input=json.dumps(request),
            timeout=timeout_seconds + 15,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except (subprocess.TimeoutExpired, ValueError):
            stdout = getattr(exc, "stdout", None) or ""
            stderr = getattr(exc, "stderr", None) or ""
            try:
                process.kill()
            except OSError:
                pass
        raise subprocess.TimeoutExpired(
            process.args, timeout_seconds + 15, output=stdout, stderr=stderr,
        ) from None
    return subprocess.CompletedProcess(process.args, process.returncode or 0, stdout or "", stderr or "")


def render_html(
    input_path: str | Path,
    output_path: str | Path,
    output_format: str,
    page_size: str = "A4",
    viewport_width: int = 1280,
    viewport_height: int = 900,
    timeout_seconds: int = 30,
    allow_javascript: bool = False,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    if output_format not in {"pdf", "png"}:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "output_format must be pdf or png."}]
    if source.suffix.casefold() not in {".html", ".htm"}:
        return False, {}, [{"code": "INVALID_INPUT", "message": "Input must be an .html or .htm file."}]
    if not source.is_file():
        return False, {}, [{"code": "INPUT_FILE_NOT_FOUND", "message": f"HTML input not found: {source}"}]
    if source.stat().st_size > _MAX_HTML_BYTES:
        return False, {}, [{"code": "INPUT_TOO_LARGE", "message": "HTML input exceeds the 10 MiB limit."}]
    if destination.suffix.casefold() != f".{output_format}":
        return False, {}, [{"code": "OUTPUT_EXTENSION_MISMATCH", "message": f"Output extension must be .{output_format}."}]
    if source == destination:
        return False, {}, [{"code": "INVALID_OUTPUT", "message": "Output path must differ from the input."}]
    if destination.exists():
        return False, {}, [{"code": "OUTPUT_ALREADY_EXISTS", "message": f"Refusing to overwrite existing output: {destination}"}]
    if not destination.parent.is_dir():
        return False, {}, [{"code": "OUTPUT_DIRECTORY_NOT_FOUND", "message": f"Output directory does not exist: {destination.parent}"}]
    if page_size not in {"A4", "Letter", "Legal", "Tabloid"}:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "page_size must be A4, Letter, Legal, or Tabloid."}]
    if not 320 <= viewport_width <= 3_840 or not 240 <= viewport_height <= 2_160:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Viewport must be within 320x240 and 3840x2160."}]
    if not 1 <= timeout_seconds <= 120:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "timeout_seconds must be between 1 and 120."}]
    node, browser = _resolve_browser_runtime()
    if not node or not browser:
        return False, {}, [{"code": "BROWSER_BACKEND_UNAVAILABLE", "message": "Node.js and Microsoft Edge are required; configure WPS_AGENT_NODE and WPS_AGENT_EDGE if they are not on the standard paths."}]
    if not _RENDERER.is_file():
        return False, {}, [{"code": "BROWSER_BACKEND_UNAVAILABLE", "message": f"Browser renderer script is missing: {_RENDERER}"}]

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=f".tmp.{output_format}", dir=destination.parent)
    os.close(descriptor)
    temporary_output = Path(temporary_name)
    temporary_output.unlink()
    request = {
        "input_path": str(source),
        "resource_root": str(source.parent),
        "output_path": str(temporary_output),
        "format": output_format,
        "page_size": page_size,
        "viewport_width": viewport_width,
        "viewport_height": viewport_height,
        "timeout_seconds": timeout_seconds,
        "allow_javascript": allow_javascript,
        "browser_executable": browser,
    }
    try:
        completed = _run_renderer(node, request, timeout_seconds)
    except subprocess.TimeoutExpired:
        temporary_output.unlink(missing_ok=True)
        return False, {}, [{"code": "RENDER_TIMEOUT", "message": f"HTML rendering exceeded {timeout_seconds} seconds."}]
    except OSError as exc:
        temporary_output.unlink(missing_ok=True)
        return False, {}, [{"code": "BROWSER_BACKEND_UNAVAILABLE", "message": str(exc)}]
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        temporary_output.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout).strip()[:1_000]
        return False, {}, [{"code": "RENDER_FAILED", "message": detail or "Browser renderer returned invalid JSON."}]
    if completed.returncode != 0 or not payload.get("ok"):
        temporary_output.unlink(missing_ok=True)
        return False, {"diagnostic": payload}, [{"code": payload.get("code", "RENDER_FAILED"), "message": payload.get("message", "HTML rendering failed.")}]
    try:
        artifact = temporary_output.read_bytes()
    except OSError as exc:
        temporary_output.unlink(missing_ok=True)
        return False, {}, [{"code": "RENDER_OUTPUT_MISSING", "message": str(exc)}]
    valid_signature = artifact.startswith(b"%PDF-") if output_format == "pdf" else artifact.startswith(b"\x89PNG\r\n\x1a\n")
    if not artifact or not valid_signature:
        temporary_output.unlink(missing_ok=True)
        return False, {"diagnostic": payload}, [{"code": "RENDER_OUTPUT_INVALID", "message": "Browser output was empty or did not match the requested format."}]
    try:
        # A hard link fails if the destination appeared after the earlier existence check.
        os.link(temporary_output, destination)
    except FileExistsError:
        return False, {}, [{"code": "OUTPUT_ALREADY_EXISTS", "message": f"Refusing to overwrite existing output: {destination}"}]
    except OSError as exc:
        return False, {}, [{"code": "OUTPUT_WRITE_FAILED", "message": str(exc)}]
    finally:
        temporary_output.unlink(missing_ok=True)
    result = {
        "input_path": str(source), "output_path": str(destination),
        "format": output_format, "bytes": len(artifact),
        "sha256": hashlib.sha256(artifact).hexdigest(),
        "backend": "playwright-edge", "page_size": page_size if output_format == "pdf" else None,
        "viewport": {"width": viewport_width, "height": viewport_height},
        "javascript_enabled": allow_javascript,
        "network_access": False,
        "websocket_blocked": True,
        "resource_root": str(source.parent),
        "browser": payload.get("browser"),
        "page_title": payload.get("page_title"),
        "document_height": payload.get("document_height"),
    }
    return True, result, []
