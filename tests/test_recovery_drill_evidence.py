import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from wps_ai_agent_cli.recovery_drill_evidence import verify_recovery_drill_artifacts, verify_recovery_drill_package
from wps_ai_agent_cli.sessions import file_identity


class RecoveryDrillEvidenceTests(unittest.TestCase):
    def _fixture(self, workspace):
        root = Path(workspace) / "artifacts" / "recovery-drill" / "p3-181-final"
        for component, suffix in (("writer", ".docx"), ("spreadsheets", ".xlsx")):
            directory = root / component
            directory.mkdir(parents=True)
            current = directory / f"current{suffix}"
            backup = directory / f"backup{suffix}"
            current.write_bytes(f"{component}-current".encode())
            backup.write_bytes(f"{component}-backup".encode())
            (directory / "manifest.json").write_text(json.dumps({
                "component": component,
                "status": "ambiguous",
                "main_operation_recorded": False,
                "current_path": str(current.relative_to(workspace)),
                "backup_path": str(backup.relative_to(workspace)),
                "current_sha256": file_identity(current)["source_sha256"],
                "backup_sha256": file_identity(backup)["source_sha256"],
            }), encoding="utf-8")
        return root

    def test_absent_evidence_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(verify_recovery_drill_artifacts(tmp)["status"], "absent")

    def test_valid_and_tampered_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(Path(tmp))
            self.assertEqual(verify_recovery_drill_artifacts(tmp)["status"], "passed")
            (root / "writer" / "current.docx").write_bytes(b"altered")
            report = verify_recovery_drill_artifacts(tmp)
            self.assertEqual(report["status"], "failed")
            self.assertIn("CURRENT_HASH_MISMATCH", report["components"][0]["errors"])

    def test_missing_or_redirected_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(Path(tmp))
            writer_manifest = root / "writer" / "manifest.json"
            writer_manifest.unlink()
            self.assertIn("MANIFEST_UNAVAILABLE", verify_recovery_drill_artifacts(tmp)["components"][0]["errors"])
            manifest = json.loads((root / "spreadsheets" / "manifest.json").read_text(encoding="utf-8"))
            manifest["current_path"] = str(Path(tmp) / "outside.xlsx")
            (root / "spreadsheets" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertIn("CURRENT_PATH_INVALID", verify_recovery_drill_artifacts(tmp)["components"][1]["errors"])

    def test_non_object_manifest_fails_with_bounded_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(Path(tmp))
            (root / "writer" / "manifest.json").write_text("[]", encoding="utf-8")
            report = verify_recovery_drill_artifacts(tmp)
            self.assertEqual(report["status"], "failed")
            self.assertIn("MANIFEST_INVALID", report["components"][0]["errors"])

    def test_package_duplicate_entry_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = self._fixture(workspace)
            package = workspace / "package.zip"
            files = [item for item in root.rglob("*") if item.is_file()]
            with ZipFile(package, "w") as archive:
                for item in files:
                    archive.write(item, item.relative_to(workspace).as_posix())
            self.assertEqual(verify_recovery_drill_package(workspace, package)["status"], "passed")
            with ZipFile(package, "a") as archive:
                archive.writestr(files[0].relative_to(workspace).as_posix(), b"tampered")
            self.assertEqual(verify_recovery_drill_package(workspace, package)["status"], "failed")

    def test_evidence_verifies_after_extraction_to_another_root(self):
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as target_tmp:
            source = Path(source_tmp)
            root = self._fixture(source)
            package = source / "package.zip"
            with ZipFile(package, "w") as archive:
                for item in root.rglob("*"):
                    if item.is_file():
                        archive.write(item, item.relative_to(source).as_posix())
            with ZipFile(package) as archive:
                archive.extractall(target_tmp)
            report = verify_recovery_drill_artifacts(target_tmp)
            self.assertEqual(report["status"], "passed")
            self.assertTrue(all(item["status"] == "passed" for item in report["components"]))


if __name__ == "__main__":
    unittest.main()
