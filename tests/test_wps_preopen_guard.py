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
                closes = script.count(".Close(")
                self.assertGreaterEqual(closes, 1)
                self.assertEqual(script.count("if (-not $wpsPreOpen) {"), closes)
                open_call = (
                    ".Open((ConvertTo-WpsLocalPath $params.path)"
                    if name == "presentation_replace"
                    else "Open-WpsDocument $app."
                )
                self.assertEqual(script.count(open_call), 1)
                self.assertNotIn(".Open($params.path", script)
                self.assertLess(script.index("Test-WpsPathOpen $app."), script.index(open_call))
                if name == "presentation_replace":
                    self.assertEqual(script.count("Assert-WpsPresentationNotOpen $wpsPreOpen"), 1)
                    self.assertNotIn("Assert-WpsPreOpenSaved $wpsPreOpen", script)
                    self.assertLess(script.index("Assert-WpsPresentationNotOpen $wpsPreOpen"), script.index(open_call))
                else:
                    self.assertEqual(script.count("Assert-WpsPreOpenSaved $wpsPreOpen"), 1)
                    self.assertLess(script.index(open_call), script.index("Assert-WpsPreOpenSaved $wpsPreOpen"))

    def test_read_only_inspect_script_does_not_close_user_workbooks(self):
        source = Path(spreadsheet_inspect.__file__).read_text(encoding="utf-8")
        self.assertIn("Test-WpsPathOpen $app.Workbooks", source)
        self.assertEqual(source.count(".Close($false)"), source.count("if (-not $wpsPreOpen) {{ try {{ $workbook.Close($false)"))

    def test_guard_text_is_embedded_verbatim(self):
        self.assertIn("function Assert-WpsPreOpenSaved", PRE_OPEN_GUARD)
        self.assertNotIn(".Close(", PRE_OPEN_GUARD)


FAKE_SPREADSHEET_PRELUDE = r'''
Add-Type -TypeDefinition 'namespace WpsAgent { public static class Running { public static object Instance; public static object Get(string progId) { return Instance; } } }'
function Write-FakeLog([string]$line) { Add-Content -LiteralPath $env:WPSFAKE_LOG -Value $line }
function New-FakeApp([string]$label, [bool]$open, [bool]$saved) {
  $sheet = [pscustomobject]@{ Name = 'S' }
  $sheet | Add-Member -MemberType ScriptMethod -Name Delete -Value { Write-FakeLog 'delete' }
  $sheets = [pscustomobject]@{ Count = 1; Sheet = $sheet }
  $sheets | Add-Member -MemberType ScriptMethod -Name Item -Value { param($key) return $this.Sheet }
  $books = [pscustomobject]@{ Count = $(if ($open) { 1 } else { 0 }); Book = $null; Other = $null }
  $book = [pscustomobject]@{ FullName = $env:WPSFAKE_PATH; Saved = $saved; Worksheets = $sheets; Books = $books }
  $book | Add-Member -MemberType ScriptMethod -Name Save -Value { Write-FakeLog 'save' }
  $book | Add-Member -MemberType ScriptMethod -Name Close -Value { param($save) Write-FakeLog 'close'; $this.Books.Count = 0 }
  $books.Book = $book
  $other = [pscustomobject]@{ FullName = $env:WPSFAKE_PATH; Saved = $true; Worksheets = $sheets; Books = $books }
  $other | Add-Member -MemberType ScriptMethod -Name Save -Value { Write-FakeLog 'save' }
  $other | Add-Member -MemberType ScriptMethod -Name Close -Value { param($save) Write-FakeLog 'close' }
  $books.Other = $other
  $books | Add-Member -MemberType ScriptMethod -Name Item -Value { param($i) return $this.Book }
  $books | Add-Member -MemberType ScriptMethod -Name Open -Value {
    param($p)
    Write-FakeLog ('open:' + $p)
    # WPS hands back a second, clean-looking object when an already open workbook is opened again.
    if ($env:WPSFAKE_OPEN_OTHER -eq '1' -and $this.Count -gt 0) { return $this.Other }
    $this.Count = 1
    return $this.Book
  }
  $app = [pscustomobject]@{ Workbooks = $books; Documents = $null; Presentations = $null; Label = $label; v = $true; a = $true; e = $true; l = $true }
  foreach ($pair in @(@('Visible', 'v', 'visible'), @('DisplayAlerts', 'a', 'alerts'), @('EnableEvents', 'e', 'events'), @('AskToUpdateLinks', 'l', 'links'))) {
    $field = $pair[1]; $tag = $pair[2]
    $app | Add-Member -MemberType ScriptProperty -Name $pair[0] `
      -Value ([scriptblock]::Create('$this.' + $field)) `
      -SecondValue ([scriptblock]::Create('param($value) $this.' + $field + ' = $value; Write-FakeLog ("' + $tag + '=" + $value + ":" + $this.Label)'))
  }
  $app | Add-Member -MemberType ScriptMethod -Name Quit -Value { Write-FakeLog ('quit:' + $this.Label) }
  return $app
}
$global:fakeLaunched = New-FakeApp 'new' ($env:WPSFAKE_OPEN -eq '1' -and $env:WPSFAKE_ATTACH -ne '1') ($env:WPSFAKE_SAVED -ne '0')
$global:fakeAttached = New-FakeApp 'attached' ($env:WPSFAKE_OPEN -eq '1' -and $env:WPSFAKE_ATTACH -eq '1') ($env:WPSFAKE_SAVED -ne '0')
if ($env:WPSFAKE_ATTACH -eq '1') { [WpsAgent.Running]::Instance = $global:fakeAttached }
function New-Object { param([string]$ComObject) Write-FakeLog 'new-object'; return $global:fakeLaunched }
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

    def log_lines(self):
        return self.log.read_text(encoding="utf-8").split()

    def events(self):
        return [
            line for line in self.log_lines()
            if not line.startswith(("visible=", "alerts=", "events=", "links=", "new-object", "open"))
        ]

    def settings(self):
        return [line for line in self.log_lines() if line.startswith(("visible=", "alerts=", "events=", "links="))]

    def open_calls(self):
        return [line for line in self.log_lines() if line.startswith("open:")]

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
        self.assertEqual(self.events(), ["delete", "save", "close", "quit:new"])

    def test_open_document_with_unsaved_changes_is_refused_untouched(self):
        result = self.delete_sheet(WPSFAKE_OPEN="1", WPSFAKE_SAVED="0")
        self.assertFalse(result["ok"], result)
        self.assertIn("unsaved changes", str(result))
        self.assertEqual(self.events(), [])

    def test_reopening_an_unsaved_workbook_cannot_hide_its_dirty_state(self):
        for attach in ("0", "1"):
            with self.subTest(attach=attach):
                self.log.write_text("", encoding="utf-8")
                result = self.delete_sheet(
                    WPSFAKE_OPEN="1", WPSFAKE_SAVED="0", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH=attach,
                )
                self.assertFalse(result["ok"], result)
                self.assertIn("unsaved changes", str(result))
                self.assertEqual(self.events(), [])
                self.assertEqual(self.open_calls(), [])

    def test_open_workbook_is_used_directly_instead_of_being_opened_again(self):
        self.log.write_text("", encoding="utf-8")
        result = self.delete_sheet(WPSFAKE_OPEN="1", WPSFAKE_SAVED="1", WPSFAKE_OPEN_OTHER="1", WPSFAKE_ATTACH="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.open_calls(), [])
        self.assertEqual(self.events(), ["delete", "save"])

    def test_closed_workbook_is_opened_by_its_path(self):
        result = self.delete_sheet(WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.open_calls(), [f"open:{self.document}"])

    def test_cell_write_keeps_alerts_quiet_and_restores_them(self):
        with patch.dict(os.environ, {"WPSFAKE_OPEN": "1", "WPSFAKE_SAVED": "1", "WPSFAKE_ATTACH": "1"}):
            result = spreadsheet_ops._run_spreadsheet_write_com(str(self.document), None, "A1", [[1]])
        self.assertEqual(self.settings(), ["alerts=False:attached", "alerts=True:attached"], result)

    def test_formula_write_keeps_alerts_quiet_and_restores_them(self):
        with patch.dict(os.environ, {"WPSFAKE_OPEN": "1", "WPSFAKE_SAVED": "1", "WPSFAKE_ATTACH": "1"}):
            result = spreadsheet_ops._run_spreadsheet_formula_write_com(str(self.document), None, "A1", [["=1"]])
        self.assertEqual(self.settings(), ["alerts=False:attached", "alerts=True:attached"], result)


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
