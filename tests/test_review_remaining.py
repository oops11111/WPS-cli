import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from wps_ai_agent_cli.document_text import docx_table_cell_rich_content
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.spreadsheet_ranges import validate_spreadsheet_read_range
from wps_ai_agent_cli.writer_ops import WORD_FIND_TEXT_MAX_CHARS, writer_replace, writer_table_write

try:
    from test_writer_ops import write_minimal_docx_paragraphs, write_minimal_docx_with_table
except ModuleNotFoundError:  # unittest discover as tests.test_*
    from tests.test_writer_ops import write_minimal_docx_paragraphs, write_minimal_docx_with_table


def write_docx_table_with_hyperlink(path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:tbl>
      <w:tr>
        <w:tc>
          <w:p>
            <w:hyperlink r:id="rId1">
              <w:r><w:t>link</w:t></w:r>
            </w:hyperlink>
          </w:p>
        </w:tc>
      </w:tr>
    </w:tbl>
    <w:p/>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        archive.writestr("word/document.xml", xml)


class RichCellWriteTests(unittest.TestCase):
    def test_rich_content_is_detected_in_a_hyperlink_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rich.docx"
            write_docx_table_with_hyperlink(path)
            self.assertEqual(docx_table_cell_rich_content(path, 1, 1, 1), ["hyperlink"])

    def test_plain_cell_has_no_rich_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.docx"
            write_minimal_docx_with_table(path)
            self.assertEqual(docx_table_cell_rich_content(path, 1, 2, 3), [])

    def test_writer_table_write_refuses_rich_cells_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "rich.docx"
            write_docx_table_with_hyperlink(document)
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok, errors)

            ok, result, errors, replayed = writer_table_write(
                document_id=record["document_id"],
                table_index=1,
                row=1,
                column=1,
                text="PLAIN",
                request_id="rich-refuse",
                dry_run=True,
                workspace=workspace,
            )
            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "CELL_HAS_RICH_CONTENT")
            self.assertEqual(result["rich_content"], ["hyperlink"])

            ok, result, errors, replayed = writer_table_write(
                document_id=record["document_id"],
                table_index=1,
                row=1,
                column=1,
                text="PLAIN",
                request_id="rich-allow",
                dry_run=True,
                allow_rich_content=True,
                workspace=workspace,
            )
            self.assertTrue(ok, errors)
            self.assertTrue(result["allow_rich_content"])


class WriterReplaceLengthTests(unittest.TestCase):
    def test_find_text_over_word_limit_is_rejected_before_wps(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "doc.docx"
            write_minimal_docx_paragraphs(document, ["hello"])
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok, errors)
            with patch("wps_ai_agent_cli.writer_ops._run_writer_replace_com") as com:
                ok, _result, errors, replayed = writer_replace(
                    document_id=record["document_id"],
                    find_text="x" * (WORD_FIND_TEXT_MAX_CHARS + 1),
                    replace_text="y",
                    request_id="find-too-long",
                    dry_run=False,
                    workspace=workspace,
                )
            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "FIND_TEXT_TOO_LONG")
            com.assert_not_called()


class SpreadsheetRangeMessageTests(unittest.TestCase):
    def test_sheet_qualified_and_whole_axis_ranges_have_clear_messages(self):
        for address, needle in (
            ("Sheet1!A1:B2", "Sheet-qualified"),
            ("A:A", "finite A1"),
            ("1:1", "finite A1"),
        ):
            with self.subTest(address=address):
                bounds, error = validate_spreadsheet_read_range(address)
                self.assertIsNone(bounds)
                self.assertEqual(error["code"], "INVALID_RANGE")
                self.assertIn(needle, error["message"])


class ProcessTreeKillTests(unittest.TestCase):
    def test_kill_process_tree_uses_taskkill_on_windows(self):
        from wps_ai_agent_cli import html_render

        process = MagicMock()
        process.pid = 99
        process.poll.return_value = None
        with patch.object(html_render.sys, "platform", "win32"), patch.object(
            html_render.subprocess, "run"
        ) as run:
            html_render._kill_process_tree(process)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][:4], ["taskkill", "/F", "/T", "/PID"])


if __name__ == "__main__":
    unittest.main()
