"""Streamlit author-facing search UI.

Start with:
  streamlit run ui/app.py

The author opens this in a browser and types queries in plain English.
No technical knowledge required.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from src.retrieval.query_engine import semantic_search, entity_search, more_like_this
from src.indexing.vector_store import collection_stats
from src.indexing.sqlite_store import get_all_chapters, get_all_entities
from src.utils.config import load_config

cfg = load_config()

st.set_page_config(
    page_title=cfg["ui"]["title"],
    page_icon="📖",
    layout="wide",
)

# ── Theme ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400;1,600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 17px;
}

.stApp {
    background-color: #0f0e09;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #16140d;
    border-right: 1px solid #3a3120;
}
[data-testid="stSidebar"] h1 {
    font-family: 'Cinzel', serif;
    color: #c9a84c;
    letter-spacing: 0.05em;
    font-size: 1.2rem;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p {
    color: #b8aa8a;
    font-family: 'Crimson Text', serif;
}

/* ── Headings ── */
h1 { font-family: 'Cinzel', serif !important; color: #c9a84c !important; letter-spacing: 0.08em; }
h2 { font-family: 'Cinzel', serif !important; color: #a8905c !important; }
h3 { font-family: 'Cinzel', serif !important; color: #8a7a50 !important; }

/* ── Search input ── */
[data-testid="stTextInput"] input {
    background-color: #1e1b12;
    border: 1px solid #4a3f25;
    color: #e8dfc8;
    font-family: 'Crimson Text', serif;
    font-size: 18px;
    border-radius: 4px;
}
[data-testid="stTextInput"] input:focus {
    border-color: #c9a84c;
    box-shadow: 0 0 0 1px #c9a84c44;
}
[data-testid="stTextInput"] input::placeholder {
    color: #6a6045;
    font-style: italic;
}

/* ── Search button ── */
[data-testid="stButton"] button[kind="primary"] {
    background-color: #5a3e1b;
    border: 1px solid #c9a84c;
    color: #f0e4c4;
    font-family: 'Cinzel', serif;
    letter-spacing: 0.1em;
    font-size: 13px;
    border-radius: 3px;
    padding: 0.4rem 1.4rem;
    transition: all 0.2s ease;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #7a5525;
    border-color: #e0c068;
    color: #fff8e8;
}

/* ── Result expanders (passage cards) ── */
[data-testid="stExpander"] {
    background-color: #1a1710;
    border: 1px solid #352e1c;
    border-radius: 3px;
    margin-bottom: 0.5rem;
}
[data-testid="stExpander"]:hover {
    border-color: #4a4025;
}
[data-testid="stExpander"] summary {
    font-family: 'Cinzel', serif;
    font-size: 14px;
    color: #c9a84c;
    letter-spacing: 0.03em;
}
[data-testid="stExpander"] p,
[data-testid="stExpander"] .stMarkdown {
    color: #ddd3b8;
    font-family: 'Crimson Text', serif;
    font-size: 17px;
    line-height: 1.7;
}

/* ── Captions / metadata ── */
[data-testid="stCaptionContainer"] p,
small, .stCaption {
    color: #7a6e52 !important;
    font-family: 'Crimson Text', serif;
    font-style: italic;
}

/* ── Success / info banners ── */
[data-testid="stAlert"] {
    background-color: #1e1b10;
    border-color: #4a3f25;
    color: #c9a84c;
}

/* ── Dividers ── */
hr {
    border-color: #3a3120 !important;
}

/* ── General text ── */
p, li, span {
    color: #ddd3b8;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📖 Novel Search")
    st.caption("Search your manuscript by meaning, character, or lore.")

    st.divider()

    search_mode = st.radio(
        "Search mode",
        ["Semantic (meaning)", "Entity (character/place lookup)"],
        help="Semantic finds passages by meaning. Entity finds which chapters a name appears in.",
    )

    st.divider()
    st.subheader("Search in")
    source_option = st.radio(
        "Source",
        ["Everything", "Novel only", "Continuity docs only", "World building only"],
        label_visibility="collapsed",
    )
    source_map = {
        "Everything": None,
        "Novel only": "manuscript",
        "Continuity docs only": "continuity",
        "World building only": "worldbuilding",
    }
    filter_source = source_map[source_option]

    st.divider()
    st.subheader("Filters (optional)")
    chapters = get_all_chapters()
    chapter_options = {f"[{c['chapter_idx']:02d}] {c['title']}": c["slug"] for c in chapters}
    selected_chapter_label = st.selectbox(
        "Restrict to chapter", ["All chapters"] + list(chapter_options.keys())
    )
    filter_chapter = (
        None
        if selected_chapter_label == "All chapters"
        else chapter_options[selected_chapter_label]
    )

    try:
        known_characters = sorted({
            e["name"] for e in get_all_entities()
            if e.get("entity_type", "").upper() in ("PERSON", "PER", "CHARACTER")
        })
    except Exception:
        known_characters = []

    selected_characters = st.multiselect(
        "Restrict to character(s)",
        options=known_characters,
        placeholder="Select one or more characters…",
    )
    filter_characters = selected_characters if selected_characters else None

    try:
        known_places = sorted({
            e["name"] for e in get_all_entities()
            if e.get("entity_type", "").upper() == "PLACE"
        })
    except Exception:
        known_places = []

    selected_places = st.multiselect(
        "Restrict to place(s)",
        options=known_places,
        placeholder="Select one or more places…",
    )
    filter_places = selected_places if selected_places else None

    top_k = st.slider("Max results", min_value=3, max_value=20, value=cfg["retrieval"]["top_k"])

    st.divider()
    try:
        stats = collection_stats()
        st.caption(f"Index: {stats['total_chunks']:,} chunks across {len(chapters)} chapters")
    except Exception:
        st.caption("Index not yet built — run setup.py first.")

    try:
        import json
        from datetime import timezone
        from pathlib import Path
        import datetime
        state_path = Path(__file__).parent.parent / cfg["paths"]["state_path"]
        state = json.loads(state_path.read_text())
        last_synced = state.get("last_synced")
        if last_synced:
            dt = datetime.datetime.fromisoformat(last_synced).astimezone().replace(tzinfo=None)
            st.caption(f"Last synced: {dt.strftime('%b %d, %Y at %I:%M %p')}")
    except Exception:
        pass

# ── Main panel ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 1.2rem 0 0.5rem 0; border-bottom: 1px solid #3a3120; margin-bottom: 1.5rem;">
    <div style="font-family:'Cinzel',serif; color:#6a5c35; font-size:13px; letter-spacing:0.25em; margin-bottom:0.3rem;">✦ &nbsp; THE CHRONICLES OF VEN &nbsp; ✦</div>
    <div style="font-family:'Cinzel',serif; color:#c9a84c; font-size:2rem; font-weight:600; letter-spacing:0.08em; line-height:1.2;">Search the Manuscript</div>
    <div style="font-family:'Crimson Text',serif; color:#6a5c35; font-style:italic; font-size:15px; margin-top:0.4rem;">Seek truth in the written word</div>
</div>
""", unsafe_allow_html=True)

query = st.text_input(
    "What are you looking for?",
    placeholder='e.g. "Find all passages implying the king suspects betrayal"',
    label_visibility="collapsed",
)

search_btn = st.button("Search", type="primary", use_container_width=False)

# Session state for "More like this"
if "mlt_chunk_id" not in st.session_state:
    st.session_state["mlt_chunk_id"] = None
if "mlt_label" not in st.session_state:
    st.session_state["mlt_label"] = None

def _render_results(results: list[dict], query_label: str) -> None:
    if not results:
        st.info("No matching passages found. Try rephrasing your query.")
        return

    st.success(f"{len(results)} passage(s) found")

    from src.retrieval.formatters import format_for_chatgpt
    chatgpt_block = format_for_chatgpt(results, query_label)
    with st.expander("📋 Copy as ChatGPT context block"):
        st.text_area(
            "Paste this into ChatGPT:",
            value=chatgpt_block,
            height=200,
            label_visibility="collapsed",
        )

    st.divider()

    for i, r in enumerate(results, 1):
        chapter = r.get("chapter_title", "Unknown")
        scene = r.get("scene_heading", "")
        score = r.get("score", 0)
        pov = r.get("pov_character", "")
        text = r.get("text", "").strip()
        chunk_id = r.get("chunk_id", "")

        label = chapter
        if scene and scene != chapter:
            label += f" › {scene}"

        with st.expander(f"**{i}. {label}** — relevance {score:.0%}", expanded=i <= 3):
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(text)
                if chunk_id:
                    if st.button("More like this", key=f"mlt_{chunk_id}"):
                        st.session_state["mlt_chunk_id"] = chunk_id
                        st.session_state["mlt_label"] = label
                        st.rerun()
            with cols[1]:
                src = r.get("source_type", "manuscript")
                subtype = r.get("doc_subtype", "")
                src_label = {"manuscript": "📖 Novel", "continuity": "📜 Continuity", "worldbuilding": "🌍 World Building"}.get(src, src)
                if subtype:
                    src_label += f" ({subtype})"
                st.caption(src_label)
                src_file = r.get("source_file", "")
                if src_file and src != "manuscript":
                    st.caption(f"File: {src_file}")
                if pov:
                    st.caption(f"POV: {pov}")
                chars = r.get("characters", "")
                if chars:
                    st.caption(f"Characters: {chars}")
                tl = r.get("timeline_tags", "")
                if tl:
                    st.caption(f"Timeline: {tl}")


# ── "More like this" mode ─────────────────────────────────────────────────────
if st.session_state["mlt_chunk_id"]:
    mlt_label = st.session_state["mlt_label"] or "selected passage"
    st.info(f"Showing passages similar to: **{mlt_label}**")
    if st.button("Clear — return to search"):
        st.session_state["mlt_chunk_id"] = None
        st.session_state["mlt_label"] = None
        st.rerun()
    with st.spinner("Finding similar passages…"):
        results = more_like_this(
            st.session_state["mlt_chunk_id"],
            top_k=top_k,
            filter_source=filter_source,
        )
    _render_results(results, f"More like: {mlt_label}")

elif search_btn and query.strip():
    with st.spinner("Searching…"):
        if search_mode.startswith("Entity"):
            results = entity_search(query)
            if not results:
                st.info("No entity matches found.")
            else:
                st.success(f"{len(results)} chapter(s) found")
                for r in results:
                    st.markdown(
                        f"**[{r['chapter_idx']:02d}] {r['chapter_title']}** — {r['entity_type']}"
                    )
        else:
            results = semantic_search(
                query,
                top_k=top_k,
                filter_chapter=filter_chapter,
                filter_characters=filter_characters,
                filter_places=filter_places,
                filter_source=filter_source,
            )
            _render_results(results, query)

elif search_btn and not query.strip():
    st.warning("Please enter a search query.")
