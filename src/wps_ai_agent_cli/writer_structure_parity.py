from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any
from zipfile import BadZipFile
import xml.etree.ElementTree as ET

from .capabilities import powershell_executable
from .document_text import docx_body_paragraphs
from .writer_structure import read_body_bookmark_text, read_supported_bookmark_text, read_writer_structure


FIXTURE = Path("fixtures/phase3/writer_structure_wps_fixture.docx")
SCRIPT = Path("scripts/audit_writer_structure_wps.ps1")
NESTED_FIXTURE = Path("fixtures/phase3/writer_nested_scope_wps_fixture.docx")
NESTED_SCOPES = {"BodyMark": "body_paragraph", "CellMark": "table",
                 "HeaderMark": "header_footer", "FooterMark": "header_footer"}
IMPLEMENTATION_FILES = (
    "src/wps_ai_agent_cli/writer_structure.py",
    "src/wps_ai_agent_cli/document_text.py",
    "src/wps_ai_agent_cli/writer_inspect.py",
    "src/wps_ai_agent_cli/writer_structure_parity.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def implementation_hashes(root: Path) -> dict[str, str]:
    return {relative: _sha256(root / relative) for relative in IMPLEMENTATION_FILES}


def _partition(values: list[str | None]) -> list[int]:
    labels: dict[str | None, int] = {}
    return [labels.setdefault(value, len(labels)) for value in values]


def compare_writer_structure(offline: dict[str, Any], observed: dict[str, Any]) -> list[dict[str, Any]]:
    paragraphs = observed.get("paragraphs", [])
    bookmarks = observed.get("bookmarks", [])
    if not isinstance(paragraphs, list):
        paragraphs = []
    if not isinstance(bookmarks, list):
        bookmarks = []
    wps_text = [item.get("text") for item in paragraphs if isinstance(item, dict)]
    wps_levels = [item.get("outline_level") for item in paragraphs if isinstance(item, dict)]
    wps_styles = [item.get("style") for item in paragraphs if isinstance(item, dict)]
    offline_styles = offline["style_ids"]
    wps_bookmarks = {item.get("name"): item.get("text") for item in bookmarks if isinstance(item, dict)}
    checks = [
        {"name": "read_only_open", "passed": observed.get("read_only") is True,
         "expected": True, "actual": observed.get("read_only")},
        {"name": "paragraph_text_and_order", "passed": wps_text == offline["paragraph_texts"] and observed.get("paragraph_count") == len(offline["paragraph_texts"]),
         "expected": offline["paragraph_texts"], "actual": wps_text},
        {"name": "heading_levels", "passed": wps_levels == [level if level is not None else 10 for level in offline["heading_levels"]],
         "expected": [level if level is not None else 10 for level in offline["heading_levels"]], "actual": wps_levels},
        {"name": "style_grouping", "passed": len(wps_styles) == len(offline_styles) and all(wps_styles) and _partition(wps_styles) == _partition(offline_styles),
         "expected": _partition(offline_styles), "actual": _partition(wps_styles),
         "representations": [{"ooxml_style_id": source, "wps_display_name": display} for source, display in zip(offline_styles, wps_styles)]},
        {"name": "bookmark_names_and_text", "passed": len(bookmarks) == len(offline["bookmarks"]) and wps_bookmarks == offline["bookmarks"],
         "expected": offline["bookmarks"], "actual": wps_bookmarks},
    ]
    return checks


def run_writer_structure_parity(
    workspace: str | Path = ".", run_wps: bool = False, timeout_seconds: int = 90,
    scope: str = "structure",
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    if scope == "nested":
        return run_writer_nested_parity(workspace, run_wps, timeout_seconds)
    if scope != "structure":
        return False, {"wps_launched": False}, [{"code": "INVALID_SCOPE", "message": "Scope must be structure or nested."}]
    if not run_wps:
        return False, {"wps_launched": False}, [{"code": "WPS_OPT_IN_REQUIRED", "message": "Pass --run-wps to launch read-only WPS corroboration."}]
    if not 1 <= timeout_seconds <= 300:
        return False, {"wps_launched": False}, [{"code": "INVALID_TIMEOUT", "message": "Timeout must be between 1 and 300 seconds."}]
    root = Path(workspace).resolve()
    fixture, script = root / FIXTURE, root / SCRIPT
    if not fixture.is_file() or not script.is_file():
        return False, {"wps_launched": False, "fixture": str(fixture), "script": str(script)}, [
            {"code": "WRITER_PARITY_INPUT_MISSING", "message": "Controlled fixture or WPS audit script is missing."}
        ]
    try:
        source_hash = _sha256(fixture)
        audit_script_hash = _sha256(script)
        code_hashes = implementation_hashes(root)
        structure = read_writer_structure(fixture)
        texts = docx_body_paragraphs(fixture)
        if _sha256(fixture) != source_hash:
            return False, {"wps_launched": False, "source_sha256": source_hash}, [
                {"code": "WRITER_PARITY_SOURCE_CHANGED", "message": "Fixture changed during offline inspection."}
            ]
        if len(texts) != len(structure["paragraphs"]):
            raise ValueError("Offline paragraph inventories differ.")
        bookmarks = structure["bookmarks"]
        if any(item["status"] != "paired" or not item["body_paragraph_range_supported"] for item in bookmarks):
            raise ValueError("Controlled fixture contains unsupported bookmarks.")
        names = [item["name"] for item in bookmarks]
        if len(names) != len(set(names)):
            raise ValueError("Controlled fixture contains ambiguous bookmark names.")
        offline = {
            "paragraph_texts": texts,
            "heading_levels": [item["heading_level"] for item in structure["paragraphs"]],
            "style_ids": [item["style_id"] for item in structure["paragraphs"]],
            "bookmarks": {name: read_body_bookmark_text(fixture, name)[1] for name in names},
        }
    except (BadZipFile, KeyError, ET.ParseError, ValueError, OSError) as exc:
        return False, {"wps_launched": False, "fixture": str(fixture)}, [
            {"code": "WRITER_PARITY_OFFLINE_FAILED", "message": str(exc)}
        ]
    if any(value is None for value in offline["bookmarks"].values()):
        return False, {"wps_launched": False, "source_sha256": source_hash}, [
            {"code": "WRITER_PARITY_OFFLINE_FAILED", "message": "Supported bookmark text could not be read."}
        ]
    try:
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Path", str(fixture)],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout_seconds,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, {"wps_launched": True, "fixture": str(fixture), "source_sha256": source_hash,
                       "source_sha256_after": _sha256(fixture)}, [
            {"code": "WRITER_PARITY_WPS_FAILED", "message": str(exc)}
        ]
    try:
        observed = json.loads(completed.stdout.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        return False, {"wps_launched": True, "fixture": str(fixture), "source_sha256": source_hash,
                       "source_sha256_after": _sha256(fixture), "wps_exit_code": completed.returncode,
                       "wps_stdout_excerpt": completed.stdout[:2000], "wps_stderr_excerpt": completed.stderr[:2000]}, [
            {"code": "WRITER_PARITY_WPS_INVALID_JSON", "message": str(exc)}
        ]
    after_hash = _sha256(fixture)
    after_code_hashes = implementation_hashes(root)
    report = {
        "fixture": str(fixture),
        "script": str(script),
        "source_sha256": source_hash,
        "source_sha256_after": after_hash,
        "audit_script_sha256": audit_script_hash,
        "implementation_sha256": code_hashes,
        "implementation_sha256_after": after_code_hashes,
        "wps_launched": True,
        "remote_git_used": False,
        "offline": offline,
        "wps": observed,
        "wps_exit_code": completed.returncode,
        "wps_stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0 or not isinstance(observed, dict) or observed.get("ok") is not True:
        return False, report, [{"code": "WRITER_PARITY_WPS_FAILED", "message": "WPS observation failed."}]
    checks = compare_writer_structure(offline, observed)
    checks.append({"name": "source_unchanged", "passed": source_hash == after_hash == str(observed.get("sha256_before", "")).upper() == str(observed.get("sha256_after", "")).upper() and observed.get("file_unchanged") is True,
                   "expected": source_hash, "actual": {"python_after": after_hash, "wps_before": observed.get("sha256_before"), "wps_after": observed.get("sha256_after")}})
    checks.append({"name": "implementation_unchanged", "passed": code_hashes == after_code_hashes,
                   "expected": code_hashes, "actual": after_code_hashes})
    report["checks"] = checks
    report["passed_count"] = sum(check["passed"] is True for check in checks)
    report["failed_count"] = len(checks) - report["passed_count"]
    report["parity_status"] = "passed" if report["failed_count"] == 0 else "failed"
    errors = [] if report["failed_count"] == 0 else [
        {"code": "WRITER_PARITY_FAILED", "message": "Writer structure differs from WPS observations.",
         "details": [check["name"] for check in checks if not check["passed"]]}
    ]
    return not errors, report, errors


def run_writer_nested_parity(
    workspace: str | Path = ".", run_wps: bool = False, timeout_seconds: int = 90,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    if not run_wps:
        return False, {"wps_launched": False}, [{"code": "WPS_OPT_IN_REQUIRED", "message": "Pass --run-wps to launch read-only WPS corroboration."}]
    if not 1 <= timeout_seconds <= 300:
        return False, {"wps_launched": False}, [{"code": "INVALID_TIMEOUT", "message": "Timeout must be between 1 and 300 seconds."}]
    root = Path(workspace).resolve()
    fixture, script = root / NESTED_FIXTURE, root / SCRIPT
    if not fixture.is_file() or not script.is_file():
        return False, {"wps_launched": False, "fixture": str(fixture), "script": str(script)}, [
            {"code": "WRITER_PARITY_INPUT_MISSING", "message": "Controlled fixture or WPS audit script is missing."}
        ]
    try:
        source_hash, script_hash = _sha256(fixture), _sha256(script)
        code_hashes = implementation_hashes(root)
        structure = read_writer_structure(fixture)
        bookmarks = structure["bookmarks"]
        names = [item["name"] for item in bookmarks]
        if len(names) != len(NESTED_SCOPES) or set(names) != set(NESTED_SCOPES):
            raise ValueError("Controlled nested fixture bookmark inventory differs from expected names.")
        if any(item["status"] != "paired" or not item["text_range_supported"]
               or item["start"]["scope"] != NESTED_SCOPES[item["name"]] for item in bookmarks):
            raise ValueError("Controlled nested fixture has unsupported or misclassified bookmarks.")
        offline = {name: read_supported_bookmark_text(fixture, name)[1] for name in names}
        if any(value is None for value in offline.values()):
            raise ValueError("Controlled nested fixture bookmark text could not be read.")
        if _sha256(fixture) != source_hash:
            raise ValueError("Controlled nested fixture changed during offline inspection.")
    except (BadZipFile, KeyError, ET.ParseError, ValueError, OSError) as exc:
        return False, {"wps_launched": False, "fixture": str(fixture)}, [
            {"code": "WRITER_PARITY_OFFLINE_FAILED", "message": str(exc)}
        ]
    try:
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Path", str(fixture)],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout_seconds,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, {"wps_launched": True, "fixture": str(fixture), "source_sha256": source_hash,
                       "source_sha256_after": _sha256(fixture)}, [
            {"code": "WRITER_PARITY_WPS_FAILED", "message": str(exc)}
        ]
    after_hash = _sha256(fixture)
    after_code_hashes = implementation_hashes(root)
    try:
        observed = json.loads(completed.stdout.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        return False, {"wps_launched": True, "fixture": str(fixture), "source_sha256": source_hash,
                       "source_sha256_after": after_hash, "wps_exit_code": completed.returncode,
                       "wps_stdout_excerpt": completed.stdout[:2000], "wps_stderr_excerpt": completed.stderr[:2000]}, [
            {"code": "WRITER_PARITY_WPS_INVALID_JSON", "message": str(exc)}
        ]
    report = {
        "scope": "nested", "fixture": str(fixture), "script": str(script),
        "source_sha256": source_hash, "source_sha256_after": after_hash,
        "audit_script_sha256": script_hash, "wps_launched": True,
        "implementation_sha256": code_hashes,
        "implementation_sha256_after": after_code_hashes,
        "remote_git_used": False, "offline": {"bookmarks": offline, "scopes": NESTED_SCOPES},
        "wps": observed, "wps_exit_code": completed.returncode,
        "wps_stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0 or not isinstance(observed, dict) or observed.get("ok") is not True:
        return False, report, [{"code": "WRITER_PARITY_WPS_FAILED", "message": "WPS observation failed."}]
    observed_items = observed.get("bookmarks", [])
    observed_names = [item.get("name") for item in observed_items if isinstance(item, dict)] if isinstance(observed_items, list) else []
    observed_text = {item.get("name"): item.get("text") for item in observed_items if isinstance(item, dict)} if isinstance(observed_items, list) else {}
    checks = [
        {"name": "read_only_open", "passed": observed.get("read_only") is True,
         "expected": True, "actual": observed.get("read_only")},
        {"name": "bookmark_names_and_text", "passed": len(observed_names) == len(offline) and observed_text == offline,
         "expected": offline, "actual": observed_text},
        {"name": "source_unchanged", "passed": source_hash == after_hash == str(observed.get("sha256_before", "")).upper() == str(observed.get("sha256_after", "")).upper() and observed.get("file_unchanged") is True,
         "expected": source_hash, "actual": {"python_after": after_hash, "wps_before": observed.get("sha256_before"), "wps_after": observed.get("sha256_after")}},
        {"name": "implementation_unchanged", "passed": code_hashes == after_code_hashes,
         "expected": code_hashes, "actual": after_code_hashes},
    ]
    report["checks"] = checks
    report["passed_count"] = sum(check["passed"] is True for check in checks)
    report["failed_count"] = len(checks) - report["passed_count"]
    report["parity_status"] = "passed" if report["failed_count"] == 0 else "failed"
    errors = [] if report["failed_count"] == 0 else [
        {"code": "WRITER_PARITY_FAILED", "message": "Nested bookmark reads differ from WPS observations.",
         "details": [check["name"] for check in checks if not check["passed"]]}
    ]
    return not errors, report, errors
