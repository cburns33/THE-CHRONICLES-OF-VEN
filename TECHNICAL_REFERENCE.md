# Inherited Cloud — Technical Reference

This document exists so that new Claude sessions can understand the full codebase without reading individual source files. Keep it updated after each implementation session.

**Last updated:** 2026-05-22 — Phases 1–3 complete; known_lore added.

---

## Key Paths

| What | Where |
|---|---|
| All runtime config | `config.yaml` |
| Secrets | `.env` (OPENAI_API_KEY) |
| Google OAuth | `credentials.json`, `token.json` |
| Vector store | `data/chroma_db/` (ChromaDB, collection = `"manuscript"`) |
| Structured metadata | `data/novel.db` (SQLite) |
| Embedding query cache | `data/embedding_cache.db` |
| Sync state + hashes | `data/sync_state.json` |
| Continuity file hashes | `data/continuity_state.json` |
| Per-chapter markdown | `data/markdown/` |
| Raw Google Docs JSON | `data/raw/manuscript.json` |

---

## Data Flow (abbreviated)

```
Google Docs API → google_docs.fetch_doc_as_json()
  → converter.docs_json_to_chapters() → [Chapter]
  → chunker.chunk_chapter() → [Chunk]
  → metadata_extractor.enrich_chunks()       # pov, timeline_tags, lore_tags
  → entity_extractor.enrich_chunks_with_entities()  # PERSON/PLACE/ORG via spaCy
  → embedder.embed_chunks()                  # OpenAI text-embedding-3-small + SQLite cache
  → vector_store.upsert_chunks()             # ChromaDB
  → sqlite_store.upsert_chapter()            # chapters table
  → sqlite_store.upsert_entities_for_chunk() # entities table

continuity_docs/ → doc_reader.read_file() → same pipeline above
```

Query flow:
```
query_engine.semantic_search(query_text)
  → embedder.embed_texts([query_text], use_cache=True)
  → vector_store.query(vector, top_k, where)
  → returns list[dict] with text + all ChromaDB metadata + score (0–1)
```

---

## Module Inventory

### `src/processing/`

**`chunker.py`**
```python
@dataclass
class Chunk:
    chunk_id: str           # SHA256 of (doc_id + chapter_slug + chunk_index)
    doc_id: str             # Google Doc ID or filename
    chapter_index: int
    chapter_title: str
    chapter_slug: str
    scene_heading: str
    text: str
    token_count: int
    chunk_index: int
    metadata: dict          # populated by enrich_chunks() and enrich_chunks_with_entities()

def chunk_chapter(chapter: Chapter, doc_id: str) -> list[Chunk]
    # RecursiveCharacterTextSplitter, 600 tokens, 100 overlap
    # separators: ["\n## ", "\n### ", "\n#### ", "\n\n"]
```

**`converter.py`**
```python
@dataclass
class Chapter:
    slug: str               # e.g. "ch00-chapter-1---the-feral-boy-of-harrowgate"
    title: str
    index: int
    content: str            # raw Markdown
    content_hash: str       # SHA256

def docs_json_to_chapters(raw_json: dict) -> list[Chapter]
    # Parses Google Docs API response with includeTabsContent=True
    # Each tab = one chapter
```

**`metadata_extractor.py`**
```python
def extract_metadata(chunk: Chunk) -> dict
    # Returns {"pov_character": str|None, "timeline_tags": list[str], "lore_tags": list[str]}

def enrich_chunks(chunks: list[Chunk]) -> list[Chunk]
    # Calls extract_metadata() per chunk and updates chunk.metadata in-place

# Patterns:
#   _TIMELINE_PATTERNS: Year N, Day N, Spring/Summer/Autumn/Fall/Winter, month names,
#                       "N years ago", "Nth year"
#   _LORE_RE: ALL CAPS words 3+ chars
#   _STOPWORDS: {"THE", "AND", "FOR", "BUT", "NOT", "YOU", "ARE", "CAN", "ALL"}
#   NOTE: _STOPWORDS is only 9 words — needs expansion to ~50 (Phase 2 task)
```

**`entity_extractor.py`**
```python
def extract_entities(text: str) -> dict[str, list[str]]
    # Returns {"PERSON": [...], "PLACE": [...], "ORG": [...], "LORE": [...]}
    # Uses spaCy en_core_web_sm (loaded once via lru_cache)
    # Caps input at 10k chars; maps GPE/LOC → PLACE
    # Known-entity lists from config.yaml injected before spaCy runs (Phase 2)
    # known_lore terms injected as LORE entries — catches world-specific common words

def enrich_chunks_with_entities(chunks: list[Chunk]) -> list[Chunk]
    # Calls extract_entities() per chunk, stores as chunk.metadata["entities"]
```

**`doc_reader.py`**
```python
def read_file(path: Path) -> str   # reads DOCX (python-docx) or PDF (pdfplumber)
```

### `src/indexing/`

**`incremental.py`** — THE indexing pipeline entry point
```python
def index_chapter(chapter: Chapter, doc_id: str) -> int
    # Full pipeline for one chapter. Returns chunks inserted.
    # Steps: delete_by_chapter → chunk_chapter → enrich_chunks
    #        → enrich_chunks_with_entities → embed_chunks
    #        → upsert_chunks → upsert_chapter → upsert_entities_for_chunk
    # Phase 2+ will add: upsert_timeline_events, upsert_cooccurrences
    # Phase 3+ will add: build_narrative_states

def index_changed_chapters(all_chapters, changed_slugs, doc_id) -> tuple[int, int]
    # Calls index_chapter() for each changed slug. Returns (chunks_added, chapters_processed).
```

**`vector_store.py`** — ChromaDB wrapper
```python
COLLECTION_NAME = "manuscript"   # single collection for ALL source types

def upsert_chunks(chunks: list[Chunk], vectors: list[list[float]]) -> None
def delete_by_chapter(chapter_slug: str) -> int   # returns count deleted
def query(vector, top_k=8, where=None) -> list[dict]
    # Returns list[dict] with keys: text, score (0–1), + all metadata fields
    # score = 1 - (cosine_distance / 2)
    # Filters results below config["retrieval"]["min_score"] (default 0.30)
def get_embedding_by_id(chunk_id: str) -> list[float] | None
def collection_stats() -> dict   # {"total_chunks": int, "collection": str}
```

**`sqlite_store.py`** — SQLite wrapper
```python
def init_db() -> None   # runs _SCHEMA (CREATE TABLE IF NOT EXISTS)
def upsert_chapter(slug, title, chapter_idx, content_hash, chunk_count) -> None
def delete_chapter(slug: str) -> None
def upsert_entities_for_chunk(chunk: Chunk) -> None
    # Reads chunk.metadata["entities"] and chunk.metadata["lore_tags"]
    # Inserts rows into entities table (INSERT OR IGNORE)
def delete_entities_for_chapter(chapter_slug: str) -> None
def log_sync(chapters_changed, chunks_added, chunks_deleted) -> None
def search_entities(entity_text: str, entity_type: str | None = None) -> list[dict]
    # Case-insensitive partial match on entity_text. Returns [{chapter_slug, title, chapter_idx, entity_type}]
def get_all_chapters() -> list[dict]   # ordered by chapter_idx
def get_all_entities() -> list[dict]   # [{name, entity_type}], deduplicated
```

**`embedder.py`**
```python
def embed_texts(texts: list[str], use_cache: bool = True) -> list[list[float]]
    # OpenAI text-embedding-3-small. Cache = SQLite embedding_cache.db.
    # Cache key = SHA256(text). Returns 1536-dim vectors.

def embed_chunks(chunks: list[Chunk]) -> tuple[list[Chunk], list[list[float]]]
    # Embeds chunk.text for all chunks. Returns (chunks, vectors).
```

### `src/retrieval/`

**`query_engine.py`**
```python
def semantic_search(
    query_text: str,
    top_k: int | None = None,       # default from config["retrieval"]["top_k"] = 8
    filter_chapter: str | None = None,
    filter_characters: list[str] | None = None,
    filter_places: list[str] | None = None,
    filter_source: str | None = None,  # "manuscript" | "continuity" | "worldbuilding"
) -> list[dict]
    # Returns results sorted by score descending.
    # filter_characters/places: ChromaDB doesn't do substring, so top_k*3 fetched then post-filtered.
    # Each result dict: {text, score, chunk_id, doc_id, chapter_index, chapter_title,
    #                    chapter_slug, scene_heading, token_count, chunk_index,
    #                    pov_character, timeline_tags, lore_tags, characters, places,
    #                    source_type, source_file, doc_subtype}

def entity_search(name: str, entity_type: str | None = None) -> list[dict]
    # Wraps sqlite_store.search_entities()

def more_like_this(chunk_id: str, top_k=None, filter_source=None) -> list[dict]
    # Fetches stored vector from ChromaDB, queries without calling OpenAI.

def combined_search(query_text, top_k=None, filter_chapter=None, filter_characters=None) -> dict
    # Returns {"semantic": list[dict], "entity_matches": list[dict]}
```

**`formatters.py`**
```python
def format_for_terminal(results: list[dict], query: str = "") -> str
def format_for_chatgpt(results: list[dict], query: str = "") -> str
    # Returns "MANUSCRIPT CONTEXT — Query: ...\n[Passage N — Chapter › Scene]\ntext\n..."
    # Used by api/server.py for the context_block field
def format_as_json(results: list[dict]) -> str
```

### `src/sync/`

**`google_docs.py`**
```python
def fetch_doc_as_json(doc_id: str) -> dict   # calls Docs API with includeTabsContent=True
```

**`change_detector.py`**
```python
def detect_changes(chapters: list[Chapter], state_path: Path) -> list[str]
    # Compares SHA256 hashes. Returns slugs of changed chapters.
def enter_burst_mode(state_path: Path) -> None   # sets burst_until = now + 3h
def is_burst_active(state_path: Path) -> bool
```

### `src/utils/`
```python
# config.py
def load_config() -> dict   # reads config.yaml (cached per process)

# hashing.py
def chunk_id(doc_id: str, chapter_slug: str, chunk_index: int) -> str   # SHA256

# logging.py
def get_logger(name: str) -> logging.Logger
```

---

## SQLite Schema (`data/novel.db`)

```sql
CREATE TABLE chapters (
    slug         TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    chapter_idx  INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_count  INTEGER DEFAULT 0,
    indexed_at   TEXT
);

CREATE TABLE entities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_slug TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id     TEXT NOT NULL,
    entity_type  TEXT NOT NULL,   -- PERSON | PLACE | ORG | LORE
    entity_text  TEXT NOT NULL,
    UNIQUE(chunk_id, entity_type, entity_text)
);
CREATE INDEX idx_entities_type    ON entities(entity_type);
CREATE INDEX idx_entities_text    ON entities(entity_text COLLATE NOCASE);
CREATE INDEX idx_entities_chapter ON entities(chapter_slug);

CREATE TABLE sync_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at        TEXT NOT NULL,
    chapters_changed INTEGER DEFAULT 0,
    chunks_added     INTEGER DEFAULT 0,
    chunks_deleted   INTEGER DEFAULT 0
);
```

**Phase 3 additions (now live):**
```sql
CREATE TABLE narrative_states (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text             TEXT NOT NULL,
    entity_type             TEXT NOT NULL,
    as_of_chapter_idx       INTEGER NOT NULL,
    first_seen_chapter_idx  INTEGER,
    last_seen_chapter_idx   INTEGER,
    appearance_count        INTEGER DEFAULT 0,
    known_associates        TEXT DEFAULT "",
    source_chunk_ids        TEXT DEFAULT "",
    UNIQUE(entity_text, as_of_chapter_idx)
);
```

**Planned additions (Phase 4, not yet implemented):**
```sql
-- Phase 4
CREATE TABLE wiki_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subject          TEXT NOT NULL UNIQUE,
    subject_type     TEXT NOT NULL,
    summary          TEXT,
    raw_passages     TEXT NOT NULL DEFAULT "[]",
    appearance_count INTEGER DEFAULT 0,
    first_chapter_idx INTEGER,
    last_chapter_idx  INTEGER,
    last_generated   TEXT,
    UNIQUE(subject)
);
```

**Phase 2 tables (already in schema):**
```sql
-- Phase 2
CREATE TABLE timeline_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_slug  TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id      TEXT NOT NULL,
    chapter_idx   INTEGER NOT NULL,
    chunk_index   INTEGER NOT NULL,
    raw_tag       TEXT NOT NULL,
    tag_type      TEXT NOT NULL,  -- "year"|"day"|"season"|"month"|"relative"
    sequence_hint REAL,           -- numeric sort key; NULL if not extractable
    UNIQUE(chunk_id, raw_tag)
);

CREATE TABLE character_cooccurrences (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a     TEXT NOT NULL,
    entity_b     TEXT NOT NULL,
    chapter_slug TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id     TEXT NOT NULL,
    chapter_idx  INTEGER NOT NULL,
    chunk_index  INTEGER NOT NULL,
    UNIQUE(chunk_id, entity_a, entity_b)
);

-- Phase 3
CREATE TABLE narrative_states (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text            TEXT NOT NULL,
    entity_type            TEXT NOT NULL,
    as_of_chapter_idx      INTEGER NOT NULL,
    first_seen_chapter_idx INTEGER,
    last_seen_chapter_idx  INTEGER,
    appearance_count       INTEGER DEFAULT 0,
    known_associates       TEXT DEFAULT "",  -- comma-sep names
    source_chunk_ids       TEXT DEFAULT "",  -- comma-sep chunk_ids
    UNIQUE(entity_text, as_of_chapter_idx)
);

-- Phase 4
CREATE TABLE wiki_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subject          TEXT NOT NULL UNIQUE,
    subject_type     TEXT NOT NULL,   -- "character"|"place"|"org"|"lore"
    summary          TEXT,            -- NULL until LLM-generated
    raw_passages     TEXT NOT NULL DEFAULT "[]",  -- JSON array
    appearance_count INTEGER DEFAULT 0,
    first_chapter_idx INTEGER,
    last_chapter_idx  INTEGER,
    last_generated   TEXT,            -- ISO datetime or NULL
    UNIQUE(subject)
);
```

---

## ChromaDB Metadata Fields (per chunk)

All values must be `str | int | float | bool` (ChromaDB constraint).

```python
{
    "chunk_id":      str,   # SHA256(doc_id + chapter_slug + chunk_index)
    "doc_id":        str,   # Google Doc ID or filename
    "chapter_index": int,
    "chapter_title": str,
    "chapter_slug":  str,
    "scene_heading": str,   # heading of current section, or chapter title
    "token_count":   int,
    "chunk_index":   int,   # position within chapter
    "pov_character": str,   # "" if not detected
    "timeline_tags": str,   # comma-separated, e.g. "Fall, Year 3"
    "lore_tags":     str,   # comma-separated ALL CAPS terms
    "characters":    str,   # comma-separated PERSON entities
    "places":        str,   # comma-separated PLACE entities
    "source_type":   str,   # "manuscript" | "continuity" | "worldbuilding"
    "source_file":   str,   # "" for manuscript; filename for continuity docs
    "doc_subtype":   str,   # "handoff" | "transcript" | "story" | "worldbuilding" | ""
}
```

**Known bug:** 92 novel manuscript chunks have `source_type` missing (no field, not empty string). Fix is in Phase 2 (full reindex). Use `not m.get("source_type")` to catch them.

---

## API (`api/server.py`)

**POST `/ask`** — Primary Custom GPT endpoint
```python
# Request:
{"question": str, "search_in": "everything"|"novel"|"continuity"|"worldbuilding", "top_k": int (1–20, default 6)}

# Response:
{"question": str, "passages": list[dict], "context_block": str, "total_results": int}
# passages[n]: {"chapter": str, "scene": str|None, "source": str, "relevance_score": float, "text": str}
# context_block: output of format_for_chatgpt()
```

**GET `/entity?name=X`** — Character/place chapter lookup

**GET `/chapters`** — List indexed chapters (manuscript only)

**GET `/stats`** — ChromaDB chunk count

**GET `/health`** — `{"status": "ok"}`

---

## Config Keys (`config.yaml`)

```yaml
google_docs:
  document_id: str
  burst_interval_seconds: 1800   # 30min
  burst_duration_seconds: 10800  # 3h

chunking:
  chunk_size: 600       # tokens
  chunk_overlap: 100    # tokens
  scene_separators: ["\n## ", "\n### ", "\n#### ", "\n\n"]

embeddings:
  provider: "openai"    # or "local"
  openai_model: "text-embedding-3-small"
  local_model: "all-MiniLM-L6-v2"

retrieval:
  top_k: 8
  min_score: 0.30
  scoring:
    cosine_weight: 0.60
    entity_weight: 0.25
    source_weight: 0.10
    position_weight: 0.05
    source_type_weights: {manuscript: 1.00, worldbuilding: 0.90, continuity: 0.85}

entities:
  known_characters: [...]   # fantasy names spaCy misses → tagged PERSON
  known_places:     [...]   # fantasy places → tagged PLACE
  known_orgs:       [...]   # factions, deities → tagged ORG
  known_lore:       [...]   # world-specific common words used as proper nouns → tagged LORE
                            # e.g. "Working"/"Workings" (spell name), "Myth" (god) already in known_orgs

paths:
  data_dir, raw_dir, markdown_dir, chunks_dir, chroma_dir, db_path, state_path, log_path

api:
  host: "0.0.0.0"
  port: 8000

ui:
  host: "0.0.0.0"
  port: 8501
  title: "Novel Search"
```

---

## Current Index State (2026-05-22)

| Source | Files | Chunks |
|---|---|---|
| Novel manuscript (Google Docs) | 9 chapters | 92 chunks |
| Continuity docs | 8 files | 5,655 chunks |
| Worldbuilding | 1 file | 26 chunks |
| **Total** | | **~5,773 chunks** |

Continuity doc notes: Several files are raw ChatGPT conversation exports (user messages + AI responses mixed with story content). Accepted as-is (Option B decision). The Stalgrad Voon Arc doc alone = 2,113 chunks.

---

## Scripts

```
scripts/setup.py               # one-time first-run setup
scripts/sync_and_index.py      # nightly sync (calls index_changed_chapters)
scripts/full_reindex.py        # wipe ChromaDB + SQLite, rebuild everything
scripts/ingest_documents.py    # continuity docs ingestion (skip unchanged by hash)
scripts/query.py               # CLI test tool: query.py "text" [--entity] [--stats] [--chapters]
```

---

## New Files Added (Phases 1–3)

| Phase | File | Purpose |
|---|---|---|
| 1 | `src/retrieval/scorer.py` | Multi-factor confidence scoring + breakdown dict |
| 3 | `src/processing/state_builder.py` | Narrative state snapshots per entity per chapter |
| 3 | `ui/theme.py` | Shared dark fantasy CSS constant |
| 3 | `ui/pages/1_Story_Health.py` | Story health dashboard (metrics + character chart + chapter table) |

## Planned New Files (Phase 4)

| Phase | File | Purpose |
|---|---|---|
| 4 | `src/processing/wiki_builder.py` | Wiki entry builder |
| 4 | `scripts/build_wiki.py` | Wiki generation script |
| 4 | `ui/pages/2_Lore_Wiki.py` | Wiki browser page |

See `CLAUDE.md` for the full implementation plan and checklist.
