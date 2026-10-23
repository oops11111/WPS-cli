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

    def test_it_installs_the_all_extra_and_ocr_only_when_asked(self):
        self.assertIn("$extras = if ($Ocr) { 'all,ocr' } else { 'all' }", self.text)
        self.assertIn('"$($wheel)[$extras]"', self.text)

    def test_playwright_uses_edge_instead_of_downloading_browsers(self):
        self.assertIn("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'", self.text)
        self.assertIn("[Environment]::SetEnvironmentVariable('NODE_PATH', $modules, 'User')", self.text)

    def test_the_mcp_client_is_configured_by_the_package_module(self):
        self.assertIn("'wps_ai_agent_cli.client_config'", self.text)
        for client in ("claude-desktop", "claude-code", "json"):
            self.assertIn(f"--client {client}", self.text)

    def test_the_server_keeps_its_records_in_a_data_folder_uninstall_keeps(self):
        self.assertIn('"WPS_AGENT_WORKSPACE=$DataDir"', self.text)
        self.assertIn("(Join-Path $env:LOCALAPPDATA 'wps-agent-data')", self.text)

    def test_uninstall_only_removes_a_folder_the_installer_made(self):
        self.assertIn("Test-Path -LiteralPath (Join-Path $InstallDir 'install.json')", self.text)
        self.assertIn("not removing a folder this installer did not create", self.text)

    def test_the_download_is_checked_against_the_release_digest(self):
        self.assertIn("Get-FileHash -LiteralPath $target -Algorithm SHA256", self.text)


class InstallerWorkflowTests(unittest.TestCase):
    def test_ci_runs_the_installer_on_windows_and_uninstalls(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        job = workflow.split("windows-install:", 1)[1].split("\n  build:", 1)[0]
        self.assertIn("runs-on: windows-latest", job)
        self.assertIn("shell: powershell", job)  # Windows PowerShell 5.1, as most users have
        self.assertIn("-McpClient claude-desktop", job)
        self.assertIn("html-render", job)
        self.assertIn("-Uninstall", job)

    def test_the_release_carries_the_installer_and_install_steps(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("dist/* scripts/install/install.ps1", workflow)
        self.assertIn("cat scripts/install/release_install.md >> release-notes.md", workflow)
        notes = (ROOT / "scripts" / "install" / "release_install.md").read_text(encoding="utf-8")
        self.assertIn("releases/latest/download/install.ps1", notes)
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
