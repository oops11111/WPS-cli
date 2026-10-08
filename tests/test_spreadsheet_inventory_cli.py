import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from openpyxl import Workbook

from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.sessions import register_document


class SpreadsheetInventoryCliTests(unittest.TestCase):
    def test_xlsx_and_xlsm_inventory_cli_is_repeatable_and_byte_preserving(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                for suffix in ("xlsx", "xlsm"):
                    document = Path(tmp) / f"inventory.{suffix}"
                    workbook = Workbook()
                    sheet = workbook.active
                    sheet.title = "Report"
                    sheet["A1"] = "value"
                    sheet["B1"] = "=1+1"
                    workbook.save(document)
                    workbook.close()
                    ok, record, errors = register_document("spreadsheets", str(document), workspace)
                    self.assertTrue(ok, errors)
                    before = hashlib.sha256(document.read_bytes()).hexdigest()
                    payloads = []
                    for _ in range(2):
                        output = io.StringIO()
                        with redirect_stdout(output):
                            exit_code = run(["spreadsheet-sheets", "--document-id", record["document_id"]])
                        self.assertEqual(exit_code, 0)
                        response = json.loads(output.getvalue())
                        self.assertTrue(response["ok"], response["errors"])
                        payloads.append(response["data"])
                    self.assertEqual(payloads[0], payloads[1])
                    self.assertEqual(payloads[0]["sheets"][0]["formula_count"], 1)
                    self.assertEqual(payloads[0]["sheets"][0]["populated_cell_count"], 2)
                    self.assertEqual(hashlib.sha256(document.read_bytes()).hexdigest(), before)
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
