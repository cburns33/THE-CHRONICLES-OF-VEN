"""SQLite metadata store.

Tracks chapters, entities, timeline events, character co-occurrences,
and sync history. Complements ChromaDB for structured queries that don't
need semantic search, e.g.:
  - "list all chapters where Elric appears"
  - "which character pairs appear together most often?"
  - "what timeline events exist in chapter 3?"
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

CREATE TABLE IF NOT EXISTS timeline_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_slug TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id     TEXT NOT NULL,
    chapter_idx  INTEGER NOT NULL,
    chunk_index  INTEGER NOT NULL,
    raw_tag      TEXT NOT NULL,
    tag_type     TEXT NOT NULL,   -- "year" | "day" | "season" | "month" | "relative"
    sequence_hint REAL,           -- numeric sort key; NULL if unextractable
    UNIQUE(chunk_id, raw_tag)
);

CREATE TABLE IF NOT EXISTS character_cooccurrences (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a     TEXT NOT NULL,   -- alphabetically first
    entity_b     TEXT NOT NULL,   -- alphabetically second
    chapter_slug TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id     TEXT NOT NULL,
    chapter_idx  INTEGER NOT NULL,
    chunk_index  INTEGER NOT NULL,
    UNIQUE(chunk_id, entity_a, entity_b)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at   TEXT NOT NULL,
    chapters_changed INTEGER DEFAULT 0,
    chunks_added     INTEGER DEFAULT 0,
    chunks_deleted   INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entities_type    ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_text    ON entities(entity_text COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_entities_chapter ON entities(chapter_slug);
CREATE INDEX IF NOT EXISTS idx_timeline_chapter ON timeline_events(chapter_idx, chunk_index);
CREATE INDEX IF NOT EXISTS idx_timeline_seq     ON timeline_events(sequence_hint);
CREATE INDEX IF NOT EXISTS idx_cooc_pair        ON character_cooccurrences(entity_a, entity_b);
CREATE INDEX IF NOT EXISTS idx_cooc_entity_a    ON character_cooccurrences(entity_a);
CREATE INDEX IF NOT EXISTS idx_cooc_entity_b    ON character_cooccurrences(entity_b);

CREATE TABLE IF NOT EXISTS narrative_states (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text             TEXT NOT NULL,
    entity_type             TEXT NOT NULL,
    as_of_chapter_idx       INTEGER NOT NULL,
    first_seen_chapter_idx  INTEGER,
    last_seen_chapter_idx   INTEGER,
    appearance_count        INTEGER DEFAULT 0,
    known_associates        TEXT DEFAULT "",   -- comma-sep names
    source_chunk_ids        TEXT DEFAULT "",   -- comma-sep chunk_ids
    UNIQUE(entity_text, as_of_chapter_idx)
);
CREATE INDEX IF NOT EXISTS idx_ns_entity  ON narrative_states(entity_text COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_ns_chapter ON narrative_states(as_of_chapter_idx);
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


# ── Chapters ──────────────────────────────────────────────────────────────────

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


def get_all_chapters(manuscript_only: bool = False) -> list[dict]:
    with _conn() as conn:
        sql = "SELECT * FROM chapters"
        if manuscript_only:
            sql += " WHERE slug LIKE 'ch%'"
        sql += " ORDER BY chapter_idx"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


# ── Entities ──────────────────────────────────────────────────────────────────

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


def get_all_entities() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT entity_text AS name, entity_type FROM entities ORDER BY entity_text"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Timeline events ───────────────────────────────────────────────────────────

def upsert_timeline_events(chunk: "Chunk", events: list[dict]) -> None:
    """Insert structured timeline events for a chunk (skips duplicates)."""
    if not events:
        return
    rows = [
        (
            chunk.chapter_slug,
            chunk.chunk_id,
            chunk.chapter_index,
            chunk.chunk_index,
            e["raw_tag"],
            e["tag_type"],
            e.get("sequence_hint"),
        )
        for e in events
    ]
    with _conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO timeline_events
                (chapter_slug, chunk_id, chapter_idx, chunk_index, raw_tag, tag_type, sequence_hint)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def delete_timeline_for_chapter(chapter_slug: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM timeline_events WHERE chapter_slug = ?", (chapter_slug,)
        )


def get_full_timeline() -> list[dict]:
    """Return manuscript timeline events sorted by sequence_hint (NULLs last), then chapter."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT t.raw_tag, t.tag_type, t.sequence_hint,
                   t.chapter_idx, t.chunk_index, c.title AS chapter_title
            FROM timeline_events t
            JOIN chapters c ON c.slug = t.chapter_slug
            WHERE t.chapter_slug LIKE 'ch%'
            ORDER BY t.sequence_hint ASC NULLS LAST, t.chapter_idx, t.chunk_index
            """
        ).fetchall()
        return [dict(r) for r in rows]


def detect_timeline_gaps() -> list[dict]:
    """Return year-type events where consecutive sequence_hints jump by more than 1."""
    rows = get_full_timeline()
    year_events = [r for r in rows if r["tag_type"] == "year" and r["sequence_hint"] is not None]
    gaps = []
    for i in range(1, len(year_events)):
        prev, curr = year_events[i - 1], year_events[i]
        if curr["sequence_hint"] - prev["sequence_hint"] > 1:
            gaps.append({
                "from_year": prev["sequence_hint"],
                "to_year": curr["sequence_hint"],
                "from_chapter": prev["chapter_title"],
                "to_chapter": curr["chapter_title"],
            })
    return gaps


# ── Character co-occurrences ──────────────────────────────────────────────────

def upsert_cooccurrences(chunk: "Chunk", pairs: list[tuple[str, str]]) -> None:
    """Insert character co-occurrence pairs for a chunk (skips duplicates)."""
    if not pairs:
        return
    rows = [
        (pair[0], pair[1], chunk.chapter_slug, chunk.chunk_id, chunk.chapter_index, chunk.chunk_index)
        for pair in pairs
    ]
    with _conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO character_cooccurrences
                (entity_a, entity_b, chapter_slug, chunk_id, chapter_idx, chunk_index)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def delete_cooccurrences_for_chapter(chapter_slug: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM character_cooccurrences WHERE chapter_slug = ?", (chapter_slug,)
        )


def get_cooccurrences_for_entity(entity_text: str) -> list[dict]:
    """Return all co-occurrence records involving a given entity (case-insensitive)."""
    name = entity_text.lower()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT entity_a, entity_b, chapter_slug, chapter_idx, COUNT(*) AS count
            FROM character_cooccurrences
            WHERE lower(entity_a) = ? OR lower(entity_b) = ?
            GROUP BY entity_a, entity_b, chapter_slug, chapter_idx
            ORDER BY chapter_idx, count DESC
            """,
            (name, name),
        ).fetchall()
        return [dict(r) for r in rows]


def get_relationship_summary() -> list[dict]:
    """Return co-occurring pairs from manuscript chapters only, sorted by frequency."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT entity_a, entity_b, COUNT(*) AS count,
                   COUNT(DISTINCT chapter_slug) AS chapter_count
            FROM character_cooccurrences
            WHERE chapter_slug LIKE 'ch%'
            GROUP BY entity_a, entity_b
            ORDER BY count DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_most_connected_characters(limit: int = 10) -> list[dict]:
    """Return characters ranked by total co-occurrence count across all pairs."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT entity, SUM(count) AS total_connections
            FROM (
                SELECT entity_a AS entity, COUNT(*) AS count FROM character_cooccurrences GROUP BY entity_a
                UNION ALL
                SELECT entity_b AS entity, COUNT(*) AS count FROM character_cooccurrences GROUP BY entity_b
            )
            GROUP BY entity
            ORDER BY total_connections DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Narrative states ──────────────────────────────────────────────────────────

def upsert_narrative_state(
    entity_text: str,
    entity_type: str,
    as_of_chapter_idx: int,
    first_seen: int | None,
    last_seen: int | None,
    appearance_count: int,
    known_associates: str,
    source_chunk_ids: str,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO narrative_states
                (entity_text, entity_type, as_of_chapter_idx, first_seen_chapter_idx,
                 last_seen_chapter_idx, appearance_count, known_associates, source_chunk_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_text, as_of_chapter_idx) DO UPDATE SET
                entity_type=excluded.entity_type,
                first_seen_chapter_idx=excluded.first_seen_chapter_idx,
                last_seen_chapter_idx=excluded.last_seen_chapter_idx,
                appearance_count=excluded.appearance_count,
                known_associates=excluded.known_associates,
                source_chunk_ids=excluded.source_chunk_ids
            """,
            (entity_text, entity_type, as_of_chapter_idx, first_seen, last_seen,
             appearance_count, known_associates, source_chunk_ids),
        )


def delete_narrative_states_from(chapter_idx: int) -> None:
    """Delete all narrative state snapshots for as_of_chapter_idx >= chapter_idx."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM narrative_states WHERE as_of_chapter_idx >= ?", (chapter_idx,)
        )


def get_narrative_state(entity_text: str, as_of_chapter_idx: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM narrative_states WHERE entity_text = ? AND as_of_chapter_idx = ?",
            (entity_text, as_of_chapter_idx),
        ).fetchone()
        return dict(row) if row else None


def get_all_narrative_states_for_entity(entity_text: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM narrative_states
            WHERE entity_text = ? COLLATE NOCASE
            ORDER BY as_of_chapter_idx
            """,
            (entity_text,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_entity_appearances_by_chapter() -> list[dict]:
    """Return PERSON entity appearance counts per manuscript chapter, for the character bar chart."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT e.entity_text, c.chapter_idx, c.title AS chapter_title,
                   COUNT(*) AS count
            FROM entities e
            JOIN chapters c ON c.slug = e.chapter_slug
            WHERE e.entity_type = 'PERSON'
              AND c.slug LIKE 'ch%'
            GROUP BY e.entity_text, c.chapter_idx
            ORDER BY c.chapter_idx, count DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_lore_tag_counts_by_chapter() -> list[dict]:
    """Return count of LORE entities per chapter, for the dashboard."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT c.chapter_idx, c.title AS chapter_title, COUNT(*) AS lore_tag_count
            FROM entities e
            JOIN chapters c ON c.slug = e.chapter_slug
            WHERE e.entity_type = 'LORE'
            GROUP BY c.slug
            ORDER BY c.chapter_idx
            """
        ).fetchall()
        return [dict(r) for r in rows]


# ── Sync log ──────────────────────────────────────────────────────────────────

def log_sync(chapters_changed: int, chunks_added: int, chunks_deleted: int) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO sync_log (synced_at, chapters_changed, chunks_added, chunks_deleted)
            VALUES (datetime('now'), ?, ?, ?)
            """,
            (chapters_changed, chunks_added, chunks_deleted),
        )


def get_character_arc_summary() -> list[dict]:
    """Return first/last appearance chapter and total counts per named character.

    Restricted to manuscript chapters only (slug prefix 'ch'), excluding continuity docs.
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT e.entity_text,
                   MIN(c.chapter_idx) AS first_chapter,
                   MAX(c.chapter_idx) AS last_chapter,
                   COUNT(DISTINCT c.chapter_idx) AS chapters_present,
                   COUNT(*) AS total_appearances
            FROM entities e
            JOIN chapters c ON c.slug = e.chapter_slug
            WHERE e.entity_type = 'PERSON'
              AND c.slug LIKE 'ch%'
            GROUP BY e.entity_text
            ORDER BY total_appearances DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_place_appearances_by_chapter() -> list[dict]:
    """Return PLACE entity appearance counts per manuscript chapter."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT e.entity_text, c.chapter_idx, c.title AS chapter_title,
                   COUNT(*) AS count
            FROM entities e
            JOIN chapters c ON c.slug = e.chapter_slug
            WHERE e.entity_type = 'PLACE'
              AND c.slug LIKE 'ch%'
            GROUP BY e.entity_text, c.chapter_idx
            ORDER BY c.chapter_idx, count DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_entity_type_breakdown_by_chapter() -> list[dict]:
    """Return entity counts grouped by manuscript chapter and entity_type."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT c.chapter_idx, c.title AS chapter_title,
                   e.entity_type, COUNT(*) AS count
            FROM entities e
            JOIN chapters c ON c.slug = e.chapter_slug
            WHERE c.slug LIKE 'ch%'
            GROUP BY c.chapter_idx, e.entity_type
            ORDER BY c.chapter_idx, e.entity_type
            """
        ).fetchall()
        return [dict(r) for r in rows]
