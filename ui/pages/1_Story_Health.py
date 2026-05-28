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
    get_character_arc_summary,
    get_place_appearances_by_chapter,
    get_entity_type_breakdown_by_chapter,
    get_relationship_summary,
    get_full_timeline,
    detect_timeline_gaps,
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
chapters = get_all_chapters(manuscript_only=True)
appearances = get_entity_appearances_by_chapter()
arc_summary = get_character_arc_summary()
place_appearances = get_place_appearances_by_chapter()
entity_breakdown = get_entity_type_breakdown_by_chapter()
relationship_pairs = get_relationship_summary()
timeline_events = get_full_timeline()
timeline_gaps = detect_timeline_gaps()

try:
    stats = collection_stats()
    total_chunks = stats["total_chunks"]
except Exception:
    total_chunks = 0

novel_chapters = len(chapters)
characters_tracked = len({r["entity_text"] for r in appearances})
max_chapter_idx = max((c["chapter_idx"] for c in chapters), default=0)
chapter_label_map = {c["chapter_idx"]: f"Ch {c['chapter_idx']}: {c['title']}" for c in chapters}
chapter_short_map = {c["chapter_idx"]: f"Ch {c['chapter_idx']}" for c in chapters}

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

# Muted fantasy palette — reused across charts
PALETTE = [
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
    "#7b8ec4",  # periwinkle
    "#c4a06b",  # tan
]

DARK_PLOTLY = dict(
    plot_bgcolor="#0f0e09",
    paper_bgcolor="#0f0e09",
    font=dict(color="#ddd3b8", family="Crimson Text, Georgia, serif"),
)


def _dark_axes():
    return dict(
        tickfont=dict(color="#b8aa8a"),
        gridcolor="#1e1b10",
        linecolor="#3a3120",
    )


def _stacked_bar_chart(df_pivot, top_items, chapter_col, height=380):
    """Render a stacked bar chart from a pivot table."""
    import plotly.graph_objects as go
    fig = go.Figure()
    for i, name in enumerate(top_items):
        if name in df_pivot.columns:
            fig.add_trace(go.Bar(
                name=name,
                x=df_pivot[chapter_col],
                y=df_pivot[name],
                marker_color=PALETTE[i % len(PALETTE)],
            ))
    fig.update_layout(
        barmode="stack",
        **DARK_PLOTLY,
        height=height,
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(bgcolor="#16140d", bordercolor="#3a3120", borderwidth=1,
                    font=dict(color="#b8aa8a")),
        xaxis=_dark_axes(),
        yaxis=dict(title="Chunk appearances", **_dark_axes()),
    )
    return fig


def _small_multiples_chart(df_pivot, top_items, chapter_col):
    """Render small-multiples bars from a pivot table."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(top_items)
    spacing = 0.018
    row_h = (1 - spacing * (n - 1)) / n
    centers = [1 - row_h / 2 - i * (row_h + spacing) for i in range(n)]

    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=spacing)
    for i, name in enumerate(top_items):
        color = PALETTE[i % len(PALETTE)]
        y_vals = df_pivot[name].tolist() if name in df_pivot.columns else [0] * len(df_pivot)
        fig.add_trace(
            go.Bar(
                x=df_pivot[chapter_col],
                y=y_vals,
                marker_color=color,
                marker_line_width=0,
                showlegend=False,
                hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y}}<extra></extra>",
            ),
            row=i + 1, col=1,
        )
        fig.add_annotation(
            text=name, xref="paper", yref="paper",
            x=-0.01, y=centers[i],
            xanchor="right", yanchor="middle",
            showarrow=False,
            font=dict(color=color, size=11, family="Crimson Text, Georgia, serif"),
        )
        fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False,
                         showline=False, row=i + 1, col=1)
        fig.update_xaxes(showticklabels=(i == n - 1), showgrid=False, zeroline=False,
                         showline=(i == n - 1), linecolor="#3a3120", row=i + 1, col=1)
    fig.update_xaxes(tickfont=dict(color="#b8aa8a", size=10), row=n, col=1)
    fig.update_layout(
        **DARK_PLOTLY,
        height=58 * n + 60,
        margin=dict(l=110, r=20, t=10, b=40),
        bargap=0.25,
    )
    return fig


if not appearances:
    st.info("No character data yet — run a full reindex first.")
else:
    try:
        import plotly.graph_objects as go
        import pandas as pd
        from plotly.subplots import make_subplots

        df = pd.DataFrame(appearances)
        top_chars = (
            df.groupby("entity_text")["count"]
            .sum()
            .nlargest(10)
            .index.tolist()
        )
        df_top = df[df["entity_text"].isin(top_chars)].copy()
        df_top["chapter_label"] = df_top["chapter_idx"].map(
            lambda i: chapter_short_map.get(i, f"Ch {i}")
        )
        pivot = df_top.pivot_table(
            index=["chapter_idx", "chapter_label"],
            columns="entity_text",
            values="count",
            aggfunc="sum",
            fill_value=0,
        ).reset_index().sort_values("chapter_idx")

        view = st.radio(
            "char_view",
            ["Stacked", "Small Multiples"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if view == "Stacked":
            st.plotly_chart(_stacked_bar_chart(pivot, top_chars, "chapter_label"),
                            use_container_width=True)
        else:
            st.plotly_chart(_small_multiples_chart(pivot, top_chars, "chapter_label"),
                            use_container_width=True)

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

# ── Character Arcs ─────────────────────────────────────────────────────────────
st.subheader("Character Arcs")
st.caption("First introduction, last appearance, and chapter coverage for every named character.")

_ARC_TABLE_STYLE = """
<style>
.arc-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 16px;
    color: #ddd3b8;
}
.arc-table th {
    font-family: 'Cinzel', serif;
    font-size: 12px;
    letter-spacing: 0.1em;
    color: #c9a84c;
    text-transform: uppercase;
    border-bottom: 1px solid #4a3f25;
    padding: 0.6rem 0.8rem;
    background-color: #16140d;
}
.arc-table th.center { text-align: center; }
.arc-table td {
    padding: 0.55rem 0.8rem;
    border-bottom: 1px solid #252010;
    vertical-align: middle;
}
.arc-table tr:hover td { background-color: #1e1b10; }
</style>
"""

_ARC_TABLE_HEADER = """
<table class="arc-table">
  <thead>
    <tr>
      <th>Character</th>
      <th class="center">First Seen</th>
      <th class="center">Last Seen</th>
      <th class="center">Coverage</th>
      <th class="center">Status</th>
    </tr>
  </thead>
  <tbody>
"""


def _arc_row(row: dict) -> str:
    first = chapter_short_map.get(row["first_chapter"], f"Ch {row['first_chapter']}")
    last = chapter_short_map.get(row["last_chapter"], f"Ch {row['last_chapter']}")
    pct = int(row["chapters_present"] / novel_chapters * 100) if novel_chapters else 0
    is_active = row["last_chapter"] >= max_chapter_idx - 2

    bar_color = "#c9a84c" if is_active else "#4a3f25"
    coverage_bar = (
        f'<span style="display:inline-flex;align-items:center;gap:6px;">'
        f'{row["chapters_present"]}/{novel_chapters}'
        f'<span style="display:inline-block;width:60px;height:6px;background:#1e1b10;border-radius:2px;">'
        f'<span style="display:inline-block;width:{pct}%;height:6px;background:{bar_color};border-radius:2px;"></span>'
        f'</span></span>'
    )
    if is_active:
        badge = '<span style="font-size:11px;padding:2px 8px;border-radius:3px;background:#1a2e1e;color:#6baa7a;border:1px solid #2a4a2e;font-family:Cinzel,serif;letter-spacing:0.05em;">Active</span>'
    else:
        badge = '<span style="font-size:11px;padding:2px 8px;border-radius:3px;background:#1e1b10;color:#6a5c35;border:1px solid #3a3120;font-family:Cinzel,serif;letter-spacing:0.05em;">Dormant</span>'

    return (
        f"<tr>"
        f"<td>{row['entity_text']}</td>"
        f"<td style='text-align:center'>{first}</td>"
        f"<td style='text-align:center'>{last}</td>"
        f"<td style='text-align:center'>{coverage_bar}</td>"
        f"<td style='text-align:center'>{badge}</td>"
        f"</tr>"
    )


_ARC_DEFAULT_ROWS = 15

_ARC_SORT_KEYS = {
    "Appearances": ("total_appearances", True),
    "Name":        ("entity_text", False),
    "First Seen":  ("first_chapter", False),
    "Last Seen":   ("last_chapter", True),
    "Coverage":    ("chapters_present", True),
}

if not arc_summary:
    st.info("No character data yet — run a full reindex first.")
else:
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1.2, 1.5])
    with ctrl1:
        sort_by = st.selectbox(
            "Sort by",
            list(_ARC_SORT_KEYS.keys()),
            index=0,
            label_visibility="collapsed",
            key="arc_sort_by",
        )
    with ctrl2:
        sort_dir = st.radio(
            "Direction",
            ["Desc", "Asc"],
            horizontal=True,
            label_visibility="collapsed",
            key="arc_sort_dir",
        )
    with ctrl3:
        status_filter = st.radio(
            "Status",
            ["All", "Active", "Dormant"],
            horizontal=True,
            label_visibility="collapsed",
            key="arc_status",
        )

    sort_field, default_desc = _ARC_SORT_KEYS[sort_by]
    descending = sort_dir == "Desc"
    filtered = arc_summary
    if status_filter == "Active":
        filtered = [r for r in filtered if r["last_chapter"] >= max_chapter_idx - 2]
    elif status_filter == "Dormant":
        filtered = [r for r in filtered if r["last_chapter"] < max_chapter_idx - 2]
    filtered = sorted(filtered, key=lambda r: r[sort_field], reverse=descending)

    visible = filtered[:_ARC_DEFAULT_ROWS]
    overflow = filtered[_ARC_DEFAULT_ROWS:]

    if not filtered:
        st.info("No characters match the current filter.")
    else:
        rows_html = "".join(_arc_row(r) for r in visible)
        st.markdown(
            _ARC_TABLE_STYLE + _ARC_TABLE_HEADER + rows_html + "</tbody></table>",
            unsafe_allow_html=True,
        )
        if overflow:
            with st.expander(f"Show {len(overflow)} more characters"):
                overflow_html = "".join(_arc_row(r) for r in overflow)
                st.markdown(
                    _ARC_TABLE_STYLE + _ARC_TABLE_HEADER + overflow_html + "</tbody></table>",
                    unsafe_allow_html=True,
                )

st.divider()

# ── Character Connections heatmap ──────────────────────────────────────────────
st.subheader("Character Connections")
st.caption("How often each pair of characters appears in the same chunk, across all chapters.")

if not relationship_pairs:
    st.info("No co-occurrence data yet — run a full reindex first.")
else:
    try:
        import plotly.graph_objects as go
        import pandas as pd

        # Build top characters by total connection count
        char_totals: dict[str, int] = {}
        for p in relationship_pairs:
            char_totals[p["entity_a"]] = char_totals.get(p["entity_a"], 0) + p["count"]
            char_totals[p["entity_b"]] = char_totals.get(p["entity_b"], 0) + p["count"]
        top_connected = sorted(char_totals, key=lambda x: -char_totals[x])[:12]

        # Build symmetric matrix via pandas
        filtered = [
            p for p in relationship_pairs
            if p["entity_a"] in top_connected and p["entity_b"] in top_connected
        ]
        if filtered:
            df_pairs = pd.DataFrame(filtered)
            rows_a = df_pairs[["entity_a", "entity_b", "count"]].rename(
                columns={"entity_a": "source", "entity_b": "target"}
            )
            rows_b = df_pairs[["entity_a", "entity_b", "count"]].rename(
                columns={"entity_b": "source", "entity_a": "target"}
            )
            df_long = pd.concat([rows_a, rows_b], ignore_index=True)
            matrix = df_long.pivot_table(
                index="source", columns="target", values="count",
                aggfunc="sum", fill_value=0,
            )
            matrix = matrix.reindex(index=top_connected, columns=top_connected, fill_value=0)

            fig_heat = go.Figure(go.Heatmap(
                z=matrix.values.tolist(),
                x=matrix.columns.tolist(),
                y=matrix.index.tolist(),
                colorscale=[[0, "#0f0e09"], [0.2, "#2a2010"], [0.6, "#6a4a1a"], [1, "#c9a84c"]],
                showscale=True,
                colorbar=dict(
                    tickfont=dict(color="#b8aa8a"),
                    outlinecolor="#3a3120",
                    outlinewidth=1,
                ),
                hovertemplate="%{y} + %{x}<br>Co-occurrences: %{z}<extra></extra>",
            ))
            fig_heat.update_layout(
                **DARK_PLOTLY,
                height=520,
                margin=dict(l=120, r=20, t=20, b=120),
                xaxis=dict(tickfont=dict(color="#b8aa8a", size=11), tickangle=-40,
                           gridcolor="#1e1b10", linecolor="#3a3120"),
                yaxis=dict(tickfont=dict(color="#b8aa8a", size=11),
                           gridcolor="#1e1b10", linecolor="#3a3120"),
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("Not enough overlapping characters for a heatmap.")

    except ImportError:
        st.info("Install plotly to see the heatmap.")

st.divider()

# ── Place Density ──────────────────────────────────────────────────────────────
st.subheader("Place Density by Chapter")
st.caption("Which locations appear most, and where the story's geography shifts over time.")

if not place_appearances:
    st.info("No place data yet — run a full reindex first.")
else:
    try:
        import plotly.graph_objects as go
        import pandas as pd
        from plotly.subplots import make_subplots

        df_p = pd.DataFrame(place_appearances)
        top_places = (
            df_p.groupby("entity_text")["count"]
            .sum()
            .nlargest(8)
            .index.tolist()
        )
        df_p_top = df_p[df_p["entity_text"].isin(top_places)].copy()
        df_p_top["chapter_label"] = df_p_top["chapter_idx"].map(
            lambda i: chapter_short_map.get(i, f"Ch {i}")
        )
        pivot_p = df_p_top.pivot_table(
            index=["chapter_idx", "chapter_label"],
            columns="entity_text",
            values="count",
            aggfunc="sum",
            fill_value=0,
        ).reset_index().sort_values("chapter_idx")

        pview = st.radio(
            "place_view",
            ["Stacked", "Small Multiples"],
            horizontal=True,
            label_visibility="collapsed",
            key="place_view",
        )
        if pview == "Stacked":
            st.plotly_chart(
                _stacked_bar_chart(pivot_p, top_places, "chapter_label"),
                use_container_width=True,
            )
        else:
            st.plotly_chart(
                _small_multiples_chart(pivot_p, top_places, "chapter_label"),
                use_container_width=True,
            )

    except ImportError:
        st.info("Install plotly to see the place density chart.")

st.divider()

# ── Timeline ───────────────────────────────────────────────────────────────────
st.subheader("Timeline")
st.caption("In-world time markers extracted from the manuscript.")

if timeline_count == 0:
    st.info("No timeline events found — run a full reindex to populate them.")
else:
    # Gap warnings
    if timeline_gaps:
        for gap in timeline_gaps:
            st.warning(
                f"Time gap: Year {int(gap['from_year'])} ({gap['from_chapter']}) "
                f"→ Year {int(gap['to_year'])} ({gap['to_chapter']}) "
                f"— {int(gap['to_year'] - gap['from_year'])} years unaccounted for."
            )

    try:
        import plotly.graph_objects as go
        import pandas as pd

        df_t = pd.DataFrame(timeline_events)

        # Scatter: year-type events with numeric sequence_hints
        year_events = df_t[
            (df_t["tag_type"] == "year") & df_t["sequence_hint"].notna()
        ].copy()

        if not year_events.empty:
            year_events["chapter_label"] = year_events["chapter_idx"].map(
                lambda i: chapter_short_map.get(i, f"Ch {i}")
            )
            chapter_indices = sorted(year_events["chapter_idx"].unique())
            color_map = {idx: PALETTE[i % len(PALETTE)] for i, idx in enumerate(chapter_indices)}
            year_events["color"] = year_events["chapter_idx"].map(color_map)

            fig_tl = go.Figure()
            for ch_idx in chapter_indices:
                subset = year_events[year_events["chapter_idx"] == ch_idx]
                ch_label = chapter_short_map.get(ch_idx, f"Ch {ch_idx}")
                fig_tl.add_trace(go.Scatter(
                    x=subset["sequence_hint"],
                    y=[0] * len(subset),
                    mode="markers+text",
                    name=ch_label,
                    marker=dict(size=14, color=color_map[ch_idx],
                                line=dict(width=1, color="#3a3120")),
                    text=subset["raw_tag"],
                    textposition="top center",
                    textfont=dict(color="#b8aa8a", size=10),
                    hovertemplate=f"<b>{ch_label}</b><br>%{{text}}<extra></extra>",
                ))

            fig_tl.update_layout(
                **DARK_PLOTLY,
                height=220,
                margin=dict(l=40, r=20, t=30, b=20),
                showlegend=True,
                legend=dict(bgcolor="#16140d", bordercolor="#3a3120", borderwidth=1,
                            font=dict(color="#b8aa8a")),
                xaxis=dict(title="In-world year", **_dark_axes()),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(fig_tl, use_container_width=True)

        # Full event table — collapsed by default
        with st.expander(f"All {timeline_count} timeline events"):
            tag_type_colors = {
                "year": "#c9a84c",
                "season": "#6baa7a",
                "month": "#6b9ec4",
                "day": "#a86b6b",
                "relative": "#9b6bc4",
            }
            tl_rows_html = ""
            for r in timeline_events:
                ch_label = chapter_short_map.get(r["chapter_idx"], f"Ch {r['chapter_idx']}")
                ttype = r["tag_type"]
                tcolor = tag_type_colors.get(ttype, "#b8aa8a")
                badge = (
                    f'<span style="font-size:11px;padding:1px 6px;border-radius:3px;'
                    f'background:#16140d;color:{tcolor};border:1px solid #3a3120;'
                    f'font-family:Cinzel,serif;">{ttype}</span>'
                )
                tl_rows_html += (
                    f"<tr>"
                    f"<td style='text-align:center'>{ch_label}</td>"
                    f"<td>{r['raw_tag']}</td>"
                    f"<td style='text-align:center'>{badge}</td>"
                    f"</tr>"
                )
            st.markdown(f"""
<table class="chapter-table" style="font-family:'Crimson Text',Georgia,serif;font-size:15px;color:#ddd3b8;width:100%;border-collapse:collapse;">
  <thead>
    <tr>
      <th style="font-family:Cinzel,serif;font-size:12px;letter-spacing:0.1em;color:#c9a84c;text-transform:uppercase;border-bottom:1px solid #4a3f25;padding:0.5rem 0.8rem;background:#16140d;text-align:center;width:120px;">Chapter</th>
      <th style="font-family:Cinzel,serif;font-size:12px;letter-spacing:0.1em;color:#c9a84c;text-transform:uppercase;border-bottom:1px solid #4a3f25;padding:0.5rem 0.8rem;background:#16140d;">Event</th>
      <th style="font-family:Cinzel,serif;font-size:12px;letter-spacing:0.1em;color:#c9a84c;text-transform:uppercase;border-bottom:1px solid #4a3f25;padding:0.5rem 0.8rem;background:#16140d;text-align:center;width:100px;">Type</th>
    </tr>
  </thead>
  <tbody>{tl_rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

    except ImportError:
        st.info("Install plotly to see the timeline chart.")

st.divider()

# ── Entity Composition by Chapter ─────────────────────────────────────────────
st.subheader("Entity Composition by Chapter")
st.caption("Balance of characters, places, organizations, and lore terms across the manuscript.")

if not entity_breakdown:
    st.info("No entity data yet — run a full reindex first.")
else:
    try:
        import plotly.graph_objects as go
        import pandas as pd

        df_e = pd.DataFrame(entity_breakdown)
        df_e["chapter_label"] = df_e["chapter_idx"].map(
            lambda i: chapter_short_map.get(i, f"Ch {i}")
        )

        entity_type_colors = {
            "PERSON": "#c9a84c",
            "PLACE":  "#6b9ec4",
            "ORG":    "#6baa7a",
            "LORE":   "#9b6bc4",
        }
        entity_types = sorted(df_e["entity_type"].unique())
        chapters_sorted = (
            df_e[["chapter_idx", "chapter_label"]]
            .drop_duplicates()
            .sort_values("chapter_idx")["chapter_label"]
            .tolist()
        )

        fig_e = go.Figure()
        for etype in entity_types:
            subset = df_e[df_e["entity_type"] == etype].set_index("chapter_label")["count"]
            y_vals = [subset.get(ch, 0) for ch in chapters_sorted]
            fig_e.add_trace(go.Bar(
                name=etype.capitalize(),
                x=chapters_sorted,
                y=y_vals,
                marker_color=entity_type_colors.get(etype, "#b8aa8a"),
            ))

        fig_e.update_layout(
            barmode="stack",
            **DARK_PLOTLY,
            height=340,
            legend=dict(bgcolor="#16140d", bordercolor="#3a3120", borderwidth=1,
                        font=dict(color="#b8aa8a")),
            xaxis=_dark_axes(),
            yaxis=dict(title="Entity mentions", **_dark_axes()),
        )
        st.plotly_chart(fig_e, use_container_width=True)

    except ImportError:
        import pandas as pd
        df_e = pd.DataFrame(entity_breakdown)
        st.dataframe(df_e, use_container_width=True, hide_index=True)

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
            indexed = indexed[:10]
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
