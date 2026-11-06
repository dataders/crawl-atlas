#!/usr/bin/env python3
"""Extract an EPUB into a private, review-oriented corpus.

No third-party packages are required. Output includes the full text and must
remain local; the repository's .gitignore excludes data/private/.
"""

from __future__ import annotations

import argparse
import hashlib
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


class SpineTextParser(HTMLParser):
    """Keep searchable body text even outside the legacy paragraph tag list.

    This is supplemental evidence only. Never rebuild numbered paragraphs from
    it: changing paragraph segmentation would invalidate existing source anchors.
    """
    BREAKS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_body = False
        self._skip = 0
        self._parts: list[str] = []
        self.images: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "body":
            self._in_body = True
        if not self._in_body:
            return
        if tag in {"script", "style"}:
            self._skip += 1
        if tag in self.BREAKS:
            self._parts.append("\n")
        if tag == "img":
            attributes = dict(attrs)
            self.images.append({"source": attributes.get("src"), "alt": attributes.get("alt", "")})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        if tag in self.BREAKS and self._in_body:
            self._parts.append("\n")
        if tag == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._in_body and not self._skip:
            self._parts.append(data)

    @property
    def text(self) -> str:
        lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


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


def chapter_number(title: str, blocks: list[Block]) -> int | None:
    """Read chapter numbers from both legacy and recent DCC EPUB layouts."""
    match = re.fullmatch(r"Chapter\s+(\d+)", title.strip(), re.I)
    if match:
        return int(match.group(1))
    if blocks:
        match = re.fullmatch(r"\[\s*(\d+)\s*\]", blocks[0].text.strip())
        if match:
            return int(match.group(1))
    return None


def extract_book(epub: Path, *, book_number: int = 1) -> tuple[list[dict], list[dict]]:
    chapters: list[dict] = []
    candidates: list[dict] = []
    chapter_by_number: dict[int, dict] = {}
    with zipfile.ZipFile(epub) as archive:
        package_path = find_package_path(archive)
        for document in ordered_documents(archive, package_path):
            parser = BlockParser()
            parser.feed(archive.read(document).decode("utf-8", errors="replace"))
            number = chapter_number(parser.title, parser.blocks)
            if number is None:
                continue
            chapter = chapter_by_number.get(number)
            if chapter is None:
                chapter = {
                    "number": number,
                    "title": f"Chapter {number}",
                    "source_documents": [],
                    "paragraphs": [],
                }
                chapter_by_number[number] = chapter
                chapters.append(chapter)
            chapter["source_documents"].append(document)
            # Some editions split one chapter across multiple spine documents.
            # Anchors remain continuous after the parts are merged.
            start = len(chapter["paragraphs"])
            for index, block in enumerate(parser.blocks, start=start + 1):
                entry = {
                    "anchor": f"b{book_number}-c{number}-p{index}",
                    "position": 0,
                    "text": block.text,
                    "bold": block.bold,
                }
                chapter["paragraphs"].append(entry)
                kinds = classify(block.text, bold=block.bold)
                if kinds:
                    candidates.append(
                        {
                            "book": book_number,
                            "chapter": number,
                            "anchor": entry["anchor"],
                            "position": 0,
                            "kinds": kinds,
                            "text": block.text,
                            "bold": block.bold,
                            "status": "unreviewed",
                        }
                    )
    chapters.sort(key=lambda chapter: chapter["number"])
    positions = {}
    for chapter in chapters:
        count = max(len(chapter["paragraphs"]), 1)
        for index, paragraph in enumerate(chapter["paragraphs"], start=1):
            paragraph["position"] = round(index / count, 6)
            positions[paragraph["anchor"]] = paragraph["position"]
        chapter["source_document"] = chapter["source_documents"][0]
    for candidate in candidates:
        candidate["position"] = positions[candidate["anchor"]]
    return chapters, candidates


def extract_book_complete(epub: Path, *, book_number: int = 1) -> tuple[dict, list[dict], list[dict]]:
    """Add every unnumbered spine section without changing numbered anchors.

    Supplemental anchors are document-derived, not chapter numbers or ordinal
    positions. Their position is local to that section, NOT the reading slider.
    No public event may use them until its reveal location is reviewed. The next
    numbered chapter is a conservative boundary after an interlude; trailing
    epilogues need a dedicated end-of-book position or the next book's start.
    """
    chapters, candidates = extract_book(epub, book_number=book_number)
    included = {document: chapter["number"] for chapter in chapters for document in chapter["source_documents"]}
    documents = []
    supplemental = []
    supplemental_candidates = []
    with zipfile.ZipFile(epub) as archive:
        for spine_index, document in enumerate(ordered_documents(archive, find_package_path(archive))):
            html = archive.read(document).decode("utf-8", errors="replace")
            parser = BlockParser()
            parser.feed(html)
            body = SpineTextParser()
            body.feed(html)
            documents.append({
                "spine_index": spine_index,
                "source_document": document,
                "title": parser.title.strip(),
                "numbered_chapter": included.get(document),
                "paragraph_count": len(parser.blocks),
                "body_text": body.text,
                "images": body.images,
            })
            if document in included:
                continue
            section_id = f"b{book_number}-s{hashlib.sha256(document.encode('utf-8')).hexdigest()[:12]}"
            title = parser.blocks[0].text if parser.blocks else parser.title.strip()
            label = f"{parser.title} {title}".lower()
            kind = next((name for name in ("prologue", "epilogue", "interlude", "recap") if name in label), "unclassified")
            # Preserve even front/back matter and empty/image-only spine files.
            # Selection for narrative analysis is a review decision, never a
            # heading heuristic that silently drops an unnamed POV section.
            section = {"id": section_id, "title": title, "document_title": parser.title.strip(),
                       "kind": kind, "source_documents": [document], "spine_index": spine_index,
                       "reveal": {"policy": "manual-review", "position_unit": "within-section",
                                  "after_chapter": None, "before_chapter": None},
                       "paragraphs": []}
            count = max(len(parser.blocks), 1)
            for index, block in enumerate(parser.blocks, 1):
                entry = {"anchor": f"{section_id}-p{index}", "position": round(index/count, 6),
                         "text": block.text, "bold": block.bold}
                section["paragraphs"].append(entry)
                kinds = classify(block.text, bold=block.bold)
                if kinds:
                    supplemental_candidates.append({"book": book_number, "section": section_id,
                        "source_document": document, **entry, "kinds": kinds,
                        "status": "unreviewed", "reveal_policy": "manual-review"})
            supplemental.append(section)
    for section in supplemental:
        before = [d["numbered_chapter"] for d in documents
                  if d["spine_index"] < section["spine_index"] and d["numbered_chapter"] is not None]
        after = [d["numbered_chapter"] for d in documents
                 if d["spine_index"] > section["spine_index"] and d["numbered_chapter"] is not None]
        section["reveal"].update(after_chapter=before[-1] if before else None,
                                 before_chapter=after[0] if after else None)
    corpus = {"source": epub.name, "book": book_number, "chapters": chapters,
              "supplemental_sections": supplemental, "spine_documents": documents,
              "coverage": {"spine_documents": len(documents),
                           "numbered_documents": len(included),
                           "supplemental_documents": len(supplemental),
                           "supplemental_paragraphs": sum(len(s["paragraphs"]) for s in supplemental)}}
    return corpus, candidates, supplemental_candidates


def extract(epub: Path, output_dir: Path, *, book_number: int = 1) -> tuple[Path, Path]:
    corpus, candidates, supplemental_candidates = extract_book_complete(epub, book_number=book_number)

    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / "corpus.json"
    candidates_path = output_dir / "review-candidates.json"
    corpus_path.write_text(
        json.dumps(corpus, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "supplemental-review-candidates.json").write_text(json.dumps(supplemental_candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return corpus_path, candidates_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/private"))
    parser.add_argument("--book-number", type=int, default=1)
    args = parser.parse_args()
    corpus, candidates = extract(args.epub, args.output, book_number=args.book_number)
    print(f"Wrote private corpus: {corpus}")
    print(f"Wrote review queue: {candidates}")


if __name__ == "__main__":
    main()
