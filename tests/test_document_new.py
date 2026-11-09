"""document-new creates a blank document offline and registers it (C-01)."""

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
    from pptx import Presentation
except ImportError as exc:  # optional test dependency: skip this module instead of erroring the suite
    raise unittest.SkipTest("python-docx and python-pptx are needed") from exc

from openpyxl import load_workbook

from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.document_new import create_document
from wps_ai_agent_cli.sessions import get_document


class CreateDocumentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def create(self, component, name, **options):
        return create_document(component, self.root / name, workspace=self.workspace, **options)

    def test_a_writer_document_with_a_title_is_created_and_registered(self):
        ok, data, errors = self.create("writer", "周报.docx", title="第 45 周周报")
        self.assertTrue(ok, errors)
        document = Document(str(self.root / "周报.docx"))
        self.assertEqual(document.paragraphs[0].text, "第 45 周周报")
        self.assertEqual(document.paragraphs[0].style.name, "Title")
        record = get_document(data["document_id"], self.workspace)
        self.assertEqual((record["component"], record["path"]), ("writer", data["path"]))

    def test_a_spreadsheet_takes_the_title_as_its_sheet_name(self):
        ok, data, errors = self.create("spreadsheets", "book.xlsx", title="销售")
        self.assertTrue(ok, errors)
        self.assertEqual(load_workbook(self.root / "book.xlsx").sheetnames, ["销售"])
        self.assertEqual(data["contents"], {"sheet_names": ["销售"]})

    def test_a_presentation_is_16_by_9_with_a_title_slide(self):
        ok, data, errors = self.create("presentation", "deck.pptx", title="季度汇报")
        self.assertTrue(ok, errors)
        deck = Presentation(str(self.root / "deck.pptx"))
        self.assertEqual((deck.slide_width, deck.slide_height), (12192000, 6858000))
        self.assertEqual([slide.shapes.title.text for slide in deck.slides], ["季度汇报"])

    def test_without_a_title_the_documents_are_empty(self):
        for component, name in (("writer", "a.docx"), ("spreadsheets", "b.xlsx"), ("presentation", "c.pptx")):
            with self.subTest(component=component):
                ok, data, errors = self.create(component, name)
                self.assertTrue(ok, errors)
        self.assertEqual(len(Presentation(str(self.root / "c.pptx")).slides), 0)
        self.assertEqual([p.text for p in Document(str(self.root / "a.docx")).paragraphs], [])

    def test_an_existing_file_is_never_overwritten(self):
        target = self.root / "keep.docx"
        target.write_bytes(b"precious")
        ok, _data, errors = self.create("writer", "keep.docx")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
        self.assertEqual(target.read_bytes(), b"precious")

    def test_a_file_that_appears_after_the_check_is_not_replaced(self):
        target = self.root / "race.xlsx"
        real_open = open

        def appear_then_open(file, mode="r", *args, **kwargs):
            if Path(file) == target and "x" in mode:
                target.write_bytes(b"theirs")
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=appear_then_open):
            ok, _data, errors = self.create("spreadsheets", "race.xlsx")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
        self.assertEqual(target.read_bytes(), b"theirs")

    def test_bad_requests_are_refused_before_writing(self):
        cases = [
            (("writer", "wrong.xlsx"), {}, "INVALID_OUTPUT"),
            (("chart", "x.docx"), {}, "UNSUPPORTED_COMPONENT"),
            (("writer", "missing/x.docx"), {}, "OUTPUT_DIRECTORY_NOT_FOUND"),
            (("spreadsheets", "bad.xlsx"), {"title": "a/b"}, "INVALID_SHEET_NAME"),
        ]
        for (component, name), options, code in cases:
            with self.subTest(code=code):
                ok, _data, errors = self.create(component, name, **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                self.assertFalse((self.root / name).exists())

    def test_no_register_only_creates_the_file(self):
        ok, data, errors = self.create("writer", "loose.docx", register=False)
        self.assertTrue(ok, errors)
        self.assertFalse(data["registered"])
        self.assertNotIn("document_id", data)
        self.assertFalse((self.workspace / ".wps-agent").exists())

    def test_the_workspace_boundary_applies(self):
        inside = self.root / "inside"
        inside.mkdir()
        with patch.dict(os.environ, {"WPS_AGENT_WORKSPACE_ROOT": str(inside)}):
            ok, _data, errors = self.create("writer", "outside.docx")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "PATH_OUTSIDE_WORKSPACE")


class CliTests(unittest.TestCase):
    def test_the_cli_creates_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                stream = io.StringIO()
                code = run(
                    ["document-new", "--component", "presentation", "--path", "deck.pptx", "--title", "T"],
                    output_stream=stream,
                )
            finally:
                os.chdir(previous)
            payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["data"]["document_id"].startswith("doc_"))
        self.assertEqual(payload["validation"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
