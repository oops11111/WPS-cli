"""The matrix script's verdicts: known deviations (decision 10) pass above their floor, fail below it."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "fidelity_baselines", Path(__file__).resolve().parents[1] / "scripts" / "fidelity_baselines.py"
)
fidelity_baselines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fidelity_baselines)


def _result(layout: float, renderer: str = "wps", text_ok: bool = True) -> dict:
    return {
        "converted": True,
        "passed": False,
        "scores": {"text": 1.0 if text_ok else 0.5, "layout": layout},
        "verdict": {"text": text_ok, "layout": False},
        "layout_renderer": renderer,
    }


class KnownDeviationTests(unittest.TestCase):
    def test_a_known_deviation_passes_above_its_floor_only(self):
        floor = fidelity_baselines.KNOWN_DEVIATIONS["A-contract-docx"][0]
        self.assertEqual(fidelity_baselines.compare({"A-contract-docx": _result(floor + 0.005)}, {}), [])
        self.assertEqual(len(fidelity_baselines.compare({"A-contract-docx": _result(floor - 0.005)}, {})), 1)

    def test_only_a_wps_layout_shortfall_is_accepted(self):
        floor = fidelity_baselines.KNOWN_DEVIATIONS["A-manual-docx"][0]
        self.assertEqual(len(fidelity_baselines.compare({"A-manual-docx": _result(floor, text_ok=False)}, {})), 1)
        self.assertEqual(len(fidelity_baselines.compare({"A-manual-docx": _result(floor, "libreoffice")}, {})), 1)
        self.assertEqual(len(fidelity_baselines.compare({"A-report-docx": _result(0.89)}, {})), 1)


if __name__ == "__main__":
    unittest.main()
