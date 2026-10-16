"""A file-based write refused on a document open in WPS names the open-document tools (P9-001)."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from wps_ai_agent_cli import cli
from wps_ai_agent_cli.mcp_schema import get_mcp_tool_schema, list_mcp_tool_schemas
from wps_ai_agent_cli.models import CommandResponse
from wps_ai_agent_cli.open_document_hints import OPEN_DOCUMENT_ALTERNATIVES, add_open_document_hint

HELD = {"code": "DOCUMENT_HELD_OPEN", "message": "The document is held open by another handle."}
GUARD = {
    "code": "COM_OPERATION_FAILED",
    "message": "The presentation is already open in WPS and WPS does not reliably report unsaved presentation "
    "changes; close it before running this command.",
}


class HintTests(unittest.TestCase):
    def test_a_held_document_points_to_the_selection_tools_of_its_component(self):
        for command, tool in (
            ("writer-replace", "wps_agent_writer_selection_replace"),
            ("presentation-replace", "wps_agent_presentation_selection_replace"),
            ("spreadsheet-write", "wps_agent_spreadsheet_selection_replace"),
        ):
            with self.subTest(command=command):
                errors = [dict(HELD)]
                self.assertTrue(add_open_document_hint(command, errors))
                self.assertTrue(errors[0]["message"].startswith(HELD["message"]))
                self.assertIn(tool, errors[0]["message"])
                self.assertIn("wps_agent_open_documents", errors[0]["message"])

    def test_the_pre_open_guard_of_a_script_gets_the_hint_too(self):
        errors = [dict(GUARD)]
        self.assertTrue(add_open_document_hint("presentation-replace", errors))
        self.assertIn("wps_agent_presentation_selection_delete", errors[0]["message"])

    def test_sheet_structure_commands_say_there_is_no_open_document_tool(self):
        errors = [dict(HELD)]
        add_open_document_hint("spreadsheet-rename-sheet", errors)
        self.assertIn("no open-document tool for sheet structure", errors[0]["message"])
        self.assertNotIn("selection_replace", errors[0]["message"])

    def test_other_errors_and_other_commands_are_left_alone(self):
        rollback = {"code": "MUTATION_ROLLBACK_BLOCKED", "message": "The document is open in WPS now: close it."}
        other = {"code": "COM_OPERATION_FAILED", "message": "WPS raised 0x800A01A8."}
        errors = [dict(rollback), dict(other)]
        self.assertFalse(add_open_document_hint("writer-replace", errors))
        self.assertEqual(errors, [rollback, other])
        held = [dict(HELD)]
        self.assertFalse(add_open_document_hint("writer-selection-replace", held))
        self.assertFalse(add_open_document_hint("spreadsheet-read", held))
        self.assertEqual(held, [HELD])

    def test_the_hint_is_added_once(self):
        errors = [dict(HELD)]
        add_open_document_hint("writer-replace", errors)
        once = errors[0]["message"]
        self.assertFalse(add_open_document_hint("writer-replace", errors))
        self.assertEqual(errors[0]["message"], once)

    def test_every_listed_command_is_a_mutating_tool_with_the_note_in_its_description(self):
        mutating = {schema["cli_command"] for schema in list_mcp_tool_schemas(mutates_document=True)}
        self.assertLessEqual(set(OPEN_DOCUMENT_ALTERNATIVES), mutating)
        for command in OPEN_DOCUMENT_ALTERNATIVES:
            with self.subTest(command=command):
                notes = get_mcp_tool_schema(command)["safety_notes"]
                self.assertTrue(any(note.startswith("Not for a") and "open in WPS" in note for note in notes))
        for schema in list_mcp_tool_schemas():
            if schema["cli_command"] not in OPEN_DOCUMENT_ALTERNATIVES:
                self.assertFalse(any(note.startswith("Not for a ") for note in schema["safety_notes"]), schema["name"])


class CliTests(unittest.TestCase):
    def run_cli(self, command, errors):
        def handler(args, request_id, output_stream):
            return CommandResponse(
                ok=False, command=command, request_id=request_id, backend="test", summary="refused", errors=errors
            )

        out = io.StringIO()
        with patch.dict(cli.COMMAND_HANDLERS, {command: handler}):
            cli.run([command, "--document-id", "doc_x", "--find", "a", "--replace", "b"], out)
        return json.loads(out.getvalue())

    def test_the_cli_envelope_of_a_refused_file_based_write_carries_the_hint(self):
        envelope = self.run_cli("presentation-replace", [dict(GUARD)])
        self.assertIn("wps_agent_presentation_selection_replace", envelope["errors"][0]["message"])

    def test_a_held_file_raised_during_a_command_carries_the_hint(self):
        def raising(args, request_id, output_stream):
            raise PermissionError(13, "Permission denied", "book.xlsx")

        out = io.StringIO()
        with patch.dict(cli.COMMAND_HANDLERS, {"spreadsheet-write": raising}):
            cli.run(["spreadsheet-write", "--document-id", "doc_x", "--range", "A1", "--values-json", "[[1]]"], out)
        envelope = json.loads(out.getvalue())
        self.assertEqual(envelope["errors"][0]["code"], "DOCUMENT_HELD_OPEN")
        self.assertIn("wps_agent_spreadsheet_selection_replace", envelope["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
