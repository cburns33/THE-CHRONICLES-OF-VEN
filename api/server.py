"""FastAPI query server.

ChatGPT or any external tool can POST to /query and receive
ranked manuscript passages as JSON.

Start with:
  uvicorn api.server:app --host 0.0.0.0 --port 8000

Endpoints:
  POST /query          Semantic search
  GET  /stats          Index statistics
  GET  /chapters       List all chapters
  GET  /health         Health check
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.retrieval.query_engine import semantic_search, entity_search, combined_search
from src.retrieval.formatters import format_for_chatgpt
from src.indexing.vector_store import collection_stats
from src.indexing.sqlite_store import get_all_chapters
from src.utils.config import load_config

app = FastAPI(
    title="Inherited Cloud — Novel Query API",
    description="Semantic search over a fantasy manuscript.",
    version="1.0.0",
)

cfg = load_config()


class QueryRequest(BaseModel):
    query: str
    top_k: int = cfg["retrieval"]["top_k"]
    filter_chapter: str | None = None
    filter_character: str | None = None
    format: str = "json"  # "json" or "chatgpt"


class QueryResponse(BaseModel):
    query: str
    results: list[dict]
    count: int
    formatted: str | None = None


@app.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results = semantic_search(
        req.query,
        top_k=req.top_k,
        filter_chapter=req.filter_chapter,
        filter_character=req.filter_character,
    )

    formatted = None
    if req.format == "chatgpt":
        formatted = format_for_chatgpt(results, req.query)

    return QueryResponse(
        query=req.query,
        results=results,
        count=len(results),
        formatted=formatted,
    )


@app.get("/entity")
def entity_endpoint(
    name: str = Query(..., description="Entity name to search for"),
    entity_type: str | None = Query(None, description="PERSON | PLACE | ORG | LORE"),
):
    results = entity_search(name, entity_type)
    return {"name": name, "matches": results, "count": len(results)}


@app.get("/chapters")
def chapters_endpoint():
    return {"chapters": get_all_chapters()}


@app.get("/stats")
def stats_endpoint():
    return collection_stats()


@app.get("/health")
def health():
    return {"status": "ok"}
