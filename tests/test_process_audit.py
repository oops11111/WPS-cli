import subprocess
import unittest
from unittest.mock import patch

from wps_ai_agent_cli.process_audit import audit_wps_processes


class ProcessAuditTests(unittest.TestCase):
    def test_audit_wps_processes_parses_single_process(self):
        completed = subprocess.CompletedProcess(
            args=["pwsh"],
            returncode=0,
            stdout='{"ProcessName":"et","Id":123,"CPU":1.5,"StartTime":"2026-10-03T10:00:00.0000000Z","MainWindowTitle":""}',
            stderr="",
        )
        with patch("wps_ai_agent_cli.process_audit.run_powershell_command", return_value=completed):
            ok, result, errors = audit_wps_processes()

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(result["process_count"], 1)
        self.assertEqual(result["processes"][0]["ProcessName"], "et")
        self.assertIn("Do not automatically kill", result["cleanup_guidance"][0])

    def test_audit_wps_processes_reports_timeout(self):
        with patch("wps_ai_agent_cli.process_audit.run_powershell_command", side_effect=subprocess.TimeoutExpired("pwsh", 2)):
            ok, _result, errors = audit_wps_processes(timeout_seconds=2)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "WPS_PROCESS_AUDIT_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
