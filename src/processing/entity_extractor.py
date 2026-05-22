"""Named entity extraction using spaCy.

Uses en_core_web_sm (12 MB, CPU-only) to extract:
  - PERSON  → characters
  - GPE/LOC → locations / places
  - ORG     → factions, guilds, organisations

Results are stored per-chunk in the SQLite entities table,
enabling structured queries like "which chapters mention Elric?"

The spaCy model is loaded once and reused across all chunks.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import spacy
from spacy.language import Language

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
    """Return {label: [entity_text, ...]} for PERSON, GPE, LOC, ORG."""
    nlp = _load_model()
    doc = nlp(text[:10_000])  # cap at 10k chars to stay within limits
    result: dict[str, list[str]] = {"PERSON": [], "PLACE": [], "ORG": []}

    for ent in doc.ents:
        text_clean = ent.text.strip()
        if ent.label_ == "PERSON":
            result["PERSON"].append(text_clean)
        elif ent.label_ in ("GPE", "LOC"):
            result["PLACE"].append(text_clean)
        elif ent.label_ == "ORG":
            result["ORG"].append(text_clean)

    # Deduplicate
    return {k: list(dict.fromkeys(v)) for k, v in result.items()}


def enrich_chunks_with_entities(chunks: list["Chunk"]) -> list["Chunk"]:
    """Add entity metadata to each chunk in-place."""
    for chunk in chunks:
        entities = extract_entities(chunk.text)
        chunk.metadata["entities"] = entities
    return chunks
