"""Tracks sync state and detects whether the Google Doc has changed.

State is persisted to data/sync_state.json so it survives process restarts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.utils.config import load_config
from src.utils.logging import get_logger

log = get_logger(__name__)


def _state_path() -> Path:
    cfg = load_config()
    return Path(cfg["paths"]["state_path"])


def load_state() -> dict:
    p = _state_path()
    if p.exists():
        return json.loads(p.read_text())
    return {
        "last_doc_modified": None,
        "last_synced": None,
        "burst_until": None,
        "chapter_hashes": {},
    }


def save_state(state: dict) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, default=str))


def doc_has_changed(current_modified: datetime, state: dict) -> bool:
    """True if the doc was modified after the last recorded modification time."""
    last = state.get("last_doc_modified")
    if not last:
        return True
    last_dt = datetime.fromisoformat(last)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    return current_modified > last_dt


def is_in_burst_mode(state: dict) -> bool:
    burst_until = state.get("burst_until")
    if not burst_until:
        return False
    burst_dt = datetime.fromisoformat(burst_until)
    if burst_dt.tzinfo is None:
        burst_dt = burst_dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < burst_dt


def mark_burst_start(state: dict) -> dict:
    cfg = load_config()
    duration = cfg["google_docs"]["burst_duration_seconds"]
    from datetime import timedelta
    burst_until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    state["burst_until"] = burst_until.isoformat()
    log.info(f"Burst mode active until {burst_until.isoformat()}")
    return state


def clear_burst_mode(state: dict) -> dict:
    state["burst_until"] = None
    return state


def changed_chapters(
    new_hashes: dict[str, str], state: dict
) -> list[str]:
    """Return slugs of chapters whose content hash has changed."""
    old_hashes = state.get("chapter_hashes", {})
    changed = []
    for slug, new_hash in new_hashes.items():
        if old_hashes.get(slug) != new_hash:
            changed.append(slug)
    # Also include chapters that were deleted (need removal)
    deleted = [s for s in old_hashes if s not in new_hashes]
    return changed + deleted
