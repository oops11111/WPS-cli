"""The P6-001 automation diagnostic: read-only by construction, and it always produces its JSON report."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "real_wps_verify_p6" / "automation-diagnostic.ps1"


class ReadOnlyTests(unittest.TestCase):
    def test_the_script_never_opens_saves_closes_starts_or_ends_anything(self):
        text = SCRIPT.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        forbidden = [
            r"\.Open\(",
            r"\.Save\w*\(",
            r"\.Close\(",
            r"\.Quit\(",
            r"\.Activate\(",
            r"New-Object\s+-ComObject",
            r"Stop-Process",
            r"Start-Process",
            r"\.Kill\(",
            r"BindToObject",
            r"CoCreateInstance",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, code), pattern)


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the diagnostic")
class ReportTests(unittest.TestCase):
    def test_the_report_has_every_section_even_without_wps(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "diag.json"
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(SCRIPT), "-Out", str(out)],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(out.read_text(encoding="utf-8-sig"))

        self.assertEqual(report["tool"], "automation-diagnostic")
        self.assertEqual(len(report["prog_ids"]), 9)
        self.assertEqual({item["component"] for item in report["prog_ids"]}, {"writer", "spreadsheets", "presentation"})
        self.assertFalse(any(item["active_object"] for item in report["prog_ids"]))
        self.assertIn("entries", report["running_object_table"])
        self.assertIn("processes", report)


if __name__ == "__main__":
    unittest.main()
