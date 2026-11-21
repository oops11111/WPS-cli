"""Formal WPS evidence must distinguish F2 from known exceptions and unavailable gates."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("html_docx_wps_matrix", ROOT / "scripts/html_docx_wps_matrix.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)


def semantic(**verdict):
    return {
        "group": "A",
        "verdict": {"text": True, "structure": True, "formatting": True, **verdict},
        "aspects": {name: {"score": 1.0} for name in ("text", "structure", "formatting")},
    }


def layout(score, renderer="wps"):
    return {"status": "measured", "renderer": renderer, "score": score}


class MatrixGateTests(unittest.TestCase):
    def test_scope_is_exactly_the_five_existing_docx_inputs(self):
        self.assertEqual(
            [c for c, _ in matrix.CASES],
            ["A-report-docx", "A-contract-docx", "A-newsletter-docx", "A-manual-docx", "A-pdfsource-docx"],
        )
        self.assertTrue(all((ROOT / source).is_file() for _, source in matrix.CASES))

    def test_known_floors_are_never_reported_as_strict_f2_passes(self):
        for case, floor in (("A-contract-docx", 0.84), ("A-manual-docx", 0.88)):
            with self.subTest(case=case):
                result = matrix.acceptance(case, semantic(), layout(floor))
                self.assertFalse(result["strict_f2"]["passed"])
                self.assertEqual(result["decision10"]["status"], "known_deviation")
                self.assertEqual(
                    matrix.acceptance(case, semantic(), layout(floor - 0.001))["decision10"]["status"], "not_accepted"
                )
        self.assertEqual(
            matrix.acceptance("A-report-docx", semantic(), layout(0.89))["decision10"]["status"], "not_accepted"
        )

    def test_exception_requires_only_layout_failure_with_official_renderer(self):
        for result in (
            matrix.acceptance("A-contract-docx", semantic(data=False), layout(0.85)),
            matrix.acceptance("A-contract-docx", semantic(), layout(0.85, "libreoffice")),
            matrix.acceptance("A-contract-docx", semantic(), {"status": "unavailable"}),
            matrix.acceptance("A-contract-docx", {}, layout(0.85)),
        ):
            self.assertEqual(result["decision10"]["status"], "not_accepted")
            self.assertFalse(result["strict_f2"]["passed"])
        self.assertFalse(
            matrix.acceptance("A-report-docx", semantic(), layout(0.95, "libreoffice"))["strict_f2"]["passed"]
        )

    def test_strict_pass_keeps_the_official_threshold(self):
        result = matrix.acceptance("A-contract-docx", semantic(), layout(0.90))
        self.assertTrue(result["strict_f2"]["passed"])
        self.assertEqual(result["decision10"]["status"], "strict_pass")
        self.assertEqual(result["strict_f2"]["layout_minimum"], 0.90)

    def test_original_missing_stylesheet_is_reported_without_fabrication(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, manifest = matrix.copy_inputs(ROOT / "fixtures/html_complex/report.html", Path(tmp) / "input")
            missing = next(e for e in manifest if e["reference"] == "print.css")
            self.assertFalse(missing["exists"])
            self.assertFalse((source.parent / "print.css").exists())
            self.assertEqual(source.read_bytes(), (ROOT / "fixtures/html_complex/report.html").read_bytes())
            self.assertTrue(next(e for e in manifest if e["reference"] == "chart.png")["exists"])

    def test_existing_wps_blocks_all_exports_and_keeps_not_run_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence"
            with (
                mock.patch.object(matrix, "probe_wps", return_value=({}, {"processes": [{"Id": 1}]})),
                mock.patch.object(matrix, "run_case") as run,
                mock.patch("sys.argv", ["matrix", "--out", str(out)]),
            ):
                matrix.main()
                run.assert_not_called()
            import json

            report = json.loads((out / "matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(report["not_run"], [c for c, _ in matrix.CASES])
            self.assertEqual(report["cases"], {})
