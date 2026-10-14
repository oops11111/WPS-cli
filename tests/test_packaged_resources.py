"""Packaged copies of config files, and how the default config/ paths resolve (P5-007)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import regression, resources
from wps_ai_agent_cli.mcp_catalog_drift import build_mcp_catalog_drift_report

REPO_ROOT = Path(__file__).resolve().parents[1]


class PackagedCopyTests(unittest.TestCase):
    def test_every_packaged_copy_is_identical_to_the_repository_file(self):
        for config_path, name in resources.SHIPPED_CONFIG.items():
            with self.subTest(config=config_path):
                self.assertEqual(
                    (resources.RESOURCE_DIR / name).read_bytes(),
                    (REPO_ROOT / config_path).read_bytes(),
                    f"copy {config_path} to src/wps_ai_agent_cli/resources/{name}",
                )

    def test_the_resource_directory_holds_only_the_shipped_copies(self):
        self.assertEqual(
            sorted(path.name for path in resources.RESOURCE_DIR.iterdir() if path.is_file()),
            sorted(resources.SHIPPED_CONFIG.values()),
        )

    def test_the_package_data_includes_the_resource_directory(self):
        self.assertIn('"resources/*.json"', (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class ResolveConfigTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.getcwd()
        self.scratch = tempfile.TemporaryDirectory()
        os.chdir(self.scratch.name)

    def tearDown(self):
        os.chdir(self.previous)
        self.scratch.cleanup()

    def test_an_existing_path_is_used_as_given(self):
        Path("config").mkdir()
        Path("config/regression_manifest.json").write_text('{"scenarios": []}', encoding="utf-8")

        self.assertEqual(
            resources.resolve_config("config/regression_manifest.json"), Path("config/regression_manifest.json")
        )

    def test_a_missing_default_path_falls_back_to_the_checkout_then_the_package(self):
        self.assertEqual(
            resources.resolve_config("config/regression_manifest.json"),
            REPO_ROOT / "config" / "regression_manifest.json",
        )
        with patch.object(resources, "source_checkout", return_value=None):
            self.assertEqual(
                resources.resolve_config("config/regression_manifest.json"),
                resources.RESOURCE_DIR / "regression_manifest.json",
            )

    def test_a_missing_path_the_caller_chose_stays_missing(self):
        with patch.object(resources, "source_checkout", return_value=None):
            ok, _manifest, errors = regression.load_regression_manifest("elsewhere/manifest.json")
            guard_ok, _report, guard_errors = build_mcp_catalog_drift_report("elsewhere/guard.json")

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "REGRESSION_MANIFEST_NOT_FOUND")
        self.assertFalse(guard_ok)
        self.assertEqual(guard_errors[0]["code"], "MCP_CATALOG_GUARD_NOT_FOUND")

    def test_without_a_checkout_the_safe_profile_runs_from_the_packaged_files(self):
        with (
            patch.object(resources, "source_checkout", return_value=None),
            patch.object(regression, "source_checkout", return_value=None),
        ):
            ok, result, errors = regression.run_regression_manifest(profile="safe")

        self.assertTrue(ok, errors)
        self.assertEqual(result["failed_count"], 0, result)
        self.assertGreaterEqual(result["scenario_count"], 7)
        self.assertEqual(result["manifest_path"], str(resources.RESOURCE_DIR / "regression_manifest.json"))

    def test_the_audit_config_for_an_installed_package_imports_the_installed_package(self):
        destination = Path("rendered")
        destination.mkdir()
        with patch.object(regression, "source_checkout", return_value=None):
            rendered = regression._render_mcp_audit_config(
                resources.RESOURCE_DIR / "mcp_client_config.regression.template.json", destination
            )
        server = next(iter(json.loads(rendered.read_text(encoding="utf-8"))["mcpServers"].values()))

        self.assertEqual(server["command"], sys.executable)
        self.assertEqual(server["cwd"], str(destination))
        self.assertEqual(server["env"], {"PYTHONPATH": str(resources.PACKAGE_DIR.parent)})


class InstalledLayoutTests(unittest.TestCase):
    def test_source_checkout_is_found_from_the_repository(self):
        self.assertEqual(resources.source_checkout(), REPO_ROOT)

    def test_regression_manifest_command_works_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, "-m", "wps_ai_agent_cli", "regression-manifest", "--profile", "safe"],
                cwd=tmp,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
                check=False,
            )
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertGreaterEqual(len(payload["data"]["scenarios"]), 7)


if __name__ == "__main__":
    unittest.main()
