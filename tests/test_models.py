import unittest

from wps_ai_agent_cli.models import CommandResponse, ValidationResult


class CommandResponseTests(unittest.TestCase):
    def test_to_dict_keeps_agent_contract_fields(self):
        response = CommandResponse(
            ok=True,
            command="inspect-env",
            request_id="req-1",
            backend="local-python",
            summary="done",
            validation=ValidationResult(
                status="passed",
                checks=[{"name": "sample", "passed": True}],
            ),
        )

        payload = response.to_dict()

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["request_id"], "req-1")
        self.assertEqual(payload["backend"], "local-python")
        self.assertEqual(payload["validation"]["status"], "passed")
        self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
