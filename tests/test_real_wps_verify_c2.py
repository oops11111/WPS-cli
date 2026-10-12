import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_wps_preopen_guard import FAKE_SPREADSHEET_PRELUDE
from tests.test_wps_quit_guard import CAPABILITIES
from wps_ai_agent_cli import spreadsheet_ops
from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")
KIT = Path(__file__).resolve().parent.parent / "scripts" / "real_wps_verify_c2"


def load_driver():
    spec = importlib.util.spec_from_file_location("c2_post_open_driver", KIT / "c2_post_open_driver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DriverPatchTests(unittest.TestCase):
    def test_patch_blinds_both_checks_and_traces_after_open(self):
        patched = load_driver().patch_guard(PRE_OPEN_GUARD)
        self.assertIn("function Test-WpsPathOpen($collection, [string]$path) {\n  return $false", patched)
        self.assertIn("function Find-WpsOpenDocument($collection, [string]$path) {\n  return $null", patched)
        self.assertLess(patched.index("$opened = $collection.Open("), patched.index("C2_TRACE_FILE"))
        self.assertLess(patched.index("C2_TRACE_FILE"), patched.index("if ([int]$collection.Count -le $countBefore) {\n    # Nothing new"))
        self.assertEqual(patched.replace("\r\n", "\n").count("function Open-WpsDocument"), 1)

    def test_patch_refuses_to_run_when_the_guard_text_changed(self):
        with self.assertRaises(SystemExit):
            load_driver().patch_guard(PRE_OPEN_GUARD.replace("function Find-WpsOpenDocument", "function Find-Renamed"))

    def test_merged_guard_has_no_test_hook(self):
        self.assertNotIn("C2_TRACE_FILE", PRE_OPEN_GUARD)


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts against a fake COM object")
class InjectedPostOpenBranchTests(unittest.TestCase):
    """The driver's injection must reach the branch after Open() with the merged guard, offline against fake COM."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.document = self.dir / "book.xlsx"
        self.document.write_bytes(b"x")
        self.log = self.dir / "fake.log"
        self.log.write_text("", encoding="utf-8")
        self.trace = self.dir / "trace.jsonl"
        real_run = spreadsheet_ops.run_powershell_script

        def run_with_fake(script, *args, **kwargs):
            return real_run(FAKE_SPREADSHEET_PRELUDE + script, *args, **kwargs)

        for patcher in (
            patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH),
            patch.object(spreadsheet_ops, "probe_wps_capabilities", return_value=CAPABILITIES),
            patch.object(spreadsheet_ops, "run_powershell_script", side_effect=run_with_fake),
            patch.dict(os.environ, {"WPSFAKE_PATH": str(self.document), "WPSFAKE_LOG": str(self.log)}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def log_lines(self):
        return self.log.read_text(encoding="utf-8").split()

    def write(self, injected, **env):
        guard = load_driver().patch_guard(PRE_OPEN_GUARD) if injected else PRE_OPEN_GUARD
        with patch.object(spreadsheet_ops, "PRE_OPEN_GUARD", guard), patch.dict(
            os.environ, {"C2_TRACE_FILE": str(self.trace), **env}
        ):
            return spreadsheet_ops._run_spreadsheet_write_com(str(self.document), None, "A1", [[1]])

    def trace_rows(self):
        if not self.trace.exists():
            return []
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

    def test_without_the_injection_the_recheck_stops_before_open_is_called(self):
        result = self.write(False, WPSFAKE_OPEN="1", WPSFAKE_SAVED="0", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH="1")
        self.assertFalse(result["ok"], result)
        self.assertIn("unsaved changes", str(result))
        self.assertEqual([line for line in self.log_lines() if line.startswith("open:")], [])

    def test_dirty_workbook_is_refused_after_open_with_count_unchanged_and_no_edit(self):
        result = self.write(True, WPSFAKE_OPEN="1", WPSFAKE_SAVED="0", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH="1")
        self.assertFalse(result["ok"], result)
        self.assertIn("between the check and the open call", str(result))
        lines = self.log_lines()
        self.assertEqual(len([line for line in lines if line.startswith("open:")]), 1)
        self.assertFalse([line for line in lines if line in ("save", "close", "delete")], lines)
        rows = self.trace_rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["event"], "open_returned")
        self.assertEqual(rows[0]["count_before"], rows[0]["count_after"])
        self.assertTrue(rows[0]["returned_saved"])

    def test_clean_workbook_is_refused_too(self):
        result = self.write(True, WPSFAKE_OPEN="1", WPSFAKE_SAVED="1", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH="1")
        self.assertFalse(result["ok"], result)
        self.assertIn("between the check and the open call", str(result))
        self.assertFalse([line for line in self.log_lines() if line in ("save", "close")])

    def test_trace_is_not_written_when_the_variable_is_unset(self):
        guard = load_driver().patch_guard(PRE_OPEN_GUARD)
        env = {k: v for k, v in os.environ.items() if k != "C2_TRACE_FILE"}
        env.update(WPSFAKE_OPEN="1", WPSFAKE_SAVED="0", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH="1")
        with patch.object(spreadsheet_ops, "PRE_OPEN_GUARD", guard), patch.dict(os.environ, env, clear=True):
            result = spreadsheet_ops._run_spreadsheet_write_com(str(self.document), None, "A1", [[1]])
        self.assertFalse(result["ok"], result)
        self.assertFalse(self.trace.exists())


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
            for name in ("c2-post-open.ps1", "lib.ps1"):
                with self.subTest(script=name):
                    done = subprocess.run(
                        [PWSH, "-NoProfile", "-File", str(checker), str(KIT / name)],
                        capture_output=True, text=True, timeout=60,
                    )
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class FixtureTests(unittest.TestCase):
    def test_fixture_script_writes_the_two_scratch_workbooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run(
                [sys.executable, str(KIT / "make_c2_fixtures.py"), tmp], capture_output=True, text=True, timeout=60
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["c2_clean.xlsx", "c2_dirty.xlsx"])


if __name__ == "__main__":
    unittest.main()
