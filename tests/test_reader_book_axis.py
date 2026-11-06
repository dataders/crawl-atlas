import unittest
from html import escape
from scripts.reader_book_axis import clean_chart_labels


def panel(title, label):
    return (
        f'<svg><text data-authored-kind="title">{escape(title)}</text>'
        '<g data-dct-role="y-axis" role="graphics-symbol" '
        f'aria-label="Y-axis titled &#x27;{escape(label)}&#x27; for a linear scale with values from 4 to 26">'
        f'<g data-authored-kind="y_label"><text transform="rotate(90)">{escape(label)}</text></g>'
        '</g></svg>'
    )


class ReaderAxisTests(unittest.TestCase):
    def test_layer_names_do_not_leak_into_visual_or_accessible_axis_titles(self):
        before = '<svg>' + panel('Base strength', 'Base strength, Value, Estimate · Carl') + panel(
            'Base intelligence', 'Base intelligence, Value, Lower bound · Princess Donut') + '</svg>'
        after = clean_chart_labels(before)
        self.assertEqual(after, '<svg>' + panel('Base strength', 'Base strength') + panel(
            'Base intelligence', 'Base intelligence') + '</svg>')

    def test_estimate_only_chart_uses_its_metric_title(self):
        self.assertEqual(clean_chart_labels(panel('Base dexterity', 'Estimate · Li Na')),
                         panel('Base dexterity', 'Base dexterity'))

    def test_compact_wrapped_layer_title_keeps_text_geometry(self):
        label = 'Base strength, Value, Estimate · Carl, Lower bound · Princess Donut'
        before = panel('Base strength', label).replace(
            f'<text transform="rotate(90)">{label}</text>',
            '<text transform="rotate(90)" x="362.17" y="41">'
            '<tspan>Base strength, Value, Estimate · Carl,</tspan>'
            '<tspan x="362.17" dy="13">Lower bound · Princess Donut</tspan></text>')
        after = clean_chart_labels(before)
        self.assertIn('<text transform="rotate(90)" x="362.17" y="41">Base strength</text>', after)
        self.assertNotIn('tspan', after)
        self.assertNotIn('Estimate', after)
        self.assertIn('titled &#x27;Base strength&#x27; for a linear scale', after)

    def test_cleaning_twice_does_not_duplicate_tooltip_header_code(self):
        before = panel('Base strength', 'Base strength, Value') + '<script>function headerRow(entry, seriesColor, ts) {\n}</script>'
        once = clean_chart_labels(before)
        self.assertEqual(once, clean_chart_labels(once))
        self.assertEqual(once.count('const position = Number(entry.value);'), 1)

    def test_exact_only_chart_and_escaped_titles_are_preserved(self):
        for title in ('Level', 'Base charisma', 'A & B'):
            with self.subTest(title=title):
                self.assertEqual(clean_chart_labels(panel(title, title)), panel(title, title))


if __name__ == '__main__':
    unittest.main()
