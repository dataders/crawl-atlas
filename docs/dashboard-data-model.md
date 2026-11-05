# Crawl Atlas dashboard data model

The dashboard reads a static SQLite snapshot today. Its public contract is a
small star-shaped model that can move to Snowflake without changing board SQL.
SQLite implements the contract as views over the existing build tables; a future
dbt project should materialize the dimensions and facts in an `analytics` schema.

## Recommended warehouse shape

| Relation | Grain | Key | Purpose |
| --- | --- | --- | --- |
| `dim_series` | one row per book series | `series_id` | Series title, total books/chapters, dataset version, coverage note |
| `dim_book` | one row per book | `book_number` | Book title and chapter count |
| `dim_character` | one row per tracked character | `character_id` | Stable name, cast group, display color |
| `fct_timeline_event` | one row per curated reveal event | `id` | Generic levels, stats, skills, items, party, and story events at their first safe reveal point |
| `fct_character_observation` | one row per event and metric | (`event_id`, `metric`) | Numeric level/stat/skill observations, prior value, delta, scope, and confidence |
| `fct_acquisition` | one row per reward/acquisition stage | `event_id` | Award, open, receive, identify, and apply steps with box/reward attributes |
| `bridge_acquisition_lineage` | one row per child-parent edge | (`child_event_id`, `parent_event_id`) | Many-step reward provenance without flattening or inventing attribution |
| `mart_crawl_atlas_dashboard` | one row per event and observed metric; one row for non-observation events | (`event_id`, `metric`) with nullable `metric` | Portable presentation mart consumed by the static dbt Charts board |

All facts carry `book`, `chapter`, and normalized `progress`. Every dashboard
query applies the reader's boundary before aggregation or display. `source` is a
private-corpus anchor; `summary` is a short public fact, never source prose.

The reader uses two coordinates. The slider filters facts by series `progress`.
Each chart then plots those facts at `book - 1 + (chapter - 1 + position) /
chapter_count`, measured in books. This gives every reached book equal width;
the smaller ticks show the fraction of its chapters traversed. The right edge is
the end of the current book, including unread space. Book-start exports change
the scale before a new observation arrives, without revealing later values.

## Column contracts

### `dim_series`

`series_id text`, `title text`, `book_count integer`, `chapter_count integer`,
`data_version text`, `coverage_note text`.

### `dim_book`

`book_number integer`, `title text`, `chapter_count integer`.

### `dim_character`

`character_id text`, `character text`, `character_group text`, `color text`.

### `fct_timeline_event`

`id text`, `book integer`, `chapter integer`, `position real`, `progress real`,
`kind text`, `character text`, `name text`, `action text`, `confidence text`,
`source text`, `summary text`, `payload text`, `item_state text`, `quantity real`.

`item_state` and `quantity` are presentation-safe projections of the item
payload. Keeping them on the fact avoids warehouse-specific JSON extraction in
the board while retaining `payload` for less common attributes.

### `fct_character_observation`

`event_id text`, `character text`, `kind text`, `metric text`, `value real`,
`previous real`, `delta real`, `scope text`, `book integer`, `chapter integer`,
`position real`, `progress real`, `confidence text`, `action text`, `source text`,
`summary text`.

### `fct_acquisition`

`event_id text`, `character text`, `name text`, `stage text`, `source_type text`,
`box_id text`, `box_tier text`, `box_kind text`, `outcome_type text`,
`occurrence_detail text`, `quantity real`, `reason_type text`,
`reason_detail text`, `attribution text`, `book integer`, `chapter integer`,
`progress real`, `source text`, `confidence text`, `summary text`.

### `bridge_acquisition_lineage`

`child_event_id text`, `parent_event_id text`.

### `mart_crawl_atlas_dashboard`

`event_id text`, `book integer`, `chapter integer`, `position real`,
`progress real`, `event_kind text`, `character text`, `event_name text`,
`action text`, `confidence text`, `source text`, `summary text`,
`item_state text`, `quantity real`, `observation_kind text`, `metric text`,
`value real`, `previous_value real`, `delta real`, `scope text`.

This denormalized mart is the deployment boundary for the current static board.
The normalized facts and dimensions remain source of truth; Snowflake/dbt can
materialize this mart from them with the same column contract.

## dbt and Snowflake path

This deserves its own dbt project in this repository once Snowflake becomes the
system of record. Keep the curated public exports as raw sources, then build:

1. `stg_crawl_atlas__series`, `__books`, `__characters`, `__events`,
   `__observations`, `__acquisitions`, and `__acquisition_links` to rename and
   type source fields.
2. The normalized public relations above plus the dashboard mart as contracted models in an `analytics`
   schema. Materialize dimensions and facts as tables; the lineage bridge can
   remain a view while small.
3. Uniqueness, not-null, accepted-value, relationship, and spoiler-boundary
   tests. In particular, assert `progress between 0 and 1` and one observation
   per (`event_id`, `metric`).
4. Point dbt Charts at a named Snowflake source with the same relation names.

Do not move private EPUB text or evidence sentences into the dashboard schema.
Those belong in a separately permissioned evidence layer, if they enter a
warehouse at all.
