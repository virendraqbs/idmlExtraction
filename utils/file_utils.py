"""
utils/file_utils.py — Stateless file-handling utilities.

Helpers for:
- Validating uploaded filenames
- Getting PDF page counts
- Reading / writing JSON output files
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import config

log = logging.getLogger(__name__)


def is_allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def get_pdf_page_count(pdf_path: str) -> int:
    """Return the number of pages in a PDF.  Tries pypdf, then pdf2image."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf_path).pages)
    except Exception:
        pass
    try:
        from pdf2image import pdfinfo_from_path
        return pdfinfo_from_path(pdf_path)["Pages"]
    except Exception:
        pass
    log.warning("Could not determine page count for %s; defaulting to 1", pdf_path)
    return 1


def write_json(path: Path, data: Any) -> None:
    """Write *data* to *path* as pretty-printed UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Any:
    """Read and return JSON from *path*."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_output_files(output_dir: Path) -> list[str]:
    """Return sorted list of JSON filenames inside *output_dir*."""
    return sorted(f.name for f in output_dir.glob("*.json"))
