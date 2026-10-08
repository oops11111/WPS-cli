import hashlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.writer_inspect import inspect_writer_structure
from wps_ai_agent_cli.writer_ops import writer_fill_bookmark


class WriterInspectTests(unittest.TestCase):
    def test_bounded_inspection_is_read_only_and_reports_offline_scope(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", f'''<w:document xmlns:w="{namespace}"><w:body>
                    <w:p><w:pPr><w:pStyle w:val="Heading"/></w:pPr><w:r><w:t>One</w:t></w:r></w:p>
                    <w:p><w:pPr><w:pStyle w:val="Heading"/></w:pPr><w:r><w:t>Two</w:t></w:r></w:p>
                    <w:p><w:bookmarkStart w:id="1" w:name="Field"/><w:r><w:t>Value</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>
                </w:body></w:document>''')
                archive.writestr("word/styles.xml", f'''<w:styles xmlns:w="{namespace}">
                    <w:style w:type="paragraph" w:styleId="Heading"><w:name w:val="Heading"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
                </w:styles>''')
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            _, document, _ = register_document("writer", str(path), tmp)
            ok, result, errors = inspect_writer_structure(document["document_id"], 1, tmp)
            self.assertTrue(ok, errors)
            self.assertEqual(result["heading_count"], 2)
            self.assertEqual(len(result["headings"]), 1)
            self.assertEqual(result["headings"][0]["preview"], "One")
            self.assertEqual(result["styles"][0]["style_id"], "Heading")
            self.assertEqual(result["bookmark_count"], 1)
            self.assertTrue(result["truncated"])
            self.assertEqual(result["evidence_backend"], "offline-ooxml")
            self.assertFalse(result["wps_validated"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
                output = io.StringIO()
                self.assertEqual(run(["writer-structure", "--document-id", document["document_id"], "--limit", "1"], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {"document_id": document["document_id"], "limit": 1})
            self.assertTrue(mcp_ok, mcp_errors)
            self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])

    def test_invalid_limit_missing_document_and_non_writer(self):
        self.assertEqual(inspect_writer_structure("missing", 0)[2][0]["code"], "INVALID_LIMIT")
        self.assertEqual(inspect_writer_structure("missing")[2][0]["code"], "DOCUMENT_NOT_FOUND")
        with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value={"component": "spreadsheets", "path": "a.xlsx"}):
            self.assertEqual(inspect_writer_structure("sheet")[2][0]["code"], "UNSUPPORTED_COMPONENT")

    def test_invalid_docx_is_structured_failure(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.docx"
            path.write_text("not a zip", encoding="utf-8")
            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value={"component": "writer", "path": str(path)}):
                ok, _, errors = inspect_writer_structure("broken")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "WRITER_STRUCTURE_INVALID")

    def test_section_pages_and_bookmark_lookup_are_stable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pages.docx"
            namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            body = "".join(
                f'<w:p><w:pPr><w:pStyle w:val="Heading"/></w:pPr><w:bookmarkStart w:id="{index}" w:name="{name}"/>'
                f'<w:r><w:t>Heading {index}</w:t></w:r><w:bookmarkEnd w:id="{index}"/></w:p>'
                for index, name in enumerate(("Repeated", "Repeated", "Unique", "Last"), 1)
            )
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", f'<w:document xmlns:w="{namespace}"><w:body>{body}</w:body></w:document>')
                archive.writestr("word/styles.xml", f'<w:styles xmlns:w="{namespace}"><w:style w:type="paragraph" w:styleId="Heading"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>')
            _, document, _ = register_document("writer", str(path), tmp)
            doc_id = document["document_id"]
            ok, first, errors = inspect_writer_structure(doc_id, 2, tmp, section="headings")
            self.assertTrue(ok, errors)
            self.assertEqual(first["pagination"]["headings"], {"offset": 0, "returned_count": 2, "total_count": 4, "next_offset": 2})
            ok, second, errors = inspect_writer_structure(doc_id, 2, tmp, section="headings", offset=2,
                                                           expected_sha256=first["source_sha256"])
            self.assertTrue(ok, errors)
            self.assertEqual([item["preview"] for item in first["headings"] + second["headings"]],
                             ["Heading 1", "Heading 2", "Heading 3", "Heading 4"])
            self.assertIsNone(second["pagination"]["headings"]["next_offset"])
            self.assertFalse(second["truncated"])
            self.assertEqual(first["source_sha256"], second["source_sha256"])

            for name, status, count in (("Repeated", "ambiguous", 2), ("Unique", "unique", 1), ("Absent", "missing", 0)):
                with self.subTest(name=name):
                    ok, result, errors = inspect_writer_structure(doc_id, 1, tmp, section="bookmarks", bookmark_name=name)
                    self.assertTrue(ok, errors)
                    self.assertEqual(result["bookmark_query"], {"name": name, "match_count": count, "status": status})
                    self.assertEqual(result["pagination"]["bookmarks"]["total_count"], count)

            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
                output = io.StringIO()
                self.assertEqual(run(["writer-structure", "--document-id", doc_id, "--section", "headings", "--offset", "2",
                                      "--limit", "2", "--expected-sha256", first["source_sha256"]], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                    "document_id": doc_id, "section": "headings", "offset": 2, "limit": 2,
                    "expected_sha256": first["source_sha256"],
                })
            self.assertTrue(mcp_ok, mcp_errors)
            self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])

            path.write_bytes(path.read_bytes() + b"changed")
            self.assertEqual(inspect_writer_structure(doc_id, 2, tmp, section="headings", offset=2,
                                                       expected_sha256=first["source_sha256"])[2][0]["code"], "WRITER_SOURCE_CHANGED")

    def test_invalid_pagination_parameters_are_rejected(self):
        for kwargs, code in (
            ({"section": "nope"}, "INVALID_SECTION"),
            ({"offset": -1}, "INVALID_OFFSET"),
            ({"offset": 1}, "INVALID_OFFSET"),
            ({"bookmark_name": "Field"}, "INVALID_BOOKMARK_QUERY"),
            ({"section": "bookmarks", "bookmark_name": ""}, "INVALID_BOOKMARK_QUERY"),
            ({"section": "bookmarks", "bookmark_name": "x" * 257}, "INVALID_BOOKMARK_QUERY"),
            ({"expected_sha256": "bad"}, "INVALID_SOURCE_HASH"),
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(inspect_writer_structure("missing", **kwargs)[2][0]["code"], code)

    def test_bookmark_text_statuses_and_cli_mcp_parity(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "values.docx"
            namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", f'''<w:document xmlns:w="{namespace}"><w:body>
                    <w:p><w:bookmarkStart w:id="1" w:name="Value"/><w:r><w:t>Long value</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>
                    <w:p><w:bookmarkStart w:id="2" w:name="Empty"/><w:bookmarkEnd w:id="2"/></w:p>
                    <w:p><w:bookmarkStart w:id="3" w:name="Repeated"/><w:bookmarkEnd w:id="3"/>
                         <w:bookmarkStart w:id="4" w:name="Repeated"/><w:bookmarkEnd w:id="4"/></w:p>
                    <w:tbl><w:tr><w:tc><w:p><w:bookmarkStart w:id="5" w:name="Cell"/>
                         <w:r><w:t>Private</w:t></w:r><w:bookmarkEnd w:id="5"/></w:p></w:tc></w:tr></w:tbl>
                </w:body></w:document>''')
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            _, document, _ = register_document("writer", str(path), tmp)
            doc_id = document["document_id"]
            expected = {
                "Value": ("available", "Long ", True, 10),
                "Empty": ("empty", "", False, 0),
                "Repeated": ("ambiguous", None, False, None),
                "Cell": ("available", "Priva", True, 7),
                "Absent": ("missing", None, False, None),
            }
            for name, (status, value, truncated, length) in expected.items():
                with self.subTest(name=name):
                    ok, result, errors = inspect_writer_structure(
                        doc_id, workspace=tmp, section="bookmarks", bookmark_name=name,
                        include_text=True, text_limit=5,
                    )
                    self.assertTrue(ok, errors)
                    self.assertEqual(result["bookmark_value"]["status"], status)
                    self.assertEqual(result["bookmark_value"]["text"], value)
                    self.assertEqual(result["bookmark_value"]["truncated"], truncated)
                    self.assertEqual(result["bookmark_value"]["text_length"], length)
                    self.assertFalse(result["wps_validated"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
                output = io.StringIO()
                args = ["writer-structure", "--document-id", doc_id, "--section", "bookmarks",
                        "--bookmark-name", "Value", "--include-text", "--text-limit", "5"]
                self.assertEqual(run(args, output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                    "document_id": doc_id, "section": "bookmarks", "bookmark_name": "Value",
                    "include_text": True, "text_limit": 5,
                })
            self.assertTrue(mcp_ok, mcp_errors)
            self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])

            with patch("wps_ai_agent_cli.writer_inspect.read_supported_bookmark_text", return_value=(None, None)):
                ok, result, errors = inspect_writer_structure(
                    doc_id, workspace=tmp, section="bookmarks", bookmark_name="Value", include_text=True,
                )
            self.assertTrue(ok, errors)
            self.assertEqual(result["bookmark_value"]["status"], "invalid_range")

    def test_bookmark_text_invalid_input_and_malformed_file(self):
        for kwargs, code in (
            ({"include_text": True}, "INVALID_BOOKMARK_TEXT_QUERY"),
            ({"section": "bookmarks", "bookmark_name": "A", "include_text": True, "offset": 1}, "INVALID_BOOKMARK_TEXT_QUERY"),
            ({"text_limit": 0}, "INVALID_TEXT_LIMIT"),
            ({"text_limit": 4097}, "INVALID_TEXT_LIMIT"),
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(inspect_writer_structure("missing", **kwargs)[2][0]["code"], code)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.docx"
            path.write_text("not a zip", encoding="utf-8")
            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value={"component": "writer", "path": str(path)}):
                ok, _, errors = inspect_writer_structure("broken", section="bookmarks", bookmark_name="A", include_text=True)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "WRITER_STRUCTURE_INVALID")

    def test_revision_paragraph_bookmark_is_unreadable_and_unwritable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "revision.docx"
            namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", f'''<w:document xmlns:w="{namespace}"><w:body><w:p>
                    <w:ins><w:r><w:t>Inserted</w:t></w:r></w:ins>
                    <w:bookmarkStart w:id="1" w:name="Field"/><w:r><w:t>Value</w:t></w:r>
                    <w:bookmarkEnd w:id="1"/>
                </w:p></w:body></w:document>''')
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            _, document, _ = register_document("writer", str(path), tmp)
            document_id = document["document_id"]
            ok, result, errors = inspect_writer_structure(
                document_id, workspace=tmp, section="bookmarks", bookmark_name="Field", include_text=True,
            )
            self.assertTrue(ok, errors)
            self.assertEqual(result["bookmark_value"]["status"], "unsupported_scope")
            with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
                output = io.StringIO()
                self.assertEqual(run(["writer-structure", "--document-id", document_id, "--section", "bookmarks",
                                      "--bookmark-name", "Field", "--include-text"], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                    "document_id": document_id, "section": "bookmarks", "bookmark_name": "Field", "include_text": True,
                })
            self.assertTrue(mcp_ok, mcp_errors)
            self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])
            filled, _, fill_errors, _ = writer_fill_bookmark(
                document_id, "Field", "replacement", "revision-dry-run", dry_run=True, workspace=tmp,
            )
            self.assertFalse(filled)
            self.assertEqual(fill_errors[0]["code"], "BOOKMARK_SCOPE_UNSUPPORTED")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
