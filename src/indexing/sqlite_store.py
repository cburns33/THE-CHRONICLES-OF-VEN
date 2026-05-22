"""SQLite metadata store.

Tracks chapters, entities, and sync history. Complements ChromaDB for
structured queries that don't need semantic search, e.g.:
  - "list all chapters where Elric appears"
  - "which chapters have unresolved lore_tags?"
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.config import load_config
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.processing.chunker import Chunk

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    slug        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    chapter_idx INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    indexed_at  TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_slug TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id    TEXT NOT NULL,
    entity_type TEXT NOT NULL,   -- PERSON | PLACE | ORG | LORE
    entity_text TEXT NOT NULL,
    UNIQUE(chunk_id, entity_type, entity_text)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at   TEXT NOT NULL,
    chapters_changed INTEGER DEFAULT 0,
    chunks_added     INTEGER DEFAULT 0,
    chunks_deleted   INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_text ON entities(entity_text COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_entities_chapter ON entities(chapter_slug);
"""


@contextmanager
def _conn():
    cfg = load_config()
    db_path = Path(cfg["paths"]["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)
    log.info("SQLite database initialised")


def upsert_chapter(
    slug: str,
    title: str,
    chapter_idx: int,
    content_hash: str,
    chunk_count: int,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO chapters (slug, title, chapter_idx, content_hash, chunk_count, indexed_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title,
                chapter_idx=excluded.chapter_idx,
                content_hash=excluded.content_hash,
                chunk_count=excluded.chunk_count,
                indexed_at=excluded.indexed_at
            """,
            (slug, title, chapter_idx, content_hash, chunk_count),
        )


def delete_chapter(slug: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM chapters WHERE slug = ?", (slug,))
    log.info(f"Deleted chapter '{slug}' from SQLite")


def upsert_entities_for_chunk(chunk: "Chunk") -> None:
    entities = chunk.metadata.get("entities", {})
    lore_tags = chunk.metadata.get("lore_tags", [])

    rows = []
    for etype, names in entities.items():
        for name in names:
            rows.append((chunk.chapter_slug, chunk.chunk_id, etype, name))
    for tag in lore_tags:
        rows.append((chunk.chapter_slug, chunk.chunk_id, "LORE", tag))

    with _conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO entities (chapter_slug, chunk_id, entity_type, entity_text)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )


def delete_entities_for_chapter(chapter_slug: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM entities WHERE chapter_slug = ?", (chapter_slug,)
        )


def log_sync(chapters_changed: int, chunks_added: int, chunks_deleted: int) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO sync_log (synced_at, chapters_changed, chunks_added, chunks_deleted)
            VALUES (datetime('now'), ?, ?, ?)
            """,
            (chapters_changed, chunks_added, chunks_deleted),
        )


def search_entities(entity_text: str, entity_type: str | None = None) -> list[dict]:
    """Find chapters containing a named entity (case-insensitive partial match)."""
    with _conn() as conn:
        if entity_type:
            rows = conn.execute(
                """
                SELECT DISTINCT e.chapter_slug, c.title, c.chapter_idx, e.entity_type
                FROM entities e
                JOIN chapters c ON c.slug = e.chapter_slug
                WHERE e.entity_text LIKE ? AND e.entity_type = ?
                ORDER BY c.chapter_idx
                """,
                (f"%{entity_text}%", entity_type.upper()),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT e.chapter_slug, c.title, c.chapter_idx, e.entity_type
                FROM entities e
                JOIN chapters c ON c.slug = e.chapter_slug
                WHERE e.entity_text LIKE ?
                ORDER BY c.chapter_idx
                """,
                (f"%{entity_text}%",),
            ).fetchall()
        return [dict(r) for r in rows]


def get_all_chapters() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chapters ORDER BY chapter_idx"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_entities() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT entity_text AS name, entity_type FROM entities ORDER BY entity_text"
        ).fetchall()
        return [dict(r) for r in rows]
