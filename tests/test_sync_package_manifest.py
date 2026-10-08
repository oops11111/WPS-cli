import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.sync_package_manifest import build_sync_package_manifest


class SyncPackageManifestTests(unittest.TestCase):
    def test_build_sync_package_manifest_filters_prefix_and_limits_entries(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package = workspace / "artifacts" / "cloud-sync" / "sync.zip"
            package.parent.mkdir(parents=True)
            files = {
                "src/app.py": "print('ok')",
                "src/lib.py": "VALUE = 1",
                "tests/test_app.py": "def test_ok(): pass",
                "config/settings.json": "{}",
                "docs/readme.md": "# docs",
                "fixtures/sample.txt": "fixture",
                "scripts/repro.ps1": "Write-Output 'ok'",
            }
            for relative, content in files.items():
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            with zipfile.ZipFile(package, "w") as archive:
                for relative in files:
                    archive.write(workspace / relative, relative)

            ok, result, errors = build_sync_package_manifest(
                workspace=workspace,
                package_path=package,
                prefix="src",
                limit=1,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["manifest_status"], "passed")
            self.assertEqual(result["entry_count"], 7)
            self.assertEqual(result["match_count"], 2)
            self.assertEqual(result["returned_count"], 1)
            self.assertTrue(result["truncated"])
            self.assertEqual(result["entries"][0]["top_level"], "src")
            self.assertTrue(all(result["expected_roots_present"].values()))
            self.assertTrue(result["read_only"])
            self.assertFalse(result["deletion_performed"])
            self.assertFalse(result["launches_wps"])
            self.assertFalse(result["remote_git_required"])

    def test_build_sync_package_manifest_warns_when_prefix_has_no_matches(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package = workspace / "sync.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("src/app.py", "print('ok')")

            ok, result, errors = build_sync_package_manifest(
                workspace=workspace,
                package_path=package,
                prefix="docs",
            )

            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["manifest_status"], "warning")
            self.assertEqual(result["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
