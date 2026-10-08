import shutil
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from wps_ai_agent_cli.cloud_sync import build_cloud_sync_package
from wps_ai_agent_cli.recovery_drill_evidence import verify_recovery_drill_package
from wps_ai_agent_cli.sessions import file_identity


POWERSHELL_AVAILABLE = bool(shutil.which("pwsh") or shutil.which("powershell"))


@unittest.skipUnless(POWERSHELL_AVAILABLE, "cloud sync packaging requires PowerShell")
class CloudSyncTests(unittest.TestCase):
    def test_recovery_drill_artifacts_are_verified_in_package(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "src").mkdir()
            (workspace / "src" / "sample.txt").write_text("source", encoding="utf-8")
            root = workspace / "artifacts" / "recovery-drill" / "p3-181-final"
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
            package = workspace / "artifacts" / "cloud-sync" / "test-sync.zip"
            ok, result, errors = build_cloud_sync_package(package, workspace)
            self.assertTrue(ok, errors)
            self.assertEqual(result["recovery_drill_package"]["status"], "passed")
            self.assertEqual(len(result["recovery_drill_package"]["entries"]), 6)
            self.assertEqual(verify_recovery_drill_package(workspace, package)["status"], "passed")
            original_package = package.read_bytes()
            (root / "writer" / "current.docx").write_bytes(b"altered")
            ok, _, errors = build_cloud_sync_package(package, workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "RECOVERY_DRILL_EVIDENCE_INVALID")
            self.assertEqual(package.read_bytes(), original_package)

    def test_build_cloud_sync_package_creates_zip_and_hash(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for root in ("src", "tests", "config", "docs", "fixtures", "scripts"):
                (workspace / root).mkdir()
                (workspace / root / f"{root}.txt").write_text(root, encoding="utf-8")
            parity = workspace / "artifacts/writer-structure-parity/writer-structure-parity-latest.json"
            parity.parent.mkdir(parents=True)
            parity.write_text("{}", encoding="utf-8")
            nested = workspace / "artifacts/writer-nested-parity/writer-nested-parity-latest.json"
            nested.parent.mkdir(parents=True)
            nested.write_text("{}", encoding="utf-8")

            ok, result, errors = build_cloud_sync_package(
                output_path="artifacts/cloud-sync/test-sync.zip",
                workspace=workspace,
                include_latest_artifacts=False,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertTrue(Path(result["output_path"]).exists())
            self.assertGreaterEqual(result["entry_count"], 6)
            self.assertIn("scripts", result["include_roots"])
            self.assertEqual(result["included_artifacts"], [])
            ok, result, errors = build_cloud_sync_package(
                output_path="artifacts/cloud-sync/test-sync.zip",
                workspace=workspace,
                include_latest_artifacts=True,
            )
            self.assertTrue(ok, errors)
            self.assertIn(str(parity), result["included_artifacts"])
            self.assertIn(str(nested), result["included_artifacts"])
            with ZipFile(result["output_path"]) as archive:
                self.assertIn("artifacts/writer-structure-parity/writer-structure-parity-latest.json",
                              {name.replace("\\", "/") for name in archive.namelist()})
                self.assertIn("artifacts/writer-nested-parity/writer-nested-parity-latest.json",
                              {name.replace("\\", "/") for name in archive.namelist()})
            self.assertEqual(len(result["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
