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


if __name__ == "__main__":
    unittest.main()
