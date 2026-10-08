import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.sync_package_inspect import inspect_sync_package


class SyncPackageInspectTests(unittest.TestCase):
    def test_inspect_sync_package_reports_roots_hash_and_latest_artifacts(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for root in ("src", "tests", "config", "docs", "fixtures", "scripts"):
                (workspace / root).mkdir(parents=True)
                (workspace / root / f"{root}.txt").write_text(root, encoding="utf-8")
            safe_artifact = workspace / "artifacts" / "regression" / "safe" / "regression-run-safe.json"
            wps_artifact = workspace / "artifacts" / "regression" / "wps" / "regression-run-wps.json"
            parity_artifact = workspace / "artifacts" / "writer-structure-parity" / "writer-structure-parity-latest.json"
            nested_artifact = workspace / "artifacts" / "writer-nested-parity" / "writer-nested-parity-latest.json"
            safe_artifact.parent.mkdir(parents=True)
            wps_artifact.parent.mkdir(parents=True)
            parity_artifact.parent.mkdir(parents=True)
            nested_artifact.parent.mkdir(parents=True)
            safe_artifact.write_text("{}", encoding="utf-8")
            wps_artifact.write_text("{}", encoding="utf-8")
            parity_artifact.write_text("{}", encoding="utf-8")
            nested_artifact.write_text("{}", encoding="utf-8")
            package = workspace / "artifacts" / "cloud-sync" / "sync.zip"
            package.parent.mkdir(parents=True)
            with zipfile.ZipFile(package, "w") as archive:
                for file_path in [
                    *(workspace / root / f"{root}.txt" for root in ("src", "tests", "config", "docs", "fixtures", "scripts")),
                    safe_artifact,
                    wps_artifact,
                    parity_artifact,
                    nested_artifact,
                ]:
                    archive.write(file_path, file_path.relative_to(workspace).as_posix())

            ok, result, errors = inspect_sync_package(workspace=workspace, package_path=package)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["inspection_status"], "passed")
            self.assertEqual(result["entry_count"], 10)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertTrue(all(result["root_coverage"].values()))
            self.assertTrue(result["latest_artifacts"]["safe"]["included"])
            self.assertTrue(result["latest_artifacts"]["wps"]["included"])
            self.assertTrue(result["latest_artifacts"]["writer_parity"]["included"])
            self.assertTrue(result["latest_artifacts"]["writer_parity"]["content_matches"])
            self.assertTrue(result["latest_artifacts"]["writer_nested_parity"]["included"])
            self.assertTrue(result["latest_artifacts"]["writer_nested_parity"]["content_matches"])
            self.assertTrue(result["read_only"])
            self.assertFalse(result["deletion_performed"])
            self.assertFalse(result["launches_wps"])
            self.assertFalse(result["remote_git_required"])

    def test_inspect_sync_package_warns_when_package_missing(self):
        with TemporaryDirectory() as tmp:
            ok, result, errors = inspect_sync_package(workspace=tmp, package_path="missing.zip")

            self.assertFalse(ok)
            self.assertEqual(result["inspection_status"], "warning")
            self.assertFalse(result["exists"])
            self.assertEqual(errors[0]["code"], "SYNC_PACKAGE_MISSING")


if __name__ == "__main__":
    unittest.main()
