"""The committed inventory of the public interface matches the code (P12-006)."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from wps_ai_agent_cli.public_interface import build_inventory, diff_inventories

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "config" / "public_interface.json"


def _script():
    spec = importlib.util.spec_from_file_location(
        "public_interface_script", REPO_ROOT / "scripts" / "public_interface.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicInterfaceTests(unittest.TestCase):
    def test_the_committed_inventory_matches_the_code(self):
        committed = json.loads(INVENTORY.read_text(encoding="utf-8"))
        current = build_inventory()
        changes = diff_inventories(committed, current)
        self.assertEqual(
            committed,
            current,
            "The public interface changed. Review the changes below against docs/RELEASING.md, then run "
            "python scripts/public_interface.py --write:\n" + "\n".join(changes),
        )

    def test_the_inventory_covers_every_command_tool_and_error_code_in_use(self):
        inventory = build_inventory()
        self.assertEqual(
            set(inventory["cli_commands"]), {tool["cli_command"] for tool in inventory["mcp_tools"].values()}
        )
        self.assertIn("writer-selection-replace", inventory["cli_commands"])
        arguments = {item["name"] for item in inventory["cli_commands"]["writer-selection-replace"]}
        self.assertTrue({"--document-id", "--text"} <= arguments)
        self.assertIn("--request-id", {item["name"] for item in inventory["cli_global_options"]})
        tool = inventory["mcp_tools"]["wps_agent_writer_selection_replace"]
        self.assertTrue(tool["mutates_document"])
        self.assertIn("document_id", tool["required"])
        for code in ("DOCUMENT_HELD_OPEN", "SELECTION_MISMATCH", "MUTATION_ROLLED_BACK", "VALIDATION_FAILED"):
            self.assertIn(code, inventory["error_codes"])

    def test_removals_are_marked_breaking_and_additions_are_not(self):
        old = {"cli_commands": {"a": [], "b": []}, "mcp_tools": {}, "error_codes": ["X_FAILED", "Y_FAILED"]}
        new = {
            "cli_commands": {"a": [{"name": "--n"}], "c": []},
            "mcp_tools": {},
            "error_codes": ["X_FAILED", "Z_FAILED"],
        }
        self.assertEqual(
            diff_inventories(old, new),
            [
                "breaking: cli_commands b removed",
                "added: cli_commands c",
                "changed: cli_commands a",
                "breaking: error code Y_FAILED removed",
                "added: error code Z_FAILED",
            ],
        )

    def test_the_check_script_passes_on_the_committed_file(self):
        self.assertEqual(_script().main([]), 0)


if __name__ == "__main__":
    unittest.main()
