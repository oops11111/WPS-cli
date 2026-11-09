"""Batch-2: exit codes (U-02), MCP boundary and destructive confirmation (S-02), formula denylist
(S-07) and the PowerShell parameter channel (S-06)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli import capabilities
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.formula_safety import forbidden_formula_function
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.workspace_boundary import boundary_error

ROOT = Path(__file__).resolve().parents[1]


class ExitCodeTests(unittest.TestCase):
    def test_failure_exits_one_by_default_and_zero_when_lenient(self):
        stream = io.StringIO()
        code = run(["mcp-tool-schema", "--name", "does-not-exist"], output_stream=stream)
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(stream.getvalue())["ok"])

        stream = io.StringIO()
        code = run(["--lenient-exit", "mcp-tool-schema", "--name", "does-not-exist"], output_stream=stream)
        self.assertEqual(code, 0)

    def test_success_exits_zero(self):
        stream = io.StringIO()
        code = run(["documents"], output_stream=stream)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stream.getvalue())["ok"])


class FormulaSafetyTests(unittest.TestCase):
    def test_forbidden_functions_are_found(self):
        for formula in ('=DDE("x")', '=WEBSERVICE("http://x")', '=HYPERLINK("http://x")', '=1+INDIRECT("A1")'):
            self.assertIsNotNone(forbidden_formula_function(formula), formula)

    def test_the_file_format_prefix_does_not_hide_a_forbidden_function(self):
        for formula, name in (
            ('=_xlfn.WEBSERVICE("http://x")', "WEBSERVICE"),
            ('=SUM(A1)+_XLFN.webservice("u")', "WEBSERVICE"),
            ('=_xlws.CALL("x")', "CALL"),
        ):
            self.assertEqual(forbidden_formula_function(formula), name, formula)
        self.assertIsNone(forbidden_formula_function("=_xlfn.XLOOKUP(A1,B:B,C:C)"))

    def test_ordinary_formulas_are_clean(self):
        for formula in ("=SUM(A1:A9)", '=IF(B2>0,"yes","no")', "=VLOOKUP(A1,Sheet2!A:B,2,FALSE)"):
            self.assertIsNone(forbidden_formula_function(formula), formula)

    def test_formula_write_rejects_a_dde_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "book.xlsx"
            Workbook().save(document)
            ok, record, _ = register_document("spreadsheets", str(document), tmp)
            self.assertTrue(ok)
            from wps_ai_agent_cli.spreadsheet_ops import write_spreadsheet_formulas

            ok, _result, errors, _ = write_spreadsheet_formulas(
                record["document_id"],
                "A1",
                [['=DDE("server|topic")']],
                [[0]],
                request_id="batch2-formula",
                workspace=tmp,
            )
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "FORMULA_FUNCTION_NOT_ALLOWED")


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_no_boundary_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WPS_AGENT_WORKSPACE_ROOT", None)
            self.assertIsNone(boundary_error("/anywhere/file.docx"))

    def test_register_document_refuses_a_path_outside_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside.docx"
            outside.write_bytes(b"x")
            with patch.dict(os.environ, {"WPS_AGENT_WORKSPACE_ROOT": str(root)}):
                ok, _record, errors = register_document("writer", str(outside), tmp)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "PATH_OUTSIDE_WORKSPACE")

    def test_register_document_accepts_a_path_inside_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            inside = root / "inside.docx"
            inside.write_bytes(b"x")
            with patch.dict(os.environ, {"WPS_AGENT_WORKSPACE_ROOT": str(root)}):
                ok, _record, errors = register_document("writer", str(inside), tmp)
            self.assertTrue(ok, errors)


class DestructiveConfirmationTests(unittest.TestCase):
    def test_delete_sheet_without_confirm_is_refused_before_anything_runs(self):
        ok, _result, errors = call_mcp_tool(
            "wps_agent_spreadsheet_delete_sheet",
            {"document_id": "doc_missing0000000", "sheet_name": "Sheet1", "request_id": "batch2-gate"},
        )
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_DESTRUCTIVE_CONFIRMATION_REQUIRED")

    def test_delete_sheet_with_dry_run_needs_no_confirm(self):
        ok, _result, errors = call_mcp_tool(
            "wps_agent_spreadsheet_delete_sheet",
            {
                "document_id": "doc_missing0000000",
                "sheet_name": "Sheet1",
                "request_id": "batch2-gate-dry",
                "dry_run": True,
            },
        )
        self.assertFalse(ok)  # the document does not exist, but the gate is not what refused it
        self.assertNotEqual(errors[0]["code"], "MCP_DESTRUCTIVE_CONFIRMATION_REQUIRED")

    def test_the_six_destructive_tools_advertise_confirm(self):
        from wps_ai_agent_cli.mcp_schema import get_mcp_tool_schema

        for name in (
            "wps_agent_restore_backup",
            "wps_agent_save_as_open_document",
            "wps_agent_writer_selection_delete",
            "wps_agent_spreadsheet_selection_delete",
            "wps_agent_spreadsheet_delete_sheet",
            "wps_agent_presentation_selection_delete",
        ):
            schema = get_mcp_tool_schema(name)
            self.assertTrue(schema["destructive"], name)
            self.assertIn("confirm", schema["input_schema"]["properties"], name)


class PowershellParameterChannelTests(unittest.TestCase):
    def test_progid_travels_as_json_not_interpolation(self):
        captured = {}

        class Completed:
            returncode = 0
            stdout = "true"

        def fake_run(command, timeout_seconds=10):
            captured["command"] = command
            return Completed()

        with patch("wps_ai_agent_cli.powershell_runner.run_powershell_command", fake_run):
            self.assertTrue(capabilities._resolve_with_powershell("ket.Application'; evil; '"))
        self.assertIn("ConvertFrom-Json", captured["command"])
        self.assertIn("ket.Application'; evil; '", captured["command"].split("@'")[1])  # inside the JSON payload only


if __name__ == "__main__":
    unittest.main()
