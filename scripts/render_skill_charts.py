"""Render one spoiler-bounded native skill chart per character.

Qualification uses only revealed levels: two actual changes within a scope,
OR a latest scoped level above five. First observation is not acquisition.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import tempfile
try:
    from .render_dossier_charts import book_axis
    from .reader_book_axis import finish_book_axes
except ImportError:
    from render_dossier_charts import book_axis
    from reader_book_axis import finish_book_axes

ROOT = Path(__file__).resolve().parents[1]


def qualifying_rows(rows, cutoff):
    visible = sorted([r for r in rows if r['progress'] <= cutoff and r['value'] is not None], key=lambda r: r['progress'])
    qualified = set()
    for skill in {r['metric'] for r in visible}:
        own = [r for r in visible if r['metric'] == skill]
        last = {}
        changes = 0
        for row in own:
            scope = row['scope']
            if scope in last and last[scope] != row['value']:
                changes += 1
            last[scope] = row['value']
        if changes >= 2 or any(value > 5 for value in last.values()):
            qualified.add(skill)
    return [r for r in visible if r['metric'] in qualified]


def board_spec(rows, books, width, counts):
    skills = sorted({r['metric'] for r in rows})
    height = max(360, 170 + len(skills) * 16)
    scopes = sorted({r['scope'] for r in rows}, key=lambda scope: (scope != 'base', scope != 'reported', scope))
    queries, layers = {}, []
    latest = {}
    for row in rows:
        if row['metric'] not in latest or row['progress'] >= latest[row['metric']]['progress']:
            latest[row['metric']] = row
    for scope in scopes:
        # Keep separate queries for raw scopes: equipment, effective, class etc.
        # share a visual category but are never joined into one numeric series.
        category = 'Base' if scope == 'base' else 'Unspecified' if scope in ('reported', 'unknown', 'unspecified') else 'Modified'
        values = [{'at': (r['book'] - 1) * 100 + 100 * (r['chapter'] - 1 + r['position']) / counts[r['book']],
                   'level': r['value'], 'skill': r['metric'], 'scope': scope,
                   'location': f"Book {r['book']}, Chapter {r['chapter']}",
                   'end_label': r['metric'] if r is latest[r['metric']] else ''} for r in rows if r['scope'] == scope]
        queries[scope] = {'type': 'values', 'rows': values}
        mark_style = {} if category == 'Base' else {'marks': {'line': {'stroke': {'dasharray': '2 4' if category == 'Unspecified' else '7 4'}}}}
        layers.append({'type': 'line', 'query': scope, 'x': 'at', 'y': 'level', 'color': 'skill',
                       'label': scope.capitalize(), 'style': mark_style})
    primary = layers.pop(0)
    primary.pop('label')
    primary.update(title='Skill & spell progression', height=height, x_label='Reading position', y_label=f"Skill level · {scopes[0]}",
                   warnings_ignore=['WARN-TOO-MANY-COLOR-CATEGORIES', 'WARN-Y-ENCODING-MOSTLY-NULL',
                                    'WARN-LAYERED-CHART-SHARED-Y-AXIS-SCALE-MISMATCH', 'WARN-AXIS-TITLE-TRUNCATED'])
    if layers:
        primary['layers'] = layers
    # Native note layout avoids collisions and draws leaders back to the real
    # endpoint. This labels overlay series too (endpoint rails only cover base).
    primary['annotations'] = [
        {'type': 'note',
         'x': (r['book']-1)*100 + 100*(r['chapter']-1+r['position'])/counts[r['book']],
         'y': r['value'],
         'text': (skill[:21] + '…') if width < 600 and len(skill)>22 else skill,
         'connector': 'line',
         'style': {'marks': {'text': {'font': {'color': '#d3ddcf', 'size': 10}},
                             'line': {'opacity': .5}}}}
        for skill, r in latest.items()]

    primary['style'].update({'axis_x': {**book_axis(books), 'grid': {'visible': False}},
                            'endpoint_labels': {'visible': False},
                            'axis_y': {'title': {'visible': False}, 'grid': {'opacity': .2}, 'scale': {'continuous': {'zero': True}}},
                            'legend': {'visible': False}})
    return {'extends': 'neon', 'width': width,
            'style': {'background': '#161c18', 'footer': {'visible': False},
                      'timestamp': {'visible': False}, 'frame': {'margin': 8}},
            'queries': queries, 'charts': {'history': primary},
            'rows': [{'text': '— Base · – – Modified · · · Unspecified'}, 'history']}


def main():
    dist = ROOT / 'site/dist/data'
    series = json.loads((dist / 'series.json').read_text())
    rows = [r for r in json.loads((dist / 'progression.json').read_text()) if r['kind'] == 'skill']
    counts = {b['number']: b['chapterCount'] for b in series['books']}
    result = {'version': 2, 'characters': {}}
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        jobs = []
        for person in sorted({r['character'] for r in rows}):
            own = [r for r in rows if r['character'] == person]
            records = result['characters'][person] = []
            boundaries = {(r['progress'], r['book']) for r in own}
            boundaries.update(((b['startChapter'] - 1) / series['series']['chapterCount'], b['number']) for b in series['books'])
            for progress, book in sorted(boundaries):
                visible = qualifying_rows(own, progress)
                record = {'progress': progress, 'count': len({r['metric'] for r in visible})}
                records.append(record)
                if not visible:
                    continue
                for width, key in [(900, 'svg'), (440, 'compactSvg')]:
                    board = Path(tmp) / f'skill-{len(jobs)}.yml'
                    board.write_text(json.dumps(board_spec(visible, book, width, counts)))
                    jobs.append((board, record, key, book))
        def render(job):
            board, record, key, book = job
            target = board.with_suffix('.svg')
            subprocess.run(['dct', 'render', str(board), '--format', 'svg', '--no-cache',
                            '--project-dir', str(ROOT), '--output', str(target)], check=True, stdout=subprocess.DEVNULL)
            svg = re.sub(r'@font-face\s*\{[^}]*\}', '', target.read_text())
            record[key] = finish_book_axes(svg, book)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(render, jobs))
    target = dist / 'skill-charts.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(target)
    print(f'Rendered {len(jobs)} native skill history charts.')


if __name__ == '__main__':
    main()
