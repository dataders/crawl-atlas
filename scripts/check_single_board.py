"""Reject incomplete or stale native board catalogs before publication."""
import argparse
import hashlib
import json
from pathlib import Path


def validate(root):
    dist = root / 'site/dist'
    manifest = json.loads((dist / 'data/reader-board.json').read_text())
    assert manifest.get('complete') is True, 'Sample board catalogs must not be published'
    assert manifest.get('renderer') == 'dbt-charts 0.11.1'
    assert 'Party' not in manifest['characters']
    for name, expected in manifest['inputs'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, f'Stale board input: {name}'
    referenced = set()
    for person, tabs in manifest['characters'].items():
        for tab, widths in tabs.items():
            for width, states in widths.items():
                assert width in ('440', '1360')
                positions = [state['progress'] for state in states]
                assert positions == sorted(set(positions)), f'Unordered states: {person}/{tab}'
                assert all(0 <= p <= 1 for p in positions)
                referenced.update('boards/'+state['file']+'.html.gz' for state in states)
    assert referenced, 'Empty board catalog'
    assert referenced <= manifest['exports'].keys(), 'Missing board hashes'
    for name, expected in manifest['exports'].items():
        assert hashlib.sha256((dist/name).read_bytes()).hexdigest() == expected, f'Stale or missing board asset: {name}'
    html = (dist/'index.html').read_text()
    assert 'static-reader.js' in html and 'src="app.js' not in html
    assert 'src="board-details.js' not in html
    print(f'Verified {len(referenced)} complete native boards and {len(manifest["characters"])} characters.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    validate(parser.parse_args().root)
