import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_wps_preopen_guard import FAKE_SPREADSHEET_PRELUDE, all_scripts
from tests.test_wps_quit_guard import CAPABILITIES, capture_scripts
from wps_ai_agent_cli import com_backend, presentation_ops, spreadsheet_ops
from wps_ai_agent_cli.wps_script_snippets import (
    ACQUIRE_WPS_APP,
    HIDE_LAUNCHED_APP,
    PRE_OPEN_GUARD,
    RELEASE_WPS_APP,
)

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

SETTING_PREFIXES = ("visible=", "alerts=", "events=", "links=")
NOISE_PREFIXES = SETTING_PREFIXES + ("new-object", "open")


class AttachFirstStaticTests(unittest.TestCase):
    def smoke_scripts(self, tmp):
        source = Path(tmp) / "input.xlsx"
        source.write_bytes(b"x")
        out = Path(tmp) / "out"
        cases = [
            (com_backend, lambda: com_backend.run_com_smoke("writer", str(source), str(out / "a.docx"))),
            (com_backend, lambda: com_backend.run_conversion_smoke("spreadsheets", str(source), str(out / "a.pdf"), "pdf")),
            (com_backend, lambda: com_backend.run_spreadsheet_calc_smoke(str(source), str(out / "a.xlsx"))),
        ]
        scripts = []
        with patch.object(com_backend, "_load_win32com", return_value=None):
            for module, call in cases:
                captured = capture_scripts(module, call)
                self.assertEqual(len(captured), 1)
                scripts.append(captured[0])
        return scripts

    def test_every_file_based_script_attaches_first_and_never_quits_an_attached_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "input.xlsx")
            Path(path).write_bytes(b"x")
            scripts = [script for script, _ in all_scripts(path).values()] + self.smoke_scripts(tmp)
        self.assertEqual(len(scripts), 15)
        for script in scripts:
            self.assertEqual(script.count(ACQUIRE_WPS_APP), 1)
            self.assertEqual(script.count("New-Object -ComObject"), 1)
            self.assertLess(script.index("Get-RunningWpsApp @($params.prog_id)"), script.index("New-Object -ComObject"))
            self.assertIn(RELEASE_WPS_APP, script)
            self.assertEqual(script.count("$app.Quit()"), 1)
            self.assertLess(script.index("if ($weLaunched) { $wpsIdle"), script.index("$app.Quit()"))
            self.assertNotIn("$app.Visible = $false", script.replace(HIDE_LAUNCHED_APP, ""))
            self.assertNotIn("$app.DisplayAlerts = $false", script)

    def test_launch_flag_is_set_only_on_the_fallback_path(self):
        self.assertIn("$weLaunched = $false;", ACQUIRE_WPS_APP)
        fallback = ACQUIRE_WPS_APP.index("if ($null -eq $app)")
        self.assertIn("$weLaunched = $true", ACQUIRE_WPS_APP[fallback:])
        self.assertNotIn("$weLaunched = $true", ACQUIRE_WPS_APP[:fallback])

    def test_smoke_scripts_refuse_an_input_that_is_already_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = self.smoke_scripts(tmp)
        for script in scripts:
            self.assertIn("Assert-WpsInputNotOpen (Test-WpsPathOpen $app.", script)
            self.assertLess(script.index("Assert-WpsInputNotOpen"), script.index(".Open((ConvertTo-WpsLocalPath $params.input_path)"))


def run_pwsh(body):
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "t.ps1"
        script.write_text(PRE_OPEN_GUARD + "\n$ErrorActionPreference = 'Stop'\n" + body, encoding="utf-8-sig")
        completed = subprocess.run(
            [PWSH, "-NoProfile", "-File", str(script)], capture_output=True, text=True, timeout=60,
        )
    if completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)
    return completed.stdout.strip().splitlines()


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts")
class LocalPathNormalisationTests(unittest.TestCase):
    def convert(self, *paths, computer="BOX1"):
        calls = "\n".join(f"ConvertTo-WpsLocalPath '{path}'" for path in paths)
        return run_pwsh(f"$env:COMPUTERNAME = '{computer}'\n{calls}\n")

    def test_admin_shares_of_this_machine_become_local_paths(self):
        self.assertEqual(
            self.convert(
                r"\\localhost\C$\work\book.xlsx",
                r"\\LOCALHOST\c$\work\book.xlsx",
                r"\\127.0.0.1\D$\a.xlsx",
                r"\\box1\E$\x\y.xlsx",
                r"\\localhost\C$",
            ),
            [r"C:\work\book.xlsx", r"c:\work\book.xlsx", r"D:\a.xlsx", r"E:\x\y.xlsx", "C:\\"],
        )

    def test_extended_length_prefixes_are_removed(self):
        self.assertEqual(
            self.convert(r"\\?\C:\work\book.xlsx", r"\\?\UNC\localhost\C$\work\book.xlsx", r"\\?\UNC\fileserver\share\a.xlsx"),
            [r"C:\work\book.xlsx", r"C:\work\book.xlsx", r"\\fileserver\share\a.xlsx"],
        )

    def test_other_hosts_regular_shares_and_local_paths_are_left_alone(self):
        paths = [r"\\otherhost\C$\a.xlsx", r"\\localhost\shared\a.xlsx", r"C:\a\b.xlsx", "D:\\"]
        self.assertEqual(self.convert(*paths), paths)

    def test_comparable_path_resolves_relative_segments(self):
        base = os.path.join(os.path.abspath(os.sep), "wps_dir")
        messy = os.path.join(base, "a", "..", "b", "book.xlsx")
        expected = os.path.join(base, "b", "book.xlsx")
        [actual] = run_pwsh(f"ConvertTo-WpsComparablePath '{messy}'")
        self.assertEqual(os.path.normcase(actual), os.path.normcase(expected))

    def test_settings_changed_on_an_attached_app_are_restored(self):
        lines = run_pwsh(
            "$app = [pscustomobject]@{ DisplayAlerts = $true; EnableEvents = $true; AskToUpdateLinks = $false; Untouched = 1 }\n"
            "Set-WpsAppQuiet $app @('DisplayAlerts', 'EnableEvents', 'AskToUpdateLinks')\n"
            "\"during: $($app.DisplayAlerts) $($app.EnableEvents) $($app.AskToUpdateLinks)\"\n"
            "Restore-WpsAppSettings $app\n"
            "\"after: $($app.DisplayAlerts) $($app.EnableEvents) $($app.AskToUpdateLinks) $($app.Untouched)\"\n"
        )
        self.assertEqual(lines, ["during: False False False", "after: True True False 1"])


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts")
class OpenByLocalPathTests(unittest.TestCase):
    FAKE_COLLECTION = r"""
$env:COMPUTERNAME = 'BOX1'
$global:opens = @()
$coll = [pscustomobject]@{ Count = 1; Existing = [pscustomobject]@{ FullName = 'C:\data\open.xlsx'; Tag = 'existing' } }
$coll | Add-Member -MemberType ScriptMethod -Name Item -Value { param($i) return $this.Existing }
$coll | Add-Member -MemberType ScriptMethod -Name Open -Value { param($p, $update, $readOnly) $global:opens += "open:$p|$update|$readOnly"; return [pscustomobject]@{ Tag = 'opened' } }
"""

    def call(self, body):
        return run_pwsh(self.FAKE_COLLECTION + body + "\n$global:opens\n")

    def test_unc_spelling_of_a_local_drive_is_opened_by_its_local_path(self):
        lines = self.call(r"[void](Open-WpsDocument $coll '\\localhost\C$\data\new.xlsx' $false)")
        self.assertEqual(lines, [r"open:C:\data\new.xlsx||"])

    def test_machine_name_and_extended_prefix_spellings_use_the_local_path(self):
        lines = self.call(
            r"[void](Open-WpsDocument $coll '\\box1\D$\x\a.xlsx' $false)" "\n"
            r"[void](Open-WpsDocument $coll '\\?\E:\x\b.xlsx' $false)" "\n"
        )
        self.assertEqual(lines, [r"open:D:\x\a.xlsx||", r"open:E:\x\b.xlsx||"])

    def test_read_only_open_passes_the_read_only_flag(self):
        lines = self.call(r"[void](Open-WpsDocument $coll 'C:\data\new.xlsx' $false $true)")
        self.assertEqual(lines, [r"open:C:\data\new.xlsx|0|True"])

    def test_already_open_document_is_returned_without_opening_again(self):
        lines = self.call(r"(Open-WpsDocument $coll 'c:\DATA\Open.xlsx' $true).Tag")
        self.assertEqual(lines, ["existing"])


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts against a fake COM object")
class AttachBehaviourTests(unittest.TestCase):
    prelude_suffix = ""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.document = self.dir / "book.xlsx"
        self.document.write_bytes(b"x")
        self.log = self.dir / "fake.log"
        self.log.write_text("", encoding="utf-8")
        real_run = spreadsheet_ops.run_powershell_script
        suffix = (
            "$global:fakeLaunched.Presentations = $global:fakeLaunched.Workbooks\n"
            "$global:fakeAttached.Presentations = $global:fakeAttached.Workbooks\n"
        )

        def run_with_fake(script, *args, **kwargs):
            return real_run(FAKE_SPREADSHEET_PRELUDE + suffix + script, *args, **kwargs)

        patchers = [
            patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH),
            patch.object(spreadsheet_ops, "probe_wps_capabilities", return_value=CAPABILITIES),
            patch.object(spreadsheet_ops, "run_powershell_script", side_effect=run_with_fake),
            patch.object(presentation_ops, "probe_wps_capabilities", return_value=CAPABILITIES),
            patch.object(presentation_ops, "run_powershell_script", side_effect=run_with_fake),
            patch.object(com_backend, "probe_wps_capabilities", return_value=CAPABILITIES),
            patch.object(com_backend, "run_powershell_script", side_effect=run_with_fake),
            patch.dict(os.environ, {"WPSFAKE_PATH": str(self.document), "WPSFAKE_LOG": str(self.log)}),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def log_lines(self):
        return self.log.read_text(encoding="utf-8").split()

    def events(self):
        return [line for line in self.log_lines() if not line.startswith(NOISE_PREFIXES)]

    def settings(self):
        return [line for line in self.log_lines() if line.startswith(SETTING_PREFIXES)]

    def delete_sheet(self, **env):
        with patch.dict(os.environ, env):
            return spreadsheet_ops._run_spreadsheet_delete_sheet_com(str(self.document), "S")

    def test_document_open_only_in_the_running_instance_is_seen_and_kept_open(self):
        # New-Object hands out an instance that sees no documents; GetActiveObject holds the user's.
        result = self.delete_sheet(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="1", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save"])
        self.assertNotIn("new-object", self.log_lines())

    def test_unsaved_document_in_the_running_instance_is_refused_untouched(self):
        result = self.delete_sheet(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="1", WPSFAKE_SAVED="0")
        self.assertFalse(result["ok"], result)
        self.assertIn("unsaved changes", str(result))
        self.assertEqual(self.events(), [])

    def test_attached_instance_is_never_quit_even_when_the_script_opened_the_document(self):
        result = self.delete_sheet(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save", "close"])
        self.assertNotIn("new-object", self.log_lines())

    def test_attached_instance_keeps_its_window_and_gets_its_alert_setting_back(self):
        self.delete_sheet(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="1", WPSFAKE_SAVED="1")
        self.assertEqual(self.settings(), ["alerts=False:attached", "alerts=True:attached"])

    def test_instance_launched_by_the_script_is_hidden_closed_and_quit(self):
        result = self.delete_sheet(WPSFAKE_ATTACH="0", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save", "close", "quit:new"])
        self.assertIn("new-object", self.log_lines())
        self.assertEqual(self.settings()[0], "visible=False:new")

    def test_launched_instance_does_not_quit_while_another_document_is_open(self):
        with patch.dict(os.environ, {"WPSFAKE_ATTACH": "0", "WPSFAKE_OPEN": "0", "WPSFAKE_SAVED": "1"}):
            real = spreadsheet_ops.run_powershell_script

            def keep_busy(script, *args, **kwargs):
                return real(script.replace("$wpsPreOpen = ", "$app.Workbooks.Count = 5; $wpsPreOpen = ", 1), *args, **kwargs)

            with patch.object(spreadsheet_ops, "run_powershell_script", side_effect=keep_busy):
                result = spreadsheet_ops._run_spreadsheet_delete_sheet_com(str(self.document), "S")
        self.assertTrue(result["ok"], result)
        self.assertNotIn("quit:new", self.events())

    def test_open_presentation_is_refused_even_though_saved_is_always_true(self):
        for attach in ("1", "0"):
            with self.subTest(attach=attach):
                self.log.write_text("", encoding="utf-8")
                with patch.dict(os.environ, {"WPSFAKE_ATTACH": attach, "WPSFAKE_OPEN": "1", "WPSFAKE_SAVED": "1"}):
                    result = presentation_ops._run_presentation_replace_com(str(self.document), "a", "b")
                self.assertFalse(result["ok"], result)
                self.assertIn("already open in WPS", str(result))
                self.assertIn("does not reliably report unsaved", str(result))
                self.assertNotIn("open", self.log_lines())
                self.assertNotIn("close", self.log_lines())

    def test_smoke_commands_refuse_an_input_open_in_the_running_instance(self):
        out = self.dir / "out.xlsx"
        env = {"WPSFAKE_ATTACH": "1", "WPSFAKE_OPEN": "1", "WPSFAKE_SAVED": "1"}
        with patch.dict(os.environ, env):
            calc = com_backend.run_spreadsheet_calc_smoke(str(self.document), str(out))
            self.assertFalse(calc["ok"], calc)
            self.assertIn("already open in WPS", str(calc))
            convert = com_backend.run_conversion_smoke("spreadsheets", str(self.document), str(self.dir / "o.pdf"), "pdf")
            self.assertFalse(convert["ok"], convert)
            self.assertIn("already open in WPS", str(convert))
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
