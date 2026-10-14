from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import regression


def _write_manifest(directory: Path, scenarios: list[dict]) -> Path:
    path = directory / "manifest.json"
    path.write_text(json.dumps({"version": "test", "default_profile": "wps", "scenarios": scenarios}), encoding="utf-8")
    return path


def _scenario(scenario_id: str, command: list[str]) -> dict:
    return {"id": scenario_id, "profile": "wps", "requires_wps": True, "command": command, "required_checks": []}


class OutputDirPlaceholderTests(unittest.TestCase):
    def test_placeholder_becomes_the_run_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            command = ["convert-smoke", "--input", "fixtures/in.docx", "--output", "{output_dir}/out.pdf"]
            rendered = regression._scenario_command(command, Path(tmp), output_dir)

        self.assertEqual(rendered[:4], command[:4])
        self.assertEqual(rendered[4], str(output_dir / "out.pdf"))

    def test_without_an_output_dir_the_command_is_unchanged(self):
        command = ["mcp-tools"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(regression._scenario_command(command, Path(tmp)), command)


class RunOutputDirTests(unittest.TestCase):
    def run_manifest(self, scenarios: list[dict]):
        seen = []

        def fake_run_cli(command):
            seen.append(command)
            return 0, {"ok": True, "summary": "ok", "errors": []}, ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            manifest = _write_manifest(Path(tmp), scenarios)
            with (
                patch.object(regression, "REGRESSION_OUTPUT_ROOT", root),
                patch.object(regression, "_run_cli", side_effect=fake_run_cli),
            ):
                ok, result, errors = regression.run_regression_manifest(manifest, profile="wps", include_wps=True)
            created = sorted(path.name for path in root.iterdir()) if root.exists() else []
            return ok, result, errors, seen, root, created

    def test_a_run_writes_outputs_to_one_new_directory_and_reports_it(self):
        ok, result, errors, seen, root, created = self.run_manifest(
            [
                _scenario("a", ["calc-smoke", "--input", "in.xlsx", "--output", "{output_dir}/a.xlsx"]),
                _scenario(
                    "b", ["convert-smoke", "--input", "in.docx", "--output", "{output_dir}/b.pdf", "--format", "pdf"]
                ),
            ]
        )

        self.assertTrue(ok, errors)
        self.assertEqual(len(created), 1)
        output_dir = Path(result["output_dir"])
        self.assertEqual(output_dir.parent, root)
        self.assertEqual(seen[0][-1], str(output_dir / "a.xlsx"))
        self.assertEqual(seen[1][4], str(output_dir / "b.pdf"))

    def test_a_run_without_the_placeholder_creates_no_directory(self):
        ok, result, errors, _seen, _root, created = self.run_manifest([_scenario("a", ["mcp-tools"])])

        self.assertTrue(ok, errors)
        self.assertIsNone(result["output_dir"])
        self.assertEqual(created, [])


class ShippedManifestTests(unittest.TestCase):
    def test_no_scenario_writes_into_the_repository_outside_the_output_dir(self):
        ok, manifest, errors = regression.load_regression_manifest()
        self.assertTrue(ok, errors)
        outputs = []
        for scenario in manifest["scenarios"]:
            command = scenario["command"]
            outputs += [command[index + 1] for index, part in enumerate(command[:-1]) if part == "--output"]

        self.assertEqual(len(outputs), 8)
        for output in outputs:
            self.assertTrue(output.startswith(regression.OUTPUT_DIR_PLACEHOLDER + "/"), output)

    def test_the_output_root_is_ignored_by_git(self):
        probe = regression.REGRESSION_OUTPUT_ROOT / "20260101T000000Z-probe" / "out.pdf"
        completed = subprocess.run(
            ["git", "check-ignore", "-q", str(probe.relative_to(regression.REPO_ROOT))],
            cwd=regression.REPO_ROOT,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 128:
            self.skipTest("not a git checkout")
        self.assertEqual(completed.returncode, 0, "artifacts/regression/outputs/ must be ignored by git")


if __name__ == "__main__":
    unittest.main()
