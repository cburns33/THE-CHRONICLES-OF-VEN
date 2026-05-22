"""Smart scene-aware chunker.

Splits a chapter's Markdown into overlapping token-bounded chunks,
respecting scene/section heading boundaries where possible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.utils.config import load_config
from src.utils.hashing import chunk_id
from src.processing.converter import Chapter


_ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_ENCODING.encode(text))


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    chapter_index: int
    chapter_title: str
    chapter_slug: str
    scene_heading: str
    text: str
    token_count: int
    chunk_index: int
    metadata: dict = field(default_factory=dict)


def _extract_frontmatter(md: str) -> tuple[dict, str]:
    """Strip YAML frontmatter block and return (meta dict, body)."""
    if not md.startswith("---"):
        return {}, md
    end = md.find("\n---", 3)
    if end == -1:
        return {}, md
    front = md[3:end].strip()
    body = md[end + 4:].strip()
    meta = {}
    for line in front.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def chunk_chapter(chapter: Chapter, doc_id: str) -> list[Chunk]:
    cfg = load_config()
    chunk_size = cfg["chunking"]["chunk_size"]
    chunk_overlap = cfg["chunking"]["chunk_overlap"]
    separators = cfg["chunking"]["scene_separators"]

    _, body = _extract_frontmatter(chapter.markdown)

    splitter = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_token_len,
        is_separator_regex=False,
    )

    raw_chunks = splitter.split_text(body)
    chunks: list[Chunk] = []

    current_scene = chapter.title
    for i, text in enumerate(raw_chunks):
        # Try to detect the scene heading from the first heading in the chunk
        scene = _detect_scene_heading(text) or current_scene
        current_scene = scene

        cid = chunk_id(doc_id, chapter.slug, i)
        chunks.append(
            Chunk(
                chunk_id=cid,
                doc_id=doc_id,
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                chapter_slug=chapter.slug,
                scene_heading=scene,
                text=text,
                token_count=_token_len(text),
                chunk_index=i,
            )
        )

    return chunks


def _detect_scene_heading(text: str) -> str | None:
    """Return the first Markdown heading found in the text, if any."""
    match = re.search(r"^#{2,4}\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def chunk_all_chapters(chapters: list[Chapter], doc_id: str) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for ch in chapters:
        all_chunks.extend(chunk_chapter(ch, doc_id))
    return all_chunks
