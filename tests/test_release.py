import re
import unittest
from pathlib import Path

import wps_ai_agent_cli
from wps_ai_agent_cli.mcp_server import SERVER_INFO

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_the_version_is_defined_only_in_the_package(self):
        # Plain text checks: tomllib is not available on Python 3.10.
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        project_table = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]
        self.assertIsNone(re.search(r"^version\s*=", project_table, re.M))
        self.assertRegex(pyproject, r'(?m)^dynamic = \["version"\]$')
        self.assertIn('version = { attr = "wps_ai_agent_cli.__version__" }', pyproject)

    def test_the_version_has_three_numeric_parts(self):
        self.assertRegex(wps_ai_agent_cli.__version__, r"^\d+\.\d+\.\d+$")

    def test_the_changelog_has_unreleased_and_the_current_version(self):
        headings = re.findall(
            r"^## \[([^\]]+)\]",
            (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            re.M,
        )
        self.assertEqual(headings[0], "Unreleased")
        self.assertIn(wps_ai_agent_cli.__version__, headings)

    def test_mcp_reports_the_package_version(self):
        self.assertEqual(SERVER_INFO["version"], wps_ai_agent_cli.__version__)


if __name__ == "__main__":
    unittest.main()
