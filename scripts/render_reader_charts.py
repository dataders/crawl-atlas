"""Build the static dbt Charts snapshots selected by the reader's spoiler boundary."""
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from check_reader_exports import record
from reader_book_axis import finish_book_axes

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
out = DIST / "charts"
out.mkdir(exist_ok=True)
compact = out / "compact"
compact.mkdir(exist_ok=True)
rows = json.loads((DIST / "data/progression.json").read_text())
series = json.loads((DIST / "data/series.json").read_text())
cast_colors = {c["name"]: c["color"] for c in series["characters"]}


def book_axis(n):
    # dct's static label pass can present numeric ticks as dates from the epoch.
    v = "(isDate(datum.value) ? toNumber(datum.value)/86400000 : toNumber(datum.value))"
    step = 25 if n == 1 else 50
    prefix = "Book " if n <= 3 else "B"
    minor = f"({v}%100) + '%'" if n <= 3 else "''"
    expr = (f"{v} === {100*n} ? " + ("'100%'" if n <= 3 else "''") +
            f" : {v}%100 === 0 ? '{prefix}' + (1+{v}/100) : {minor}")
    return {"scale": {"nice": False, "values": list(range(0, n*100+1, step)),
                      "continuous": {"domain": [0, n*100]}},
            "ticks": {"step": step}, "labels": {"expr": expr}}


OPEN_SCOPES = {"estimate": "Estimate", "lower-bound": "Lower bound"}
OPEN_POINT_STYLE = {"marks": {"point": {"filled": False, "stroke_width": 2, "size": 88}}}


def point_query(metric, predicate, cutoff):
    return f"""SELECT (book-1)*100 + 100.0*(chapter-1+position)/chapter_count AS book_position,
            value, character AS crawler
        FROM progression JOIN books ON books.number = progression.book
        WHERE metric = '{metric}' AND ({predicate}) AND value IS NOT NULL
            AND progress <= {cutoff}
        ORDER BY progress, character"""


boundaries = [{"book": b["number"], "event_id": f"book-start-{b['number']}",
               "kind": "level", "progress": (b["startChapter"]-1)/series["series"]["chapterCount"]}
              for b in series["books"][1:]]
with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
    boards = {}
    book_counts = {}
    metrics = {"Level": "Level", "STR": "Strength", "INT": "Intelligence",
               "DEX": "Dexterity", "CHA": "Charisma"}
    for row in [*rows, *boundaries]:
        if row["event_id"] in boards:
            continue
        visible = [r for r in rows if r["kind"] in ("level", "stat") and r["progress"] <= row["progress"]]
        spec = {"extends": "neon", "source": "crawl_atlas", "rows": [],
                "style": {"background": "#161c18", "charts": {
                    "category_colors": {"crawler": {"values": {
                        r["character"]: cast_colors[r["character"]] for r in visible if r["character"] in cast_colors}}},
                    "axis_x": {"grid": {"visible": False}},
                    "axis_y": {"grid": {"opacity": 0.2}}}},
                "queries": {}, "charts": {}}
        for metric, title in metrics.items():
            measured = [r for r in visible if r["metric"] == metric and r["value"] is not None]
            exact = [r for r in measured if r["scope"] not in OPEN_SCOPES and
                     (r["kind"] == "level" or r["scope"] == "base")]
            qualified = [r for r in measured if r["scope"] in OPEN_SCOPES]
            title = title if metric == "Level" else f"Base {title.lower()}"
            if not exact and not qualified:
                spec["rows"].append({"title": title, "text": "No value recorded yet."})
                continue
            chart = {"title": title, "color": "crawler", "x": "book_position", "y": "value",
                     "x_label": ("Progress within book" if row["book"] <= 3 else "Book start · minor ticks mark 50%"),
                     "y_label": title, "style": {"axis_x": book_axis(row["book"])}, "height": 240}
            if exact:
                spec["queries"][metric] = point_query(metric,
                    "(kind = 'level' AND scope NOT IN ('estimate','lower-bound')) OR scope = 'base'",
                    max(r["progress"] for r in exact))
                chart.update(type="line", query=metric, layers=[{"type": "scatter", "y": "value", "color": "crawler"}])

            # Separate native scatter queries keep bounds and estimates out of the line.
            for index, (scope, person) in enumerate(sorted({(r["scope"], r["character"]) for r in qualified})):
                query = f"{metric}_open_{index}"
                last = max(r["progress"] for r in qualified if r["scope"] == scope and r["character"] == person)
                sql_person = person.replace("'", "''")
                spec["queries"][query] = point_query(metric, f"scope = '{scope}' AND character = '{sql_person}'", last)
                label = f"{OPEN_SCOPES[scope]} · {person}"
                if "query" not in chart:
                    chart.update(type="scatter", query=query, y_label=label, layers=[])
                    chart["style"].update(OPEN_POINT_STYLE)
                else:
                    chart["layers"].append({"type": "scatter", "x": "book_position", "y": "value",
                        "color": "crawler", "query": query, "label": label, "style": OPEN_POINT_STYLE})
            if qualified:
                chart["subtitle"] = "Filled: recorded value. Open: estimate or lower bound."
            spec["charts"][metric] = chart
            spec["rows"].append(metric)
        boards[row["event_id"]] = spec
        book_counts[row["event_id"]] = row["book"]
    for columns, width, destination in [(1, 440, compact), (2, 1360, out)]:
        paths = []
        rendered_specs = {}
        aliases = {}
        for event_id, spec in boards.items():
            items = spec["rows"]
            if columns == 1:
                layout = items
            else:
                level, strength, intelligence, dexterity, charisma = items
                layout = [level, {"cols": [strength, intelligence]},
                          {"cols": [dexterity, charisma]}]
                if "Level" in spec["charts"]:
                    spec["charts"]["Level"]["height"] = 320
            board = Path(scratch) / f"{event_id}.yml"
            serialized = json.dumps({**spec, "width": width, "rows": layout,
                "style": {**spec["style"], "frame": {"margin": 16, "card_gap": 12}}})
            # History updates at every observation, even when the plots are identical.
            key = (book_counts[event_id], serialized)
            if key in rendered_specs:
                aliases[event_id] = rendered_specs[key]
                continue
            rendered_specs[key] = event_id
            board.write_text(serialized)
            paths.append(str(board))
        def render_batch(batch):
            subprocess.run(["dct", "render", *batch, "--no-cache", "--project-dir", str(ROOT),
                        "--format", "html", "--output", str(destination / "{stem}.html")], check=True)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(render_batch, [paths[i::4] for i in range(4)]))
        for board in paths:
            html = destination / (Path(board).stem + ".html")
            link = '<link rel="stylesheet" href="/chart-sizing.css">'
            html.write_text(finish_book_axes(html.read_text(), book_counts[Path(board).stem]).replace("</head>", link + "</head>", 1))
        for event_id, original in aliases.items():
            shutil.copyfile(destination / f"{original}.html", destination / f"{event_id}.html")
subprocess.run([sys.executable, str(ROOT / "scripts/render_detail_tables.py")], check=True)
record()
