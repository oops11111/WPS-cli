"""PDF page tools: info, merge, split, extract pages, watermark (C-02)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import pypdf
except ImportError as exc:  # optional test dependency: skip this module instead of erroring the suite
    raise unittest.SkipTest("pypdf is not installed") from exc

from wps_ai_agent_cli import pdf_tools
from wps_ai_agent_cli.cli import run

A4 = (595.0, 842.0)
LANDSCAPE = (842.0, 595.0)


def write_pdf(path: Path, sizes, encrypt: str | None = None, owner: str | None = None) -> Path:
    writer = pypdf.PdfWriter()
    for width, height in sizes:
        writer.add_blank_page(width=width, height=height)
    writer.add_metadata({"/Title": "Fixture"})
    if encrypt is not None:
        writer.encrypt(user_password=encrypt, owner_password=owner or encrypt)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def sizes_of(path: Path):
    return [(float(page.mediabox.width), float(page.mediabox.height)) for page in pypdf.PdfReader(str(path)).pages]


class PdfToolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        # Five pages whose sizes tell them apart: page n is n points taller than A4.
        self.source = write_pdf(self.root / "book.pdf", [(595.0, 842.0 + n) for n in range(1, 6)])

    def test_info_reports_pages_sizes_and_the_missing_text_layer(self):
        write_pdf(self.root / "mixed.pdf", [A4, A4, LANDSCAPE])
        ok, data, errors = pdf_tools.pdf_info(self.root / "mixed.pdf")
        self.assertTrue(ok, errors)
        self.assertEqual(data["pages"], 3)
        by_orientation = {size["orientation"]: size for size in data["page_sizes"]}
        self.assertEqual(by_orientation["portrait"]["paper"], "A4")
        self.assertEqual(by_orientation["portrait"]["count"], 2)
        self.assertEqual(by_orientation["landscape"]["count"], 1)
        self.assertEqual(data["metadata"]["title"], "Fixture")
        self.assertTrue(data["likely_scanned"])  # blank pages carry no text

    def test_merge_keeps_the_order_and_every_page(self):
        other = write_pdf(self.root / "other.pdf", [LANDSCAPE])
        ok, data, errors = pdf_tools.pdf_merge([str(other), str(self.source)], self.root / "all.pdf")
        self.assertTrue(ok, errors)
        self.assertEqual(sizes_of(self.root / "all.pdf"), [LANDSCAPE] + sizes_of(self.source))
        self.assertTrue(data["validation_passed"])

    def test_merge_needs_two_inputs_and_a_new_output(self):
        ok, _data, errors = pdf_tools.pdf_merge([str(self.source)], self.root / "one.pdf")
        self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
        ok, _data, errors = pdf_tools.pdf_merge([str(self.source), str(self.source)], self.source)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "INVALID_OUTPUT")

    def test_extract_keeps_the_order_given(self):
        ok, data, errors = pdf_tools.pdf_extract_pages(self.source, self.root / "pick.pdf", "4-,1，2")
        self.assertTrue(ok, errors)
        self.assertEqual(data["pages"], [4, 5, 1, 2])
        heights = [height for _width, height in sizes_of(self.root / "pick.pdf")]
        self.assertEqual(heights, [846.0, 847.0, 843.0, 844.0])

    def test_page_lists_are_checked(self):
        for spec in ("", "0", "6", "3-2", "a", "1;2"):
            with self.subTest(spec=spec):
                ok, _data, errors = pdf_tools.pdf_extract_pages(self.source, self.root / f"x{len(spec)}.pdf", spec)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "PAGE_RANGE_INVALID")
        self.assertEqual(list(self.root.glob("x*.pdf")), [])

    def test_split_every_n_pages_and_by_ranges(self):
        out = self.root / "parts"
        out.mkdir()
        ok, data, errors = pdf_tools.pdf_split(self.source, out, every=2)
        self.assertTrue(ok, errors)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["book_p1-2.pdf", "book_p3-4.pdf", "book_p5.pdf"])
        ranged = self.root / "ranged"
        ranged.mkdir()
        ok, data, errors = pdf_tools.pdf_split(self.source, ranged, ranges="1,2-3,4-")
        self.assertTrue(ok, errors)
        self.assertEqual([output["source_pages"] for output in data["outputs"]], [[1], [2, 3], [4, 5]])

    def test_split_writes_nothing_when_one_name_is_taken(self):
        out = self.root / "parts"
        out.mkdir()
        (out / "book_p3.pdf").write_bytes(b"theirs")
        ok, _data, errors = pdf_tools.pdf_split(self.source, out)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
        self.assertEqual([p.name for p in out.iterdir()], ["book_p3.pdf"])

    def test_split_removes_what_it_wrote_when_a_later_file_fails(self):
        out = self.root / "parts"
        out.mkdir()
        real_write = pdf_tools._write
        calls = []

        def fail_on_third(writer, destination):
            calls.append(destination)
            if len(calls) == 3:
                raise pdf_tools._Refusal("OUTPUT_WRITE_FAILED", "disk full")
            real_write(writer, destination)

        with patch.object(pdf_tools, "_write", side_effect=fail_on_third):
            ok, _data, errors = pdf_tools.pdf_split(self.source, out)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "OUTPUT_WRITE_FAILED")
        self.assertEqual(list(out.iterdir()), [])

    def test_watermark_draws_the_text_on_the_chosen_pages(self):
        ok, data, errors = pdf_tools.pdf_watermark(self.source, self.root / "wm.pdf", "内部资料 Draft", pages="2-3")
        self.assertTrue(ok, errors)
        reader = pypdf.PdfReader(str(self.root / "wm.pdf"))
        texts = [page.extract_text() or "" for page in reader.pages]
        self.assertEqual(["内部资料 Draft" in text for text in texts], [False, True, True, False, False])
        self.assertEqual(sizes_of(self.root / "wm.pdf"), sizes_of(self.source))
        resources = reader.pages[1]["/Resources"]
        self.assertEqual(resources["/ExtGState"]["/WmGS"]["/ca"], 0.15)
        self.assertEqual(resources["/Font"]["/WmF"]["/BaseFont"], "/STSong-Light")

    def test_watermark_text_and_settings_are_checked(self):
        for options in (
            {"text": ""},
            {"text": "a\nb"},
            {"text": "x" * 101},
            {"text": "😀"},
            {"text": "x", "opacity": 0},
        ):
            with self.subTest(options=options):
                ok, _data, errors = pdf_tools.pdf_watermark(self.source, self.root / "bad.pdf", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
        self.assertFalse((self.root / "bad.pdf").exists())

    def test_encrypted_and_damaged_inputs_are_refused(self):
        write_pdf(self.root / "locked.pdf", [A4], encrypt="secret")
        ok, _data, errors = pdf_tools.pdf_info(self.root / "locked.pdf")
        self.assertEqual(errors[0]["code"], "PDF_ENCRYPTED")
        (self.root / "broken.pdf").write_bytes(b"not a pdf")
        ok, _data, errors = pdf_tools.pdf_info(self.root / "broken.pdf")
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "INVALID_INPUT")

    def test_an_open_password_of_nothing_is_not_a_lock(self):
        write_pdf(self.root / "owner-only.pdf", [A4], encrypt="", owner="owner")
        ok, data, errors = pdf_tools.pdf_info(self.root / "owner-only.pdf")
        self.assertTrue(ok, errors)
        self.assertTrue(data["encrypted"])

    def test_existing_outputs_are_never_overwritten(self):
        target = self.root / "taken.pdf"
        target.write_bytes(b"theirs")
        ok, _data, errors = pdf_tools.pdf_extract_pages(self.source, target, "1")
        self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
        self.assertEqual(target.read_bytes(), b"theirs")

    def test_the_workspace_boundary_applies_to_outputs(self):
        inside = self.root / "inside"
        inside.mkdir()
        source = write_pdf(inside / "in.pdf", [A4])
        with patch.dict(os.environ, {"WPS_AGENT_WORKSPACE_ROOT": str(inside)}):
            ok, _data, errors = pdf_tools.pdf_extract_pages(source, self.root / "out.pdf", "1")
        self.assertEqual(errors[0]["code"], "PATH_OUTSIDE_WORKSPACE")

    def test_without_pypdf_the_extra_is_named(self):
        with patch.object(pdf_tools, "_pypdf", return_value=None):
            ok, _data, errors = pdf_tools.pdf_info(self.source)
        self.assertEqual(errors[0]["code"], "CONVERTER_UNAVAILABLE")
        self.assertIn("pypdf", errors[0]["message"])

    def test_the_cli_merges_repeated_inputs(self):
        other = write_pdf(self.root / "other.pdf", [A4])
        stream = io.StringIO()
        code = run(
            ["pdf-merge", "--input", str(self.source), "--input", str(other), "--output", str(self.root / "m.pdf")],
            output_stream=stream,
        )
        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["data"]["outputs"][0]["pages"], 6)


if __name__ == "__main__":
    unittest.main()
