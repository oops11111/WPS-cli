import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_wps_preopen_guard import FAKE_SPREADSHEET_PRELUDE, all_scripts
from tests.test_wps_quit_guard import CAPABILITIES, capture_scripts
from wps_ai_agent_cli import com_backend, presentation_ops, spreadsheet_inspect, spreadsheet_ops
from wps_ai_agent_cli.sessions import register_document
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
$coll | Add-Member -MemberType ScriptMethod -Name Open -Value { param($p, $update, $readOnly) $global:opens += "open:$p|$update|$readOnly"; $this.Count = $this.Count + 1; return [pscustomobject]@{ Tag = 'opened' } }
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


class ScriptWarningTests(unittest.TestCase):
    def run_with(self, stdout, stderr, returncode=0):
        from wps_ai_agent_cli import powershell_runner

        completed = subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)
        with patch.object(powershell_runner.subprocess, "run", return_value=completed), \
                patch.object(powershell_runner, "powershell_executable", return_value="pwsh"):
            return powershell_runner.run_powershell_script("exit 0")

    def test_stderr_notices_are_returned_as_warnings_without_touching_stdout_json(self):
        payload, failure = self.run_with(
            '{"ok": true}',
            "noise\nWPS_AGENT_WARNING: 3 wps processes\nWPS_AGENT_WARNING: 3 wps processes\nWPS_AGENT_WARNING: other\n",
        )
        self.assertIsNone(failure)
        self.assertEqual(payload, {"ok": True, "warnings": ["3 wps processes", "other"]})

    def test_no_warnings_key_without_notices(self):
        payload, failure = self.run_with('{"ok": true}', "some unrelated stderr")
        self.assertEqual(payload, {"ok": True})


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts")
class ProcessNameTests(unittest.TestCase):
    def test_progids_map_to_the_component_process(self):
        progids = [
            "kwps.Application", "wps.Application", "Kingsoft Writer.Application",
            "ket.Application", "et.Application", "Kingsoft Spreadsheets.Application",
            "kwpp.Application", "wpp.Application", "Kingsoft Presentation.Application",
            "something.Else",
        ]
        calls = "\n".join(f"\"[$(Get-WpsProcessName '{progid}')]\"" for progid in progids)
        self.assertEqual(
            run_pwsh(calls),
            ["[wps]", "[wps]", "[wps]", "[et]", "[et]", "[et]", "[wpp]", "[wpp]", "[wpp]", "[]"],
        )


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts")
class ProcessSnapshotTests(unittest.TestCase):
    FAKE_PROCESSES = r"""
function Get-Process {
  [CmdletBinding()] param([string]$Name)
  $session = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
  [Console]::Error.WriteLine('queried:' + $Name)
  $specs = @(
    @{ Id = 11; Window = 100; Session = $session; Title = 'Main' },
    @{ Id = 12; Window = 0; Session = $session; Title = '' },
    @{ Id = 13; Window = 0; Session = $session; Title = '' },
    @{ Id = 14; Window = 400; Session = ($session + 1); Title = 'Other user' }
  ) | Select-Object -First ([int]$env:FAKE_TOTAL)
  foreach ($spec in $specs) {
    [pscustomobject]@{ Name = $Name; Id = $spec.Id; SessionId = $spec.Session; MainWindowHandle = [IntPtr]$spec.Window; MainWindowTitle = $spec.Title }
  }
}
"""

    def run_script(self, body, total):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "t.ps1"
            script.write_text(
                PRE_OPEN_GUARD + "\n$ErrorActionPreference = 'Stop'\n" + self.FAKE_PROCESSES + body,
                encoding="utf-8-sig",
            )
            env = {key: value for key, value in os.environ.items() if key != "WPS_AGENT_ALLOW_MULTI_INSTANCE"}
            env["FAKE_TOTAL"] = str(total)
            return subprocess.run(
                [PWSH, "-NoProfile", "-File", str(script)], capture_output=True, text=True, timeout=60, env=env,
            )

    def test_progids_query_the_matching_process_name(self):
        for progid, name in (("kwps.Application", "wps"), ("ket.Application", "et"), ("kwpp.Application", "wpp")):
            with self.subTest(progid=progid):
                completed = self.run_script(f"Assert-WpsSingleInstance '{progid}'", 1)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn(f"queried:{name}", completed.stderr)

    def test_one_windowed_process_among_background_ones_is_allowed_with_a_warning(self):
        for progid, name in (("kwps.Application", "wps"), ("ket.Application", "et"), ("kwpp.Application", "wpp")):
            with self.subTest(progid=progid):
                completed = self.run_script(f"Assert-WpsSingleInstance '{progid}'", 3)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn(f"WPS_AGENT_WARNING: 3 {name} processes", completed.stderr)

    def test_a_windowed_process_in_another_session_is_not_counted(self):
        completed = self.run_script("Assert-WpsSingleInstance 'kwps.Application'", 4)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("only 1 has a window", completed.stderr)

    def test_snapshot_reports_windowed_processes_with_titles(self):
        completed = self.run_script(
            "$s = Get-WpsProcessSnapshot 'wps'\n\"windowed=$(@($s.Windowed).Count) all=$(@($s.All).Count)\"\nFormat-WpsProcessList $s.Windowed\n",
            3,
        )
        self.assertEqual(completed.stdout.strip().splitlines(), ["windowed=1 all=3", 'pid 11 "Main"'])


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts against a fake COM object")
class InspectRecalculationTests(unittest.TestCase):
    def setUp(self):
        from openpyxl import Workbook

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        workspace = self.dir / "workspace"
        workspace.mkdir()
        self.workspace = workspace
        self.document = self.dir / "book.xlsx"
        workbook = Workbook()
        workbook.active.title = "S"
        workbook.active["A1"] = 1
        workbook.active["B1"] = "=A1*2"
        workbook.save(self.document)
        workbook.close()
        ok, record, errors = register_document("spreadsheets", str(self.document), workspace)
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]
        self.log = self.dir / "fake.log"
        self.log.write_text("", encoding="utf-8")
        real_run = spreadsheet_inspect.run_powershell_script

        def run_with_fake(script, *args, **kwargs):
            return real_run(FAKE_SPREADSHEET_PRELUDE + script, *args, **kwargs)

        for patcher in (
            patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH),
            patch.object(spreadsheet_inspect, "probe_wps_capabilities", return_value=CAPABILITIES),
            patch.object(spreadsheet_inspect, "run_powershell_script", side_effect=run_with_fake),
            patch.dict(os.environ, {"WPSFAKE_PATH": str(self.document), "WPSFAKE_LOG": str(self.log)}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def inspect(self, **env):
        with patch.dict(os.environ, env):
            return spreadsheet_inspect.inspect_spreadsheet_range(self.document_id, "A1:B1", "S", self.workspace)

    def log_lines(self):
        return self.log.read_text(encoding="utf-8").split()

    def test_attached_instance_is_not_fully_recalculated(self):
        ok, result, errors = self.inspect(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="1", WPSFAKE_SAVED="1")
        self.assertTrue(ok, errors)
        self.assertFalse([line for line in self.log_lines() if line.startswith("rebuild")])
        self.assertFalse(result["calculation_performed_in_memory"])
        self.assertIn("skipped", result["recalculation_skipped_reason"])
        self.assertIsNone(result["cache_mismatch_count"])
        self.assertTrue(all(cell["cache_matches_recalculated"] is None for cell in result["cells"]))
        self.assertTrue(result["read_only"])
        self.assertFalse(result["saved"])
        self.assertNotIn("close", self.log_lines())

    def test_attached_instance_is_not_recalculated_when_the_script_opens_the_document_itself(self):
        ok, result, errors = self.inspect(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(ok, errors)
        self.assertFalse([line for line in self.log_lines() if line.startswith("rebuild")])
        self.assertFalse(result["calculation_performed_in_memory"])
        self.assertIn("close", self.log_lines())
        self.assertNotIn("quit:attached", self.log_lines())

    def test_read_only_inspect_is_not_blocked_by_several_processes(self):
        ok, result, errors = self.inspect(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="2", WPSFAKE_WINDOWED="2")
        self.assertTrue(ok, errors)

    def test_instance_launched_by_the_script_is_still_fully_recalculated(self):
        ok, result, errors = self.inspect(WPSFAKE_ATTACH="0", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1")
        self.assertTrue(ok, errors)
        self.assertEqual([line for line in self.log_lines() if line.startswith("rebuild")], ["rebuild:new"])
        self.assertTrue(result["calculation_performed_in_memory"])
        self.assertNotIn("recalculation_skipped_reason", result)
        self.assertIsInstance(result["cache_mismatch_count"], int)
        self.assertIn("quit:new", self.log_lines())


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

    def test_several_windowed_wps_instances_refuse_opening_a_closed_document(self):
        for attach in ("1", "0"):
            with self.subTest(attach=attach):
                self.log.write_text("", encoding="utf-8")
                result = self.delete_sheet(
                    WPSFAKE_ATTACH=attach, WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="3", WPSFAKE_WINDOWED="2",
                )
                self.assertFalse(result["ok"], result)
                text = str(result)
                self.assertIn("Several WPS instances with a window", text)
                self.assertIn("et x2", text)
                self.assertIn("pid 1001", text)
                self.assertIn("Doc1 - WPS Office", text)
                self.assertIn("pid 1002", text)
                self.assertNotIn("pid 1003", text)
                self.assertIn("WPS_AGENT_ALLOW_MULTI_INSTANCE", text)
                self.assertFalse([line for line in self.log_lines() if line.startswith("open:")])
                self.assertEqual([line for line in self.events() if line != "quit:new"], [])

    def test_background_processes_without_a_window_do_not_block_but_are_reported(self):
        for attach in ("1", "0"):
            with self.subTest(attach=attach):
                self.log.write_text("", encoding="utf-8")
                result = self.delete_sheet(
                    WPSFAKE_ATTACH=attach, WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="3", WPSFAKE_WINDOWED="1",
                )
                self.assertTrue(result["ok"], result)
                [warning] = result["data"]["warnings"]
                self.assertIn("3 et processes", warning)
                self.assertIn("only 1 has a window", warning)
                self.assertTrue([line for line in self.log_lines() if line.startswith("open:")])

    def test_only_background_processes_are_allowed_with_a_warning(self):
        result = self.delete_sheet(
            WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="3", WPSFAKE_WINDOWED="0",
        )
        self.assertTrue(result["ok"], result)
        self.assertIn("only 0 has a window", result["data"]["warnings"][0])

    def test_a_single_process_has_no_warning(self):
        result = self.delete_sheet(WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="1")
        self.assertTrue(result["ok"], result)
        self.assertNotIn("warnings", result["data"])
        self.assertEqual(self.events(), ["delete", "save", "close"])

    def test_a_document_already_open_in_the_attached_instance_is_still_used_with_several_windows(self):
        result = self.delete_sheet(
            WPSFAKE_ATTACH="1", WPSFAKE_OPEN="1", WPSFAKE_SAVED="1", WPSFAKE_PROCS="3", WPSFAKE_WINDOWED="3",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.events(), ["delete", "save"])

    def test_the_multi_instance_check_can_be_switched_off(self):
        result = self.delete_sheet(
            WPSFAKE_ATTACH="1", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="2", WPSFAKE_WINDOWED="2",
            WPS_AGENT_ALLOW_MULTI_INSTANCE="1",
        )
        self.assertTrue(result["ok"], result)
        self.assertNotIn("warnings", result["data"])

    def test_launched_instance_is_still_quit_after_the_refusal(self):
        self.delete_sheet(WPSFAKE_ATTACH="0", WPSFAKE_OPEN="0", WPSFAKE_SAVED="1", WPSFAKE_PROCS="2", WPSFAKE_WINDOWED="2")
        self.assertEqual(self.events(), ["quit:new"])

    def test_presentation_and_smoke_commands_refuse_with_several_windowed_instances(self):
        env = {
            "WPSFAKE_ATTACH": "1", "WPSFAKE_OPEN": "0", "WPSFAKE_SAVED": "1", "WPSFAKE_PROCS": "3", "WPSFAKE_WINDOWED": "2",
        }
        with patch.dict(os.environ, env):
            presentation = presentation_ops._run_presentation_replace_com(str(self.document), "a", "b")
            calc = com_backend._run_powershell_com_smoke("spreadsheets", "ket.Application", str(self.document), str(self.dir / "out.xlsx"), False)
            conversion = com_backend.run_conversion_smoke("writer", str(self.document), str(self.dir / "out.pdf"), "pdf")
        for name, result in (("presentation", presentation), ("smoke", calc), ("conversion", conversion)):
            with self.subTest(command=name):
                self.assertFalse(result["ok"], result)
                self.assertIn("Several WPS instances with a window", str(result))
        self.assertFalse([line for line in self.log_lines() if line.startswith("open:")])

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

    def test_presentation_opened_by_the_user_after_the_check_is_refused_untouched(self):
        for reads in ("1", "2"):
            with self.subTest(race_reads=reads):
                self.log.write_text("", encoding="utf-8")
                env = {
                    "WPSFAKE_ATTACH": "1", "WPSFAKE_SAVED": "1", "WPSFAKE_RACE": "1", "WPSFAKE_RACE_READS": reads,
                    "WPSFAKE_OPEN_OTHER": "1",
                }
                with patch.dict(os.environ, env):
                    result = presentation_ops._run_presentation_replace_com(str(self.document), "a", "b")
                self.assertFalse(result["ok"], result)
                self.assertIn("between the check and the open call", str(result))
                self.assertNotIn("close", self.log_lines())
                self.assertEqual(bool([line for line in self.log_lines() if line.startswith("open:")]), reads == "2")

    def test_smoke_input_opened_by_the_user_after_the_check_is_refused_and_not_closed(self):
        env = {
            "WPSFAKE_ATTACH": "1", "WPSFAKE_SAVED": "0", "WPSFAKE_RACE": "1", "WPSFAKE_RACE_READS": "1",
            "WPSFAKE_OPEN_OTHER": "1",
        }
        with patch.dict(os.environ, env):
            convert = com_backend.run_conversion_smoke("spreadsheets", str(self.document), str(self.dir / "o.pdf"), "pdf")
            calc = com_backend.run_spreadsheet_calc_smoke(str(self.document), str(self.dir / "out.xlsx"))
        for name, result in (("conversion", convert), ("calc", calc)):
            with self.subTest(command=name):
                self.assertFalse(result["ok"], result)
                self.assertIn("between the check and the open call", str(result))
        self.assertNotIn("close", self.log_lines())
        self.assertNotIn("save", self.log_lines())

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
