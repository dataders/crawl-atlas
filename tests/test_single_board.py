import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_single_board import character_order

class RankingTests(unittest.TestCase):
    def test_only_revealed_changed_base_measurements_count(self):
        series={'characters':[{'name':'Carl'},{'name':'Princess Donut'},{'name':'Juice Box'},{'name':'Party'}],
                'books':[{'number':1,'chapterCount':10}],
                'events':[{'subject':'Carl','progress':0},{'subject':'Princess Donut','progress':0},
                          {'subject':'Party','progress':0},{'subject':'Juice Box','progress':.9}]}
        def row(name,stat,value,at,kind='base'):
            return {'character':name,'metric':stat,'value':value,'progress':at,'book':1,'chapter':1,
                    'position':at,'kind':'stat','scope':kind,'source':f'{name}-{stat}-{at}'}
        facts=[row('Carl','STR',6,.1),row('Carl','STR',6,.2),row('Princess Donut','CHA',25,.3),
               row('Princess Donut','CHA',30,.4),row('Carl','INT',50,.5,'estimate')]
        audit={'observations':[]}
        self.assertEqual(character_order(series,facts,audit,.25),['Carl','Princess Donut'])
        self.assertEqual(character_order(series,facts,audit,.5),['Princess Donut','Carl'])
        self.assertEqual(character_order(series,facts,audit,1),['Princess Donut','Carl','Juice Box'])
        self.assertEqual(character_order(series,facts,audit,.25),['Carl','Princess Donut'])

    def test_static_host_does_not_construct_svg_or_table_rows(self):
        source=(Path(__file__).resolve().parents[1]/'site/dist/static-reader.js').read_text()
        for forbidden in ('createElementNS','innerHTML','data-detail-table','<svg','<path','<table'):
            self.assertNotIn(forbidden,source)
        self.assertIn("dbt-variable-change",source)
        self.assertIn("DecompressionStream('gzip')",source)

if __name__=='__main__':unittest.main()
