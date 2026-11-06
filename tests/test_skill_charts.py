import unittest
from scripts.render_skill_charts import qualifying_rows, board_spec


def row(value, progress, skill='Pugilism', scope='base'):
    return dict(value=value, progress=progress, metric=skill, scope=scope)


class SkillChartTests(unittest.TestCase):
    def test_skill_color_is_shared_but_scope_lines_stay_separate(self):
        rows = [row(6,.1), row(9,.2,scope='effective'), row(7,.3,scope='reported')]
        rows = [r | dict(book=1,chapter=1,position=.5) for r in rows]
        spec = board_spec(rows,1,900,{1:10})
        chart = spec['charts']['history']
        self.assertEqual(chart['query'], 'base')
        self.assertEqual({r['skill'] for q in spec['queries'].values() for r in q['rows']}, {'Pugilism'})
        self.assertEqual([l['style']['marks']['line']['stroke']['dasharray'] for l in chart['layers']], ['2 4','7 4'])

    def test_above_five_is_strict_and_future_cannot_qualify(self):
        rows = [row(5,.1), row(6,.9)]
        self.assertEqual(qualifying_rows(rows,.5), [])
        self.assertEqual(qualifying_rows(rows,1), rows)

    def test_two_changes_not_two_repeated_observations(self):
        rows = [row(1,.1), row(1,.2), row(2,.3), row(3,.4)]
        self.assertEqual(qualifying_rows(rows,.3), [])
        self.assertEqual(qualifying_rows(rows,.4), rows)

    def test_scope_changes_dont_count_as_level_changes(self):
        rows = [row(1,.1),row(2,.2,scope='effective'),row(3,.3,scope='equipment')]
        self.assertEqual(qualifying_rows(rows,1), [])

    def test_unknown_level_never_becomes_zero(self):
        rows = [row(None,.1),row(6,.2)]
        self.assertEqual(qualifying_rows(rows,1), [rows[1]])

    def test_latest_level_rule_rewinds_and_handles_decrease(self):
        rows = [row(6,.1),row(5,.2)]
        self.assertEqual(qualifying_rows(rows,.1), rows[:1])
        self.assertEqual(qualifying_rows(rows,.2), [])
