#!/usr/bin/env python3
"""
Extract module-level data from a Carnegie Learning module PDF and output JSON
that matches CL-Json-Schema/schemas/content/module.json.

Usage:
  python scripts/extract_module_pdf.py <path_to_module.pdf> [--output module.json] [--max-pages 5]
  python scripts/extract_module_pdf.py "/Users/.../sourceFile/SM5e_A1_SE_MI_M01 1.pdf"

Requires: GEMINI_API_KEY in .env or --api-key. Uses pdf2image and the existing
Gemini extraction pipeline to infer title, moduleNumber, gradeLevel, moduleSummary,
and standardsBody from the first N pages. Filename patterns like M01 are used as fallback
for module number.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Project root in path so we can import config, utils (no heavy services until needed)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import config
from utils.schema_chunks import extract_lesson_meta, gen_id


def parse_module_number_from_filename(filename: str) -> int | None:
    """e.g. SM5e_A1_SE_MI_M01 1.pdf or M03_... -> 1 or 3."""
    base = Path(filename).stem
    # M01, M02, M1, M12
    m = re.search(r"M(\d{1,2})(?:\s|_|$)", base, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_title_from_filename(filename: str) -> str:
    """e.g. SM5e_A1_SE_MI_M01 1.pdf -> Module 1 or similar."""
    num = parse_module_number_from_filename(filename)
    if num is not None:
        return f"Module {num}"
    return Path(filename).stem.replace("_", " ").strip() or "Module"


def build_module_json(
    *,
    module_id: str,
    resource_id: str,
    module_number: int,
    title: str,
    grade_level: str,
    module_summary: str = "",
    standards_body: str | None = None,
    topic_refs: list[dict] | None = None,
    image_refs: list[dict] | None = None,
) -> dict:
    """Build a dict that matches schemas/content/module.json."""
    body = standards_body if standards_body in ("CCSS", "CA_CCSS", "TEKS", "BEST") else None
    return {
        "id": module_id,
        "resourceId": resource_id,
        "standardsBody": body,
        "moduleNumber": module_number,
        "title": title,
        "moduleSummary": module_summary or "",
        "images": image_refs or [],
        "gradeLevel": grade_level or "1",
        "topics": topic_refs or [],
        "metadata": {
            "localizationInfo": {"language": "en"},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract module JSON from a CL module PDF (matches module.json schema)."
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the module PDF (e.g. sourceFile/SM5e_A1_SE_MI_M01 1.pdf)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Write JSON to this file; default is stdout",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max number of PDF pages to send to Gemini (default 5)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Gemini API key (default: GEMINI_API_KEY from .env)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate output against CL-Json-Schema/schemas/content/module.json",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Skip Gemini; use filename-only fallback (title, module number)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = _PROJECT_ROOT / pdf_path
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    api_key = args.api_key or config.GEMINI_API_KEY
    if not args.no_gemini and not api_key:
        print("Error: GEMINI_API_KEY not set and --no-gemini not used.", file=sys.stderr)
        return 1

    # Fallback from filename
    filename = pdf_path.name
    fallback_module_number = parse_module_number_from_filename(filename) or 1
    fallback_title = parse_title_from_filename(filename)

    module_id = gen_id()
    resource_id = gen_id()
    topic_refs: list[dict] = []
    image_refs: list[dict] = []

    title = fallback_title
    module_number = fallback_module_number
    grade_level = "1"
    module_summary = ""
    standards_body = None

    if not args.no_gemini:
        try:
            from pdf2image import convert_from_path
        except ImportError:
            print("Error: pdf2image required. pip install pdf2image", file=sys.stderr)
            return 1
        from services.gemini_service import GeminiService

        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=config.PDF_RENDER_DPI,
                fmt="PNG",
            )
        except Exception as e:
            print(f"Error rendering PDF: {e}", file=sys.stderr)
            return 1

        n_pages = min(len(images), args.max_pages)
        if n_pages == 0:
            print("Error: PDF produced no pages.", file=sys.stderr)
            return 1

        gemini = GeminiService(api_key=api_key)
        raw_pages: list[dict] = []
        for i in range(n_pages):
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
            standards_body = (meta["standards_body"] or "").strip()

    module_json = build_module_json(
        module_id=module_id,
        resource_id=resource_id,
        module_number=module_number,
        title=title,
        grade_level=grade_level,
        module_summary=module_summary,
        standards_body=standards_body,
        topic_refs=topic_refs,
        image_refs=image_refs,
    )

    out = json.dumps(module_json, indent=2, ensure_ascii=False)

    if args.validate:
        # Required by module.json: id, moduleNumber, title, gradeLevel
        uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        required = {"id", "moduleNumber", "title", "gradeLevel"}
        missing = required - set(module_json.keys())
        if missing:
            print(f"Validation failed: missing required fields {missing}", file=sys.stderr)
            return 1
        if not uuid_re.match(module_json["id"].lower()):
            print("Validation failed: id must be a UUID", file=sys.stderr)
            return 1
        if not isinstance(module_json["moduleNumber"], int) or module_json["moduleNumber"] < 1:
            print("Validation failed: moduleNumber must be an integer >= 1", file=sys.stderr)
            return 1
        if not isinstance(module_json["title"], str) or not isinstance(module_json["gradeLevel"], str):
            print("Validation failed: title and gradeLevel must be strings", file=sys.stderr)
            return 1
        print("Validation OK (required fields and types).", file=sys.stderr)

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = _PROJECT_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
