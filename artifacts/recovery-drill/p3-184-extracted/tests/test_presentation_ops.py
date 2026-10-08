import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from wps_ai_agent_cli.presentation_ops import presentation_replace
from wps_ai_agent_cli.presentation_text import count_text_in_pptx
from wps_ai_agent_cli.sessions import register_document


def write_minimal_pptx(path: Path, slide_texts: list[str], order: list[int] | None = None) -> None:
    order = list(range(1, len(slide_texts) + 1)) if order is None else order
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{index}"/>' for index in order)
    relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, len(slide_texts) + 1)
    )
    overrides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index, _text in enumerate(slide_texts, start=1)
    )
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
{overrides}
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/presentation.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>{slide_ids}</p:sldIdLst></p:presentation>
""",
        )
        archive.writestr("ppt/_rels/presentation.xml.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{relationships}</Relationships>')
        for index, text in enumerate(slide_texts, start=1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:r><a:t>{text}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
""",
            )


class PresentationOpsTests(unittest.TestCase):
    def test_count_text_in_pptx_reads_slide_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.pptx"
            write_minimal_pptx(path, ["alpha beta alpha", "alpha"])

            self.assertEqual(count_text_in_pptx(path, "alpha"), 3)
            self.assertEqual(count_text_in_pptx(path, "alpha", slide_index=2), 1)

    def test_presentation_replace_dry_run_reports_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.pptx"
            write_minimal_pptx(document, ["alpha beta alpha"])
            ok, record, errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            ok, result, errors, replayed = presentation_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="presentation-dry",
                dry_run=True,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["scope"], "deck")
            self.assertEqual(result["matches"], 2)
            self.assertFalse((workspace / ".wps-agent" / "backups").exists())

    def test_presentation_replace_dry_run_can_scope_to_slide(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.pptx"
            write_minimal_pptx(document, ["alpha beta", "alpha beta alpha"])
            ok, record, _errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors, replayed = presentation_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="presentation-slide-dry",
                dry_run=True,
                slide_index=1,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["scope"], "slide")
            self.assertEqual(result["slide_index"], 1)
            self.assertEqual(result["matches"], 1)

    def test_presentation_replace_rejects_out_of_range_slide(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.pptx"
            write_minimal_pptx(document, ["alpha beta"])
            ok, record, _errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok)

            ok, _result, errors, replayed = presentation_replace(
                document_id=record["document_id"],
                find_text="alpha",
                replace_text="gamma",
                request_id="presentation-slide-missing",
                dry_run=True,
                slide_index=2,
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "SLIDE_NOT_FOUND")

    def test_presentation_replace_rejects_empty_find_text(self):
        ok, result, errors, replayed = presentation_replace(
            document_id="doc_missing",
            find_text="",
            replace_text="x",
            request_id="presentation-empty",
            dry_run=True,
        )

        self.assertFalse(ok)
        self.assertFalse(replayed)
        self.assertEqual(result, {})
        self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")

    def test_presentation_replace_replays_only_identical_request_arguments(self):
        prior = {
            "command": "presentation-replace",
            "result": {
                "document_id": "doc_1", "find_text": "alpha", "replace_text": "beta",
                "slide_index": 2, "dry_run": False, "validation_passed": True,
            },
        }
        with patch("wps_ai_agent_cli.operations.get_operation", return_value=prior), patch("wps_ai_agent_cli.presentation_ops.create_backup") as backup, patch("wps_ai_agent_cli.presentation_ops._run_presentation_replace_com") as com:
            ok, result, errors, replayed = presentation_replace(
                "doc_1", "alpha", "beta", "same-request", slide_index=2,
            )
            self.assertTrue(ok)
            self.assertTrue(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result, prior["result"])
            backup.assert_not_called()
            com.assert_not_called()

            for changed in (
                {"document_id": "doc_2"},
                {"find_text": "other"},
                {"replace_text": "other"},
                {"slide_index": 1},
                {"dry_run": True},
            ):
                with self.subTest(changed=changed):
                    arguments = {"document_id": "doc_1", "find_text": "alpha", "replace_text": "beta", "slide_index": 2, "dry_run": False}
                    arguments.update(changed)
                    ok, result, errors, replayed = presentation_replace(
                        arguments.pop("document_id"), arguments.pop("find_text"),
                        arguments.pop("replace_text"), "same-request", **arguments,
                    )
                    self.assertFalse(ok)
                    self.assertFalse(replayed)
                    self.assertEqual(errors[0]["code"], "IDEMPOTENCY_CONFLICT")
                    self.assertTrue(result["conflicting_fields"])
            backup.assert_not_called()
            com.assert_not_called()


if __name__ == "__main__":
    unittest.main()
