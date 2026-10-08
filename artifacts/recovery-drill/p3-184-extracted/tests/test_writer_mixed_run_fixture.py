import hashlib
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.capabilities import powershell_executable
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.writer_inspect import inspect_writer_structure
from wps_ai_agent_cli.writer_structure import read_supported_bookmark_text


FIXTURE = Path("fixtures/phase3/writer_mixed_run_wps_fixture.docx")
SCRIPT = Path("scripts/audit_writer_structure_wps.ps1")
EXPECTED_SHA256 = "0CF410E40E6B1AD88A9AA7471CCA3CBF03BF5125A8C045D9BBB281EF1BC34B6C"


class WriterMixedRunFixtureTests(unittest.TestCase):
    def test_offline_cli_mcp_mixed_text_agreement(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest().upper()
        self.assertEqual(before, EXPECTED_SHA256)
        bookmark, value = read_supported_bookmark_text(FIXTURE, "MixedMark")
        self.assertEqual(bookmark["start"]["scope"], "table")
        self.assertTrue(bookmark["text_range_supported"])
        self.assertEqual(value, "AB\tC")
        document = {"component": "writer", "path": str(FIXTURE.resolve())}
        with patch("wps_ai_agent_cli.writer_inspect.get_document", return_value=document):
            ok, result, errors = inspect_writer_structure(
                "fixture", section="bookmarks", bookmark_name="MixedMark", include_text=True,
            )
            self.assertTrue(ok, errors)
            self.assertEqual(result["bookmark_value"]["text"], value)
            output = io.StringIO()
            self.assertEqual(run(["writer-structure", "--document-id", "fixture", "--section", "bookmarks",
                                  "--bookmark-name", "MixedMark", "--include-text"], output_stream=output), 0)
            cli = json.loads(output.getvalue())
            mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_writer_structure", {
                "document_id": "fixture", "section": "bookmarks", "bookmark_name": "MixedMark",
                "include_text": True,
            })
            self.assertTrue(mcp_ok, mcp_errors)
            self.assertEqual(cli["data"]["writer_structure"], mcp["response"]["data"]["writer_structure"])
            self.assertEqual(cli["data"]["writer_structure"]["bookmark_value"]["text"], value)
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest().upper(), before)

    @unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_INTEGRATION") == "1", "set WPS_AGENT_RUN_INTEGRATION=1 to launch local WPS Writer")
    def test_read_only_wps_mixed_text(self):
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
        self.assertEqual(observed["bookmarks"], [{"name": "MixedMark", "text": read_supported_bookmark_text(FIXTURE, "MixedMark")[1]}])
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest().upper(), before)


if __name__ == "__main__":
    unittest.main()
