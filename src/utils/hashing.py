"""Stable ID and content hashing utilities."""

import hashlib


def chunk_id(doc_id: str, chapter_slug: str, chunk_index: int) -> str:
    """Deterministic chunk ID from doc + chapter + position."""
    raw = f"{doc_id}:{chapter_slug}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def content_hash(text: str) -> str:
    """SHA-256 of normalised text, used for change detection."""
    normalised = " ".join(text.split())
    return hashlib.sha256(normalised.encode()).hexdigest()


def chapter_slug(title: str, index: int) -> str:
    """URL-safe slug: 'Chapter 3 The Ash Crown' → 'ch03-the-ash-crown'."""
    import re
    clean = re.sub(r"[^\w\s-]", "", title.lower())
    clean = re.sub(r"[\s_]+", "-", clean).strip("-")
    return f"ch{index:02d}-{clean}"
