"""Fixed six inputs, one-property packages and preregistered STOP conditions."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "cellspacing", Path(__file__).resolve().parents[1] / "scripts/horizontal_cell_spacing_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class CellSpacingMechanismTests(unittest.TestCase):
    def test_fixed_sources_and_pair_xml(self):
        for h in m.H_VALUES:
            source = m.ROOT / f"artifacts/horizontal-cell-spacing-20261121/H{h}/control.docx"
            with ZipFile(source) as z:
                old = z.read("word/document.xml")
            new = m.patch_xml(old, h * 15)
            root = m.ET.fromstring(new)
            spacing = root.find(".//" + m.W + "tblPr/" + m.W + "tblCellSpacing")
            self.assertEqual(spacing.get(m.W + "w"), str(h * 15))
            spacing.getparent().remove(spacing)
            self.assertEqual(m.ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), old)
            with self.assertRaises(ValueError):
                m.patch_xml(new, h * 15)

    def test_deterministic_other_parts(self):
        with tempfile.TemporaryDirectory() as d:
            source = m.ROOT / "artifacts/horizontal-cell-spacing-20261121/H2/control.docx"
            a, b = Path(d) / "a.docx", Path(d) / "b.docx"
            m.candidate(source, a, 30)
            m.candidate(source, b, 30)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with ZipFile(source) as x, ZipFile(a) as y:
                self.assertTrue(all(x.read(n) == y.read(n) for n in x.namelist() if n != "word/document.xml"))

    def test_vertical_horizontal_and_zero_gate(self):
        g = {
            "pages": 1,
            "relative_x": {"LEFT": 9, "RIGHT": 159.75},
            "tokens": {
                t: {"top": v, "baseline": v + 10}
                for t, v in [("BEFORE", 0), ("LEFT", 13.5), ("RIGHT", 13.5), ("FOLLOWING", 27)]
            },
        }
        self.assertTrue(all(m.pair_gates(g, g, 0, True).values()))
        self.assertFalse(m.pair_gates(g, g, 0, False)["h0_pixels"])
        n = copy.deepcopy(g)
        n["relative_x"] = {"LEFT": 10.5, "RIGHT": 162.75}
        self.assertTrue(all(m.pair_gates(g, n, 2, False).values()))
        n["tokens"]["FOLLOWING"]["top"] += 0.1
        self.assertFalse(m.pair_gates(g, n, 2, False)["following_y"])
        n["tokens"]["LEFT"]["baseline"] += 0.1
        self.assertFalse(m.pair_gates(g, n, 2, False)["cell_y"])


if __name__ == "__main__":
    unittest.main()
