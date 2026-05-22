"""Incremental indexing logic.

For changed chapters:
  1. Delete existing chunks from ChromaDB + SQLite
  2. Re-chunk, embed, and insert fresh chunks

Unchanged chapters are skipped entirely.
"""

from __future__ import annotations

from src.processing.chunker import Chunk, chunk_chapter
from src.processing.metadata_extractor import enrich_chunks
from src.processing.entity_extractor import enrich_chunks_with_entities
from src.indexing.embedder import embed_chunks
from src.indexing.vector_store import upsert_chunks, delete_by_chapter
from src.indexing.sqlite_store import (
    upsert_chapter,
    upsert_entities_for_chunk,
    upsert_timeline_events,
    upsert_cooccurrences,
    delete_chapter,
    delete_entities_for_chapter,
    delete_timeline_for_chapter,
    delete_cooccurrences_for_chapter,
)
from src.processing.state_builder import build_narrative_states
from src.utils.logging import get_logger

log = get_logger(__name__)


def index_chapter(chapter, doc_id: str) -> int:
    """Index a single chapter. Returns number of chunks inserted."""
    slug = chapter.slug

    # 1. Remove stale data
    deleted = delete_by_chapter(slug)
    delete_entities_for_chapter(slug)
    delete_timeline_for_chapter(slug)
    delete_cooccurrences_for_chapter(slug)
    if deleted:
        log.info(f"Cleared {deleted} stale chunks for '{slug}'")

    # 2. Chunk
    chunks = chunk_chapter(chapter, doc_id)
    if not chunks:
        log.warning(f"No chunks produced for chapter '{slug}' — skipping")
        return 0

    # 3. Enrich with metadata (sets timeline_events, lore_tags, pov_character)
    enrich_chunks(chunks)
    # 4. Enrich with entities (sets entities, cooccurrences)
    enrich_chunks_with_entities(chunks)

    # 5. Embed
    chunks, vectors = embed_chunks(chunks)

    # 6. Store vectors
    upsert_chunks(chunks, vectors)

    # 7. Store structured metadata
    upsert_chapter(
        slug=slug,
        title=chapter.title,
        chapter_idx=chapter.index,
        content_hash=chapter.content_hash,
        chunk_count=len(chunks),
    )
    for chunk in chunks:
        upsert_entities_for_chunk(chunk)
        upsert_timeline_events(chunk, chunk.metadata.get("timeline_events", []))
        upsert_cooccurrences(chunk, chunk.metadata.get("cooccurrences", []))

    # 8. Rebuild narrative state snapshots from this chapter onwards
    build_narrative_states(chapter.index)

    log.info(f"Indexed chapter '{slug}' — {len(chunks)} chunks")
    return len(chunks)


def index_changed_chapters(
    all_chapters: list,
    changed_slugs: list[str],
    doc_id: str,
) -> tuple[int, int]:
    """
    Index only the chapters in changed_slugs.
    Returns (total_chunks_added, chapters_processed).
    """
    chapter_map = {ch.slug: ch for ch in all_chapters}
    total_added = 0
    processed = 0

    for slug in changed_slugs:
        if slug not in chapter_map:
            # Chapter was deleted from the doc
            delete_by_chapter(slug)
            delete_entities_for_chapter(slug)
            delete_timeline_for_chapter(slug)
            delete_cooccurrences_for_chapter(slug)
            delete_chapter(slug)
            log.info(f"Removed deleted chapter '{slug}'")
            continue

        added = index_chapter(chapter_map[slug], doc_id)
        total_added += added
        processed += 1

    return total_added, processed
