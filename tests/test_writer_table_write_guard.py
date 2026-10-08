import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.writer_ops import writer_table_write
from tests.test_writer_ops import write_minimal_docx_with_table


class WriterTableWriteGuardTests(unittest.TestCase):
    def _register(self, tmp):
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        document = Path(tmp) / "table.docx"
        write_minimal_docx_with_table(document)
        ok, record, _errors = register_document("writer", str(document), workspace)
        self.assertTrue(ok)
        return workspace, record["document_id"]

    def test_rejects_unsafe_text_before_any_backup_or_com_call(self):
        bad_values = ["line1\nline2", "a\rb", "tab\tchar", "nul\x00", "x" * 4097]
        with tempfile.TemporaryDirectory() as tmp:
            workspace, document_id = self._register(tmp)
            with patch("wps_ai_agent_cli.writer_ops._run_writer_table_write_com") as com:
                for index, value in enumerate(bad_values):
                    ok, _result, errors, _replayed = writer_table_write(
                        document_id=document_id,
                        table_index=1,
                        row=2,
                        column=3,
                        text=value,
                        request_id=f"table-bad-{index}",
                        dry_run=False,
                        workspace=workspace,
                    )
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                com.assert_not_called()
            self.assertFalse((workspace / ".wps-agent" / "backups").exists())

    def test_accepts_boundary_length_text_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, document_id = self._register(tmp)
            ok, result, errors, _replayed = writer_table_write(
                document_id=document_id,
                table_index=1,
                row=2,
                column=3,
                text="x" * 4096,
                request_id="table-max",
                dry_run=True,
                workspace=workspace,
            )
            self.assertTrue(ok, errors)
            self.assertTrue(result["would_modify"])


if __name__ == "__main__":
    unittest.main()
