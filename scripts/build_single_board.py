"""Build one complete native dbt Charts board for a frozen reader state.

The static host selects whole artifacts; it never stitches SVGs or table rows.
This proof uses the existing audited stat template and native line/table charts.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import shutil
from render_dossier_charts import observations, board_spec as stats_board
from render_skill_charts import qualifying_rows, board_spec as skills_board

ROOT = Path(__file__).resolve().parents[1]
TABS = ('overview', 'inventory', 'rewards', 'history', 'equipped')


def dim_color(color):
    background = (22, 28, 24)
    rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return '#' + ''.join(f'{round(v*.60+b*.40):02x}' for v,b in zip(rgb,background))


def character_order(series, facts, audit, cutoff):
    """Rank revealed characters by distinct exact base-stat observations.

    A first numeric measurement counts once; subsequent measurements count only
    when that stat's value changes. Totals, bonuses, estimates and lower bounds
    do not inflate this measure. No future observation affects the order.
    """
    canonical = lambda name: 'Princess Donut' if name == 'Donut' else name
    roster = {c['name'] for c in series['characters'] if c['name'] != 'Party'}
    known = {canonical(r['character']) for r in facts if r['progress'] <= cutoff and canonical(r['character']) in roster}
    known.update(canonical(e.get('subject')) for e in series['events']
                 if e['progress'] <= cutoff and canonical(e.get('subject')) in roster)
    counts, previous = {}, {}
    for point in observations(facts, audit, series['books']):
        if point['progress'] > cutoff or point['kind'] != 'base':
            continue
        value = point['value']
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        name = canonical(point['character'])
        known.add(name)
        key = (name, point['stat'])
        if key not in previous or previous[key] != value:
            counts[name] = counts.get(name, 0) + 1
        previous[key] = value
    return sorted(known & roster, key=lambda name: (-counts.get(name, 0), name.casefold()))


def detail_rows(data_root, progress, character):
    """Use the same pure inventory/reward/history reducers as the reader."""
    javascript = r'''
const fs = require('node:fs');
const [root, dataRoot, cutoffText, character] = process.argv.slice(1);
const cutoff = Number(cutoffText);
const {inventoryAt,inventoryRecord,storyEntries} = require(root+'/site/dist/detail-model.js');
const {rewardRows,rewardRecord} = require(root+'/site/dist/rewards.js');
const {dossierRecord,dossierEvents,isRecordedEquipped} = require(root+'/site/dist/board-details.js');
const data = JSON.parse(fs.readFileSync(dataRoot+'/site/dist/data/series.json'));
const facts = JSON.parse(fs.readFileSync(dataRoot+'/site/dist/data/progression.json'));
const visible = data.events.filter(e=>e.progress<=cutoff).sort((a,b)=>a.progress-b.progress);
const own = dossierEvents(visible,character);
const items = inventoryAt(visible).filter(e=>e.subject===character||(character==='Princess Donut'&&e.subject==='Donut'));
items.sort((a,b)=>(b.acquiredProgress??b.progress)-(a.acquiredProgress??a.progress));
console.log(JSON.stringify({
 inventory:items.map(e=>dossierRecord('inventory',inventoryRecord(e))),
 equipped:items.filter(isRecordedEquipped).map(e=>dossierRecord('inventory',inventoryRecord(e))),
 rewards:rewardRows(own,visible).sort((a,b)=>b.event.progress-a.event.progress).map(e=>dossierRecord('rewards',rewardRecord(e))),
 history:storyEntries(own,facts,cutoff).map(e=>({...dossierRecord('story',e.row),evidence:e.note}))
}));
'''
    return json.loads(subprocess.check_output(['node', '-e', javascript, str(ROOT), str(data_root), str(progress), character], text=True))


def axis(books):
    value = '(isDate(datum.value) ? toNumber(datum.value)/86400000 : toNumber(datum.value))'
    step = 25 if books == 1 else 100
    expr = f"{value} >= {books*100} ? '' : {value}%100 === 0 ? 'B' + (1+{value}/100) : ({value}%100) + '%'"
    return {'scale': {'nice': False, 'values': list(range(0, books*100, step)),
                      'continuous': {'domain': [0, books*100]}},
            'labels': {'expr': expr}, 'grid': {'visible': False}}


def nested(board):
    """Inherit the parent theme and emit only one board footer."""
    return {key: value for key, value in board.items() if key not in ('extends', 'width')}


def build(data_root, progress, character, tab, width):
    dist = data_root / 'site/dist/data'
    series = json.loads((dist / 'series.json').read_text())
    facts = json.loads((dist / 'progression.json').read_text())
    visible = [row for row in facts if row['progress'] <= progress]
    books = max(b['number'] for b in series['books'] if (b['startChapter']-1)/series['series']['chapterCount'] <= progress)
    counts = {b['number']: b['chapterCount'] for b in series['books']}
    audit = json.loads((data_root/'data/public/stat-breakdown-audit.json').read_text())
    ordered_characters = character_order(series, facts, audit, progress)
    known = set(ordered_characters)
    if character not in known and progress > 0:
        raise ValueError(f'{character} has no revealed observations at this position')
    level = [{'at': (r['book']-1)*100+100*(r['chapter']-1+r['position'])/counts[r['book']],
              'level': r['value'], 'character': r['character']} for r in visible
             if r['kind']=='level' and r['value'] is not None and r['scope'] not in ('estimate','lower-bound')]
    board = json.loads((ROOT/'charts/reader.yml').read_text())
    board['width'] = width
    board['style']['charts']['category_colors'] = {'character':{'values':{c['name']:(c.get('color','#8e9c90') if c['name'] in ('Carl','Princess Donut') else dim_color(c.get('color','#8e9c90'))) for c in series['characters'] if c['name'] in {r['character'] for r in level}}}}
    board['queries'] = {}
    dossier = board['rows'][1]
    board['rows'] = []
    if level:
        board['queries']['levels']={'type':'values','rows':level}
        board['charts']['levels']['style']['axis_x'] = axis(books)
        floor_path = dist/'floors.json'
        if floor_path.exists() and width>=800:
            floor_entries = [e for e in json.loads(floor_path.read_text()) if (series['books'][e['book']-1]['startChapter']+e['chapter']-2+e['position'])/series['series']['chapterCount'] <= progress]
            coord = lambda e: (e['book']-1)*100+100*(e['chapter']-1+e['position'])/counts[e['book']]
            current_book = series['books'][books-1]
            end = (books-1)*100+100*(progress*series['series']['chapterCount']-(current_book['startChapter']-1))/counts[books]
            board['charts']['levels']['annotations'] = [
                {'type':'band','x':{'from':coord(e),'to':coord(floor_entries[i+1]) if i+1<len(floor_entries) else end},'text':f'Floor {e["floor"]}'}
                for i,e in enumerate(floor_entries) if (coord(floor_entries[i+1]) if i+1<len(floor_entries) else end)>coord(e)]
        board['rows'].append('levels')
    else:
        board['charts'].pop('levels',None)
        board['rows'].append({'text':'No levels recorded at this reading position.'})
    points=[p for p in observations(facts,audit,series['books']) if p['character']==character and p['progress']<=progress]
    skill_rows=qualifying_rows([r for r in visible if r['kind']=='skill' and r['character']==character],progress)
    overview=[]
    if points:
        stats=stats_board(points,books,width-40)
        for record in stats['queries']['observations']['rows']:
            if record.get('description'):
                record['description']=record['description'].split('. ')[0]+'.'
        overview.append(nested(stats))
        overview.append({'text':'— Base · – – With modifiers · ○ Estimate / minimum'})
    if skill_rows:
        skill_spec=skills_board(skill_rows,books,width-40,counts)
        skill_spec['charts']['history']['style']['axis_x']=axis(books)
        overview.append(nested(skill_spec))
    if not overview:
        overview=[{'text':'No stat or skill measurements recorded at this position.'}]
    tables=detail_rows(data_root,progress,character)
    tabs = dossier['tabs']['items']
    tabs[0]['rows'] = overview
    gear_tabs = tabs[1]['rows'][0]['tabs']
    gear_tabs['items'][0]['rows'][0]['queries']['inventory_entries']['rows'] = tables['inventory']
    if tables['equipped']:
        gear_tabs['items'][1]['rows'][1]['queries']['equipped_entries']['rows'] = tables['equipped']
    else:
        gear_tabs['items'] = gear_tabs['items'][:1]
    gear_tabs['default'] = 'Equipped' if tab == 'equipped' and tables['equipped'] else 'All items'
    for item, name in zip(tabs[2:], ('rewards', 'history')):
        if tables[name]:
            item['rows'][0]['queries'][name+'_entries']['rows'] = tables[name]
        else:
            item['rows'] = [{'text':'No entries recorded at this position.'}]
    available = [item for i, item in enumerate(tabs) if (bool(points or skill_rows) if i == 0 else bool(tables[TABS[i]]))]
    if available: dossier['tabs']['items'] = available
    dossier['title'] = character
    dossier['variables']['character'] = {'options':{'static':ordered_characters},'default':character,'required':True}
    dossier['tabs']['default'] = {'overview':'Overview','inventory':'Inventory','rewards':'Boxes & rewards','history':'History','equipped':'Inventory'}[tab]
    if dossier['tabs']['default'] not in {item['title'] for item in dossier['tabs']['items']}:
        dossier['tabs']['default'] = dossier['tabs']['items'][0]['title']
    board['rows'].append(dossier)
    return board


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progress',type=float,default=1)
    parser.add_argument('--character',default='Carl')
    parser.add_argument('--tab',choices=TABS,default='overview')
    parser.add_argument('--width',type=int,default=1360)
    parser.add_argument('--data-root',type=Path,default=Path('/tmp/atlas-next'))
    parser.add_argument('--output',type=Path,default=Path('/tmp/atlas-single-board.yml'))
    args=parser.parse_args()
    if not 0<=args.progress<=1: parser.error('--progress must be between zero and one')
    if args.width<320: parser.error('--width must be at least 320')
    args.output.write_text(json.dumps(build(args.data_root,args.progress,args.character,args.tab,args.width),ensure_ascii=False,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='atlas-native-') as scratch:
        project = Path(scratch)
        (project/'dbt_charts.yml').write_text('{}\n')
        staged = project/args.output.name
        shutil.copyfile(args.output, staged)
        subprocess.run(['dct','validate',str(staged),'--strict','--project-dir',str(project)],check=True)
        subprocess.run(['dct','render',str(staged),'--format','html','--output',str(args.output.with_suffix('.html')),'--project-dir',str(project),'--no-cache'],check=True)
    print(args.output.with_suffix('.html'))

if __name__=='__main__': main()
