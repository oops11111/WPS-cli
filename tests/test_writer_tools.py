"""writer-insert-image, writer-page-setup and writer-style-apply (C-06).

The two WPS commands are simulated with python-docx (the stand-in makes the change and saves the way WPS would),
so their offline read-back runs on a real package; writer-style-apply runs for real, with the font list mocked.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt
    from PIL import Image
except ImportError as exc:  # optional test dependency: skip this module instead of erroring the suite
    raise unittest.SkipTest("python-docx and Pillow are needed") from exc

from wps_ai_agent_cli import writer_tools as tools
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.sessions import register_document

ALL_FONTS = {"方正小标宋简体", "黑体", "楷体_GB2312", "仿宋_GB2312", "宋体"}


def build_document(path: Path) -> Path:
    document = Document()
    document.add_paragraph("关于开展检查的通知")
    document.add_heading("一、总体要求", 1)
    document.add_paragraph("正文第一段。")
    document.add_heading("（一）工作目标", 2)
    document.add_paragraph("正文第二段，含 English 和数字 2026。")
    document.add_heading("1. 具体任务", 3)
    document.add_paragraph("")
    document.add_paragraph("结尾。")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "表格里的字不算正文段落"
    document.save(path)
    return path


def wps_insert_image(*, misplace=False, wrong_width=False):
    def run_com(path, params):
        document = Document(path)
        anchor = document.paragraphs[params["paragraph_index"] - (2 if misplace else 1)]
        new = document.add_paragraph()
        anchor._p.addnext(new._p)
        width_mm = params["width_pt"] / tools.PT_PER_MM * (1.2 if wrong_width else 1)
        new.add_run().add_picture(params["image_path"], width=Mm(width_mm))
        if params["caption"]:
            caption = document.add_paragraph(params["caption"])
            new._p.addnext(caption._p)
        document.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps"}}

    return run_com


def wps_page_setup(*, off_by_mm=0.0):
    def run_com(path, params):
        document = Document(path)
        for section, target in zip(document.sections, params["sections"], strict=True):
            section.page_width = int(target["width_pt"] / tools.PT_PER_MM * tools.EMU_PER_MM)
            section.page_height = int(target["height_pt"] / tools.PT_PER_MM * tools.EMU_PER_MM)
            for side in ("top", "bottom", "left", "right"):
                value = target[f"{side}_pt"] / tools.PT_PER_MM + (off_by_mm if side == "top" else 0)
                setattr(section, f"{side}_margin", int(value * tools.EMU_PER_MM))
        document.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps", "sections": len(document.sections)}}

    return run_com


class WriterToolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "ws"
        self.workspace.mkdir()
        self.path = build_document(self.root / "通知.docx")
        self.picture = self.root / "图.png"
        Image.new("RGB", (400, 200), "steelblue").save(self.picture, dpi=(96, 96))
        ok, record, errors = register_document("writer", str(self.path), self.workspace)
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]

    # ------------------------------------------------------------------------------------------ insert image
    def insert(self, com=None, request_id="i1", **options):
        with patch.object(tools, "_run_insert_image_com", side_effect=com or wps_insert_image()) as fake:
            outcome = tools.insert_writer_image(
                self.document_id, str(self.picture), request_id, workspace=self.workspace, **options
            )
        self.calls = fake.call_args_list
        return outcome

    def test_insert_after_a_paragraph_with_a_caption(self):
        ok, result, errors, _ = self.insert(at_paragraph=3, width_mm=80, caption="图 1 示意")
        self.assertTrue(ok, errors)
        self.assertTrue(all(result["checks"].values()), result["checks"])
        texts = [p.text for p in Document(str(self.path)).paragraphs]
        self.assertEqual(texts[2:5], ["正文第一段。", "", "图 1 示意"])
        self.assertEqual(result["height_mm"], 40.0)  # 400 x 200 px keeps its proportions

    def test_the_default_width_is_the_picture_but_at_most_the_text_width(self):
        ok, result, _errors, _ = self.insert(at_end=True, dry_run=True)
        self.assertTrue(ok)
        self.assertAlmostEqual(result["width_mm"], 105.8, places=1)  # 400 px at 96 dpi
        Image.new("RGB", (4000, 1000)).save(self.picture, dpi=(96, 96))
        ok, result, _errors, _ = self.insert(at_end=True, dry_run=True, request_id="i2")
        self.assertEqual(result["width_mm"], result["text_width_mm"])
        self.assertEqual(self.calls, [])

    def test_after_text_finds_the_first_paragraph(self):
        ok, result, errors, _ = self.insert(after_text="正文第二段")
        self.assertTrue(ok, errors)
        self.assertEqual(result["after_paragraph"], 5)
        self.assertEqual(self.calls[0].args[1]["expected_text"], "正文第二段，含 English 和数字 2026。")

    def test_a_misplaced_or_wrong_size_picture_is_rolled_back(self):
        before = self.path.read_bytes()
        for index, com in enumerate((wps_insert_image(misplace=True), wps_insert_image(wrong_width=True))):
            with self.subTest(index=index):
                ok, result, errors, _ = self.insert(com=com, at_paragraph=3, width_mm=60, request_id=f"bad{index}")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
                self.assertTrue(result["rollback"]["performed"], result.get("rollback"))
                self.assertEqual(self.path.read_bytes(), before)

    def test_insert_refusals(self):
        (self.root / "x.txt").write_text("x")
        cases = [
            ({}, "INVALID_ARGUMENT"),
            ({"at_paragraph": 1, "at_end": True}, "INVALID_ARGUMENT"),
            ({"at_paragraph": 99}, "PARAGRAPH_NOT_FOUND"),
            ({"after_text": "没有这段"}, "TEXT_NOT_FOUND"),
            ({"at_end": True, "width_mm": 2}, "INVALID_ARGUMENT"),
            ({"at_end": True, "caption": "a\nb"}, "INVALID_ARGUMENT"),
        ]
        for index, (options, code) in enumerate(cases):
            with self.subTest(options=options):
                ok, _result, errors, _ = self.insert(request_id=f"r{index}", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
        with patch.object(tools, "_run_insert_image_com") as com:
            ok, _r, errors, _ = tools.insert_writer_image(
                self.document_id, str(self.root / "x.txt"), "txt", at_end=True, workspace=self.workspace
            )
        self.assertEqual(errors[0]["code"], "INVALID_INPUT")
        com.assert_not_called()

    # -------------------------------------------------------------------------------------------- page setup
    def page(self, com=None, request_id="p1", **options):
        with patch.object(tools, "_run_page_setup_com", side_effect=com or wps_page_setup()) as fake:
            outcome = tools.set_writer_page_setup(self.document_id, request_id, workspace=self.workspace, **options)
        self.calls = fake.call_args_list
        return outcome

    def test_paper_orientation_and_margins_read_back(self):
        ok, result, errors, _ = self.page(paper="A3", orientation="landscape", margins_mm={"top": 30, "left": 20})
        self.assertTrue(ok, errors)
        after = result["read_back"]["after"][0]
        self.assertEqual((after["width_mm"], after["height_mm"], after["orientation"]), (420.0, 297.0, "landscape"))
        self.assertEqual((after["margins_mm"]["top"], after["margins_mm"]["left"]), (30.0, 20.0))
        self.assertEqual(result["sections"], 1)

    def test_a_margin_that_reads_back_wrong_is_rolled_back(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.page(com=wps_page_setup(off_by_mm=3), margins_mm={"top": 30})
        self.assertFalse(ok)
        self.assertFalse(result["checks"]["sections_match"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_page_setup_refusals(self):
        for index, options in enumerate(
            ({}, {"paper": "B4"}, {"orientation": "sideways"}, {"margins_mm": {"top": 300}})
        ):
            with self.subTest(options=options):
                ok, _result, errors, _ = self.page(request_id=f"r{index}", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                self.assertEqual(self.calls, [])

    # ------------------------------------------------------------------------------------------ style preset
    def style(self, preset, fonts=ALL_FONTS, request_id="s1", **options):
        with patch.object(tools, "_installed_fonts", return_value=fonts):
            return tools.apply_writer_style(self.document_id, preset, request_id, workspace=self.workspace, **options)

    def test_gongwen_formats_each_role_and_keeps_the_text(self):
        before = [p.text for p in Document(str(self.path)).paragraphs]
        ok, result, errors, _ = self.style("gongwen")
        self.assertTrue(ok, errors)
        self.assertEqual(
            result["paragraph_roles"], {"title": 1, "heading1": 1, "body": 3, "heading2": 1, "heading3": 1}
        )
        document = Document(str(self.path))
        self.assertEqual([p.text for p in document.paragraphs], before)
        title, heading1, body = document.paragraphs[0], document.paragraphs[1], document.paragraphs[2]
        fonts = title.runs[0]._r.rPr.find(qn("w:rFonts"))
        self.assertEqual((fonts.get(qn("w:eastAsia")), title.runs[0].font.size.pt), ("方正小标宋简体", 22.0))
        self.assertEqual(heading1.runs[0].font.size.pt, 16.0)
        self.assertTrue(document.paragraphs[3].runs[0].font.bold)  # 楷体 heading 2 is bold
        self.assertEqual(body.paragraph_format.line_spacing.pt, 28.0)
        self.assertEqual(body._p.pPr.find(qn("w:ind")).get(qn("w:firstLineChars")), "200")
        section = document.sections[0]
        self.assertEqual(round(section.top_margin / tools.EMU_PER_MM), 37)
        self.assertEqual(round(section.right_margin / tools.EMU_PER_MM), 26)
        self.assertTrue(result["checks"]["page_numbers"])
        # Table cells are not body paragraphs: their text is left as it was.
        self.assertIsNone(document.tables[0].cell(0, 0).paragraphs[0].runs[0].font.size)

    def test_report_uses_one_and_a_half_lines(self):
        ok, _result, errors, _ = self.style("report")
        self.assertTrue(ok, errors)
        body = Document(str(self.path)).paragraphs[2]
        self.assertEqual(body.paragraph_format.line_spacing, 1.5)
        self.assertEqual(body.runs[0].font.size.pt, 12.0)

    def test_missing_fonts_are_listed_and_refused_unless_mapped_or_allowed(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.style("gongwen", fonts={"宋体", "黑体"})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "FONT_NOT_INSTALLED")
        self.assertEqual(result["missing_fonts"], ["仿宋_GB2312", "方正小标宋简体", "楷体_GB2312"])
        self.assertEqual(self.path.read_bytes(), before)
        mapping = {"方正小标宋简体": "宋体", "仿宋_GB2312": "宋体", "楷体_GB2312": "黑体"}
        ok, result, errors, _ = self.style("gongwen", fonts={"宋体", "黑体"}, font_map=mapping, request_id="s2")
        self.assertTrue(ok, errors)
        title = Document(str(self.path)).paragraphs[0].runs[0]
        self.assertEqual(title._r.rPr.find(qn("w:rFonts")).get(qn("w:eastAsia")), "宋体")
        ok, _result, errors, _ = self.style("report", fonts=set(), allow_missing_fonts=True, request_id="s3")
        self.assertTrue(ok, errors)

    def test_style_dry_run_and_a_failed_read_back(self):
        before = self.path.read_bytes()
        ok, result, _errors, _ = self.style("gongwen", dry_run=True)
        self.assertTrue(ok)
        self.assertEqual(self.path.read_bytes(), before)
        with patch.object(
            tools, "_check_styled", return_value=({"paragraphs_styled": False, "page_numbers": True}, ["x"])
        ):
            ok, result, errors, _ = self.style("gongwen", request_id="s4")
        self.assertFalse(ok)
        self.assertTrue(result["rollback"]["performed"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_document_held_by_another_program_is_refused_as_held(self):
        # CI (Python 3.10) saw python-docx turn the held file into "Package not found" (an uncaught error).
        real_open = open

        def held(file, *args, **kwargs):
            if Path(file) == self.path:
                raise PermissionError(13, "The process cannot access the file", str(file))
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=held):
            ok, _result, errors, _ = self.style("gongwen", dry_run=True)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "DOCUMENT_HELD_OPEN")

    def test_a_caption_under_a_picture_keeps_its_format(self):
        # The C-06 Windows check: gongwen turned the 宋体 五号 caption into 仿宋 三号 body text.
        ok, _result, errors, _ = self.insert(at_paragraph=3, width_mm=60, caption="图 1 示意")
        self.assertTrue(ok, errors)
        document = Document(str(self.path))
        document.paragraphs[4].runs[0].font.size = before = Pt(10.5)  # 宋体 五号 as WPS sets it
        document.save(str(self.path))
        register_document("writer", str(self.path), self.workspace)
        ok, result, errors, _ = self.style("gongwen")
        self.assertTrue(ok, errors)
        self.assertEqual(result["paragraph_roles"]["caption"], 1)
        self.assertEqual(Document(str(self.path)).paragraphs[4].runs[0].font.size, before)

    def test_a_held_document_says_the_command_writes_the_file_itself(self):
        from wps_ai_agent_cli.file_hold import held_open_error

        held = held_open_error("document", "being used by another process")
        with patch.object(tools, "probe_file_not_held", return_value=held):
            ok, _result, errors, _ = self.style("gongwen")
        self.assertEqual(errors[0]["code"], "DOCUMENT_HELD_OPEN")
        self.assertIn("without WPS", errors[0]["message"])
        self.assertNotIn("Open()", errors[0]["message"])

    def test_an_existing_page_number_is_restyled_not_duplicated(self):
        ok, _result, errors, _ = self.style("report")
        self.assertTrue(ok, errors)
        ok, _result, errors, _ = self.style("gongwen", request_id="again")
        self.assertTrue(ok, errors)
        footer = Document(str(self.path)).sections[0].footer
        fields = [t for t in footer._element.iter(qn("w:instrText")) if "PAGE" in (t.text or "")]
        self.assertEqual(len(fields), 1)


class CliTests(unittest.TestCase):
    def test_the_cli_parses_font_maps_and_margins(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                build_document(Path("a.docx"))
                ok, record, _ = register_document("writer", "a.docx")
                outputs = []
                with (
                    patch("wps_ai_agent_cli.cli_writer.apply_writer_style") as style,
                    patch("wps_ai_agent_cli.cli_writer.set_writer_page_setup") as page,
                ):
                    style.return_value = (True, {"paragraph_roles": {"body": 2}}, [], False)
                    page.return_value = (True, {"sections": 1}, [], False)
                    for argv in (
                        [
                            "writer-style-apply",
                            "--document-id",
                            record["document_id"],
                            "--preset",
                            "gongwen",
                            "--font-map",
                            "方正小标宋简体=宋体",
                            "--font-map",
                            "bad",
                        ],
                        [
                            "writer-page-setup",
                            "--document-id",
                            record["document_id"],
                            "--paper",
                            "A4",
                            "--margin-top-mm",
                            "37",
                        ],
                    ):
                        stream = io.StringIO()
                        outputs.append((run(argv, output_stream=stream), json.loads(stream.getvalue())))
            finally:
                os.chdir(previous)
        self.assertEqual([code for code, _ in outputs], [0, 0], outputs)
        self.assertEqual(style.call_args.kwargs["font_map"], {"方正小标宋简体": "宋体"})
        self.assertEqual(page.call_args.kwargs["margins_mm"]["top"], 37.0)


if __name__ == "__main__":
    unittest.main()
