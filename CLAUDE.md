# Inherited Cloud — Project Handoff

> **For Claude:** At the start of any session involving code changes, read `TECHNICAL_REFERENCE.md` (function signatures, schemas, data flow) and `ROADMAP.md` (8-feature plan with per-phase checklists). Reading these two files replaces crawling the source files.

## What this is

A semantic search and retrieval system for a fantasy novel manuscript. The author writes in Google Docs (using Tabs for chapters). This system indexes the manuscript and a corpus of old D&D campaign continuity documents, then serves semantic search via a Streamlit browser UI and a FastAPI endpoint for a Custom GPT.

**Author:** Non-technical. Should never touch code.
**Chase's role:** Maintains the system, handles fixes or upgrades. The server runs 24/7 on a VPS — no manual start needed.

---

## Current state (as of 2026-05-28) — Phases 1–3 complete + VPS deployed

### What is fully working
- Google Docs API sync (tabs-based — each tab = one chapter)
- Full manuscript indexed: 11 chapters, 125 chunks
- Continuity docs indexed: 8 of 10 files, ~3,829 chunks (2 PDFs still failing — see Known issues)
- Semantic search via ChromaDB + OpenAI `text-embedding-3-small`
- spaCy entity extraction with canonicalization: `known_*` lists in `config.yaml` are ground truth and override spaCy labels; includes `entity_blocklist` for junk tokens
- SQLite metadata store with 5 tables: `chapters`, `entities`, `timeline_events`, `character_cooccurrences`, `narrative_states`
- Streamlit multi-page UI: Search page + Story Health dashboard
- Dark fantasy theme (Cinzel/Crimson Text fonts, gold/charcoal palette) — shared via `ui/theme.py`; widget styling (selects, radios, multiselects) via `.streamlit/config.toml` + CSS
- FastAPI `/ask` endpoint with citation keys (`[C{n}-P{n}]`) for Custom GPT
- Custom GPT system prompt + author setup guide
- IONOS VPS running 24/7 at `novel.talos-advisory.com` (Cloudflare proxied, HTTPS)
- API live at `https://novel.talos-advisory.com/api` — no ngrok or Chase's machine required
- Nightly manuscript sync via cron at 3am CT on the VPS
- Windows `.bat` launchers: `START_SEARCH.bat` and `START_WITH_CHATGPT.bat` (local use only)
- Author-facing Custom GPT setup guide: `deploy/windows/AUTHOR_SETUP_VPS.md`
- Embedding cache (SQLite) — repeated queries don't re-call OpenAI
- "More like this" button on result cards
- Character/place multiselect filters in UI
- Last synced timestamp shown in sidebar
- Multi-factor confidence scoring (`src/retrieval/scorer.py`) — cosine + entity overlap + source weight + narrative position
- "Why this result?" expander on every search result card
- Timeline events table with sequence hints and gap detection
- Character co-occurrence table (which characters appear in the same chunk)
- Narrative state snapshots: per-character, per-chapter cumulative view (populated on next reindex)
- Story Health dashboard: character appearances, character arcs table (with sort/filter controls), co-occurrence heatmap, place density, timeline strip, entity composition, chapter overview
- All Story Health queries filtered to manuscript chapters only (`slug LIKE 'ch%'`)
- `known_lore` list in `config.yaml` catches world-specific common words used as proper nouns (e.g. "Working", "Workings", "Myth")
- `ingest_documents.py` processes each file in an isolated subprocess — prevents memory accumulation across files on the 1GB VPS

### What is NOT yet done
- Phase 4: Lore wiki (`wiki_entries` table, `wiki_builder.py`, `2_Lore_Wiki.py` page)
- Narrative states table is empty until the next full reindex populates it

### Known issues / gotchas
- PDF reading uses PyMuPDF (`fitz`), not pdfplumber — pdfplumber used ~478MB RAM per file and crashed the VPS. PyMuPDF is installed in the venv; do not revert.
- `Ven Transcript Part 6.docx` was empty — skipped at ingestion, not a bug
- Windows terminal (cp1252) cannot print some Unicode from the manuscript — fixed in `scripts/query.py` but raw `python -c` one-liners will still fail; use the scripts
- Background Bash tasks in Claude Code are slow to flush output — use `run_in_background=true` and wait for task-notification rather than polling
- After adding new `known_characters`, `known_places`, `known_orgs`, or `known_lore` entries to `config.yaml`, a full reindex is needed to pick them up across existing chunks
- When pushing code changes to the VPS, copy updated files via `scp` and restart the affected service (`systemctl restart novel-api` or `novel-ui`)
- **Full reindex on the VPS requires stopping services first** — the VPS has 826MB usable RAM; running a reindex with services up causes OOM kills. Always `systemctl stop novel-ui novel-api` before reindexing, then `systemctl start` after. See the reindex procedure below.
- **Never run `full_reindex.py` and `ingest_documents.py` simultaneously** — they will OOM the server. Always wait for the first to finish before starting the second.

---

## How the author uses this (plain English)

There are two ways the author can interact with the system:

### Option A — Streamlit UI (Chase's machine)
Chase double-clicks `START_SEARCH.bat`. A browser opens on Chase's machine at `http://localhost:8501`. The author can use it if Chase shares his screen, or Chase can run queries on his behalf.

### Option B — Custom GPT (author's own ChatGPT)
This is the main intended workflow. The author has a Custom GPT called "Chronicles of Ven" in his ChatGPT account. He opens ChatGPT, clicks Chronicles of Ven, and types his question. No coordination with Chase needed — the API runs 24/7 on the VPS.

The Custom GPT is set up once using `deploy/windows/AUTHOR_SETUP_VPS.md`. As of 2026-05-27 Zach has not yet done this setup.

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
| `src/retrieval/scorer.py` | Multi-factor confidence scoring; adds `confidence` + `confidence_breakdown` to results |
| `src/retrieval/formatters.py` | Result formatters incl. citation formatter and `format_confidence_breakdown()` |
| `src/processing/state_builder.py` | Builds `narrative_states` snapshots after each chapter index |
| `ui/theme.py` | Shared dark fantasy CSS constant imported by all Streamlit pages |
| `ui/pages/1_Story_Health.py` | Story Health dashboard page |
| `scripts/setup.py` | One-time first-run setup |
| `scripts/sync_and_index.py` | Nightly sync with burst mode |
| `scripts/ingest_documents.py` | One-time (or on-demand) continuity doc ingestion |
| `scripts/full_reindex.py` | Wipe and rebuild manuscript index |
| `ui/app.py` | Streamlit author UI |
| `api/server.py` | FastAPI server (`/ask` endpoint for Custom GPT) |
| `deploy/windows/START_SEARCH.bat` | Double-click: starts API + Streamlit UI |
| `deploy/windows/START_WITH_CHATGPT.bat` | Double-click: starts API + UI + ngrok tunnel (local fallback only) |
| `deploy/windows/AUTHOR_SETUP_VPS.md` | One-time Custom GPT setup guide for the author (send this to Zach) |
| `deploy/windows/AUTHOR_SETUP.md` | Old ngrok-based setup guide — superseded, kept for reference |
| `deploy/custom_gpt/system_prompt.md` | The GPT's instruction set |

---

## Common tasks

### Start local UI (Chase's machine only — for screen-share sessions)
Double-click `deploy/windows/START_SEARCH.bat`

### Check VPS service health
```
ssh root@216.250.112.169
systemctl status novel-api novel-ui
```

### Restart a VPS service (after deploying a code change)
```
ssh root@216.250.112.169
systemctl restart novel-api   # or novel-ui
```

### Push a code change to the VPS
```powershell
# From project root on Windows — example pushing src/ and api/ after a code change
scp -r src api root@216.250.112.169:/opt/inherited-cloud/
ssh root@216.250.112.169 "systemctl restart novel-api"
```

### Trigger a manual sync on the VPS
```
ssh root@216.250.112.169
sudo -u novel /opt/inherited-cloud/.venv/bin/python /opt/inherited-cloud/scripts/sync_and_index.py
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

### Force full reindex on the VPS (preferred — server runs 24/7)
**Always stop services first.** The VPS has 826MB RAM — reindexing with services up will OOM.
```bash
ssh root@216.250.112.169
systemctl stop novel-ui novel-api
cd /opt/inherited-cloud
sudo -u novel .venv/bin/python scripts/full_reindex.py --yes
sudo -u novel .venv/bin/python scripts/ingest_documents.py --reindex-all
systemctl start novel-ui novel-api
```
Wait for `full_reindex.py` to fully exit before starting `ingest_documents.py`. The site will be down during this (~15–20 minutes). 

**Note:** `full_reindex.py` wipes the entire ChromaDB collection (manuscript + continuity). You must follow it with `ingest_documents.py --reindex-all` or the continuity docs will be missing.

### Force full manuscript reindex (local machine)
```
.venv\Scripts\activate
python scripts/full_reindex.py --yes
python scripts/ingest_documents.py --reindex-all
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

## VPS / Custom GPT

- **VPS:** IONOS VPS XS — IP `216.250.112.169`
- **Hardware:** 1 vCore, 826MB usable RAM, 10GB NVMe SSD, **1GB swap** at `/swapfile` (added 2026-05-28)
- **Domain:** `novel.talos-advisory.com` (Cloudflare proxied, HTTPS)
- **API base URL:** `https://novel.talos-advisory.com/api`
- **OpenAPI schema URL:** `https://novel.talos-advisory.com/api/openapi.json`
- **Author's Custom GPT name:** Chronicles of Ven (setup not yet done as of 2026-05-27)
- **Author setup guide:** `deploy/windows/AUTHOR_SETUP_VPS.md`
- The API runs 24/7 — no action from Chase needed for Zach to use it
- Nightly sync cron runs at 3am CT as the `novel` user

---

## Google Cloud setup (for reference)

- Project: "Zach Novel"
- APIs enabled: Google Docs API, Google Drive API
- OAuth client: Desktop app type
- Test user: chase.burns33@gmail.com
- Scopes: `documents.readonly`, `drive.readonly`

---

## VPS deployment notes

The VPS was provisioned on 2026-05-27. Key gotcha encountered during setup:
`provision.sh` uses `set -euo pipefail` and exited early when `python3.11` wasn't
found in the default Ubuntu 22.04 apt repos. This meant the `novel` user and nginx
were never created by the script. Fix applied manually:

```bash
add-apt-repository ppa:deadsnakes/ppa -y && apt-get update && apt-get install -y python3.11 python3.11-venv python3-pip
useradd -r -m -s /bin/bash novel
apt-get install -y nginx
```

If reprovisioning from scratch, add the deadsnakes PPA step to `provision.sh` before
the Python install line.
