import json
import unittest
from unittest.mock import patch

from wps_ai_agent_cli import process_audit


class Completed:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


class ProcessAuditParsingTests(unittest.TestCase):
    def audit(self, stdout):
        with patch.object(process_audit.subprocess, "run", return_value=Completed(stdout)):
            return process_audit.audit_wps_processes()

    def test_valid_list_output(self):
        ok, data, errors = self.audit(json.dumps([{"ProcessName": "wps", "Id": 1}, {"ProcessName": "et", "Id": 2}]))
        self.assertTrue(ok)
        self.assertEqual(data["process_count"], 2)

    def test_single_object_output(self):
        ok, data, _ = self.audit(json.dumps({"ProcessName": "wps", "Id": 1}))
        self.assertTrue(ok)
        self.assertEqual(data["process_count"], 1)

    def test_warning_prefix_before_json_is_tolerated(self):
        ok, data, _ = self.audit("WARNING: something\n" + json.dumps([{"ProcessName": "wps", "Id": 1}]))
        self.assertTrue(ok)
        self.assertEqual(data["process_count"], 1)

    def test_garbage_output_is_structured_failure(self):
        ok, data, errors = self.audit("not json at all")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "WPS_PROCESS_AUDIT_FAILED")

    def test_truncated_json_is_structured_failure(self):
        ok, _, errors = self.audit('[{"ProcessName": "wps"')
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "WPS_PROCESS_AUDIT_FAILED")

    def test_empty_output_means_no_processes(self):
        ok, data, _ = self.audit("")
        self.assertTrue(ok)
        self.assertEqual(data["process_count"], 0)


if __name__ == "__main__":
    unittest.main()
