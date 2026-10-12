"""Offline checks for scripts/real_wps_verify_remaining/ (no real WPS required)."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")
KIT = Path(__file__).resolve().parent.parent / "scripts" / "real_wps_verify_remaining"
PS1_SCRIPTS = (
    "1-inspect-fileshare-read.ps1",
    "2-writer-wpp-lock.ps1",
    "3-displayalerts.ps1",
    "4-concurrency-window.ps1",
    "5-other-holder.ps1",
    "lib.ps1",
)
FIXTURE_NAMES = (
    "r1_inspect_free.xlsx",
    "r1_inspect_hold.xlsx",
    "r1_inspect_wps.xlsx",
    "r2_writer_clean.docx",
    "r2_writer_hold.docx",
    "r2_wpp_clean.pptx",
    "r2_wpp_hold.pptx",
    "r3_alerts.xlsx",
    "r4_race.xlsx",
    "r5_other_free.xlsx",
    "r5_other_hold.xlsx",
)


def load_inject_driver():
    spec = importlib.util.spec_from_file_location("remaining_inject_driver", KIT / "inject_driver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InjectDriverPatchTests(unittest.TestCase):
    def test_patch_blinds_path_checks(self):
        patched = load_inject_driver().patch_guard(PRE_OPEN_GUARD)
        self.assertIn("function Test-WpsPathOpen($collection, [string]$path) {\n  return $false", patched)
        self.assertIn("function Find-WpsOpenDocument($collection, [string]$path) {\n  return $null", patched)
        self.assertIn("C2_TRACE_FILE", patched)
        self.assertLess(patched.index("$opened = $collection.Open("), patched.index("C2_TRACE_FILE"))

    def test_patch_refuses_when_guard_markers_change(self):
        with self.assertRaises(SystemExit):
            load_inject_driver().patch_guard(
                PRE_OPEN_GUARD.replace("function Find-WpsOpenDocument", "function Find-Renamed")
            )

    def test_production_guard_has_no_test_hook(self):
        self.assertNotIn("C2_TRACE_FILE", PRE_OPEN_GUARD)


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to syntax-check the scripts")
class ScriptSyntaxTests(unittest.TestCase):
    def test_powershell_scripts_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            checker = Path(tmp) / "check.ps1"
            checker.write_text(
                "param($p)\n$e = $null\n[void][System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$null, [ref]$e)\n"
                "if ($e.Count) { $e | ForEach-Object { $_.ToString() }; exit 1 }\n",
                encoding="utf-8",
            )
            for name in PS1_SCRIPTS:
                with self.subTest(script=name):
                    done = subprocess.run(
                        [PWSH, "-NoProfile", "-File", str(checker), str(KIT / name)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class KitScriptTextTests(unittest.TestCase):
    def test_lib_retries_file_hold_and_sha(self):
        text = (KIT / "lib.ps1").read_text(encoding="utf-8")
        self.assertIn("function Open-FileHold", text)
        self.assertIn("Open-FileHold waiting for share", text)
        self.assertIn("function Get-Sha", text)
        self.assertIn("[System.IO.FileShare]::ReadWrite", text)
        self.assertIn("Start-Sleep -Milliseconds 400", text)
        self.assertIn("Start-Sleep -Milliseconds 500", text)

    def test_other_holder_uses_separate_free_fixture_and_records_gaps(self):
        text = (KIT / "5-other-holder.ps1").read_text(encoding="utf-8")
        self.assertIn("r5_other_free.xlsx", text)
        self.assertIn("r5_other_hold.xlsx", text)
        self.assertIn("DOCUMENT_IDENTITY_UNAVAILABLE", text)
        self.assertIn("PermissionError", text)
        self.assertIn("inspect_exclusive_hold_product_gap", text)
        self.assertIn("write_exclusive_hold_product_gap", text)
        self.assertIn("Open-FileHold", text)

    def test_inspect_script_covers_fileshare_cases(self):
        text = (KIT / "1-inspect-fileshare-read.ps1").read_text(encoding="utf-8")
        self.assertIn("FileShare.Read", text)
        self.assertIn("inject_driver.py", text)
        self.assertIn("Open() was not called", text)

    def test_concurrency_default_is_documented_exempt(self):
        text = (KIT / "4-concurrency-window.ps1").read_text(encoding="utf-8")
        self.assertIn("EXEMPT", text)
        self.assertIn("'document'", text)
        self.assertIn("'stress'", text)

    def test_kit_ships_readme_and_results_summary(self):
        readme = (KIT / "README.md").read_text(encoding="utf-8")
        results = (KIT / "RESULTS-973590b.md").read_text(encoding="utf-8")
        self.assertIn("973590b", readme)
        self.assertIn("Product gaps", readme)
        self.assertIn("973590b", results)
        self.assertIn("ZipFile", results)


class FixtureTests(unittest.TestCase):
    def test_fixture_script_writes_expected_scratch_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run(
                [sys.executable, str(KIT / "make_fixtures.py"), tmp],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), sorted(FIXTURE_NAMES))


if __name__ == "__main__":
    unittest.main()
