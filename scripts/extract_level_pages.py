"""Refresh the public anchor-to-page index using locally owned EPUB editions."""
import argparse
import json
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree
from zipfile import ZipFile

from extract_epub import BlockParser, find_package_path, ordered_documents


class PageParser(BlockParser):
    def __init__(self, targets, page):
        super().__init__()
        self.targets = targets
        self.page = targets.get('', page)
        self.pages = []

    def handle_starttag(self, tag, attrs):
        marker = dict(attrs).get('id')
        if marker in self.targets:
            self.page = self.targets[marker]
        if tag in self.BLOCK_TAGS and not self._depth:
            self.start_page = None
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._depth and data.strip():
            if self.start_page is None:
                self.start_page = self.page
            self.end_page = self.page
        super().handle_data(data)

    def handle_endtag(self, tag):
        before = len(self.blocks)
        super().handle_endtag(tag)
        if len(self.blocks) > before:
            self.pages.append((self.start_page, self.end_page))


def extract(corpus, series, epub_dir):
    wanted = {e['source'] for e in series['events'] if e['type'] == 'level'}
    result = {}
    for book in corpus['books']:
        with ZipFile(epub_dir / book['source']) as archive:
            targets = {}
            for filename in archive.namelist():
                if not filename.endswith('.ncx'):
                    continue
                for t in ElementTree.fromstring(archive.read(filename)).findall('.//{*}pageTarget'):
                    if t.get('type') != 'normal':
                        continue
                    src = t.find('{*}content').attrib['src']
                    doc, _, fragment = src.partition('#')
                    targets.setdefault(str(PurePosixPath(filename).parent / doc), {})[fragment] = t.attrib['value']
            if not targets:
                continue
            paragraphs = {}
            page = None
            for doc in ordered_documents(archive, find_package_path(archive)):
                parser = PageParser(targets.get(doc, {}), page)
                parser.feed(archive.read(doc).decode())
                paragraphs[doc] = list(zip(parser.blocks, parser.pages, strict=True))
                page = parser.page
            for chapter in book['chapters']:
                blocks = [row for doc in chapter['source_documents'] for row in paragraphs[doc]]
                for para, (block, (start, end)) in zip(chapter['paragraphs'], blocks, strict=True):
                    assert para['text'] == block.text
                    if para['anchor'] in wanted and start and end:
                        result[para['anchor']] = f'p. {start}' if start == end else f'pp. {start}–{end}'
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('corpus', type=Path)
    p.add_argument('epub_dir', type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    series = json.loads((root/'site/dist/data/series.json').read_text())
    pages = extract(json.loads(args.corpus.read_text()), series, args.epub_dir)
    (root/'data/public/level-pages.json').write_text(json.dumps(pages, indent=2, sort_keys=True)+'\n')
