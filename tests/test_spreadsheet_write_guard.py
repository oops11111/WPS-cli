import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli import spreadsheet_ops
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.spreadsheet_ops import write_spreadsheet_range


class SpreadsheetWriteGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir()
        document = Path(self.tmp.name) / "book.xlsx"
        workbook = Workbook()
        workbook.save(document)
        workbook.close()
        _, record, _ = register_document("spreadsheets", str(document), self.workspace)
        self.document_id = record["document_id"]

    def write(self, values, request_id="w1", dry_run=False):
        rows, columns = len(values), len(values[0])
        address = f"A1:{chr(64 + columns)}{rows}"
        with patch.object(spreadsheet_ops, "create_backup") as backup, \
                patch.object(spreadsheet_ops, "_run_spreadsheet_write_com") as com:
            result = write_spreadsheet_range(
                self.document_id, address, values, request_id, dry_run=dry_run, workspace=self.workspace,
            )
        return result, backup, com

    def test_formula_like_strings_are_rejected_before_backup_and_com(self):
        for text in ("=1+1", "+1", "-5", "@SUM(A1)", "=cmd|' /c calc'!A0"):
            with self.subTest(text=text):
                (ok, _, errors, _), backup, com = self.write([["safe", text]])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "FORMULA_PREFIX_REJECTED")
                self.assertEqual(errors[0]["details"], {"row": 1, "column": 2})
                self.assertIn("spreadsheet-formula-write", errors[0]["message"])
                backup.assert_not_called()
                com.assert_not_called()

    def test_formula_like_strings_are_rejected_in_dry_run_too(self):
        (ok, _, errors, _), _, _ = self.write([["=A1"]], dry_run=True)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "FORMULA_PREFIX_REJECTED")

    def test_non_scalar_values_are_rejected(self):
        for value in ({"a": 1}, [1, 2]):
            with self.subTest(value=value):
                (ok, _, errors, _), backup, com = self.write([[value]])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                backup.assert_not_called()
                com.assert_not_called()

    def test_non_finite_numbers_are_rejected(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                (ok, _, errors, _), _, com = self.write([[value]])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                com.assert_not_called()

    def test_plain_scalars_pass_dry_run(self):
        (ok, result, errors, _), _, _ = self.write([["text", 1, 2.5, True, None]], dry_run=True)
        self.assertTrue(ok, errors)
        self.assertEqual(result["column_count"], 5)

    def test_text_containing_prefix_characters_later_in_string_is_allowed(self):
        (ok, _, errors, _), _, _ = self.write([["a=b", "x-y", "me@host"]], dry_run=True)
        self.assertTrue(ok, errors)

    def test_script_writes_booleans_as_booleans(self):
        scripts = []

        class Completed:
            returncode, stdout, stderr = 0, "{}", ""

        def fake_run(command, **kwargs):
            scripts.append(Path(command[-1]).read_text(encoding="utf-8-sig"))
            return Completed()

        caps = {"components": {"spreadsheets": {"selected_prog_id": "ket.Application"}}}
        with patch.object(spreadsheet_ops, "probe_wps_capabilities", return_value=caps), \
                patch.object(spreadsheet_ops.subprocess, "run", side_effect=fake_run):
            spreadsheet_ops._run_spreadsheet_write_com(str(Path(self.tmp.name) / "book.xlsx"), None, "A1", [[True]])
        self.assertIn("$value -is [bool]", scripts[0])
        self.assertLess(scripts[0].index("$value -is [bool]"), scripts[0].index("$value -is [int]"))


if __name__ == "__main__":
    unittest.main()
