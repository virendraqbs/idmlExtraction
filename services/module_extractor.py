"""
services/module_extractor.py — Extract module-level data from a CL module PDF using Gemini.
Used when uploading a module PDF: returns title, module_number, grade_level, module_summary, standards_body.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import config
from utils.schema_chunks import extract_lesson_meta


def _parse_module_number_from_filename(filename: str) -> int | None:
    m = re.search(r"M(\d{1,2})(?:\s|_|$)", Path(filename).stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_title_from_filename(filename: str) -> str:
    num = _parse_module_number_from_filename(filename)
    if num is not None:
        return f"Module {num}"
    return Path(filename).stem.replace("_", " ").strip() or "Module"


def extract_module_from_pdf(
    pdf_path: str | Path,
    api_key: str | None = None,
    max_pages: int = 5,
) -> dict[str, Any]:
    """
    Extract module metadata from a module PDF using Gemini (first N pages).
    Returns dict with: title, module_number, grade_level, module_summary, standards_body.
    Uses filename as fallback for title/module_number when Gemini doesn't return them.
    """
    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    fallback_title = _parse_title_from_filename(filename)
    fallback_number = _parse_module_number_from_filename(filename) or 1

    title = fallback_title
    module_number = fallback_number
    grade_level = "1"
    module_summary = ""
    standards_body = None

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
                if meta.get("module_title"):
                    title = (meta["module_title"] or "").strip() or title
                if meta.get("module_number") is not None:
                    try:
                        module_number = int(meta["module_number"])
                    except (TypeError, ValueError):
                        pass
                if meta.get("grade_level"):
                    grade_level = (meta["grade_level"] or "").strip() or grade_level
                if meta.get("module_summary"):
                    module_summary = (meta["module_summary"] or "").strip()
                if meta.get("standards_body"):
                    sb = (meta["standards_body"] or "").strip()
                    if sb in ("CCSS", "CA_CCSS", "TEKS", "BEST"):
                        standards_body = sb
        except Exception:
            pass

    return {
        "title": title,
        "module_number": module_number,
        "grade_level": grade_level,
        "module_summary": module_summary,
        "standards_body": standards_body,
    }
