# Inherited Cloud — Narrative Intelligence Platform
## Architecture Evolution Plan

---

## Context

The current system is a working semantic retrieval tool: Google Docs sync, ChromaDB embeddings, SQLite metadata, Streamlit UI, FastAPI + Custom GPT integration. The author uses it to ask questions about his manuscript and campaign history.

This plan evolves it into a more capable narrative intelligence platform by adding 8 features. The governing philosophy stays the same: compute once at index time, read many times at query time, zero new cloud services, no LLM calls unless unavoidable and cached.

**Known data bugs to fix during this work:**
- 92 novel manuscript chunks are missing `source_type` in ChromaDB metadata (they're the novel but have no label)
- `lore_tags` extractor picks up profanity as "lore terms"

---

## Executive Summary

All 8 features fit into the existing architecture without new databases or cloud services. They fall into three categories:

1. **Query layer changes** (Features 1, 5, 7): formatters, scoring, explanations — touch nothing except `formatters.py`, `query_engine.py`, and a new `scorer.py`
2. **Index-time enrichment** (Features 2, 3, 4): new SQLite tables populated during existing indexing pipeline — wired into `incremental.py`
3. **UI and generation** (Features 6, 8): new Streamlit pages + a wiki builder script

Total new code: approximately 1,200–1,500 lines across 5 new files and modifications to 6 existing ones.

---

## Feature Dependency Map

```
Feature 1 (Citations)         ← no dependencies
Feature 5 (Confidence)        ← no dependencies
Feature 3 (Timeline)          ← no dependencies
Feature 4 (Relationships)     ← existing entities table
Feature 7 (Explainability)    ← requires Feature 5
Feature 2 (State tracking)    ← requires Features 3, 4
Feature 6 (Health dashboard)  ← requires Features 3, 4 (Feature 2 optional)
Feature 8 (Lore wiki)         ← requires Feature 4
```

---

## Recommended Implementation Order

### Phase 1 — Query layer (no schema changes, ~1–2 days)
1. Feature 1: Citation-grounded answering
2. Feature 5: Retrieval confidence scoring

### Phase 2 — Index enrichment (new SQLite tables, ~3–5 days)
3. Feature 3: Timeline engine
4. Feature 4: Relationship graphs
5. Fix `source_type` bug + lore_tag stopword expansion

### Phase 3 — State tracking + UI (~4–6 days)
6. Feature 2: Narrative state tracking
7. Feature 6: Story health dashboard
8. Feature 7: Retrieval explainability

### Phase 4 — Wiki (~2–3 days)
9. Feature 8: Auto lore wiki generation

---

## Feature-by-Feature Design

---

### Feature 1: Citation-Grounded Answering

**Purpose.** The Custom GPT inconsistently cites which chapter it's drawing from. This restructures the context block format so every passage has a machine-readable citation key `[C3-P2]` (Chapter 3, Passage 2), and the system prompt requires the GPT to embed keys inline.

**Integration.**
1. `src/retrieval/formatters.py` — new function `format_for_chatgpt_with_citations(results, query)`. Each passage gets a `[C{chapter_index}-P{passage_number}]` prefix.
2. `deploy/custom_gpt/system_prompt.md` — add a "Citation format" section requiring inline key use and "not found in indexed text" when unsupported.
3. `api/server.py` — swap in the citation formatter; add `citation_key` to each passage object in the response.

**Schema changes.** None.

**New files.** None. Modifications to `formatters.py`, `server.py`, `system_prompt.md`.

**Cost.** Zero.

**Complexity.** Low.

**Hallucination reduction.** High. Forces explicit passage-level attribution on every claim.

**MVP = ideal.** Do it fully in Phase 1.

**Future extension.** A `/validate` endpoint that checks whether each cited key in a GPT response corresponds to an actual retrieved passage for that query.

---

### Feature 5: Retrieval Confidence Scoring

**Purpose.** Replace the flat cosine score with a multi-factor score that also accounts for entity overlap with the query, source type relevance, and narrative position.

**Integration.** New file `src/retrieval/scorer.py`. Wired into `query_engine.semantic_search()` — runs after ChromaDB returns results, before they're returned to the caller. Results gain both `score` (raw cosine) and `confidence` (multi-factor).

**Scoring formula:**
```
confidence = (
    0.60 * cosine_similarity
  + 0.25 * entity_overlap_ratio      # |query_entities ∩ chunk_entities| / |query_entities|
  + 0.10 * source_type_weight         # manuscript=1.0, worldbuilding=0.90, continuity=0.85
  + 0.05 * narrative_position_factor  # chapter_idx / max_chapter_idx (ms chunks only)
)
```

Entity extraction on the query string uses spaCy (already loaded, ~5ms).

Weights configurable in `config.yaml` under `retrieval.scoring`.

**Schema changes.** None.

**New files.** `src/retrieval/scorer.py`

**Cost.** Zero (~5ms spaCy call per query).

**Complexity.** Low.

**Future extension.** Author-tunable weight sliders in the Streamlit sidebar.

---

### Feature 3: Timeline Engine

**Purpose.** `timeline_tags` are currently free-text strings ("fall", "Year 3") with no ordering. This feature converts them to structured rows with a numeric `sequence_hint` for sorting, and detects timeline gaps.

**Integration.** Extend `metadata_extractor.extract_timeline_structured()` to return `{raw_tag, tag_type, sequence_hint}` dicts. Wire into `incremental.index_chapter()` to populate a new `timeline_events` table. Add `query_engine.timeline_query()`.

**Also fix here:** Expand `_STOPWORDS` in `metadata_extractor.py` from 9 words to ~50 to eliminate profanity from `lore_tags`. Static list, no API cost.

**Also fix here:** Populate `source_type="manuscript"` on novel chunks (bug fix during full reindex).

**Schema additions:**
```sql
CREATE TABLE IF NOT EXISTS timeline_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_slug    TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id        TEXT NOT NULL,
    chapter_idx     INTEGER NOT NULL,
    chunk_index     INTEGER NOT NULL,
    raw_tag         TEXT NOT NULL,
    tag_type        TEXT NOT NULL,   -- "year" | "day" | "season" | "month" | "relative"
    sequence_hint   REAL,            -- numeric sort key; NULL if unextractable
    UNIQUE(chunk_id, raw_tag)
);
CREATE INDEX IF NOT EXISTS idx_timeline_chapter ON timeline_events(chapter_idx, chunk_index);
CREATE INDEX IF NOT EXISTS idx_timeline_seq ON timeline_events(sequence_hint);
```

**New SQLite functions:** `upsert_timeline_events()`, `get_full_timeline()`, `detect_timeline_gaps()`

**Cost.** Zero. Regex-only extraction.

**Complexity.** Low-medium.

**Future extension.** Author-defined calendar anchor (e.g. "The Bellwarren Siege = Year 5, Day 47") to resolve relative tags.

---

### Feature 4: Relationship Graphs

**Purpose.** Characters are extracted per chunk but there's no cross-chunk co-occurrence tracking. This builds a character co-occurrence table: every pair of PERSON entities appearing in the same chunk gets a row.

**Integration.** New function `entity_extractor.extract_cooccurrences()`. Called from `incremental.index_chapter()` after entity insertion. Results written to new `character_cooccurrences` table.

**Also add here:** `known_characters`, `known_places`, `known_orgs` lists in `config.yaml`. The entity extractor checks these first before spaCy — critical because spaCy misses fantasy names like "Ven".

```yaml
# config.yaml addition
entities:
  known_characters: ["Ven", "Rho", "Thorn", "Boc", "Aveline"]
  known_places:     ["Bellwarren", "Harrowgate", "Stalgrad", "Ulun"]
  known_orgs:       ["Silver Oath", "Ashwing"]
```

**Schema additions:**
```sql
CREATE TABLE IF NOT EXISTS character_cooccurrences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a        TEXT NOT NULL,   -- alphabetically first
    entity_b        TEXT NOT NULL,   -- alphabetically second
    chapter_slug    TEXT NOT NULL REFERENCES chapters(slug) ON DELETE CASCADE,
    chunk_id        TEXT NOT NULL,
    chapter_idx     INTEGER NOT NULL,
    chunk_index     INTEGER NOT NULL,
    UNIQUE(chunk_id, entity_a, entity_b)
);
CREATE INDEX IF NOT EXISTS idx_cooc_pair ON character_cooccurrences(entity_a, entity_b);
CREATE INDEX IF NOT EXISTS idx_cooc_entity_a ON character_cooccurrences(entity_a);
CREATE INDEX IF NOT EXISTS idx_cooc_entity_b ON character_cooccurrences(entity_b);
```

**New SQLite functions:** `upsert_cooccurrences()`, `get_cooccurrences_for_entity()`, `get_relationship_summary()`, `get_most_connected_characters()`

**Cost.** Zero. Pure Python pair extraction.

**Complexity.** Low.

**Future extension.** Force-directed graph visualization in the Streamlit UI using `streamlit-agraph` or Plotly.

---

### Feature 2: Narrative State Tracking

**Purpose.** Author asks: "What does Ven know at the end of Chapter 4?" Precomputed per-character, per-chapter snapshots answer this deterministically from SQLite without any vector search.

**Integration.** New file `src/processing/state_builder.py`. Called from `incremental.index_chapter()` after the co-occurrence table is updated. For each unique PERSON entity, writes one row per chapter into `narrative_states` capturing: appearance count, first/last chapter seen, known associates (co-occurring characters up to that chapter), and source chunk IDs.

New function `query_engine.character_state_query(character, as_of_chapter_idx)` returns the snapshot plus 3 most recent relevant passages.

**Schema additions:**
```sql
CREATE TABLE IF NOT EXISTS narrative_states (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text             TEXT NOT NULL,
    entity_type             TEXT NOT NULL,
    as_of_chapter_idx       INTEGER NOT NULL,
    first_seen_chapter_idx  INTEGER,
    last_seen_chapter_idx   INTEGER,
    appearance_count        INTEGER DEFAULT 0,
    known_associates        TEXT DEFAULT "",   -- comma-sep names
    source_chunk_ids        TEXT DEFAULT "",   -- comma-sep chunk_ids
    UNIQUE(entity_text, as_of_chapter_idx)
);
CREATE INDEX IF NOT EXISTS idx_ns_entity ON narrative_states(entity_text COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_ns_chapter ON narrative_states(as_of_chapter_idx);
```

**New files.** `src/processing/state_builder.py`

**Cost.** Zero. Pure computation from existing SQLite data.

**Complexity.** Medium. Snapshot logic must correctly handle incremental chapter ordering.

**Risk.** spaCy misses fantasy proper nouns — mitigated by `known_characters` list in Phase 2.

**MVP.** PERSON entities only, manuscript chapters only.

**Future extension.** PLACE/ORG entities. Per-chapter "what changed" diff view.

---

### Feature 6: Story Health Dashboard

**Purpose.** New Streamlit page giving the author a visual overview: chapter coverage, character appearance frequency, timeline events, co-occurrence summary, lore tag density.

**Integration.** New file `ui/pages/1_Story_Health.py`. Multi-page Streamlit is enabled automatically by the `pages/` subdirectory. Existing `ui/app.py` becomes Page 1 (Search). No changes to `app.py` required.

All data sourced from SQLite. No ChromaDB queries, no embedding calls.

**Sections:**
1. `st.metric()` cards: total chunks, novel chapters, characters tracked, timeline events
2. Character appearance bar chart (Plotly, top 10 characters, x=chapter, y=count)
3. Chapter overview table (title, chunk count, indexed date)
4. Timeline events panel (sorted list, gaps flagged)
5. Co-occurrence top-15 table

**New file.** `ui/theme.py` — extracts the dark fantasy CSS from `app.py` into a shared constant imported by all pages.

**New SQLite functions:** `get_entity_appearances_by_chapter()`, `get_lore_tag_counts_by_chapter()`

**Cost.** Zero.

**Complexity.** Medium (Plotly chart setup).

**MVP.** Chapter table + character chart only.

---

### Feature 7: Retrieval Explainability

**Purpose.** Each search result shows WHY it was retrieved: cosine score, matched entity names, source type, confidence breakdown.

**Integration.** Extend `scorer.py` to return a breakdown dict alongside the score. Add `format_confidence_breakdown(breakdown)` to `formatters.py` producing a one-liner: `"Match: 87% similarity · 2 shared characters (Ven, Thorn) · Novel source"`. Add a `st.expander("Why this result?")` to `ui/app.py` under each result card. Add optional `explanation` field to `AskResponse` in `server.py` (off by default to keep GPT context compact).

**Schema changes.** None.

**New files.** None. Modifications to `scorer.py`, `formatters.py`, `server.py`, `app.py`.

**Cost.** Zero.

**Complexity.** Low (breakdown is computed as a byproduct of Feature 5).

---

### Feature 8: Auto Lore Wiki Generation

**Purpose.** For each major character, location, and faction: a wiki entry showing aggregated relevant passages ordered by chapter. Optional LLM-generated one-paragraph summary.

**Integration.** New file `src/processing/wiki_builder.py`. New script `scripts/build_wiki.py`. New UI page `ui/pages/2_Lore_Wiki.py`.

The wiki builder: queries `entities` table for all entities with ≥ 3 appearances, fetches their chunk texts from ChromaDB by ID (batch get), serializes as JSON into `wiki_entries.raw_passages`. LLM summary is optional and manually triggered.

**LLM summary cost (gpt-4o-mini, optional):**
- ~1,500 input tokens + ~200 output tokens per entity
- 50 entities: ~$0.02 total for a full rebuild
- Per-entity on-demand: < $0.001

**Schema additions:**
```sql
CREATE TABLE IF NOT EXISTS wiki_entries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    subject             TEXT NOT NULL UNIQUE,
    subject_type        TEXT NOT NULL,       -- "character" | "place" | "org" | "lore"
    summary             TEXT,                -- NULL until generated
    raw_passages        TEXT NOT NULL DEFAULT "[]",  -- JSON array
    appearance_count    INTEGER DEFAULT 0,
    first_chapter_idx   INTEGER,
    last_chapter_idx    INTEGER,
    last_generated      TEXT,                -- ISO datetime or NULL
    UNIQUE(subject)
);
CREATE INDEX IF NOT EXISTS idx_wiki_type ON wiki_entries(subject_type);
```

**New files.** `src/processing/wiki_builder.py`, `scripts/build_wiki.py`, `ui/pages/2_Lore_Wiki.py`

**Complexity.** Medium (ChromaDB batch fetch by ID, JSON serialization).

**MVP.** Raw passages only (`--with-summaries` flag off by default).

---

## Schema Evolution Summary

All additions go into existing `data/novel.db`. Added to `_SCHEMA` in `sqlite_store.py` as `CREATE TABLE IF NOT EXISTS` — existing installs are not broken.

**New tables:** `timeline_events`, `character_cooccurrences`, `narrative_states`, `wiki_entries`

**Existing table fix:**
```sql
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'manuscript';
```

---

## Token/Cost Impact Analysis

| Feature | Per-query cost | Per-reindex cost | Notes |
|---|---|---|---|
| Feature 1 (citations) | $0.000 | $0.000 | Formatting only |
| Feature 5 (confidence) | ~$0.000 | $0.000 | 5ms spaCy call |
| Feature 3 (timeline) | $0.000 | $0.000 | Regex only |
| Feature 4 (relationships) | $0.000 | $0.000 | Python pair logic |
| Feature 2 (state tracking) | $0.000 | $0.000 | SQLite aggregates |
| Feature 6 (dashboard) | $0.000 | $0.000 | SQLite reads |
| Feature 7 (explainability) | $0.000 | $0.000 | Byproduct of Feature 5 |
| Feature 8 (wiki, raw) | $0.000 | $0.000 | ChromaDB batch fetch |
| Feature 8 (wiki, summaries) | $0.000 | ~$0.02 max | Manual trigger only |

**Net new monthly cost: ~$0.00 for 95% of usage.**

---

## Complexity/Risk Analysis

| Feature | Complexity | Risk | Key concern |
|---|---|---|---|
| Feature 1 | Low | Low | None |
| Feature 5 | Low | Low | None |
| Feature 3 | Low-Med | Low | sequence_hint mapping edge cases |
| Feature 4 | Low | Low | None |
| Feature 2 | Medium | Medium | spaCy misses fantasy names — mitigated by known_characters list |
| Feature 6 | Medium | Low | Plotly chart setup is fiddly |
| Feature 7 | Low | Low | None |
| Feature 8 | Medium | Low | ChromaDB batch-by-ID API shape |

---

## Updated Architecture Diagram

```
Google Docs API (tabs)            continuity_docs/ (DOCX/PDF)
  └→ google_docs.py                   └→ doc_reader.py
       └→ converter.py                      │
            └→ chunker.py ←────────────────┘
                 └→ metadata_extractor.py   [pov, timeline_structured, lore_tags (filtered)]
                 └→ entity_extractor.py     [PERSON/PLACE/ORG + cooccurrences]
                 └→ embedder.py (OpenAI + cache)
                      │
          ┌───────────┼───────────────────────┐
          ↓           ↓                       ↓
    ChromaDB      SQLite novel.db       state_builder.py
    "manuscript"  ┌─────────────┐       (Phase 3 enrichment)
    ~5,832 chunks │ chapters    │
    + metadata    │ entities    │
                  │ sync_log    │
                  │ timeline_events        ← Phase 2
                  │ character_cooccurrences ← Phase 2
                  │ narrative_states       ← Phase 3
                  │ wiki_entries           ← Phase 4
                  └─────────────┘
                        │
          ┌─────────────┤
          ↓             ↓
    query_engine.py    wiki_builder.py
    scorer.py          (scripts/build_wiki.py)
    formatters.py
          │
    ┌─────┴──────────────┐
    ↓                    ↓
ui/app.py           api/server.py
(Search)            (FastAPI /ask)
ui/pages/                ↓
  1_Story_Health.py  ngrok tunnel
  2_Lore_Wiki.py         ↓
                    Custom GPT
```

---

## Proposed Directory Structure

```
inherited-cloud/
├── config.yaml                         ← + scoring weights, known_characters/places/orgs
├── src/
│   ├── processing/
│   │   ├── chunker.py
│   │   ├── converter.py
│   │   ├── doc_reader.py
│   │   ├── entity_extractor.py         ← + extract_cooccurrences(), known-entity override
│   │   ├── metadata_extractor.py       ← + extract_timeline_structured(), expanded stopwords
│   │   ├── state_builder.py            ← NEW (Phase 3)
│   │   └── wiki_builder.py             ← NEW (Phase 4)
│   ├── indexing/
│   │   ├── embedder.py
│   │   ├── incremental.py              ← + timeline, cooccurrence, state calls
│   │   ├── sqlite_store.py             ← + 4 new tables + new query functions
│   │   └── vector_store.py
│   ├── retrieval/
│   │   ├── query_engine.py             ← + character_state_query(), timeline_query()
│   │   ├── formatters.py               ← + format_for_chatgpt_with_citations(), breakdown formatter
│   │   └── scorer.py                   ← NEW (Phase 1)
│   └── sync/, utils/                   (unchanged)
├── ui/
│   ├── app.py                          ← + confidence display, "Why this result?" expander
│   ├── theme.py                        ← NEW: shared CSS
│   └── pages/
│       ├── 1_Story_Health.py           ← NEW (Phase 3)
│       └── 2_Lore_Wiki.py              ← NEW (Phase 4)
├── api/
│   └── server.py                       ← + citation keys, optional explanation field
├── scripts/
│   ├── sync_and_index.py
│   ├── ingest_documents.py
│   ├── full_reindex.py
│   ├── build_wiki.py                   ← NEW (Phase 4)
│   └── query.py
├── deploy/
│   └── custom_gpt/
│       └── system_prompt.md            ← + citation format instructions
└── data/
    ├── chroma_db/
    ├── novel.db                        ← + 4 new tables
    └── ...
```

---

## Testing Strategy

**After Phase 1:**
- `python scripts/query.py "what does Ven know about the Magelord"` — confirm results have both `score` and `confidence` fields
- Call `/ask` endpoint — confirm every passage in `context_block` has a `[C{n}-P{n}]` key

**After Phase 2:**
- `SELECT COUNT(*) FROM timeline_events` > 0; spot-check "Year 3" → `sequence_hint=3.0`
- `SELECT entity_a, entity_b, COUNT(*) FROM character_cooccurrences GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5` — top pairs should make narrative sense
- `source_type` on novel chunks is now "manuscript" (run query, check metadata)

**After Phase 3:**
- `SELECT * FROM narrative_states WHERE entity_text='Ven' ORDER BY as_of_chapter_idx` — one row per chapter, `appearance_count` monotonically increasing
- Open `http://localhost:8501` — sidebar shows Search, Story Health, Lore Wiki; Story Health renders without error

**After Phase 4:**
- `python scripts/build_wiki.py` — no errors; `SELECT COUNT(*) FROM wiki_entries` > 0
- Open Lore Wiki page, find "Ven", confirm passage list renders
- Run LLM summary for one entity only, confirm cost < $0.001

**Regression (after every phase):**
1. `python scripts/query.py --stats` — chunk count unchanged
2. `python scripts/query.py "Ven at Bellwarren"` — results still return
3. Start API, hit `/health` — 200 OK

---

## Hallucination Evaluation Strategy

Create `data/eval_questions.json` — 10–15 questions answerable from the manuscript text:

```json
[
  {"question": "What is Ven's relationship to the Magelord?", "verifiable_in": ["ch02", "ch04"]},
  {"question": "Where does the Silver Oath first appear?", "verifiable_in": ["ch00"]},
  {"question": "Who fights in the opening scene?", "verifiable_in": ["ch00"]}
]
```

**Baseline (before Phase 1):** Record citation rate (does GPT cite a chapter?), citation accuracy (is the cited chapter correct?), and hallucination rate (does GPT add details absent from retrieved passages?).

**After Phase 1:** Expected citation rate: >90% (was ~60%). Run same 15 questions.

**After Phase 3:** For temporal questions ("What does X know at end of Chapter N?"), check GPT answer against `narrative_states` row. Correct = matches precomputed snapshot.

**Ongoing:** `data/eval_questions.json` grows as the author catches errors. Run manually after any reindex. Takes ~15 minutes. No automation needed.

---

## Implementation Checklist

### Phase 1
- [x] `src/retrieval/scorer.py` — multi-factor confidence scoring
- [x] `query_engine.py` — wire `score_results()` into `semantic_search()`
- [x] `config.yaml` — add `retrieval.scoring` weights section
- [x] `formatters.py` — add `format_for_chatgpt_with_citations()`
- [x] `server.py` — use citation formatter; add `citation_key` to passage objects
- [x] `deploy/custom_gpt/system_prompt.md` — add citation format section

### Phase 2
- [x] `config.yaml` — add `entities.known_characters/places/orgs`
- [x] `metadata_extractor.py` — `extract_timeline_structured()`; expand stopwords to ~50
- [x] `entity_extractor.py` — known-entity override; `extract_cooccurrences()`
- [x] `sqlite_store.py` — add `timeline_events` and `character_cooccurrences` DDL; new query functions
- [x] `incremental.py` — wire in timeline and co-occurrence calls
- [x] `full_reindex.py --yes` — rebuild with new tables and fix `source_type` bug

### Phase 3
- [x] `sqlite_store.py` — add `narrative_states` DDL; new query functions
- [x] `src/processing/state_builder.py` — NEW
- [x] `incremental.py` — wire in state builder call
- [x] `ui/theme.py` — NEW: extract shared CSS
- [x] `ui/pages/1_Story_Health.py` — NEW: chapter table + character chart
- [x] `scorer.py` — extend to return breakdown dict
- [x] `formatters.py` — add `format_confidence_breakdown()`
- [x] `ui/app.py` — add "Why this result?" expander

### Phase 4
- [ ] `sqlite_store.py` — add `wiki_entries` DDL
- [ ] `src/processing/wiki_builder.py` — NEW
- [ ] `scripts/build_wiki.py` — NEW
- [ ] `ui/pages/2_Lore_Wiki.py` — NEW
