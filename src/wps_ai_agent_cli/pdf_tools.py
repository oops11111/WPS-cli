"""PDF page tools: info, merge, split, extract pages and a text watermark (C-02).

All offline with pypdf (the pdf optional dependency); WPS is not started. Inputs are only read, and outputs are
new files created with an exclusive open: an existing path is never overwritten, and a command that fails part
way removes what it created. Every output is read back (page count and page sizes) before the command reports
success. Page numbers are 1-based; a page list is "1,3-5,8-" ("8-" runs to the last page).
"""

from __future__ import annotations

import io
import math
import re
from pathlib import Path
from typing import Any

from .conversion_paths import MAX_INPUT_BYTES, missing_dependency
from .workspace_boundary import boundary_error

PDF_ENCRYPTED = "PDF_ENCRYPTED"
PAGE_RANGE_INVALID = "PAGE_RANGE_INVALID"
MAX_SPLIT_OUTPUTS = 500
_PAPER = {"A3": (842, 1191), "A4": (595, 842), "A5": (420, 595), "B5": (499, 709), "Letter": (612, 792)}

Result = tuple[bool, dict[str, Any], list[dict[str, str]]]


class _Refusal(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.error = {"code": code, "message": message}


def _pypdf():
    try:
        import pypdf
    except ImportError:
        return None
    return pypdf


def _guard(path: Path, what: str) -> None:
    outside = boundary_error(path, what)
    if outside is not None:
        raise _Refusal(outside["code"], outside["message"])


def _reader(path: str | Path):
    """An opened, decrypted-if-possible PdfReader for an existing .pdf, or a refusal."""
    import pypdf

    source = Path(path).expanduser().resolve()
    _guard(source, "Input path")
    if source.suffix.casefold() != ".pdf":
        raise _Refusal("INVALID_INPUT", f"Input must be a .pdf file: {source}")
    if not source.is_file():
        raise _Refusal("INPUT_FILE_NOT_FOUND", f"Input not found: {source}")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise _Refusal("INPUT_TOO_LARGE", f"Input exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MiB limit.")
    try:
        reader = pypdf.PdfReader(str(source), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise _Refusal(PDF_ENCRYPTED, f"{source.name} is password protected; remove the password and retry.")
        page_count = len(reader.pages)  # parses the page tree, so a damaged file fails here
    except _Refusal:
        raise
    except Exception as exc:  # pypdf raises many types for damaged files
        raise _Refusal("INVALID_INPUT", f"{source.name} could not be read as a PDF: {exc}") from exc
    if page_count == 0:
        raise _Refusal("INVALID_INPUT", f"{source.name} has no pages.")
    return source, reader


def _new_output(path: str | Path, sources: list[Path]) -> Path:
    destination = Path(path).expanduser().resolve()
    _guard(destination, "Output path")
    if destination.suffix.casefold() != ".pdf":
        raise _Refusal("INVALID_OUTPUT", f"Output must be a .pdf file: {destination}")
    if destination in sources:
        raise _Refusal("INVALID_OUTPUT", "Output must be a new file, not one of the inputs.")
    if destination.exists():
        raise _Refusal("OUTPUT_ALREADY_EXISTS", f"Refusing to overwrite existing output: {destination}")
    if not destination.parent.is_dir():
        raise _Refusal("OUTPUT_DIRECTORY_NOT_FOUND", f"Output directory does not exist: {destination.parent}")
    return destination


def _write(writer, destination: Path) -> None:
    buffer = io.BytesIO()
    writer.write(buffer)
    try:
        with open(destination, "xb") as handle:
            handle.write(buffer.getvalue())
    except FileExistsError as exc:
        raise _Refusal("OUTPUT_ALREADY_EXISTS", f"Refusing to overwrite existing output: {destination}") from exc
    except OSError as exc:
        raise _Refusal("OUTPUT_WRITE_FAILED", f"Could not write {destination}: {exc}") from exc


def _size(page) -> tuple[float, float]:
    box = page.mediabox
    return round(float(box.width), 2), round(float(box.height), 2)


def _read_back(destination: Path, expected_sizes: list[tuple[float, float]]) -> dict[str, Any]:
    import pypdf

    reader = pypdf.PdfReader(str(destination), strict=False)
    sizes = [_size(page) for page in reader.pages]
    return {
        "path": str(destination),
        "pages": len(sizes),
        "size": destination.stat().st_size,
        "pages_match": sizes == expected_sizes,
    }


def parse_pages(spec: str, total: int) -> list[int]:
    """1-based page numbers from "1,3-5,8-", in the order given."""
    if not spec or not spec.strip():
        raise _Refusal(PAGE_RANGE_INVALID, "The page list is empty.")
    pages: list[int] = []
    for part in spec.replace("，", ",").split(","):
        part = part.strip()
        found = re.fullmatch(r"(\d+)(?:\s*-\s*(\d*))?", part)
        if not found:
            raise _Refusal(PAGE_RANGE_INVALID, f"Not a page or range: {part!r} (use 1,3-5,8-).")
        start = int(found.group(1))
        end = start if found.group(2) is None else int(found.group(2) or total)
        if start < 1 or end > total or start > end:
            raise _Refusal(PAGE_RANGE_INVALID, f"Pages {part} are outside 1-{total}.")
        pages.extend(range(start, end + 1))
    return pages


def _run(action) -> Result:
    if _pypdf() is None:
        return missing_dependency("pdf", "pypdf")
    try:
        return action()
    except _Refusal as refusal:
        return False, {}, [refusal.error]


def _finish(data: dict[str, Any], outputs: list[dict[str, Any]]) -> Result:
    data["outputs"] = outputs
    data["validation_passed"] = all(output["pages_match"] for output in outputs)
    if not data["validation_passed"]:
        return False, data, [{"code": "VALIDATION_FAILED", "message": "An output's pages differ from the request."}]
    return True, data, []


def _paper(width: float, height: float) -> str | None:
    short, long = sorted((width, height))
    for name, (a, b) in _PAPER.items():
        if abs(short - a) <= 3 and abs(long - b) <= 3:
            return name
    return None


def pdf_info(input_path: str | Path) -> Result:
    def action() -> Result:
        source, reader = _reader(input_path)
        sizes: dict[tuple[float, float], int] = {}
        rotations: dict[int, int] = {}
        for page in reader.pages:
            sizes[_size(page)] = sizes.get(_size(page), 0) + 1
            rotation = int(page.get("/Rotate", 0) or 0) % 360
            rotations[rotation] = rotations.get(rotation, 0) + 1
        sampled = list(reader.pages)[:5]
        text_pages = sum(1 for page in sampled if (page.extract_text() or "").strip())
        metadata = {
            key.lstrip("/").lower(): str(value) for key, value in (reader.metadata or {}).items() if value is not None
        }
        try:
            outline_count = len(reader.outline)
        except Exception:
            outline_count = 0
        data = {
            "path": str(source),
            "file_size": source.stat().st_size,
            "pdf_version": reader.pdf_header.replace("%PDF-", ""),
            "pages": len(reader.pages),
            "page_sizes": [
                {
                    "width_pt": width,
                    "height_pt": height,
                    "width_mm": round(width * 25.4 / 72, 1),
                    "height_mm": round(height * 25.4 / 72, 1),
                    "paper": _paper(width, height),
                    "orientation": "landscape" if width > height else "portrait",
                    "count": count,
                }
                for (width, height), count in sizes.items()
            ],
            "rotations": {str(angle): count for angle, count in sorted(rotations.items())},
            "encrypted": bool(reader.is_encrypted),
            "metadata": metadata,
            "outline_items": outline_count,
            "text_layer": {"pages_checked": len(sampled), "pages_with_text": text_pages},
            "likely_scanned": text_pages == 0,
        }
        return True, data, []

    return _run(action)


def pdf_merge(input_paths: list[str], output_path: str | Path) -> Result:
    def action() -> Result:
        import pypdf

        if len(input_paths) < 2:
            raise _Refusal("INVALID_ARGUMENT", "Give at least two input PDFs to merge, in order.")
        opened = [_reader(path) for path in input_paths]
        destination = _new_output(output_path, [source for source, _ in opened])
        writer = pypdf.PdfWriter()
        expected: list[tuple[float, float]] = []
        for _source, reader in opened:
            writer.append(reader)
            expected.extend(_size(page) for page in reader.pages)
        _write(writer, destination)
        data = {
            "inputs": [{"path": str(source), "pages": len(reader.pages)} for source, reader in opened],
            "output_path": str(destination),
        }
        return _finish(data, [_read_back(destination, expected)])

    return _run(action)


def _subset(reader, pages: list[int]):
    import pypdf

    writer = pypdf.PdfWriter()
    for number in pages:
        writer.add_page(reader.pages[number - 1])
    if reader.metadata:
        writer.add_metadata({key: value for key, value in reader.metadata.items() if isinstance(value, str)})
    return writer, [_size(reader.pages[number - 1]) for number in pages]


def pdf_extract_pages(input_path: str | Path, output_path: str | Path, pages: str) -> Result:
    def action() -> Result:
        source, reader = _reader(input_path)
        numbers = parse_pages(pages, len(reader.pages))
        destination = _new_output(output_path, [source])
        writer, expected = _subset(reader, numbers)
        _write(writer, destination)
        data = {"input_path": str(source), "output_path": str(destination), "pages": numbers}
        return _finish(data, [_read_back(destination, expected)])

    return _run(action)


def pdf_split(
    input_path: str | Path, output_dir: str | Path, every: int | None = None, ranges: str | None = None
) -> Result:
    """One file per `every` pages (1 by default), or one file per comma-separated item of `ranges`."""

    def action() -> Result:
        source, reader = _reader(input_path)
        total = len(reader.pages)
        if every is not None and ranges:
            raise _Refusal("INVALID_ARGUMENT", "Give either every or ranges, not both.")
        if ranges:
            groups = [parse_pages(part, total) for part in ranges.replace("，", ",").split(",")]
        else:
            size = every or 1
            if size < 1:
                raise _Refusal("INVALID_ARGUMENT", "every must be 1 or more.")
            groups = [list(range(start, min(start + size, total + 1))) for start in range(1, total + 1, size)]
        if len(groups) > MAX_SPLIT_OUTPUTS:
            raise _Refusal(
                "INVALID_ARGUMENT", f"That would write {len(groups)} files; the limit is {MAX_SPLIT_OUTPUTS}."
            )
        folder = Path(output_dir).expanduser().resolve()
        _guard(folder, "Output directory")
        if not folder.is_dir():
            raise _Refusal("OUTPUT_DIRECTORY_NOT_FOUND", f"Output directory does not exist: {folder}")

        def name(group: list[int]) -> str:
            first, last = group[0], group[-1]
            contiguous = group == list(range(first, last + 1))
            label = f"p{first}" if len(group) == 1 else f"p{first}-{last}" if contiguous else f"p{first}-etc"
            return f"{source.stem}_{label}.pdf"

        targets = [folder / name(group) for group in groups]
        if len(set(targets)) != len(targets):
            targets = [folder / f"{source.stem}_part{index}.pdf" for index in range(1, len(groups) + 1)]
        for target in targets:
            _new_output(target, [source])  # every name is checked before anything is written
        created: list[Path] = []
        outputs = []
        try:
            for group, target in zip(groups, targets, strict=True):
                writer, expected = _subset(reader, group)
                _write(writer, target)
                created.append(target)
                outputs.append({**_read_back(target, expected), "source_pages": group})
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        data = {"input_path": str(source), "output_dir": str(folder), "files": len(outputs)}
        return _finish(data, outputs)

    return _run(action)


# The watermark is drawn in STSong-Light, one of the CJK fonts every PDF reader must supply (Adobe-GB1), so
# Chinese and Latin text show without embedding a font. Half-width characters (CIDs 1-95) are 500 units wide.
def _watermark_font(pypdf):
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject

    def name(value: str) -> NameObject:
        return NameObject(value)

    descriptor = DictionaryObject(
        {
            name("/Type"): name("/FontDescriptor"),
            name("/FontName"): name("/STSong-Light"),
            name("/Flags"): NumberObject(6),
            name("/FontBBox"): ArrayObject([NumberObject(v) for v in (-25, -254, 1000, 880)]),
            name("/ItalicAngle"): NumberObject(0),
            name("/Ascent"): NumberObject(880),
            name("/Descent"): NumberObject(-120),
            name("/CapHeight"): NumberObject(880),
            name("/StemV"): NumberObject(93),
        }
    )
    descendant = DictionaryObject(
        {
            name("/Type"): name("/Font"),
            name("/Subtype"): name("/CIDFontType0"),
            name("/BaseFont"): name("/STSong-Light"),
            name("/CIDSystemInfo"): DictionaryObject(
                {
                    name("/Registry"): TextStringObject("Adobe"),
                    name("/Ordering"): TextStringObject("GB1"),
                    name("/Supplement"): NumberObject(2),
                }
            ),
            name("/FontDescriptor"): descriptor,
            name("/DW"): NumberObject(1000),
            name("/W"): ArrayObject([NumberObject(1), NumberObject(95), NumberObject(500)]),
        }
    )
    return DictionaryObject(
        {
            name("/Type"): name("/Font"),
            name("/Subtype"): name("/Type0"),
            name("/BaseFont"): name("/STSong-Light"),
            name("/Encoding"): name("/UniGB-UCS2-H"),
            name("/DescendantFonts"): ArrayObject([descendant]),
        }
    )


def _text_width(text: str, font_size: float) -> float:
    return sum(0.5 if ord(char) < 0x7F else 1.0 for char in text) * font_size


def _stamp(pypdf, page, text: str, font_size: float, opacity: float, angle: float):
    """A blank page the size of `page` with the text centred and turned by `angle`."""
    from pypdf.generic import (
        ContentStream,
        DictionaryObject,
        FloatObject,
        NameObject,
    )

    box = page.cropbox
    left, bottom = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)
    stamp = pypdf.PageObject.create_blank_page(width=float(page.mediabox.width), height=float(page.mediabox.height))
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    half_width, half_height = _text_width(text, font_size) / 2, font_size * 0.35
    centre_x, centre_y = left + width / 2, bottom + height / 2
    start_x = centre_x - half_width * cos + half_height * sin
    start_y = centre_y - half_width * sin - half_height * cos
    hex_text = text.encode("utf-16-be").hex().upper()
    operations = (
        f"q /WmGS gs 0.5 g BT /WmF {font_size:.2f} Tf "
        f"{cos:.5f} {sin:.5f} {-sin:.5f} {cos:.5f} {start_x:.2f} {start_y:.2f} Tm <{hex_text}> Tj ET Q"
    )
    content = ContentStream(None, None)
    content.set_data(operations.encode("ascii"))
    stamp[NameObject("/Contents")] = content
    stamp[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/WmF"): _watermark_font(pypdf)}),
            NameObject("/ExtGState"): DictionaryObject(
                {
                    NameObject("/WmGS"): DictionaryObject(
                        {NameObject("/ca"): FloatObject(opacity), NameObject("/CA"): FloatObject(opacity)}
                    )
                }
            ),
        }
    )
    return stamp


def pdf_watermark(
    input_path: str | Path,
    output_path: str | Path,
    text: str,
    pages: str | None = None,
    font_size: int = 48,
    opacity: int = 15,
    angle: int = 45,
) -> Result:
    """Every page (or `pages`) with `text` drawn over it, grey, `opacity` percent, turned `angle` degrees."""

    def action() -> Result:
        import pypdf

        cleaned = (text or "").strip()
        if not cleaned or len(cleaned) > 100 or "\n" in cleaned:
            raise _Refusal("INVALID_ARGUMENT", "The watermark is one line of 1 to 100 characters.")
        if any(ord(char) > 0xFFFF or ord(char) < 0x20 for char in cleaned):
            raise _Refusal("INVALID_ARGUMENT", "The watermark cannot contain control characters or emoji.")
        if not 6 <= font_size <= 300 or not 1 <= opacity <= 100 or not -360 <= angle <= 360:
            raise _Refusal("INVALID_ARGUMENT", "font_size is 6-300, opacity 1-100 (percent), angle -360 to 360.")
        source, reader = _reader(input_path)
        selected = set(parse_pages(pages, len(reader.pages))) if pages else set(range(1, len(reader.pages) + 1))
        destination = _new_output(output_path, [source])
        writer = pypdf.PdfWriter(clone_from=reader)
        for number, page in enumerate(writer.pages, 1):
            if number in selected:
                page.merge_page(_stamp(pypdf, page, cleaned, font_size, opacity / 100, angle), over=True)
        expected = [_size(page) for page in reader.pages]
        _write(writer, destination)
        output = _read_back(destination, expected)
        marked = pypdf.PdfReader(str(destination), strict=False)
        first = min(selected)
        output["text_found_on_first_marked_page"] = cleaned in (marked.pages[first - 1].extract_text() or "")
        output["pages_match"] = output["pages_match"] and output["text_found_on_first_marked_page"]
        data = {
            "input_path": str(source),
            "output_path": str(destination),
            "text": cleaned,
            "marked_pages": sorted(selected),
            "font_size": font_size,
            "opacity": opacity,
            "angle": angle,
        }
        return _finish(data, [output])

    return _run(action)
