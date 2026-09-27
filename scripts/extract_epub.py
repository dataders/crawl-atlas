#!/usr/bin/env python3
"""Extract an EPUB into a private, review-oriented corpus.

No third-party packages are required. Output includes the full text and must
remain local; the repository's .gitignore excludes data/private/.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


SYSTEM_PATTERNS = {
    "level": re.compile(r"\blevel\s+\d+\b|\bnow level\s+\d+\b", re.I),
    "stat": re.compile(r"\b(strength|intelligence|constitution|dexterity|charisma)\s*:\s*\d+", re.I),
    "skill": re.compile(r"\b(skill|spell)\b|\bpugilism\b|\bmagic missile\b", re.I),
    "item": re.compile(r"\b(inventory|equipped|wearer|potion|scroll|box|biscuit|boots|gloves|jacket)\b", re.I),
    "party": re.compile(r"\bparty\b|\bjoined the party\b", re.I),
    "reward": re.compile(r"\b(reward|achievement|received)\b", re.I),
}


@dataclass
class Block:
    text: str
    bold: bool


class BlockParser(HTMLParser):
    BLOCK_TAGS = {"p", "h1", "h2", "h3", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._depth = 0
        self._bold_depth = 0
        self._parts: list[str] = []
        self._saw_bold = False
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.BLOCK_TAGS:
            if self._depth == 0:
                self._parts = []
                self._saw_bold = False
            self._depth += 1
        if tag in {"b", "strong"} and self._depth:
            self._bold_depth += 1
            self._saw_bold = True
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"b", "strong"} and self._bold_depth:
            self._bold_depth -= 1
        if tag in self.BLOCK_TAGS and self._depth:
            self._depth -= 1
            if self._depth == 0:
                text = re.sub(r"\s+", " ", "".join(self._parts)).strip()
                if text:
                    self.blocks.append(Block(text=text, bold=self._saw_bold))
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._depth:
            self._parts.append(data)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_package_path(archive: zipfile.ZipFile) -> str:
    root = ET.fromstring(archive.read("META-INF/container.xml"))
    for node in root.iter():
        if local_name(node.tag) == "rootfile" and node.get("full-path"):
            return node.get("full-path", "")
    raise ValueError("EPUB container does not identify a package document")


def ordered_documents(archive: zipfile.ZipFile, package_path: str) -> list[str]:
    root = ET.fromstring(archive.read(package_path))
    manifest: dict[str, str] = {}
    spine: list[str] = []
    for node in root.iter():
        name = local_name(node.tag)
        if name == "item" and node.get("id") and node.get("href"):
            manifest[node.get("id", "")] = node.get("href", "")
        elif name == "itemref" and node.get("idref"):
            spine.append(node.get("idref", ""))
    base = PurePosixPath(package_path).parent
    return [str(base / manifest[item_id]) for item_id in spine if item_id in manifest]


def classify(text: str, *, bold: bool = False) -> list[str]:
    """Return review categories for a block.

    Bold blocks in this edition carry most game-interface output. Retaining a
    generic category prevents uncommon item and ability names from silently
    falling out of the review queue just because they are absent from the
    small keyword list.
    """
    kinds = [name for name, pattern in SYSTEM_PATTERNS.items() if pattern.search(text)]
    if bold and not kinds:
        kinds.append("system")
    return kinds


def extract(epub: Path, output_dir: Path) -> tuple[Path, Path]:
    chapters: list[dict] = []
    candidates: list[dict] = []
    with zipfile.ZipFile(epub) as archive:
        package_path = find_package_path(archive)
        for document in ordered_documents(archive, package_path):
            parser = BlockParser()
            parser.feed(archive.read(document).decode("utf-8", errors="replace"))
            match = re.fullmatch(r"Chapter\s+(\d+)", parser.title.strip(), re.I)
            if not match:
                continue
            chapter_number = int(match.group(1))
            count = max(len(parser.blocks), 1)
            paragraphs = []
            for index, block in enumerate(parser.blocks, start=1):
                entry = {
                    "anchor": f"b1-c{chapter_number}-p{index}",
                    "position": round(index / count, 6),
                    "text": block.text,
                    "bold": block.bold,
                }
                paragraphs.append(entry)
                kinds = classify(block.text, bold=block.bold)
                if kinds:
                    candidates.append(
                        {
                            "chapter": chapter_number,
                            "anchor": entry["anchor"],
                            "position": entry["position"],
                            "kinds": kinds,
                            "text": block.text,
                            "bold": block.bold,
                            "status": "unreviewed",
                        }
                    )
            chapters.append(
                {
                    "number": chapter_number,
                    "title": parser.title.strip(),
                    "source_document": document,
                    "paragraphs": paragraphs,
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / "corpus.json"
    candidates_path = output_dir / "review-candidates.json"
    corpus_path.write_text(
        json.dumps({"source": epub.name, "chapters": chapters}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return corpus_path, candidates_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/private"))
    args = parser.parse_args()
    corpus, candidates = extract(args.epub, args.output)
    print(f"Wrote private corpus: {corpus}")
    print(f"Wrote review queue: {candidates}")


if __name__ == "__main__":
    main()
