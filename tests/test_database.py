import json
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.build_database import build, progression_rows


class DatabaseTests(unittest.TestCase):
    def event(self, progress, value=None, scope='base', **extra):
        return dict(id=str(progress), type='stat', subject='Carl', name='Stats',
                    stats={'STR': value} if value is not None else {},
                    statScopes={'STR': scope}, confidence='verified', book=1,
                    chapter=1, position=progress, progress=progress, source='b1-c1-p1', **extra)

    def test_scopes_never_mix_and_unknown_is_not_zero(self):
        rows = progression_rows([self.event(.1, 5), self.event(.2, 9, 'equipment'), self.event(.3, 7)])
        self.assertEqual([r['delta'] for r in rows], [None, None, 2])
        self.assertEqual(rows[-1]['previous'], 5)

    def test_modifier_has_change_without_invented_total(self):
        rows = progression_rows([self.event(.1, 9, 'equipment'),
            self.event(.2, scope='equipment', statsDelta={'STR': 3}, action='delta'),
            self.event(.3, 15, 'equipment')])
        self.assertEqual(rows[1]['delta'], 3)
        self.assertIsNone(rows[1]['value'])
        self.assertIsNone(rows[1]['previous'])
        self.assertIsNone(rows[2]['delta'])

    def test_future_observations_cannot_change_prior_rows(self):
        early = [self.event(.1, 5), self.event(.2, 7)]
        self.assertEqual(progression_rows(early), progression_rows(early + [self.event(.9, 40)])[:2])

    def test_unquantified_growth_invalidates_previous_total(self):
        events = [dict(self.event(.1), type='level', level=24),
                  dict(self.event(.2), type='level', level=None, action='increase'),
                  dict(self.event(.3), type='level', level=50)]
        rows = progression_rows(events)
        self.assertEqual(rows[1]['previous'], 24)
        self.assertIsNone(rows[1]['value'])
        self.assertIsNone(rows[1]['delta'])
        self.assertIsNone(rows[2]['delta'])

    def test_database_covers_every_event_and_progression_event(self):
        source = Path('site/dist/data/series.json')
        data = json.loads(source.read_text())
        with tempfile.TemporaryDirectory() as directory:
            rows = build(source, Path(directory))
            with closing(sqlite3.connect(Path(directory) / 'crawl-atlas.sqlite')) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], len(data['events']))
                expected = {e['id'] for e in data['events'] if e['type'] in ('stat', 'skill', 'level')}
                self.assertEqual({r['event_id'] for r in rows}, expected)
                self.assertEqual(rows, json.loads(Path('site/dist/data/progression.json').read_text()))

class CuratedRegressionTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path('site/dist/data/series.json').read_text())

    def test_imani_milestones_use_first_reveal(self):
        imani = [e for e in self.data['events'] if e['subject'] == 'Imani C.' and e['type'] == 'level']
        self.assertIn((11, 'b1-c27-p9'), [(e['level'], e['source']) for e in imani])
        self.assertIn((24, 'b3-c8-p96'), [(e['level'], e['source']) for e in imani])
        point = next(e['progress'] for e in imani if e['level'] == 24)
        self.assertEqual([e for e in imani if e['progress'] < point][-1]['level'], 11)

    def test_dialogue_level_belongs_to_subject_not_speaker(self):
        events = [e for e in self.data['events'] if e['source'] == 'b7-c79-p71' and e['type'] == 'level']
        self.assertEqual([(e['subject'], e['level']) for e in events], [('Princess Donut', 135)])

    def test_profile_changes_have_their_own_source_boundary(self):
        events = [e for e in self.data['events'] if e['subject'] == 'Imani C.' and 'profile' in e]
        self.assertEqual({e['source'] for e in events}, {'b3-c8-p97', 'b3-c8-p98'})

class BookEightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads(Path('site/dist/data/series.json').read_text())['events']
        cls.rows = progression_rows(cls.events)

    def test_audit_is_published_without_missing_records(self):
        audit = json.loads(Path('data/public/book-8-audit.json').read_text())
        published = [e for e in self.events if e['book'] == 8]
        imani = json.loads(Path('data/public/imani-audit.json').read_text())
        additions = [e for e in imani['events'] if e['source'].startswith('b8-')]
        rewards = json.loads(Path('data/public/reward-provenance.json').read_text())
        new_rewards = [e for e in rewards['events'] if e['source'].startswith('b8-') and e['id'].startswith('reward-')]
        self.assertEqual(len(published), len(audit['events']) + len(additions) + len(new_rewards))
        self.assertEqual(len([e for e in published if e['type'] == 'level']), 7)

    def test_skill_scope_does_not_invent_training_growth(self):
        rows = [r for r in self.rows if r['book'] == 8 and r['metric'] == 'Second Chance']
        self.assertEqual({(r['scope'], r['value']) for r in rows}, {('base', 11), ('effective', 12)})
        self.assertTrue(all(r['delta'] is None for r in rows))

    def test_costume_skill_alias_and_retrospective_do_not_regress(self):
        row = next(r for r in self.rows if r['metric'] == 'Fursona' and r['value'] == 8)
        self.assertEqual((row['previous'], row['delta']), (6, 2))
        self.assertFalse(any(e['source'] == 'b8-c25-p13' for e in self.events))

    def test_item_thresholds_and_promises_are_not_learned_levels(self):
        skills = [e for e in self.events if e['book'] == 8 and e['type'] == 'skill']
        self.assertFalse(any(e['name'] == 'Oozy Form' and e.get('level') == 15 for e in skills))
        self.assertFalse(any(e['name'] == 'Gatekeeper' for e in skills))
        self.assertFalse(any(e['name'] == 'Razzmatazz' and e.get('level') is not None for e in skills))
        self.assertTrue(all(e['source'] != 'b8-c16-p27' for e in self.events))

    def test_confirmations_remain_searchable_in_book_eight(self):
        row = next(r for r in self.rows if r['book'] == 8 and r['character'] == 'Princess Donut' and r['kind'] == 'level')
        self.assertEqual((row['value'], row['delta']), (135, 0))

    def test_temporary_equipment_has_explicit_end(self):
        rows = [r for r in self.rows if r['book'] == 8 and r['character'] == 'Carl' and r['metric'] == 'Jump' and r['scope'] == 'equipment']
        self.assertEqual([r['action'] for r in rows], ['set', 'remove'])
        self.assertIsNone(rows[-1]['value'])


class ImaniAuditTests(unittest.TestCase):
    def test_later_growth_and_borrowed_spell_keep_unknown_totals(self):
        events = json.loads(Path('site/dist/data/series.json').read_text())['events']
        mine = [e for e in events if e['subject'] == 'Imani C.']
        growth = next(e for e in mine if e['source'] == 'b5-c36-p14')
        self.assertEqual(growth['action'], 'increase')
        self.assertIsNone(growth['level'])
        self.assertIn('b5-c36-p12', growth['evidence'])
        for e in mine:
            if e['name'] == 'Tripper':
                self.assertEqual(e['skillScope'], 'granted')
                self.assertIsNone(e.get('level'))
        self.assertTrue(any(e['name'] == 'Confuzzled' for e in mine))
