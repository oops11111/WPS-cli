"""com-smoke always runs the guarded PowerShell script, also when pywin32 is installed.

P4-003 (main@82c7a88): with pywin32 installed, com-smoke used a separate pywin32 branch that skipped the
open/held checks, and presentation-com-smoke failed on real WPS. convert-smoke, which always used the
PowerShell script, passed on the same file.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_wps_quit_guard import capture_scripts
from wps_ai_agent_cli import com_backend


class ComSmokeBackendTests(unittest.TestCase):
    def test_pywin32_being_installed_does_not_change_the_backend(self):
        client = MagicMock()
        win32com = types.ModuleType("win32com")
        win32com.client = client
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "deck.pptx"
            source.write_bytes(b"not a real presentation")
            target = Path(tmp) / "out" / "deck.pptx"
            target.parent.mkdir()
            with patch.dict(sys.modules, {"win32com": win32com, "win32com.client": client}):
                scripts = capture_scripts(
                    com_backend, lambda: com_backend.run_com_smoke("presentation", str(source), str(target))
                )

        client.DispatchEx.assert_not_called()
        self.assertEqual(len(scripts), 1)
        script = scripts[0]
        self.assertIn("Assert-WpsFileNotHeld $params.input_path 'input document' $true", script)
        self.assertIn("$app.Presentations.Open((ConvertTo-WpsLocalPath $params.input_path), $false, $false,", script)
        self.assertNotIn("WithWindow", script)

    def test_the_pywin32_branch_is_gone(self):
        self.assertFalse(hasattr(com_backend, "_load_win32com"))


if __name__ == "__main__":
    unittest.main()
