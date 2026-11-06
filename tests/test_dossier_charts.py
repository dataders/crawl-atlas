import unittest
from scripts.render_dossier_charts import observations, checkpoints, board_spec, ribbon_rows, finish_svg

BOOKS = [{'number': 1, 'chapterCount': 10, 'startChapter': 1},
         {'number': 2, 'chapterCount': 10, 'startChapter': 11}]


def fact(**kwargs):
    return {'character': 'Carl', 'metric': 'DEX', 'kind': 'stat', 'value': 5,
            'scope': 'base', 'source': 'b1-c1-p1', 'book': 1, 'chapter': 1,
            'position': .5, 'progress': .025, **kwargs}


def point(x, value, kind):
    return {'stat': 'Strength', 'kind': kind, 'book_position': x, 'value': value}


class DossierChartTests(unittest.TestCase):
    def test_only_explicit_absolute_total_enters_total_series(self):
        progression = [fact(), fact(scope='equipment', value=3, source='b1-c1-p2'),
                       fact(scope='reported', value=99, source='b1-c1-p3'),
                       fact(scope='base', value=None, source='b1-c1-p4')]
        total = fact(source='b1-c2-p1', chapter=2, progress=.075, total=12, confidence='verified')
        points = observations(progression, {'observations': [total]}, BOOKS)
        self.assertEqual([(p['kind'], p['value']) for p in points], [('base', 5), ('total', 12)])
        self.assertNotIn('base', total)

    def test_inferred_total_stays_separate_from_exact_total_and_ribbon(self):
        row = fact(total=64, confidence='inferred')
        points = observations([], {'observations': [row]}, BOOKS)
        self.assertEqual(points[0]['kind'], 'total-estimate')
        chart = board_spec(points, 1, 440)
        rows = chart['queries']['observations']['rows']
        self.assertEqual([r['kind'] for r in rows], ['total-estimate'])
        self.assertIn('estimated total', rows[0]['description'])

    def test_reported_estimate_does_not_claim_base_or_total_scope(self):
        points = observations([fact(scope='reported', confidence='inferred', value=30)], {}, BOOKS)
        self.assertEqual(points[0]['kind'], 'reported-estimate')
        self.assertEqual(ribbon_rows(points), [])
        rows = board_spec(points, 1, 440)['queries']['observations']['rows']
        self.assertEqual(rows[0]['kind'], 'reported-estimate')
        self.assertIn('reported estimate; modifier scope unknown', rows[0]['description'])

    def test_unshaded_checkpoint_keeps_numeric_lower_column(self):
        rows = board_spec(observations([fact()], {}, BOOKS), 1, 440)['queries']['observations']['rows']
        self.assertEqual(rows[0]['lower'], 5)

    def test_checkpoint_boundaries_never_include_future_observations(self):
        points = observations([fact(), fact(progress=.55, book=2, source='b2-c2-p1', value=10)], {}, BOOKS)
        self.assertEqual(checkpoints(points, BOOKS, 20), [(.025, 1), (.5, 2), (.55, 2)])
        visible = [p for p in points if p['progress'] <= .5]
        chart = board_spec(visible, 2, 440)
        self.assertEqual([r['value'] for r in chart['queries']['observations']['rows']], [5])
        self.assertEqual(chart['charts']['stats']['options']['books'], 2)

    def test_all_five_stats_share_one_color_per_metric_and_disable_embed_chrome(self):
        rows = [fact(metric=m, source=f'b1-c1-{m}', base=5, total=10, confidence='verified')
                for m in ['STR', 'INT', 'CON', 'DEX', 'CHA']]
        board = board_spec(observations([], {'observations': rows}, BOOKS), 1, 900)
        self.assertEqual(len(board['style']['charts']['category_colors']['stat']['values']), 5)
        self.assertEqual(board['charts']['stats']['type'], 'custom')
        self.assertFalse(board['style']['footer']['visible'])
        self.assertFalse(board['style']['timestamp']['visible'])
        self.assertEqual(len(board['queries']['observations']['rows']), 10, 'no fabricated base points')

    def test_ribbon_clips_to_overlap_and_interpolates_each_visible_series(self):
        rows = ribbon_rows([point(0, 5, 'base'), point(100, 15, 'base'),
                            point(50, 20, 'total'), point(150, 40, 'total')])
        self.assertEqual([(r['book_position'], r['lower'], r['value']) for r in rows],
                         [(50, 10, 20), (100, 15, 30)])

    def test_ribbon_uses_every_knot_so_shading_follows_actual_lines(self):
        rows = ribbon_rows([point(0, 0, 'base'), point(50, 10, 'base'), point(100, 10, 'base'),
                            point(0, 10, 'total'), point(100, 30, 'total')])
        self.assertEqual([(r['book_position'], r['lower'], r['value']) for r in rows],
                         [(0, 0, 10), (50, 10, 20), (100, 10, 30)])

    def test_ribbon_requires_two_exact_points_per_series_and_overlapping_domains(self):
        base = [point(0, 5, 'base'), point(100, 15, 'base')]
        self.assertEqual(ribbon_rows(base + [point(50, 20, 'total')]), [])
        self.assertEqual(ribbon_rows(base + [point(0, 10, 'total-estimate'), point(100, 30, 'total-estimate')]), [])
        self.assertEqual(ribbon_rows(base + [point(110, 20, 'total'), point(150, 40, 'total')]), [])

    def test_source_titles_become_keyboard_accessible_without_changing_geometry(self):
        svg = '<svg><circle cx="1" cy="2" r="3"><title>STR &gt; 10</title></circle><circle cx="5" cy="6" r="3"/></svg>'
        result = finish_svg(svg, [], 1)
        self.assertIn('cx="1" cy="2" r="3" tabindex="0" role="img" aria-label="STR &gt; 10"', result)
        self.assertIn('<circle cx="5" cy="6" r="3"/>', result)
        self.assertEqual(result.count('<circle'), 2)


if __name__ == '__main__':
    unittest.main()
