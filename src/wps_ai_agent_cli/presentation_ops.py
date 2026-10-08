from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import powershell_executable, probe_wps_capabilities
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .mutation_lock import coordinated_mutation
from .operations import record_operation, replay_operation
from .presentation_text import PresentationStructureError, count_text_in_pptx, pptx_slide_texts, pptx_text_objects
from .sessions import get_document
from .wps_script_snippets import QUIT_IF_IDLE


def _run_presentation_replace_com(
    path: str,
    find_text: str,
    replace_text: str,
    slide_index: int | None = None,
) -> dict[str, Any]:
    capabilities = probe_wps_capabilities()
    selected_prog_id = capabilities["components"]["presentation"]["selected_prog_id"]
    if not selected_prog_id:
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_BACKEND_UNAVAILABLE,
                    "message": "No registered WPS ProgID detected for presentation.",
                }
            ],
            "data": {"capabilities": capabilities},
        }

    params = {
        "prog_id": selected_prog_id,
        "path": str(Path(path).resolve()),
        "find_text": find_text,
        "replace_text": replace_text,
        "slide_index": slide_index,
    }
    params_json = json.dumps(params)
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
$app = $null
$presentation = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $presentation = $app.Presentations.Open($params.path, $false, $false, $false)
  $findText = [string]$params.find_text
  $replaceText = [string]$params.replace_text
  $script:replaceCount = 0
  $script:textShapeCount = 0
  $script:tableCellCount = 0
  function ReplaceInTextRange($textRange) {{
    $text = [string]$textRange.Text
    $searchAfter = 0
    while ($searchAfter -le $text.Length - $findText.Length) {{
      $matchIndex = $text.IndexOf($findText, [int]$searchAfter, [System.StringComparison]::Ordinal)
      if ($matchIndex -lt 0) {{ break }}
      $match = $textRange.Characters(([int]$matchIndex + 1), $findText.Length)
      $sourceFont = $textRange.Characters(([int]$matchIndex + 1), 1).Font
      $fontStyle = @{{
        Bold = $sourceFont.Bold
        Italic = $sourceFont.Italic
        Underline = $sourceFont.Underline
        Name = $sourceFont.Name
        Size = $sourceFont.Size
        Color = $sourceFont.Color.RGB
      }}
      $match.Text = $replaceText
      if ($replaceText.Length -gt 0) {{
        $replacement = $textRange.Characters(([int]$matchIndex + 1), $replaceText.Length)
        $replacement.Font.Bold = $fontStyle.Bold
        $replacement.Font.Italic = $fontStyle.Italic
        $replacement.Font.Underline = $fontStyle.Underline
        $replacement.Font.Name = $fontStyle.Name
        $replacement.Font.Size = $fontStyle.Size
        $replacement.Font.Color.RGB = $fontStyle.Color
      }}
      $script:replaceCount += 1
      $text = [string]$textRange.Text
      $searchAfter = $matchIndex + $replaceText.Length
    }}
  }}
  function VisitShape($shape) {{
    if ([int]$shape.Type -eq 6) {{
      for ($itemIndex = 1; $itemIndex -le $shape.GroupItems.Count; $itemIndex++) {{
        VisitShape $shape.GroupItems.Item($itemIndex)
      }}
      return
    }}
    $hasTable = $false
    try {{ $hasTable = [int]$shape.HasTable -ne 0 }} catch {{ }}
    if ($hasTable) {{
      $table = $shape.Table
      for ($rowIndex = 1; $rowIndex -le $table.Rows.Count; $rowIndex++) {{
        for ($columnIndex = 1; $columnIndex -le $table.Columns.Count; $columnIndex++) {{
          $cellShape = $table.Cell($rowIndex, $columnIndex).Shape
          $script:tableCellCount += 1
          if ([int]$cellShape.TextFrame.HasText -ne 0) {{
            $script:textShapeCount += 1
            ReplaceInTextRange $cellShape.TextFrame.TextRange
          }}
        }}
      }}
      return
    }}
    $hasText = $false
    try {{
      $hasText = ([int]$shape.HasTextFrame -ne 0) -and ([int]$shape.TextFrame.HasText -ne 0)
    }} catch {{ $hasText = $false }}
    if ($hasText) {{
      $script:textShapeCount += 1
      ReplaceInTextRange $shape.TextFrame.TextRange
    }}
  }}
  $targetSlideIndex = $null
  if ($null -ne $params.slide_index) {{
    $targetSlideIndex = [int]$params.slide_index
    if ($targetSlideIndex -lt 1 -or $targetSlideIndex -gt $presentation.Slides.Count) {{
      throw "Slide index out of range: $targetSlideIndex"
    }}
  }}

  for ($slideIndex = 1; $slideIndex -le $presentation.Slides.Count; $slideIndex++) {{
    if ($null -ne $targetSlideIndex -and $slideIndex -ne $targetSlideIndex) {{ continue }}
    $slide = $presentation.Slides.Item($slideIndex)
    for ($shapeIndex = 1; $shapeIndex -le $slide.Shapes.Count; $shapeIndex++) {{
      VisitShape $slide.Shapes.Item($shapeIndex)
    }}
  }}
  $presentation.Save()

  [pscustomobject]@{{
    ok = $true
    backend = 'powershell-com'
    component = 'presentation'
    prog_id = $params.prog_id
    path = $params.path
    find_text = $params.find_text
    replace_text = $params.replace_text
    slide_index = $params.slide_index
    slide_count = $presentation.Slides.Count
    text_shape_count = $script:textShapeCount
    table_cell_count = $script:tableCellCount
    replace_count = $script:replaceCount
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    backend = 'powershell-com'
    component = 'presentation'
    prog_id = $params.prog_id
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($presentation -ne $null) {{
    try {{ $presentation.Close() }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ {QUIT_IF_IDLE} }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }}
  }}
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".ps1",
            delete=False,
            encoding="utf-8-sig",
        ) as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [
                powershell_executable(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=120,
        )
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except OSError:
                pass

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None

    if completed.returncode != 0 or not isinstance(payload, dict):
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": (
                        payload.get("error_message")
                        if isinstance(payload, dict)
                        else (completed.stderr or completed.stdout).strip()
                    ),
                }
            ],
            "data": {"diagnostic": payload, "backend": "powershell-com"},
        }
    return {"ok": True, "errors": [], "data": payload}


@coordinated_mutation
def presentation_replace(
    document_id: str,
    find_text: str,
    replace_text: str,
    request_id: str,
    dry_run: bool = False,
    slide_index: int | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "presentation-replace",
        {"document_id": document_id, "find_text": find_text, "replace_text": replace_text, "slide_index": slide_index, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    if not find_text:
        return (
            False,
            {},
            [{"code": "INVALID_ARGUMENT", "message": "find_text must not be empty."}],
            False,
        )
    if slide_index is not None and slide_index < 1:
        return (
            False,
            {},
            [{"code": "INVALID_ARGUMENT", "message": "slide_index must be 1 or greater."}],
            False,
        )

    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            False,
        )
    if document["component"] != "presentation":
        return (
            False,
            {"document": document},
            [{"code": "UNSUPPORTED_COMPONENT", "message": "presentation-replace requires a presentation document."}],
            False,
        )

    path = Path(document["path"])
    if not path.exists():
        return (
            False,
            {"document": document},
            [{"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {path}"}],
            False,
        )

    try:
        slides = pptx_slide_texts(path)
    except PresentationStructureError as exc:
        return False, {"document": document}, [{"code": "INVALID_PRESENTATION_STRUCTURE", "message": str(exc)}], False
    slide_count = len(slides)
    if slide_index is not None and not any(slide["slide_index"] == slide_index for slide in slides):
        return (
            False,
            {
                "document_id": document_id,
                "component": "presentation",
                "path": str(path),
                "slide_index": slide_index,
                "slide_count": slide_count,
            },
            [{"code": "SLIDE_NOT_FOUND", "message": f"Slide index out of range: {slide_index}"}],
            False,
        )

    before_objects = pptx_text_objects(path)
    before_count = sum(
        str(segment).count(find_text)
        for item in before_objects
        if slide_index is None or int(item["slide_index"]) == slide_index
        for segment in item.get("match_segments", [item["text"]])
    )
    preview = {
        "document_id": document_id,
        "component": "presentation",
        "path": str(path),
        "find_text": find_text,
        "replace_text": replace_text,
        "scope": "slide" if slide_index is not None else "deck",
        "slide_index": slide_index,
        "slide_count": slide_count,
        "matches": before_count,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False
    if before_count == 0:
        return (
            False,
            preview,
            [{"code": "TEXT_NOT_FOUND", "message": "No matching text found before replace."}],
            False,
        )

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    replace_result = guarded_com_mutation(
        path, backup_result,
        lambda: _run_presentation_replace_com(
            str(path), find_text, replace_text, slide_index=slide_index,
        ),
    )
    if not replace_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "replace": replace_result["data"]}, replace_result["errors"], False

    after_objects = pptx_text_objects(path)
    def object_signature(item: dict[str, Any], expected: bool) -> tuple[Any, ...]:
        segments = tuple(
            str(segment).replace(find_text, replace_text)
            if expected and (slide_index is None or int(item["slide_index"]) == slide_index)
            else str(segment)
            for segment in item.get("match_segments", [item["text"]])
        )
        return int(item["slide_index"]), int(item["object_index"]), item["object_type"], segments

    expected_objects = [object_signature(item, True) for item in before_objects]
    actual_objects = [object_signature(item, False) for item in after_objects]
    text_readback_matches = actual_objects == expected_objects
    backend_count_matches = replace_result["data"].get("replace_count") == before_count
    remaining_find_count = count_text_in_pptx(path, find_text, slide_index=slide_index)
    validation_passed = text_readback_matches and backend_count_matches
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "replace_backend": replace_result["data"].get("backend"),
        "backend_replace_count": replace_result["data"].get("replace_count"),
        "text_shape_count": replace_result["data"].get("text_shape_count"),
        "table_cell_count": replace_result["data"].get("table_cell_count"),
        "matches_before": before_count,
        "remaining_find_count": remaining_find_count,
        "backend_count_matches": backend_count_matches,
        "text_readback_matches": text_readback_matches,
        "validation_passed": validation_passed,
    }
    post_error = verify_post_com_source(path, replace_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": "WPS replacement count or exact slide-text read-back did not match the expected result."}],
            False,
        )

    record_operation(request_id, "presentation-replace", result, workspace)
    return True, result, [], False
