"""Batch-1 hardening: macro safety (S-01), installer fail-closed (S-03), rollback whitelist (S-05),
license metadata (U-03) and the release gate (T-01)."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from wps_ai_agent_cli import wps_convert
from wps_ai_agent_cli.atomic_mutation import atomic_mutation
from wps_ai_agent_cli.backups import create_backup, record_after_com_identity
from wps_ai_agent_cli.errors import ROLLBACK_FAILED
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD, QUIET_ALERTS

ROOT = Path(__file__).resolve().parents[1]


class MacroSafetyTests(unittest.TestCase):
    def test_quiet_alerts_also_disables_macros_and_link_updates(self):
        self.assertIn("AskToUpdateLinks", QUIET_ALERTS)
        self.assertIn("EnableEvents", QUIET_ALERTS)
        self.assertIn("Disable-WpsMacros", QUIET_ALERTS)

    def test_macro_disable_is_defined_in_the_shared_prelude_and_restored(self):
        self.assertIn("function Disable-WpsMacros", PRE_OPEN_GUARD)
        self.assertIn("AutomationSecurity = 3", PRE_OPEN_GUARD)
        self.assertIn("wpsPrevSettings['AutomationSecurity']", PRE_OPEN_GUARD)

    def test_writer_and_presentation_scripts_quiet_the_app_they_open_with(self):
        writer = (ROOT / "src/wps_ai_agent_cli/writer_ops.py").read_text(encoding="utf-8")
        presentation = (ROOT / "src/wps_ai_agent_cli/presentation_ops.py").read_text(encoding="utf-8")
        self.assertEqual(writer.count("{QUIET_ALERTS}"), 3)
        self.assertEqual(presentation.count("{QUIET_ALERTS}"), 1)

    def test_wps_conversion_refuses_macro_enabled_sources(self):
        for suffix in (".docm", ".xlsm", ".pptm"):
            component, _code, _mode, refusal = wps_convert.plan(Path(f"in{suffix}"), Path("out.pdf"))
            self.assertIsNone(component)
            self.assertEqual(len(refusal), 1)
            self.assertIn("Macro-enabled", refusal[0]["message"])

    def test_trusted_macro_source_can_be_planned_explicitly(self):
        component, _code, mode, refusal = wps_convert.plan(Path("in.docm"), Path("out.pdf"), allow_macro_enabled=True)
        self.assertEqual(component, "writer")
        self.assertEqual(mode, "pdf")
        self.assertEqual(refusal, [])


class InstallerAndReleaseTests(unittest.TestCase):
    def test_installer_refuses_an_unchecked_wheel(self):
        text = (ROOT / "scripts/install/install.ps1").read_text(encoding="utf-8")
        self.assertIn("refusing to install an unchecked download", text)
        self.assertNotIn("the download was not checked", text)

    def test_release_is_gated_on_the_test_suite(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("needs: verify", workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)

    def test_license_file_and_metadata_exist(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = { text = "MIT" }', pyproject)


class RollbackWhitelistTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.document = root / "book.xlsx"
        Workbook().save(self.document)
        ok, record, _ = register_document("spreadsheets", str(self.document), self.workspace)
        self.assertTrue(ok)
        self.document_id = record["document_id"]
        ok, backup, _, _ = create_backup(self.document_id, "req-batch1:backup", workspace=self.workspace)
        self.assertTrue(ok)
        self.backup_path = backup["backup_path"]
        self.original_bytes = self.document.read_bytes()
        from unittest.mock import patch

        probe = patch("wps_ai_agent_cli.open_documents.list_open_documents", return_value=(True, {"documents": []}, []))
        self._probe = probe.start()
        self.addCleanup(probe.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _mutation(self, backup_path: str, after_change: bytes | None):
        document, workspace = self.document, self.workspace

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            document.write_bytes(b"WPS saved this")
            if after_change is not None:
                document.write_bytes(after_change)
            return (
                False,
                {"document_id": document_id, "backup": {"backup_path": backup_path}},
                [{"code": "VALIDATION_FAILED", "message": "read-back mismatch"}],
                False,
            )

        return write(self.document_id, "req-batch1", workspace=workspace)

    def test_rollback_restores_the_bytes_the_command_itself_wrote(self):
        record_after_com_identity(self.document, {"source_sha256": hashlib.sha256(b"WPS saved this").hexdigest()})
        ok, result, errors, _ = self._mutation(self.backup_path, after_change=None)
        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertTrue(result["rollback"]["performed"])

    def test_after_a_rollback_the_next_command_needs_no_new_registration(self):
        record_after_com_identity(self.document, {"source_sha256": hashlib.sha256(b"WPS saved this").hexdigest()})
        ok, result, _errors, _ = self._mutation(self.backup_path, after_change=None)
        self.assertFalse(ok)
        self.assertTrue(result["rollback"]["performed"])
        self.assertTrue(result["rollback"]["registration_refreshed"])
        # It used to fail with DOCUMENT_IDENTITY_CHANGED: the restored file is a new file with the same content.
        ok, _backup, errors, _ = create_backup(self.document_id, "next:backup", workspace=self.workspace)
        self.assertTrue(ok, errors)

    def test_a_registration_is_not_moved_onto_other_content(self):
        from wps_ai_agent_cli.atomic_mutation import _refresh_registration
        from wps_ai_agent_cli.sessions import get_document

        document = get_document(self.document_id, self.workspace)
        self.document.write_bytes(b"something else")
        outcome = _refresh_registration(document, self.workspace)
        self.assertFalse(outcome["registration_refreshed"])
        self.assertEqual(get_document(self.document_id, self.workspace)["source_sha256"], document["source_sha256"])

    def test_rollback_does_not_overwrite_a_later_change(self):
        record_after_com_identity(self.document, {"source_sha256": hashlib.sha256(b"WPS saved this").hexdigest()})
        ok, result, errors, _ = self._mutation(self.backup_path, after_change=b"someone else edited this")
        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), b"someone else edited this")
        self.assertFalse(result["rollback"]["performed"])
        self.assertIn("changed after this command wrote it", result["rollback"]["reason"])
        self.assertEqual([error["code"] for error in errors], ["VALIDATION_FAILED"])

    def test_rollback_refuses_a_backup_outside_the_backup_directory(self):
        stray = Path(self._tmp.name) / "stray-backup.xlsx"
        stray.write_bytes(self.original_bytes)
        ok, result, errors, _ = self._mutation(str(stray), after_change=None)
        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), b"WPS saved this")
        self.assertFalse(result["rollback"]["performed"])
        self.assertEqual(errors[-1]["code"], ROLLBACK_FAILED)


if __name__ == "__main__":
    unittest.main()
