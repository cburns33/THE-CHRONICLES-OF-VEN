"""ChromaDB interface.

Single collection named "manuscript" stores all chunk vectors.
Metadata stored alongside vectors enables filtered queries.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings

from src.utils.config import load_config
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.processing.chunker import Chunk

log = get_logger(__name__)

COLLECTION_NAME = "manuscript"


@functools.lru_cache(maxsize=1)
def _get_client() -> chromadb.ClientAPI:
    cfg = load_config()
    db_path = Path(cfg["paths"]["chroma_dir"])
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )
    return client


def get_collection() -> chromadb.Collection:
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    chunks: list["Chunk"],
    vectors: list[list[float]],
) -> None:
    """Insert or update chunks in ChromaDB."""
    collection = get_collection()

    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [_build_chroma_meta(c) for c in chunks]

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=vectors,
        metadatas=metadatas,
    )
    log.info(f"Upserted {len(ids)} chunks into ChromaDB")


def delete_by_chapter(chapter_slug: str) -> int:
    """Delete all chunks belonging to a given chapter. Returns count deleted."""
    collection = get_collection()
    results = collection.get(
        where={"chapter_slug": chapter_slug},
        include=[],
    )
    ids = results["ids"]
    if ids:
        collection.delete(ids=ids)
        log.info(f"Deleted {len(ids)} chunks for chapter '{chapter_slug}'")
    return len(ids)


def query(
    vector: list[float],
    top_k: int = 8,
    where: dict | None = None,
) -> list[dict]:
    """Semantic search. Returns list of result dicts with text + metadata."""
    cfg = load_config()
    collection = get_collection()

    kwargs: dict = {
        "query_embeddings": [vector],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    min_score = cfg["retrieval"]["min_score"]

    for doc, meta, dist in zip(docs, metas, dists):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity score 0–1
        score = 1 - (dist / 2)
        if score < min_score:
            continue
        output.append({"text": doc, "score": round(score, 4), **meta})

    return output


def get_embedding_by_id(chunk_id: str) -> list[float] | None:
    """Return the stored embedding vector for a chunk, or None if not found."""
    collection = get_collection()
    result = collection.get(ids=[chunk_id], include=["embeddings"])
    embeddings = result.get("embeddings")
    if embeddings and len(embeddings) > 0:
        return embeddings[0]
    return None


def collection_stats() -> dict:
    collection = get_collection()
    count = collection.count()
    return {"total_chunks": count, "collection": COLLECTION_NAME}


def _build_chroma_meta(chunk: "Chunk") -> dict:
    """ChromaDB metadata values must be str, int, float, or bool."""
    meta = {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "chapter_index": chunk.chapter_index,
        "chapter_title": chunk.chapter_title,
        "chapter_slug": chunk.chapter_slug,
        "scene_heading": chunk.scene_heading or "",
        "token_count": chunk.token_count,
        "chunk_index": chunk.chunk_index,
        "pov_character": chunk.metadata.get("pov_character") or "",
        "timeline_tags": ", ".join(chunk.metadata.get("timeline_tags") or []),
        "lore_tags": ", ".join(chunk.metadata.get("lore_tags") or []),
        "characters": ", ".join(
            (chunk.metadata.get("entities") or {}).get("PERSON", [])
        ),
        "places": ", ".join(
            (chunk.metadata.get("entities") or {}).get("PLACE", [])
        ),
        # Source type — "manuscript" for Google Doc chunks, set by ingest for local files
        "source_type": chunk.metadata.get("source_type", "manuscript"),
        "source_file": chunk.metadata.get("source_file", ""),
        "doc_subtype": chunk.metadata.get("doc_subtype", ""),
    }
    return meta
