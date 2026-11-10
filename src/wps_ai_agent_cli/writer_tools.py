"""Insert a picture, set up the page and apply a style preset in a Writer document (C-06).

The three commands follow the C-06 list settled on 2026-11-10 (docs/ROADMAP.md history, the capability-gap note):

- writer-insert-image and writer-page-setup change the document through WPS (COM) and are read back offline with
  python-docx, with the same backup, read-back and rollback as the other writes (spreadsheet_tools._commit).
- writer-style-apply rewrites run, paragraph and section properties offline with python-docx, like writer-merge: it
  touches every paragraph, which is slow and fragile through COM, and the read-back checks each one. The document
  must therefore be closed in WPS. Missing fonts are not substituted silently: they are listed and the command
  refuses, unless the caller maps them to installed fonts or allows them.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .atomic_mutation import atomic_mutation
from .backups import create_backup, record_after_com_identity
from .capabilities import probe_wps_capabilities
from .document_text import docx_body_paragraphs
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .file_hold import probe_file_not_held
from .mutation_lock import coordinated_mutation
from .ooxml import read_zip_part
from .operations import record_operation, replay_operation
from .powershell_runner import run_powershell_script
from .sessions import file_identity, get_document
from .spreadsheet_tools import _commit, _guarded, _Refusal
from .wps_script_snippets import ACQUIRE_WPS_APP, HIDE_LAUNCHED_APP, PRE_OPEN_GUARD, QUIET_ALERTS, RELEASE_WPS_APP
from .writer_merge import _replace_file

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
EMU_PER_MM = 36000
PT_PER_MM = 72 / 25.4
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
MAX_IMAGE_BYTES = 50 * 1024 * 1024
# (width, height) in millimetres, portrait. 16K is the 184 x 260 mm sheet WPS lists as 16开.
PAPERS = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "16K": (184.0, 260.0),
}
TOLERANCE_MM = 0.6

# Chinese type sizes in points.
SIZES = {"二号": 22.0, "三号": 16.0, "四号": 14.0, "小四": 12.0, "五号": 10.5}

# The two presets of the C-06 list. Fonts are the names Windows registers; 小标宋 is 方正小标宋简体.
PRESETS: dict[str, dict[str, Any]] = {
    "gongwen": {
        "paper": "A4",
        "margins_mm": {"top": 37, "bottom": 35, "left": 28, "right": 26},
        "title": {"font": "方正小标宋简体", "size": "二号", "align": "center"},
        "heading1": {"font": "黑体", "size": "三号"},
        "heading2": {"font": "楷体_GB2312", "size": "三号", "bold": True},
        "heading3": {"font": "仿宋_GB2312", "size": "三号", "bold": True},
        "body": {"font": "仿宋_GB2312", "size": "三号", "line_exact_pt": 28, "first_line_chars": 2},
        "page_number": {"font": "宋体", "size": "四号"},
    },
    "report": {
        "paper": "A4",
        "margins_mm": {"top": 25, "bottom": 25, "left": 28, "right": 26},
        "title": {"font": "黑体", "size": "二号", "align": "center"},
        "heading1": {"font": "黑体", "size": "三号"},
        "heading2": {"font": "黑体", "size": "四号"},
        "heading3": {"font": "宋体", "size": "小四", "bold": True},
        "body": {"font": "宋体", "size": "小四", "line_multiple": 1.5, "first_line_chars": 2},
        "page_number": {"font": "宋体", "size": "五号"},
    },
}
FONT_NOT_INSTALLED = "FONT_NOT_INSTALLED"
Outcome = tuple[bool, dict[str, Any], list[dict[str, str]], bool]


# ---------------------------------------------------------------------------------------------------- shared
def _writer(document_id: str, command: str, workspace: str | Path) -> Path:
    document = get_document(document_id, workspace)
    if not document:
        raise _Refusal("DOCUMENT_NOT_FOUND", f"Document not registered: {document_id}")
    if document["component"] != "writer":
        raise _Refusal("UNSUPPORTED_COMPONENT", f"{command} requires a writer document.", {"document": document})
    path = Path(document["path"])
    if not path.exists():
        raise _Refusal(INPUT_FILE_NOT_FOUND, f"Input file not found: {path}", {"document": document})
    if path.suffix.casefold() not in {".docx", ".docm"}:
        raise _Refusal("INVALID_INPUT", f"{command} works on .docx files; convert other formats first.")
    held = probe_file_not_held(path, read_only=True, what="document")
    if held is not None:
        raise _Refusal(held["code"], held["message"], {"document_id": document_id, "path": str(path)})
    return path


def _docx(path: Path):
    try:
        from docx import Document
    except ImportError as exc:
        raise _Refusal("CONVERTER_UNAVAILABLE", "Install the html optional dependency: python-docx.") from exc
    return Document(str(path))


def _run_writer_script(path: str, params: dict[str, Any], body: str) -> dict[str, Any]:
    """Open the document in WPS, run body with $document and $params, save, and return the $out it fills."""
    capabilities = probe_wps_capabilities()
    prog_id = capabilities["components"]["writer"]["selected_prog_id"]
    if not prog_id:
        return {
            "ok": False,
            "errors": [{"code": COM_BACKEND_UNAVAILABLE, "message": "No registered WPS ProgID detected for writer."}],
            "data": {"capabilities": capabilities},
        }
    params_json = json.dumps({**params, "prog_id": prog_id, "path": str(Path(path).resolve())})
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
{PRE_OPEN_GUARD}
$app = $null; $document = $null
try {{
  {ACQUIRE_WPS_APP}
  {HIDE_LAUNCHED_APP}
  {QUIET_ALERTS}
  $wpsPreOpen = Test-WpsPathOpen $app.Documents $params.path
  $document = Open-WpsDocument $app.Documents $params.path $wpsPreOpen
  Assert-WpsPreOpenSaved $wpsPreOpen $document
  $out = @{{ ok = $true; backend = 'powershell-com'; prog_id = $params.prog_id }}
{body}
  $document.Save()
  [pscustomobject]$out | ConvertTo-Json -Depth 6 -Compress
}} catch {{
  [pscustomobject]@{{ ok = $false; error_message = $_.Exception.Message }} | ConvertTo-Json -Depth 5 -Compress
  exit 2
}} finally {{
  if ($document -ne $null) {{ if (-not $wpsPreOpen) {{ try {{ $document.Close($false) }} catch {{ }} }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }} }}
  if ($app -ne $null) {{ try {{ {RELEASE_WPS_APP} }} catch {{ }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }} }}
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}}
"""
    payload, failure = run_powershell_script(script)
    if failure is not None:
        return failure
    if not payload.get("ok"):
        return {
            "ok": False,
            "errors": [{"code": COM_OPERATION_FAILED, "message": payload.get("error_message", "WPS could not do it.")}],
            "data": {"diagnostic": payload},
        }
    return {"ok": True, "errors": [], "data": payload}


# The body paragraph a command anchors on, found the way writer-replace finds it: paragraphs outside tables, with
# the count and text checked against the offline read so that WPS and the file agree on which paragraph it is.
_FIND_BODY_PARAGRAPH = """
  $bodyParagraphs = @()
  for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
    $candidate = $document.Paragraphs.Item($i).Range
    if (-not $candidate.Information(12)) { $bodyParagraphs += $candidate }
  }
  if ($bodyParagraphs.Count -ne [int]$params.body_paragraph_count) { throw "WPS body paragraph collection differs from the offline body." }
  $anchor = $bodyParagraphs[[int]$params.paragraph_index - 1]
  $anchorText = ([string]$anchor.Text).TrimEnd([char[]]@([char]13, [char]7)).Replace([string][char]11, "`n")
  if ($anchorText -cne [string]$params.expected_text) { throw "WPS paragraph text differs from the offline target." }
"""


# ----------------------------------------------------------------------------------------------- insert image
def _image_size(path: Path) -> tuple[float, float]:
    """The picture's own size in millimetres (from its pixels and resolution, 96 dpi when it has none)."""
    try:
        from docx.image.image import Image
    except ImportError as exc:
        raise _Refusal("CONVERTER_UNAVAILABLE", "Install the html optional dependency: python-docx.") from exc
    try:
        image = Image.from_file(str(path))
    except Exception as exc:  # unreadable or unsupported picture
        raise _Refusal("INVALID_INPUT", f"{path.name} could not be read as a picture: {exc}") from exc
    dpi_x, dpi_y = image.horz_dpi or 96, image.vert_dpi or 96
    return image.px_width / dpi_x * 25.4, image.px_height / dpi_y * 25.4


def _text_width_mm(document) -> float:
    section = document.sections[0]
    width = section.page_width - section.left_margin - section.right_margin
    return width / EMU_PER_MM


def _body_elements(path: Path) -> list:
    from lxml import etree

    with ZipFile(path) as archive:
        root = etree.fromstring(read_zip_part(archive, "word/document.xml"))
    body = root.find(f"{{{W}}}body")
    return [child for child in body if child.tag == f"{{{W}}}p"]


def _inline_widths_mm(paragraph) -> list[float]:
    """The widths of the paragraph's inline pictures, from their wp:extent."""
    widths = []
    for inline in paragraph.iter(f"{{{WP}}}inline"):
        extent = inline.find(f"{{{WP}}}extent")
        if extent is not None:
            widths.append(int(extent.get("cx")) / EMU_PER_MM)
    return widths


def _run_insert_image_com(path: str, params: dict[str, Any]) -> dict[str, Any]:
    body = (
        _FIND_BODY_PARAGRAPH
        + """
  [void]$anchor.InsertParagraphAfter()
  $holder = $anchor.Paragraphs.Last.Range
  $holder.ParagraphFormat.OutlineLevel = 10
  $holder.ParagraphFormat.FirstLineIndent = 0
  $holder.ParagraphFormat.Alignment = 1
  $at = $holder.Duplicate
  $at.Collapse(1)
  $shape = $document.InlineShapes.AddPicture($params.image_path, $false, $true, $at)
  $shape.LockAspectRatio = -1
  $shape.Width = [double]$params.width_pt
  $out.width_pt = [double]$shape.Width
  $out.height_pt = [double]$shape.Height
  if ($params.caption) {
    $picture = $shape.Range.Paragraphs.First.Range
    [void]$picture.InsertParagraphAfter()
    $captionParagraph = $picture.Paragraphs.Last.Range
    $text = $document.Range($captionParagraph.Start, $captionParagraph.End - 1)
    $text.Text = [string]$params.caption
    $captionParagraph = $text.Paragraphs.First.Range
    $captionParagraph.Font.Name = '宋体'
    $captionParagraph.Font.NameFarEast = '宋体'
    $captionParagraph.Font.Size = 10.5
    $captionParagraph.ParagraphFormat.Alignment = 1
    $captionParagraph.ParagraphFormat.FirstLineIndent = 0
    $captionParagraph.ParagraphFormat.OutlineLevel = 10
  }
"""
    )
    return _run_writer_script(path, params, body)


@coordinated_mutation
@atomic_mutation
@_guarded
def insert_writer_image(
    document_id: str,
    image_path: str,
    request_id: str,
    at_paragraph: int | None = None,
    after_text: str | None = None,
    at_end: bool = False,
    width_mm: float | None = None,
    caption: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Insert a picture as its own paragraph after a body paragraph, with an optional caption below it."""
    replay = replay_operation(
        request_id,
        "writer-insert-image",
        {"document_id": document_id, "image_path": image_path, "caption": caption, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay
    chosen = [at_paragraph is not None, bool(after_text), bool(at_end)]
    if sum(chosen) != 1:
        raise _Refusal("INVALID_ARGUMENT", "Give exactly one of at_paragraph, after_text or at_end.")
    picture = Path(image_path).expanduser().resolve()
    if picture.suffix.casefold() not in IMAGE_SUFFIXES:
        raise _Refusal("INVALID_INPUT", f"The picture must be one of: {', '.join(sorted(IMAGE_SUFFIXES))}.")
    if not picture.is_file():
        raise _Refusal(INPUT_FILE_NOT_FOUND, f"Picture not found: {picture}")
    if picture.stat().st_size > MAX_IMAGE_BYTES:
        raise _Refusal("INPUT_TOO_LARGE", "The picture is larger than 50 MiB.")
    if width_mm is not None and not 5 <= width_mm <= 1000:
        raise _Refusal("INVALID_ARGUMENT", "width_mm is 5 to 1000.")
    caption = caption.strip() if caption else None
    if caption and (len(caption) > 255 or "\n" in caption):
        raise _Refusal("INVALID_ARGUMENT", "The caption is one line of at most 255 characters.")
    path = _writer(document_id, "writer-insert-image", workspace)
    texts = docx_body_paragraphs(path)
    if not texts:
        raise _Refusal("PARAGRAPH_NOT_FOUND", "The document has no body paragraph to insert after.")
    if at_paragraph is not None:
        if not 1 <= at_paragraph <= len(texts):
            raise _Refusal("PARAGRAPH_NOT_FOUND", f"at_paragraph must be 1 to {len(texts)}.")
        index = at_paragraph
    elif after_text:
        matches = [number for number, text in enumerate(texts, 1) if after_text in text]
        if not matches:
            raise _Refusal("TEXT_NOT_FOUND", f"No body paragraph contains {after_text!r}.")
        index = matches[0]
    else:
        index = len(texts)
    natural_width, natural_height = _image_size(picture)
    text_width = _text_width_mm(_docx(path))
    width = width_mm if width_mm is not None else min(natural_width, text_width)
    height = natural_height * width / natural_width
    preview = {
        "document_id": document_id,
        "path": str(path),
        "image_path": str(picture),
        "after_paragraph": index,
        "after_paragraph_text": texts[index - 1][:80],
        "width_mm": round(width, 1),
        "height_mm": round(height, 1),
        "natural_size_mm": [round(natural_width, 1), round(natural_height, 1)],
        "text_width_mm": round(text_width, 1),
        "caption": caption,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False
    params = {
        "image_path": str(picture),
        "width_pt": width * PT_PER_MM,
        "caption": caption,
        "paragraph_index": index,
        "body_paragraph_count": len(texts),
        "expected_text": texts[index - 1],
    }
    inline_before = sum(len(_inline_widths_mm(paragraph)) for paragraph in _body_elements(path))

    def read_back():
        after = docx_body_paragraphs(path)
        expected = texts[:index] + [""] + ([caption] if caption else []) + texts[index:]
        elements = _body_elements(path)
        widths = _inline_widths_mm(elements[index]) if len(elements) > index else []
        inline_after = sum(len(_inline_widths_mm(paragraph)) for paragraph in elements)
        return (
            {
                "paragraphs_in_place": after == expected,
                "picture_after_anchor": len(widths) == 1,
                "one_picture_added": inline_after == inline_before + 1,
                "width_matches": bool(widths) and abs(widths[0] - width) <= max(1.0, width * 0.02),
            },
            {"picture_width_mm": round(widths[0], 1) if widths else None, "paragraphs_after": len(after)},
        )

    return _commit(
        "writer-insert-image",
        document_id,
        request_id,
        path,
        preview,
        lambda: _run_insert_image_com(str(path), params),
        read_back,
        workspace,
    )


# ------------------------------------------------------------------------------------------------- page setup
def _sections(path: Path) -> list[dict[str, Any]]:
    document = _docx(path)
    found = []
    for section in document.sections:
        found.append(
            {
                "width_mm": round(section.page_width / EMU_PER_MM, 1),
                "height_mm": round(section.page_height / EMU_PER_MM, 1),
                "orientation": "landscape" if section.page_width > section.page_height else "portrait",
                "margins_mm": {
                    side: round(getattr(section, f"{side}_margin") / EMU_PER_MM, 1)
                    for side in ("top", "bottom", "left", "right")
                },
            }
        )
    return found


def _run_page_setup_com(path: str, params: dict[str, Any]) -> dict[str, Any]:
    body = """
  $targets = @($params.sections)
  if ($document.Sections.Count -ne $targets.Count) { throw "WPS sees $($document.Sections.Count) sections; the file has $($targets.Count)." }
  for ($i = 0; $i -lt $targets.Count; $i++) {
    $target = $targets[$i]
    $page = $document.Sections.Item($i + 1).PageSetup
    $page.Orientation = [int]$target.orientation
    $page.PageWidth = [double]$target.width_pt
    $page.PageHeight = [double]$target.height_pt
    $page.TopMargin = [double]$target.top_pt
    $page.BottomMargin = [double]$target.bottom_pt
    $page.LeftMargin = [double]$target.left_pt
    $page.RightMargin = [double]$target.right_pt
  }
  $out.sections = $targets.Count
"""
    return _run_writer_script(path, params, body)


def _target_sections(before: list[dict[str, Any]], paper, orientation, margins) -> list[dict[str, Any]]:
    targets = []
    for section in before:
        width, height = section["width_mm"], section["height_mm"]
        if paper:
            width, height = PAPERS[paper]
        landscape = (orientation or section["orientation"]) == "landscape"
        short, long = sorted((width, height))
        width, height = (long, short) if landscape else (short, long)
        targets.append(
            {
                "width_mm": width,
                "height_mm": height,
                "orientation": "landscape" if landscape else "portrait",
                "margins_mm": {side: margins.get(side, section["margins_mm"][side]) for side in section["margins_mm"]},
            }
        )
    return targets


def _sections_match(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    if len(actual) != len(expected):
        return False
    for got, want in zip(actual, expected, strict=True):
        if got["orientation"] != want["orientation"]:
            return False
        if (
            abs(got["width_mm"] - want["width_mm"]) > TOLERANCE_MM
            or abs(got["height_mm"] - want["height_mm"]) > TOLERANCE_MM
        ):
            return False
        if any(abs(got["margins_mm"][side] - value) > TOLERANCE_MM for side, value in want["margins_mm"].items()):
            return False
    return True


@coordinated_mutation
@atomic_mutation
@_guarded
def set_writer_page_setup(
    document_id: str,
    request_id: str,
    paper: str | None = None,
    orientation: str | None = None,
    margins_mm: dict[str, float] | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Set paper, orientation and margins of every section, through WPS, with backup, read-back and rollback."""
    margins = {side: float(value) for side, value in (margins_mm or {}).items() if value is not None}
    replay = replay_operation(
        request_id,
        "writer-page-setup",
        {"document_id": document_id, "paper": paper, "orientation": orientation, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay
    if paper is not None and paper not in PAPERS:
        raise _Refusal("INVALID_ARGUMENT", f"paper must be one of: {', '.join(PAPERS)}.")
    if orientation is not None and orientation not in {"portrait", "landscape"}:
        raise _Refusal("INVALID_ARGUMENT", "orientation is portrait or landscape.")
    if any(side not in {"top", "bottom", "left", "right"} or not 0 <= value <= 200 for side, value in margins.items()):
        raise _Refusal("INVALID_ARGUMENT", "Margins are top, bottom, left and right, 0 to 200 mm.")
    if paper is None and orientation is None and not margins:
        raise _Refusal("INVALID_ARGUMENT", "Give a paper, an orientation or at least one margin.")
    path = _writer(document_id, "writer-page-setup", workspace)
    before = _sections(path)
    expected = _target_sections(before, paper, orientation, margins)
    preview = {
        "document_id": document_id,
        "path": str(path),
        "paper": paper,
        "orientation": orientation,
        "margins_mm": margins,
        "sections": len(before),
        "before": before,
        "expected": expected,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False
    params = {
        "sections": [
            {
                "orientation": 1 if target["orientation"] == "landscape" else 0,
                "width_pt": target["width_mm"] * PT_PER_MM,
                "height_pt": target["height_mm"] * PT_PER_MM,
                **{f"{side}_pt": value * PT_PER_MM for side, value in target["margins_mm"].items()},
            }
            for target in expected
        ]
    }

    def read_back():
        after = _sections(path)
        return {"sections_match": _sections_match(after, expected)}, {"after": after}

    return _commit(
        "writer-page-setup",
        document_id,
        request_id,
        path,
        preview,
        lambda: _run_page_setup_com(str(path), params),
        read_back,
        workspace,
    )


# ------------------------------------------------------------------------------------------------ style preset
_HEADING_NAME = re.compile(r"^(?:heading|标题)\s*([1-9])$", re.IGNORECASE)


def _outline_level(paragraph) -> int | None:
    """0-based outline level from the paragraph or its style chain, or the Heading N / 标题 N style name."""
    element = paragraph._p.pPr.find(f"{{{W}}}outlineLvl") if paragraph._p.pPr is not None else None
    if element is not None:
        return int(element.get(f"{{{W}}}val"))
    style = paragraph.style
    while style is not None:
        properties = style.element.pPr
        level = properties.find(f"{{{W}}}outlineLvl") if properties is not None else None
        if level is not None:
            return int(level.get(f"{{{W}}}val"))
        found = _HEADING_NAME.match(style.name or "")
        if found:
            return int(found.group(1)) - 1
        style = style.base_style
    return None


def classify_paragraphs(document) -> list[tuple[int, str]]:
    """(index in document.paragraphs, role) for every non-empty body paragraph: title, heading1-3 or body."""
    roles = []
    title_seen = False
    for index, paragraph in enumerate(document.paragraphs):
        if not paragraph.text.strip():
            continue
        if not title_seen:
            roles.append((index, "title"))
            title_seen = True
            continue
        level = _outline_level(paragraph)
        roles.append((index, f"heading{level + 1}" if level is not None and level < 3 else "body"))
    return roles


def _set_run_font(run, font: str, size_pt: float, bold: bool | None) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt

    run.font.name = font
    properties = run._r.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = properties.makeelement(qn("w:rFonts"), {})
        properties.insert(0, fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attribute), font)
    for attribute in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        fonts.attrib.pop(qn(attribute), None)
    run.font.size = Pt(size_pt)
    if bold is not None:
        run.font.bold = bold


def _first_line_chars(paragraph, chars: int, size_pt: float) -> None:
    """Indent the first line by chars characters: firstLineChars for WPS and Word, firstLine for other readers."""
    from docx.oxml.ns import qn

    properties = paragraph._p.get_or_add_pPr()
    indent = properties.find(qn("w:ind"))
    if indent is None:
        indent = properties.makeelement(qn("w:ind"), {})
        properties.append(indent)
    for attribute in ("w:hanging", "w:hangingChars"):
        indent.attrib.pop(qn(attribute), None)
    indent.set(qn("w:firstLineChars"), str(chars * 100))
    indent.set(qn("w:firstLine"), str(round(chars * size_pt * 20)))


def _apply_role(paragraph, spec: dict[str, Any], fonts: dict[str, str]) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.shared import Pt

    font = fonts.get(spec["font"], spec["font"])
    for run in paragraph.runs:
        _set_run_font(run, font, SIZES[spec["size"]], spec.get("bold"))
    formatting = paragraph.paragraph_format
    if spec.get("align") == "center":
        formatting.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if "line_exact_pt" in spec:
        formatting.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        formatting.line_spacing = Pt(spec["line_exact_pt"])
    if "line_multiple" in spec:
        formatting.line_spacing = spec["line_multiple"]
    if "first_line_chars" in spec:
        _first_line_chars(paragraph, spec["first_line_chars"], SIZES[spec["size"]])


def _page_number_paragraph(section, spec: dict[str, Any], fonts: dict[str, str]) -> None:
    """Give the section's footer a centred PAGE field in the preset's font; restyle one that is already there."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    footer = section.footer
    footer.is_linked_to_previous = False
    target = next(
        (p for p in footer.paragraphs if "PAGE" in "".join(t.text or "" for t in p._p.iter(qn("w:instrText")))), None
    )
    if target is None:
        target = (
            footer.paragraphs[0]
            if len(footer.paragraphs) == 1 and not footer.paragraphs[0].text.strip()
            else footer.add_paragraph()
        )
        run = target.add_run()
        for kind, text in (("begin", None), ("instr", " PAGE "), ("separate", None), ("end", None)):
            if kind == "instr":
                element = run._r.makeelement(qn("w:instrText"), {qn("xml:space"): "preserve"})
                element.text = text
            else:
                element = run._r.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): kind})
            run._r.append(element)
    target.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font = fonts.get(spec["font"], spec["font"])
    for run in target.runs:
        _set_run_font(run, font, SIZES[spec["size"]], None)


def _installed_fonts() -> set[str] | None:
    """Font family names installed on this Windows machine, or None when they cannot be listed."""
    script = """
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Drawing
  $names = @((New-Object System.Drawing.Text.InstalledFontCollection).Families | ForEach-Object { $_.Name })
  [pscustomobject]@{ ok = $true; fonts = $names } | ConvertTo-Json -Depth 3 -Compress
} catch {
  [pscustomobject]@{ ok = $false; error_message = $_.Exception.Message } | ConvertTo-Json -Compress
  exit 2
}
"""
    try:
        payload, failure = run_powershell_script(script)
    except OSError:
        return None
    if failure is not None or not payload.get("ok"):
        return None
    return {str(name) for name in payload.get("fonts") or []}


def preset_fonts(preset: str) -> list[str]:
    spec = PRESETS[preset]
    return sorted({part["font"] for key, part in spec.items() if isinstance(part, dict) and "font" in part})


def _expected_role(spec: dict[str, Any], fonts: dict[str, str]) -> dict[str, Any]:
    return {"font": fonts.get(spec["font"], spec["font"]), "size": SIZES[spec["size"]], "bold": spec.get("bold")}


def _check_styled(document, roles, preset: dict[str, Any], fonts: dict[str, str]) -> tuple[dict[str, bool], list[str]]:
    from docx.oxml.ns import qn

    problems = []
    for index, role in roles:
        paragraph = document.paragraphs[index]
        want = _expected_role(preset[role], fonts)
        for run in paragraph.runs:
            properties = run._r.rPr
            fonts_element = properties.find(qn("w:rFonts")) if properties is not None else None
            east_asia = fonts_element.get(qn("w:eastAsia")) if fonts_element is not None else None
            size = run.font.size.pt if run.font.size is not None else None
            if (
                east_asia != want["font"]
                or size != want["size"]
                or (want["bold"] is not None and run.font.bold != want["bold"])
            ):
                problems.append(f"paragraph {index + 1} ({role})")
                break
    footers_ok = all(
        any("PAGE" in (text.text or "") for text in section.footer._element.iter(qn("w:instrText")))
        for section in document.sections
    )
    return {"paragraphs_styled": not problems, "page_numbers": footers_ok}, problems


@coordinated_mutation
@atomic_mutation
@_guarded
def apply_writer_style(
    document_id: str,
    preset: str,
    request_id: str,
    font_map: dict[str, str] | None = None,
    allow_missing_fonts: bool = False,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Apply the gongwen or report preset: fonts, sizes, bold, line spacing, indents, paper, margins, page numbers."""
    replay = replay_operation(
        request_id, "writer-style-apply", {"document_id": document_id, "preset": preset, "dry_run": dry_run}, workspace
    )
    if replay is not None:
        return replay
    if preset not in PRESETS:
        raise _Refusal("INVALID_ARGUMENT", f"preset must be one of: {', '.join(PRESETS)}.")
    spec = PRESETS[preset]
    fonts = {str(key).strip(): str(value).strip() for key, value in (font_map or {}).items() if str(value).strip()}
    path = _writer(document_id, "writer-style-apply", workspace)
    document = _docx(path)
    roles = classify_paragraphs(document)
    needed = sorted({fonts.get(name, name) for name in preset_fonts(preset)})
    installed = _installed_fonts()
    missing = [name for name in needed if installed is not None and name not in installed]
    counts: dict[str, int] = {}
    for _index, role in roles:
        counts[role] = counts.get(role, 0) + 1
    preview = {
        "document_id": document_id,
        "path": str(path),
        "preset": preset,
        "font_map": fonts,
        "fonts_needed": needed,
        "fonts_checked": installed is not None,
        "missing_fonts": missing,
        "paragraph_roles": counts,
        "sections": len(document.sections),
        "dry_run": dry_run,
    }
    if missing and not allow_missing_fonts:
        raise _Refusal(
            FONT_NOT_INSTALLED,
            "These fonts are not installed: " + ", ".join(missing) + ". Install them, map each to an installed font "
            "(font_map, such as 方正小标宋简体=宋体), or allow_missing_fonts to keep the names. Nothing was changed.",
            preview,
        )
    if dry_run:
        return True, preview, [], False
    texts_before = docx_body_paragraphs(path)
    backup_ok, backup, backup_errors, backup_replayed = create_backup(
        document_id, f"{request_id}:backup", workspace=workspace
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup}, backup_errors, False
    from docx.enum.section import WD_ORIENT

    for index, role in roles:
        _apply_role(document.paragraphs[index], spec[role], fonts)
    width, height = PAPERS[spec["paper"]]
    for section in document.sections:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = int(width * EMU_PER_MM)
        section.page_height = int(height * EMU_PER_MM)
        for side, value in spec["margins_mm"].items():
            setattr(section, f"{side}_margin", int(value * EMU_PER_MM))
        _page_number_paragraph(section, spec["page_number"], fonts)
    buffer = io.BytesIO()
    document.save(buffer)
    _replace_file(path, buffer.getvalue())
    record_after_com_identity(path, file_identity(path))  # this command's own write, for a rollback check

    reread = _docx(path)
    checks, problems = _check_styled(reread, classify_paragraphs(reread), spec, fonts)
    checks["text_unchanged"] = docx_body_paragraphs(path) == texts_before
    expected_sections = [
        {"width_mm": width, "height_mm": height, "orientation": "portrait", "margins_mm": dict(spec["margins_mm"])}
        for _ in reread.sections
    ]
    checks["page_setup"] = _sections_match(_sections(path), expected_sections)
    validation_passed = all(checks.values())
    result = {
        **preview,
        "dry_run": False,
        "backup": backup,
        "backup_replayed": backup_replayed,
        "checks": checks,
        "unstyled_paragraphs": problems[:20],
        "validation_passed": validation_passed,
    }
    if not validation_passed:
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": f"The styled document did not read back: {failed}."}],
            False,
        )
    record_operation(request_id, "writer-style-apply", result, workspace)
    return True, result, [], False
