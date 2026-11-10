# Events Parquet

A denormalized export of the eight curated book ledgers. One row is one recorded fact; `event_id` retains the source event ID and may repeat. `row_id` is unique. No inferred totals or private evidence sentences are included.

Current snapshot: **6,487 rows from 5,400 events**, dataset version **2.13.0**. Zstandard compressed; **1,150,284 bytes**.

Regenerate from the repository root:

```sh
uv run scripts/export_events_parquet.py
```

The script declares its PyArrow dependency. It verifies source-event coverage, unique row IDs, reward references, and a lossless Parquet read-back.

## Columns

| Column | Parquet/Arrow type |
| --- | --- |
| `row_id` | `string` |
| `event_id` | `string` |
| `book_number` | `int16` |
| `chapter_number` | `int16` |
| `chapter_position` | `double` |
| `source_anchor` | `string` |
| `reveal_progress` | `double` |
| `character_id` | `string` |
| `character_name` | `string` |
| `subject_type` | `string` |
| `subject_name` | `string` |
| `event_type` | `string` |
| `action` | `string` |
| `entity_id` | `string` |
| `entity_name` | `string` |
| `value` | `double` |
| `unit` | `string` |
| `quantity` | `double` |
| `operation` | `string` |
| `value_scope` | `string` |
| `value_kind` | `string` |
| `state_before` | `string` |
| `state_after` | `string` |
| `source_item_id` | `string` |
| `attached_to_item_id` | `string` |
| `condition` | `string` |
| `related_event_ids` | `list<element: string>` |
| `history_only` | `bool` |
| `event_detail` | `string` |
| `confidence` | `string` |
| `metadata` | `struct<discovery_batch: string, reviewed_on: string, revision_batches: list<element: string>, attributes_json: string>` |

## Semantics

- `book_number`, `chapter_number`, `chapter_position`, and `source_anchor` locate the recorded reveal, not necessarily when an earlier event happened. Both position fields are fractions from 0 to 1. Page numbers are omitted because they require an edition.
- `history_only` preserves retrospective/background records; do not treat these as present-day status transitions.
- `event_type` describes the fact; `action` describes the recorded action. `observe` does not mean obtained. Death certainty is preserved as `state_after` (`dead`, `presumed-dead`, `alive`).
- `value` with `operation=set` is a reading; `add` or `multiply` is an adjustment. `quantity` is an item count. Percent values retain their source units (10 percent is 10, not 0.10). Null is unknown, never zero.
- `value_scope` and `value_kind` keep modifier status separate from numerical certainty. Original scope labels remain in metadata.
- Equipment-effect rows reference their source item; attachment IDs are owner-scoped and refer to a parent item. The file includes historical equip/unequip events: an effect definition alone does not assert the item is currently equipped.
- `related_event_ids` is a typed list of original parent event IDs. Every link is checked against the source events.
- `metadata` is a typed struct with audit batch, review date, revision batches and `attributes_json`. The JSON preserves public source attributes for uncommon event types; evidence fields are excluded recursively.
- Independent `statReading`, character and book definition records are not counted as source events. Character IDs/names are repeated on facts for convenient querying.

## Examples (DuckDB)

```sql
SELECT event_type, count(*) FROM read_parquet('data/exports/events.parquet') GROUP BY ALL;

SELECT book_number, chapter_number, value, value_scope, action
FROM read_parquet('data/exports/events.parquet')
WHERE character_name = 'Carl' AND event_type = 'skill' AND entity_name = 'Pugilism'
ORDER BY reveal_progress;
```
