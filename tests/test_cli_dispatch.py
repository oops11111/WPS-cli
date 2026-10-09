import io
import json
import unittest

from wps_ai_agent_cli import cli


def _subcommands():
    parser = cli.build_parser()
    action = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    return set(action.choices)


class CliDispatchTests(unittest.TestCase):
    def test_every_parser_command_has_exactly_one_handler(self):
        self.assertEqual(_subcommands(), set(cli.COMMAND_HANDLERS))

    def test_removed_reporting_commands_are_rejected_by_the_parser(self):
        from tests.test_mcp_schema import REMOVED_REPORTING_COMMANDS

        for command in sorted(REMOVED_REPORTING_COMMANDS | {"local-release-gates"}):
            with self.subTest(command=command):
                self.assertNotIn(command, _subcommands())
                self.assertNotIn(command, cli.COMMAND_HANDLERS)

    def test_dispatch_emits_json_envelope(self):
        stream = io.StringIO()
        code = cli.run(["plan", "--request-id", "dispatch-1"], stream)
        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["command"], "plan")
        self.assertEqual(payload["request_id"], "dispatch-1")

    def test_server_handler_exit_code_is_returned_without_envelope(self):
        stream = io.StringIO()
        code = cli.run(["mcp-server", "--once-json", json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})], stream)
        self.assertEqual(code, 0)
        self.assertEqual(stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
