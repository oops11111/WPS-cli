import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "wps_ai_agent_cli"
THIRD_PARTY_TO_DISTRIBUTION = {"openpyxl": "openpyxl"}


def _module_level_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


class PackagingMetadataTests(unittest.TestCase):
    def test_module_level_third_party_imports_are_runtime_dependencies(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.M | re.S)
        self.assertIsNotNone(match)
        declared = match.group(1).lower()
        stdlib = set(sys.stdlib_module_names)
        found = set()
        for path in SRC.glob("*.py"):
            found |= _module_level_imports(path)
        third_party = {name for name in found if name not in stdlib and name != "wps_ai_agent_cli"}
        self.assertEqual(
            third_party,
            set(THIRD_PARTY_TO_DISTRIBUTION),
            "update THIRD_PARTY_TO_DISTRIBUTION and pyproject dependencies",
        )
        for module, distribution in THIRD_PARTY_TO_DISTRIBUTION.items():
            self.assertIn(distribution, declared, module)

    def test_pyproject_has_no_inert_unittest_table(self):
        self.assertNotIn("[tool.unittest]", (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_package_json_declares_playwright_for_renderer(self):
        import json

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("playwright", package["dependencies"])
        script = (SRC / "html_render_playwright.cjs").read_text(encoding="utf-8")
        self.assertIn("require('playwright')", script)

    def test_test_extra_covers_every_third_party_import_in_tests(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
        match = re.search(r"^test\s*=\s*\[(.*?)\]", pyproject, re.M | re.S)
        self.assertIsNotNone(match)
        extra = match.group(1)
        stdlib = set(sys.stdlib_module_names)
        found = set()
        for path in (ROOT / "tests").glob("*.py"):
            found |= _module_level_imports(path)
        module_to_distribution = {
            "PIL": "pillow",
            "docx": "python-docx",
            "pptx": "python-pptx",
            "pypdfium2": "pypdfium2",
            "openpyxl": "openpyxl",
        }
        third_party = {name for name in found if name not in stdlib and name not in {"wps_ai_agent_cli", "tests"}}
        self.assertLessEqual(
            third_party, set(module_to_distribution), "map new test dependencies and add them to the test extra"
        )
        for module in third_party:
            self.assertIn(module_to_distribution[module], extra, module)

    def test_ci_workflow_installs_test_extra_and_runs_the_suite(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn('pip install -e ".[test]"', workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)
        self.assertIn("WPS_TEST_PWSH", workflow)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/tests.yml", readme)


if __name__ == "__main__":
    unittest.main()
