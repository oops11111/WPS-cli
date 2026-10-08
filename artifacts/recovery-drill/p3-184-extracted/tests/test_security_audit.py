import unittest

from wps_ai_agent_cli.security_audit import build_security_boundary_audit


class SecurityAuditTests(unittest.TestCase):
    def test_security_boundary_audit_passes_for_mutating_tools(self):
        ok, result, errors = build_security_boundary_audit()

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(result["mutating_tool_count"], 8)
        self.assertEqual(result["failed_tool_count"], 0)
        self.assertTrue(all(tool["status"] == "passed" for tool in result["tools"]))


if __name__ == "__main__":
    unittest.main()
