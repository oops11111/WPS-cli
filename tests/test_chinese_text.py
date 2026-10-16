"""Chinese text on every path in and out of the CLI (P8-003, Phase 8 exit criterion I1).

Phase 7 found two of these paths broken on Chinese Windows only on real WPS: PowerShell output and the MCP server's
stdin. These tests cover each path with Chinese text:

- the CLI process itself, under a GBK locale (PYTHONIOENCODING=gbk stands in for cp936): arguments, stdout and
  stderr;
- every PowerShell component, through its real scripts against a fake WPS: a Chinese document path, Chinese
  selection text read and written, Chinese cell contents written and undone.

The MCP server's stdin under GBK is covered in tests/test_mcp_server.py (RealStdioEncodingTests).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_open_documents_powershell import FAKE_WPS_PRELUDE
from tests.test_undo_in_wps_powershell import FAKE_BOOK_PRELUDE, FAKE_DECK_PRELUDE
from tests.test_writer_ops import write_minimal_docx
from wps_ai_agent_cli import open_documents
from wps_ai_agent_cli.sessions import register_document

SRC = Path(__file__).resolve().parents[1] / "src"
PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")


def run_cli(args, cwd, stdin=b""):
    env = {**os.environ, "PYTHONIOENCODING": "gbk", "PYTHONPATH": str(SRC)}
    env.pop("PYTHONUTF8", None)
    return subprocess.run(
        [sys.executable, "-m", "wps_ai_agent_cli", *args],
        input=stdin,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=120,
        check=False,
    )


class CliProcessUnderGbkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_a_chinese_path_is_registered_and_listed_intact(self):
        document = self.root / "季度报告.docx"
        write_minimal_docx(document, "状态：草稿")
        registered = run_cli(
            ["register-document", "--component", "writer", "--path", str(document), "--request-id", "注册-1"],
            self.root,
        )
        self.assertEqual(registered.returncode, 0, registered.stderr.decode("utf-8", "replace"))
        envelope = json.loads(registered.stdout.decode("utf-8"))
        self.assertTrue(envelope["ok"], envelope)
        self.assertEqual(Path(envelope["data"]["document"]["path"]).name, "季度报告.docx")
        self.assertEqual(envelope["request_id"], "注册-1")
        listed = json.loads(run_cli(["documents"], self.root).stdout.decode("utf-8"))
        self.assertIn("季度报告.docx", [Path(item["path"]).name for item in listed["data"]["documents"]])

    def test_validation_with_chinese_text_finds_it(self):
        document = self.root / "报告.docx"
        write_minimal_docx(document, "负责人：财务部")
        registered = json.loads(
            run_cli(["register-document", "--component", "writer", "--path", str(document)], self.root).stdout.decode(
                "utf-8"
            )
        )
        checked = run_cli(
            [
                "validate-document",
                "--document-id",
                registered["data"]["document"]["document_id"],
                "--contains",
                "财务部",
            ],
            self.root,
        )
        envelope = json.loads(checked.stdout.decode("utf-8"))
        self.assertTrue(envelope["ok"], envelope)
        self.assertEqual(envelope["data"]["contains"], "财务部")

    def test_a_chinese_sheet_name_and_cell_text_are_read_intact(self):
        from openpyxl import Workbook

        book = self.root / "状态表.xlsx"
        workbook = Workbook()
        workbook.active.title = "汇总"
        workbook.active["A1"] = "已完成"
        workbook.save(book)
        registered = json.loads(
            run_cli(["register-document", "--component", "spreadsheets", "--path", str(book)], self.root).stdout.decode(
                "utf-8"
            )
        )
        document_id = registered["data"]["document"]["document_id"]
        sheets = json.loads(run_cli(["spreadsheet-sheets", "--document-id", document_id], self.root).stdout)
        self.assertTrue(sheets["ok"], sheets)
        self.assertIn("汇总", json.dumps(sheets["data"], ensure_ascii=False))
        read = run_cli(
            ["spreadsheet-read", "--document-id", document_id, "--sheet", "汇总", "--range", "A1"], self.root
        )
        envelope = json.loads(read.stdout.decode("utf-8"))
        self.assertTrue(envelope["ok"], envelope)
        self.assertIn("已完成", json.dumps(envelope["data"], ensure_ascii=False))

    def test_an_error_about_a_chinese_argument_reaches_stderr_intact(self):
        refused = run_cli(["register-document", "--component", "表格", "--path", "x.docx"], self.root)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("表格", refused.stderr.decode("utf-8"))


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the component scripts against a fake WPS")
class ComponentScriptsRoundTripChineseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        patcher = patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake(self, prelude, document, **env):
        def render(script, values):
            return prelude + open_documents.json.dumps(values).join(script.split("__PARAMS_JSON__"))

        for patcher in (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(document.resolve()), **env}),
            patch.object(open_documents, "_render", side_effect=render),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_writer_reads_and_replaces_a_chinese_selection_in_a_chinese_named_document(self):
        document = self.root / "季度报告.docx"
        write_minimal_docx(document, "你好勇敢的世界")
        ok, record, errors = register_document("writer", str(document), self.workspace)
        self.assertTrue(ok, errors)
        self.fake(FAKE_WPS_PRELUDE, document, WPSFAKE_TEXT="你好勇敢的世界", WPSFAKE_START="2", WPSFAKE_END="4")
        ok, selection, errors = open_documents.read_writer_selection(record["document_id"], self.workspace)
        self.assertTrue(ok, errors)
        self.assertEqual(selection["selection_text"], "勇敢")
        ok, result, errors, _replayed = open_documents.replace_writer_selection(
            record["document_id"], "坚定", "替换-1", expected_selection_text="勇敢", workspace=self.workspace
        )
        self.assertTrue(ok, errors)
        self.assertEqual(result["read_back_text"], "坚定")

    def test_presentation_replaces_a_chinese_selection(self):
        from tests.test_presentation_ops import write_minimal_pptx

        deck = self.root / "汇报.pptx"
        write_minimal_pptx(deck, ["状态：草稿"])
        ok, record, errors = register_document("presentation", str(deck), self.workspace)
        self.assertTrue(ok, errors)
        self.fake(
            FAKE_DECK_PRELUDE,
            deck,
            WPSFAKE_FRAME="状态：草稿",
            WPSFAKE_START="4",
            WPSFAKE_LENGTH="2",
            WPSFAKE_SAVES="1",
        )
        ok, result, errors, _replayed = open_documents.replace_presentation_selection(
            record["document_id"], "定稿", "替换-2", expected_selection_text="草稿", workspace=self.workspace
        )
        self.assertTrue(ok, errors)
        self.assertEqual(result["read_back_text"], "定稿")

    def test_spreadsheet_cells_with_chinese_text_are_written_recorded_and_undone(self):
        book = self.root / "状态表.xlsx"
        book.write_bytes(b"xlsx")
        self.fake(FAKE_BOOK_PRELUDE, book, WPSFAKE_CELLS="'甲方|'乙方", WPSFAKE_SAVES="1")
        written = open_documents._run_spreadsheet_attached_com(
            "selection-replace",
            {
                "path": str(book.resolve()),
                "expected_address": "$A$1:$A$2",
                "expected_text": "甲方\t乙方",
                "max_cells": 100,
                "mode": "constant",
                "text": "已完成",
            },
        )
        self.assertTrue(written["ok"], written)
        data = written["data"]
        self.assertEqual(data["read_back_values"], ["已完成", "已完成"])
        revert = open_documents._spreadsheet_revert(data)
        self.assertEqual([cell["formula"] for cell in revert["before_cells"]], ["甲方", "乙方"])
        with patch.dict(os.environ, {"WPSFAKE_CELLS": "'已完成|'已完成"}):
            undone = open_documents._run_spreadsheet_attached_com("selection-revert", {"path": str(book), **revert})
        self.assertEqual(undone["data"]["status"], "reverted", undone)
        self.assertEqual(undone["data"]["read_back_formulas"], ["甲方", "乙方"])


if __name__ == "__main__":
    unittest.main()
