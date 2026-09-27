#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


CONFIDENCE_VALUES = {"verified", "inferred", "needs-review"}


def validate(path: Path, corpus_path: Path | None = None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["book"]["chapterCount"] > 0
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
        for row in checkpoints:
            source = row["source"]
            assert source in anchors, f"checkpoint {row['id']} has unknown source anchor {source}"
            source_position = anchors[source]["position"]
            assert source_position <= row["position"], (
                f"checkpoint {row['id']} appears before its source "
                f"({row['position']} < {source_position})"
            )

    return len(checkpoints)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a public timeline dataset")
    parser.add_argument("path", type=Path)
    parser.add_argument("--corpus", type=Path, help="optionally verify private source anchors and spoiler boundaries")
    args = parser.parse_args()
    count = validate(args.path, args.corpus)
    print(f"Validated {count} checkpoints in {args.path}")


if __name__ == "__main__":
    main()
