"""Resolve level-chart positions to curated passage anchors and edition pages."""
import json
import re
from pathlib import Path


def level_locations(series, pages):
    counts = {book['number']: book['chapterCount'] for book in series['books']}
    locations = {}
    for event in series['events']:
        if event['type'] != 'level' or event.get('level') is None:
            continue
        book, chapter = event['book'], event['chapter']
        coordinate = (book - 1) * 100 + 100 * (chapter - 1 + event['position']) / counts[book]
        label = f'Book {book} · Chapter {chapter}'
        source = event['source']
        paragraph = re.fullmatch(fr'b{book}-c{chapter}-p(\d+)', source)
        if source in pages:
            label += ' · ' + pages[source]
        elif paragraph:
            label += f' · ¶ {paragraph[1]}'
        locations[f'{coordinate:.8f}'] = label
    return locations
