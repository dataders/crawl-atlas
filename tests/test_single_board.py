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

class CheckpointTests(unittest.TestCase):
    def test_history_and_skill_updates_do_not_reexport_unrelated_inventory(self):
        import json,tempfile
        from export_single_board import catalog
        def event(p,kind,name,**extra):
            return dict(id=str(p),source=str(p),subject='Carl',progress=p,type=kind,name=name,**extra)
        events=[event(.1,'item','Ring',action='equip'),event(.2,'story','First story'),
                event(.25,'story','Later story'),event(.3,'skill','Spell'),event(.35,'skill','Spell'),
                event(.4,'story','Box',acquisition={'stage':'award'}),
                event(.45,'story','Second box',acquisition={'stage':'award'})]
        series={'characters':[{'name':'Carl'}],'events':events,'books':[{'startChapter':1}],
                'series':{'chapterCount':1}}
        facts=[{'character':'Carl','kind':'skill','progress':p}for p in (.3,.35)]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'site/dist/data').mkdir(parents=True);(root/'data/public').mkdir(parents=True)
            (root/'site/dist/data/floors.json').write_text('[]')
            (root/'data/public/reader-characters.json').write_text('["Carl"]')
            with patch('export_single_board.reader_data',return_value=(series,facts,{'observations':[]})):
                _,states=catalog(root)
            self.assertIn(.25,states['Carl']['history'])
            self.assertNotIn(.25,states['Carl']['inventory'])
            self.assertIn(.35,states['Carl']['overview'])
            self.assertNotIn(.35,states['Carl']['inventory'])
            self.assertIn(.45,states['Carl']['rewards'])
            self.assertNotIn(.45,states['Carl']['inventory'])

class ReleaseBoardTests(unittest.TestCase):
    def test_level_plot_is_readable_and_has_no_duplicate_scene_marks(self):
        from build_single_board import build
        root=Path(__file__).resolve().parents[1]
        board=build(root,1,'Carl','overview',1360)
        rows=board['queries']['levels']['rows']
        self.assertLessEqual(len({r['character'] for r in rows}),11)
        self.assertEqual(len(rows),len({(r['at'],r['character']) for r in rows}))
        self.assertIn('Carl',{r['character'] for r in rows})
        self.assertIn('Princess Donut',{r['character'] for r in rows})

    def test_wiki_reference_is_present_in_each_selected_dossier_tab(self):
        from build_single_board import build
        root=Path(__file__).resolve().parents[1]
        for tab in ('overview','inventory','rewards','history'):
            board=build(root,1,'Carl',tab,1360)
            dossier=board['rows'][-1]
            selected=next(t for t in dossier['tabs']['items'] if t['title']==dossier['tabs']['default'])
            self.assertIn('wiki_reference',selected['rows'])
            self.assertIn('target="_blank"',dossier['charts']['wiki_reference']['svg'])

if __name__=='__main__':unittest.main()
