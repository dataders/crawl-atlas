# Crawl Atlas

A spoiler-safe reading companion for LitRPG books. Move one slider to the point you have reached and see the party's complete known history, levels, stats, skills, and active inventory—never facts first revealed later.

The current dataset maps all eight *Dungeon Crawler Carl* books. This repository does **not** redistribute the books: EPUB files, extracted prose, and machine-generated review candidates remain local and are ignored by Git.

## What works

- EPUB-to-JSON corpus extraction using only Python's standard library
- one continuous, series-wide progress control with book, chapter, and paragraph anchors
- candidate detection for levels, stats, skills, items, rewards, and party changes
- source-anchored character and inventory audits
- cumulative level and base-stat charts with explicit milestone labels
- clickable character dossiers, inventory ledger, and event history
- strict location filtering so every view respects the reader's spoiler boundary

## Local setup

1. Put your legally obtained EPUBs in this directory using the filenames listed in `scripts/extract_series.py`.
2. Extract the private eight-book analysis corpus:

   ```bash
   uv run python3 scripts/extract_series.py
   ```

3. Serve the static site:

   ```bash
   uv run python3 -m http.server 4173 --directory site/dist
   ```

4. Open `http://localhost:4173`.

The checked-in public data contains short factual summaries, not book text. To rebuild it after improving the private audits, run:

```bash
uv run python3 scripts/build_public_timeline.py
uv run python3 scripts/validate_data.py site/dist/data/series.json --corpus data/private/series-corpus.json
```

## Data model

Each event has a `book`, local `chapter`, fractional `position`, and computed series-wide `progress`. The app replays every event at or before the reader's chosen location to reconstruct the current state. Event types include character levels, stats, skills, inventory changes, party changes, and brief story milestones. Entries carry:

- `confidence`: `verified`, `inferred`, or `needs-review`
- `action`: how the event changes the current state
- `subject`: the affected character or party
- `source`: a private corpus anchor used for validation; source prose is not published

See [`schema/book-timeline.schema.json`](schema/book-timeline.schema.json).

## Copyright and contributions

Do not commit EPUBs, extracted prose, cover art, or long quotations. Contributions should be transformative facts and brief summaries with chapter/paragraph anchors. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

This is an unofficial fan project and is not affiliated with Matt Dinniman, Dandy House, or any publisher.

## License

Code is available under the MIT License. Book titles, character names, and other referenced properties belong to their respective owners.
