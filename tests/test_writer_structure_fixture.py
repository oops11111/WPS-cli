import hashlib
import unittest
from pathlib import Path

from wps_ai_agent_cli.document_text import docx_body_paragraphs
from wps_ai_agent_cli.writer_structure import read_body_bookmark_text, read_writer_structure


FIXTURE = Path("fixtures/phase3/writer_structure_wps_fixture.docx")


class WriterStructureFixtureTests(unittest.TestCase):
    def test_controlled_fixture_has_stable_offline_structure(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        structure = read_writer_structure(FIXTURE)
        self.assertEqual(docx_body_paragraphs(FIXTURE), [
            "Structure Audit", "Evidence Section", "Before Alpha after.", "Plain body text.",
        ])
        self.assertEqual([item["heading_level"] for item in structure["paragraphs"]], [1, 2, None, None])
        self.assertEqual([item["style_id"] for item in structure["paragraphs"]], ["Heading1", "Heading2", "Normal", "Normal"])
        self.assertEqual([item["name"] for item in structure["bookmarks"]], ["AuditMark"])
        self.assertEqual(read_body_bookmark_text(FIXTURE, "AuditMark")[1], "Alpha")
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
