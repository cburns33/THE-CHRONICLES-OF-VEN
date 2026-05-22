"""Narrative state snapshot builder.

For each unique PERSON entity, writes one cumulative row per chapter into the
`narrative_states` table. A row for (entity, N) answers: "at the end of chapter N,
what do we know about this entity?"

Called from incremental.index_chapter() after entities and co-occurrences are stored.
When chapter N is reindexed, all snapshots for as_of_chapter_idx >= N are deleted
and rebuilt so downstream chapter snapshots stay correct.
"""

from __future__ import annotations

from src.indexing.sqlite_store import (
    delete_narrative_states_from,
    get_all_chapters,
    upsert_narrative_state,
)
from src.utils.logging import get_logger

log = get_logger(__name__)


def build_narrative_states(from_chapter_idx: int) -> int:
    """Rebuild narrative state snapshots for all chapters >= from_chapter_idx.

    Returns the number of rows written.
    """
    import sqlite3
    from contextlib import contextmanager
    from pathlib import Path
    from src.utils.config import load_config

    cfg = load_config()
    db_path = Path(cfg["paths"]["db_path"])

    @contextmanager
    def _conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Wipe stale snapshots for this chapter and beyond
    delete_narrative_states_from(from_chapter_idx)

    chapters = get_all_chapters()
    if not chapters:
        return 0

    max_idx = max(c["chapter_idx"] for c in chapters)
    rows_written = 0

    for as_of_idx in range(from_chapter_idx, max_idx + 1):
        with _conn() as conn:
            # All PERSON entities with cumulative stats up to this chapter
            entity_rows = conn.execute(
                """
                SELECT e.entity_text,
                       MIN(c.chapter_idx) AS first_seen,
                       MAX(c.chapter_idx) AS last_seen,
                       COUNT(*)           AS appearance_count,
                       GROUP_CONCAT(e.chunk_id) AS chunk_ids
                FROM entities e
                JOIN chapters c ON c.slug = e.chapter_slug
                WHERE e.entity_type = 'PERSON' AND c.chapter_idx <= ?
                GROUP BY e.entity_text
                ORDER BY e.entity_text
                """,
                (as_of_idx,),
            ).fetchall()

            for row in entity_rows:
                entity = row["entity_text"]

                # Co-occurring characters seen together with this entity up to as_of_idx
                assoc_rows = conn.execute(
                    """
                    SELECT CASE WHEN entity_a = ? THEN entity_b ELSE entity_a END AS assoc,
                           COUNT(*) AS n
                    FROM character_cooccurrences
                    WHERE (entity_a = ? OR entity_b = ?) AND chapter_idx <= ?
                    GROUP BY assoc
                    ORDER BY n DESC
                    """,
                    (entity, entity, entity, as_of_idx),
                ).fetchall()

                known_associates = ",".join(r["assoc"] for r in assoc_rows)
                source_chunk_ids = row["chunk_ids"] or ""

                conn.execute(
                    """
                    INSERT INTO narrative_states
                        (entity_text, entity_type, as_of_chapter_idx,
                         first_seen_chapter_idx, last_seen_chapter_idx,
                         appearance_count, known_associates, source_chunk_ids)
                    VALUES (?, 'PERSON', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(entity_text, as_of_chapter_idx) DO UPDATE SET
                        first_seen_chapter_idx=excluded.first_seen_chapter_idx,
                        last_seen_chapter_idx=excluded.last_seen_chapter_idx,
                        appearance_count=excluded.appearance_count,
                        known_associates=excluded.known_associates,
                        source_chunk_ids=excluded.source_chunk_ids
                    """,
                    (
                        entity, as_of_idx,
                        row["first_seen"], row["last_seen"],
                        row["appearance_count"],
                        known_associates, source_chunk_ids,
                    ),
                )
                rows_written += 1

    log.info(
        f"Narrative states rebuilt from chapter {from_chapter_idx} — {rows_written} rows"
    )
    return rows_written
