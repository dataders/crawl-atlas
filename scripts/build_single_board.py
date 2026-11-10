"""Build one complete native dbt Charts board for a frozen reader state.

The static host selects whole artifacts; it never stitches SVGs or table rows.
This proof uses the existing audited stat template and native line/table charts.
"""
import argparse
from zlib import crc32
import json
from pathlib import Path
import subprocess
import tempfile
import shutil
from functools import lru_cache
from copy import deepcopy
from render_dossier_charts import observations, board_spec as stats_board
from render_skill_charts import qualifying_rows
from wiki_links import wiki_link, wiki_label

ROOT = Path(__file__).resolve().parents[1]
TABS = ('overview', 'inventory', 'rewards', 'history', 'equipped')


def dim_color(color):
    background = (22, 28, 24)
    rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return '#' + ''.join(f'{round(v*.60+b*.40):02x}' for v,b in zip(rgb,background))


def character_order(series, facts, audit, cutoff):
    """Rank by revealed updates; multiple metrics from one event count once."""
    canonical = lambda name: 'Princess Donut' if name == 'Donut' else name
    roster = {c['name'] for c in series['characters'] if c['name'] != 'Party'}
    roster &= set(json.loads((ROOT/'data/public/reader-characters.json').read_text()))
    updates = {}
    for event in series['events']:
        name = canonical(event.get('subject'))
        if event['progress'] <= cutoff and name in roster:
            # One source scene/type/name is one update, even if multiple audits
            # record it or its numeric facts have been expanded into rows.
            updates.setdefault(name, set()).add((event.get('source', event.get('id', event['progress'])),
                                                event.get('type'), event.get('name')))
    return sorted(updates, key=lambda name: (-len(updates[name]), name.casefold()))


def detail_rows(data_root, progress, character):
    # Tabs share frozen data; callers may reshape rows for compact layouts.
    return deepcopy(_detail_rows(data_root, progress, character))


@lru_cache(maxsize=16)
def _detail_rows(data_root, progress, character):
    """Use the same pure inventory/reward/history reducers as the reader."""
    process = _start_detail_worker(data_root)
    process.stdin.write(json.dumps(dict(cutoff=progress, character=character)) + "\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


@lru_cache(maxsize=None)
def reader_data(root):
    from build_public_timeline import compile_books
    from build_database import progression_rows
    series, audit = compile_books(root / "data/public")
    return series, progression_rows([e for e in series["events"] if not e.get("historyOnly")]), audit


@lru_cache(maxsize=None)
def _start_detail_worker(root):
    import atexit
    series, facts, _ = reader_data(root)
    worker = subprocess.Popen(["node", ROOT / "scripts/reader_detail_worker.cjs"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    atexit.register(worker.terminate)
    worker.stdin.write(json.dumps(dict(series=series, facts=facts)) + "\n")
    worker.stdin.flush()
    return worker


@lru_cache(maxsize=None)
def template():
    return json.loads((ROOT / 'charts/reader.yml').read_text())


@lru_cache(maxsize=None)
def floors(root):
    return json.loads((root / 'site/dist/data/floors.json').read_text())


@lru_cache(maxsize=None)
def stat_points(root):
    series, facts, audit = reader_data(root)
    return observations(facts, audit, series['books'])



def axis(books):
    value = '(isDate(datum.value) ? toNumber(datum.value)/86400000 : toNumber(datum.value))'
    step = 25 if books == 1 else 100
    expr = f"{value} >= {books*100} ? '' : {value}%100 === 0 ? 'B' + (1+{value}/100) : ({value}%100) + '%'"
    return {'scale': {'nice': False, 'values': list(range(0, books*100, step)),
                      'continuous': {'domain': [0, books*100]}},
            'labels': {'expr': expr}, 'grid': {'visible': False}}


SKILL_TEMPLATE = r"""{#---
description: Recorded skill levels with a named endpoint and a book and chapter on each observation.
options:
  books:
    type: integer
---#}
{% set left = 28 %}{% set rail = 107 if width < 600 else 180 %}{% set right = width - rail %}
{% set top = 16 %}{% set bottom = height - 34 %}
{% set x = d3.scale_linear([0, options.books * 100], [left, right]) %}
{% set y = d3.scale_linear([0, rows | map(attribute='level') | max], [bottom, top]).nice(5) %}
{% set ink = style.font.color %}
{% for t in y.ticks(5) %}
  <line x1="{{ left }}" x2="{{ right }}" y1="{{ y(t) }}" y2="{{ y(t) }}" stroke="{{ ink }}" stroke-opacity=".14"/>
  <text x="{{ left-5 }}" y="{{ y(t)+4 }}" text-anchor="end" font-size="11" fill="{{ ink }}">{{ t | format('~g') }}</text>
{% endfor %}
{% for i in range(options.books) %}
  <text x="{{ x(i*100) }}" y="{{ bottom+20 }}" font-size="11" fill="{{ ink }}">B{{ i+1 }}</text>
{% endfor %}
{% for skill, readings in rows | groupby('skill') %}
  {% set color = readings[0].ink %}
  {% for scope, series in readings | groupby('scope') %}
    {% set path = namespace(points=[]) %}
    {% for r in series %}{% set path.points = path.points + [[x(r.at), y(r.level)]] %}{% endfor %}
    {% if series|length > 1 %}
    <path d="{{ d3.line(path.points) }}" fill="none" stroke="{{ color }}" stroke-width="2" stroke-dasharray="{{ series[0].dash }}"/>
    {% endif %}
  {% endfor %}
{% endfor %}
{% set ends = rows | selectattr('endpoint') | sort(attribute='rank') | list %}
{% for r in ends %}
  {% set color = r.ink %}
  {% set ly = top + (loop.index0+0.5)*(bottom-top)/(ends|length) %}
  <path d="M {{ x(r.at) }} {{ y(r.level) }} L {{ right+6 }} {{ ly }}" fill="none" stroke="{{ color }}" stroke-width=".8" stroke-opacity=".45"/>
  <a href="{{ r.wiki_url }}" target="_blank" rel="noopener noreferrer"><text x="{{ right+9 }}" y="{{ ly+3 }}" fill="{{ color }}" font-size="{{ 9 if width < 600 else 11 }}"><title>{{ r.wiki_label }}: {{ r.skill }} (spoilers)</title>{{ r.short_label }}</text></a>
{% endfor %}
{% for r in rows %}
  <circle cx="{{ x(r.at) }}" cy="{{ y(r.level) }}" r="4" fill="{{ r.ink }}"><title>{{ r.detail }}</title></circle>
{% endfor %}
"""


def skill_history(rows, counts, books, width):
    palette = ('#89c4ff', '#f5af77', '#c9a4f0', '#78cfbb', '#ea9dc2', '#e5ca82', '#98b68b', '#aab6ed')
    observations = []
    endpoints = {}
    for row in sorted(rows, key=lambda r: r['progress']):
        skill, scope = row['metric'], row['scope']
        description = f"{skill} · Level {row['value']} ({scope}) · Book {row['book']}, Chapter {row['chapter']}"
        limit = 17 if width < 600 else 27
        observations.append({
            'skill': skill, 'scope': scope, 'level': row['value'],
            'wiki_url':wiki_link(skill), 'wiki_label':wiki_label(skill),
            'ink': palette[crc32(skill.encode()) % len(palette)],
            'at': (row['book']-1)*100 + 100*(row['chapter']-1+row['position'])/counts[row['book']],
            'detail': description, 'endpoint': False, 'rank': -1,
            'short_label': skill if len(skill) <= limit else skill[:limit-1]+'…',
            'dash': 'none' if scope == 'base' else '2 4' if scope in ('reported','unknown','unspecified') else '7 4',
        })
        endpoints[skill] = observations[-1]
    for rank, point in enumerate(sorted(endpoints.values(), key=lambda p: (-p['level'], p['skill']))):
        point.update(endpoint=True, rank=rank)
    height = max(270, 64 + len(endpoints)*17)
    return {'queries': {'skill_levels': {'type': 'values', 'rows': observations}},
            'charts': {'history': {'type': 'custom', 'query': 'skill_levels', 'title': 'Skill & spell progression',
                                  'svg': SKILL_TEMPLATE, 'options': {'books': books},
                                  'style': {'min_height': height, 'max_height': height}}},
            'rows': [{'text':'— Base · – – Modified · · · Reported'}, 'history']}


def nested(board):
    """Inherit the parent theme and emit only one board footer."""
    return {key: value for key, value in board.items() if key not in ('extends', 'width')}


def build(data_root, progress, character, tab, width):
    dist = data_root / 'site/dist/data'
    series, facts, audit = reader_data(data_root)
    visible = [row for row in facts if row['progress'] <= progress]
    books = max(b['number'] for b in series['books'] if (b['startChapter']-1)/series['series']['chapterCount'] <= progress)
    counts = {b['number']: b['chapterCount'] for b in series['books']}
    ordered_characters = character_order(series, facts, audit, progress)
    known = set(ordered_characters)
    main_cast = set(ordered_characters[:10]) | {character}
    if character not in known and progress > 0:
        raise ValueError(f'{character} has no revealed observations at this position')
    level = [{'at': (r['book']-1)*100+100*(r['chapter']-1+r['position'])/counts[r['book']],
              'level': r['value'], 'character': r['character']} for r in visible
             if r['kind']=='level' and r['character'] in main_cast and r['value'] is not None and r['scope'] not in ('estimate','lower-bound')]
    level = list({(r['at'],r['character']):r for r in level}.values())
    board = deepcopy(template())
    board['width'] = width
    swatches = {}
    roster = {c['name']: c for c in series['characters']}
    for name in sorted(set(roster) | {r['character'] for r in level}):
        c = roster.get(name, {})
        seed = crc32(name.encode())
        fallback = '#' + ''.join(f'{65 + ((seed >> shift) & 63):02x}' for shift in (0,8,16))
        color = c.get('color', fallback)
        if name not in ('Carl', 'Princess Donut'):
            color = dim_color(color)
        while color in swatches.values():
            seed = crc32(str(seed).encode())
            color = '#' + ''.join(f'{50 + ((seed >> shift) & 63):02x}' for shift in (0,8,16))
        swatches[name] = color
    board['style']['charts']['category_colors'] = {'character':{'values':{
        name:swatches.get(name, '#8e9c90') for name in {r['character'] for r in level}
    }}}
    board['queries'] = {}
    dossier = board['rows'][1]
    board['rows'] = []
    if level:
        board['queries']['levels']={'type':'values','rows':level}
        board['charts']['levels']['style']['axis_x'] = axis(books)
        columns = 2 if width < 800 else min(8, len({r['character'] for r in level}))
        board['charts']['levels']['style']['legend'] = {
            'position': {'edge': 'top'}, 'direction': 'horizontal', 'columns': columns,
            'compact_columns': columns, 'title': {'visible': False},
        }
        floor_path = dist/'floors.json'
        if floor_path.exists() and width>=800:
            floor_entries = [e for e in floors(data_root) if (series['books'][e['book']-1]['startChapter']+e['chapter']-2+e['position'])/series['series']['chapterCount'] <= progress]
            coord = lambda e: (e['book']-1)*100+100*(e['chapter']-1+e['position'])/counts[e['book']]
            end = max([r['at'] for r in level] + [coord(e) for e in floor_entries])
            bands = []
            for i, entry in enumerate(floor_entries):
                start = coord(entry)
                stop = coord(floor_entries[i+1]) if i+1 < len(floor_entries) else end
                if stop <= start:
                    continue
                odd = entry['floor'] % 2
                color = '#bed792' if odd else '#92bac6'
                bands.append({'type': 'band', 'x': {'from': start, 'to': stop},
                              'text': f"Floor {entry['floor']}",
                              'style': {'marks': {'rect': {'fill': color, 'opacity': .13 if odd else .08},
                                                  'text': {'font': {'color': color}}}}})
            board['charts']['levels']['annotations'] = bands
        # Trails are annotations, never observations or tooltip values.
        stops = {}
        deaths = {}
        for e in series['events']:
            if e['progress'] > progress or e.get('historyOnly') or not e.get('lifeStatus'):
                continue
            if e['lifeStatus'] in ('dead', 'presumed-dead'):
                if deaths.get(e['subject'], {}).get('lifeStatus') == e['lifeStatus']:
                    continue  # Reconfirmations do not move the first report.
                deaths[e['subject']] = e
                stops[e['subject']] = (e['book']-1)*100 + 100*(e['chapter']-1+e['position'])/counts[e['book']]
            elif e['lifeStatus']=='alive':
                stops.pop(e['subject'],None)
                deaths.pop(e['subject'],None)
        current = series['books'][books-1]
        boundary = (books-1)*100 + 100*(progress*series['series']['chapterCount']-current['startChapter']+1)/counts[books]
        chart = board['charts']['levels']
        colors = board['style']['charts']['category_colors']['character']['values']
        for who, r in {r['character']:r for r in level}.items():
            end = min(boundary, stops.get(who,boundary))
            if end-r['at'] > .0001:
                chart.setdefault('annotations',[]).append({'type':'rule','x':{'from':r['at'],'to':end},'y':r['level'],
                    'style':{'marks':{'rule':{'stroke':{'color':colors.get(who,'#8e9c90'),'width':1,'dasharray':'2 5'}}}}})
            if who in deaths and stops[who] >= r['at']:
                death = deaths[who]
                confirmed = death['lifeStatus'] == 'dead'
                chart.setdefault('annotations',[]).append({
                    'type':'note', 'x': stops[who], 'y':r['level'], 'connector':'line',
                    'text':'×' if confirmed else '?',
                    'style':{'marks':{'text':{'font':{'color':colors.get(who,'#8e9c90'), 'size':18}}}}})
        board['rows'].extend(['levels', {'text':'Most-recorded characters + selected dossier · Dotted: last recorded level · × Death reported · ? Presumed dead'}])
    else:
        board['charts'].pop('levels',None)
        board['rows'].append({'text':'No levels recorded at this reading position.'})
    points=[p for p in stat_points(data_root) if p['character']==character and p['progress']<=progress]
    skill_rows=qualifying_rows([r for r in visible if r['kind']=='skill' and r['character']==character],progress)
    overview=[]
    if points and tab == 'overview':
        stats=stats_board(points,books,width-40)
        for record in stats['queries']['observations']['rows']:
            if record.get('description'):
                record['description']=record['description'].split('. ')[0]+'.'
        overview.append(nested(stats))
        overview.append({'text':'— Base · – – With modifiers · ○ Estimate / minimum'})
    own = [r for r in visible if r['character']==character]
    other_skills = {r['metric']:r for r in own if r['kind']=='skill' and
                    r['metric'] not in {s['metric'] for s in skill_rows}}
    changes = list({(r['source'],r['summary']):r for r in own if r['kind']=='stat' and r['value'] is None and r['delta'] is not None}.values())
    notes = [e for e in series['events'] if e['progress'] <= progress and e['subject']==character and e.get('statContext')]
    if tab == 'overview':
        overview.extend({'text': f"B{e['book']} · Ch {e['chapter']} — {e['summary']}"} for e in notes)
    if tab == 'overview' and changes:
        for r in changes:
            overview.append({'text': f"B{r['book']} · Ch {r['chapter']} — {r['summary']}"})
    if skill_rows and tab == 'overview':
        overview.append(skill_history(skill_rows, counts, books, width-40))
    if other_skills and tab == 'overview':
        overview.append({'queries':{'other_abilities':{'type':'values','rows':[
            {'ability':name, 'reference':wiki_label(name), 'wiki_url':wiki_link(name)} for name in sorted(other_skills)]}},
            'charts':{'other_abilities':{'type':'table','query':'other_abilities','title':'Other recorded abilities',
                'style':{'pagination':{'page_rows':10},'columns':{'ability':{'link':{'url':'{{ wiki_url }}','open':'new_tab'}},'wiki_url':{'visible':False}}}}},
            'rows':['other_abilities']})
    tables=detail_rows(data_root,progress,character)
    if tables['effects'] and tab == 'overview':
        for row in tables['effects']: row['wiki_url']=wiki_link(row['from_item'])
        if width < 800:
            tables['effects'] = [{'effect': r['effect'], 'source': r['from_item']+' · '+r['observed']+((' · '+r['condition']) if r['condition']!='—' else ''),'wiki_url':r['wiki_url']} for r in tables['effects']]
        overview.append({'queries':{'equipment_effects':{'type':'values','rows':tables['effects']}},
                         'charts':{'equipment_effects':{'type':'table','query':'equipment_effects',
                                  'title':'Equipment effects','style':{'pagination':{'page_rows':8},'columns':{'source' if width<800 else 'from_item':{'link':{'url':'{{ wiki_url }}','open':'new_tab'}},'wiki_url':{'visible':False}}}}},
                         'rows':['equipment_effects']})
    if not overview:
        overview=[{'text':'No stat or skill measurements recorded at this position.'}]
    for key in ('inventory','equipped'):
        for row in tables[key]: row['wiki_url'] = wiki_link(row['item'])
    tabs = dossier['tabs']['items']
    tabs[0]['rows'] = overview
    gear_tabs = tabs[1]['rows'][0]['tabs']
    gear_tabs['items'][0]['rows'][0]['queries']['inventory_entries']['rows'] = tables['inventory']
    if tables['equipped']:
        gear_tabs['items'][1]['rows'][1]['queries']['equipped_entries']['rows'] = tables['equipped']
    else:
        gear_tabs['items'] = gear_tabs['items'][:1]
    for item in gear_tabs['items']:
        for row in item['rows']:
            for chart in row.get('charts',{}).values():
                chart.setdefault('style',{}).setdefault('columns',{}).update({
                    'item':{'link':{'url':'{{ wiki_url }}','open':'new_tab'}},'wiki_url':{'visible':False}})
    gear_tabs['default'] = 'Equipped' if tab == 'equipped' and tables['equipped'] else 'All items'
    for item, name in zip(tabs[2:], ('rewards', 'history')):
        if tables[name]:
            item['rows'][0]['queries'][name+'_entries']['rows'] = tables[name]
        else:
            item['rows'] = [{'text':'No entries recorded at this position.'}]
    available = [item for i, item in enumerate(tabs) if (bool(points or skill_rows or other_skills or changes or notes or tables['effects']) if i == 0 else bool(tables[TABS[i]]))]
    if available: dossier['tabs']['items'] = available
    dossier.setdefault('queries',{})['wiki_reference'] = {'type':'values','rows':[
        {'url':wiki_link(character),'label':wiki_label(character)}]}
    dossier.setdefault('charts',{})['wiki_reference'] = {'type':'custom','query':'wiki_reference',
        'svg':'<a href="{{ rows[0].url }}" target="_blank" rel="noopener noreferrer"><text x="0" y="16" font-size="12" fill="{{ style.font.color }}">{{ rows[0].label }} ↗</text></a><text x="100" y="16" font-size="12" fill="{{ style.font.color }}">External wiki contains spoilers.</text>',
        'style':{'min_height':24,'max_height':24}}
    dossier['title'] = character
    dossier['variables']['character'] = {'options':{'static':[character]},'default':character,'required':True}
    dossier['tabs']['default'] = {'overview':'Overview','inventory':'Inventory','rewards':'Boxes & rewards','history':'History','equipped':'Inventory'}[tab]
    if dossier['tabs']['default'] not in {item['title'] for item in dossier['tabs']['items']}:
        dossier['tabs']['default'] = dossier['tabs']['items'][0]['title']
    for item in dossier['tabs']['items']:
        if item['title'] == dossier['tabs']['default']:
            item['rows'].insert(0,'wiki_reference')
        if item['title'] != dossier['tabs']['default']:
            item['rows'] = [{'text': ' '}]
        elif item['title'] == 'Inventory':
            for gear in gear_tabs['items']:
                if gear['title'] != gear_tabs['default']:
                    gear['rows'] = [{'text': ' '}]
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
