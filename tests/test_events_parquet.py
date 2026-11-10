import importlib.util
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
HAS_ARROW = importlib.util.find_spec('pyarrow') is not None
if HAS_ARROW:
    from export_events_parquet import event_rows, SCHEMA
    import pyarrow as pa


@unittest.skipUnless(HAS_ARROW, 'Run with uv run --with pyarrow python -m unittest discover -s tests')
class EventParquetTests(unittest.TestCase):
    def event(self, **updates):
        return dict(id='event-1', book=1, chapter=5, position=.4, progress=.01,
                    source='b1-c5-p48', subject='Carl', type='story', name='Readout',
                    summary='Public paraphrase.', confidence='verified',
                    metadata={'discoveryBatch': 'audit'}, **updates)

    def test_multistat_facts_preserve_original_id_and_spoiler_boundary(self):
        rows = event_rows(self.event(stats={'STR': 10, 'DEX': 7}), {'Carl': 'carl'})
        stats = [r for r in rows if r['event_type'] == 'stat']
        self.assertEqual({r['entity_name']: r['value'] for r in stats}, {'STR': 10, 'DEX': 7})
        self.assertEqual(len({r['row_id'] for r in rows}), len(rows))
        self.assertTrue(all(r['event_id'] == 'event-1' and r['reveal_progress'] == .01 for r in rows))

    def test_unknown_equipment_total_does_not_hide_effect(self):
        e = self.event()
        e.update(type='item', name='Jacket', itemId='jacket', effects=[
            dict(id='strength', kind='stat', target='STR', operation='add', value=5, unit='points')])
        effect = next(r for r in event_rows(e, {}) if r['event_type'] == 'equipment_effect')
        self.assertEqual((effect['value'], effect['operation'], effect['source_item_id']), (5, 'add', 'jacket'))
        self.assertEqual(effect['value_scope'], 'modifier')

    def test_reward_links_and_historical_death_survive(self):
        rows = event_rows(self.event(lifeStatus='dead', historyOnly=True,
                                    acquisition={'stage': 'opened', 'parentEventIds': ['award-1']}), {})
        self.assertTrue(all(r['related_event_ids'] == ['award-1'] for r in rows))
        death = next(r for r in rows if r['event_type'] == 'life_status')
        self.assertEqual(death['state_after'], 'dead')
        self.assertTrue(death['history_only'])

    def test_no_private_evidence_in_metadata(self):
        rows = event_rows(self.event(evidenceSentences=['SECRET'], evidence={'nested': 'SECRET'},
                                    effects=[dict(kind='benefit', target='X', operation='grant', evidence='SECRET')]), {})
        self.assertTrue(all('SECRET' not in r['metadata']['attributes_json'] for r in rows))

    def test_unknown_skill_is_null_and_group_is_not_character(self):
        e = self.event()
        e.update(type='skill', subject='Party')
        rows = event_rows(e, {'Party': 'party'})
        self.assertIsNone(rows[0]['value'])
        self.assertIsNone(rows[0]['character_id'])
        self.assertEqual(rows[0]['subject_type'], 'group')
        self.assertEqual(pa.Table.from_pylist(rows, schema=SCHEMA).num_rows, 1)


if __name__ == '__main__':
    unittest.main()
