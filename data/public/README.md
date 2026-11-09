Edit the eight book-*.jsonl files. Each line is one JSON object; recordType distinguishes events, character definitions, stat readings, and catalog records. Keep event IDs stable when fixing a name or a source location: reward links refer to those IDs.

On an event, source is *where the reader learns the fact*. Optional metadata.discoveryBatch names the real-world review that found it, for example "leaderboard-level-audit". metadata.reviewedOn is the known review date (YYYY-MM-DD); leave it out when unknown. metadata.revisions lists later batches that corrected the record. No review date affects the spoiler boundary. Older records with an unknown discovery batch use null.

Run `uv run python scripts/build_public_timeline.py` to regenerate series.json, its book-1.json compatibility copy, and stat-breakdown-audit.json (a generated input for existing chart exports). Never edit those outputs directly. No EPUB or private corpus is needed to rebuild the public records.
