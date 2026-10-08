import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.state_store import StateCorruptError, read_json_state


def invoke(argv):
    stream = io.StringIO()
    code = run(argv, output_stream=stream)
    return code, json.loads(stream.getvalue())


class StateCorruptionTests(unittest.TestCase):
    def test_corrupt_state_is_quarantined_and_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{"documents": {', encoding="utf-8")
            with self.assertRaises(StateCorruptError) as caught:
                read_json_state(path, {})
            self.assertFalse(path.exists())
            self.assertTrue(caught.exception.quarantined.exists())
            self.assertEqual(caught.exception.quarantined.read_text(encoding="utf-8"), '{"documents": {')

    def test_non_object_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(StateCorruptError):
                read_json_state(path, {})

    def test_missing_state_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_json_state(Path(tmp) / "none.json", {"a": 1}), {"a": 1})

    def test_cli_reports_corrupt_state_as_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                state = Path(".wps-agent")
                state.mkdir()
                (state / "documents.json").write_text("{", encoding="utf-8")
                code, payload = invoke(["documents", "--request-id", "r-corrupt"])
            finally:
                os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["code"], "STATE_CORRUPT")
        self.assertEqual(payload["request_id"], "r-corrupt")
        self.assertEqual(payload["command"], "documents")


class StrictExitTests(unittest.TestCase):
    def run_in_tmp(self, argv):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                return invoke(argv)
            finally:
                os.chdir(previous)

    def test_default_exit_code_stays_zero_on_failure(self):
        code, payload = self.run_in_tmp(["backup-document", "--document-id", "nope", "--request-id", "x"])
        self.assertFalse(payload["ok"])
        self.assertEqual(code, 0)

    def test_strict_exit_returns_one_on_failure(self):
        code, payload = self.run_in_tmp(["--strict-exit", "backup-document", "--document-id", "nope", "--request-id", "x"])
        self.assertFalse(payload["ok"])
        self.assertEqual(code, 1)

    def test_strict_exit_flag_works_after_subcommand_and_keeps_success_zero(self):
        code, payload = self.run_in_tmp(["documents", "--strict-exit"])
        self.assertTrue(payload["ok"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
