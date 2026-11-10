"""batch (C-07), get by path (C-08), document-view and document-check (C-09)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

try:
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
except ImportError as exc:  # optional test dependencies: skip this module instead of erroring the suite
    raise unittest.SkipTest("python-docx, openpyxl or python-pptx is not installed") from exc

from wps_ai_agent_cli import agent_tools
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document


def build_writer(path: Path) -> Path:
    document = Document()
    document.add_paragraph("关于开展安全检查的通知")
    document.add_paragraph("一、总体要求", style="Heading 1")
    document.add_paragraph("正文 {{单位}} 负责。")
    document.add_paragraph("1. 具体任务", style="Heading 3")  # skips level 2
    for _ in range(3):
        document.add_paragraph("")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "名称"
    table.cell(1, 1).text = "数量"
    document.add_table(rows=1, cols=1)  # empty table
    document.save(path)
    return path


def build_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "销售"
    sheet.append(["地区", "销量"])
    sheet.append(["华东", 120])
    sheet["C2"] = "=B2/0"
    sheet["D2"] = "=[其他.xlsx]Sheet1!A1"
    workbook.create_sheet("空表")
    workbook.save(path)
    return path


def build_deck(path: Path) -> Path:
    deck = Presentation()
    for text in ("第一页", "", "第一页", "你好 {{姓名}}"):
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        if text:
            slide.shapes.title.text = text
        else:
            slide.shapes._spTree.remove(slide.shapes.title._element)
    deck.save(path)
    return path


class AgentToolsTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        previous = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        self.ids = {}
        for component, name, builder in (
            ("writer", "通知.docx", build_writer),
            ("spreadsheets", "数据.xlsx", build_workbook),
            ("presentation", "汇报.pptx", build_deck),
        ):
            ok, record, errors = register_document(component, str(builder(self.root / name)), self.root)
            self.assertTrue(ok, errors)
            self.ids[component] = record["document_id"]


class GetTests(AgentToolsTestCase):
    def get(self, component, path):
        return agent_tools.get_by_path(self.ids[component], path, self.root)

    def test_parse_path(self):
        self.assertEqual(agent_tools.parse_path('/sheet["销售"]/cell["C12"]'), [("sheet", "销售"), ("cell", "C12")])
        self.assertEqual(agent_tools.parse_path("/table[1]/cell[2, 3]"), [("table", 1), ("cell", (2, 3))])
        self.assertEqual(agent_tools.parse_path('/sheet["a\\"b"]'), [("sheet", 'a"b')])
        for bad in ("", "paragraph[1]", "/paragraph[x]", "/paragraph[1]junk", '/sheet["open'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                agent_tools.parse_path(bad)

    def test_writer_paths(self):
        ok, data, errors = self.get("writer", "/paragraph[2]")
        self.assertTrue(ok, errors)
        self.assertEqual((data["text"], data["heading_level"]), ("一、总体要求", 1))
        ok, data, errors = self.get("writer", "/table[1]/cell[2,2]")
        self.assertTrue(ok, errors)
        self.assertEqual(data["text"], "数量")
        ok, data, _ = self.get("writer", "/headings")
        self.assertEqual([h["text"] for h in data["headings"]], ["一、总体要求", "1. 具体任务"])
        ok, data, _ = self.get("writer", "/tables")
        self.assertEqual(data["count"], 2)

    def test_spreadsheet_paths(self):
        ok, data, errors = self.get("spreadsheets", '/sheet["销售"]/cell["B2"]')
        self.assertTrue(ok, errors)
        self.assertEqual((data["values"], data["path"]), ([[120]], '/sheet["销售"]/cell["B2"]'))
        ok, data, errors = self.get("spreadsheets", '/sheet["销售"]')
        self.assertTrue(ok, errors)
        self.assertEqual(data["max_column"], 4)
        ok, _data, errors = self.get("spreadsheets", '/sheet["没有"]')
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "PATH_TARGET_NOT_FOUND")

    def test_presentation_paths(self):
        ok, data, errors = self.get("presentation", "/slides")
        self.assertTrue(ok, errors)
        self.assertEqual(data["count"], 4)
        ok, data, errors = self.get("presentation", "/slide[1]")
        self.assertTrue(ok, errors)
        self.assertEqual(data["index"], 1)

    def test_errors_name_the_problem(self):
        cases = {
            ("writer", "/paragraph[99]"): "PATH_TARGET_NOT_FOUND",
            ("writer", "/table[1]/cell[9,9]"): "PATH_TARGET_NOT_FOUND",
            ("writer", "/slide[1]"): "PATH_SYNTAX_INVALID",
            ("spreadsheets", "/paragraph[1]"): "PATH_SYNTAX_INVALID",
            ("presentation", "/slide[9]"): "PATH_TARGET_NOT_FOUND",
            ("writer", "nope"): "PATH_SYNTAX_INVALID",
        }
        for (component, path), code in cases.items():
            with self.subTest(path=path):
                ok, _data, errors = self.get(component, path)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
        ok, _data, errors = agent_tools.get_by_path("doc_missing", "/paragraphs", self.root)
        self.assertEqual(errors[0]["code"], "DOCUMENT_NOT_FOUND")

    def test_damaged_or_held_files_are_reported(self):
        from unittest.mock import patch

        (self.root / "通知.docx").write_bytes(b"not a zip")
        for call in (
            lambda: self.get("writer", "/paragraphs"),
            lambda: agent_tools.document_view(self.ids["writer"], self.root),
            lambda: agent_tools.document_check(self.ids["writer"], self.root),
        ):
            ok, _data, errors = call()
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "INVALID_INPUT")
        with patch.object(agent_tools, "_view_spreadsheet", side_effect=PermissionError(13, "in use")):
            ok, _data, errors = agent_tools.document_view(self.ids["spreadsheets"], self.root)
        self.assertEqual(errors[0]["code"], "DOCUMENT_HELD_OPEN")


class ViewAndCheckTests(AgentToolsTestCase):
    def test_view(self):
        ok, data, errors = agent_tools.document_view(self.ids["writer"], self.root)
        self.assertTrue(ok, errors)
        self.assertEqual(data["title"], "关于开展安全检查的通知")
        self.assertEqual([h["level"] for h in data["outline"]], [1, 3])
        self.assertEqual(len(data["tables"]), 2)
        ok, data, errors = agent_tools.document_view(self.ids["spreadsheets"], self.root)
        self.assertTrue(ok, errors)
        self.assertEqual([s["name"] for s in data["sheets"]], ["销售", "空表"])
        self.assertEqual(data["sheets"][0]["formulas"], 2)
        ok, data, errors = agent_tools.document_view(self.ids["presentation"], self.root)
        self.assertTrue(ok, errors)
        self.assertEqual(data["slide_count"], 4)

    def codes(self, component):
        ok, data, errors = agent_tools.document_check(self.ids[component], self.root)
        self.assertTrue(ok, errors)
        return {issue["code"] for issue in data["issues"]}, data

    def test_check_writer(self):
        codes, data = self.codes("writer")
        self.assertEqual(codes, {"PLACEHOLDER_UNFILLED", "HEADING_LEVEL_SKIPPED", "EMPTY_PARAGRAPHS", "TABLE_EMPTY"})
        self.assertEqual(data["counts"]["error"], 0)

    def test_check_spreadsheet(self):
        codes, data = self.codes("spreadsheets")
        self.assertIn("EXTERNAL_LINK", codes)
        self.assertIn("SHEET_EMPTY", codes)
        self.assertIn("FORMULA_NOT_CALCULATED", codes)  # openpyxl saves no cached values

    def test_check_spreadsheet_reads_cached_errors(self):
        path = self.root / "数据.xlsx"
        import zipfile

        with zipfile.ZipFile(path) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        sheet = parts["xl/worksheets/sheet1.xml"].decode()
        sheet = (
            sheet.replace("<f>B2/0</f><v></v>", "<f>B2/0</f><v>#DIV/0!</v>")
            .replace("<f>B2/0</f>", "<f>B2/0</f><v>#DIV/0!</v>")
            .replace('r="C2"', 'r="C2" t="e"', 1)
        )
        parts["xl/worksheets/sheet1.xml"] = sheet.encode()
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        _codes, data = self.codes("spreadsheets")
        errors = [issue for issue in data["issues"] if issue["code"] == "FORMULA_ERROR"]
        self.assertEqual(errors[0]["where"], "销售!C2")
        self.assertEqual(data["counts"]["error"], 1)

    def test_check_presentation(self):
        codes, _data = self.codes("presentation")
        self.assertEqual(codes, {"SLIDE_WITHOUT_TEXT", "SLIDE_DUPLICATE_TEXT", "PLACEHOLDER_UNFILLED"})


class BatchTests(AgentToolsTestCase):
    def test_parse_refuses_bad_lists(self):
        cases = [
            [],
            {"tool": "get"},
            [{"tool": "batch", "arguments": {}}],
            [{"tool": "wps_agent_mcp_call"}],
            [{"tool": "no-such-tool"}],
            [{"tool": "get", "arguments": []}],
            [{"tool": "get"}] * 51,
        ]
        for commands in cases:
            with self.subTest(commands=str(commands)[:40]):
                items, problem = agent_tools.parse_batch(commands)
                self.assertIsNone(items)
                self.assertTrue(problem)

    def test_runs_in_order_and_stops_at_failure(self):
        writer = self.ids["writer"]
        commands = [
            {"tool": "document-view", "arguments": {"document_id": writer}},
            {"tool": "wps_agent_writer_merge", "arguments": {"document_id": writer, "data_json": '{"单位": "办公室"}'}},
            {"tool": "get", "arguments": {"document_id": writer, "path": "/paragraph[3]"}},
            {"tool": "get", "arguments": {"document_id": writer, "path": "/paragraph[99]"}},
            {"tool": "document-check", "arguments": {"document_id": writer}},
        ]
        ok, data, errors = agent_tools.run_batch(commands, "b1")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "BATCH_COMMAND_FAILED")
        self.assertEqual((data["ran"], data["failed"], data["stopped_at"], data["skipped"]), (4, [4], 4, 1))
        results = data["results"]
        self.assertEqual([r["request_id"] for r in results], ["b1:1", "b1:2", "b1:3", "b1:4"])
        self.assertEqual(results[2]["data"]["text"], "正文 办公室 负责。")  # the merge ran before the get
        self.assertEqual(results[3]["errors"][0]["code"], "PATH_TARGET_NOT_FOUND")

        ok, data, _ = agent_tools.run_batch(commands, "b2", continue_on_error=True)
        self.assertFalse(ok)
        self.assertEqual((data["ran"], data["skipped"], data["stopped_at"]), (5, 0, None))

    def test_destructive_tools_still_need_confirm(self):
        commands = [{"tool": "restore-backup", "arguments": {"document_id": self.ids["writer"], "backup_name": "x"}}]
        ok, data, _errors = agent_tools.run_batch(commands, "b3")
        self.assertFalse(ok)
        self.assertEqual(data["results"][0]["errors"][0]["code"], "MCP_DESTRUCTIVE_CONFIRMATION_REQUIRED")

    def test_cli_and_mcp(self):
        commands = json.dumps([{"tool": "document-view", "arguments": {"document_id": self.ids["presentation"]}}])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = run(["batch", "--commands-json", commands, "--request-id", "cli1"])
        response = json.loads(buffer.getvalue())
        self.assertEqual(code, 0, response)
        self.assertEqual(response["data"]["results"][0]["data"]["slide_count"], 4)

        commands_file = self.root / "calls.json"
        commands_file.write_text(commands, encoding="utf-8")
        ok, data, errors = call_mcp_tool("wps_agent_batch", {"commands_file": str(commands_file), "request_id": "m1"})
        self.assertTrue(ok, errors)
        self.assertTrue(data["response"]["data"]["results"][0]["ok"])

        for tool, arguments in (
            ("wps_agent_get", {"document_id": self.ids["writer"], "path": "/headings"}),
            ("wps_agent_document_view", {"document_id": self.ids["spreadsheets"]}),
            ("wps_agent_document_check", {"document_id": self.ids["presentation"]}),
        ):
            with self.subTest(tool=tool):
                ok, data, errors = call_mcp_tool(tool, arguments)
                self.assertTrue(ok, errors)

    def test_bad_json(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = run(["batch", "--commands-json", "[nope"])
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["errors"][0]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
