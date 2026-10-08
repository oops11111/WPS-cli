import io
import json
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.writer_structure_parity import _sha256, run_writer_structure_parity


class WriterStructureParityTests(unittest.TestCase):
    def _observation(self):
        digest = _sha256(Path("fixtures/phase3/writer_structure_wps_fixture.docx"))
        return {
            "ok": True, "read_only": True, "file_unchanged": True,
            "sha256_before": digest, "sha256_after": digest,
            "paragraph_count": 4,
            "paragraphs": [
                {"text": "Structure Audit", "style": "标题 1", "outline_level": 1},
                {"text": "Evidence Section", "style": "标题 2", "outline_level": 2},
                {"text": "Before Alpha after.", "style": "正文", "outline_level": 10},
                {"text": "Plain body text.", "style": "正文", "outline_level": 10},
            ],
            "bookmark_count": 1,
            "bookmarks": [{"name": "AuditMark", "text": "Alpha"}],
        }

    def test_opt_in_is_required_before_subprocess_or_artifact(self):
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run") as process:
            ok, report, errors = run_writer_structure_parity()
        self.assertFalse(ok)
        self.assertFalse(report["wps_launched"])
        self.assertEqual(errors[0]["code"], "WPS_OPT_IN_REQUIRED")
        process.assert_not_called()
        output = io.StringIO()
        self.assertEqual(run(["writer-structure-parity"], output_stream=output), 0)
        self.assertEqual(json.loads(output.getvalue())["errors"][0]["code"], "WPS_OPT_IN_REQUIRED")

    def test_localized_style_names_pass_when_grouping_matches(self):
        observed = self._observation()
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                   return_value=CompletedProcess([], 0, json.dumps(observed), "")) as process:
            ok, report, errors = run_writer_structure_parity(run_wps=True)
        self.assertTrue(ok, errors)
        self.assertEqual(report["parity_status"], "passed")
        self.assertEqual(report["failed_count"], 0)
        self.assertEqual(report["source_sha256"], report["source_sha256_after"])
        self.assertEqual(next(item for item in report["checks"] if item["name"] == "style_grouping")["representations"][0],
                         {"ooxml_style_id": "Heading1", "wps_display_name": "标题 1"})
        process.assert_called_once()

    def test_substantive_mismatches_fail_with_named_checks(self):
        observed = self._observation()
        observed["paragraphs"][0]["text"] = "Wrong"
        observed["paragraphs"][3]["style"] = "Different"
        observed["bookmarks"][0]["text"] = "Wrong"
        observed["sha256_after"] = "0" * 64
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                   return_value=CompletedProcess([], 0, json.dumps(observed), "")):
            ok, report, errors = run_writer_structure_parity(run_wps=True)
        self.assertFalse(ok)
        self.assertEqual(report["parity_status"], "failed")
        self.assertEqual(errors[0]["code"], "WRITER_PARITY_FAILED")
        self.assertEqual(set(errors[0]["details"]), {
            "paragraph_text_and_order", "style_grouping", "bookmark_names_and_text", "source_unchanged",
        })

    def test_failed_wps_observation_keeps_diagnostics(self):
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                   return_value=CompletedProcess([], 2, json.dumps({"ok": False, "error": "COM failed"}), "stderr detail")):
            ok, report, errors = run_writer_structure_parity(run_wps=True)
        self.assertFalse(ok)
        self.assertEqual(report["wps_stderr"], "stderr detail")
        self.assertEqual(report["wps"]["error"], "COM failed")
        self.assertEqual(errors[0]["code"], "WRITER_PARITY_WPS_FAILED")

    def test_invalid_wps_json_keeps_bounded_diagnostics(self):
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                   return_value=CompletedProcess([], 1, "not-json" * 500, "stderr detail")):
            ok, report, errors = run_writer_structure_parity(run_wps=True)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "WRITER_PARITY_WPS_INVALID_JSON")
        self.assertEqual(len(report["wps_stdout_excerpt"]), 2000)
        self.assertEqual(report["wps_stderr_excerpt"], "stderr detail")

    def test_cli_and_mcp_write_local_report_only_with_opt_in(self):
        observed = self._observation()
        with TemporaryDirectory() as tmp, patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                                               return_value=CompletedProcess([], 0, json.dumps(observed), "")):
            output = io.StringIO()
            argv = ["writer-structure-parity", "--run-wps", "--artifact-dir", tmp, "--request-id", "parity-cli"]
            self.assertEqual(run(argv, output_stream=output), 0)
            cli = json.loads(output.getvalue())
            self.assertTrue(cli["ok"])
            self.assertTrue(Path(cli["data"]["artifact"]["path"]).is_file())
            ok, mcp, errors = call_mcp_tool("wps_agent_writer_structure_parity", {
                "run_wps": True, "artifact_dir": tmp, "request_id": "parity-mcp",
            })
            self.assertTrue(ok, errors)
            self.assertEqual(cli["data"]["writer_structure_parity"]["checks"],
                             mcp["response"]["data"]["writer_structure_parity"]["checks"])

    def test_nested_parity_detects_text_mismatch_and_source_immutability(self):
        digest = _sha256(Path("fixtures/phase3/writer_nested_scope_wps_fixture.docx"))
        observed = {
            "ok": True, "read_only": True, "file_unchanged": True,
            "sha256_before": digest, "sha256_after": digest,
            "bookmarks": [
                {"name": "BodyMark", "text": "BodyValue"},
                {"name": "CellMark", "text": "wrong"},
                {"name": "HeaderMark", "text": "HeaderValue"},
                {"name": "FooterMark", "text": "FooterValue"},
            ],
        }
        with patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                   return_value=CompletedProcess([], 0, json.dumps(observed), "")):
            ok, report, errors = run_writer_structure_parity(run_wps=True, scope="nested")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["details"], ["bookmark_names_and_text"])
        self.assertEqual(report["source_sha256"], report["source_sha256_after"])
        self.assertEqual(report["scope"], "nested")

    def test_nested_parity_cli_mcp_artifact_agreement(self):
        digest = _sha256(Path("fixtures/phase3/writer_nested_scope_wps_fixture.docx"))
        observed = {
            "ok": True, "read_only": True, "file_unchanged": True,
            "sha256_before": digest, "sha256_after": digest,
            "bookmarks": [
                {"name": "BodyMark", "text": "BodyValue"},
                {"name": "CellMark", "text": "CellValue"},
                {"name": "HeaderMark", "text": "HeaderValue"},
                {"name": "FooterMark", "text": "FooterValue"},
            ],
        }
        with TemporaryDirectory() as tmp, patch("wps_ai_agent_cli.writer_structure_parity.subprocess.run",
                                               return_value=CompletedProcess([], 0, json.dumps(observed), "")):
            output = io.StringIO()
            self.assertEqual(run(["writer-structure-parity", "--scope", "nested", "--run-wps",
                                  "--artifact-dir", tmp, "--request-id", "nested-cli"], output_stream=output), 0)
            cli = json.loads(output.getvalue())
            self.assertTrue(cli["ok"])
            self.assertTrue(Path(cli["data"]["artifact"]["path"]).name.startswith("writer-nested-parity-"))
            ok, mcp, errors = call_mcp_tool("wps_agent_writer_structure_parity", {
                "scope": "nested", "run_wps": True, "artifact_dir": tmp, "request_id": "nested-mcp",
            })
            self.assertTrue(ok, errors)
            self.assertEqual(cli["data"]["writer_structure_parity"]["checks"],
                             mcp["response"]["data"]["writer_structure_parity"]["checks"])


if __name__ == "__main__":
    unittest.main()
