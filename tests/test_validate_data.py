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

    def test_generated_roster_includes_major_allies(self):
        data = json.loads(Path("site/dist/data/series.json").read_text(encoding="utf-8"))
        names = {character["name"] for character in data["characters"]}
        self.assertTrue({"Katia Grim", "Prepotente", "Imani C.", "Elle McGib", "Li Na", "Louis Santiago", "Samantha", "Mordecai"} <= names)
        levels = {(event["subject"], event.get("level")) for event in data["events"] if event["type"] == "level"}
        self.assertIn(("Katia Grim", 60), levels)
        self.assertIn(("Prepotente", 100), levels)

    def test_roster_relationship_changes_are_source_anchored(self):
        data = json.loads(Path("site/dist/data/series.json").read_text(encoding="utf-8"))
        katia_relationships = [
            event["relationship"]
            for event in data["events"]
            if event["subject"] == "Katia Grim" and event["type"] == "party" and event.get("relationship")
        ]
        self.assertEqual(katia_relationships, ["Temporary party member", "Core party member", "Allied team leader"])


if __name__ == "__main__":
    unittest.main()
