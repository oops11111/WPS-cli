import io
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.capabilities import powershell_executable
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.writer_inspect import inspect_writer_structure
from wps_ai_agent_cli.writer_ops import writer_fill_bookmark
from wps_ai_agent_cli.writer_structure import read_body_bookmark_text, read_supported_bookmark_text, read_writer_structure


FIXTURE = Path("fixtures/phase3/writer_nested_scope_wps_fixture.docx")
SCRIPT = Path("scripts/audit_writer_structure_wps.ps1")


class WriterNestedScopeFixtureTests(unittest.TestCase):
    def test_offline_scopes_and_public_read_boundaries(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        structure = read_writer_structure(FIXTURE)
        bookmarks = {item["name"]: item for item in structure["bookmarks"]}
        self.assertEqual(set(bookmarks), {"BodyMark", "CellMark", "HeaderMark", "FooterMark"})
        self.assertEqual(len(structure["paragraphs"]), 2)
        self.assertEqual(bookmarks["BodyMark"]["start"]["scope"], "body_paragraph")
        self.assertEqual(bookmarks["CellMark"]["start"]["scope"], "table")
        self.assertEqual(bookmarks["HeaderMark"]["start"]["scope"], "header_footer")
        self.assertEqual(bookmarks["FooterMark"]["start"]["scope"], "header_footer")
        self.assertTrue(all(item["status"] == "paired" for item in bookmarks.values()))
        self.assertTrue(bookmarks["BodyMark"]["body_paragraph_range_supported"])
        self.assertFalse(any(bookmarks[name]["body_paragraph_range_supported"] for name in ("CellMark", "HeaderMark", "FooterMark")))
        self.assertTrue(all(item["text_range_supported"] for item in bookmarks.values()))
        self.assertEqual(read_body_bookmark_text(FIXTURE, "BodyMark")[1], "BodyValue")
        self.assertIsNone(read_body_bookmark_text(FIXTURE, "CellMark")[1])
        expected = {"BodyMark": "BodyValue", "CellMark": "CellValue",
                    "HeaderMark": "HeaderValue", "FooterMark": "FooterValue"}
        self.assertEqual({name: read_supported_bookmark_text(FIXTURE, name)[1] for name in bookmarks}, expected)
        document = {"component": "writer", "path": str(FIXTURE.resolve())}
        with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
            for name in bookmarks:
                with self.subTest(name=name):
                    ok, result, errors = inspect_writer_structure(
                        "fixture", section="bookmarks", bookmark_name=name, include_text=True,
                    )
                    self.assertTrue(ok, errors)
                    self.assertEqual(result["bookmark_value"]["status"], "available")
                    self.assertEqual(result["bookmark_value"]["text"], expected[name])
                    self.assertFalse(result["wps_validated"])
                    output = io.StringIO()
                    args = ["writer-structure", "--document-id", "fixture", "--section", "bookmarks",
                            "--bookmark-name", name, "--include-text"]
                    self.assertEqual(run(args, output_stream=output), 0)
                    cli = json.loads(output.getvalue())
                    mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                        "document_id": "fixture", "section": "bookmarks", "bookmark_name": name, "include_text": True,
                    })
                    self.assertTrue(mcp_ok, mcp_errors)
                    self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)

    def test_direct_table_dry_run_stays_read_only_and_other_nested_writes_reject(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            ok, record, errors = register_document("writer", str(FIXTURE.resolve()), tmp)
            self.assertTrue(ok, errors)
            with patch("wps_ai_agent_cli.writer_ops._run_writer_bookmark_fill_com") as mutation:
                for name in ("CellMark", "HeaderMark", "FooterMark"):
                    with self.subTest(name=name):
                        filled, _, fill_errors, _ = writer_fill_bookmark(
                            record["document_id"], name, "replacement", f"read-only-{name}",
                            dry_run=True, workspace=tmp,
                        )
                        if name == "CellMark":
                            self.assertTrue(filled, fill_errors)
                        else:
                            self.assertFalse(filled)
                            self.assertEqual(fill_errors[0]["code"], "BOOKMARK_SCOPE_UNSUPPORTED")
                mutation.assert_not_called()
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)

    @unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_INTEGRATION") == "1", "set WPS_AGENT_RUN_INTEGRATION=1 to launch local WPS Writer")
    def test_wps_read_only_bookmark_observations(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest().upper()
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT.resolve()),
             "-Path", str(FIXTURE.resolve())],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=90,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        observed = json.loads(completed.stdout)
        self.assertTrue(observed["ok"])
        self.assertTrue(observed["read_only"])
        self.assertTrue(observed["file_unchanged"])
        self.assertEqual(observed["sha256_before"], before)
        self.assertEqual(observed["sha256_after"], before)
        self.assertEqual({item["name"]: item["text"] for item in observed["bookmarks"]}, {
            "BodyMark": "BodyValue", "CellMark": "CellValue",
            "HeaderMark": "HeaderValue", "FooterMark": "FooterValue",
        })
        document = {"component": "writer", "path": str(FIXTURE.resolve())}
        with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
            for item in observed["bookmarks"]:
                name = item["name"]
                ok, result, errors = inspect_writer_structure(
                    "fixture", section="bookmarks", bookmark_name=name, include_text=True,
                )
                self.assertTrue(ok, errors)
                self.assertEqual(result["bookmark_value"]["text"], item["text"])
                output = io.StringIO()
                self.assertEqual(run(["writer-structure", "--document-id", "fixture", "--section", "bookmarks",
                                      "--bookmark-name", name, "--include-text"], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                    "document_id": "fixture", "section": "bookmarks", "bookmark_name": name,
                    "include_text": True,
                })
                self.assertTrue(mcp_ok, mcp_errors)
                self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])
                self.assertEqual(cli["data"]["writer_structure"]["bookmark_value"]["text"], item["text"])
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest().upper(), before)


if __name__ == "__main__":
    unittest.main()
