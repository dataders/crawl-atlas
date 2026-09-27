# Contributing

## Add or correct a checkpoint

1. Run the extractor against your own EPUB.
2. Find the relevant candidate in `data/private/review-candidates.json`.
3. Update `site/dist/data/book-1.json` with a factual paraphrase and its chapter/paragraph anchor.
4. Mark facts `verified` only when the source explicitly supports them. Use `inferred` when continuity is required and `needs-review` when evidence conflicts.
5. Check that a checkpoint reveals nothing from a later reading position.

Never commit source EPUBs, extracted paragraphs, cover art, or substantial quotations. Pull requests containing copyrighted prose will not be accepted.

## Validate

```bash
uv run python3 scripts/validate_data.py site/dist/data/book-1.json
uv run python3 -m unittest discover -s tests
```

