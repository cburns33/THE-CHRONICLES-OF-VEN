"""FastAPI query server.

Serves semantic search over the manuscript and continuity docs.
Designed for both direct use and Custom GPT Actions.

Start with:
  uvicorn api.server:app --host 0.0.0.0 --port 8000

Endpoints:
  POST /ask            Primary endpoint for Custom GPT — handles all query types
  POST /query          Semantic search (raw results)
  GET  /entity         Entity/character chapter lookup
  GET  /chapters       List all chapters
  GET  /stats          Index statistics
  GET  /health         Health check
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.retrieval.query_engine import semantic_search, entity_search
from src.retrieval.formatters import format_for_chatgpt_with_citations
from src.indexing.vector_store import collection_stats
from src.indexing.sqlite_store import get_all_chapters
from src.utils.config import load_config

cfg = load_config()

app = FastAPI(
    title="Chronicles of Ven — Manuscript Search",
    description=(
        "Semantic search over a fantasy novel manuscript and its continuity documents. "
        "Returns relevant passages with chapter context for use in AI writing assistance."
    ),
    version="1.0.0",
)

# Allow ChatGPT to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── /ask — Primary Custom GPT endpoint ───────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        description="A natural language question about the manuscript, characters, lore, plot, or continuity.",
        examples=["Where was the Silver Oath first mentioned?", "What does Ven know about the Magelord?"],
    )
    search_in: str = Field(
        default="everything",
        description="Where to search: 'everything', 'novel', 'continuity', or 'worldbuilding'.",
    )
    top_k: int = Field(default=6, ge=1, le=20, description="Number of passages to return.")


class AskResponse(BaseModel):
    question: str
    passages: list[dict] = Field(description="Relevant passages from the manuscript, sorted by relevance.")
    context_block: str = Field(description="Pre-formatted context block ready to reason over.")
    total_results: int


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about the manuscript",
    description=(
        "The primary endpoint for the Custom GPT. Given a natural language question, "
        "returns the most relevant passages from the manuscript and/or continuity documents, "
        "along with a pre-formatted context block. Use this before answering any question "
        "about the novel's plot, characters, lore, timeline, or continuity."
    ),
)
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    source_map = {
        "everything": None,
        "novel": "manuscript",
        "continuity": "continuity",
        "worldbuilding": "worldbuilding",
    }
    filter_source = source_map.get(req.search_in.lower())

    results = semantic_search(
        req.question,
        top_k=req.top_k,
        filter_source=filter_source,
    )

    # Build clean passage list for the GPT to reason over
    passages = []
    for i, r in enumerate(results, 1):
        source = r.get("source_type", "manuscript")
        source_label = {
            "manuscript": "Novel",
            "continuity": f"Continuity ({r.get('doc_subtype', 'doc')})",
            "worldbuilding": "World Building",
        }.get(source, source)

        passages.append({
            "chapter": r.get("chapter_title", ""),
            "scene": r.get("scene_heading", "") or None,
            "source": source_label,
            "relevance_score": r.get("score", 0),
            "confidence": r.get("confidence"),
            "citation_key": f"[C{r.get('chapter_index', 0)}-P{i}]",
            "text": r.get("text", "").strip(),
        })

    context_block = format_for_chatgpt_with_citations(results, req.question)

    return AskResponse(
        question=req.question,
        passages=passages,
        context_block=context_block,
        total_results=len(passages),
    )


# ── /entity — Character / place lookup ───────────────────────────────────────

@app.get(
    "/entity",
    summary="Look up which chapters mention a character, place, or named object",
    description="Returns a list of chapters where the given name appears. Useful for tracking a character across the story.",
)
def entity_endpoint(
    name: str = Query(..., description="Name to search for, e.g. 'Ven', 'Harrowgate', 'Silver Oath'"),
):
    results = entity_search(name)
    return {
        "name": name,
        "appears_in": [
            {"chapter": r["chapter_title"], "chapter_number": r["chapter_idx"], "type": r["entity_type"]}
            for r in results
        ],
        "count": len(results),
    }


# ── /chapters — Chapter list ──────────────────────────────────────────────────

@app.get(
    "/chapters",
    summary="List all indexed chapters",
    description="Returns all chapters currently indexed from the manuscript.",
)
def chapters_endpoint():
    chapters = get_all_chapters()
    return {
        "chapters": [
            {"number": c["chapter_idx"], "title": c["title"], "chunks": c["chunk_count"]}
            for c in chapters
            if c.get("source_type", "manuscript") == "manuscript" or not c.get("source_type")
        ]
    }


# ── /stats ────────────────────────────────────────────────────────────────────

@app.get("/stats", summary="Index statistics", include_in_schema=False)
def stats_endpoint():
    return collection_stats()


# ── /health ───────────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check", include_in_schema=False)
def health():
    return {"status": "ok"}
