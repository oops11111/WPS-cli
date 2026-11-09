"""PDF page tool commands (C-02): pdf-info, pdf-merge, pdf-split, pdf-extract-pages, pdf-watermark."""

from __future__ import annotations

from typing import Any

from .models import CommandResponse, ValidationResult
from .pdf_tools import pdf_extract_pages, pdf_info, pdf_merge, pdf_split, pdf_watermark


def _response(command: str, request_id: str, result: tuple[bool, dict[str, Any], list[dict[str, str]]], done: str):
    ok, data, errors = result
    outputs = data.get("outputs", [])
    checks = [
        {"name": "output_read_back", "passed": bool(output.get("pages_match")), "details": output.get("path")}
        for output in outputs
    ] or [{"name": "pdf_read", "passed": ok, "details": data.get("path") or data.get("input_path")}]
    return CommandResponse(
        ok=ok,
        command=command,
        request_id=request_id,
        backend="python",
        summary=done if ok else f"{command} could not complete.",
        data=data,
        validation=ValidationResult(status="passed" if ok else "failed", checks=checks),
        errors=errors,
    )


def pdf_info_response(request_id: str, input_path: str) -> CommandResponse:
    result = pdf_info(input_path)
    pages = result[1].get("pages")
    return _response("pdf-info", request_id, result, f"Read the PDF ({pages} pages).")


def pdf_merge_response(request_id: str, inputs: list[str], output: str) -> CommandResponse:
    result = pdf_merge(inputs, output)
    return _response("pdf-merge", request_id, result, f"Merged {len(inputs)} PDFs into {result[1].get('output_path')}.")


def pdf_split_response(
    request_id: str, input_path: str, output_dir: str, every: int | None, ranges: str | None
) -> CommandResponse:
    result = pdf_split(input_path, output_dir, every=every, ranges=ranges)
    return _response("pdf-split", request_id, result, f"Split into {result[1].get('files')} files.")


def pdf_extract_pages_response(request_id: str, input_path: str, output: str, pages: str) -> CommandResponse:
    result = pdf_extract_pages(input_path, output, pages)
    return _response("pdf-extract-pages", request_id, result, f"Wrote pages {pages} to {result[1].get('output_path')}.")


def pdf_watermark_response(
    request_id: str,
    input_path: str,
    output: str,
    text: str,
    pages: str | None,
    font_size: int,
    opacity: int,
    angle: int,
) -> CommandResponse:
    result = pdf_watermark(input_path, output, text, pages=pages, font_size=font_size, opacity=opacity, angle=angle)
    return _response("pdf-watermark", request_id, result, f"Watermarked into {result[1].get('output_path')}.")
