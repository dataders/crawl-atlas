#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


CONFIDENCE_VALUES = {"verified", "partial", "inferred", "needs-review"}
STAT_SCOPE_VALUES = {"base", "reported", "equipment", "temporary"}


def validate(path: Path, corpus_path: Path | None = None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["book"]["chapterCount"] > 0
    if "events" in data:
        events = data["events"]
        assert events, "at least one event is required"
        locations = [(row["chapter"], row["position"]) for row in events]
        assert locations == sorted(locations), "events must be in reading order"
        ids = [row["id"] for row in events]
        assert len(ids) == len(set(ids)), "event ids must be unique"
        for row in events:
            assert 1 <= row["chapter"] <= data["book"]["chapterCount"]
            assert 0 <= row["position"] <= 1
            assert row["type"] in {"level", "stat", "skill", "item", "party", "story"}
            assert row["confidence"] in CONFIDENCE_VALUES
            if row["type"] == "stat":
                stat_names = set(row.get("stats", {})) | set(row.get("statsDelta", {}))
                assert set(row.get("statScopes", {})) <= stat_names
                assert set(row.get("statScopes", {}).values()) <= STAT_SCOPE_VALUES
        records = events
    else:
        checkpoints = data["checkpoints"]
        assert checkpoints, "at least one checkpoint is required"
        locations = [(row["chapter"], row["position"]) for row in checkpoints]
        assert locations == sorted(locations), "checkpoints must be in reading order"
        ids = [row["id"] for row in checkpoints]
        assert len(ids) == len(set(ids)), "checkpoint ids must be unique"
        for row in checkpoints:
            assert 1 <= row["chapter"] <= data["book"]["chapterCount"]
            assert 0 <= row["position"] <= 1
            assert row["party"], f"checkpoint {row['id']} has no party"
            for collection in (row["party"], row["inventory"], row["skills"]):
                for entry in collection:
                    assert entry["confidence"] in CONFIDENCE_VALUES
        records = checkpoints

    if corpus_path is not None:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        chapters = corpus["chapters"]
        chapter_numbers = [chapter["number"] for chapter in chapters]
        expected = list(range(1, data["book"]["chapterCount"] + 1))
        assert chapter_numbers == expected, "private corpus chapters must be complete and ordered"
        anchors = {
            paragraph["anchor"]: paragraph
            for chapter in chapters
            for paragraph in chapter["paragraphs"]
        }
        for row in records:
            source = row["source"]
            assert source in anchors, f"record {row['id']} has unknown source anchor {source}"
            source_position = anchors[source]["position"]
            assert source_position <= row["position"], (
                f"record {row['id']} appears before its source "
                f"({row['position']} < {source_position})"
            )

    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a public timeline dataset")
    parser.add_argument("path", type=Path)
    parser.add_argument("--corpus", type=Path, help="optionally verify private source anchors and spoiler boundaries")
    args = parser.parse_args()
    count = validate(args.path, args.corpus)
    print(f"Validated {count} timeline records in {args.path}")


if __name__ == "__main__":
    main()
