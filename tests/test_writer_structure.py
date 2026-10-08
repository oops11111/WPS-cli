import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.snapshots import snapshot_document
from wps_ai_agent_cli.writer_structure import W, read_body_bookmark_text, read_supported_bookmark_text, read_writer_structure


def write_document(path, body, styles=None, header=None):
    namespace = W[1:-1]
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{namespace}"><w:body>{body}</w:body></w:document>')
        if styles is not None:
            archive.writestr("word/styles.xml", f'<w:styles xmlns:w="{namespace}">{styles}</w:styles>')
        if header is not None:
            archive.writestr("word/header1.xml", f'<w:hdr xmlns:w="{namespace}">{header}</w:hdr>')


class WriterStructureTests(unittest.TestCase):
    def test_snapshot_resolves_custom_headings_and_direct_override_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''
                <w:p><w:pPr><w:pStyle w:val="Custom"/></w:pPr><w:r><w:t>Title</w:t></w:r></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
                <w:p><w:pPr><w:pStyle w:val="Custom"/><w:outlineLvl w:val="9"/></w:pPr><w:r><w:t>Body</w:t></w:r></w:p>
            ''', '''
                <w:style w:type="paragraph" w:styleId="Base"><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
                <w:style w:type="paragraph" w:styleId="Custom"><w:name w:val="Report Title"/><w:basedOn w:val="Base"/></w:style>
            ''')
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            _, record, _ = register_document("writer", str(path), tmp)
            ok, result, errors = snapshot_document(record["document_id"], tmp)
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["paragraph_count"], 2)
            self.assertEqual(result["heading_count"], 1)
            self.assertEqual(result["headings"][0]["heading_level"], 2)
            self.assertEqual(result["headings"][0]["style_name"], "Report Title")
            self.assertEqual(result["headings"][0]["outline_source"], "style:Base")
            self.assertEqual(result["paragraphs"][1]["paragraph_index"], 2)
            self.assertEqual(result["paragraphs"][1]["outline_level"], 9)
            self.assertIsNone(result["paragraphs"][1]["heading_level"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_defaults_and_cycle_and_missing_style_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''
                <w:p/>
                <w:p><w:pPr><w:pStyle w:val="A"/></w:pPr></w:p>
                <w:p><w:pPr><w:pStyle w:val="Missing"/></w:pPr></w:p>
                <w:p><w:pPr><w:outlineLvl w:val="invalid"/></w:pPr></w:p>
            ''', '''
                <w:docDefaults><w:pPrDefault><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:pPrDefault></w:docDefaults>
                <w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>
                <w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/></w:style>
                <w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style>
            ''')
            result = read_writer_structure(path)
            self.assertEqual(result["paragraphs"][0]["style_id"], "Normal")
            self.assertFalse(result["paragraphs"][0]["style_is_explicit"])
            self.assertEqual(result["paragraphs"][0]["heading_level"], 3)
            self.assertEqual(result["paragraphs"][1]["style_resolution"], "cycle")
            self.assertEqual(result["paragraphs"][2]["style_resolution"], "missing_style")
            self.assertIsNone(result["paragraphs"][2]["heading_level"])
            self.assertIsNone(result["paragraphs"][3]["outline_level"])
            self.assertEqual({w["code"] for w in result["warnings"]}, {"CYCLE", "MISSING_STYLE", "INVALID_OUTLINE_LEVEL"})

    def test_missing_styles_do_not_infer_heading_from_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr></w:p><w:p/>')
            result = read_writer_structure(path)
            self.assertIsNone(result["paragraphs"][0]["heading_level"])
            self.assertEqual(result["paragraphs"][0]["style_resolution"], "missing_style")
            self.assertEqual(result["paragraphs"][1]["style_resolution"], "none")

    def test_duplicate_style_definitions_do_not_select_arbitrary_heading_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '<w:p><w:pPr><w:pStyle w:val="Heading"/></w:pPr></w:p>', '''
                <w:style w:type="paragraph" w:styleId="Heading"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
                <w:style w:type="paragraph" w:styleId="Heading"><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>
            ''')
            result = read_writer_structure(path)
            self.assertIsNone(result["paragraphs"][0]["heading_level"])
            self.assertEqual(result["paragraphs"][0]["style_resolution"], "duplicate_style")
            self.assertEqual(result["warnings"][0]["code"], "DUPLICATE_STYLE")

    def test_bookmark_pairing_across_paragraphs_and_other_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''
                <w:p><w:bookmarkStart w:id="1" w:name="Span"/><w:r><w:t>One</w:t></w:r></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:bookmarkStart w:id="2" w:name="Cell"/><w:bookmarkEnd w:id="2"/></w:p></w:tc></w:tr></w:tbl>
                <w:p><w:bookmarkEnd w:id="1"/><w:r><w:t>Two</w:t></w:r>
                    <w:r><w:txbxContent><w:p><w:bookmarkStart w:id="3" w:name="Box"/><w:bookmarkEnd w:id="3"/></w:p></w:txbxContent></w:r>
                </w:p>
            ''', header='<w:p><w:bookmarkStart w:id="1" w:name="Header"/><w:bookmarkEnd w:id="1"/></w:p>')
            result = read_writer_structure(path)
            bookmarks = {b["name"]: b for b in result["bookmarks"]}
            self.assertEqual(bookmarks["Span"]["start"]["paragraph_index"], 1)
            self.assertEqual(bookmarks["Span"]["end"]["paragraph_index"], 2)
            self.assertFalse(bookmarks["Span"]["body_paragraph_range_supported"])
            for name, scope in [("Cell", "table"), ("Box", "text_box"), ("Header", "header_footer")]:
                self.assertEqual(bookmarks[name]["status"], "paired")
                self.assertEqual(bookmarks[name]["start"]["scope"], scope)
                self.assertIsNone(bookmarks[name]["start"]["paragraph_index"])
                self.assertFalse(bookmarks[name]["body_paragraph_range_supported"])

    def test_same_paragraph_bookmark_has_character_offsets_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''<w:p><w:r><w:t>before </w:t></w:r>
                <w:bookmarkStart w:id="5" w:name="Field"/>
                <w:r><w:t>old </w:t></w:r><w:bookmarkEnd w:id="5"/>
                <w:r><w:t>after</w:t></w:r></w:p>''')
            bookmark, value = read_body_bookmark_text(path, "Field")
            self.assertEqual(value, "old ")
            self.assertTrue(bookmark["body_paragraph_range_supported"])
            self.assertEqual(bookmark["start"]["text_offset"], 7)
            self.assertEqual(bookmark["end"]["text_offset"], 11)

    def test_duplicate_name_is_visible_to_fill_resolver(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''<w:p><w:bookmarkStart w:id="1" w:name="Repeat"/><w:r><w:t>A</w:t></w:r><w:bookmarkEnd w:id="1"/>
                <w:bookmarkStart w:id="2" w:name="Repeat"/><w:r><w:t>B</w:t></w:r><w:bookmarkEnd w:id="2"/></w:p>''')
            self.assertEqual(read_body_bookmark_text(path, "Repeat"), (None, None))
            self.assertEqual(read_supported_bookmark_text(path, "Repeat"), (None, None))

    def test_nested_bookmark_offsets_include_special_text_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "special.docx"
            write_document(path, '''<w:tbl><w:tr><w:tc><w:p>
                <w:r><w:noBreakHyphen/><w:softHyphen/></w:r>
                <w:bookmarkStart w:id="1" w:name="Special"/>
                <w:r><w:t>Value</w:t></w:r><w:bookmarkEnd w:id="1"/>
            </w:p></w:tc></w:tr></w:tbl>''')
            bookmark, value = read_supported_bookmark_text(path, "Special")
            self.assertTrue(bookmark["text_range_supported"])
            self.assertEqual(bookmark["start"]["text_offset"], 2)
            self.assertEqual(value, "Value")

    def test_invalid_bookmarks_are_not_claimed_as_supported_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            write_document(path, '''<w:p>
                <w:bookmarkStart w:id="1" w:name="Unclosed"/>
                <w:bookmarkEnd w:id="2"/>
                <w:bookmarkEnd w:id="3"/><w:bookmarkStart w:id="3" w:name="Reversed"/>
                <w:bookmarkStart w:id="4" w:name="Dup"/><w:bookmarkStart w:id="4" w:name="DupAgain"/><w:bookmarkEnd w:id="4"/>
            </w:p>''')
            bookmarks = {b["id"]: b for b in read_writer_structure(path)["bookmarks"]}
            self.assertEqual([bookmarks[str(i)]["status"] for i in range(1, 5)], ["missing_end", "missing_start", "reversed", "ambiguous"])
            self.assertFalse(any(b["body_paragraph_range_supported"] for b in bookmarks.values()))

    def test_cross_paragraph_and_cross_cell_bookmarks_remain_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cross.docx"
            write_document(path, '''
                <w:p><w:bookmarkStart w:id="1" w:name="CrossBody"/><w:r><w:t>One</w:t></w:r></w:p>
                <w:p><w:r><w:t>Two</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>
                <w:tbl><w:tr>
                  <w:tc><w:p><w:bookmarkStart w:id="2" w:name="CrossCell"/><w:r><w:t>Left</w:t></w:r></w:p></w:tc>
                  <w:tc><w:p><w:r><w:t>Right</w:t></w:r><w:bookmarkEnd w:id="2"/></w:p></w:tc>
                </w:tr></w:tbl>
            ''', header='''<w:p><w:bookmarkStart w:id="3" w:name="CrossHeader"/><w:r><w:t>A</w:t></w:r></w:p>
                <w:p><w:r><w:t>B</w:t></w:r><w:bookmarkEnd w:id="3"/></w:p>''')
            bookmarks = {item["name"]: item for item in read_writer_structure(path)["bookmarks"]}
            self.assertEqual(set(bookmarks), {"CrossBody", "CrossCell", "CrossHeader"})
            for name, bookmark in bookmarks.items():
                with self.subTest(name=name):
                    self.assertEqual(bookmark["status"], "paired")
                    self.assertFalse(bookmark["text_range_supported"])
                    self.assertIsNone(read_supported_bookmark_text(path, name)[1])

    def test_header_text_box_bookmark_remains_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "header-box.docx"
            write_document(path, '<w:p/>', header='''<w:p><w:r><w:txbxContent><w:p>
                <w:bookmarkStart w:id="1" w:name="HeaderBox"/><w:r><w:t>Hidden</w:t></w:r>
                <w:bookmarkEnd w:id="1"/></w:p></w:txbxContent></w:r></w:p>''')
            bookmark, value = read_supported_bookmark_text(path, "HeaderBox")
            self.assertEqual(bookmark["start"]["scope"], "text_box")
            self.assertFalse(bookmark["text_range_supported"])
            self.assertIsNone(value)

    def test_revision_containers_do_not_yield_supported_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "revisions.docx"
            write_document(path, '''
                <w:p><w:del><w:bookmarkStart w:id="1" w:name="Deleted"/>
                    <w:r><w:delText>Old</w:delText></w:r><w:bookmarkEnd w:id="1"/></w:del></w:p>
                <w:p><w:ins><w:r><w:t>New</w:t></w:r></w:ins>
                    <w:bookmarkStart w:id="2" w:name="AfterInsertion"/>
                    <w:r><w:t>Value</w:t></w:r><w:bookmarkEnd w:id="2"/></w:p>
                <w:p><w:bookmarkStart w:id="3" w:name="AcrossBox"/>
                    <w:r><w:t>A</w:t></w:r><w:r><w:txbxContent><w:p><w:r><w:t>Box</w:t></w:r></w:p></w:txbxContent></w:r>
                    <w:r><w:t>B</w:t></w:r><w:bookmarkEnd w:id="3"/></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:moveFrom><w:bookmarkStart w:id="4" w:name="Moved"/>
                    <w:r><w:t>Old</w:t></w:r><w:bookmarkEnd w:id="4"/></w:moveFrom></w:p></w:tc></w:tr></w:tbl>
            ''')
            bookmarks = {item["name"]: item for item in read_writer_structure(path)["bookmarks"]}
            self.assertEqual(bookmarks["Deleted"]["start"]["scope"], "revision_excluded")
            self.assertNotIn("text_offset", bookmarks["Deleted"]["start"])
            self.assertEqual(bookmarks["Moved"]["start"]["scope"], "revision_excluded")
            for name in bookmarks:
                with self.subTest(name=name):
                    self.assertFalse(bookmarks[name]["text_range_supported"])
                    self.assertFalse(bookmarks[name]["body_paragraph_range_supported"])
                    self.assertIsNone(read_supported_bookmark_text(path, name)[1])

    def test_mixed_run_bookmark_text_in_table_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.docx"
            write_document(path, '''<w:tbl><w:tr><w:tc><w:p>
                <w:r><w:t>Before </w:t></w:r><w:bookmarkStart w:id="1" w:name="Mixed"/>
                <w:r><w:t>A</w:t></w:r>
                <w:hyperlink w:anchor="target"><w:r><w:t>B</w:t></w:r></w:hyperlink>
                <w:r><w:tab/><w:t>C</w:t><w:br/><w:noBreakHyphen/><w:softHyphen/></w:r>
                <w:bookmarkEnd w:id="1"/><w:r><w:t> After</w:t></w:r>
            </w:p></w:tc></w:tr></w:tbl>''')
            bookmark, value = read_supported_bookmark_text(path, "Mixed")
            self.assertTrue(bookmark["text_range_supported"])
            self.assertEqual(bookmark["start"]["text_offset"], 7)
            self.assertEqual({key: bookmark["start"][key] for key in ("table_index", "row", "column")},
                             {"table_index": 1, "row": 1, "column": 1})
            self.assertEqual(value, "AB\tC\n\u2011\u00ad")


if __name__ == "__main__":
    unittest.main()
