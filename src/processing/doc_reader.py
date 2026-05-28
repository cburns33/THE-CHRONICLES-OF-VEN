"""Extract text from local DOCX and PDF files.

Returns plain Markdown-ish text suitable for chunking.
Preserves heading structure in DOCX files where possible.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.utils.logging import get_logger

log = get_logger(__name__)


def read_file(path: Path) -> str:
    """Dispatch to the right reader based on file extension."""
    ext = path.suffix.lower()
    if ext == ".docx":
        return read_docx(path)
    elif ext == ".pdf":
        return read_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def read_docx(path: Path) -> str:
    """Extract text from a DOCX file, preserving heading structure as Markdown."""
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")

    doc = Document(str(path))
    lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue

        style_name = para.style.name if para.style else ""

        if "Heading 1" in style_name:
            lines.append(f"## {text}")
        elif "Heading 2" in style_name:
            lines.append(f"### {text}")
        elif "Heading 3" in style_name:
            lines.append(f"#### {text}")
        else:
            # Apply basic inline formatting
            formatted = _docx_para_to_markdown(para)
            lines.append(formatted)

    result = _clean_text("\n".join(lines))
    log.info(f"Read DOCX '{path.name}': {len(result)} chars")
    return result


def read_pdf(path: Path) -> str:
    """Extract text from a PDF file page by page using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")

    pages = []
    with fitz.open(str(path)) as pdf:
        for page in pdf:
            text = page.get_text()
            if text and text.strip():
                pages.append(text.strip())

    result = _clean_text("\n\n".join(pages))
    log.info(f"Read PDF '{path.name}': {len(pages)} pages, {len(result)} chars")
    return result


def classify_doc(filename: str) -> dict[str, str]:
    """
    Infer source_type and doc_subtype from filename.

    Returns:
        source_type: "worldbuilding" | "continuity"
        doc_subtype: "worldbuilding" | "handoff" | "transcript" | "story" | "unknown"
    """
    name_lower = filename.lower()

    if "world" in name_lower and "build" in name_lower:
        return {"source_type": "worldbuilding", "doc_subtype": "worldbuilding"}

    if any(x in name_lower for x in ["hand-off", "hand off", "handoff", "hand_off"]):
        return {"source_type": "continuity", "doc_subtype": "handoff"}

    if "transcript" in name_lower:
        return {"source_type": "continuity", "doc_subtype": "transcript"}

    if any(x in name_lower for x in ["story", "arc", "chapter"]):
        return {"source_type": "continuity", "doc_subtype": "story"}

    return {"source_type": "continuity", "doc_subtype": "unknown"}


def _docx_para_to_markdown(para) -> str:
    """Convert a docx paragraph to a Markdown string with inline formatting."""
    parts = []
    for run in para.runs:
        text = run.text
        if not text:
            continue
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"
        parts.append(text)
    return "".join(parts)


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()
