"""Main query interface.

Accepts a natural-language query, optional filters, and returns
ranked passages with chapter context.
"""

from __future__ import annotations

from src.indexing.embedder import embed_texts
from src.indexing.vector_store import query as chroma_query, get_embedding_by_id
from src.indexing.sqlite_store import search_entities
from src.retrieval.scorer import score_results
from src.utils.config import load_config
from src.utils.logging import get_logger

log = get_logger(__name__)


def semantic_search(
    query_text: str,
    top_k: int | None = None,
    filter_chapter: str | None = None,
    filter_characters: list[str] | None = None,
    filter_places: list[str] | None = None,
    filter_source: str | None = None,
) -> list[dict]:
    """
    Search the manuscript semantically.

    Args:
        query_text:         Natural language query
        top_k:              Number of results (default from config)
        filter_chapter:     Restrict to a specific chapter slug
        filter_characters:  Restrict to chunks mentioning ALL of these characters

    Returns:
        List of result dicts, sorted by relevance score descending.
    """
    cfg = load_config()
    k = top_k or cfg["retrieval"]["top_k"]

    # Embed the query (cache hit skips the API call for repeated searches)
    [vector] = embed_texts([query_text], use_cache=True)

    # Build optional ChromaDB where filter
    where: dict | None = None
    filters = {}
    if filter_chapter:
        filters["chapter_slug"] = filter_chapter
    if filter_source:
        filters["source_type"] = filter_source
    if filter_characters or filter_places:
        # These fields are comma-separated; we can't do substring in ChromaDB
        # directly, so we fetch more results and post-filter
        k = k * 3

    if filters:
        if len(filters) == 1:
            where = filters
        else:
            where = {"$and": [{k: v} for k, v in filters.items()]}

    results = chroma_query(vector=vector, top_k=k, where=where)

    # Post-filter: chunk must mention ALL requested characters and places
    if filter_characters or filter_places:
        char_names = [n.lower() for n in (filter_characters or [])]
        place_names = [n.lower() for n in (filter_places or [])]
        results = [
            r for r in results
            if all(
                n in r.get("characters", "").lower() or n in r.get("text", "").lower()
                for n in char_names
            )
            and all(
                n in r.get("places", "").lower() or n in r.get("text", "").lower()
                for n in place_names
            )
        ]
        results = results[:top_k or cfg["retrieval"]["top_k"]]

    score_results(results, query_text)
    log.info(f"Query '{query_text[:60]}…' → {len(results)} results")
    return results


def entity_search(name: str, entity_type: str | None = None) -> list[dict]:
    """
    Find all chapters where a named entity appears.
    Useful for: "Which chapters mention the Silver Oath?"
    """
    return search_entities(name, entity_type)


def more_like_this(
    chunk_id: str,
    top_k: int | None = None,
    filter_source: str | None = None,
) -> list[dict]:
    """
    Find passages similar to an already-indexed chunk, using its stored vector.
    No API call needed — the embedding is read directly from ChromaDB.
    """
    cfg = load_config()
    k = top_k or cfg["retrieval"]["top_k"]

    vector = get_embedding_by_id(chunk_id)
    if vector is None:
        log.warning(f"No embedding found for chunk_id={chunk_id}")
        return []

    where: dict | None = None
    if filter_source:
        where = {"source_type": filter_source}

    results = chroma_query(vector=vector, top_k=k + 1, where=where)
    # The source chunk itself will be the top hit — drop it
    results = [r for r in results if r.get("chunk_id") != chunk_id]
    return results[:k]


def combined_search(
    query_text: str,
    top_k: int | None = None,
    filter_chapter: str | None = None,
    filter_characters: list[str] | None = None,
) -> dict:
    """Return both semantic results and entity matches for a query."""
    semantic = semantic_search(
        query_text, top_k=top_k,
        filter_chapter=filter_chapter,
        filter_characters=filter_characters,
    )
    # Try to extract a name from the query for entity lookup
    entity_results = []
    words = [w.strip('?"\'.,') for w in query_text.split() if len(w) > 3]
    if words:
        # Heuristic: capitalised words are likely proper nouns
        candidates = [w for w in words if w[0].isupper()]
        for name in candidates[:2]:
            entity_results.extend(search_entities(name))

    return {
        "semantic": semantic,
        "entity_matches": entity_results,
    }
