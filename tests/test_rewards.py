import json
import unittest
from pathlib import Path
from scripts.reward_provenance import acquisition_rows


class RewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads(Path('site/dist/data/series.json').read_text())['events']
        cls.rows, cls.links = acquisition_rows(cls.events)

    def test_boss_item_chain_preserves_cause_and_box(self):
        parents = {r['child_event_id']: r['parent_event_id'] for r in self.links}
        node = 'inv-014-second-major-opening-item-1-0'
        path = []
        while node in parents:
            node = parents[node]
            path.append(node)
        self.assertEqual(path, ['reward-hoarder-carl-open', 'reward-hoarder-carl-award', 'reward-hoarder-victory'])

    def test_benefactor_is_not_a_tier_and_details_are_not_backdated(self):
        box = [r for r in self.rows if r['box_id'] == 'imani-apothecary-hammer']
        self.assertTrue(all(r['box_kind'] == 'Benefactor' for r in box))
        early = [r for r in box if r['chapter'] == 57]
        self.assertTrue(all(r['box_tier'] is None for r in early))
        silver = next(r for r in box if r['box_tier'] == 'Silver')
        self.assertEqual(silver['source'], 'b5-c62-p44')

    def test_unattributed_batch_does_not_invent_specific_box(self):
        potion = next(r for r in self.rows if r['event_id'] == 'inv-004-first-ten-boxes-opened-item-3-0')
        self.assertEqual(potion['attribution'], 'batch')
        self.assertIsNone(potion['box_id'])
        self.assertTrue(any(r['outcome_type'] == 'boon' for r in self.rows))

    def test_future_links_and_cycles_are_rejected(self):
        def event(id, progress, parent):
            return dict(id=id, subject='Carl', name=id, book=1, chapter=1, progress=progress,
                        source='b1-c1-p1', confidence='verified',
                        acquisition=dict(stage='opened', sourceType='reward_box', parentEventIds=parent))
        with self.assertRaises(AssertionError):
            acquisition_rows([event('a', .1, ['b']), event('b', .2, [])])
        with self.assertRaises(AssertionError):
            acquisition_rows([event('a', .1, ['b']), event('b', .1, ['a'])])
