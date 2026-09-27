#!/usr/bin/env python3
"""Extract all eight DCC EPUBs into one private, ordered series corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_epub import extract_book


BOOKS = (
    (1, "Dungeon Crawler Carl", "Dungeon Crawler Carl by Matt Dinniman.epub"),
    (2, "Carl's Doomsday Scenario", "DCC-02_ Carl's Doomsday Scenario -- Dinniman, Matt -- 2021 -- 64cf96f5480b4f04fe88dd4c05e7dcb6 -- Anna’s Archive.epub"),
    (3, "The Dungeon Anarchist's Cookbook", "The Dungeon Anarchist's Cookbook_ Dungeon Crawler Carl Book -- Dinniman, Matt -- Dungeon Crawler Carl Book 3, 2021 -- Dandy House -- 0cbd759918a08522f2694b9de4dabac0 -- Anna’s Archive.epub"),
    (4, "The Gate of the Feral Gods", "The Gate of the Feral Gods_ Dungeon Crawler Carl Book 4 -- Matt Dinniman -- Dungeon Crawler Carl 4, 2021 -- Dandy House -- 201c3bd3fae6ce236da1ac4fe4d3cc9a -- Anna’s Archive.epub"),
    (5, "The Butcher's Masquerade", "The Butcher's Masquerade_ Dungeon Crawler Carl (Book 5) -- Matt Dinniman -- Dungeon Crawler Carl, 5, 2022 -- Dandy House -- 36f4843189af9088cb329a37b7171c82 -- Anna’s Archive.epub"),
    (6, "The Eye of the Bedlam Bride", "The Eye of the Bedlam Bride -- Matt Dinniman -- 2023 -- 062620c665e891a616b37aa9376680a2 -- Anna’s Archive.epub"),
    (7, "This Inevitable Ruin", "This Inevitable Ruin_ Dungeon Crawler Carl Book 7 -- Matt Dinniman -- Dungeon Crawler Carl, 2024 -- Dandy House -- 9f03951ed3eca60c23430c21fe317007 -- Anna’s Archive.epub"),
    (8, "A Parade of Horribles", "A Parade of Horribles -- Matt Dinniman -- Dungeon Crawler Carl #8, 2026 -- Dandy House -- isbn13 9788217190066 -- 18d29569f0bdd768975ca7d130748bf9 -- Anna’s Archive.epub"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("data/private"))
    args = parser.parse_args()

    books = []
    candidates = []
    for number, title, filename in BOOKS:
        epub = args.root / filename
        if not epub.exists():
            raise FileNotFoundError(f"Missing Book {number} EPUB: {epub}")
        chapters, book_candidates = extract_book(epub, book_number=number)
        books.append(
            {
                "number": number,
                "id": f"dcc-{number}",
                "title": title,
                "source": epub.name,
                "chapterCount": len(chapters),
                "chapters": chapters,
            }
        )
        candidates.extend(book_candidates)

    args.output.mkdir(parents=True, exist_ok=True)
    corpus_path = args.output / "series-corpus.json"
    candidates_path = args.output / "series-review-candidates.json"
    corpus_path.write_text(json.dumps({"series": "Dungeon Crawler Carl", "books": books}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {sum(book['chapterCount'] for book in books)} chapters across {len(books)} books to {corpus_path}")
    print(f"Wrote {len(candidates)} review candidates to {candidates_path}")


if __name__ == "__main__":
    main()
