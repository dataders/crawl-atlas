# /// script
# dependencies = ["pyarrow>=20"]
# ///
"""Export public JSONL ledgers as denormalized, atomic Parquet facts.

Run: uv run scripts/export_events_parquet.py
One source event can yield multiple facts; event_id and reward links stay intact.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = pa.schema([
    ("row_id", pa.string()), ("event_id", pa.string()),
    ("book_number", pa.int16()), ("chapter_number", pa.int16()),
    ("chapter_position", pa.float64()), ("source_anchor", pa.string()),
    ("reveal_progress", pa.float64()),
    ("character_id", pa.string()), ("character_name", pa.string()),
    ("subject_type", pa.string()), ("subject_name", pa.string()),
    ("event_type", pa.string()), ("action", pa.string()),
    ("entity_id", pa.string()), ("entity_name", pa.string()),
    ("value", pa.float64()), ("unit", pa.string()), ("quantity", pa.float64()),
    ("operation", pa.string()), ("value_scope", pa.string()),
    ("value_kind", pa.string()), ("state_before", pa.string()),
    ("state_after", pa.string()), ("source_item_id", pa.string()),
    ("attached_to_item_id", pa.string()), ("condition", pa.string()),
    ("related_event_ids", pa.list_(pa.string())), ("history_only", pa.bool_()),
    ("event_detail", pa.string()), ("confidence", pa.string()),
    ("metadata", pa.struct([
        ("discovery_batch", pa.string()), ("reviewed_on", pa.string()),
        ("revision_batches", pa.list_(pa.string())),
        ("attributes_json", pa.string()),
    ])),
])
PRIVATE_KEYS = {"evidence", "evidenceSentences", "deathEvidence"}


def public_attributes(value):
    if isinstance(value, dict):
        return {k: public_attributes(v) for k, v in value.items() if k not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [public_attributes(v) for v in value]
    return value


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def entity_id(kind, name, owner=None):
    if not name:
        return None
    identity = json.dumps([kind, owner, name], ensure_ascii=False)
    return kind + ':' + hashlib.sha256(identity.encode()).hexdigest()[:20]


def scope_fields(scope, value, estimate=False):
    scope = scope or 'unspecified'
    kind = ('lower_bound' if scope == 'lower-bound' else 'upper_bound' if scope == 'upper-bound'
            else 'estimate' if scope == 'estimate' or estimate else 'exact')
    normalized = {'confirmed': 'unspecified', 'reported': 'unspecified',
                  'effective': 'with_modifiers', 'equipment': 'modifier',
                  'temporary': 'modifier', 'estimate': 'unspecified',
                  'lower-bound': 'unspecified', 'upper-bound': 'unspecified'}.get(scope, scope)
    return normalized, kind if value is not None else 'unknown'


def event_rows(event, characters, item_ids=None):
    e = event
    subject = e['subject']
    group = subject == 'Party' or e.get('type') == 'party' and subject == e.get('partyName')
    character = None if group else characters.get(subject)
    meta = e.get('metadata', {})
    item_ids = item_ids or {}
    owner = character or subject
    own_item = e.get('itemId') or item_ids.get((subject, e['name'])) or entity_id('item', e['name'], owner)
    parent = e.get('attachedTo')
    parent_id = (item_ids.get((subject, parent)) or entity_id('item', parent, owner)) if parent else None
    base = dict.fromkeys(SCHEMA.names)
    base.update(event_id=e['id'], book_number=e['book'], chapter_number=e['chapter'],
                chapter_position=e['position'], source_anchor=e['source'],
                reveal_progress=e['progress'], character_id=character,
                character_name=None if group else subject,
                subject_type='group' if group else 'character', subject_name=subject,
                event_type=e['type'], action=e.get('action', 'observe'),
                entity_name=e['name'], entity_id=(own_item if e['type']=='item' else None) or e.get('skillId') or
                entity_id(e['type'], e['name'], character or subject),
                quantity=number(e.get('quantity')), unit=e.get('unit'), state_after=e.get('state'),
                source_item_id=None, attached_to_item_id=parent_id,
                related_event_ids=e.get('acquisition', {}).get('parentEventIds', []),
                history_only=bool(e.get('historyOnly')), event_detail=e.get('summary'),
                confidence=e.get('confidence'), value_kind='unknown',
                metadata=dict(discovery_batch=meta.get('discoveryBatch'),
                              reviewed_on=meta.get('reviewedOn'),
                              revision_batches=meta.get('revisions', []),
                              attributes_json=json.dumps(public_attributes(e), ensure_ascii=False, sort_keys=True)))
    facts = []

    def emit(key, **updates):
        row = {**base, **updates}
        row['row_id'] = e['id'] + '#' + key
        facts.append(row)

    if e['type'] in ('level', 'skill'):
        value = number(e.get('level'))
        delta = number(e.get('levelDelta'))
        scope = e.get('skillScope', e.get('scope', 'unspecified'))
        emit('reading', value=value if value is not None else delta,
             operation='set' if value is not None or delta is None else 'add', unit='levels',
             **dict(zip(('value_scope', 'value_kind'), scope_fields(scope, value if value is not None else delta, e.get('estimate', False)))))
    for field, operation in (('stats', 'set'), ('statsDelta', 'add')):
        for stat, raw in e.get(field, {}).items():
            value = number(raw)
            scope = e.get('statScopes', {}).get(stat, e.get('scope', 'unspecified'))
            value_scope, value_kind = scope_fields(scope, value, e.get('estimate', False))
            emit(f'{field}:{stat}', event_type='stat', entity_name=stat,
                 entity_id=entity_id('stat', stat), value=value, unit='points', operation=operation,
                 value_scope=value_scope if operation == 'set' else 'modifier', value_kind=value_kind)
    if e['type'] not in ('level', 'skill') and not (e['type'] == 'stat' and facts):
        emit('event')

    for field, value in (('lifeStatus', e.get('lifeStatus')), ('characterClass', e.get('characterClass')),
                         ('race', e.get('race')), ('class', e.get('profile', {}).get('class')),
                         ('subclass', e.get('profile', {}).get('subclass')),
                         ('profileRace', e.get('profile', {}).get('race'))):
        if value is not None:
            emit(field, event_type='life_status' if field == 'lifeStatus' else 'race' if field in ('race', 'profileRace') else 'class',
                 action='observe', operation='set', state_after=value,
                 entity_name=subject if field == 'lifeStatus' else value,
                 entity_id=character if field == 'lifeStatus' else entity_id(field, value))
    if e.get('acquisition'):
        acquisition = e['acquisition']
        emit('reward', event_type='reward', action=acquisition.get('stage', 'observe'))
    if isinstance(e.get('floor'), int):
        emit('floor', event_type='floor', value=float(e['floor']), unit='floor',
             operation='set', value_kind='exact', state_after=e.get('mode'))
    effects = list(e.get('effects', []))
    existing = {(x.get('target'), number(x.get('value')), x.get('unit'), x.get('condition')) for x in effects if x.get('kind') == 'stat'}
    for boost in e.get('statBoosts', []):
        if (boost['stat'], number(boost.get('value')), boost.get('unit'), boost.get('condition')) not in existing:
            effects.append(dict(kind='stat', target=boost['stat'], operation='add', **{k: v for k, v in boost.items() if k != 'stat'}))
    used = Counter()
    for effect in effects:
        target, raw_operation = effect['target'], effect['operation']
        operation = raw_operation.split(':', 1)[0].strip()
        value = number(effect.get('value'))
        unit = effect.get('unit')
        explicit_level = re.fullmatch(r'grant: level (\d+)', raw_operation)
        if explicit_level and value is None:
            value, unit = float(explicit_level[1]), 'levels'
        identity = effect.get('id') or entity_id('effect', json.dumps([effect['kind'], target, raw_operation, unit, effect.get('condition')], ensure_ascii=False))
        used[identity] += 1
        suffix = f':{used[identity]}' if used[identity] > 1 else ''
        emit(f'effect:{identity}{suffix}', event_type='equipment_effect' if e['type'] == 'item' else 'effect',
             action='grant' if operation == 'grant' else 'modify', entity_name=target,
             entity_id=entity_id(effect['kind'], target), value=value, operation=operation,
             unit=unit, value_scope='modifier', value_kind='exact' if value is not None else 'unknown',
             source_item_id=base['entity_id'] if e['type'] == 'item' else None,
             condition=effect.get('condition') or (raw_operation.split(':', 1)[1].strip() if ':' in raw_operation and not explicit_level else None))
    return facts


def export(public, destination):
    records = [json.loads(line) for path in sorted(public.glob('book-*.jsonl'))
               for line in path.read_text().splitlines() if line.strip()]
    events = [r for r in records if r['recordType'] == 'event']
    characters = {r['name']: r['id'] for r in records if r['recordType'] == 'character'}
    ids = {e['id'] for e in events}
    if len(ids) != len(events):
        raise ValueError('Duplicate source event IDs')
    item_ids = {(e['subject'], e['name']): e['itemId'] for e in events if e['type']=='item' and e.get('itemId')}
    rows = [row for e in sorted(events, key=lambda e: (e['progress'], e['id'])) for row in event_rows(e, characters, item_ids)]
    assert len({r['row_id'] for r in rows}) == len(rows), 'Duplicate fact row IDs'
    assert {r['event_id'] for r in rows} == ids, 'Missing source events'
    assert all(set(r['related_event_ids']) <= ids for r in rows), 'Broken reward links'
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    version = next(r['series']['dataVersion'] for r in records if r['recordType'] == 'catalog')
    table = table.replace_schema_metadata({b'schema_version': b'1', b'dataset_version': version.encode(),
        b'grain': b'One atomic recorded fact per row; source event_id may repeat',
        b'source_event_count': str(len(events)).encode(),
        b'positions': b'chapter_position and reveal_progress are fractions from 0 to 1',
        b'privacy': b'Public summaries and source anchors only; evidence fields excluded'})
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, destination, compression='zstd', use_dictionary=True, row_group_size=10000)
    restored = pq.read_table(destination)
    assert table.equals(restored), 'Parquet round-trip changed the facts'
    result = dict(source_events=len(events), fact_rows=len(rows), columns=len(SCHEMA),
                  bytes=destination.stat().st_size, uncompressed_arrow_bytes=table.nbytes,
                  dataset_version=version, event_types=dict(Counter(r['event_type'] for r in rows)))
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, default=ROOT / 'data/public')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/exports/events.parquet')
    args = parser.parse_args()
    export(args.public, args.output)
