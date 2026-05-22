"""Named entity extraction using spaCy.

Uses en_core_web_sm (12 MB, CPU-only) to extract:
  - PERSON  → characters
  - GPE/LOC → locations / places
  - ORG     → factions, guilds, organisations

Known fantasy proper nouns (Ven, Rho, etc.) are injected before spaCy runs
because spaCy's general model misses them. Configure under entities.known_*
in config.yaml.

The spaCy model is loaded once and reused across all chunks.
"""

from __future__ import annotations

import functools
from itertools import combinations
from typing import TYPE_CHECKING

import spacy
from spacy.language import Language

from src.utils.config import load_config
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.processing.chunker import Chunk

log = get_logger(__name__)

_MODEL = "en_core_web_sm"


@functools.lru_cache(maxsize=1)
def _load_model() -> Language:
    try:
        nlp = spacy.load(_MODEL, disable=["parser", "lemmatizer"])
        log.info(f"spaCy model '{_MODEL}' loaded")
        return nlp
    except OSError:
        raise OSError(
            f"spaCy model '{_MODEL}' not found. Run:\n"
            f"  python -m spacy download {_MODEL}"
        )


def extract_entities(text: str) -> dict[str, list[str]]:
    """Return {label: [entity_text, ...]} for PERSON, PLACE, ORG.

    Known fantasy names from config.yaml are checked first so spaCy misses
    don't produce gaps for the main characters and locations.
    """
    cfg = load_config()
    entity_cfg = cfg.get("entities", {})
    known_chars  = entity_cfg.get("known_characters", [])
    known_places = entity_cfg.get("known_places", [])
    known_orgs   = entity_cfg.get("known_orgs", [])
    known_lore   = entity_cfg.get("known_lore", [])

    nlp = _load_model()
    doc = nlp(text[:10_000])
    result: dict[str, list[str]] = {"PERSON": [], "PLACE": [], "ORG": [], "LORE": []}

    for ent in doc.ents:
        name = ent.text.strip()
        if ent.label_ == "PERSON":
            result["PERSON"].append(name)
        elif ent.label_ in ("GPE", "LOC"):
            result["PLACE"].append(name)
        elif ent.label_ == "ORG":
            result["ORG"].append(name)

    # Inject known entities that spaCy missed
    text_lower = text[:10_000].lower()
    for name in known_chars:
        if name.lower() in text_lower:
            result["PERSON"].append(name)
    for name in known_places:
        if name.lower() in text_lower:
            result["PLACE"].append(name)
    for name in known_orgs:
        if name.lower() in text_lower:
            result["ORG"].append(name)
    for term in known_lore:
        if term.lower() in text_lower:
            result["LORE"].append(term)

    # Deduplicate case-insensitively, keeping first occurrence
    deduped: dict[str, list[str]] = {}
    for label, names in result.items():
        seen: set[str] = set()
        unique: list[str] = []
        for name in names:
            if name.lower() not in seen:
                seen.add(name.lower())
                unique.append(name)
        deduped[label] = unique

    return deduped


def extract_cooccurrences(entities: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return sorted (entity_a, entity_b) pairs for all PERSON entities in one chunk.

    Pairs are alphabetically ordered (entity_a < entity_b) so (A, B) and (B, A)
    are always stored the same way.
    """
    persons = entities.get("PERSON", [])
    if len(persons) < 2:
        return []
    pairs = [tuple(sorted([a, b])) for a, b in combinations(persons, 2)]
    return list(dict.fromkeys(pairs))  # deduplicate


def enrich_chunks_with_entities(chunks: list["Chunk"]) -> list["Chunk"]:
    """Add entity metadata and co-occurrence pairs to each chunk in-place."""
    for chunk in chunks:
        entities = extract_entities(chunk.text)
        chunk.metadata["entities"] = entities
        chunk.metadata["cooccurrences"] = extract_cooccurrences(entities)
    return chunks
