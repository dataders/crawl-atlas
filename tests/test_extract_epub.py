import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("extract_epub", Path("scripts/extract_epub.py"))
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractorTests(unittest.TestCase):
    def test_classifies_compound_candidate(self):
        kinds = MODULE.classify("Reward: received boots. You are now level 2.")
        self.assertIn("reward", kinds)
        self.assertIn("item", kinds)
        self.assertIn("level", kinds)

    def test_parser_keeps_block_order(self):
        parser = MODULE.BlockParser()
        parser.feed("<title>Chapter 4</title><p>First</p><p><b>Level 2.</b></p>")
        self.assertEqual(parser.title, "Chapter 4")
        self.assertEqual([block.text for block in parser.blocks], ["First", "Level 2."])
        self.assertTrue(parser.blocks[1].bold)

    def test_bold_unknown_block_is_kept_for_review(self):
        self.assertEqual(MODULE.classify("Enchanted Oddity", bold=True), ["system"])

    def test_recognizes_recent_bracketed_chapter_heading(self):
        blocks = [MODULE.Block(text="[ 98 ]", bold=False)]
        self.assertEqual(MODULE.chapter_number("c6T", blocks), 98)

    def test_extracts_spine_chapters_and_review_candidates(self):
        container = """<?xml version="1.0"?>
        <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
          <rootfiles><rootfile full-path="OPS/package.opf"/></rootfiles>
        </container>"""
        package = """<?xml version="1.0"?>
        <package xmlns="http://www.idpf.org/2007/opf">
          <manifest>
            <item id="front" href="front.xhtml"/>
            <item id="chapter" href="chapter.xhtml"/>
          </manifest>
          <spine><itemref idref="front"/><itemref idref="chapter"/></spine>
        </package>"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            epub = root / "sample.epub"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr("META-INF/container.xml", container)
                archive.writestr("OPS/package.opf", package)
                archive.writestr("OPS/front.xhtml", "<html><head><title>Cover</title></head></html>")
                archive.writestr(
                    "OPS/chapter.xhtml",
                    "<html><head><title>Chapter 1</title></head>"
                    "<body><h1>1</h1><p>Opening.</p><p><b>Enchanted Oddity</b></p></body></html>",
                )

            corpus_path, candidates_path = MODULE.extract(epub, root / "private")
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))

        self.assertEqual(len(corpus["chapters"]), 1)
        self.assertEqual(corpus["chapters"][0]["number"], 1)
        self.assertEqual(corpus["chapters"][0]["paragraphs"][-1]["anchor"], "b1-c1-p3")
        self.assertEqual(candidates[0]["kinds"], ["system"])
        self.assertEqual(candidates[0]["anchor"], "b1-c1-p3")

    def test_supplemental_sections_preserve_anchors_and_require_reveal_review(self):
        container = '<container><rootfiles><rootfile full-path="OPS/package.opf"/></rootfiles></container>'
        documents = [
            ('prologue.xhtml', 'Prologue', '<h1>Prologue</h1><p>Level 8.</p>'),
            ('one.xhtml', 'Chapter 1', '<h1>1</h1><p>Opening.</p>'),
            ('interlude.xhtml', 'i9', '<h1>Another perspective</h1><p>A skill appears.</p>'),
            ('two.xhtml', 'Chapter 2', '<h1>2</h1><p>Next.</p>'),
            ('epilogue.xhtml', 'Epilogue', '<h1>Epilogue</h1><p>Level 15.</p>'),
            ('back.xhtml', 'Back matter', '<div>Text outside supported paragraph tags.</div>'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / 'sections.epub'
            with zipfile.ZipFile(epub, 'w') as archive:
                archive.writestr('META-INF/container.xml', container)
                manifest = ''.join(f'<item id="d{i}" href="{name}"/>' for i,(name,_,_) in enumerate(documents))
                spine = ''.join(f'<itemref idref="d{i}"/>' for i in range(len(documents)))
                archive.writestr('OPS/package.opf', f'<package><manifest>{manifest}</manifest><spine>{spine}</spine></package>')
                for name,title,body in documents:
                    archive.writestr('OPS/'+name, f'<html><head><title>{title}</title></head><body>{body}</body></html>')
            legacy_chapters, legacy_candidates = MODULE.extract_book(epub, book_number=6)
            corpus, candidates, supplemental_candidates = MODULE.extract_book_complete(epub, book_number=6)
            again, _, _ = MODULE.extract_book_complete(epub, book_number=6)
        self.assertEqual(corpus['chapters'], legacy_chapters)
        self.assertEqual(candidates, legacy_candidates)
        self.assertEqual(corpus['chapters'][1]['paragraphs'][1]['anchor'], 'b6-c2-p2')
        self.assertEqual(len(corpus['spine_documents']), len(documents))
        self.assertEqual(len(corpus['supplemental_sections']), 4)
        prologue, interlude, epilogue, back = corpus['supplemental_sections']
        self.assertEqual(prologue['reveal']['before_chapter'], 1)
        self.assertEqual(interlude['reveal'], {'policy':'manual-review', 'position_unit':'within-section', 'after_chapter':1, 'before_chapter':2})
        self.assertEqual(epilogue['reveal']['after_chapter'], 2)
        self.assertIsNone(epilogue['reveal']['before_chapter'])
        self.assertTrue(all('-s' in candidate['anchor'] and 'chapter' not in candidate for candidate in supplemental_candidates))
        self.assertTrue(all(candidate['reveal_policy'] == 'manual-review' for candidate in supplemental_candidates))
        self.assertEqual(corpus['supplemental_sections'], again['supplemental_sections'])
        self.assertIn('Text outside supported paragraph tags.', corpus['spine_documents'][-1]['body_text'])
        self.assertEqual(back['paragraphs'], [])

    def test_complete_body_text_omits_script_and_records_images(self):
        parser = MODULE.SpineTextParser()
        parser.feed('<html><head><title>Ignore</title></head><body><div>Outside<p>Inside<br>Next</p></div><script>not prose</script><img src="map.png" alt="Floor map"></body></html>')
        self.assertEqual(parser.text, 'Outside\nInside\nNext')
        self.assertEqual(parser.images, [{'source':'map.png','alt':'Floor map'}])


if __name__ == "__main__":
    unittest.main()
