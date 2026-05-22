"""Extract structured metadata from chunk text.

Looks for:
  - POV character: lines starting with a name before a colon, or
    "POV: Name" / "— Name" annotations the author may include.
  - Timeline tags: patterns like "Year 3", "Day 12", "Spring", month names.
  - Lore tags: words in ALL CAPS (common fantasy convention for proper nouns).

All extraction is heuristic and regex-based — no LLM calls, no cost.
Results are stored as metadata on each chunk and in SQLite.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.processing.chunker import Chunk

# Patterns for timeline references
_TIMELINE_PATTERNS = [
    r"\bYear\s+\d+\b",
    r"\bDay\s+\d+\b",
    r"\b(Spring|Summer|Autumn|Fall|Winter)\b",
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    r"\b\d{1,4}\s+(years?|months?|days?|weeks?)\s+(ago|later|before|after)\b",
    r"\bthe\s+\d+(?:st|nd|rd|th)\s+year\b",
]

_TIMELINE_RE = re.compile("|".join(_TIMELINE_PATTERNS), re.IGNORECASE)

# POV annotation pattern: "POV: Elric" or "[Elric]" at start of chunk
_POV_RE = re.compile(
    r"^(?:POV[:\s]+|--\s*|—\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.MULTILINE,
)

# Lore/proper-noun detection: ALL CAPS words 3+ chars (e.g. ASH CROWN, SILVER OATH)
_LORE_RE = re.compile(r"\b([A-Z]{3,}(?:\s+[A-Z]{3,})*)\b")


def extract_metadata(chunk: "Chunk") -> dict:
    text = chunk.text

    pov = _extract_pov(text)
    timeline_tags = _extract_timeline_tags(text)
    lore_tags = _extract_lore_tags(text)

    return {
        "pov_character": pov,
        "timeline_tags": timeline_tags,
        "lore_tags": lore_tags,
    }


def _extract_pov(text: str) -> str | None:
    m = _POV_RE.search(text)
    return m.group(1).strip() if m else None


def _extract_timeline_tags(text: str) -> list[str]:
    matches = _TIMELINE_RE.findall(text)
    # Flatten tuples from alternation groups
    tags = []
    for m in matches:
        if isinstance(m, tuple):
            tags.extend(x for x in m if x)
        else:
            tags.append(m)
    return list(dict.fromkeys(tags))  # deduplicate, preserve order


def _extract_lore_tags(text: str) -> list[str]:
    raw = _LORE_RE.findall(text)
    # Filter out common English acronyms and stopwords
    _STOPWORDS = {"THE", "AND", "FOR", "BUT", "NOT", "YOU", "ARE", "CAN", "ALL"}
    return [t for t in dict.fromkeys(raw) if t not in _STOPWORDS]


def enrich_chunks(chunks: list["Chunk"]) -> list["Chunk"]:
    """Add extracted metadata to each chunk's metadata dict in-place."""
    for chunk in chunks:
        extracted = extract_metadata(chunk)
        chunk.metadata.update(extracted)
    return chunks
