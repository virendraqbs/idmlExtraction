"""
services/topic_extractor.py — Extract topic-level data from a CL topic PDF using Gemini.
Used when uploading a topic PDF: returns title, topic_number, topic_summary.
Schema: CL-Json-Schema/schemas/content/topic.json (id, moduleId, topicNumber, title, topicSummary, images, lessons, metadata).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import config
from utils.schema_chunks import extract_lesson_meta


def _parse_topic_number_from_filename(filename: str) -> int | None:
    """e.g. SM5e_A1_SE_M01_T01_TOC.pdf or T03_... -> 1 or 3."""
    m = re.search(r"T(\d{1,2})(?:\s|_|$)", Path(filename).stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_title_from_filename(filename: str) -> str:
    num = _parse_topic_number_from_filename(filename)
    if num is not None:
        return f"Topic {num}"
    return Path(filename).stem.replace("_", " ").strip() or "Topic"


def extract_topic_from_pdf(
    pdf_path: str | Path,
    api_key: str | None = None,
    max_pages: int = 5,
) -> dict[str, Any]:
    """
    Extract topic metadata from a topic PDF using Gemini (first N pages).
    Returns dict with: title, topic_number, topic_summary.
    Uses filename as fallback for title/topic_number when Gemini doesn't return them.
    """
    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    fallback_title = _parse_title_from_filename(filename)
    fallback_number = _parse_topic_number_from_filename(filename) or 1

    title = fallback_title
    topic_number = fallback_number
    topic_summary = ""

    key = (api_key or config.GEMINI_API_KEY or "").strip()
    if key:
        try:
            from pdf2image import convert_from_path
            from services.gemini_service import GeminiService

            images = convert_from_path(
                str(pdf_path),
                dpi=config.PDF_RENDER_DPI,
                fmt="PNG",
            )
            n = min(len(images), max_pages)
            if n > 0:
                gemini = GeminiService(api_key=key)
                raw_pages = []
                for i in range(n):
                    page_data, _ = gemini.extract_page(images[i], i + 1)
                    raw_pages.append(page_data)
                meta = extract_lesson_meta(raw_pages)
                if meta.get("topic_title"):
                    title = (meta["topic_title"] or "").strip() or title
                if meta.get("topic_number") is not None:
                    try:
                        topic_number = int(meta["topic_number"])
                    except (TypeError, ValueError):
                        pass
                if meta.get("topic_summary"):
                    topic_summary = (meta["topic_summary"] or "").strip()
        except Exception:
            pass

    return {
        "title": title,
        "topic_number": topic_number,
        "topic_summary": topic_summary,
    }
