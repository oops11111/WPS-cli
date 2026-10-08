import json
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from tests.test_presentation_ops import write_minimal_pptx
from wps_ai_agent_cli.presentation_ops import presentation_replace
from wps_ai_agent_cli.capabilities import powershell_executable, probe_wps_capabilities
from wps_ai_agent_cli.presentation_text import (
    PresentationStructureError, count_text_in_pptx, pptx_slide_texts, pptx_text_objects,
)
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.snapshots import snapshot_document


def replace_part(path, name, payload):
    with ZipFile(path) as archive:
        parts = {entry: archive.read(entry) for entry in archive.namelist()}
    parts[name] = payload
    with ZipFile(path, "w") as archive:
        for entry, content in parts.items():
            archive.writestr(entry, content)


class PresentationOrderTests(unittest.TestCase):
    def test_reordered_noncontiguous_parts_drive_reads_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "deck.pptx"
            write_minimal_pptx(path, ["alpha", "orphan", "alpha alpha"], order=[3, 1])
            before = path.read_bytes()
            slides = pptx_slide_texts(path)
            self.assertEqual([slide["part"] for slide in slides], ["ppt/slides/slide3.xml", "ppt/slides/slide1.xml"])
            self.assertEqual([slide["slide_index"] for slide in slides], [1, 2])
            self.assertEqual(count_text_in_pptx(path, "alpha", slide_index=1), 2)
            self.assertEqual(count_text_in_pptx(path, "orphan"), 0)
            self.assertEqual(pptx_text_objects(path)[0]["text"], "alpha alpha")
            _, record, _ = register_document("presentation", str(path), workspace)
            with patch("wps_ai_agent_cli.presentation_ops._run_presentation_replace_com") as com:
                ok, result, errors, replayed = presentation_replace(
                    record["document_id"], "alpha", "beta", "reordered-dry",
                    dry_run=True, slide_index=1, workspace=workspace,
                )
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertFalse(replayed)
            self.assertEqual(result["matches"], 2)
            self.assertEqual(result["slide_count"], 2)
            com.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_snapshots_keep_blank_and_image_only_slides(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "deck.pptx"
            write_minimal_pptx(path, ["text", "image", "blank"], order=[3, 1, 2])
            for index, shape in [(3, ""), (2, "<p:pic/>")]:
                replace_part(path, f"ppt/slides/slide{index}.xml", f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree>{shape}</p:spTree></p:cSld></p:sld>')
            _, record, _ = register_document("presentation", str(path), workspace)
            ok, result, errors = snapshot_document(record["document_id"], workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["slide_count"], 3)
            self.assertEqual([slide["text_object_count"] for slide in result["slides"]], [0, 1, 0])
            self.assertEqual(result["slides"][1]["objects"][0]["preview"], "text")
            self.assertEqual(result["slides"][0]["objects"], [])

    def test_snapshot_captures_grouped_shape_text_and_table_without_duplicate_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "objects.pptx"
            write_minimal_pptx(path, ["placeholder"])
            slide_xml = '''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<p:cSld><p:spTree>
<p:grpSp><p:nvGrpSpPr/><p:grpSpPr/>
<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:txBody><a:p><a:r><a:t>Group A</a:t></a:r></a:p></p:txBody></p:sp>
<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:txBody><a:p><a:r><a:t>Group B</a:t></a:r></a:p></p:txBody></p:sp>
</p:grpSp>
<p:graphicFrame><a:graphic><a:graphicData><a:tbl>
<a:tr><a:tc><a:txBody><a:p><a:r><a:t>Cell 1</a:t></a:r></a:p></a:txBody></a:tc><a:tc><a:txBody><a:p><a:r><a:t>Cell 2</a:t></a:r></a:p></a:txBody></a:tc></a:tr>
<a:tr><a:tc><a:txBody><a:p><a:r><a:t>Cell 3</a:t></a:r></a:p></a:txBody></a:tc><a:tc><a:txBody><a:p/></a:txBody></a:tc></a:tr>
</a:tbl></a:graphicData></a:graphic></p:graphicFrame>
<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:txBody><a:p><a:r><a:t>Outside</a:t></a:r></a:p></p:txBody></p:sp>
</p:spTree></p:cSld></p:sld>'''
            replace_part(path, "ppt/slides/slide1.xml", slide_xml)

            objects = pptx_text_objects(path)
            self.assertEqual([item["object_index"] for item in objects], [1, 2, 3, 4])
            self.assertEqual([item["object_type"] for item in objects], ["shape", "shape", "table", "shape"])
            self.assertEqual([item["text"] for item in objects], ["Group A", "Group B", "Cell 1\tCell 2\nCell 3\t", "Outside"])
            self.assertEqual(sum(item["text"].count("Cell 1") for item in objects), 1)
            self.assertEqual(count_text_in_pptx(path, "AGroup"), 0)
            self.assertEqual(count_text_in_pptx(path, "2\tCell"), 0)

            _, record, _ = register_document("presentation", str(path), workspace)
            ok, result, errors = snapshot_document(record["document_id"], workspace)
            self.assertTrue(ok, errors)
            self.assertEqual(result["text_object_count"], 4)
            snapshot_objects = result["slides"][0]["objects"]
            self.assertEqual([item["object_type"] for item in snapshot_objects], ["shape", "shape", "table", "shape"])
            self.assertEqual(snapshot_objects[2]["preview"], "Cell 1 Cell 2 Cell 3")

    def test_replace_requires_exact_slide_text_readback(self):
        for replacement_xml, expected_ok in ((b"gamma beta", True), (b"gamma damaged", False)):
            with self.subTest(expected_ok=expected_ok), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                path = workspace / "deck.pptx"
                write_minimal_pptx(path, ["alpha beta", "untouched"])
                _, record, _ = register_document("presentation", str(path), workspace)

                def simulated_wps(*_args, **_kwargs):
                    with ZipFile(path) as archive:
                        parts = {entry: archive.read(entry) for entry in archive.namelist()}
                    parts["ppt/slides/slide1.xml"] = parts["ppt/slides/slide1.xml"].replace(b"alpha beta", replacement_xml)
                    with ZipFile(path, "w") as archive:
                        for entry, payload in parts.items():
                            archive.writestr(entry, payload)
                    return {"ok": True, "errors": [], "data": {"backend": "mock", "replace_count": 1, "text_shape_count": 1, "table_cell_count": 0}}

                with patch("wps_ai_agent_cli.presentation_ops._run_presentation_replace_com", side_effect=simulated_wps):
                    ok, result, errors, _replayed = presentation_replace(
                        record["document_id"], "alpha", "gamma", f"replace-{expected_ok}", workspace=workspace,
                    )

                self.assertEqual(ok, expected_ok)
                self.assertEqual(result["text_readback_matches"], expected_ok)
                self.assertEqual(result["backend_count_matches"], True)
                if expected_ok:
                    self.assertEqual(errors, [])
                else:
                    self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")

    def test_empty_deck_ignores_unreferenced_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deck.pptx"
            write_minimal_pptx(path, ["orphan"], order=[])
            self.assertEqual(pptx_slide_texts(path), [])
            self.assertEqual(pptx_text_objects(path), [])

    def test_invalid_relationships_fail_before_mutation(self):
        relationships = [
            "",
            '<Relationship Id="rId1" Type="wrong" Target="slides/slide1.xml"/>',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="https://example.invalid/slide.xml" TargetMode="External"/>',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/missing.xml"/>',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "deck.pptx"
            for rel in relationships:
                with self.subTest(relationship=rel):
                    write_minimal_pptx(path, ["alpha"])
                    replace_part(path, "ppt/_rels/presentation.xml.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rel}</Relationships>')
                    with self.assertRaises(PresentationStructureError):
                        pptx_slide_texts(path)
                    _, record, _ = register_document("presentation", str(path), workspace)
                    with patch("wps_ai_agent_cli.presentation_ops.create_backup") as backup, patch("wps_ai_agent_cli.presentation_ops._run_presentation_replace_com") as com:
                        ok, _, errors, _ = presentation_replace(record["document_id"], "alpha", "beta", "invalid", workspace=workspace)
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], "INVALID_PRESENTATION_STRUCTURE")
                    backup.assert_not_called()
                    com.assert_not_called()
                    ok, _, errors = snapshot_document(record["document_id"], workspace)
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], "INVALID_PRESENTATION_STRUCTURE")

    def test_absolute_part_target_is_resolved_in_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deck.pptx"
            write_minimal_pptx(path, ["alpha"])
            with ZipFile(path) as archive:
                rels = archive.read("ppt/_rels/presentation.xml.rels").replace(b'Target="slides/', b'Target="/ppt/slides/')
            replace_part(path, "ppt/_rels/presentation.xml.rels", rels)
            self.assertEqual(count_text_in_pptx(path, "alpha", slide_index=1), 1)


@unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_INTEGRATION") == "1", "Requires explicit local WPS integration run")
class PresentationNestedReplaceWpsIntegrationTests(unittest.TestCase):
    def test_replace_reaches_grouped_shapes_and_table_cells_with_exact_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            document = workspace / "nested.pptx"
            capabilities = probe_wps_capabilities()
            prog_id = capabilities["components"]["presentation"]["selected_prog_id"]
            self.assertTrue(prog_id, capabilities)
            params = json.dumps({"prog_id": prog_id, "path": str(document)})
            script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params}
'@ | ConvertFrom-Json
$app = $null; $deck = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $deck = $app.Presentations.Add()
  $slide = $deck.Slides.Add(1, 12)
  $first = $slide.Shapes.AddTextbox(1, 20, 20, 220, 45)
  $first.TextFrame.TextRange.Text = 'group needle one'
  $second = $slide.Shapes.AddTextbox(1, 20, 75, 220, 45)
  $second.TextFrame.TextRange.Text = 'group needle two'
  $members = [object[]]@($first.Name, $second.Name)
  [void]$slide.Shapes.Range($members).Group()
  $table = $slide.Shapes.AddTable(2, 2, 300, 20, 260, 100).Table
  $table.Cell(1, 1).Shape.TextFrame.TextRange.Text = 'table needle A'
  $table.Cell(1, 2).Shape.TextFrame.TextRange.Text = 'table needle B'
  $table.Cell(2, 1).Shape.TextFrame.TextRange.Text = 'untouched'
  $deck.SaveAs($params.path, 24)
}} finally {{
  if ($deck -ne $null) {{ try {{ $deck.Close() }} catch {{ }} }}
  if ($app -ne $null) {{ try {{ $app.Quit() }} catch {{ }} }}
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}}
"""
            completed = subprocess.run(
                [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            self.assertTrue(document.exists())
            ok, record, errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok, errors)

            ok, result, errors, replayed = presentation_replace(
                record["document_id"], "needle", "token", "nested-shape-table-replace", workspace=workspace,
            )

            self.assertTrue(ok, errors)
            self.assertFalse(replayed)
            self.assertEqual(result["matches_before"], 4)
            self.assertEqual(result["backend_replace_count"], 4)
            self.assertEqual(result["table_cell_count"], 4)
            self.assertTrue(result["text_readback_matches"])
            self.assertEqual(count_text_in_pptx(document, "needle"), 0)
            self.assertEqual(count_text_in_pptx(document, "token"), 4)

    def test_replace_preserves_unaffected_mixed_run_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            document = workspace / "formatted.pptx"
            capabilities = probe_wps_capabilities()
            prog_id = capabilities["components"]["presentation"]["selected_prog_id"]
            self.assertTrue(prog_id, capabilities)
            params = json.dumps({"prog_id": prog_id, "path": str(document)})
            script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params}
'@ | ConvertFrom-Json
$app = $null; $deck = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $deck = $app.Presentations.Add()
  $slide = $deck.Slides.Add(1, 12)
  $shape = $slide.Shapes.AddTextbox(1, 20, 20, 420, 60)
  $range = $shape.TextFrame.TextRange
  $range.Text = 'Keep MID tail'
  $range.Characters(6, 3).Font.Bold = -1
  $range.Characters(9, 5).Font.Italic = -1
  $deck.SaveAs($params.path, 24)
}} finally {{
  if ($deck -ne $null) {{ try {{ $deck.Close() }} catch {{ }} }}
  if ($app -ne $null) {{ try {{ $app.Quit() }} catch {{ }} }}
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}}
"""
            completed = subprocess.run(
                [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            ok, record, errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok, errors)

            ok, result, errors, _replayed = presentation_replace(
                record["document_id"], "MID", "center", "formatted-replace", workspace=workspace,
            )

            self.assertTrue(ok, f"{errors}; result={result}")
            self.assertTrue(result["text_readback_matches"])
            with ZipFile(document) as archive:
                slide = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            runs = {}
            for run in slide.findall(".//a:r", ns):
                text_node = run.find("a:t", ns)
                props = run.find("a:rPr", ns)
                if text_node is not None:
                    runs[text_node.text or ""] = props.attrib if props is not None else {}
            self.assertEqual("".join(runs), "Keep center tail")
            self.assertNotEqual(runs.get("Keep ", {}).get("b"), "1", repr(runs))
            self.assertEqual(runs.get("center", {}).get("b"), "1", repr(runs))
            self.assertEqual(runs.get(" tail", {}).get("i"), "1", repr(runs))


if __name__ == "__main__":
    unittest.main()
