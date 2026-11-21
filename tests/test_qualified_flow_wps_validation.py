import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flowwps", ROOT / "scripts/qualified_flow_wps_validation.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class QualifiedFlowNativeTests(unittest.TestCase):
    def test_retry_is_blocked_before_any_native_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "wps-manifest.json").write_text("{}", encoding="utf-8")
            with patch.object(m, "probe_wps") as probe, patch.object(m, "wps_convert") as export:
                with self.assertRaises(ValueError):
                    m.run(out)
                probe.assert_not_called()
                export.assert_not_called()

    def test_missing_seal_stops_without_native_export(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(m, "probe_wps") as probe, patch.object(m, "wps_convert") as export:
                m.run(out)
                probe.assert_not_called()
                export.assert_not_called()
            result = json.loads((out / "wps-manifest.json").read_text())
            self.assertEqual(result["outcome"], "STOP")
            self.assertEqual(result["attempted_exports"], [])
            self.assertEqual(len(result["not_run"]), 5)

    def test_contract_requires_all_frozen_gates_and_strict_floor(self):
        folder = m.BASE / "A-contract-docx"
        detail = json.loads(
            (ROOT / "artifacts/contract-spacing-interaction-20261121/acceptance.json").read_text(encoding="utf-8")
        )
        semantic = json.loads(
            (ROOT / "artifacts/contract-spacing-interaction-20261121/export-semantics.json").read_text(encoding="utf-8")
        )["candidate"]
        layout = {"score": 0.9236, "page_scores": [0.9236]}
        with (
            patch.object(m, "semantic_snapshot", return_value=semantic),
            patch.object(m, "score_layout", return_value=layout),
            patch.object(m, "assess_contract", return_value=detail),
        ):
            self.assertTrue(m.compare("A-contract-docx", folder, None)["accepted"])
            changed = copy.deepcopy(detail)
            changed["gates"]["transfer"] = False
            with patch.object(m, "assess_contract", return_value=changed):
                self.assertFalse(m.compare("A-contract-docx", folder, None)["accepted"])
            with patch.object(m, "score_layout", return_value={"score": 0.895, "page_scores": [0.895]}):
                self.assertFalse(m.compare("A-contract-docx", folder, None)["accepted"])

    def test_other_case_archived_rgb_and_text_self_controls(self):
        path = m.BASE / "A-report-docx/wps.pdf"
        self.assertTrue(m.source_pixels_equal(path, path))
        self.assertTrue(m.unchanged_text(path, path))
