# Inherited Cloud — Fantasy Novel Retrieval System

A semantic search and retrieval system for a long-form fantasy manuscript.
The manuscript lives in Google Docs. This system keeps a local index updated
automatically and lets you (or ChatGPT) ask questions about it in plain English.

---

## What it does

- Pulls the manuscript from Google Docs automatically every night at 3am
- Detects which chapters changed and re-indexes only those
- Stores vector embeddings locally (no cloud database required)
- Answers queries like:
  - "Find all passages implying the king suspects betrayal"
  - "Which characters know about the Ash Crown?"
  - "Track references to the Silver Oath across the manuscript"
  - "Where was this prophecy foreshadowed?"

---

## Project structure

```
inherited-cloud/
├── config.yaml          ← All settings live here (no code editing needed)
├── .env                 ← API keys (never commit this)
├── scripts/
│   ├── setup.py         ← Run once to set up and index the manuscript
│   ├── sync_and_index.py← Run by cron nightly to keep the index updated
│   ├── query.py         ← CLI for testing queries
│   └── full_reindex.py  ← Wipe and rebuild from scratch
├── api/server.py        ← FastAPI server (for ChatGPT integration)
├── ui/app.py            ← Streamlit browser UI (for the author)
└── deploy/              ← VPS deployment scripts
```

---

## First-time setup (local development / Chase's machine)

### 1. Prerequisites

- Python 3.11+
- A Google Cloud project with the Google Docs and Drive APIs enabled
- An OAuth 2.0 Desktop credentials file (`credentials.json`)
- An OpenAI API key

### 2. Google Cloud setup

1. Go to https://console.cloud.google.com
2. Create a new project (or use an existing one)
3. Enable these two APIs:
   - Google Docs API
   - Google Drive API
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON file and save it as `credentials.json` in the project root

### 3. Configure the project

```bash
# Copy the env template
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

Edit `config.yaml` — find this line and paste your Google Doc ID:
```yaml
google_docs:
  document_id: "YOUR_GOOGLE_DOC_ID_HERE"
```

The Doc ID is in the URL: `https://docs.google.com/document/d/THIS_PART/edit`

### 4. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 5. Run setup (first-time index)

```bash
python scripts/setup.py
```

This will open a browser window to authorise Google access, then index the
entire manuscript. Takes 2–5 minutes depending on manuscript length.

### 6. Test retrieval

```bash
# Semantic search
python scripts/query.py "find all passages mentioning betrayal"

# Filter by character
python scripts/query.py "what does Elric believe about the prophecy" --character Elric

# Entity lookup (which chapters does a name appear in?)
python scripts/query.py "Silver Oath" --entity

# See what's indexed
python scripts/query.py --stats
python scripts/query.py --chapters
```

### 7. Start the interfaces

```bash
# Author UI (browser)
streamlit run ui/app.py

# API server (for ChatGPT)
uvicorn api.server:app --port 8000
```

---

## Deploying to IONOS VPS

### 1. Provision the server

SSH into your VPS and run:
```bash
bash deploy/provision.sh
```

### 2. Copy the project

From your local machine:
```bash
scp -r . root@YOUR_VPS_IP:/opt/inherited-cloud
```

### 3. Set up the Python environment

```bash
ssh root@YOUR_VPS_IP
cd /opt/inherited-cloud
bash deploy/setup_venv.sh
```

### 4. Configure .env on the server

```bash
cp .env.example .env
nano .env    # fill in OPENAI_API_KEY
```

### 5. Run first-time setup

```bash
sudo -u novel /opt/inherited-cloud/.venv/bin/python scripts/setup.py
```

Note: The Google OAuth browser flow won't work headlessly. Run setup
locally first, then copy the generated `token.json` to the VPS:
```bash
scp token.json root@YOUR_VPS_IP:/opt/inherited-cloud/
```

### 6. Install services and cron

```bash
bash deploy/install_services.sh
crontab -u novel deploy/crontab.txt
```

### 7. Configure nginx

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/inherited-cloud
# Edit the file and replace YOUR_VPS_IP_OR_DOMAIN
nano /etc/nginx/sites-available/inherited-cloud
ln -s /etc/nginx/sites-available/inherited-cloud /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

The author can now open `http://YOUR_VPS_IP` in a browser to search the manuscript.

---

## Keeping the index updated

The cron job runs automatically every night at 3am CT. If it detects changes,
it re-checks every 30 minutes for 3 hours (burst mode), then returns to the
daily schedule.

To manually trigger a sync:
```bash
sudo -u novel /opt/inherited-cloud/.venv/bin/python scripts/sync_and_index.py
```

To watch the sync log:
```bash
tail -f /opt/inherited-cloud/data/sync.log
```

---

## Connecting to ChatGPT

Point ChatGPT to your API server:

```
POST http://YOUR_VPS_IP/api/query
Content-Type: application/json

{
  "query": "Find all passages where the king expresses doubt",
  "top_k": 8,
  "format": "chatgpt"
}
```

The `formatted` field in the response is a pre-formatted context block
ready to paste into any ChatGPT conversation.

---

## Tuning

All behaviour is controlled by `config.yaml` — no code changes needed:

| Setting | What it controls |
|---|---|
| `chunking.chunk_size` | How large each indexed passage is (tokens) |
| `chunking.chunk_overlap` | How much passages overlap (helps retrieval) |
| `retrieval.top_k` | Default number of results returned |
| `retrieval.min_score` | Minimum relevance threshold (0–1) |
| `embeddings.provider` | `openai` or `local` |
| `google_docs.burst_interval_seconds` | How often to re-check during burst mode |
| `google_docs.burst_duration_seconds` | How long burst mode lasts after a change |

---

## Troubleshooting

**"credentials.json not found"**
Download your OAuth 2.0 Desktop client credentials from Google Cloud Console
and place the file at the project root.

**"OPENAI_API_KEY is not set"**
Add your key to `.env`: `OPENAI_API_KEY=sk-...`

**"spaCy model not found"**
Run: `python -m spacy download en_core_web_sm`

**Index seems stale**
Run a manual sync: `python scripts/sync_and_index.py`
Or force a full rebuild: `python scripts/full_reindex.py`

**Out of memory on VPS**
Check swap is active: `free -h`
If not: `sudo swapon /swapfile`
