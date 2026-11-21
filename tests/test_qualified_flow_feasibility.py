import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flowfeasibility", ROOT / "scripts/qualified_flow_feasibility.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class QualifiedFlowFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = m.extract()

    def test_reproduces_raw_missing_evidence_without_defaults(self):
        raw = json.loads(
            (ROOT / "artifacts/qualified-flow-feasibility-20261122/feasibility.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.result, raw)
        self.assertEqual(len(self.result["missing_guard_fields"]), 4)
        for boundary in self.result["boundaries"]:
            for style in boundary["styles"].values():
                self.assertEqual(style["break-before"], "auto")
                self.assertEqual(style["break-after"], "MISSING")

    def test_only_contract_table_enters_potential_domain(self):
        for case, tables in self.result["tables"].items():
            eligible = [i for i, table in enumerate(tables) if table["minima"] is not None]
            self.assertEqual(eligible, [1] if case == "contract" else [])

    def test_observable_geometry_does_not_cure_missing_break_proof(self):
        for boundary in self.result["boundaries"]:
            self.assertLessEqual(boundary["gap_error"], 1 / 64)
            self.assertEqual(boundary["gap"], 18.25)
            self.assertEqual(boundary["p_line"], "22px")
            self.assertEqual(boundary["h2_line"], "33px")
            self.assertLess(boundary["current_h2_before_twips"], boundary["full_h2_before_twips"])
        self.assertTrue(self.result["missing_guard_fields"])
