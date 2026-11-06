import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_single_board import character_order, detail_rows
from unittest.mock import patch

class RankingTests(unittest.TestCase):
    def test_cached_detail_rows_are_isolated_between_layouts(self):
        shared={"effects":[{"effect":"STR +2"}]}
        with patch("build_single_board._detail_rows", return_value=shared):
            first=detail_rows(Path("/tmp"),1,"Carl")
            first["effects"][0]["effect"]="compact"
            self.assertEqual(detail_rows(Path("/tmp"),1,"Carl"),shared)
            self.assertEqual(shared["effects"][0]["effect"],"STR +2")

    def test_order_counts_revealed_updates_not_only_base_stats(self):
        series={'characters':[{'name':'Carl'},{'name':'Princess Donut'},{'name':'Party'}],
                'events':[{'subject':'Carl','progress':.1,'source':'a','type':'item','name':'Jacket'},
                          {'subject':'Princess Donut','progress':.2,'source':'b','type':'skill','name':'Spell'},
                          {'subject':'Princess Donut','progress':.3,'source':'c','type':'level','name':'Level'},
                          {'subject':'Party','progress':0,'source':'d'}]}
        self.assertEqual(character_order(series,[],{},.1),['Carl'])
        self.assertEqual(character_order(series,[],{},.3),['Princess Donut','Carl'])
        series['events'].append(dict(series['events'][0]))
        self.assertEqual(character_order(series,[],{},.3),['Princess Donut','Carl'])
        self.assertEqual(character_order(series,[],{},.1),['Carl'])

    def test_static_host_does_not_construct_svg_or_table_rows(self):
        source=(Path(__file__).resolve().parents[1]/'site/dist/static-reader.js').read_text()
        for forbidden in ('createElementNS','innerHTML','data-detail-table','<svg','<path','<table'):
            self.assertNotIn(forbidden,source)
        self.assertIn("dbt-variable-change",source)
        self.assertIn("DecompressionStream('gzip')",source)

if __name__=='__main__':unittest.main()
