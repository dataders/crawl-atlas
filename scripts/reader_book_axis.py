"""Finish the two-tier ruler on dct's static SVG; leave its scales and marks intact."""
import re
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
            anchor = "start" if major else "end" if end else "middle"
            ET.SubElement(plot, "text", {"x": str(x), "y": str(y+(22 if major else 36)),
                "text-anchor": anchor, "font-family": "Inter Variable, system-ui, sans-serif",
                "font-size": "12" if major else "10", "font-weight": "600" if major else "400",
                "fill": color}).text = label

        for i in range(books):
            tick(width*i/books, f"{'Book ' if books <= 3 else 'B'}{i+1}", major=True)
            for pct in ((25, 50, 75) if books == 1 else (50,)):
                tick(width*(i+pct/100)/books, f"{pct}%" if books <= 3 else "½")
        tick(width, "100%" if books <= 3 else "", end=True)
        return ET.tostring(axis, encoding="unicode")

    result, count = AXIS.subn(ruler, html)
    if not count or count != len(re.findall(r'<g\b[^>]* data-dct-role="x-axis"', html)):
        raise ValueError("Unexpected dct x-axis markup; review the static export before publishing.")
    return result
