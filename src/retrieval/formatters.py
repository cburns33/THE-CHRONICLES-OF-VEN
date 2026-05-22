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


def format_as_json(results: list[dict]) -> str:
    return json.dumps(results, indent=2, ensure_ascii=False)
