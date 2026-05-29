#!/usr/bin/env python3
"""
Wipe and rebuild the manuscript portion of the index.

Continuity doc chunks (source_type != "manuscript") are preserved, so
running ingest_documents.py afterward is no longer needed after a
routine manuscript reindex.

Use this when:
  - You change embedding models (follow with ingest_documents.py --reindex-all)
  - The index gets corrupted
  - You want a clean slate after major manuscript restructuring

Usage:
  python scripts/full_reindex.py
  python scripts/full_reindex.py --yes   # skip confirmation prompt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

from src.utils.config import load_config
from src.utils.logging import get_logger
from src.sync.google_docs import get_doc_modified_time, fetch_doc_as_json
from src.sync.change_detector import load_state, save_state
from src.processing.converter import docs_json_to_chapters, save_chapters
from src.processing.chunker import chunk_all_chapters
from src.processing.metadata_extractor import enrich_chunks
from src.processing.entity_extractor import enrich_chunks_with_entities
from src.indexing.embedder import embed_chunks
from src.indexing.vector_store import upsert_chunks, collection_stats, delete_by_source_type
from src.indexing.sqlite_store import (
    init_db,
    upsert_chapter,
    upsert_entities_for_chunk,
    upsert_timeline_events,
    upsert_cooccurrences,
)
from datetime import datetime, timezone

log = get_logger("reindex")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    cfg = load_config()

    if not args.yes:
        confirm = input(
            "This will wipe and rebuild the entire index. Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            return

    doc_id = cfg["google_docs"]["document_id"]

    # Remove only manuscript chunks — continuity docs stay intact
    try:
        deleted = delete_by_source_type("manuscript")
        log.info(f"Cleared {deleted} manuscript chunks from ChromaDB")
    except Exception as e:
        log.warning(f"Could not clear manuscript chunks: {e}")

    # Wipe SQLite
    db_path = Path(cfg["paths"]["db_path"])
    if db_path.exists():
        db_path.unlink()
        log.info(f"Wiped SQLite at {db_path}")

    # Reinitialise
    init_db()

    # Export
    raw_path = Path(cfg["paths"]["raw_dir"]) / "manuscript.json"
    log.info("Fetching manuscript…")
    modified = get_doc_modified_time(doc_id)
    document = fetch_doc_as_json(doc_id, raw_path)

    # Parse
    chapters = docs_json_to_chapters(document)
    save_chapters(chapters, Path(cfg["paths"]["markdown_dir"]))
    log.info(f"Parsed {len(chapters)} chapters")

    # Chunk + enrich
    chunks = chunk_all_chapters(chapters, doc_id)
    enrich_chunks(chunks)
    enrich_chunks_with_entities(chunks)
    log.info(f"Produced {len(chunks)} chunks")

    # Embed + store
    log.info("Generating embeddings…")
    chunks, vectors = embed_chunks(chunks)
    upsert_chunks(chunks, vectors)

    for ch in chapters:
        ch_chunks = [c for c in chunks if c.chapter_slug == ch.slug]
        upsert_chapter(
            slug=ch.slug,
            title=ch.title,
            chapter_idx=ch.index,
            content_hash=ch.content_hash,
            chunk_count=len(ch_chunks),
        )
        for chunk in ch_chunks:
            upsert_entities_for_chunk(chunk)
            upsert_timeline_events(chunk, chunk.metadata.get("timeline_events", []))
            upsert_cooccurrences(chunk, chunk.metadata.get("cooccurrences", []))

    # Reset state
    state = {
        "last_doc_modified": modified.isoformat(),
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "burst_until": None,
        "chapter_hashes": {ch.slug: ch.content_hash for ch in chapters},
    }
    save_state(state)

    stats = collection_stats()
    print(f"\nReindex complete — {len(chapters)} chapters, {stats['total_chunks']} chunks")


if __name__ == "__main__":
    main()
