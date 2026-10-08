import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from wps_ai_agent_cli.backups import create_backup
from wps_ai_agent_cli.sessions import get_document
from wps_ai_agent_cli.writer_table_smoke import run_writer_table_smoke


def write_docx_table(path: Path, target_text: str = "PENDING_STATUS") -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>A1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>C1</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>A2</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B2</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>{target_text}</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""")
        archive.writestr("word/document.xml", xml)


class WriterTableSmokeTests(unittest.TestCase):
    def test_writer_table_smoke_copies_fixture_writes_and_checks_restore_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            source = Path(tmp) / "source.docx"
            output = Path(tmp) / "out" / "smoke.docx"
            write_docx_table(source)

            def fake_write(document_id, table_index, row, column, text, request_id, dry_run, workspace):
                ok, backup, errors, _replayed = create_backup(document_id, f"{request_id}:backup", workspace=workspace)
                self.assertTrue(ok)
                self.assertEqual(errors, [])
                document = get_document(document_id, workspace)
                write_docx_table(Path(document["path"]), target_text=text)
                return True, {
                    "document_id": document_id,
                    "table_index": table_index,
                    "row": row,
                    "column": column,
                    "replacement_text": text,
                    "read_back_text": text,
                    "validation_passed": True,
                    "backup": backup,
                }, [], False

            with patch("wps_ai_agent_cli.writer_table_smoke.writer_table_write", side_effect=fake_write):
                result = run_writer_table_smoke(
                    input_path=str(source),
                    output_path=str(output),
                    table_index=1,
                    row=2,
                    column=3,
                    text="REGRESSION_STATUS",
                    request_id="smoke-test",
                    workspace=workspace,
                )

            self.assertTrue(result["ok"])
            self.assertTrue(output.exists())
            self.assertTrue(result["data"]["backup_exists"])
            self.assertTrue(result["data"]["restore_check"]["ok"])
            self.assertEqual(result["data"]["writer_table"]["read_back_text"], "REGRESSION_STATUS")


if __name__ == "__main__":
    unittest.main()
