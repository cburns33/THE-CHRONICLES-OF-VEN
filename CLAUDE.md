# Inherited Cloud — Project Handoff

## What this is

A semantic search and retrieval system for a fantasy novel manuscript. The author writes in Google Docs (using Tabs for chapters). This system indexes the manuscript and a corpus of old D&D campaign continuity documents, then serves semantic search via a Streamlit browser UI and a FastAPI endpoint for a Custom GPT.

**Author:** Non-technical. Should never touch code.
**Chase's role:** Maintains the system, handles fixes or upgrades, runs the server when the author wants to use it.

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
- Dark fantasy theme (Cinzel/Crimson Text fonts, gold/charcoal palette)
- FastAPI `/ask` endpoint optimised for Custom GPT Actions
- Custom GPT system prompt + author setup guide
- ngrok static domain locked in: `tarot-seltzer-ought.ngrok-free.dev`
- Windows `.bat` launchers: `START_SEARCH.bat` and `START_WITH_CHATGPT.bat`
- Author-facing Custom GPT setup guide: `deploy/windows/AUTHOR_SETUP.md`
- Embedding cache (SQLite) — repeated queries don't re-call OpenAI
- "More like this" button on result cards
- Character/place multiselect filters in UI
- Last synced timestamp shown in sidebar

### What is NOT yet done
- Windows Task Scheduler setup (auto-sync at 3am CT) — still manual for now
- Continuity doc ingestion may need re-run when author locates more old files

### Known issues / gotchas
- `Ven Transcript Part 6.docx` was empty — skipped at ingestion, not a bug
- Windows terminal (cp1252) cannot print some Unicode from the manuscript — fixed in `scripts/query.py` but raw `python -c` one-liners will still fail; use the scripts
- ngrok free tier: the static domain (`tarot-seltzer-ought.ngrok-free.dev`) is permanent but ngrok must be running on Chase's machine for the Custom GPT to work
- Background Bash tasks in Claude Code are slow to flush output — use `run_in_background=true` and wait for task-notification rather than polling

---

## How the author uses this (plain English)

There are two ways the author can interact with the system:

### Option A — Streamlit UI (Chase's machine)
Chase double-clicks `START_SEARCH.bat`. A browser opens on Chase's machine at `http://localhost:8501`. The author can use it if Chase shares his screen, or Chase can run queries on his behalf.

### Option B — Custom GPT (author's own ChatGPT)
This is the main intended workflow. The author has a Custom GPT called "Chronicles of Ven" in his ChatGPT account. When he wants to use it:

1. He texts Chase
2. Chase double-clicks `START_WITH_CHATGPT.bat` (starts API + ngrok tunnel, takes ~30 seconds)
3. Chase texts back "ready"
4. The author opens ChatGPT, clicks Chronicles of Ven, and types his question
5. The GPT silently searches the manuscript, then answers with sourced passages
6. Chase can close it when the author is done

The author's Custom GPT was set up once using `deploy/windows/AUTHOR_SETUP.md` and never needs to be touched again, as long as the ngrok static domain stays the same (it will — it's permanent).

**What the author does NOT need to do:** install anything, run any commands, touch any files, or understand how any of it works. He just opens ChatGPT.

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
                                              embedder.py (OpenAI + cache)
                                                        ↓
                                    ChromaDB ←──── vector_store.py
                                    SQLite   ←──── sqlite_store.py
                                                        ↓
                                              query_engine.py
                                              ↙            ↘
                                       ui/app.py      api/server.py
                                    (Streamlit)       (FastAPI /ask)
                                                            ↓
                                                    ngrok static tunnel
                                                            ↓
                                                   Custom GPT Action
                                                  (author's ChatGPT)
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
| `src/indexing/embedder.py` | OpenAI embeddings with SQLite query cache |
| `src/indexing/vector_store.py` | ChromaDB wrapper |
| `src/indexing/sqlite_store.py` | SQLite for structured metadata |
| `src/retrieval/query_engine.py` | `semantic_search()`, `entity_search()`, `more_like_this()` |
| `scripts/setup.py` | One-time first-run setup |
| `scripts/sync_and_index.py` | Nightly sync with burst mode |
| `scripts/ingest_documents.py` | One-time (or on-demand) continuity doc ingestion |
| `scripts/full_reindex.py` | Wipe and rebuild manuscript index |
| `ui/app.py` | Streamlit author UI |
| `api/server.py` | FastAPI server (`/ask` endpoint for Custom GPT) |
| `deploy/windows/START_SEARCH.bat` | Double-click: starts API + Streamlit UI |
| `deploy/windows/START_WITH_CHATGPT.bat` | Double-click: starts API + UI + ngrok tunnel |
| `deploy/windows/AUTHOR_SETUP.md` | One-time Custom GPT setup guide for the author |
| `deploy/custom_gpt/system_prompt.md` | The GPT's instruction set |

---

## Common tasks

### Start everything (UI + ChatGPT support)
Double-click `deploy/windows/START_WITH_CHATGPT.bat`

### Start UI only (no ChatGPT)
Double-click `deploy/windows/START_SEARCH.bat`

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
.venv\Scripts\activate
python scripts/full_reindex.py --yes
```

### Test retrieval from CLI
```
.venv\Scripts\activate
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
| `data/novel.db` | SQLite metadata + entity index |
| `data/embedding_cache.db` | SQLite cache for query embeddings |
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

## ngrok / Custom GPT

- **Static domain:** `tarot-seltzer-ought.ngrok-free.dev` (permanent, free)
- **OpenAPI schema URL:** `https://tarot-seltzer-ought.ngrok-free.dev/openapi.json`
- **Start tunnel:** `ngrok http 8000 --domain=tarot-seltzer-ought.ngrok-free.dev`
  (handled automatically by `START_WITH_CHATGPT.bat`)
- **Author's Custom GPT name:** Chronicles of Ven (on his ChatGPT Plus account)
- The Custom GPT only works when Chase has the bat file running

---

## Google Cloud setup (for reference)

- Project: "Zach Novel"
- APIs enabled: Google Docs API, Google Drive API
- OAuth client: Desktop app type
- Test user: chase.burns33@gmail.com
- Scopes: `documents.readonly`, `drive.readonly`

---

## Future upgrade path

When/if the author decides the tool is worth $2/month:
1. Spin up IONOS VPS XS (Ubuntu, 1 vCore, 1GB RAM, 10GB NVMe)
2. Run `deploy/provision.sh` on the server
3. Copy project folder to `/opt/inherited-cloud`
4. Run `deploy/setup_venv.sh`
5. Copy `.env`, `credentials.json`, `token.json` to the server
6. Install systemd services: `deploy/install_services.sh`
7. Install cron: `crontab -u novel deploy/crontab.txt`
8. Configure nginx: `deploy/nginx.conf`
9. Update Custom GPT action URL to the VPS IP

Result: everything runs 24/7, no coordination needed, author can use the GPT anytime.
