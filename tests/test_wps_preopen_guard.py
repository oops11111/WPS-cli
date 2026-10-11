import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_wps_quit_guard import CAPABILITIES, capture_scripts
from wps_ai_agent_cli import presentation_ops, spreadsheet_inspect, spreadsheet_ops, writer_ops
from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")


def mutating_cases(path):
    return [
        ("writer_replace", writer_ops, lambda: writer_ops._run_writer_replace_com(path, "a", "b")),
        ("writer_bookmark", writer_ops, lambda: writer_ops._run_writer_bookmark_fill_com(path, "n", "v", "old")),
        ("writer_table", writer_ops, lambda: writer_ops._run_writer_table_write_com(path, 1, 1, 1, "t")),
        ("presentation_replace", presentation_ops, lambda: presentation_ops._run_presentation_replace_com(path, "a", "b")),
        ("sheet_rename", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_rename_sheet_com(path, "a", "b")),
        ("sheet_create", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_create_sheet_com(path, "n", 1)),
        ("sheet_visibility", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_visibility_com(path, "n", True)),
        ("sheet_delete", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_delete_sheet_com(path, "n")),
        ("sheet_copy", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_copy_sheet_com(path, "a", "b", 1)),
        ("sheet_tab_color", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_tab_color_com(path, "n", "FF0000")),
        ("sheet_write", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_write_com(path, None, "A1", [[1]])),
        ("sheet_formula_write", spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_formula_write_com(path, None, "A1", [["=1"]])),
    ]


def all_scripts(path):
    scripts = {}
    for name, module, call in mutating_cases(path):
        captured = capture_scripts(module, call)
        assert len(captured) == 1, name
        scripts[name] = (captured[0], True)
    return scripts


class PreOpenGuardStaticTests(unittest.TestCase):
    def test_every_file_based_script_only_closes_documents_it_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "input.xlsx")
            Path(path).write_bytes(b"x")
            scripts = all_scripts(path)
        for name, (script, _) in scripts.items():
            with self.subTest(script=name):
                self.assertIn("function Test-WpsPathOpen", script)
                self.assertEqual(script.count("Test-WpsPathOpen $app."), 1)
                self.assertEqual(script.count("Assert-WpsPreOpenSaved $wpsPreOpen"), 1)
                closes = script.count(".Close(")
                self.assertGreaterEqual(closes, 1)
                self.assertEqual(script.count("if (-not $wpsPreOpen) {"), closes)
                self.assertLess(script.index("Test-WpsPathOpen $app."), script.index(".Open($params.path"))
                self.assertLess(script.index(".Open($params.path"), script.index("Assert-WpsPreOpenSaved $wpsPreOpen"))

    def test_read_only_inspect_script_does_not_close_user_workbooks(self):
        source = Path(spreadsheet_inspect.__file__).read_text(encoding="utf-8")
        self.assertIn("Test-WpsPathOpen $app.Workbooks", source)
        self.assertEqual(source.count(".Close($false)"), source.count("if (-not $wpsPreOpen) {{ try {{ $workbook.Close($false)"))

    def test_guard_text_is_embedded_verbatim(self):
        self.assertIn("function Assert-WpsPreOpenSaved", PRE_OPEN_GUARD)
        self.assertNotIn(".Close(", PRE_OPEN_GUARD)


FAKE_SPREADSHEET_PRELUDE = r'''
$global:fakeSheet = [pscustomobject]@{ Name = 'S' }
$global:fakeSheet | Add-Member -MemberType ScriptMethod -Name Delete -Value { Add-Content -LiteralPath $env:WPSFAKE_LOG -Value 'delete' }
$global:fakeSheets = [pscustomobject]@{ Count = 1 }
$global:fakeSheets | Add-Member -MemberType ScriptMethod -Name Item -Value { param($key) return $global:fakeSheet }
$global:fakeBooks = [pscustomobject]@{ Count = $(if ($env:WPSFAKE_OPEN -eq '1') { 1 } else { 0 }) }
$global:fakeBook = [pscustomobject]@{ FullName = $env:WPSFAKE_PATH; Saved = ($env:WPSFAKE_SAVED -ne '0'); Worksheets = $global:fakeSheets }
$global:fakeBook | Add-Member -MemberType ScriptMethod -Name Save -Value { Add-Content -LiteralPath $env:WPSFAKE_LOG -Value 'save' }
$global:fakeBook | Add-Member -MemberType ScriptMethod -Name Close -Value { param($save) Add-Content -LiteralPath $env:WPSFAKE_LOG -Value 'close'; $global:fakeBooks.Count = 0 }
$global:fakeBooks | Add-Member -MemberType ScriptMethod -Name Item -Value { param($i) return $global:fakeBook }
$global:fakeBooks | Add-Member -MemberType ScriptMethod -Name Open -Value { param($p) $global:fakeBooks.Count = 1; return $global:fakeBook }
$global:fakeApp = [pscustomobject]@{ Workbooks = $global:fakeBooks; Visible = $true; DisplayAlerts = $true; Documents = $null; Presentations = $null }
$global:fakeApp | Add-Member -MemberType ScriptMethod -Name Quit -Value { Add-Content -LiteralPath $env:WPSFAKE_LOG -Value 'quit' }
function New-Object { param([string]$ComObject) return $global:fakeApp }
'''


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts against a fake COM object")
class PreOpenGuardBehaviourTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.document = self.dir / "book.xlsx"
        self.document.write_bytes(b"x")
        self.log = self.dir / "fake.log"
        self.log.write_text("", encoding="utf-8")
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

    def events(self):
        return self.log.read_text(encoding="utf-8").split()

    def delete_sheet(self, **env):
        with patch.dict(os.environ, env):
            return spreadsheet_ops._run_spreadsheet_delete_sheet_com(str(self.document), "S")

    def test_document_already_open_in_wps_is_not_closed(self):
        result = self.delete_sheet(WPSFAKE_OPEN="1", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save"])

    def test_document_opened_by_the_script_is_still_closed(self):
        result = self.delete_sheet(WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save", "close", "quit"])

    def test_open_document_with_unsaved_changes_is_refused_untouched(self):
        result = self.delete_sheet(WPSFAKE_OPEN="1", WPSFAKE_SAVED="0")
        self.assertFalse(result["ok"], result)
        self.assertIn("unsaved changes", str(result))
        self.assertEqual(self.events(), [])


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to syntax-check the generated scripts")
class GeneratedScriptSyntaxTests(unittest.TestCase):
    def test_every_generated_script_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "input.xlsx")
            Path(path).write_bytes(b"x")
            scripts = all_scripts(path)
            texts = {name: script for name, (script, _) in scripts.items()}
            checker = Path(tmp) / "check.ps1"
            checker.write_text(
                "param($File)\n$errors = $null; $tokens = $null\n"
                "[void][System.Management.Automation.Language.Parser]::ParseFile($File, [ref]$tokens, [ref]$errors)\n"
                "if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 }\n",
                encoding="utf-8",
            )
            for name, text in texts.items():
                target = Path(tmp) / f"{name}.ps1"
                target.write_text(text, encoding="utf-8-sig")
                completed = subprocess.run(
                    [PWSH, "-NoProfile", "-File", str(checker), str(target)],
                    capture_output=True, text=True, timeout=60,
                )
                with self.subTest(script=name):
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
