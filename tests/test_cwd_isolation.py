import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.isolation import use_temporary_cwd

ROOT = Path(__file__).resolve().parents[1]


class CwdIsolationTests(unittest.TestCase):
    def test_helper_switches_to_an_empty_directory_and_restores(self):
        original = os.getcwd()
        saved_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved_path))
        sys.path.insert(0, "relative-src")
        restore = use_temporary_cwd()
        try:
            self.assertNotEqual(os.getcwd(), original)
            self.assertEqual(os.listdir("."), [])
            self.assertTrue(all(os.path.isabs(entry) for entry in sys.path))
        finally:
            restore()
        self.assertEqual(os.getcwd(), original)

    def test_state_heavy_modules_leave_the_launch_directory_clean(self):
        for module in ("test_backups", "test_writer_ops"):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as launch:
                completed = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", f"{module}.py"],
                    cwd=launch, capture_output=True, text=True, timeout=300,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)},
                )
                self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
                self.assertEqual(os.listdir(launch), [], "the module wrote state into its launch directory")


if __name__ == "__main__":
    unittest.main()
