"""Finish the two-tier ruler on dct's static SVG; leave its scales and marks intact."""
import re
from html import escape, unescape
from xml.etree import ElementTree as ET

# Match only the exported x axis, including its title and the two translated groups.
AXIS = re.compile(r'<g\b[^>]* data-dct-role="x-axis"[^>]*>.*?data-authored-kind="x_label".*?</text></g></g></g></g>', re.S)


def finish_book_axes(html, books):
    def ruler(match):
        axis = ET.fromstring(match[0])
        plot = axis.find("./g/g")
        title = plot.find("./g/text")
        width = 2 * float(title.get("x"))  # centered by dct in the actual plot area
        y = float(plot.find("line").get("y1"))
        for node in list(plot):
            plot.remove(node)
        axis.set("aria-label", f"Reading position across books 1 to {books}; small ticks show progress within each book")
        axis.set("data-book-count", str(books))

        def tick(x, label, major=False, end=False):
            color = "#c5dc99" if major else "#a6b2a9"
            ET.SubElement(plot, "line", x1=str(x), x2=str(x), y1=str(y),
                          y2=str(y+(9 if major else 4)), stroke=color)
            if not label:
                return
            anchor = "start" if major else "end" if end else "middle"
            ET.SubElement(plot, "text", {"x": str(x), "y": str(y+(22 if major else 36)),
                "text-anchor": anchor, "font-family": "Inter Variable, system-ui, sans-serif",
                "font-size": "12" if major else "10", "font-weight": "600" if major else "400",
                "fill": color}).text = label

        for i in range(books):
            tick(width*i/books, f"{'Book ' if books <= 3 else 'B'}{i+1}", major=True)
            for pct in ((25, 50, 75) if books == 1 else (50,)):
                tick(width*(i+pct/100)/books, f"{pct}%" if books <= 3 else "")
        tick(width, "100%" if books <= 3 else "", end=True)
        return ET.tostring(axis, encoding="unicode")

    result, count = AXIS.subn(ruler, html)
    if not count or count != len(re.findall(r'<g\b[^>]* data-dct-role="x-axis"', html)):
        raise ValueError("Unexpected dct x-axis markup; review the static export before publishing.")
    return clean_chart_labels(result)


def clean_chart_labels(html):
    """Use one hover identity for the line and dot at the same chart position."""
    def clean_plot(match):
        labels = {}

        def clean_point(point):
            tag = point[0]
            label = re.search(r'aria-label="([^"]*)"', tag)
            if label is None:
                return tag
            open_label = re.search(r"(Estimate|Lower bound) · ([^;]+)", label[1])
            if open_label:
                scope, person = open_label.groups()
                # Retain the native numeric hover header so dbt groups matching marks.
                header, _, reading = label[1].split("; ", 2)
                value = reading.rsplit(": ", 1)[-1]
                person = unescape(person)
                description = ("approximately " if scope == "Estimate" else "greater than ") + value
                encoded = escape(f"{header}; ⁢{person} · {scope.lower()}; Value: {description}")
                tag = tag[:label.start(1)] + encoded + tag[label.end(1):]
                if "data-dbt-series=" not in tag:
                    tag = tag.replace("<circle ", f'<circle data-dbt-series="{escape(person)}" ', 1)
                position = float(header.removeprefix("⁡"))
                location = f"Book {int(position // 100) + 1}, {position % 100:.1f}% through"
                title = escape(f"{person}, {description}. {location}.")
                return tag[:-2] + f' tabindex="0"><title>{title}</title></circle>'
            key = (re.search(r'transform="([^"]+)"', tag)[1],
                   re.search(r'fill="([^"]+)"', tag)[1])
            if "; ⁢Value" not in label[1]:
                series = re.search(r'data-dbt-series="([^"]+)"', tag)
                labels[key] = (re.sub(r"; ⁢[^;]+", lambda _: "; ⁢" + series[1], label[1])
                               if series else label[1])
            if key in labels:
                tag = tag[:label.start(1)] + labels[key] + tag[label.end(1):]
            return tag

        return re.sub(r'<circle\b[^>]*data-dct-role="point"[^>]*/>', clean_point, match[0])

    # Each dct panel is a nested SVG. Scope lookups to that panel.
    html = re.sub(r'<svg\b(?:(?!<svg\b|</svg>).)*</svg>', clean_plot, html, flags=re.S)
    # Format the native hover header at display time; dct groups marks by the
    # original coordinate, so nearby observations still have separate tooltips.
    html = html.replace("function headerRow(entry, seriesColor, ts) {", """function headerRow(entry, seriesColor, ts) {
        const position = Number(entry.value);
        if (Number.isFinite(position)) {
            const book = Math.floor(position / 100) + 1;
            const percent = Math.floor(position % 100);
            entry = {...entry, value: 'Book ' + book + ' · ' + percent + '% through'};
        }""", 1)
    return re.sub(r'(data-authored-kind="y_label"><text[^>]*>)([^<]+), Value</text>',
                  r'\1\2</text>', html).replace(", Value&#x27; for a linear scale", "&#x27; for a linear scale")
