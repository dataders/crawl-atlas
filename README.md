# Crawl Atlas

A spoiler-safe reading companion for LitRPG books. Pick the chapter and position you have reached to see the latest known party, levels, stats, skills, and inventory—never facts first revealed later.

The first dataset targets *Dungeon Crawler Carl* book one. This repository does **not** redistribute the book: EPUB files, extracted prose, and machine-generated review candidates remain local and are ignored by Git.

## What works

- EPUB-to-JSON corpus extraction using only Python's standard library
- chapter and paragraph progress anchors
- candidate detection for levels, stats, skills, items, rewards, and party changes
- a curated, source-anchored public timeline
- an interactive, responsive website with strict chapter/position filtering
- confidence and coverage labels so uncertain or incomplete facts are visible

## Local setup

1. Put your legally obtained EPUB in this directory.
2. Extract the private analysis corpus:

   ```bash
   uv run python3 scripts/extract_epub.py "Dungeon Crawler Carl by Matt Dinniman.epub"
   ```

3. Serve the static site:

   ```bash
   uv run python3 -m http.server 4173 --directory site/dist
   ```

4. Open `http://localhost:4173`.

The checked-in public data contains short factual summaries, not book text. To improve coverage, review `data/private/review-candidates.json` and add verified facts to `site/dist/data/book-1.json`.

## Data model

Each checkpoint has a `chapter` and a fractional `position`. The app selects the latest checkpoint at or before the reader's chosen location. Entries carry:

- `confidence`: `verified`, `inferred`, or `needs-review`
- `source`: chapter and paragraph anchor in the private corpus
- `note`: short provenance or ambiguity note

See [`schema/book-timeline.schema.json`](schema/book-timeline.schema.json).

## Copyright and contributions

Do not commit EPUBs, extracted prose, cover art, or long quotations. Contributions should be transformative facts and brief summaries with chapter/paragraph anchors. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

This is an unofficial fan project and is not affiliated with Matt Dinniman, Dandy House, or any publisher.

## License

Code is available under the MIT License. Book titles, character names, and other referenced properties belong to their respective owners.

