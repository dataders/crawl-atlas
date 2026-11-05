"""Build queryable public facts from the curated timeline (never EPUB prose)."""
import json
from contextlib import closing
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def progression_rows(events):
    previous = {}
    rows = []
    for event in sorted(events, key=lambda e: e['progress']):
        kind = event['type']
        if kind not in ('level', 'skill', 'stat'):
            continue
        values = {**{name: None for name in event.get('statsDelta', {})}, **event.get('stats', {})} if kind == 'stat' else {
            'Level' if kind == 'level' else event['name']: event.get('level')}
        for metric, value in values.items():
            scope = event.get('statScopes', {}).get(metric, 'reported') if kind == 'stat' else (event.get('skillScope', 'reported') if kind == 'skill' else 'confirmed')
            key = (event['subject'], kind, event.get('skillId', metric.lower()), scope, event['confidence'])
            before = previous.get(key)
            delta = value - before if isinstance(value, (int, float)) and before is not None else None
            if kind == 'skill' and 'levelDelta' in event:
                delta = event['levelDelta']
                before = None
            if metric in event.get('statsDelta', {}):
                delta = event['statsDelta'][metric]
                before = None  # An explicit modifier does not establish an absolute total.
            rows.append(dict(event_id=event['id'], character=event['subject'], kind=kind,
                             metric=metric, value=value, previous=before, delta=delta, scope=scope,
                             book=event['book'], chapter=event['chapter'], position=event['position'],
                             progress=event['progress'], confidence=event['confidence'],
                             action=event.get('action', 'note'), source=event['source'],
                             summary=event.get('summary', '')))
            if event.get('action') in ('remove', 'delta', 'increase') or metric in event.get('statsDelta', {}):
                previous.pop(key, None)
            elif isinstance(value, (int, float)):
                previous[key] = value
    return rows


def build(source, output):
    try:
        from .reward_provenance import acquisition_rows
    except ImportError:
        from reward_provenance import acquisition_rows
    data = json.loads(source.read_text())
    rows = progression_rows(data['events'])
    acquisitions, links = acquisition_rows(data['events'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'progression.json').write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + '\n')
    path = output / 'crawl-atlas.sqlite'
    path.unlink(missing_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
            CREATE TABLE series (id TEXT PRIMARY KEY, title TEXT, book_count INTEGER,
                chapter_count INTEGER, data_version TEXT, coverage_note TEXT);
            CREATE TABLE books (number INTEGER PRIMARY KEY, title TEXT, chapter_count INTEGER);
            CREATE TABLE characters (id TEXT PRIMARY KEY, name TEXT UNIQUE,
                character_group TEXT, color TEXT);
            CREATE TABLE events (id TEXT PRIMARY KEY, book INTEGER REFERENCES books(number),
                chapter INTEGER, position REAL, progress REAL, kind TEXT, character TEXT,
                name TEXT, action TEXT, confidence TEXT, source TEXT, summary TEXT, payload TEXT);
            CREATE TABLE progression (event_id TEXT REFERENCES events(id), character TEXT,
                kind TEXT, metric TEXT, value REAL, previous REAL, delta REAL, scope TEXT,
                book INTEGER, chapter INTEGER, position REAL, progress REAL,
                confidence TEXT, action TEXT, source TEXT, summary TEXT,
                PRIMARY KEY(event_id, metric));
            CREATE INDEX events_location ON events(progress);
            CREATE INDEX progression_lookup ON progression(character, kind, metric, progress);
            CREATE INDEX progression_location ON progression(progress);
            CREATE VIEW increases AS SELECT * FROM progression WHERE delta > 0 OR action = 'increase';
            CREATE TABLE acquisitions (event_id TEXT PRIMARY KEY REFERENCES events(id),
                character TEXT, name TEXT, stage TEXT, source_type TEXT, box_id TEXT,
                box_tier TEXT, box_kind TEXT, outcome_type TEXT, occurrence_detail TEXT,
                quantity REAL, reason_type TEXT, reason_detail TEXT, attribution TEXT,
                book INTEGER, chapter INTEGER, progress REAL, source TEXT,
                confidence TEXT, summary TEXT);
            CREATE TABLE acquisition_links (
                child_event_id TEXT REFERENCES acquisitions(event_id),
                parent_event_id TEXT REFERENCES acquisitions(event_id),
                PRIMARY KEY(child_event_id, parent_event_id));
            CREATE INDEX acquisitions_character_stage ON acquisitions(character, stage, progress);
            CREATE VIEW dim_series AS SELECT id AS series_id, title, book_count,
                chapter_count, data_version, coverage_note FROM series;
            CREATE VIEW dim_book AS SELECT number AS book_number, title, chapter_count
                FROM books;
            CREATE VIEW dim_character AS SELECT id AS character_id, name AS character,
                character_group, color FROM characters;
            CREATE VIEW fct_timeline_event AS SELECT events.*,
                json_extract(payload, '$.state') AS item_state,
                CAST(json_extract(payload, '$.quantity') AS REAL) AS quantity
                FROM events;
            CREATE VIEW fct_character_observation AS SELECT * FROM progression;
            CREATE VIEW fct_acquisition AS SELECT * FROM acquisitions;
            CREATE VIEW bridge_acquisition_lineage AS SELECT * FROM acquisition_links;
            CREATE VIEW mart_crawl_atlas_dashboard AS
                SELECT
                    event.id AS event_id,
                    event.book,
                    event.chapter,
                    event.position,
                    event.progress,
                    event.kind AS event_kind,
                    event.character,
                    event.name AS event_name,
                    event.action,
                    event.confidence,
                    event.source,
                    event.summary,
                    event.item_state,
                    event.quantity,
                    observation.kind AS observation_kind,
                    observation.metric,
                    observation.value,
                    observation.previous AS previous_value,
                    observation.delta,
                    observation.scope
                FROM fct_timeline_event AS event
                LEFT JOIN fct_character_observation AS observation
                    ON observation.event_id = event.id;
        ''')
        series = data['series']
        db.execute('INSERT INTO series VALUES (?,?,?,?,?,?)', (
            series['id'], series['title'], series['bookCount'], series['chapterCount'],
            series['dataVersion'], series['coverageNote']))
        db.executemany('INSERT INTO books VALUES (?,?,?)', [(b['number'], b['title'], b['chapterCount']) for b in data['books']])
        db.executemany('INSERT INTO characters VALUES (?,?,?,?)', [(
            character['id'], character['name'], character.get('group'), character.get('color'))
            for character in data['characters']])
        db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', [(
            e['id'], e['book'], e['chapter'], e['position'], e['progress'], e['type'],
            e['subject'], e['name'], e.get('action'), e['confidence'], e['source'],
            e.get('summary'), json.dumps(e, ensure_ascii=False)) for e in data['events']])
        db.executemany('INSERT INTO progression VALUES (' + ','.join('?' * 16) + ')', [tuple(r.values()) for r in rows])
        db.executemany('INSERT INTO acquisitions VALUES (' + ','.join('?' * 20) + ')', [tuple(r.values()) for r in acquisitions])
        db.executemany('INSERT INTO acquisition_links VALUES (?,?)', [tuple(r.values()) for r in links])
    return rows


if __name__ == '__main__':
    rows = build(ROOT / 'site/dist/data/series.json', ROOT / 'site/dist/data')
    print(f'Built SQLite database and {len(rows)} progression observations.')
