import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from wps_ai_agent_cli.document_text import count_text_in_docx, docx_body_tables, docx_table_cell_text
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.writer_ops import writer_fill_bookmark, writer_replace, writer_table_write


def write_minimal_docx(path: Path, text: str) -> None:
    write_minimal_docx_paragraphs(path, [text])


def write_minimal_docx_paragraphs(path: Path, paragraphs: list[str]) -> None:
    body = "\n".join(
        f"    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
{body}
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


def write_minimal_docx_with_table(
    path: Path,
    target_text: str = "PENDING_STATUS",
    include_second_table: bool = True,
) -> None:
    second_table = """
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Second table</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>""" if include_second_table else ""
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Body marker outside table</w:t></w:r></w:p>
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
      <w:tr>
        <w:tc><w:p><w:r><w:t>A3</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B3</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>C3</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
{second_table}
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


class WriterOpsTests(unittest.TestCase):
    def test_count_text_in_docx_reads_word_xml_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_minimal_docx(path, "alpha beta alpha")

            self.assertEqual(count_text_in_docx(path, "alpha"), 2)

    def test_docx_table_helpers_read_body_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.docx"
            write_minimal_docx_with_table(path)

            tables = docx_body_tables(path)

            self.assertEqual(len(tables), 2)
            self.assertEqual(docx_table_cell_text(path, 1, 2, 3), "PENDING_STATUS")
            self.assertIsNone(docx_table_cell_text(path, 3, 1, 1))

    def test_writer_replace_dry_run_reports_matches_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            write_minimal_docx(document, "alpha beta alpha")
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            ok, result, errors, replayed = writer_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="replace-dry",
                dry_run=True,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["matches"], 2)
            self.assertFalse((workspace / ".wps-agent" / "backups").exists())

    def test_writer_replace_dry_run_can_scope_to_paragraph(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            write_minimal_docx_paragraphs(document, ["alpha beta", "alpha beta alpha"])
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            ok, result, errors, replayed = writer_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="replace-para-dry",
                dry_run=True,
                paragraph_index=1,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["scope"], "paragraph")
            self.assertEqual(result["paragraph_index"], 1)
            self.assertEqual(result["matches"], 1)

    def test_writer_replace_rejects_out_of_range_paragraph(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            write_minimal_docx_paragraphs(document, ["alpha beta"])
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, _result, errors, replayed = writer_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="replace-para-missing",
                dry_run=True,
                paragraph_index=2,
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "PARAGRAPH_NOT_FOUND")

    def test_writer_replace_rejects_empty_find_text(self):
        ok, result, errors, replayed = writer_replace(
            document_id="doc_missing",
            find_text="",
            replace_text="x",
            request_id="replace-empty",
            dry_run=True,
        )

        self.assertFalse(ok)
        self.assertFalse(replayed)
        self.assertEqual(result, {})
        self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")

    def test_writer_table_write_dry_run_reports_target_without_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "table.docx"
            write_minimal_docx_with_table(document)
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            ok, result, errors, replayed = writer_table_write(
                document_id=record["document_id"],
                table_index=1,
                row=2,
                column=3,
                text="APPROVED_STATUS",
                request_id="table-dry",
                dry_run=True,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["table_count"], 2)
            self.assertEqual(result["current_text"], "PENDING_STATUS")
            self.assertEqual(result["replacement_text"], "APPROVED_STATUS")
            self.assertTrue(result["would_modify"])
            self.assertFalse((workspace / ".wps-agent" / "backups").exists())

    def test_writer_table_write_rejects_missing_cell_without_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "table.docx"
            write_minimal_docx_with_table(document)
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, _result, errors, replayed = writer_table_write(
                document_id=record["document_id"],
                table_index=1,
                row=99,
                column=3,
                text="APPROVED_STATUS",
                request_id="table-missing-cell",
                dry_run=False,
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "CELL_NOT_FOUND")
            self.assertFalse((workspace / ".wps-agent" / "backups").exists())

    def test_writer_table_write_accepts_table_count_normalization_when_cell_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "table.docx"
            write_minimal_docx_with_table(document)
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            def fake_write(path, table_index, row, column, text):
                write_minimal_docx_with_table(
                    Path(path),
                    target_text=text,
                    include_second_table=False,
                )
                return {
                    "ok": True,
                    "data": {"backend": "fake-wps", "read_back_text": text},
                    "errors": [],
                }

            with patch("wps_ai_agent_cli.writer_ops._run_writer_table_write_com", side_effect=fake_write):
                ok, result, errors, replayed = writer_table_write(
                    document_id=record["document_id"],
                    table_index=1,
                    row=2,
                    column=3,
                    text="APPROVED_STATUS",
                    request_id="table-write-normalized",
                    dry_run=False,
                    workspace=workspace,
                )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["table_count"], 2)
            self.assertEqual(result["final_table_count"], 1)
            self.assertFalse(result["table_count_preserved"])
            self.assertEqual(result["read_back_text"], "APPROVED_STATUS")
            self.assertTrue(result["validation_passed"])


if __name__ == "__main__":
    unittest.main()
