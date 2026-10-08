import hashlib
import json
import os
import time
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.sync_package_readiness import build_sync_package_readiness
from wps_ai_agent_cli.writer_structure_parity import IMPLEMENTATION_FILES


class SyncPackageReadinessTests(unittest.TestCase):
    def _ready_workspace(self, workspace: Path, parity_passed: bool = True) -> tuple[Path, Path]:
        entries = [
            "src/app.py", "tests/test_app.py", "config/settings.json", "docs/readme.md",
            "fixtures/sample.txt", "scripts/repro.ps1",
            "artifacts/regression/safe/regression-run-safe.json",
            "artifacts/regression/wps/regression-run-wps.json",
            "fixtures/phase3/writer_structure_wps_fixture.docx",
            "fixtures/phase3/writer_nested_scope_wps_fixture.docx",
            "scripts/audit_writer_structure_wps.ps1",
            *IMPLEMENTATION_FILES,
        ]
        for relative in entries:
            self._write_file(workspace, relative, relative)
        fixture_hash = hashlib.sha256((workspace / "fixtures/phase3/writer_structure_wps_fixture.docx").read_bytes()).hexdigest().upper()
        script_hash = hashlib.sha256((workspace / "scripts/audit_writer_structure_wps.ps1").read_bytes()).hexdigest().upper()
        implementation_hashes = {
            relative: hashlib.sha256((workspace / relative).read_bytes()).hexdigest().upper()
            for relative in IMPLEMENTATION_FILES
        }
        parity = workspace / "artifacts/writer-structure-parity/writer-structure-parity-latest.json"
        parity.parent.mkdir(parents=True)
        parity.write_text(json.dumps({
            "ok": parity_passed,
            "validation": {"status": "passed" if parity_passed else "failed"},
            "data": {"writer_structure_parity": {
                "parity_status": "passed" if parity_passed else "failed",
                "failed_count": 0 if parity_passed else 1,
                "wps_launched": True,
                "source_sha256": fixture_hash,
                "source_sha256_after": fixture_hash,
                "audit_script_sha256": script_hash,
                "implementation_sha256": implementation_hashes,
                "implementation_sha256_after": implementation_hashes,
                "checks": [
                    {"name": "source_unchanged", "passed": parity_passed},
                    {"name": "implementation_unchanged", "passed": parity_passed},
                ],
            }},
        }), encoding="utf-8")
        entries.append(str(parity.relative_to(workspace)).replace("\\", "/"))
        nested_fixture_hash = hashlib.sha256((workspace / "fixtures/phase3/writer_nested_scope_wps_fixture.docx").read_bytes()).hexdigest().upper()
        nested = workspace / "artifacts/writer-nested-parity/writer-nested-parity-latest.json"
        nested.parent.mkdir(parents=True)
        nested.write_text(json.dumps({
            "ok": True, "validation": {"status": "passed"},
            "data": {"writer_structure_parity": {
                "scope": "nested", "parity_status": "passed", "failed_count": 0,
                "wps_launched": True, "source_sha256": nested_fixture_hash,
                "source_sha256_after": nested_fixture_hash,
                "audit_script_sha256": script_hash,
                "implementation_sha256": implementation_hashes,
                "implementation_sha256_after": implementation_hashes,
                "checks": [
                    {"name": "read_only_open", "passed": True},
                    {"name": "bookmark_names_and_text", "passed": True},
                    {"name": "source_unchanged", "passed": True},
                    {"name": "implementation_unchanged", "passed": True},
                ],
            }},
        }), encoding="utf-8")
        entries.append(str(nested.relative_to(workspace)).replace("\\", "/"))
        return self._build_package(workspace, entries), parity

    def _write_file(self, workspace: Path, relative: str, content: str) -> Path:
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _build_package(self, workspace: Path, entries: list[str]) -> Path:
        package = workspace / "artifacts" / "cloud-sync" / "sync.zip"
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "w") as archive:
            for relative in entries:
                archive.write(workspace / relative, relative)
        return package

    def test_build_sync_package_readiness_passes_for_complete_package(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)

            ok, result, errors = build_sync_package_readiness(workspace=workspace, package_path=package)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["readiness_status"], "passed")
            self.assertEqual(result["package"]["entry_count"], 17)
            self.assertEqual(result["coverage"]["missing_entry_count"], 0)
            self.assertEqual(result["coverage"]["newer_than_package_count"], 0)
            self.assertTrue(result["latest_artifacts"]["safe"]["included"])
            self.assertTrue(result["latest_artifacts"]["wps"]["included"])
            self.assertEqual(result["writer_parity_evidence"]["status"], "passed")
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "passed")
            self.assertTrue(result["read_only"])
            self.assertFalse(result["deletion_performed"])
            self.assertFalse(result["launches_wps"])
            self.assertFalse(result["remote_git_required"])

            source = workspace / "src/app.py"
            stamp = source.stat().st_mtime
            source.write_text("changed content", encoding="utf-8")
            os.utime(source, (stamp, stamp))
            ok, result, errors = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["coverage"]["changed_entries"], ["src/app.py"])
            self.assertEqual(result["coverage"]["newer_than_package_count"], 0)

    def test_build_sync_package_readiness_warns_for_newer_workspace_file(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            time.sleep(0.02)
            newer_file = self._write_file(workspace, "docs/newer.md", "# newer")
            future = time.time() + 5
            os.utime(newer_file, (future, future))

            ok, result, errors = build_sync_package_readiness(workspace=workspace, package_path=package)

            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["readiness_status"], "warning")
            self.assertEqual(result["coverage"]["newer_than_package_count"], 1)
            self.assertIn("docs/newer.md", result["coverage"]["newer_than_package"])

    def test_missing_failed_stale_and_unpacked_parity_evidence(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, parity = self._ready_workspace(workspace)
            parity.unlink()
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "missing")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace, parity_passed=False)
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "failed")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            fixture = workspace / "fixtures/phase3/writer_structure_wps_fixture.docx"
            stamp = fixture.stat().st_mtime
            fixture.write_text("changed", encoding="utf-8")
            os.utime(fixture, (stamp, stamp))
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "stale")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            script = workspace / "scripts/audit_writer_structure_wps.ps1"
            script.write_text("changed script", encoding="utf-8")
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "stale")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, parity = self._ready_workspace(workspace)
            parity.write_text("not-json", encoding="utf-8")
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "failed")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, parity = self._ready_workspace(workspace)
            newer = parity.with_name("writer-structure-parity-newer.json")
            newer.write_bytes(parity.read_bytes())
            future = time.time() + 5
            os.utime(newer, (future, future))
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_parity_evidence"]["status"], "stale_package")

    def test_nested_parity_missing_stale_and_package_mismatch(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            nested = workspace / "artifacts/writer-nested-parity/writer-nested-parity-latest.json"
            nested.unlink()
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "missing")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            fixture = workspace / "fixtures/phase3/writer_nested_scope_wps_fixture.docx"
            fixture.write_text("changed", encoding="utf-8")
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "stale")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            nested = workspace / "artifacts/writer-nested-parity/writer-nested-parity-latest.json"
            payload = json.loads(nested.read_text(encoding="utf-8"))
            payload["data"]["writer_structure_parity"]["offline"] = {"altered": True}
            nested.write_text(json.dumps(payload), encoding="utf-8")
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "stale_package")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            nested = workspace / "artifacts/writer-nested-parity/writer-nested-parity-latest.json"
            payload = json.loads(nested.read_text(encoding="utf-8"))
            payload["data"]["writer_structure_parity"]["checks"] = [
                {"name": "source_unchanged", "passed": True},
            ]
            nested.write_text(json.dumps(payload), encoding="utf-8")
            ok, result, _ = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "failed")

    def test_parser_code_change_stales_both_parity_reports_without_mtime_change(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package, _ = self._ready_workspace(workspace)
            parser = workspace / IMPLEMENTATION_FILES[0]
            stamp = parser.stat().st_mtime
            parser.write_text("changed parser", encoding="utf-8")
            os.utime(parser, (stamp, stamp))
            ok, result, errors = build_sync_package_readiness(workspace, package)
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["writer_parity_evidence"]["status"], "stale")
            self.assertEqual(result["writer_nested_parity_evidence"]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
