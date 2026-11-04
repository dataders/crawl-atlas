"""Source-anchored acquisition chains; raw prose remains in the private corpus."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply_reward_audit(events, corpus):
    audit = json.loads((ROOT / 'data/public/reward-provenance.json').read_text())
    anchors = {p['anchor']: (b['number'], c['number'], p['position'])
               for b in corpus['books'] for c in b['chapters'] for p in c['paragraphs']}
    by_id = {e['id']: e for e in events}
    for row in audit['events']:
        if row['id'] in by_id:
            event = by_id[row['id']]
            event.update(row)
        else:
            event = {'confidence': 'verified', 'action': 'note', 'type': 'story', **row}
            events.append(event)
            by_id[event['id']] = event
        event['book'], event['chapter'], event['position'] = anchors[event['source']]
        for evidence in event.get('evidence', []):
            assert anchors[evidence] <= anchors[event['source']], 'Reward evidence reveals future text'
    return events


def acquisition_rows(events):
    rows, links = [], []
    by_id = {e['id']: e for e in events}
    for e in events:
        a = e.get('acquisition')
        if not a:
            continue
        rows.append(dict(event_id=e['id'], character=e['subject'], name=e['name'],
            stage=a['stage'], source_type=a['sourceType'], box_id=a.get('boxId'),
            box_tier=a.get('boxTier'), box_kind=a.get('boxKind'),
            outcome_type=a.get('outcomeType'), occurrence_detail=a.get('occurrenceDetail'),
            quantity=a.get('quantity'), reason_type=a.get('reasonType'),
            reason_detail=a.get('reasonDetail'), attribution=a.get('attribution', 'explicit'),
            book=e['book'], chapter=e['chapter'], progress=e['progress'],
            source=e['source'], confidence=e['confidence'], summary=e.get('summary', '')))
        for parent_id in a.get('parentEventIds', []):
            assert parent_id in by_id, f'Unknown acquisition parent {parent_id}'
            parent = by_id[parent_id]
            assert parent.get('acquisition'), f'Parent lacks acquisition metadata: {parent_id}'
            assert parent['progress'] <= e['progress'], 'Acquisition link reveals future evidence'
            assert parent_id != e['id'], 'Self-referencing acquisition'
            links.append(dict(child_event_id=e['id'], parent_event_id=parent_id))
    parents = {}
    for link in links:
        parents.setdefault(link['child_event_id'], []).append(link['parent_event_id'])
    def visit(node, visiting, visited):
        assert node not in visiting, 'Cycle in acquisition chain'
        if node in visited:
            return
        visiting.add(node)
        for parent in parents.get(node, []):
            visit(parent, visiting, visited)
        visiting.remove(node)
        visited.add(node)
    visited = set()
    for row in rows:
        visit(row['event_id'], set(), visited)
    return rows, links
