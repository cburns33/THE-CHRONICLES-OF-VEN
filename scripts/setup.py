#!/usr/bin/env python3
"""
One-time setup script. Run this first.

What it does:
  1. Validates your .env and config.yaml
  2. Tests Google Docs API authentication (opens browser on first run)
  3. Initialises the SQLite database schema
  4. Exports the manuscript from Google Docs
  5. Runs a full initial index of the entire manuscript

Usage:
  python scripts/setup.py
"""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config, get_openai_key
from src.utils.logging import get_logger
from src.indexing.sqlite_store import init_db
from src.sync.google_docs import get_doc_modified_time, fetch_doc_as_json
from src.processing.converter import docs_json_to_chapters, save_chapters
from src.processing.chunker import chunk_all_chapters
from src.processing.metadata_extractor import enrich_chunks
from src.processing.entity_extractor import enrich_chunks_with_entities
from src.indexing.embedder import embed_chunks
from src.indexing.vector_store import upsert_chunks, collection_stats
from src.indexing.sqlite_store import upsert_chapter, upsert_entities_for_chunk
from src.sync.change_detector import save_state, load_state

log = get_logger("setup")


def main():
    print("\n=== Inherited Cloud — Setup ===\n")

    # 1. Validate config
    cfg = load_config()
    doc_id = cfg["google_docs"]["document_id"]
    if doc_id == "YOUR_GOOGLE_DOC_ID_HERE":
        print("ERROR: Set your Google Doc ID in config.yaml before running setup.")
        sys.exit(1)
    print(f"Document ID: {doc_id}")

    # 2. Validate OpenAI key (if using OpenAI embeddings)
    if cfg["embeddings"]["provider"] == "openai":
        try:
            get_openai_key()
            print("OpenAI API key: OK")
        except EnvironmentError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    # 3. Test Google Docs auth
    print("\nConnecting to Google Docs (browser auth on first run)…")
    try:
        modified = get_doc_modified_time(doc_id)
        print(f"Google Docs auth: OK  (doc last modified: {modified})")
    except Exception as e:
        print(f"ERROR connecting to Google Docs: {e}")
        sys.exit(1)

    # 4. Init SQLite
    init_db()
    print("SQLite database: OK")

    # 5. Fetch doc
    raw_path = Path(cfg["paths"]["raw_dir"]) / "manuscript.json"
    print(f"\nFetching manuscript from Google Docs…")
    document = fetch_doc_as_json(doc_id, raw_path)

    # 6. Parse into chapters
    print("Parsing chapters…")
    chapters = docs_json_to_chapters(document)
    print(f"Found {len(chapters)} chapters")

    # 7. Save markdown files
    md_dir = Path(cfg["paths"]["markdown_dir"])
    save_chapters(chapters, md_dir)

    # 8. Chunk + enrich
    print("Chunking and extracting metadata…")
    chunks = chunk_all_chapters(chapters, doc_id)
    enrich_chunks(chunks)
    enrich_chunks_with_entities(chunks)
    print(f"Produced {len(chunks)} chunks")

    # 9. Embed
    print("Generating embeddings (this may take a minute)…")
    chunks, vectors = embed_chunks(chunks)

    # 10. Store
    print("Storing vectors and metadata…")
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

    # 11. Save sync state
    state = load_state()
    state["last_doc_modified"] = modified.isoformat()
    state["last_synced"] = modified.isoformat()
    state["chapter_hashes"] = {ch.slug: ch.content_hash for ch in chapters}
    save_state(state)

    # 12. Summary
    stats = collection_stats()
    print(f"\n{'='*40}")
    print(f"Setup complete!")
    print(f"  Chapters indexed : {len(chapters)}")
    print(f"  Total chunks     : {stats['total_chunks']}")
    print(f"\nNext steps:")
    print(f"  Test retrieval : python scripts/query.py")
    print(f"  Start API      : python -m uvicorn api.server:app --port 8000")
    print(f"  Start UI       : streamlit run ui/app.py")


if __name__ == "__main__":
    main()
