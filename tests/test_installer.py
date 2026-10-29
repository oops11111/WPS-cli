"""The Windows installer script (P14-003): it parses, and does the steps the user guide promises."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install" / "install.ps1"
PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")


class InstallerContentTests(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_it_is_plain_ascii_for_windows_powershell(self):
        # Windows PowerShell 5.1 reads a file without a BOM in the ANSI code page.
        self.assertTrue(self.text.isascii())

    def test_every_line_closes_its_strings(self):
        # A string left open swallows the rest of the script (it failed to parse on Windows in CI once); this
        # catches that without PowerShell. The script has no here-strings or strings spanning lines.
        open_lines = []
        in_block_comment = False
        for number, line in enumerate(self.text.splitlines(), 1):
            stripped = line.strip()
            if in_block_comment or stripped.startswith("<#"):
                in_block_comment = "#>" not in stripped
                continue
            quote = None
            index = 0
            while index < len(line):
                char = line[index]
                if quote is None and char == "#":
                    break
                if char == "`" and quote != "'":
                    index += 2
                    continue
                if quote is None and char in "\"'":
                    quote = char
                elif char == quote:
                    if index + 1 < len(line) and line[index + 1] == quote:
                        index += 1  # a doubled quote inside the string
                    else:
                        quote = None
                index += 1
            if quote is not None:
                open_lines.append(number)
        self.assertEqual(open_lines, [])

    def test_it_installs_the_all_extra_and_ocr_only_when_asked(self):
        self.assertIn("$extras = if ($Ocr) { 'all,ocr' } else { 'all' }", self.text)
        self.assertIn('"$($wheel)[$extras]"', self.text)

    def test_playwright_uses_edge_instead_of_downloading_browsers(self):
        self.assertIn("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'", self.text)
        # Ours first, then the user's own entries; -Uninstall removes only entries under the install folder.
        self.assertIn("Set-UserEnv 'NODE_PATH' ((@($modules) + $others) -join ';')", self.text)
        self.assertIn("Where-Object { -not (Test-UnderPath $_ $InstallDir) }", self.text)

    def test_user_variables_are_edited_in_the_registry_without_expanding_them(self):
        # [Environment]::SetEnvironmentVariable(..., 'User') stores the expanded value as REG_SZ, so %USERPROFILE%
        # and the like in the user's PATH were written out for good.
        self.assertNotIn("SetEnvironmentVariable", self.text)
        self.assertIn("[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames", self.text)
        self.assertIn("$key.GetValueKind($Name)", self.text)
        self.assertIn("SendMessageTimeout", self.text)  # new terminals see the change

    def test_the_shim_names_no_path_so_any_user_name_works(self):
        # Written as ASCII, a path with a Chinese user name in it became question marks.
        self.assertIn('"@echo off`r`n`"%~dp0..\\venv\\Scripts\\wps-agent.exe`" %*`r`n"', self.text)

    def test_relative_folders_follow_the_powershell_location(self):
        self.assertIn("$InstallDir = Resolve-FullPath $InstallDir", self.text)
        self.assertIn("$DataDir = Resolve-FullPath $DataDir", self.text)
        self.assertIn("GetUnresolvedProviderPathFromPSPath", self.text)

    def test_the_mcp_client_is_configured_by_the_package_module(self):
        self.assertIn("'wps_ai_agent_cli.client_config'", self.text)
        for client in ("claude-desktop", "claude-code", "json"):
            self.assertIn(f"--client {client}", self.text)

    def test_the_server_keeps_its_records_in_a_data_folder_uninstall_keeps(self):
        self.assertIn('"WPS_AGENT_WORKSPACE=$DataDir"', self.text)
        self.assertIn("(Join-Path $env:LOCALAPPDATA 'wps-agent-data')", self.text)

    def test_uninstall_only_removes_a_folder_the_installer_made(self):
        self.assertIn("not removing a folder this installer did not create", self.text)
        self.assertIn("foreach ($part in 'venv', 'node', 'bin')", self.text)
        self.assertIn("if (@(Get-ChildItem -LiteralPath $InstallDir -Force).Count -eq 0)", self.text)
        self.assertIn("if ($state -and $state.data_dir) { $dataDir = [string]$state.data_dir }", self.text)

    def test_the_install_record_is_written_before_anything_else_goes_in(self):
        # So -Uninstall can clean up after an install that failed half way.
        first_record = self.text.index("status = 'installing'")
        self.assertLess(first_record, self.text.index("& $pythonExe -m venv $venvDir"))
        self.assertLess(first_record, self.text.index("Install-Browser $nodeDir"))

    def test_files_of_a_running_server_stop_the_upgrade_or_uninstall_before_anything_is_removed(self):
        self.assertIn("if (Test-Path -LiteralPath $venvDir) { Assert-NotRunning $venvDir }", self.text)
        self.assertLess(self.text.index("Assert-NotRunning $InstallDir"), self.text.index("foreach ($part in"))

    def test_claude_code_registration_replaces_an_old_entry_and_checks_the_result(self):
        self.assertIn("& claude mcp remove --scope user $result.name", self.text)
        self.assertIn("claude mcp add failed (exit code $LASTEXITCODE)", self.text)

    def test_native_output_is_read_as_utf8_and_the_session_is_restored(self):
        self.assertIn("$env:PYTHONUTF8 = '1'", self.text)
        self.assertIn("[Console]::OutputEncoding = $savedEncoding", self.text)

    def test_the_download_is_checked_against_the_release_digest(self):
        self.assertIn("Get-FileHash -LiteralPath $target -Algorithm SHA256", self.text)
        self.assertIn("the download was not checked", self.text)  # said when GitHub lists no digest


class InstallerWorkflowTests(unittest.TestCase):
    def test_ci_runs_the_installer_on_windows_and_uninstalls(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        job = workflow.split("windows-install:", 1)[1].split("\n  build:", 1)[0]
        self.assertIn("runs-on: windows-latest", job)
        self.assertIn("shell: powershell", job)  # Windows PowerShell 5.1, as most users have
        self.assertIn("-McpClient claude-desktop", job)
        self.assertIn("html-render", job)
        self.assertIn("-Uninstall", job)
        # A Chinese folder name with a space, a %VARIABLE% PATH entry and a NODE_PATH of the user's own, all kept.
        self.assertIn("(0x5B89, 0x88C5)", job)
        self.assertIn("%USERPROFILE%\\wps-agent-ci-marker", job)
        self.assertIn("C:\\ci\\own_node_modules", job)
        self.assertIn("foreach ($run in 1, 2)", job)  # the second run is an upgrade

    def test_the_release_carries_the_installer_and_install_steps(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("dist/* scripts/install/install.ps1", workflow)
        notes = (ROOT / "scripts" / "install" / "release_install.md").read_text(encoding="utf-8")
        self.assertIn("releases/latest/download/install.ps1", notes)
        self.assertIn("install.ps1 -McpClient", notes)
        # Each version's notes install that version.
        self.assertIn(
            "s#releases/latest/download/install.ps1#releases/download/${GITHUB_REF_NAME}/install.ps1#", workflow
        )
        self.assertIn("s#install.ps1 -McpClient#install.ps1 -Version ${GITHUB_REF_NAME#v} -McpClient#", workflow)
        self.assertIn("scripts/install/release_install.md >> release-notes.md", workflow)
        self.assertIn("docs/USER_GUIDE.md", notes)


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to parse the installer")
class InstallerParseTests(unittest.TestCase):
    def test_the_installer_parses(self):
        check = (
            "$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{SCRIPT}', [ref]$null, [ref]$errors); $errors.Count"
        )
        completed = subprocess.run(
            [PWSH, "-NoProfile", "-Command", check], capture_output=True, text=True, timeout=120, check=False
        )
        self.assertEqual(completed.stdout.strip(), "0", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()


class UserGuideTests(unittest.TestCase):
    def setUp(self):
        self.guide = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")

    def test_every_error_code_the_guide_names_exists(self):
        import json
        import re

        known = set(json.loads((ROOT / "config" / "public_interface.json").read_text(encoding="utf-8"))["error_codes"])
        named = set(re.findall(r"`([A-Z][A-Z0-9_]{4,})`", self.guide)) - {"NODE_PATH", "WPS_AGENT_WORKSPACE"}
        self.assertTrue(named)
        self.assertLessEqual(named, known)

    def test_every_installer_option_the_guide_names_exists(self):
        import re

        script = SCRIPT.read_text(encoding="utf-8")
        params = set(re.findall(r"\[(?:string|switch)\]\$(\w+)", script))
        for option in set(re.findall(r"`-(\w+)", self.guide)):
            self.assertIn(option, params, option)

    def test_the_mcp_entry_in_the_guide_matches_the_generated_one(self):
        from wps_ai_agent_cli import client_config

        entry = client_config.server_entry("x", {"WPS_AGENT_WORKSPACE": "w", "NODE_PATH": "n"})
        self.assertIn(f'"args": {json_list(entry["args"])}', self.guide)
        for key in entry["env"]:
            self.assertIn(f'"{key}"', self.guide)


def json_list(values):
    import json

    return json.dumps(values)
