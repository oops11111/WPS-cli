import os
import time
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.sync_package_coverage import build_sync_package_coverage


class SyncPackageCoverageTests(unittest.TestCase):
    def test_content_changes_cannot_hide_behind_preserved_timestamps(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "src/app.py"
            source.parent.mkdir()
            source.write_bytes(b"old")
            stamp = source.stat().st_mtime
            package = workspace / "sync.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.write(source, "src\\app.py")
            source.write_bytes(b"new")
            os.utime(source, (stamp, stamp))
            before = package.read_bytes()
            ok, result, errors = build_sync_package_coverage(workspace, package, limit=0)
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["changed_entry_count"], 1)
            self.assertEqual(result["changed_entries"], [])
            self.assertTrue(result["truncated"]["changed_entries"])
            self.assertEqual(result["newer_than_package_count"], 0)
            self.assertEqual(package.read_bytes(), before)
            self.assertEqual(source.read_bytes(), b"new")

    def test_obsolete_and_duplicate_entries_fail_coverage(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "src/app.py"
            source.parent.mkdir()
            source.write_bytes(b"same")
            package = workspace / "sync.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.write(source, "src/app.py")
                archive.write(source, "src\\app.py")
                archive.writestr("src/removed.py", "obsolete")
            ok, result, errors = build_sync_package_coverage(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["extra_root_entries"], ["src/removed.py"])
            self.assertEqual(result["duplicate_entries"], ["src/app.py"])
            self.assertEqual(result["changed_entry_count"], 0)

    def test_build_sync_package_coverage_reports_full_root_coverage(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            files = {
                "src/app.py": "print('ok')",
                "tests/test_app.py": "def test_ok(): pass",
                "config/settings.json": "{}",
                "docs/readme.md": "# docs",
                "fixtures/sample.txt": "fixture",
            }
            for relative, content in files.items():
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            package = workspace / "artifacts" / "cloud-sync" / "sync.zip"
            package.parent.mkdir(parents=True)
            with zipfile.ZipFile(package, "w") as archive:
                for relative in files:
                    archive.write(workspace / relative, relative)

            ok, result, errors = build_sync_package_coverage(workspace=workspace, package_path=package)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["coverage_status"], "passed")
            self.assertEqual(result["expected_entry_count"], 5)
            self.assertEqual(result["missing_entry_count"], 0)
            self.assertTrue(all(item["expected"] == item["packaged"] for item in result["root_coverage"].values()))
            self.assertTrue(result["read_only"])
            self.assertFalse(result["deletion_performed"])
            self.assertFalse(result["launches_wps"])
            self.assertFalse(result["remote_git_required"])

    def test_build_sync_package_coverage_reports_newer_files_without_failing(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            src_file = workspace / "src" / "app.py"
            docs_file = workspace / "docs" / "new.md"
            src_file.parent.mkdir(parents=True)
            docs_file.parent.mkdir(parents=True)
            src_file.write_text("print('ok')", encoding="utf-8")
            package = workspace / "sync.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.write(src_file, "src/app.py")
            time.sleep(0.02)
            docs_file.write_text("# new", encoding="utf-8")
            future = time.time() + 5
            os.utime(docs_file, (future, future))

            ok, result, errors = build_sync_package_coverage(workspace=workspace, package_path=package)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["newer_than_package_count"], 1)
            self.assertIn("docs/new.md", result["newer_than_package"])
            self.assertEqual(result["missing_entry_count"], 0)


if __name__ == "__main__":
    unittest.main()
