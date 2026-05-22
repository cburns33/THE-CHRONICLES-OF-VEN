"""Multi-factor confidence scoring for retrieval results.

Augments each result dict with a `confidence` field (0–1) computed from:
  - cosine similarity (raw ChromaDB score)
  - entity overlap between query and chunk
  - source type weight
  - narrative position (manuscript chunks only)

Weights are configurable under retrieval.scoring in config.yaml.
"""

from __future__ import annotations

from src.processing.entity_extractor import extract_entities
from src.utils.config import load_config


def score_results(results: list[dict], query_text: str) -> list[dict]:
    """Add a `confidence` field to each result dict. Modifies in-place and returns results."""
    if not results:
        return results

    cfg = load_config()
    scoring = cfg.get("retrieval", {}).get("scoring", {})
    w_cosine   = scoring.get("cosine_weight",   0.60)
    w_entity   = scoring.get("entity_weight",   0.25)
    w_source   = scoring.get("source_weight",   0.10)
    w_position = scoring.get("position_weight", 0.05)
    source_weights = scoring.get("source_type_weights", {
        "manuscript":   1.00,
        "worldbuilding": 0.90,
        "continuity":   0.85,
    })

    # Extract named entities from the query (~5ms spaCy call)
    query_entities = extract_entities(query_text)
    query_names: set[str] = {
        e.lower()
        for entities in query_entities.values()
        for e in entities
    }

    # Max chapter index across manuscript chunks in this result set
    ms_indices = [
        r.get("chapter_index", 0)
        for r in results
        if r.get("source_type") == "manuscript"
    ]
    max_chapter_idx = max(ms_indices) if ms_indices else 1

    for r in results:
        cosine = float(r.get("score", 0))

        # Entity overlap: fraction of query entities that appear in this chunk
        if query_names:
            chunk_names: set[str] = set()
            for field in ("characters", "places"):
                raw = r.get(field, "")
                if raw:
                    chunk_names.update(n.strip().lower() for n in raw.split(",") if n.strip())
            overlap = len(query_names & chunk_names) / len(query_names)
        else:
            overlap = 0.0

        # Source type weight
        source = r.get("source_type") or "manuscript"
        src_w = source_weights.get(source, 0.85)

        # Narrative position: later chapters score slightly higher (manuscript only)
        if source == "manuscript" and max_chapter_idx > 0:
            position = r.get("chapter_index", 0) / max_chapter_idx
        else:
            position = 0.0

        confidence = (
            w_cosine   * cosine
            + w_entity   * overlap
            + w_source   * src_w
            + w_position * position
        )
        r["confidence"] = round(min(confidence, 1.0), 4)
        r["confidence_breakdown"] = {
            "cosine": round(cosine, 4),
            "entity_overlap": round(overlap, 4),
            "source_weight": round(src_w, 4),
            "position": round(position, 4),
            "matched_entities": sorted(query_names & chunk_names) if query_names else [],
            "source_type": source,
        }

    return results
