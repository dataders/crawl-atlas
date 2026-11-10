import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_single_board import build, reader_data
ROOT=Path(__file__).resolve().parents[1]

class DeathMarkerTests(unittest.TestCase):
    def test_reveal_and_rewind(self):
        data,_,_=reader_data(ROOT)
        death=next(e for e in data['events'] if e.get('subject')=='Miriam Dom' and e.get('lifeStatus')=='dead')
        def annotations(p):
            return build(ROOT,p,'Miriam Dom','overview',1360)['charts']['levels'].get('annotations',[])
        before=annotations(death['progress']-1e-8)
        after=annotations(death['progress'])
        count=lambda rows:sum(a.get('text')=='×' for a in rows)
        self.assertEqual(count(after),count(before)+1)
        self.assertEqual(count(annotations(death['progress']-1e-8)),count(before))
        self.assertTrue(all(e['lifeStatus']!='dead' for e in data['events'] if e['subject']=='Mordecai' and 'lifeStatus' in e))
