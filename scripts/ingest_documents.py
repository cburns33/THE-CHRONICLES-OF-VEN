#!/usr/bin/env python3
"""
Ingest local continuity documents (DOCX/PDF) into the index.

Scans the continuity_docs/ folder, extracts text, chunks, embeds, and
stores alongside the manuscript. Each file is tagged with source_type
("continuity" or "worldbuilding") and doc_subtype ("handoff", "transcript", etc.)

On subsequent runs, only changed files are re-indexed (tracked by file hash).

Usage:
  python scripts/ingest_documents.py
  python scripts/ingest_documents.py --reindex-all   # force full re-ingest
"""

import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.utils.logging import get_logger
from src.processing.doc_reader import read_file, classify_doc
from src.processing.metadata_extractor import enrich_chunks
from src.processing.entity_extractor import enrich_chunks_with_entities
from src.indexing.embedder import embed_chunks
from src.indexing.vector_store import upsert_chunks, delete_by_chapter
from src.indexing.sqlite_store import upsert_entities_for_chunk, upsert_chapter
from src.processing.chunker import Chunk
from src.utils.hashing import chunk_id as make_chunk_id

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

log = get_logger("ingest")

_ENCODING = tiktoken.get_encoding("cl100k_base")
_STATE_PATH = Path("data/continuity_state.json")
_DOCS_DIR = Path("continuity_docs")

SUPPORTED_EXTENSIONS = {".docx", ".pdf"}


def _token_len(text: str) -> int:
    return len(_ENCODING.encode(text))


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_state() -> dict:
    if _STATE_PATH.exists():
        return json.loads(_STATE_PATH.read_text())
    return {"files": {}}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2))


def _file_slug(filename: str) -> str:
    """Stable slug used as the 'chapter_slug' key for a local file."""
    import re
    clean = re.sub(r"[^\w\s-]", "", filename.lower())
    clean = re.sub(r"[\s_]+", "-", clean).strip("-")
    return f"local-{clean[:60]}"


def chunk_text(text: str, cfg: dict) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " "],
        chunk_size=cfg["chunking"]["chunk_size"],
        chunk_overlap=cfg["chunking"]["chunk_overlap"],
        length_function=_token_len,
    )
    return splitter.split_text(text)


def ingest_file(path: Path, cfg: dict, doc_index: int) -> int:
    """Ingest a single file. Returns number of chunks indexed."""
    filename = path.name
    slug = _file_slug(filename)
    classification = classify_doc(filename)

    log.info(f"Ingesting '{filename}' [{classification['doc_subtype']}]")

    # Extract text
    try:
        text = read_file(path)
    except Exception as e:
        log.error(f"Failed to read '{filename}': {e}")
        return 0

    if not text.strip():
        log.warning(f"No text extracted from '{filename}' — skipping")
        return 0

    # Delete existing chunks for this file
    deleted = delete_by_chapter(slug)
    if deleted:
        log.info(f"Cleared {deleted} stale chunks for '{filename}'")

    # Chunk
    raw_chunks = chunk_text(text, cfg)
    if not raw_chunks:
        return 0

    # Build Chunk objects
    chunks = []
    for i, chunk_text_str in enumerate(raw_chunks):
        cid = make_chunk_id(f"local:{filename}", slug, i)
        chunk = Chunk(
            chunk_id=cid,
            doc_id=f"local:{filename}",
            chapter_index=doc_index,
            chapter_title=filename,
            chapter_slug=slug,
            scene_heading="",
            text=chunk_text_str,
            token_count=_token_len(chunk_text_str),
            chunk_index=i,
            metadata={
                **classification,
                "source_file": filename,
            },
        )
        chunks.append(chunk)

    # Enrich
    enrich_chunks(chunks)
    enrich_chunks_with_entities(chunks)

    # Embed + store
    chunks, vectors = embed_chunks(chunks)
    upsert_chunks(chunks, vectors)

    # Register in chapters table so entity foreign keys resolve
    upsert_chapter(
        slug=slug,
        title=filename,
        chapter_idx=doc_index,
        content_hash=_file_hash(path),
        chunk_count=len(chunks),
    )

    for chunk in chunks:
        upsert_entities_for_chunk(chunk)

    log.info(f"Indexed '{filename}' — {len(chunks)} chunks [{classification['source_type']}]")
    return len(chunks)


def _run_single_file(path: Path, doc_index: int) -> int:
    """Spawn a fresh subprocess to ingest one file and return chunk count.

    Each file gets its own Python interpreter so memory (spaCy, ChromaDB,
    text buffers) is fully released by the OS when the process exits. This
    prevents memory from accumulating across files on constrained hardware.
    """
    import subprocess
    result = subprocess.run(
        [sys.executable, __file__, "--_single-file", str(path), "--_doc-index", str(doc_index)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error(f"Subprocess failed for '{path.name}':\n{result.stderr}")
        return 0
    # Last line of stdout is the chunk count written by the subprocess
    lines = result.stdout.strip().splitlines()
    for line in reversed(lines):
        if line.startswith("CHUNKS:"):
            return int(line.split(":")[1])
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reindex-all", action="store_true", help="Force re-ingest all files")
    # Internal flags used by subprocess calls — not intended for direct use
    parser.add_argument("--_single-file", dest="single_file", help=argparse.SUPPRESS)
    parser.add_argument("--_doc-index", dest="doc_index", type=int, default=0,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()

    # ── Single-file mode (called by _run_single_file) ─────────────────────────
    if args.single_file:
        cfg = load_config()
        path = Path(args.single_file)
        added = ingest_file(path, cfg, args.doc_index)
        print(f"CHUNKS:{added}")
        return

    # ── Normal orchestration mode ──────────────────────────────────────────────
    cfg = load_config()

    if not _DOCS_DIR.exists():
        print(f"ERROR: '{_DOCS_DIR}' folder not found. Create it and add your documents.")
        sys.exit(1)

    files = [f for f in sorted(_DOCS_DIR.iterdir()) if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        print(f"No DOCX or PDF files found in '{_DOCS_DIR}'.")
        sys.exit(0)

    print(f"\n=== Continuity Document Ingestion ===")
    print(f"Found {len(files)} files in {_DOCS_DIR}\n")

    state = _load_state()
    total_chunks = 0
    processed = 0
    skipped = 0

    for i, path in enumerate(files):
        fhash = _file_hash(path)
        stored_hash = state["files"].get(path.name, {}).get("hash")

        if not args.reindex_all and fhash == stored_hash:
            print(f"  [skip] {path.name} (unchanged)")
            skipped += 1
            continue

        print(f"  [index] {path.name}...")
        added = _run_single_file(path, i)
        total_chunks += added
        processed += 1

        state["files"][path.name] = {
            "hash": fhash,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "chunks": added,
            **classify_doc(path.name),
        }
        _save_state(state)

    print(f"\n{'='*40}")
    print(f"Ingestion complete!")
    print(f"  Files processed : {processed}")
    print(f"  Files skipped   : {skipped} (unchanged)")
    print(f"  Chunks added    : {total_chunks}")
    print(f"\nRun queries with --source continuity to search these docs.")


if __name__ == "__main__":
    main()
