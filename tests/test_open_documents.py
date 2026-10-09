import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import cli, open_documents
from wps_ai_agent_cli.open_documents import (
    export_open_document_html,
    list_open_documents,
    read_writer_selection,
    replace_writer_selection,
)
from wps_ai_agent_cli.sessions import register_document, stable_document_id
from tests.test_writer_ops import write_minimal_docx_with_table


def com_ok(data):
    return {"ok": True, "errors": [], "data": data}


def selection_payload(text="PENDING_STATUS", start=10, end=None, saved=True, **extra):
    return {
        "ok": True,
        "status": "ok",
        "saved": saved,
        "start": start,
        "end": start + len(text) if end is None else end,
        "selection_text": text,
        "paragraph_index": 3,
        "page_number": 1,
        **extra,
    }


class Fixture:
    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir()
        self.document = Path(self.tmp.name) / "open.docx"
        write_minimal_docx_with_table(self.document)
        ok, record, _errors = register_document("writer", str(self.document), self.workspace)
        assert ok
        self.document_id = record["document_id"]


class ListOpenDocumentsTests(unittest.TestCase):
    def test_reports_missing_instance_without_launching_anything(self):
        with patch.object(open_documents, "_run_open_documents_com", return_value=com_ok({"ok": True, "instances": []})) as com:
            ok, data, errors = list_open_documents()
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "NO_RUNNING_WPS_INSTANCE")
        self.assertEqual(data["probed_components"], ["writer", "spreadsheets", "presentation"])
        com.assert_called_once()

    def test_lists_documents_with_registered_id_and_untitled_documents(self):
        fixture = Fixture(self)
        payload = {
            "ok": True,
            "instances": {
                "component": "writer",
                "version": "12.1",
                "documents": [
                    {"name": "open.docx", "full_name": str(fixture.document), "saved": True, "read_only": False, "active": True},
                    {"name": "Document1", "full_name": "Document1", "saved": False, "read_only": False, "active": False},
                ],
            },
        }
        with patch.object(open_documents, "_run_open_documents_com", return_value=com_ok(payload)):
            ok, data, errors = list_open_documents(component="writer", workspace=fixture.workspace)
        self.assertTrue(ok, errors)
        self.assertEqual(data["instances"], [{"component": "writer", "version": "12.1", "document_count": 2}])
        saved, untitled = data["documents"]
        self.assertEqual(saved["document_id"], fixture.document_id)
        self.assertTrue(saved["registered"])
        self.assertTrue(saved["active"])
        self.assertIsNone(untitled["document_id"])
        self.assertFalse(untitled["path_exists"])

    def test_register_flag_registers_saved_documents_only(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        workspace = Path(tmp.name) / "workspace"
        workspace.mkdir()
        document = Path(tmp.name) / "fresh.docx"
        write_minimal_docx_with_table(document)
        payload = {
            "ok": True,
            "instances": [{
                "component": "writer",
                "documents": [{"name": "fresh.docx", "full_name": str(document), "saved": True, "read_only": False, "active": False}],
            }],
        }
        with patch.object(open_documents, "_run_open_documents_com", return_value=com_ok(payload)):
            _ok, without, _errors = list_open_documents(workspace=workspace)
            self.assertIsNone(without["documents"][0]["document_id"])
            ok, data, _errors = list_open_documents(register=True, workspace=workspace)
        self.assertTrue(ok)
        self.assertEqual(data["documents"][0]["document_id"], stable_document_id("writer", str(document)))

    def test_rejects_unknown_component_before_touching_wps(self):
        with patch.object(open_documents, "_run_open_documents_com") as com:
            ok, _data, errors = list_open_documents(component="outlook")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "UNSUPPORTED_COMPONENT")
        com.assert_not_called()


class SelectionReadTests(unittest.TestCase):
    def test_reads_selection_and_flags_page_as_unverified(self):
        fixture = Fixture(self)
        with patch.object(open_documents, "_run_writer_attached_com", return_value=com_ok(selection_payload())):
            ok, data, errors = read_writer_selection(fixture.document_id, fixture.workspace)
        self.assertTrue(ok, errors)
        self.assertEqual(data["selection_text"], "PENDING_STATUS")
        self.assertFalse(data["collapsed"])
        self.assertEqual(data["paragraph_index"], 3)
        self.assertFalse(data["page_info_verified"])

    def test_truncates_long_selection_text(self):
        fixture = Fixture(self)
        payload = selection_payload(text="x" * 5000)
        with patch.object(open_documents, "_run_writer_attached_com", return_value=com_ok(payload)):
            ok, data, _errors = read_writer_selection(fixture.document_id, fixture.workspace)
        self.assertTrue(ok)
        self.assertEqual(len(data["selection_text"]), 4096)
        self.assertTrue(data["selection_text_truncated"])
        self.assertEqual(data["selection_length"], 5000)

    def test_status_codes_map_to_structured_errors(self):
        fixture = Fixture(self)
        cases = {
            "no_instance": "NO_RUNNING_WPS_INSTANCE",
            "not_open": "DOCUMENT_NOT_OPEN",
            "no_window": "SELECTION_UNAVAILABLE",
        }
        for status, code in cases.items():
            with self.subTest(status=status):
                with patch.object(open_documents, "_run_writer_attached_com", return_value=com_ok({"ok": True, "status": status})):
                    ok, _data, errors = read_writer_selection(fixture.document_id, fixture.workspace)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)

    def test_unregistered_and_wrong_component_documents_are_rejected(self):
        fixture = Fixture(self)
        ok, _data, errors = read_writer_selection("doc_missing", fixture.workspace)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "DOCUMENT_NOT_FOUND")

        sheet = Path(fixture.tmp.name) / "book.xlsx"
        sheet.write_bytes(b"x")
        _ok, record, _errors = register_document("spreadsheets", str(sheet), fixture.workspace)
        ok, _data, errors = read_writer_selection(record["document_id"], fixture.workspace)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "UNSUPPORTED_COMPONENT")

    def test_com_timeout_is_returned_as_structured_error(self):
        fixture = Fixture(self)
        failure = {"ok": False, "errors": [{"code": "COM_OPERATION_TIMEOUT", "message": "timed out"}], "data": {"timed_out": True}}
        with patch.object(open_documents, "_run_writer_attached_com", return_value=failure):
            ok, data, errors = read_writer_selection(fixture.document_id, fixture.workspace)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "COM_OPERATION_TIMEOUT")
        self.assertTrue(data["timed_out"])


class SelectionReplaceTests(unittest.TestCase):
    def replace(self, fixture, text="APPROVED", request_id="sel-1", **kwargs):
        return replace_writer_selection(
            document_id=fixture.document_id, text=text, request_id=request_id, workspace=fixture.workspace, **kwargs,
        )

    def fake_attached(self, fixture, selection, write_status="ok", read_back=None, calls=None):
        def fake(action, params):
            if calls is not None:
                calls.append(action)
            if action == "selection-read":
                return com_ok(selection)
            self.assertEqual(action, "selection-replace")
            fixture.document.write_bytes(fixture.document.read_bytes() + b"\0")
            if write_status != "ok":
                return com_ok({"ok": True, "status": write_status})
            return com_ok({"ok": True, "status": "ok", "backend": "fake-wps", "read_back_text": params["text"] if read_back is None else read_back})
        return fake

    def test_dry_run_previews_without_backup_or_write(self):
        fixture = Fixture(self)
        calls = []
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_attached(fixture, selection_payload(), calls=calls)):
            ok, data, errors, replayed = self.replace(fixture, dry_run=True, expected_selection_text="PENDING_STATUS")
        self.assertTrue(ok, errors)
        self.assertFalse(replayed)
        self.assertEqual(calls, ["selection-read"])
        self.assertTrue(data["would_modify"])
        self.assertEqual(data["selection_text"], "PENDING_STATUS")
        self.assertFalse((fixture.workspace / ".wps-agent" / "backups").exists())

    def test_replaces_with_backup_validation_and_replay(self):
        fixture = Fixture(self)
        calls = []
        original = fixture.document.read_bytes()
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_attached(fixture, selection_payload(), calls=calls)):
            ok, data, errors, _replayed = self.replace(fixture, expected_selection_text="PENDING_STATUS")
            self.assertTrue(ok, errors)
            self.assertTrue(data["validation_passed"])
            self.assertTrue(data["backup"]["created"])
            self.assertEqual(Path(data["backup"]["backup_path"]).read_bytes(), original)
            self.assertEqual(data["write_backend"], "fake-wps")
            self.assertFalse(data["selection_preserved"])

            ok, again, errors, replayed = self.replace(fixture, expected_selection_text="PENDING_STATUS")
            self.assertTrue(ok, errors)
            self.assertTrue(replayed)
            self.assertEqual(again["read_back_text"], "APPROVED")
        self.assertEqual(calls.count("selection-replace"), 1)

    def test_rejections_happen_before_backup_and_write(self):
        fixture = Fixture(self)
        cases = [
            ("unsaved", {"ok": True, "status": "unsaved"}, {}, "DOCUMENT_HAS_UNSAVED_CHANGES"),
            ("empty", selection_payload(text="", start=5, end=5), {}, "SELECTION_EMPTY"),
            ("too-large", selection_payload(text="x" * 5000), {}, "SELECTION_TOO_LARGE"),
            ("paragraph-mark", selection_payload(text="line\r", start=4), {}, "SELECTION_SPANS_STRUCTURE"),
            ("object", selection_payload(text="ab", start=4, end=9), {}, "SELECTION_SPANS_STRUCTURE"),
            ("mismatch", selection_payload(), {"expected_selection_text": "something else"}, "SELECTION_MISMATCH"),
        ]
        for name, payload, kwargs, code in cases:
            with self.subTest(name=name):
                calls = []
                with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_attached(fixture, payload, calls=calls)):
                    ok, _data, errors, _replayed = self.replace(fixture, request_id=f"sel-{name}", **kwargs)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                self.assertNotIn("selection-replace", calls)
        self.assertFalse((fixture.workspace / ".wps-agent" / "backups").exists())

    def test_invalid_replacement_text_is_rejected_before_attaching(self):
        fixture = Fixture(self)
        with patch.object(open_documents, "_run_writer_attached_com") as com:
            for index, value in enumerate(["a\nb", "a\x00b", "x" * 4097]):
                ok, _data, errors, _replayed = self.replace(fixture, text=value, request_id=f"sel-bad-{index}")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
        com.assert_not_called()

    def test_selection_changed_between_preview_and_write_is_reported(self):
        fixture = Fixture(self)
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_attached(fixture, selection_payload(), write_status="selection_changed")):
            ok, data, errors, _replayed = self.replace(fixture, request_id="sel-race")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "SELECTION_MISMATCH")
        self.assertTrue(data["backup"]["created"])

    def test_read_back_mismatch_fails_validation_and_is_not_recorded(self):
        fixture = Fixture(self)
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_attached(fixture, selection_payload(), read_back="garbled")):
            ok, data, errors, _replayed = self.replace(fixture, request_id="sel-bad-readback")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
            self.assertFalse(data["validation_passed"])
        from wps_ai_agent_cli.operations import get_operation

        self.assertIsNone(get_operation("sel-bad-readback", fixture.workspace))

    def test_com_timeout_during_write_leaves_structured_error(self):
        import subprocess

        fixture = Fixture(self)

        def fake(action, params):
            if action == "selection-read":
                return com_ok(selection_payload())
            raise subprocess.TimeoutExpired("powershell", 120)

        with patch.object(open_documents, "_run_writer_attached_com", side_effect=fake):
            ok, _data, errors, _replayed = self.replace(fixture, request_id="sel-timeout")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "COM_OPERATION_TIMEOUT")


class ExportOpenDocumentTests(unittest.TestCase):
    def export(self, fixture, output, request_id="exp-1"):
        return export_open_document_html(
            document_id=fixture.document_id, output=str(output), request_id=request_id, workspace=fixture.workspace,
        )

    def fake_export(self, output, status="ok", write=True, touch_source=None, still_open=True):
        def fake(action, params):
            self.assertEqual(action, "export-html")
            if write:
                Path(params["output"]).write_text("<html></html>", encoding="utf-8")
                Path(params["output"]).with_name(Path(params["output"]).stem + ".files").mkdir()
            if touch_source is not None:
                touch_source.write_bytes(touch_source.read_bytes() + b"\0")
            return com_ok({"ok": True, "status": status, "export_method": "SaveAs2", "source_still_open": still_open})
        return fake

    def test_exports_html_and_verifies_source_unchanged(self):
        fixture = Fixture(self)
        output = Path(fixture.tmp.name) / "out.html"
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_export(output)):
            ok, data, errors, _replayed = self.export(fixture, output)
            self.assertTrue(ok, errors)
            self.assertTrue(data["source_unchanged"])
            self.assertTrue(data["source_still_open"])
            self.assertTrue(data["validation_passed"])
            self.assertEqual(data["format"], "html")
            self.assertEqual(len(data["companion_directories"]), 1)
            self.assertTrue(data["known_losses"])

            ok, again, _errors, replayed = self.export(fixture, output)
            self.assertTrue(ok)
            self.assertTrue(replayed)
            self.assertEqual(again["output"], data["output"])

    def test_invalid_outputs_are_rejected_without_calling_wps(self):
        fixture = Fixture(self)
        existing = Path(fixture.tmp.name) / "exists.html"
        existing.write_text("keep", encoding="utf-8")
        cases = [
            (fixture.document, "INVALID_ARGUMENT"),
            (Path(fixture.tmp.name) / "out.pdf", "INVALID_ARGUMENT"),
            (existing, "OUTPUT_EXISTS"),
            (Path(fixture.tmp.name) / "missing-dir" / "out.html", "INVALID_ARGUMENT"),
        ]
        with patch.object(open_documents, "_run_writer_attached_com") as com:
            for index, (output, code) in enumerate(cases):
                with self.subTest(output=str(output)):
                    ok, _data, errors, _replayed = self.export(fixture, output, request_id=f"exp-bad-{index}")
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], code)
        com.assert_not_called()
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_unsaved_or_closed_documents_are_reported(self):
        fixture = Fixture(self)
        for status, code in (("unsaved", "DOCUMENT_HAS_UNSAVED_CHANGES"), ("not_open", "DOCUMENT_NOT_OPEN"), ("no_instance", "NO_RUNNING_WPS_INSTANCE")):
            with self.subTest(status=status):
                output = Path(fixture.tmp.name) / f"{status}.html"
                with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_export(output, status=status, write=False)):
                    ok, _data, errors, _replayed = self.export(fixture, output, request_id=f"exp-{status}")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)

    def test_missing_output_and_changed_source_are_failures(self):
        fixture = Fixture(self)
        missing = Path(fixture.tmp.name) / "missing.html"
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_export(missing, write=False)):
            ok, _data, errors, _replayed = self.export(fixture, missing, request_id="exp-missing")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "EXPORT_OUTPUT_MISSING")

        changed = Path(fixture.tmp.name) / "changed.html"
        with patch.object(open_documents, "_run_writer_attached_com", side_effect=self.fake_export(changed, touch_source=fixture.document)):
            ok, data, errors, _replayed = self.export(fixture, changed, request_id="exp-changed")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "DOCUMENT_CHANGED_AFTER_COM")
        self.assertFalse(data["source_unchanged"])


class ScriptRenderingTests(unittest.TestCase):
    def test_rendered_scripts_have_no_placeholders_and_never_quit_wps(self):
        for action in ("selection-read", "selection-replace", "export-html"):
            with self.subTest(action=action):
                captured = {}

                def fake_run(script, timeout_seconds=120, **_kwargs):
                    captured["script"] = script
                    return {"ok": True, "status": "no_instance"}, None

                with patch.object(open_documents, "run_powershell_script", side_effect=fake_run):
                    result = open_documents._run_writer_attached_com(action, {"path": "C:\\docs\\a.docx", "text": "it's '@ tricky"})
                script = captured["script"]
                self.assertTrue(result["ok"])
                self.assertNotIn("__PARAMS_JSON__", script)
                self.assertNotIn("__ACTION_BODY__", script)
                self.assertNotIn(".Quit()", script)
                self.assertIn('"prog_ids"', script)
                self.assertIn("\n'@ | ConvertFrom-Json", script)

    def test_list_script_probes_every_component_prog_id(self):
        captured = {}

        def fake_run(script, timeout_seconds=120, **_kwargs):
            captured["script"] = script
            return {"ok": True, "instances": []}, None

        with patch.object(open_documents, "run_powershell_script", side_effect=fake_run):
            open_documents._run_open_documents_com(["writer", "presentation"])
        script = captured["script"]
        self.assertIn("kwps.Application", script)
        self.assertIn("kwpp.Application", script)
        self.assertNotIn("ket.Application", script)
        self.assertNotIn(".Quit()", script)


class CliWiringTests(unittest.TestCase):
    def run_cli(self, argv):
        output = io.StringIO()
        code = cli.run(argv, output_stream=output)
        return code, json.loads(output.getvalue())

    def test_open_documents_command_reports_missing_instance(self):
        with patch.object(open_documents, "_run_open_documents_com", return_value=com_ok({"ok": True, "instances": []})):
            code, response = self.run_cli(["open-documents", "--component", "writer", "--request-id", "cli-open"])
        self.assertEqual(code, 0)
        self.assertFalse(response["ok"])
        self.assertEqual(response["errors"][0]["code"], "NO_RUNNING_WPS_INSTANCE")
        self.assertEqual(response["request_id"], "cli-open")

    def test_new_commands_are_exposed_as_mcp_tools(self):
        from wps_ai_agent_cli.mcp_schema import get_mcp_tool_schema

        expected = {
            "open-documents": False,
            "writer-selection-read": False,
            "writer-selection-replace": True,
            "export-open-document": False,
        }
        for command, mutates in expected.items():
            schema = get_mcp_tool_schema(command)
            self.assertIsNotNone(schema, command)
            self.assertTrue(schema["requires_wps"])
            self.assertEqual(schema["mutates_document"], mutates)
            self.assertTrue(schema["safety_notes"])


if __name__ == "__main__":
    unittest.main()
