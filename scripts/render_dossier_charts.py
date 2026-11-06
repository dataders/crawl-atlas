"""Export native dbt Charts stat histories for each character and reveal boundary.

Only curated absolute totals enter the dashed series. Equipment bonuses and
unscoped reported values never become totals through arithmetic or carry-forward.
"""
from concurrent.futures import ThreadPoolExecutor
from html import escape, unescape
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
METRICS = {'STR': 'Strength', 'INT': 'Intelligence', 'CON': 'Constitution',
           'DEX': 'Dexterity', 'CHA': 'Charisma'}
COLORS = {'Strength': 'category.orange', 'Intelligence': 'category.blue',
          'Constitution': 'category.green', 'Dexterity': 'category.purple',
          'Charisma': 'category.cyan'}


def observations(progression, audit, books):
    """Normalize public observations, never treating a bonus as an absolute total."""
    counts = {b['number']: b['chapterCount'] for b in books}
    result = {}

    def add(row, value, kind):
        if value is None or row['metric'] not in METRICS:
            return
        point = {'character': row['character'], 'stat': METRICS[row['metric']],
                 'value': value, 'kind': kind, 'source': row['source'],
                 'summary': row.get('summary', ''), 'book': row['book'],
                 'chapter': row['chapter'], 'position': row['position'],
                 'progress': row['progress'],
                 'book_position': (row['book'] - 1) * 100 +
                    100 * (row['chapter'] - 1 + row['position']) / counts[row['book']]}
        key = (row['character'], row['metric'], row['source'], kind)
        if key in result and result[key]['value'] != value:
            raise ValueError(f'Conflicting stat observations: {key}')
        result[key] = point

    for row in progression:
        if row['kind'] == 'stat' and row['scope'] in ('base', 'estimate', 'lower-bound'):
            add(row, row['value'], row['scope'])
        elif row['kind'] == 'stat' and row['scope'] == 'reported' and row.get('confidence') == 'inferred':
            # Some ratios imply an approximate stat without establishing whether
            # modifiers are included. Preserve that uncertainty as an isolated dot.
            add(row, row['value'], 'reported-estimate')
    for row in audit.get('observations', []):
        approximate = row.get('confidence') == 'inferred'
        if 'base' in row:
            add(row, row['base'], 'estimate' if approximate else 'base')
        if 'total' in row:
            add(row, row['total'], 'total-estimate' if approximate else 'total')
    return sorted(result.values(), key=lambda p: (p['progress'], p['character'], p['stat'], p['kind']))


def book_axis(books):
    v = '(isDate(datum.value) ? toNumber(datum.value)/86400000 : toNumber(datum.value))'
    step = 25 if books == 1 else 50
    return {'scale': {'nice': False, 'values': list(range(0, books * 100 + 1, step)),
                      'continuous': {'domain': [0, books * 100]}},
            'ticks': {'step': step}, 'labels': {'expr': v}}


STAT_TEMPLATE = r'''{#---
description: Five stat histories with exact base and inclusive totals, and a translucent gap only within their shared observed range.
options:
  books:
    type: integer
---#}
{% set left = 38 %}{% set right = width - 12 %}
{% set top = 38 %}{% set bottom = height - 44 %}
{% set x = d3.scale_linear([0, options.books * 100], [left, right]) %}
{% set maximum = rows | map(attribute='value') | max %}
{% set y = d3.scale_linear([0, maximum if maximum > 0 else 1], [bottom, top]).nice(4) %}
{% set ink = style.fonts.secondary.color %}
{% set measured = rows | rejectattr('kind', 'equalto', 'ribbon') | list %}
{% set legend = measured | groupby('stat') %}
{% for stat, values in legend %}
  {% set lx = left + loop.index0 * (right - left) / (legend | length) %}
  <circle cx="{{ lx + 4 }}" cy="12" r="3.5" fill="{{ color_for(stat, 'stat') }}"/>
  <text x="{{ lx + 13 }}" y="16" font-family="{{ style.font.family }}" font-size="11" fill="{{ style.font.color }}">{{ values[0].abbreviation }}</text>
{% endfor %}
{% for tick in y.ticks(4) %}
  <line x1="{{ left }}" x2="{{ right }}" y1="{{ y(tick) }}" y2="{{ y(tick) }}" stroke="{{ ink }}" stroke-opacity="0.16"/>
  <text x="{{ left - 8 }}" y="{{ y(tick) + 4 }}" text-anchor="end" font-family="{{ style.font.family }}" font-size="11" fill="{{ ink }}">{{ tick | format('~g') }}</text>
{% endfor %}
{% for stat, values in rows | selectattr('kind', 'equalto', 'ribbon') | groupby('stat') %}
  {% set polygon = namespace(upper=[], lower=[]) %}
  {% for r in values %}
    {% set polygon.upper = polygon.upper + [(x(r.book_position) ~ ',' ~ y(r.value))] %}
    {% set polygon.lower = [(x(r.book_position) ~ ',' ~ y(r.lower))] + polygon.lower %}
  {% endfor %}
  <polygon points="{{ (polygon.upper + polygon.lower) | join(' ') }}" fill="{{ color_for(stat, 'stat') }}" fill-opacity="0.13">
    <title>{{ stat }}: gap between interpolated base and total observations, within their overlapping recorded range.</title>
  </polygon>
{% endfor %}
{% for stat, values in measured | groupby('stat') %}
  {% for kind in ['base', 'total'] %}
    {% set path = namespace(points=[]) %}
    {% for r in values | selectattr('kind', 'equalto', kind) %}
      {% set path.points = path.points + [[x(r.book_position), y(r.value)]] %}
    {% endfor %}
    {% if path.points | length > 1 %}
      <path d="{{ d3.line(path.points) }}" fill="none" stroke="{{ color_for(stat, 'stat') }}" stroke-width="2.5" stroke-linecap="round"{% if kind == 'total' %} stroke-dasharray="6 4"{% endif %}/>
    {% endif %}
  {% endfor %}
  {% for r in values %}
    <circle cx="{{ x(r.book_position) }}" cy="{{ y(r.value) }}" r="{{ 4 if r.kind in ['estimate', 'lower-bound', 'total-estimate', 'reported-estimate'] else 3 }}" fill="{{ style.background if r.kind in ['estimate', 'lower-bound', 'total-estimate', 'reported-estimate'] else color_for(stat, 'stat') }}" stroke="{{ color_for(stat, 'stat') }}" stroke-width="1.8"><title>{{ r.description }}</title></circle>
  {% endfor %}
{% endfor %}
<line x1="{{ left }}" x2="{{ right }}" y1="{{ bottom }}" y2="{{ bottom }}" stroke="{{ ink }}" stroke-opacity="0.5"/>
{% for i in range(options.books) %}
  <line x1="{{ x(i * 100) }}" x2="{{ x(i * 100) }}" y1="{{ bottom }}" y2="{{ bottom + 7 }}" stroke="{{ ink }}"/>
  <text x="{{ x(i * 100) }}" y="{{ bottom + 21 }}" font-family="{{ style.font.family }}" font-size="11" fill="{{ style.font.color }}">{{ 'Book ' if options.books <= 3 else 'B' }}{{ i + 1 }}</text>
  {% for percent in ([25,50,75] if options.books == 1 else [50]) %}
    <line x1="{{ x(i * 100 + percent) }}" x2="{{ x(i * 100 + percent) }}" y1="{{ bottom }}" y2="{{ bottom + 3 }}" stroke="{{ ink }}"/>
    {% if options.books <= 3 %}<text x="{{ x(i * 100 + percent) }}" y="{{ bottom + 36 }}" text-anchor="middle" font-family="{{ style.font.family }}" font-size="9" fill="{{ ink }}">{{ percent }}%</text>{% endif %}
  {% endfor %}
{% endfor %}
{% if options.books <= 3 %}<text x="{{ right }}" y="{{ bottom + 36 }}" text-anchor="end" font-family="{{ style.font.family }}" font-size="9" fill="{{ ink }}">100%</text>{% endif %}
'''


def ribbon_rows(points):
    """Interpolate only inside the shared domain of two exact observed series.

    These are drawing vertices, not new measurements. Every original knot is
    retained so shading follows the same straight segments as the visible lines.
    """
    ribbons = []
    for metric, stat in METRICS.items():
        series = {kind: sorted({p['book_position']: p['value'] for p in points
                                if p['stat'] == stat and p['kind'] == kind}.items())
                  for kind in ('base', 'total')}
        base, total = series['base'], series['total']
        if len(base) < 2 or len(total) < 2:
            continue
        lo = max(base[0][0], total[0][0])
        hi = min(base[-1][0], total[-1][0])
        if lo >= hi:
            continue
        knots = sorted({lo, hi, *(x for x, _ in base + total if lo < x < hi)})

        def interpolate(values, x):
            for (x0, y0), (x1, y1) in zip(values, values[1:]):
                if x0 <= x <= x1:
                    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            raise ValueError('Ribbon attempted to extrapolate outside observed values')

        ribbons.extend({'stat': stat, 'abbreviation': metric, 'kind': 'ribbon',
                        'book_position': x, 'lower': interpolate(base, x),
                        'value': interpolate(total, x), 'description': ''} for x in knots)
    return ribbons


def chart_rows(points):
    rows = []
    for p in points:
        kind = {'base': 'base', 'total': 'total including modifiers', 'estimate': 'estimated base',
                'lower-bound': 'base lower bound', 'total-estimate': 'estimated total',
                'reported-estimate': 'reported estimate; modifier scope unknown'}[p['kind']]
        rows.append({key: p[key] for key in ('stat', 'kind', 'book_position', 'value')} | {
            'abbreviation': next(m for m, stat in METRICS.items() if stat == p['stat']),
            # This column is only used by ribbon vertices. Keep its type numeric
            # even in early checkpoints that have no ribbon yet.
            'lower': p['value'],
            'description': f"{p['stat']} {p['value']} ({kind}), Book {p['book']}, Chapter {p['chapter']}. {p['summary']} Source: {p['source']}."})
    return rows + ribbon_rows(points)


def board_spec(points, books, width):
    if not points:
        raise ValueError('Cannot render a stat history without observations')
    return {'extends': 'neon', 'width': width,
            'queries': {'observations': {'type': 'values', 'rows': chart_rows(points)}},
            'style': {'background': '#161c18', 'frame': {'margin': 8},
                      'footer': {'visible': False}, 'timestamp': {'visible': False},
                      'charts': {'category_colors': {'stat': {'values': {
                          stat: COLORS[stat] for stat in METRICS.values() if any(p['stat'] == stat for p in points)}}}}},
            'charts': {'stats': {'type': 'custom', 'query': 'observations', 'title': 'Stat points',
                                  'svg': STAT_TEMPLATE, 'options': {'books': books},
                                  'style': {'min_height': 310 if width < 600 else 340,
                                            'max_height': 310 if width < 600 else 340}}},
            'rows': ['stats']}


def finish_svg(svg, points, books):
    # Parent reader supplies fonts. App accessibility is added after native
    # custom-template validation, without altering its generated chart geometry.
    svg = re.sub(r'@font-face\s*\{[^}]*\}', '', svg)
    def focusable(match):
        opening, title, ending = match.groups()
        label = re.sub(r'<[^>]+>', '', title)
        return opening + f' tabindex="0" role="img" aria-label="{escape(unescape(label))}">' + title + ending
    return re.sub(r'(<circle\b[^>]*?)>(<title>.*?</title>)(</circle>)', focusable, svg, flags=re.S)


def checkpoints(points, books, chapter_count):
    boundaries = [(p['progress'], p['book']) for p in points]
    boundaries.extend(((b['startChapter'] - 1) / chapter_count, b['number']) for b in books)
    return [(progress, book) for progress, book in sorted(set(boundaries))
            if any(p['progress'] <= progress for p in points)]


def main():
    dist = ROOT / 'site/dist'
    series = json.loads((dist / 'data/series.json').read_text())
    progression = json.loads((dist / 'data/progression.json').read_text())
    audit = json.loads((ROOT / 'data/public/stat-breakdown-audit.json').read_text())
    points = observations(progression, audit, series['books'])
    result = {'version': 1, 'key': 'Solid = base. Dashed = total including modifiers. Shading interpolates the gap between recorded series where both have observations; it is not an additional measurement. Open circles = estimates or lower bounds.',
              'characters': {c['name']: [] for c in series['characters']}}
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        jobs = []
        for person, records in result['characters'].items():
            own = [p for p in points if p['character'] == person]
            for progress, book in checkpoints(own, series['books'], series['series']['chapterCount']):
                visible = [p for p in own if p['progress'] <= progress]
                record = {'progress': progress, 'book': book}
                records.append(record)
                for width, key in [(900, 'svg'), (440, 'compactSvg')]:
                    board = Path(tmp) / f'chart-{len(jobs)}.yml'
                    board.write_text(json.dumps(board_spec(visible, book, width)))
                    jobs.append((board, record, key, visible, book))
        def render(job):
            board, record, key, visible, book = job
            target = board.with_suffix('.svg')
            subprocess.run(['dct', 'render', str(board), '--format', 'svg', '--no-cache',
                            '--project-dir', str(ROOT), '--output', str(target)], check=True,
                           stdout=subprocess.DEVNULL)
            record[key] = finish_svg(target.read_text(), visible, book)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(render, jobs))
    target = dist / 'data/dossier-charts.json'
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Rendered {len(jobs)} native dossier charts for {sum(bool(v) for v in result["characters"].values())} characters.')


if __name__ == '__main__':
    main()
