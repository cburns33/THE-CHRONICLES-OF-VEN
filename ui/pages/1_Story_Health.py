"""Story Health dashboard — overview of manuscript coverage and character activity.

Sourced entirely from SQLite (no ChromaDB queries, no embedding calls).
"""

import sys
from pathlib import Path

# Project root on sys.path so src.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# ui/ on sys.path so `theme` import works
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from theme import DARK_FANTASY_CSS

from src.indexing.sqlite_store import (
    get_all_chapters,
    get_entity_appearances_by_chapter,
)
from src.indexing.vector_store import collection_stats
from src.utils.config import load_config

cfg = load_config()

st.set_page_config(
    page_title="Story Health — Inherited Cloud",
    page_icon="📊",
    layout="wide",
)

st.markdown(DARK_FANTASY_CSS, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 1.2rem 0 0.5rem 0; border-bottom: 1px solid #3a3120; margin-bottom: 1.5rem;">
    <div style="font-family:'Cinzel',serif; color:#6a5c35; font-size:13px; letter-spacing:0.25em; margin-bottom:0.3rem;">✦ &nbsp; THE CHRONICLES OF VEN &nbsp; ✦</div>
    <div style="font-family:'Cinzel',serif; color:#c9a84c; font-size:2rem; font-weight:600; letter-spacing:0.08em; line-height:1.2;">Story Health</div>
    <div style="font-family:'Crimson Text',serif; color:#6a5c35; font-style:italic; font-size:15px; margin-top:0.4rem;">Manuscript coverage at a glance</div>
</div>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
chapters = get_all_chapters()
appearances = get_entity_appearances_by_chapter()

try:
    stats = collection_stats()
    total_chunks = stats["total_chunks"]
except Exception:
    total_chunks = 0

novel_chapters = len(chapters)
characters_tracked = len({r["entity_text"] for r in appearances})

# Timeline event count from SQLite if available
try:
    import sqlite3
    db_path = Path(cfg["paths"]["db_path"])
    with sqlite3.connect(str(db_path)) as conn:
        timeline_count = conn.execute(
            "SELECT COUNT(*) FROM timeline_events"
        ).fetchone()[0]
except Exception:
    timeline_count = 0

# ── Metric cards ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total chunks", f"{total_chunks:,}")
c2.metric("Novel chapters", novel_chapters)
c3.metric("Characters tracked", characters_tracked)
c4.metric("Timeline events", timeline_count)

st.divider()

# ── Character appearance chart ─────────────────────────────────────────────────
st.subheader("Character Appearances by Chapter")

if not appearances:
    st.info("No character data yet — run a full reindex first.")
else:
    try:
        import plotly.graph_objects as go
        import pandas as pd
        from plotly.subplots import make_subplots

        df = pd.DataFrame(appearances)

        # Top 10 characters by total appearances
        top_chars = (
            df.groupby("entity_text")["count"]
            .sum()
            .nlargest(10)
            .index.tolist()
        )
        df_top = df[df["entity_text"].isin(top_chars)].copy()

        # Build chapter label map for x-axis
        chapter_labels = {
            c["chapter_idx"]: f"Ch {c['chapter_idx']}"
            for c in chapters
        }
        df_top["chapter_label"] = df_top["chapter_idx"].map(
            lambda i: chapter_labels.get(i, f"Ch {i}")
        )

        # Pivot: rows=chapter, cols=character
        pivot = df_top.pivot_table(
            index=["chapter_idx", "chapter_label"],
            columns="entity_text",
            values="count",
            aggfunc="sum",
            fill_value=0,
        ).reset_index().sort_values("chapter_idx")

        # Muted fantasy palette — distinct hues, dark-background friendly
        palette = [
            "#c9a84c",  # gold
            "#6b9ec4",  # steel blue
            "#a86b6b",  # dusty rose
            "#6baa7a",  # sage green
            "#9b6bc4",  # muted purple
            "#c4876b",  # burnt sienna
            "#5a9e9e",  # teal
            "#c46b9b",  # dusty mauve
            "#8fa86b",  # olive
            "#c4b06b",  # warm amber
        ]

        view = st.radio(
            "chart_view",
            ["Stacked", "Small Multiples"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if view == "Stacked":
            fig = go.Figure()
            for i, char in enumerate(top_chars):
                if char in pivot.columns:
                    fig.add_trace(go.Bar(
                        name=char,
                        x=pivot["chapter_label"],
                        y=pivot[char],
                        marker_color=palette[i % len(palette)],
                    ))

            fig.update_layout(
                barmode="stack",
                plot_bgcolor="#0f0e09",
                paper_bgcolor="#0f0e09",
                font=dict(color="#ddd3b8", family="Crimson Text, Georgia, serif"),
                legend=dict(
                    bgcolor="#16140d",
                    bordercolor="#3a3120",
                    borderwidth=1,
                    font=dict(color="#b8aa8a"),
                ),
                xaxis=dict(
                    tickfont=dict(color="#b8aa8a"),
                    gridcolor="#1e1b10",
                    linecolor="#3a3120",
                ),
                yaxis=dict(
                    title="Chunk appearances",
                    tickfont=dict(color="#b8aa8a"),
                    gridcolor="#1e1b10",
                    linecolor="#3a3120",
                ),
                margin=dict(l=40, r=20, t=20, b=40),
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            n = len(top_chars)
            spacing = 0.018
            row_h = (1 - spacing * (n - 1)) / n
            # Paper-coord y-center for each row, top to bottom
            centers = [1 - row_h / 2 - i * (row_h + spacing) for i in range(n)]

            fig2 = make_subplots(
                rows=n, cols=1,
                shared_xaxes=True,
                vertical_spacing=spacing,
            )

            for i, char in enumerate(top_chars):
                color = palette[i % len(palette)]
                y_vals = pivot[char].tolist() if char in pivot.columns else [0] * len(pivot)

                fig2.add_trace(
                    go.Bar(
                        x=pivot["chapter_label"],
                        y=y_vals,
                        marker_color=color,
                        marker_line_width=0,
                        showlegend=False,
                        hovertemplate=f"<b>{char}</b><br>%{{x}}: %{{y}}<extra></extra>",
                    ),
                    row=i + 1, col=1,
                )

                fig2.add_annotation(
                    text=char,
                    xref="paper", yref="paper",
                    x=-0.01, y=centers[i],
                    xanchor="right", yanchor="middle",
                    showarrow=False,
                    font=dict(color=color, size=11, family="Crimson Text, Georgia, serif"),
                )

                fig2.update_yaxes(
                    showticklabels=False,
                    showgrid=False,
                    zeroline=False,
                    showline=False,
                    row=i + 1, col=1,
                )
                fig2.update_xaxes(
                    showticklabels=(i == n - 1),
                    showgrid=False,
                    zeroline=False,
                    showline=(i == n - 1),
                    linecolor="#3a3120",
                    row=i + 1, col=1,
                )

            fig2.update_xaxes(
                tickfont=dict(color="#b8aa8a", size=10),
                row=n, col=1,
            )
            fig2.update_layout(
                plot_bgcolor="#0f0e09",
                paper_bgcolor="#0f0e09",
                font=dict(color="#ddd3b8", family="Crimson Text, Georgia, serif"),
                height=58 * n + 60,
                margin=dict(l=110, r=20, t=10, b=40),
                bargap=0.25,
            )
            st.plotly_chart(fig2, use_container_width=True)

    except ImportError:
        import pandas as pd
        df = pd.DataFrame(appearances)
        top = (
            df.groupby("entity_text")["count"]
            .sum()
            .nlargest(10)
            .reset_index()
            .rename(columns={"entity_text": "Character", "count": "Total appearances"})
        )
        st.dataframe(top, use_container_width=True, hide_index=True)

st.divider()

# ── Chapter overview table ─────────────────────────────────────────────────────
st.subheader("Chapter Overview")

if not chapters:
    st.info("No chapters indexed yet.")
else:
    sorted_chapters = sorted(chapters, key=lambda c: c["chapter_idx"])

    rows_html = ""
    for c in sorted_chapters:
        indexed = c.get("indexed_at") or ""
        if indexed:
            indexed = indexed[:10]  # date only
        rows_html += (
            f"<tr>"
            f"<td>{c['title']}</td>"
            f"<td style='text-align:center'>{c['chunk_count']}</td>"
            f"<td style='text-align:center'>{indexed}</td>"
            f"</tr>"
        )

    st.markdown(f"""
<style>
.chapter-table {{
    width: 100%;
    border-collapse: collapse;
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 16px;
    color: #ddd3b8;
}}
.chapter-table th {{
    font-family: 'Cinzel', serif;
    font-size: 12px;
    letter-spacing: 0.1em;
    color: #c9a84c;
    text-transform: uppercase;
    border-bottom: 1px solid #4a3f25;
    padding: 0.6rem 0.8rem;
    text-align: left;
    background-color: #16140d;
}}
.chapter-table th.center {{ text-align: center; }}
.chapter-table td {{
    padding: 0.55rem 0.8rem;
    border-bottom: 1px solid #252010;
    vertical-align: top;
}}
.chapter-table tr:hover td {{
    background-color: #1e1b10;
}}
</style>
<table class="chapter-table">
  <thead>
    <tr>
      <th>Title</th>
      <th class="center">Chunks</th>
      <th class="center">Indexed</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
""", unsafe_allow_html=True)
