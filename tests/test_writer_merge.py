"""writer-merge fills {{name}} placeholders from JSON data (C-03)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

try:
    from docx import Document
    from docx.shared import Pt
except ImportError as exc:  # optional test dependency: skip this module instead of erroring the suite
    raise unittest.SkipTest("python-docx is not installed") from exc

from wps_ai_agent_cli import writer_merge as merge
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.sessions import register_document


def build_template(path: Path) -> Path:
    document = Document()
    title = document.add_paragraph()
    # The placeholder spread over three runs, the way WPS often stores typed text.
    for piece in ("合同编号：{{", "合同", "编号}}"):
        title.add_run(piece)
    body = document.add_paragraph("甲方：")
    bold = body.add_run("{{ 客户 }}")
    bold.bold = True
    body.add_run("，金额 {{金额}} 元，备注 {{备注}}。")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "联系人"
    table.cell(0, 1).text = "{{联系人}}"
    section = document.sections[0]
    section.header.paragraphs[0].text = "页眉 {{客户}}"
    section.footer.paragraphs[0].text = "第 {{页码说明}} 页"
    document.add_paragraph("{{未提供}} 保持原样")
    document.save(path)
    return path


def texts(path: Path) -> dict[str, list[str]]:
    return {name.removeprefix("word/"): lines for name, lines in merge.actual_texts(path).items()}


DATA = {"合同编号": "HT-2026-001", "客户": "甲公司", "金额": 1200, "备注": "第一行\n第二行", "联系人": "张三"}


class WriterMergeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "ws"
        self.workspace.mkdir()
        self.path = build_template(self.root / "合同.docx")
        ok, record, errors = register_document("writer", str(self.path), self.workspace)
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]

    def call(self, data, request_id="m1", **options):
        return merge.writer_merge(self.document_id, data, request_id, workspace=self.workspace, **options)

    def test_dry_run_lists_placeholders_and_changes_nothing(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.call(DATA, dry_run=True)
        self.assertTrue(ok, errors)
        self.assertEqual(result["placeholders"]["客户"], 2)
        self.assertEqual(result["placeholder_parts"]["客户"], {"document": 1, "header1": 1})
        self.assertEqual(result["unfilled"], ["未提供", "页码说明"])
        self.assertEqual(result["unused_keys"], [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_merge_fills_runs_tables_headers_and_keeps_formatting(self):
        ok, result, errors, replayed = self.call(DATA)
        self.assertTrue(ok, errors)
        self.assertFalse(replayed)
        self.assertEqual(result["replaced"], 6)  # 页码说明 and 未提供 have no value
        self.assertTrue(result["validation_passed"])
        document = Document(str(self.path))
        self.assertEqual(document.paragraphs[0].text, "合同编号：HT-2026-001")
        body = document.paragraphs[1]
        self.assertEqual(body.text, "甲方：甲公司，金额 1200 元，备注 第一行\n第二行。")
        self.assertTrue(body.runs[1].bold)  # the value took the run where its placeholder started
        self.assertEqual(body.runs[1].text, "甲公司")
        self.assertEqual(document.tables[0].cell(0, 1).text, "张三")
        self.assertEqual(document.sections[0].header.paragraphs[0].text, "页眉 甲公司")
        self.assertEqual(document.sections[0].footer.paragraphs[0].text, "第 {{页码说明}} 页")
        self.assertEqual(document.paragraphs[-1].text, "{{未提供}} 保持原样")
        self.assertTrue(Path(result["backup"]["backup_path"]).is_file())

    def test_only_story_parts_change(self):
        with zipfile.ZipFile(self.path) as archive:
            before = {name: archive.read(name) for name in archive.namelist()}
        ok, _result, errors, _ = self.call(DATA)
        self.assertTrue(ok, errors)
        with zipfile.ZipFile(self.path) as archive:
            after = {name: archive.read(name) for name in archive.namelist()}
        self.assertEqual(set(before), set(after))
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, {"word/document.xml", "word/header1.xml"})

    def test_require_all_refuses_before_writing(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.call(DATA, require_all=True)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "PLACEHOLDER_UNFILLED")
        self.assertIn("页码说明", errors[0]["message"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_names_that_match_nothing_are_reported(self):
        ok, result, errors, _ = self.call({"客户": "乙", "不存在": "x"})
        self.assertTrue(ok, errors)
        self.assertEqual(result["unused_keys"], ["不存在"])
        ok, _result, errors, _ = self.call({"不存在": "x"}, request_id="m2")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "PLACEHOLDER_NOT_FOUND")

    def test_bad_data_is_refused(self):
        for data in ({}, [], {"a": {"nested": 1}}, {"{{a}}": "x"}, {"a": "bell\x07"}):
            with self.subTest(data=data):
                ok, _result, errors, _ = self.call(data, request_id=f"bad-{data!r}")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")

    def test_a_value_that_looks_like_a_placeholder_is_not_filled_again(self):
        ok, _result, errors, _ = self.call({"客户": "{{金额}}", "金额": "9"})
        self.assertTrue(ok, errors)
        self.assertEqual(texts(self.path)["header1.xml"][0], "页眉 {{金额}}")

    def test_the_request_is_replayed_not_repeated(self):
        ok, first, errors, _ = self.call(DATA, request_id="same")
        self.assertTrue(ok, errors)
        ok, second, errors, replayed = self.call(DATA, request_id="same")
        self.assertTrue(ok, errors)
        self.assertTrue(replayed)
        self.assertEqual(second["replaced"], first["replaced"])

    def test_a_failed_read_back_restores_the_backup(self):
        before = self.path.read_bytes()
        with patch.object(merge, "actual_texts", return_value={}):
            ok, result, errors, _ = self.call(DATA)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
        self.assertTrue(result["rollback"]["performed"], result["rollback"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_held_document_is_refused(self):
        held = {"code": "DOCUMENT_HELD_OPEN", "message": "held"}
        with patch.object(merge, "probe_file_not_held", return_value=held):
            ok, _result, errors, _ = self.call(DATA)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "DOCUMENT_HELD_OPEN")

    def test_other_components_are_refused(self):
        sheet = self.root / "b.xlsx"
        from openpyxl import Workbook

        Workbook().save(sheet)
        ok, record, _ = register_document("spreadsheets", str(sheet), self.workspace)
        ok, _result, errors, _ = merge.writer_merge(record["document_id"], DATA, "x", workspace=self.workspace)
        self.assertEqual(errors[0]["code"], "UNSUPPORTED_COMPONENT")


class FillParagraphTests(unittest.TestCase):
    def paragraph(self, *pieces):
        document = Document()
        paragraph = document.add_paragraph()
        for piece in pieces:
            run = paragraph.add_run(piece)
            run.font.size = Pt(12)
        return paragraph

    def test_adjacent_and_repeated_placeholders(self):
        paragraph = self.paragraph("{{a}}{{b}}", "-{{a}")
        paragraph.add_run("}")
        count = merge.fill_paragraph(paragraph._p, {"a": "1", "b": "22"})
        self.assertEqual(count, 3)
        self.assertEqual(paragraph.text, "122-1")

    def test_spaces_are_kept_and_tabs_become_tab_marks(self):
        paragraph = self.paragraph("x{{v}}y")
        merge.fill_paragraph(paragraph._p, {"v": "  a\tb  "})
        self.assertEqual(paragraph.text, "x  a\tb  y")
        self.assertIn("w:tab", paragraph._p.xml)
        self.assertIn('xml:space="preserve"', paragraph._p.xml)


class CliTests(unittest.TestCase):
    def test_data_from_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = build_template(root / "t.docx")
            (root / "data.json").write_text(json.dumps(DATA, ensure_ascii=False), encoding="utf-8-sig")
            previous = os.getcwd()
            os.chdir(root)
            try:
                ok, record, _ = register_document("writer", str(path))
                stream = io.StringIO()
                code = run(
                    ["writer-merge", "--document-id", record["document_id"], "--data-file", "data.json"],
                    output_stream=stream,
                )
            finally:
                os.chdir(previous)
        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0, payload)
        self.assertIn("No value for: 未提供, 页码说明", payload["summary"])

    def test_bad_json_is_an_argument_error(self):
        stream = io.StringIO()
        code = run(["writer-merge", "--document-id", "doc_x", "--data-json", "{not json"], output_stream=stream)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stream.getvalue())["errors"][0]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
