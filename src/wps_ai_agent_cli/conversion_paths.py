"""Input and output checks shared by the Phase 13 converters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

MAX_INPUT_BYTES = 100 * 1024 * 1024


def check_paths(
    input_path: str | Path,
    output_path: str | Path,
    inputs: Iterable[str],
    outputs: Iterable[str],
    max_bytes: int = MAX_INPUT_BYTES,
) -> tuple[Path, Path, list[dict[str, str]]]:
    """An existing source with one of ``inputs`` suffixes and a new output with one of ``outputs``."""
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    inputs, outputs = sorted(set(inputs)), sorted(set(outputs))

    def fail(code: str, message: str):
        return source, destination, [{"code": code, "message": message}]

    if source.suffix.casefold() not in inputs:
        return fail("INVALID_INPUT", f"Input must be one of: {', '.join(inputs)}.")
    if not source.is_file():
        return fail("INPUT_FILE_NOT_FOUND", f"Input not found: {source}")
    if source.stat().st_size > max_bytes:
        return fail("INPUT_TOO_LARGE", f"Input exceeds the {max_bytes // (1024 * 1024)} MiB limit.")
    if destination.suffix.casefold() not in outputs or destination == source:
        return fail("INVALID_OUTPUT", f"Output must be a separate file ending in one of: {', '.join(outputs)}.")
    if destination.exists():
        return fail("OUTPUT_ALREADY_EXISTS", f"Refusing to overwrite existing output: {destination}")
    if not destination.parent.is_dir():
        return fail("OUTPUT_DIRECTORY_NOT_FOUND", f"Output directory does not exist: {destination.parent}")
    return source, destination, []


def missing_dependency(extra: str, package: str) -> tuple[bool, dict, list[dict[str, str]]]:
    return (
        False,
        {},
        [{"code": "CONVERTER_UNAVAILABLE", "message": f"Install the {extra} optional dependency: {package}."}],
    )
