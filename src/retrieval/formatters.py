"""Format query results for different consumers.

- format_for_terminal: readable CLI output
- format_for_chatgpt:  compact context block for pasting into ChatGPT
- format_as_json:      raw structured output for the API
"""

from __future__ import annotations

import json


def format_for_terminal(results: list[dict], query: str = "") -> str:
    if not results:
        return "No results found."

    lines = []
    if query:
        lines.append(f"Query: {query}\n{'─' * 60}")

    for i, r in enumerate(results, 1):
        chapter = r.get("chapter_title", "Unknown")
        scene = r.get("scene_heading", "")
        score = r.get("score", 0)
        pov = r.get("pov_character", "")
        text = r.get("text", "").strip()

        header = f"[{i}] {chapter}"
        if scene and scene != chapter:
            header += f" › {scene}"
        if pov:
            header += f"  (POV: {pov})"
        header += f"  score={score:.2f}"

        lines.append(header)
        lines.append(text[:600] + ("…" if len(text) > 600 else ""))
        lines.append("")

    return "\n".join(lines)


def format_for_chatgpt(results: list[dict], query: str = "") -> str:
    """Produces a compact context block suitable for pasting into ChatGPT."""
    if not results:
        return "No relevant passages found."

    parts = []
    if query:
        parts.append(f"MANUSCRIPT CONTEXT — Query: {query}\n")

    for i, r in enumerate(results, 1):
        chapter = r.get("chapter_title", "Unknown chapter")
        scene = r.get("scene_heading", "")
        text = r.get("text", "").strip()
        location = chapter if not scene or scene == chapter else f"{chapter} › {scene}"

        parts.append(f"[Passage {i} — {location}]\n{text}\n")

    return "\n".join(parts)


def format_for_chatgpt_with_citations(results: list[dict], query: str = "") -> str:
    """Context block with machine-readable citation keys [C{chapter_index}-P{passage_number}].

    The GPT system prompt requires it to embed these keys inline so every claim
    can be traced back to a specific passage.
    """
    if not results:
        return "No relevant passages found."

    parts = []
    if query:
        parts.append(f"MANUSCRIPT CONTEXT — Query: {query}\n")

    for i, r in enumerate(results, 1):
        chapter_index = r.get("chapter_index", 0)
        chapter = r.get("chapter_title", "Unknown chapter")
        scene = r.get("scene_heading", "")
        text = r.get("text", "").strip()
        location = chapter if not scene or scene == chapter else f"{chapter} › {scene}"
        citation_key = f"[C{chapter_index}-P{i}]"

        parts.append(f"{citation_key} [{location}]\n{text}\n")

    return "\n".join(parts)


def format_as_json(results: list[dict]) -> str:
    return json.dumps(results, indent=2, ensure_ascii=False)


def format_confidence_breakdown(breakdown: dict) -> str:
    """One-liner explaining why a result was retrieved.

    Example: "Match: 87% similarity · 2 shared characters (Ven, Thorn) · Novel source"
    """
    parts = []

    cosine = breakdown.get("cosine", 0)
    parts.append(f"Match: {cosine:.0%} similarity")

    matched = breakdown.get("matched_entities", [])
    if matched:
        names = ", ".join(matched[:3])
        suffix = "s" if len(matched) != 1 else ""
        parts.append(f"{len(matched)} shared character{suffix} ({names})")

    src = breakdown.get("source_type", "")
    src_labels = {
        "manuscript": "Novel source",
        "continuity": "Continuity source",
        "worldbuilding": "Worldbuilding source",
    }
    if src:
        parts.append(src_labels.get(src, f"{src} source"))

    return " · ".join(parts)
