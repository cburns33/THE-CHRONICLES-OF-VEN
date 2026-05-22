"""Embedding wrapper supporting OpenAI and local sentence-transformers.

Provider is controlled by config.yaml → embeddings.provider.
Batches requests to stay within API rate limits.
"""

from __future__ import annotations

import functools
import json
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.config import load_config, get_openai_key
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.processing.chunker import Chunk

log = get_logger(__name__)

_BATCH_SIZE = 100  # OpenAI allows up to 2048; 100 is safe and fast


# ── Query embedding cache (SQLite, persists across restarts) ──────────────────

def _cache_conn() -> sqlite3.Connection:
    cfg = load_config()
    db_path = Path(cfg["paths"]["data_dir"]) / "embedding_cache.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (text TEXT PRIMARY KEY, vector TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _cache_get(text: str) -> list[float] | None:
    try:
        conn = _cache_conn()
        row = conn.execute("SELECT vector FROM cache WHERE text = ?", (text,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _cache_set(text: str, vector: list[float]) -> None:
    try:
        conn = _cache_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (text, vector) VALUES (?, ?)",
            (text, json.dumps(vector)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def embed_texts(texts: list[str], use_cache: bool = False) -> list[list[float]]:
    """Return a list of embedding vectors, one per input text.

    Set use_cache=True for single query strings to avoid redundant API calls.
    Leave False for bulk indexing (always fresh).
    """
    cfg = load_config()
    provider = cfg["embeddings"]["provider"]

    if use_cache and len(texts) == 1:
        cached = _cache_get(texts[0])
        if cached is not None:
            log.debug("Embedding cache hit")
            return [cached]

    if provider == "openai":
        vectors = _embed_openai(texts, cfg["embeddings"]["openai_model"])
    elif provider == "local":
        vectors = _embed_local(texts, cfg["embeddings"]["local_model"])
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")

    if use_cache and len(texts) == 1:
        _cache_set(texts[0], vectors[0])

    return vectors


def embed_chunks(chunks: list["Chunk"]) -> tuple[list["Chunk"], list[list[float]]]:
    """Embed all chunks and return (chunks, vectors) in the same order."""
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)
    log.info(f"Generated {len(vectors)} embeddings")
    return chunks, vectors


def _embed_openai(texts: list[str], model: str) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=get_openai_key())
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        # Retry once on rate limit
        for attempt in range(2):
            try:
                resp = client.embeddings.create(model=model, input=batch)
                all_vectors.extend([r.embedding for r in resp.data])
                break
            except Exception as e:
                if attempt == 0:
                    log.warning(f"Embedding batch failed ({e}), retrying in 10s…")
                    time.sleep(10)
                else:
                    raise

    return all_vectors


@functools.lru_cache(maxsize=1)
def _get_local_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    log.info(f"Loading local embedding model: {model_name}")
    return SentenceTransformer(model_name)


def _embed_local(texts: list[str], model_name: str) -> list[list[float]]:
    model = _get_local_model(model_name)
    vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vectors]
