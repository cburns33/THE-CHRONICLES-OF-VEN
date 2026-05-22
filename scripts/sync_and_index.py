#!/usr/bin/env python3
"""
Sync pipeline — called by cron at 3am UTC daily.

Behaviour:
  - If doc unchanged since last sync: exit immediately.
  - If doc changed: index changed chapters, then enter burst mode
    (re-check every 30 min for 3 hours in case the author keeps writing).
  - After burst mode expires: exit and wait for next cron trigger.

Usage:
  python scripts/sync_and_index.py
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.utils.logging import get_logger
from src.sync.google_docs import get_doc_modified_time, fetch_doc_as_json
from src.sync.change_detector import (
    load_state,
    save_state,
    doc_has_changed,
    is_in_burst_mode,
    mark_burst_start,
    clear_burst_mode,
    changed_chapters,
)
from src.processing.converter import docs_json_to_chapters, save_chapters
from src.indexing.incremental import index_changed_chapters
from src.indexing.sqlite_store import log_sync

log = get_logger("sync")


def run_sync(cfg: dict, state: dict) -> tuple[dict, bool]:
    """
    Run one sync pass. Returns (updated_state, did_change).
    """
    doc_id = cfg["google_docs"]["document_id"]

    # Check modification time
    try:
        current_modified = get_doc_modified_time(doc_id)
    except Exception as e:
        log.error(f"Failed to check doc modification time: {e}")
        return state, False

    if not doc_has_changed(current_modified, state):
        log.info("No changes detected — skipping")
        return state, False

    log.info(f"Change detected (doc modified {current_modified})")

    # Fetch doc
    raw_path = Path(cfg["paths"]["raw_dir"]) / "manuscript.json"
    try:
        document = fetch_doc_as_json(doc_id, raw_path)
    except Exception as e:
        log.error(f"Fetch failed: {e}")
        return state, False

    # Parse chapters
    chapters = docs_json_to_chapters(document)
    save_chapters(chapters, Path(cfg["paths"]["markdown_dir"]))

    # Compute new hashes
    new_hashes = {ch.slug: ch.content_hash for ch in chapters}
    changed_slugs = changed_chapters(new_hashes, state)

    if not changed_slugs:
        log.info("Doc timestamp changed but no chapter content changed — skipping index")
        state["last_doc_modified"] = current_modified.isoformat()
        return state, False

    log.info(f"Chapters changed: {changed_slugs}")

    # Index changed chapters
    chunks_added, chapters_processed = index_changed_chapters(
        chapters, changed_slugs, doc_id
    )

    # Update state
    state["last_doc_modified"] = current_modified.isoformat()
    state["last_synced"] = datetime.now(timezone.utc).isoformat()
    state["chapter_hashes"] = new_hashes

    log_sync(
        chapters_changed=chapters_processed,
        chunks_added=chunks_added,
        chunks_deleted=0,
    )

    log.info(
        f"Sync complete — {chapters_processed} chapters, {chunks_added} chunks added"
    )
    return state, True


def main():
    cfg = load_config()
    state = load_state()

    burst_interval = cfg["google_docs"]["burst_interval_seconds"]

    # First pass
    state, changed = run_sync(cfg, state)

    if changed:
        state = mark_burst_start(state)
        save_state(state)

        # Burst loop: re-check every 30 min while burst mode is active
        while is_in_burst_mode(state):
            log.info(f"Burst mode: sleeping {burst_interval}s before next check…")
            time.sleep(burst_interval)

            state, changed = run_sync(cfg, state)
            if not changed:
                log.info("No further changes during burst mode")
            save_state(state)

        state = clear_burst_mode(state)
        save_state(state)
        log.info("Burst mode ended — returning to daily schedule")
    else:
        save_state(state)
        log.info("Exiting — next run at next cron trigger")


if __name__ == "__main__":
    main()
