"""Source-anchored acquisition chains; raw prose remains in the private corpus."""
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
