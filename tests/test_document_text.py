import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from tests.test_writer_structure import write_document
from wps_ai_agent_cli.document_text import count_text_in_docx, count_text_in_docx_paragraph, docx_body_paragraphs
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.validators import validate_document
from wps_ai_agent_cli.writer_ops import writer_replace


class LogicalWriterTextTests(unittest.TestCase):
    def test_split_runs_entities_and_scoped_consumers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.docx"
            write_document(path, '<w:p><w:r><w:t>A &amp; </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>B &lt; C</w:t></w:r></w:p>')
            before = path.read_bytes()
            needle = "A & B < C"
            self.assertEqual(count_text_in_docx(path, needle), 1)
            self.assertEqual(count_text_in_docx_paragraph(path, 1, needle), 1)
            _, record, _ = register_document("writer", str(path), tmp)
            ok, result, errors = validate_document(record["document_id"], contains=needle, workspace=tmp)
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["count"], 1)
            for scope in (None, 1):
                with patch("wps_ai_agent_cli.writer_ops.create_backup") as backup:
                    ok, result, errors, _ = writer_replace(record["document_id"], needle, "updated", "logical-dry", dry_run=True, paragraph_index=scope, workspace=tmp)
                self.assertTrue(ok)
                self.assertEqual(errors, [])
                self.assertEqual(result["matches"], 1)
                backup.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_attributes_field_instructions_and_deleted_text_are_not_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.docx"
            write_document(path, '''<w:p>
                <w:bookmarkStart w:id="1" w:name="attribute_only"/>
                <w:r><w:instrText>instruction_only</w:instrText><w:t>result</w:t></w:r>
                <w:del><w:r><w:delText>deleted_only</w:delText><w:t>deleted_fallback</w:t></w:r></w:del>
                <w:moveFrom><w:r><w:t>moved_only</w:t></w:r></w:moveFrom>
                <w:ins><w:r><w:t>inserted</w:t></w:r></w:ins>
            </w:p>''')
            for needle in ("attribute_only", "instruction_only", "deleted_only", "deleted_fallback", "moved_only", "bookmarkStart"):
                self.assertEqual(count_text_in_docx(path, needle), 0)
            self.assertEqual(count_text_in_docx(path, "resultinserted"), 1)
            _, record, _ = register_document("writer", str(path), tmp)
            ok, _, errors = validate_document(record["document_id"], contains="attribute_only", workspace=tmp)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
            with patch("wps_ai_agent_cli.writer_ops.create_backup") as backup:
                ok, _, errors, _ = writer_replace(record["document_id"], "attribute_only", "x", "no-match", workspace=tmp)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "TEXT_NOT_FOUND")
            backup.assert_not_called()

    def test_paragraph_cell_and_story_boundaries_and_part_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.docx"
            write_document(path, '''
                <w:p><w:r><w:t>alpha</w:t></w:r></w:p>
                <w:p><w:r><w:t>beta</w:t></w:r></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r><w:r><w:t>text</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>other</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
            ''', header='<w:p><w:r><w:t>alpha</w:t></w:r></w:p>')
            self.assertEqual(count_text_in_docx(path, "alpha"), 2)
            self.assertEqual(count_text_in_docx(path, "alpha", parts=["word/document.xml"]), 1)
            self.assertEqual(count_text_in_docx(path, "celltext"), 1)
            self.assertEqual(count_text_in_docx(path, "alphabeta"), 0)
            self.assertEqual(count_text_in_docx(path, "celltextother"), 0)
            self.assertEqual(count_text_in_docx(path, "alpha", parts=[]), 0)
            self.assertEqual(docx_body_paragraphs(path), ["alpha", "beta"])

    def test_tabs_breaks_and_textboxes_do_not_join_unrelated_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.docx"
            write_document(path, '''<w:p><w:r><w:t>left</w:t><w:tab/><w:t>right</w:t><w:br/><w:t>next</w:t><w:cr/><w:t>end</w:t></w:r>
                <w:r><w:txbxContent><w:p><w:r><w:t>box_only</w:t></w:r></w:p></w:txbxContent></w:r></w:p>''')
            self.assertEqual(docx_body_paragraphs(path), ["left\tright\nnext\nend"])
            self.assertEqual(count_text_in_docx(path, "leftright"), 0)
            self.assertEqual(count_text_in_docx(path, "right\nnext"), 1)
            self.assertEqual(count_text_in_docx(path, "box_only"), 0)
            self.assertEqual(count_text_in_docx_paragraph(path, 1, "box_only"), 0)

    def test_non_story_xml_is_not_treated_as_document_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.docx"
            write_document(path, "<w:p/>")
            with ZipFile(path, "a") as archive:
                archive.writestr("word/styles.xml", '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>metadata</w:t></w:r></w:p></w:styles>')
            self.assertEqual(count_text_in_docx(path, "metadata"), 0)


if __name__ == "__main__":
    unittest.main()
