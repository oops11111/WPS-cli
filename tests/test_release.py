import importlib.util
import re
import unittest
from pathlib import Path

import wps_ai_agent_cli
from wps_ai_agent_cli.mcp_server import SERVER_INFO

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("release_notes", REPO_ROOT / "scripts" / "release_notes.py")
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Unreleased]

## [1.2.0] - 2026-01-02

### Added

- A thing.

## [1.1.0]

- Undated.

## [1.0.0] - 2025-12-01
"""


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

    def test_the_current_version_has_a_dated_non_empty_section(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        notes = release_notes.release_notes(f"v{wps_ai_agent_cli.__version__}", wps_ai_agent_cli.__version__, changelog)

        self.assertIn("### ", notes)
        self.assertNotIn("## [", notes)

    def test_the_mcp_reports_the_package_version(self):
        self.assertEqual(SERVER_INFO["version"], wps_ai_agent_cli.__version__)


class ReleaseNotesTests(unittest.TestCase):
    def test_the_section_for_the_tagged_version_is_the_release_notes(self):
        self.assertEqual(release_notes.release_notes("v1.2.0", "1.2.0", CHANGELOG), "### Added\n\n- A thing.\n")

    def test_a_tag_that_does_not_match_the_package_version_is_refused(self):
        with self.assertRaisesRegex(release_notes.ReleaseError, "expected v1.2.0"):
            release_notes.release_notes("v1.2.1", "1.2.0", CHANGELOG)
        with self.assertRaisesRegex(release_notes.ReleaseError, "expected v1.2.0"):
            release_notes.release_notes("1.2.0", "1.2.0", CHANGELOG)

    def test_a_missing_undated_or_empty_section_is_refused(self):
        with self.assertRaisesRegex(release_notes.ReleaseError, "no section for 9.9.9"):
            release_notes.release_notes("v9.9.9", "9.9.9", CHANGELOG)
        with self.assertRaisesRegex(release_notes.ReleaseError, "no date"):
            release_notes.release_notes("v1.1.0", "1.1.0", CHANGELOG)
        with self.assertRaisesRegex(release_notes.ReleaseError, "is empty"):
            release_notes.release_notes("v1.0.0", "1.0.0", CHANGELOG)

    def test_the_release_workflow_runs_on_version_tags_and_checks_before_publishing(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        self.assertIn('tags: ["v*"]', workflow)
        check = workflow.index("scripts/release_notes.py --tag")
        regression = workflow.index("regression-run --profile safe")
        publish = workflow.index("gh release create")
        self.assertLess(check, regression)
        self.assertLess(regression, publish)

    def test_pypi_gets_the_files_of_the_github_release_through_trusted_publishing(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        pypi = workflow[workflow.index("\n  pypi:") :]
        self.assertIn("needs: release", pypi)
        self.assertIn("id-token: write", pypi)
        self.assertIn("pypa/gh-action-pypi-publish@release/v1", pypi)
        self.assertIn("actions/download-artifact@v4", pypi)
        self.assertNotIn("password", pypi)
        self.assertNotIn("secrets.", workflow)
        # The release job keeps exactly what it published.
        self.assertLess(workflow.index("gh release create"), workflow.index("actions/upload-artifact@v4"))


if __name__ == "__main__":
    unittest.main()
