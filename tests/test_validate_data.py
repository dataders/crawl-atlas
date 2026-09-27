import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("validate_data", Path("scripts/validate_data.py"))
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ValidatorTests(unittest.TestCase):
    def write_json(self, root, name, value):
        path = Path(root) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_rejects_checkpoint_before_source(self):
        data = {
            "book": {"chapterCount": 1},
            "checkpoints": [{
                "id": "early",
                "chapter": 1,
                "position": 0.2,
                "source": "b1-c1-p1",
                "party": [{"confidence": "verified"}],
                "inventory": [],
                "skills": [],
            }],
        }
        corpus = {"chapters": [{
            "number": 1,
            "paragraphs": [{"anchor": "b1-c1-p1", "position": 0.5}],
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            data_path = self.write_json(tmp, "data.json", data)
            corpus_path = self.write_json(tmp, "corpus.json", corpus)
            with self.assertRaisesRegex(AssertionError, "appears before its source"):
                MODULE.validate(data_path, corpus_path)

    def test_accepts_event_ledger(self):
        data = {
            "book": {"chapterCount": 1},
            "events": [{
                "id": "level-one",
                "chapter": 1,
                "position": 0.5,
                "source": "b1-c1-p1",
                "type": "level",
                "confidence": "verified",
            }],
        }
        corpus = {"chapters": [{
            "number": 1,
            "paragraphs": [{"anchor": "b1-c1-p1", "position": 0.5}],
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            data_path = self.write_json(tmp, "data.json", data)
            corpus_path = self.write_json(tmp, "corpus.json", corpus)
            self.assertEqual(MODULE.validate(data_path, corpus_path), 1)

    def test_accepts_series_event_ledger(self):
        data = {
            "series": {"bookCount": 2, "chapterCount": 3},
            "books": [
                {"number": 1, "chapterCount": 1},
                {"number": 2, "chapterCount": 2},
            ],
            "events": [{
                "id": "book-two-level",
                "book": 2,
                "chapter": 1,
                "position": 0.5,
                "progress": 0.5,
                "source": "b2-c1-p1",
                "type": "level",
                "confidence": "verified",
            }],
        }
        corpus = {"books": [
            {"chapters": [{"number": 1, "paragraphs": [{"anchor": "b1-c1-p1", "position": 0.5}]}]},
            {"chapters": [
                {"number": 1, "paragraphs": [{"anchor": "b2-c1-p1", "position": 0.5}]},
                {"number": 2, "paragraphs": [{"anchor": "b2-c2-p1", "position": 0.5}]},
            ]},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            data_path = self.write_json(tmp, "data.json", data)
            corpus_path = self.write_json(tmp, "corpus.json", corpus)
            self.assertEqual(MODULE.validate(data_path, corpus_path), 1)


if __name__ == "__main__":
    unittest.main()
