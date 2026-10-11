import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_open_documents import Fixture, com_ok
from wps_ai_agent_cli import cli, open_documents
from wps_ai_agent_cli.errors import OperationRecordError
from wps_ai_agent_cli.mutation_lock import coordinated_mutation, coordinated_request
from wps_ai_agent_cli.state_store import StateCorruptError


class OperationRecordFailureTests(unittest.TestCase):
    def test_decorator_turns_a_record_failure_into_a_structured_error(self):
        @coordinated_mutation
        def mutate(document_id, request_id, workspace="."):
            raise OperationRecordError("Operation recorded, but document identity could not be captured: gone")

        with tempfile.TemporaryDirectory() as workspace:
            ok, data, errors, replayed = mutate("doc_1", "req-1", workspace=workspace)
        self.assertFalse(ok)
        self.assertFalse(replayed)
        self.assertTrue(data["mutation_applied"])
        self.assertEqual(data["request_id"], "req-1")
        self.assertEqual(errors[0]["code"], "OPERATION_RECORD_FAILED")
        self.assertIn("mutation-request-inspect", errors[0]["message"])

    def test_request_decorator_turns_a_record_failure_into_a_structured_error(self):
        @coordinated_request
        def mutate(request_id, workspace="."):
            raise OperationRecordError("Operation recorded, but document identity could not be captured: gone")

        with tempfile.TemporaryDirectory() as workspace:
            ok, data, errors, replayed = mutate("req-r1", workspace=workspace)
        self.assertFalse(ok)
        self.assertFalse(replayed)
        self.assertTrue(data["mutation_applied"])
        self.assertEqual(data["request_id"], "req-r1")
        self.assertEqual(errors[0]["code"], "OPERATION_RECORD_FAILED")
        self.assertIn("mutation-request-inspect", errors[0]["message"])

    def test_request_decorator_does_not_mask_other_oserrors(self):
        @coordinated_request
        def mutate(request_id, workspace="."):
            raise OSError("disk on fire")

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaises(OSError):
                mutate("req-r2", workspace=workspace)

    def test_save_as_open_document_reports_record_failure_instead_of_a_traceback(self):
        with tempfile.TemporaryDirectory() as workspace:
            output = Path(workspace) / "saved.docx"
            inspect_payload = com_ok({"ok": True, "status": "ok", "saved": False, "read_only": False})

            def fake_com(component, name, output_path, do_save):
                if do_save:
                    Path(output_path).write_bytes(b"PK-fake")
                    return com_ok({
                        "ok": True, "status": "ok", "saved": True, "read_only": False,
                        "wrote": True, "source_still_open": True, "path_matched": True,
                        "full_name": output_path, "backend": "powershell-com",
                    })
                return inspect_payload

            with patch.object(open_documents, "_run_save_as_untitled_com", side_effect=fake_com), \
                    patch("wps_ai_agent_cli.open_documents.record_operation",
                          side_effect=OperationRecordError("ledger write failed")):
                ok, data, errors, _replayed = open_documents.save_as_open_document(
                    "writer", "Document1", str(output), request_id="req-saveas-record",
                    workspace=workspace,
                )
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OPERATION_RECORD_FAILED")
        self.assertTrue(data["mutation_applied"])

    def test_other_oserrors_are_not_masked(self):
        @coordinated_mutation
        def mutate(document_id, request_id, workspace="."):
            raise OSError("disk on fire")

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaises(OSError):
                mutate("doc_1", "req-2", workspace=workspace)

    def test_save_open_document_reports_record_failure_instead_of_a_traceback(self):
        fixture = Fixture(self)
        saved = com_ok({"ok": True, "status": "ok", "saved": True, "read_only": False})
        with patch.object(open_documents, "_run_component_attached_com", return_value=saved), \
                patch("wps_ai_agent_cli.operations.file_identity", side_effect=OSError("unavailable")):
            ok, data, errors, _replayed = open_documents.save_open_document(
                fixture.document_id, "req-save-record", workspace=fixture.workspace,
            )
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OPERATION_RECORD_FAILED")
        self.assertTrue(data["mutation_applied"])

    def test_state_corruption_summary_does_not_claim_the_command_never_ran(self):
        import io
        import json

        output = io.StringIO()
        error = StateCorruptError(Path("documents.json"), Path("documents.json.corrupt-x"), "bad json")
        with patch.object(cli, "documents_response", side_effect=error):
            cli.run(["documents"], output_stream=output)
        response = json.loads(output.getvalue())
        self.assertEqual(response["errors"][0]["code"], "STATE_CORRUPT")
        self.assertNotIn("was not executed", response["summary"])
        self.assertIn("mutation-request-inspect", response["summary"])


if __name__ == "__main__":
    unittest.main()
