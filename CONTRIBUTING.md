# Contributing

## Add or correct an event

1. Run the extractor against your own EPUB.
2. Edit the appropriate book JSONL in data/public. Keep its ID and reward links stable; record the review name under metadata.discoveryBatch.
3. Run `uv run python3 scripts/build_public_timeline.py` to regenerate the public event ledger.
4. Mark facts `verified` only when the source explicitly supports them. Use `inferred` when continuity is required and `needs-review` when evidence conflicts.
5. Check that the event reveals nothing before its source location and does not duplicate a later status recap.

Never commit source EPUBs, extracted paragraphs, cover art, or substantial quotations. Pull requests containing copyrighted prose will not be accepted.

## Validate

```bash
uv run python3 scripts/validate_data.py site/dist/data/series.json --corpus data/private/series-corpus.json
uv run python3 -m unittest discover -s tests
```
