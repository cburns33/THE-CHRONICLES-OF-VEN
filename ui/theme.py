"""Shared dark fantasy CSS for all Streamlit pages."""

DARK_FANTASY_CSS = """
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
    color: rgb(221, 211, 184);
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

/* ── Hide Streamlit chrome (toolbar, header, footer) ── */
[data-testid="stToolbar"],
[data-testid="stHeader"],
[data-testid="stDecoration"],
footer {
    display: none !important;
}

/* ── General text ── */
p, li, span {
    color: #ddd3b8;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #1e1b12 !important;
    border: 1px solid #4a3f25 !important;
    border-radius: 4px !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] span {
    color: #e8dfc8 !important;
    font-family: 'Crimson Text', serif !important;
    font-size: 16px !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
    fill: #b8aa8a !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
    border-color: #c9a84c !important;
    box-shadow: 0 0 0 1px #c9a84c44 !important;
}

/* Selectbox dropdown menu */
ul[data-baseweb="menu"] {
    background-color: #1e1b12 !important;
    border: 1px solid #4a3f25 !important;
    border-radius: 4px !important;
}
li[data-baseweb="option"] {
    background-color: #1e1b12 !important;
    color: #ddd3b8 !important;
    font-family: 'Crimson Text', serif !important;
    font-size: 16px !important;
}
li[data-baseweb="option"]:hover {
    background-color: #2a2510 !important;
    color: #c9a84c !important;
}
li[data-baseweb="option"][aria-selected="true"] {
    background-color: #2a2510 !important;
    color: #c9a84c !important;
}

/* ── All placeholder text ── */
input::placeholder,
textarea::placeholder {
    color: rgb(221, 211, 184) !important;
    font-style: italic;
}

/* ── Radio buttons ── */
/* Fill color is handled by primaryColor in .streamlit/config.toml */
[data-testid="stRadio"] label {
    color: #b8aa8a !important;
    font-family: 'Crimson Text', serif !important;
    font-size: 15px !important;
}
[data-testid="stRadio"] label:hover {
    color: #ddd3b8 !important;
}

/* ── Multiselect ── */
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background-color: #1e1b12 !important;
    border: 1px solid #4a3f25 !important;
    border-radius: 4px !important;
}
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within {
    border-color: #c9a84c !important;
    box-shadow: 0 0 0 1px #c9a84c44 !important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #2e2510 !important;
    color: #c9a84c !important;
    border: 1px solid #4a3f25 !important;
    font-family: 'Crimson Text', serif !important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
    color: #c9a84c !important;
}
[data-testid="stMultiSelect"] input {
    color: #e8dfc8 !important;
    font-family: 'Crimson Text', serif !important;
}

/* ── Secondary / tertiary buttons ── */
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stButton"] button[kind="tertiary"] {
    background-color: transparent !important;
    border: 1px solid #4a3f25 !important;
    color: #b8aa8a !important;
    font-family: 'Crimson Text', serif !important;
    font-size: 15px !important;
    border-radius: 3px !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stButton"] button[kind="tertiary"]:hover {
    border-color: #c9a84c !important;
    color: #c9a84c !important;
    background-color: #1e1b10 !important;
}

/* ── Sliders ── */
[data-testid="stSlider"] div[role="slider"] {
    background-color: #c9a84c !important;
    border-color: #c9a84c !important;
}
[data-testid="stSlider"] div[data-testid="stSliderTrack"] > div:first-child {
    background-color: #3a3120 !important;
}
[data-testid="stSlider"] div[data-testid="stSliderTrack"] > div:nth-child(2) {
    background-color: #c9a84c !important;
}
[data-testid="stSlider"] label,
[data-testid="stSlider"] p {
    color: #b8aa8a !important;
    font-family: 'Crimson Text', serif !important;
}

/* ── Number / text inputs (non-search) ── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"]:not([data-search]) input {
    background-color: #1e1b12 !important;
    border: 1px solid #4a3f25 !important;
    color: #e8dfc8 !important;
    font-family: 'Crimson Text', serif !important;
    border-radius: 4px !important;
}
[data-testid="stNumberInput"] button {
    background-color: #1e1b12 !important;
    border-color: #4a3f25 !important;
    color: #b8aa8a !important;
}
</style>
"""
