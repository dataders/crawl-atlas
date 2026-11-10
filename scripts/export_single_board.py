"""Export complete dbt Charts board states for the static reader.

Run with the pinned dct Python environment (dbt-charts==0.11.1).
Only the native renderer writes chart/table/layout markup. The browser selects
one complete compressed HTML artifact through dbt Charts' host message hook.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from level_locations import level_locations
from build_single_board import build, TABS, character_order, reader_data, detail_rows

ROOT = Path(__file__).resolve().parents[1]


def catalog(data_root):
    data, facts, audit = reader_data(data_root)
    events = sorted(data['events'], key=lambda e:e['progress'])
    first = {}
    names = {c['name'] for c in data['characters'] if c['name'] != 'Party'} & set(json.loads((data_root/'data/public/reader-characters.json').read_text()))
    for event in events:
        if event.get('subject') in names:
            first.setdefault(event['subject'], event['progress'])
    global_points = {0, 1, *first.values()}
    global_points.update(e['progress'] for e in events if e.get('subject') in names and e.get('lifeStatus') and not e.get('historyOnly'))
    global_points.update(r['progress'] for r in facts if r['kind']=='level' and r['character'] in names)
    global_points.update((b['startChapter']-1)/data['series']['chapterCount'] for b in data['books'])
    for floor in json.loads((data_root/'site/dist/data/floors.json').read_text()):
        book = data['books'][floor['book']-1]
        global_points.add((book['startChapter']+floor['chapter']-2+floor['position'])/data['series']['chapterCount'])
    order=[]
    for point in sorted({e['progress'] for e in events}|{r['progress'] for r in audit['observations']}):
        next_order=sorted(character_order(data,facts,audit,point)[:10])
        if next_order!=order:global_points.add(point);order=next_order
    result={}
    for person,start in sorted(first.items()):
        own=[e for e in events if e.get('subject')==person]
        base=set(global_points)
        # New native tab labels must appear at their own first reveal, but a
        # later history-only event need not regenerate unrelated inventory.
        first_ui={}
        for e in own:
            first_ui.setdefault(e['type'],e['progress'])
            if e.get('acquisition'):first_ui.setdefault('rewards',e['progress'])
            if e.get('action')=='equip' or e.get('state')=='equipped':first_ui.setdefault('equipped',e['progress'])
        base.update(first_ui.values())
        result[person]={}
        for tab in TABS:
            points=set(base)
            for e in own:
                if tab=='history' or (tab=='overview' and (e['type'] in ('stat','skill') or e.get('statContext') or e.get('effects') or e.get('statBoosts') or e.get('attachedTo') or (e['type']=='item' and (e.get('action') in ('equip','unequip','remove','consume','destroy','lose') or e.get('state')=='equipped')))) or (tab in ('inventory','equipped') and e['type']=='item') or (tab=='rewards' and e.get('acquisition')):
                    points.add(e['progress'])
            if tab=='overview':
                points.update(r['progress'] for r in audit['observations'] if r['character']==person)
            def available(p):
                revealed=[e for e in own if e['progress']<=p]
                if tab=='history':return bool(revealed)
                if tab in ('inventory','equipped'):return any(e['type']=='item' for e in revealed)
                if tab=='rewards':return any(e.get('acquisition') for e in revealed)
                if any(r['character']==person and r['progress']<=p for r in audit['observations']):return True
                return any(r['character']==person and r['kind'] in ('stat','skill') and r['progress']<=p for r in facts) or any(e.get('statContext') for e in revealed) or (any(e.get('effects') or e.get('statBoosts') for e in revealed) and bool(detail_rows(data_root,p,person)['effects']))
            result[person][tab]=sorted(p for p in points if p>=start and available(p))
    return data,result


def export(job):
    data_root, destination, person, tab, progress, width = job
    from dbt_charts.cli.filesystem_project import FilesystemProject
    from dbt_charts.core.project import InMemoryBoard
    from dbt_charts.core.board import render_dashboard
    from dbt_charts.agent_api.project_session import ProjectSession
    global SESSION
    if 'SESSION' not in globals(): SESSION=ProjectSession.open(ROOT)
    spec=build(Path(data_root),progress,person,tab,width)
    serialized=json.dumps(spec,ensure_ascii=False)
    key=hashlib.sha256(('native-host-v2'+serialized).encode()).hexdigest()[:24]
    destination=Path(destination)
    target=destination/'boards'/f'{key}.html.gz'
    if not target.exists():
        result=render_dashboard(board=InMemoryBoard(serialized,path=None),project=FilesystemProject(ROOT),
            adapter_registry=SESSION.adapter_registry,result_cache=None,format='html',use_cache=False,controls=True,standalone=True)
        if result.status not in ('success','ok') or result.chart_errors or result.board_error:
            raise RuntimeError(f'{person}/{tab}/{progress}: {result.model_dump_json(exclude={'data'},exclude_none=True)[:4000]}')
        html=result.data
        # Share the renderer's unmodified JS/CSS payloads. Never rewrite SVG,
        # marks, rows, axes, layout, or native controls after rendering.
        def external(match):
            kind, attrs, body=match.groups()
            if not body.strip(): return match.group(0)
            ext='js' if kind=='script' else 'css'
            asset=hashlib.sha256(body.encode()).hexdigest()[:24]+'.'+ext
            path=destination/'board-assets'/asset
            path.write_text(body)
            return (f'<script src="../board-assets/{asset}"{attrs}></script>' if kind=='script'
                    else f'<style{attrs}>@import url("../board-assets/{asset}");</style>')
        html=re.sub(r'<(script|style)([^>]*)>(.*?)</\1>',external,html,flags=re.S)
        target.write_bytes(gzip.compress(html.encode(),mtime=0))
    return person,tab,progress,str(width),key


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,default=ROOT)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--plan',action='store_true')
    p.add_argument('--sample',action='store_true',help='Only full-progress Carl and Donut; never publish this partial catalog')
    args=p.parse_args()
    data,states=catalog(args.data_root)
    jobs=[]
    for person,tabs in states.items():
        if args.sample and person not in ('Carl','Princess Donut'): continue
        for tab,points in tabs.items():
            for progress in ([1] if args.sample else points):
                for width in (440,1360):jobs.append((str(args.data_root),str(args.output),person,tab,progress,width))
    # Keep one character/checkpoint together to reuse its frozen detail rows.
    jobs.sort(key=lambda job: (job[2], job[4], job[5], job[3]))
    print(f'{len(jobs)} whole-board states for {len(states)} characters',flush=True)
    if args.plan:return
    for directory in ('boards','board-assets','data'):(args.output/directory).mkdir(parents=True,exist_ok=True)
    manifest={'version':1,'renderer':'dbt-charts 0.11.1','complete':not args.sample,'characters':{},'books':data['books'],'series':data['series']}
    pages_path = args.data_root / 'data/public/level-pages.json'
    manifest['levelLocations'] = level_locations(data, json.loads(pages_path.read_text()))
    updates={}
    seen=set()
    for event in sorted(data['events'],key=lambda e:e['progress']):
        who=event.get('subject')
        identity=(who,event.get('source',event['id']),event.get('type'),event.get('name'))
        if who in states and identity not in seen:
            seen.add(identity)
            updates.setdefault(who,[]).append(event['progress'])
    manifest['characterUpdates']=updates
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,(person,tab,progress,width,key) in enumerate(pool.map(export,jobs,chunksize=10),1):
            checkpoints = manifest['characters'].setdefault(person,{}).setdefault(tab,{}).setdefault(width,[])
            if not checkpoints or checkpoints[-1]['file'] != key:
                checkpoints.append({'progress':progress,'file':key})
            if i%50==0:print(f'{i}/{len(jobs)} states, {time.monotonic()-start:.0f}s',flush=True)
    source_inputs=['scripts/wiki_links.py','scripts/level_locations.py','charts/reader.yml','scripts/build_single_board.py','scripts/export_single_board.py',
        'scripts/render_dossier_charts.py','scripts/render_skill_charts.py','site/dist/detail-model.js','site/dist/equipment-effects.js',
        'scripts/reader_detail_worker.cjs','scripts/build_public_timeline.py','scripts/build_database.py','scripts/reward_provenance.py','site/dist/board-details.js','site/dist/rewards.js','site/dist/static-reader.js']
    data_inputs=['data/public/reader-characters.json','data/public/level-pages.json','site/dist/data/floors.json', *[str(path.relative_to(args.data_root)) for path in sorted((args.data_root/'data/public').glob('book-*.jsonl'))]]
    manifest['inputs']={path:hashlib.sha256(((ROOT if path in source_inputs else args.data_root)/path).read_bytes()).hexdigest() for path in source_inputs+data_inputs}
    manifest['exports']={str(path.relative_to(args.output)):hashlib.sha256(path.read_bytes()).hexdigest() for directory in ('boards','board-assets') for path in (args.output/directory).iterdir() if path.is_file()}
    (args.output/'data/reader-board.json').write_text(json.dumps(manifest,separators=(',',':'))+'\n')
    retained = sum(len(points) for tabs in manifest['characters'].values()
                   for widths in tabs.values() for points in widths.values())
    print(f'{retained:,} checkpoints retained from {len(jobs):,} candidates '
          f'in {time.monotonic() - start:.1f}s.', flush=True)
    print('Complete native board catalog written.',flush=True)

if __name__=='__main__':main()
