#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


CONFIDENCE_VALUES = {"verified", "partial", "inferred", "needs-review"}
STAT_SCOPE_VALUES = {"base", "reported", "equipment", "temporary"}


def validate(path: Path, corpus_path: Path | None = None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("series") or data["book"]
    assert metadata["chapterCount"] > 0
    books = data.get("books")
    book_by_number = {book["number"]: book for book in books} if books else None
    if books:
        assert metadata["bookCount"] == len(books)
        assert metadata["chapterCount"] == sum(book["chapterCount"] for book in books)
        assert [book["number"] for book in books] == list(range(1, len(books) + 1))
    if "events" in data:
        events = data["events"]
        assert events, "at least one event is required"
        locations = [row.get("progress", (row["chapter"] - 1 + row["position"]) / metadata["chapterCount"]) for row in events]
        assert locations == sorted(locations), "events must be in reading order"
        ids = [row["id"] for row in events]
        assert len(ids) == len(set(ids)), "event ids must be unique"
        for row in events:
            if book_by_number:
                assert row["book"] in book_by_number
                assert 1 <= row["chapter"] <= book_by_number[row["book"]]["chapterCount"]
                assert 0 <= row["progress"] <= 1
            else:
                assert 1 <= row["chapter"] <= metadata["chapterCount"]
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
        if "books" in corpus:
            assert len(corpus["books"]) == len(books)
            anchors = {}
            for corpus_book, public_book in zip(corpus["books"], books, strict=True):
                chapter_numbers = [chapter["number"] for chapter in corpus_book["chapters"]]
                assert chapter_numbers == list(range(1, public_book["chapterCount"] + 1)), "private corpus chapters must be complete and ordered"
                anchors.update({paragraph["anchor"]: paragraph for chapter in corpus_book["chapters"] for paragraph in chapter["paragraphs"]})
        else:
            chapters = corpus["chapters"]
            chapter_numbers = [chapter["number"] for chapter in chapters]
            expected = list(range(1, metadata["chapterCount"] + 1))
            assert chapter_numbers == expected, "private corpus chapters must be complete and ordered"
            anchors = {paragraph["anchor"]: paragraph for chapter in chapters for paragraph in chapter["paragraphs"]}
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
