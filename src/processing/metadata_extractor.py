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

_STOPWORDS = {
    # Common English words
    "THE", "AND", "FOR", "BUT", "NOT", "YOU", "ARE", "CAN", "ALL",
    "WAS", "HIS", "HER", "ITS", "OUR", "OUT", "WHO", "DID", "GET",
    "HIM", "HAD", "HAS", "ONE", "TWO", "NEW", "OLD", "NOW", "HOW",
    "SAY", "SEE", "USE", "MAN", "MEN", "WAY", "MAY", "SHE",
    "THAT", "WITH", "THIS", "THEY", "HAVE", "FROM", "BEEN", "THEN",
    "THAN", "SOME", "WHEN", "WERE", "WHAT", "WILL", "JUST", "INTO",
    "OVER", "ALSO", "BACK", "WELL", "SUCH", "EVEN", "VERY", "SAID",
    "LIKE", "ONLY", "EACH", "THEM", "UPON", "MUCH", "YOUR", "THEIR",
    "COULD", "WOULD", "SHOULD", "ABOUT", "AFTER", "AGAIN", "EVERY",
    "FIRST", "NEVER", "OTHER", "STILL", "THINK", "THERE", "THESE",
    "THOSE", "UNDER", "WHERE", "WHICH", "WHILE", "SINCE", "MIGHT",
    "BEING", "GOING", "DOING", "UNTIL", "AMONG", "ABOVE", "BELOW",
    "BEFORE", "BEHIND", "THOUGH", "THROUGH", "ALWAYS", "AROUND",
    "ANOTHER", "BECAUSE", "WITHOUT", "HIMSELF", "HERSELF", "MYSELF",
    "YOURSELF", "NOTHING", "SOMEONE", "SOMEHOW", "SOMETHING",
    # Profanity / false positives
    "SHIT", "FUCK", "DAMN", "HELL", "CRAP", "ASS", "BITCH", "BASTARD",
}

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def extract_metadata(chunk: "Chunk") -> dict:
    text = chunk.text
    pov = _extract_pov(text)
    timeline_tags = _extract_timeline_tags(text)
    lore_tags = _extract_lore_tags(text)
    timeline_events = extract_timeline_structured(text)
    return {
        "pov_character": pov,
        "timeline_tags": timeline_tags,
        "lore_tags": lore_tags,
        "timeline_events": timeline_events,
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
    return [t for t in dict.fromkeys(raw) if t not in _STOPWORDS]


def extract_timeline_structured(text: str) -> list[dict]:
    """Return [{raw_tag, tag_type, sequence_hint}] for each timeline reference.

    tag_type: "year" | "day" | "season" | "month" | "relative"
    sequence_hint: numeric sort key, or None if unextractable
    """
    events: list[dict] = []
    seen: set[str] = set()

    def add(raw: str, tag_type: str, hint: float | None) -> None:
        if raw not in seen:
            seen.add(raw)
            events.append({"raw_tag": raw, "tag_type": tag_type, "sequence_hint": hint})

    for m in re.finditer(r"\bYear\s+(\d+)\b", text, re.IGNORECASE):
        add(m.group(0), "year", float(m.group(1)))

    for m in re.finditer(r"\bDay\s+(\d+)\b", text, re.IGNORECASE):
        add(m.group(0), "day", float(m.group(1)))

    for m in re.finditer(r"\b(Spring|Summer|Autumn|Fall|Winter)\b", text, re.IGNORECASE):
        add(m.group(0), "season", None)

    for i, month in enumerate(_MONTHS, 1):
        if re.search(rf"\b{month}\b", text, re.IGNORECASE):
            add(month, "month", float(i))

    for m in re.finditer(
        r"\b\d{1,4}\s+(?:years?|months?|days?|weeks?)\s+(?:ago|later|before|after)\b",
        text, re.IGNORECASE,
    ):
        add(m.group(0), "relative", None)

    for m in re.finditer(r"\bthe\s+\d+(?:st|nd|rd|th)\s+year\b", text, re.IGNORECASE):
        add(m.group(0), "relative", None)

    return events


def enrich_chunks(chunks: list["Chunk"]) -> list["Chunk"]:
    """Add extracted metadata to each chunk's metadata dict in-place."""
    for chunk in chunks:
        extracted = extract_metadata(chunk)
        chunk.metadata.update(extracted)
    return chunks
