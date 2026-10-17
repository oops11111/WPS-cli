"""An open-document write result says what the saved file now holds (P10-002)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from tests.test_open_documents import Fixture, com_ok, selection_payload
from tests.test_presentation_ops import write_minimal_pptx
from tests.test_writer_ops import write_minimal_docx_paragraphs
from wps_ai_agent_cli import cli, open_documents
from wps_ai_agent_cli.mcp_schema import get_mcp_tool_schema
from wps_ai_agent_cli.models import CommandResponse
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.verified_state import (
    VERIFIED_COMMANDS,
    cell_write_state,
    document_summary_state,
    saved_document_state,
    text_file_state,
    text_write_state,
)


class Files:
    def __init__(self, test):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def docx(self, name, paragraphs):
        path = self.root / name
        write_minimal_docx_paragraphs(path, paragraphs)
        return path

    def pptx(self, name, slides):
        path = self.root / name
        write_minimal_pptx(path, slides)
        return path

    def xlsx(self, name, cells):
        path = self.root / name
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Status"
        for coordinate, value in cells.items():
            sheet[coordinate] = value
        workbook.save(path)
        workbook.close()
        return path


class TextWriteStateTests(unittest.TestCase):
    def test_a_replaced_paragraph_is_named_with_its_text_before_and_after(self):
        files = Files(self)
        backup = files.docx("before.docx", ["Title", "Status: DRAFT", "Owner: Finance"])
        saved = files.docx("after.docx", ["Title", "Status: FINAL", "Owner: Finance"])
        state = text_write_state(saved, str(backup), "DRAFT", "FINAL")
        self.assertTrue(state["passed"])
        self.assertEqual(state["source"], "saved_file")
        self.assertEqual(state["changes"], [{"paragraph": 2, "before": "Status: DRAFT", "after": "Status: FINAL"}])
        self.assertIn("paragraph 2 changed from 'Status: DRAFT' to 'Status: FINAL'", state["check"])
        self.assertIn("no other content changed", state["check"])

    def test_inserts_and_deletes_are_checked_by_the_change_in_length(self):
        files = Files(self)
        backup = files.docx("before.docx", ["Owner: Finance"])
        inserted = files.docx("inserted.docx", ["Owner: Finance (reviewed)"])
        self.assertTrue(text_write_state(inserted, str(backup), "", " (reviewed)")["passed"])
        self.assertFalse(text_write_state(inserted, str(backup), "", " (checked)")["passed"])
        deleted = files.docx("deleted.docx", ["Owner: "])
        self.assertTrue(text_write_state(deleted, str(backup), "Finance", "")["passed"])

    def test_a_paragraph_wps_rewrote_on_save_is_listed_after_the_write(self):
        files = Files(self)
        backup = files.docx("before.docx", ["Owner: Finance", "Status: DRAFT"])
        saved = files.docx("after.docx", ["Owner: Finance ", "Status: FINAL"])
        state = text_write_state(saved, str(backup), "DRAFT", "FINAL")
        self.assertTrue(state["passed"])
        self.assertEqual(state["other_changes"], 1)
        self.assertEqual(state["changes"][0]["after"], "Status: FINAL")
        self.assertIn("The write is there", state["check"])
        self.assertIn("the file also has 1 other change(s) in its paragraphs", state["check"])

    def test_a_paragraph_without_the_write_fails_the_check(self):
        files = Files(self)
        backup = files.docx("before.docx", ["Status: DRAFT"])
        saved = files.docx("after.docx", ["Status: FINAL!"])
        state = text_write_state(saved, str(backup), "DRAFT", "FINAL")
        self.assertFalse(state["passed"])
        self.assertIn("does not match the write", state["check"])

    def test_a_presentation_text_box_is_named_by_slide(self):
        files = Files(self)
        backup = files.pptx("before.pptx", ["Agenda", "Status: DRAFT"])
        saved = files.pptx("after.pptx", ["Agenda", "Status: FINAL"])
        state = text_write_state(saved, str(backup), "DRAFT", "FINAL")
        self.assertTrue(state["passed"], state)
        self.assertEqual(state["unit"], "text_boxes")
        self.assertEqual(state["changes"][0]["slide"], 2)
        self.assertIn("on slide 2 changed from 'Status: DRAFT' to 'Status: FINAL'", state["check"])

    def test_without_a_backup_or_a_reader_the_state_says_it_was_read_back_in_wps_only(self):
        files = Files(self)
        saved = files.docx("after.docx", ["x"])
        self.assertEqual(text_write_state(saved, None, "a", "b")["source"], "wps_read_back")
        legacy = files.root / "old.doc"
        legacy.write_bytes(b"\xd0\xcf")
        state = text_write_state(legacy, str(legacy), "a", "b")
        self.assertIsNone(state["passed"])
        self.assertIn("no reader for .doc", state["check"])
        broken = files.root / "broken.docx"
        broken.write_bytes(b"not a zip")
        self.assertEqual(text_write_state(broken, str(broken), "a", "b")["source"], "wps_read_back")


class CellWriteStateTests(unittest.TestCase):
    def test_changed_cells_inside_the_selection_pass(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"A1": "Item", "C2": "DRAFT", "D2": "DRAFT"})
        saved = files.xlsx("after.xlsx", {"A1": "Item", "C2": "FINAL", "D2": "FINAL"})
        state = cell_write_state(saved, str(backup), "Status", "$C$2:$D$2")
        self.assertTrue(state["passed"])
        self.assertEqual(
            state["changes"],
            [
                {"sheet": "Status", "cell": "C2", "before": "DRAFT", "after": "FINAL"},
                {"sheet": "Status", "cell": "D2", "before": "DRAFT", "after": "FINAL"},
            ],
        )
        self.assertIn("Status!C2 changed from 'DRAFT' to 'FINAL'", state["check"])

    def test_the_cells_around_the_write_and_the_header_are_shown(self):
        files = Files(self)
        cells = {"A1": "Item", "B1": "Owner", "C1": "Status", "A4": "Gamma", "C4": "DRAFT", "C5": "DRAFT"}
        backup = files.xlsx("before.xlsx", cells)
        saved = files.xlsx("after.xlsx", {**cells, "C4": "FINAL", "C5": "FINAL"})
        state = cell_write_state(saved, str(backup), "Status", "$C$4:$C$5")
        around = state["surroundings"]
        self.assertEqual(around["range"], "B3:D6")
        self.assertEqual(around["rows"][1], [None, "FINAL", None])
        self.assertEqual(around["header_range"], "B1:D1")
        self.assertEqual(around["header"], ["Owner", "Status", None])
        self.assertEqual(around["changed_outside_selection"], [])
        self.assertIn("The cells around it (B3:D6 and the header row B1:D1)", state["check"])

    def test_a_range_at_the_top_left_has_no_separate_header_and_a_changed_neighbour_is_named(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"A1": "DRAFT", "B1": "x"})
        saved = files.xlsx("after.xlsx", {"A1": "FINAL", "B1": "y"})
        state = cell_write_state(saved, str(backup), "Status", "A1")
        around = state["surroundings"]
        self.assertEqual(around["range"], "A1:B2")
        self.assertNotIn("header", around)
        self.assertEqual(around["changed_outside_selection"], ["B1"])
        self.assertFalse(state["passed"])
        self.assertNotIn("did not change", state["check"])

    def test_the_surroundings_of_a_large_range_are_capped(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"A1": 1})
        state = cell_write_state(files.xlsx("after.xlsx", {"A1": 1}), str(backup), "Status", "C3:Z40")
        around = state["surroundings"]
        self.assertEqual(around["range"], "B2:K11")
        self.assertTrue(around["truncated"])
        self.assertEqual(len(around["rows"]), 10)

    def test_a_change_outside_the_selection_fails(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"C2": "DRAFT", "E9": 1})
        saved = files.xlsx("after.xlsx", {"C2": "FINAL", "E9": 2})
        outside = cell_write_state(saved, str(backup), "Status", "C2")
        self.assertFalse(outside["passed"])
        self.assertEqual(outside["other_changes"], 1)
        self.assertTrue(cell_write_state(saved, str(backup), "Status", "C2,E9")["passed"])

    def test_a_clear_must_leave_the_cells_empty(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"B2": "DRAFT"})
        cleared = files.xlsx("cleared.xlsx", {})
        state = cell_write_state(cleared, str(backup), "Status", "B2", cleared=True)
        self.assertTrue(state["passed"])
        self.assertIn("Status!B2 changed from 'DRAFT' to (empty)", state["check"])

    def test_a_chart_or_shape_write_changes_no_cell(self):
        files = Files(self)
        backup = files.xlsx("before.xlsx", {"A1": 1})
        same = files.xlsx("same.xlsx", {"A1": 1})
        state = cell_write_state(same, str(backup), "Status", None, object_kind="chart title", read_back_text="Q3")
        self.assertTrue(state["passed"])
        self.assertIn("WPS read the chart title back as 'Q3'", state["check"])


class FileStateTests(unittest.TestCase):
    def test_save_names_what_the_save_wrote(self):
        files = Files(self)
        backup = files.docx("before.docx", ["Draft"])
        saved = files.docx("after.docx", ["Draft", "Added in WPS"])
        state = saved_document_state(saved, str(backup))
        self.assertTrue(state["passed"])
        self.assertEqual(state["changes"], [{"paragraph": 2, "before": None, "after": "Added in WPS"}])

    def test_save_as_reads_the_new_file(self):
        files = Files(self)
        state = document_summary_state(files.docx("new.docx", ["Hello", "World"]))
        self.assertTrue(state["passed"])
        self.assertIn("a Writer document with 2 paragraphs", state["check"])
        self.assertIn(
            "a workbook with 1 non-empty cells", document_summary_state(files.xlsx("b.xlsx", {"A1": 1}))["check"]
        )

    def test_text_export_reads_the_file_back(self):
        files = Files(self)
        out = files.root / "out.txt"
        out.write_bytes("核对清单\r\n✅".encode())
        state = text_file_state(out, "utf-8")
        self.assertEqual(state["text_head"], "核对清单\n✅")
        self.assertIn("read back as utf-8: 6 characters", state["check"])


class WriterWriteResultTests(unittest.TestCase):
    def test_a_selection_replace_result_carries_the_saved_paragraph(self):
        fixture = Fixture(self)
        write_minimal_docx_paragraphs(fixture.document, ["Report", "Status: PENDING_STATUS"])
        register_document("writer", str(fixture.document), fixture.workspace)

        def fake(action, params):
            if action == "selection-read":
                return com_ok(selection_payload())
            write_minimal_docx_paragraphs(fixture.document, ["Report", f"Status: {params['text']}"])
            return com_ok({"ok": True, "status": "ok", "backend": "fake-wps", "read_back_text": params["text"]})

        with patch.object(open_documents, "_run_writer_attached_com", side_effect=fake):
            ok, data, errors, _replayed = open_documents.replace_writer_selection(
                document_id=fixture.document_id,
                text="APPROVED",
                request_id="sel-1",
                workspace=fixture.workspace,
            )
        self.assertTrue(ok, errors)
        state = data["verified_state"]
        self.assertTrue(state["passed"], state)
        self.assertEqual(state["changes"][0]["after"], "Status: APPROVED")


class CliSummaryTests(unittest.TestCase):
    def test_the_check_is_added_to_the_summary_of_a_successful_write(self):
        state = {"passed": True, "check": "The saved file was compared with the pre-write backup: x."}

        def handler(args, request_id, output_stream):
            return CommandResponse(
                ok=True,
                command="writer-selection-replace",
                request_id=request_id,
                backend="test",
                summary="Writer selection replace completed.",
                data={"verified_state": state},
            )

        out = io.StringIO()
        with patch.dict(cli.COMMAND_HANDLERS, {"writer-selection-replace": handler}):
            cli.run(["writer-selection-replace", "--document-id", "doc_x", "--text", "a"], out)
        envelope = json.loads(out.getvalue())
        self.assertEqual(envelope["summary"], f"Writer selection replace completed. {state['check']}")


class McpDescriptionTests(unittest.TestCase):
    def test_the_checking_tools_say_they_are_not_needed_after_a_write(self):
        for command in ("validate-document", "snapshot-document", "spreadsheet-read"):
            with self.subTest(command=command):
                notes = get_mcp_tool_schema(command)["safety_notes"]
                self.assertTrue(any(note.startswith("Not needed to check an open-document write") for note in notes))

    def test_every_verified_command_says_the_result_is_already_checked(self):
        for command in VERIFIED_COMMANDS:
            with self.subTest(command=command):
                notes = get_mcp_tool_schema(command)["safety_notes"]
                self.assertTrue(any("verified_state" in note and "no need" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
