# Inherited Cloud — Project Handoff

## What this is

A semantic search and retrieval system for a fantasy novel manuscript. The author writes in Google Docs (using Tabs for chapters). This system indexes the manuscript and a corpus of old D&D campaign continuity documents, then serves semantic search via a Streamlit browser UI and a FastAPI endpoint for ChatGPT.

**Author:** Non-technical. Should never touch code.
**Chase's role:** Maintains the system, handles any fixes or upgrades.

---

## Current state (as of 2026-05-21)

### What is fully working
- Google Docs API sync (tabs-based — each tab = one chapter)
- Full manuscript indexed: 9 chapters, 92 chunks
- Continuity docs indexed: 9 files, 5,714 chunks (~5,800 total)
- Semantic search via ChromaDB + OpenAI `text-embedding-3-small`
- spaCy entity extraction (characters, places)
- SQLite metadata store
- Streamlit UI with source filter (Novel / Continuity / Worldbuilding / All)
- FastAPI query endpoint
- CLI query tool (`scripts/query.py`)

### What is NOT yet done
- Windows Task Scheduler setup (auto-sync at 3am) — Phase 6
- `.bat` launcher files for the author — Phase 6
- Author handoff guide (`deploy/windows/HANDOFF.md`) — Phase 6
- Continuity doc ingestion may need re-run when author provides updated files

### Known issues / gotchas
- `Ven Transcript Part 6.docx` was empty — skipped, not a bug
- Windows terminal (cp1252) cannot print some Unicode from the manuscript — fixed in `scripts/query.py` but raw `python -c` one-liners will still fail; use the scripts
- Background Bash tasks in Claude Code are slow to flush output — use `run_in_background=true` and wait for task-notification rather than polling

---

## Architecture

```
Google Docs API (tabs) → fetch_doc_as_json() → docs_json_to_chapters()
                                                        ↓
continuity_docs/ (DOCX/PDF) → doc_reader.py ──────→ chunker.py
                                                        ↓
                                              metadata_extractor.py
                                              entity_extractor.py (spaCy)
                                                        ↓
                                              embedder.py (OpenAI)
                                                        ↓
                                    ChromaDB ←──── vector_store.py
                                    SQLite   ←──── sqlite_store.py
                                                        ↓
                                              query_engine.py
                                              ↙            ↘
                                       ui/app.py      api/server.py
                                    (Streamlit)       (FastAPI)
```

---

## Key files

| File | Purpose |
|---|---|
| `config.yaml` | All runtime config — chunk size, doc ID, model, ports |
| `.env` | `OPENAI_API_KEY` and optionally `GOOGLE_DOC_ID` |
| `credentials.json` | Google OAuth Desktop client (never commit) |
| `token.json` | Google OAuth token — auto-refreshed, never delete |
| `src/sync/google_docs.py` | Fetches doc via Docs API with `includeTabsContent=True` |
| `src/processing/converter.py` | Parses tabs into Chapter objects |
| `src/processing/doc_reader.py` | Reads DOCX/PDF for continuity ingestion |
| `src/indexing/vector_store.py` | ChromaDB wrapper |
| `src/indexing/sqlite_store.py` | SQLite for structured metadata |
| `src/retrieval/query_engine.py` | `semantic_search()` + `entity_search()` |
| `scripts/setup.py` | One-time first-run setup |
| `scripts/sync_and_index.py` | Nightly sync with burst mode |
| `scripts/ingest_documents.py` | One-time (or on-demand) continuity doc ingestion |
| `scripts/full_reindex.py` | Wipe and rebuild manuscript index |
| `ui/app.py` | Streamlit author UI |
| `api/server.py` | FastAPI server |

---

## Common tasks

### Start the author UI
```
.venv\Scripts\activate
streamlit run ui/app.py
```

### Start the API server
```
.venv\Scripts\activate
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### Manually trigger a manuscript sync
```
.venv\Scripts\activate
python scripts/sync_and_index.py
```

### Re-ingest continuity docs (when author adds/updates files)
Drop updated files into `continuity_docs/`, then:
```
.venv\Scripts\activate
python scripts/ingest_documents.py
```
Unchanged files are skipped automatically. Use `--reindex-all` to force full rebuild.

### Force full manuscript reindex
```
python scripts/full_reindex.py --yes
```

### Test retrieval from CLI
```
python scripts/query.py "find all passages about the Blackened War"
python scripts/query.py "Ven" --entity
python scripts/query.py --stats
python scripts/query.py --chapters
```

---

## Data locations

| Path | Contents |
|---|---|
| `data/raw/manuscript.json` | Latest Google Docs API response |
| `data/markdown/` | Per-chapter .md files |
| `data/chroma_db/` | ChromaDB vector store |
| `data/novel.db` | SQLite metadata |
| `data/sync_state.json` | Last sync timestamp + chapter hashes |
| `data/continuity_state.json` | File hashes for continuity docs |
| `data/sync.log` | Sync/indexing log |
| `continuity_docs/` | Local DOCX/PDF continuity documents |

---

## Source types in the index

| `source_type` | Description |
|---|---|
| `manuscript` | Chunks from the Google Doc (the novel) |
| `continuity` | Chunks from old campaign documents |
| `worldbuilding` | Chunks from Ulun World Building.docx |

Subtypes (`doc_subtype`): `handoff`, `transcript`, `story`, `worldbuilding`, `unknown`

---

## Remaining work (Phase 6)

1. **Windows Task Scheduler** — register `sync_and_index.py` to run at 3am CT daily
   - Script goes in `deploy/windows/setup_task.ps1`
   - Run once as admin to register the task
2. **Launcher .bat files** — double-click to start UI/API without touching terminal
   - `deploy/windows/start_ui.bat`
   - `deploy/windows/start_api.bat`
3. **Author handoff guide** — plain English, no code
   - `deploy/windows/HANDOFF.md`

---

## Google Cloud setup (for reference)

- Project: "Zach Novel"
- APIs enabled: Google Docs API, Google Drive API
- OAuth client: Desktop app type
- Test user: chase.burns33@gmail.com
- Scopes: `documents.readonly`, `drive.readonly`

---

## Deployment note

Currently running locally on Chase's machine. When handing off to the author's machine:
1. Copy entire project folder
2. Run `deploy/windows/provision.bat` (to be created in Phase 6)
3. Run `scripts/setup.py` (will re-auth Google on his machine)
4. Run `scripts/ingest_documents.py` for continuity docs
5. Register Task Scheduler job via `deploy/windows/setup_task.ps1`
