"""Convert Google Docs API JSON (with Tabs) to structured per-chapter Markdown files.

The manuscript uses Google Docs Tabs — each tab is a chapter. The API returns
all tab content when called with includeTabsContent=True.

Tab structure in the API response:
  document['tabs'] = [
    {
      'tabProperties': {'title': 'Chapter 1 - The Feral ...', 'index': 0},
      'documentTab': {'body': {'content': [...]}}
    },
    ...
  ]

Each tab becomes one Chapter. Within a tab, headings become Markdown headings
for scene-level splitting during chunking.
"""

import re
from pathlib import Path
from typing import NamedTuple

from src.utils.hashing import content_hash, chapter_slug
from src.utils.logging import get_logger

log = get_logger(__name__)


class Chapter(NamedTuple):
    index: int
    title: str
    slug: str
    markdown: str
    content_hash: str


def docs_json_to_chapters(document: dict) -> list[Chapter]:
    """Parse a Google Docs API document dict (tabs-based) into Chapter objects.

    Falls back to treating the whole document as a single chapter if no tabs
    are present (handles plain single-tab documents too).
    """
    tabs = document.get("tabs", [])

    if tabs:
        return _chapters_from_tabs(tabs)
    else:
        # Fallback: single body, no tabs
        log.warning("No tabs found — treating entire document as one chapter")
        body_content = document.get("body", {}).get("content", [])
        title = document.get("title", "Manuscript")
        md = _content_to_markdown(body_content)
        if not md.strip():
            return []
        slug = chapter_slug(title, 0)
        return [Chapter(index=0, title=title, slug=slug, markdown=md, content_hash=content_hash(md))]


def _chapters_from_tabs(tabs: list[dict]) -> list[Chapter]:
    chapters = []
    for tab in tabs:
        props = tab.get("tabProperties", {})
        title = props.get("title", f"Chapter {props.get('index', 0)}")
        index = props.get("index", 0)

        # Content lives in documentTab.body.content
        doc_tab = tab.get("documentTab", {})
        body_content = doc_tab.get("body", {}).get("content", [])

        md = _content_to_markdown(body_content)
        if not md.strip():
            log.debug(f"Skipping empty tab: '{title}'")
            continue

        slug = chapter_slug(title, index)
        chapters.append(Chapter(
            index=index,
            title=title,
            slug=slug,
            markdown=md,
            content_hash=content_hash(md),
        ))

    log.info(f"Parsed {len(chapters)} chapters from {len(tabs)} tabs")
    return chapters


def _content_to_markdown(content: list[dict]) -> str:
    """Convert a Docs API body content list to a Markdown string."""
    lines = []
    for element in content:
        if "paragraph" not in element:
            continue

        para = element["paragraph"]
        style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text = _extract_paragraph_text(para)

        if not text.strip():
            lines.append("")
            continue

        if style == "HEADING_1":
            lines.append(f"## {text.strip()}")
        elif style == "HEADING_2":
            lines.append(f"### {text.strip()}")
        elif style == "HEADING_3":
            lines.append(f"#### {text.strip()}")
        else:
            lines.append(_apply_inline_formatting(para).rstrip())

    return _clean_markdown("\n".join(lines))


def save_chapters(chapters: list[Chapter], out_dir: Path) -> None:
    """Write each chapter to its own Markdown file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for ch in chapters:
        path = out_dir / f"{ch.slug}.md"
        path.write_text(
            f"---\ntitle: {ch.title}\nchapter: {ch.index}\nslug: {ch.slug}\n---\n\n"
            + ch.markdown,
            encoding="utf-8",
        )
    log.info(f"Saved {len(chapters)} chapter files to {out_dir}")


def _extract_paragraph_text(para: dict) -> str:
    """Extract raw text from a paragraph element."""
    text = ""
    for element in para.get("elements", []):
        if "textRun" in element:
            text += element["textRun"].get("content", "")
    return text


def _apply_inline_formatting(para: dict) -> str:
    """Extract text with basic Markdown inline formatting (bold, italic)."""
    parts = []
    for element in para.get("elements", []):
        if "textRun" not in element:
            continue
        run = element["textRun"]
        text = run.get("content", "")
        if not text:
            continue
        style = run.get("textStyle", {})
        bold = style.get("bold", False)
        italic = style.get("italic", False)

        if bold and italic:
            text = f"***{text}***"
        elif bold:
            text = f"**{text}**"
        elif italic:
            text = f"*{text}*"

        parts.append(text)

    return "".join(parts)


def _clean_markdown(md: str) -> str:
    """Remove excessive blank lines and trailing whitespace."""
    md = re.sub(r"\n{3,}", "\n\n", md)
    lines = [line.rstrip() for line in md.splitlines()]
    return "\n".join(lines).strip()
