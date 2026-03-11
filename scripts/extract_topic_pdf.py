#!/usr/bin/env python3
"""
Extract topic-level data from a Carnegie Learning topic PDF and output JSON
that matches CL-Json-Schema/schemas/content/topic.json.

Usage:
  python scripts/extract_topic_pdf.py <path_to_topic.pdf> [--output topic.json] [--max-pages 5]
  python scripts/extract_topic_pdf.py "/Users/.../sourceFile/SM5e_A1_SE_M01_T01_TOC.pdf"

Requires: GEMINI_API_KEY in .env or --api-key. Uses pdf2image and the existing
Gemini extraction pipeline to infer title, topicNumber, topicSummary from the
first N pages. Filename patterns like T01 are used as fallback for topic number.
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
from utils.schema_chunks import gen_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract topic JSON from a CL topic PDF (matches topic.json schema)."
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the topic PDF (e.g. sourceFile/SM5e_A1_SE_M01_T01_TOC.pdf)",
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
        "--module-id",
        type=str,
        default=None,
        help="moduleId for output (default: generate a UUID)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate output against CL-Json-Schema/schemas/content/topic.json",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Skip Gemini; use filename-only fallback (title, topic number)",
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

    from services.topic_extractor import extract_topic_from_pdf
    extracted = extract_topic_from_pdf(
        pdf_path,
        api_key="" if args.no_gemini else (api_key or None),
        max_pages=args.max_pages,
    )
    title = (extracted.get("title") or "").strip() or "Topic"
    topic_number = extracted.get("topic_number") or 1
    topic_summary = (extracted.get("topic_summary") or "").strip()

    topic_id = gen_id()
    module_id = args.module_id or gen_id()

    topic_json = {
        "id": topic_id,
        "moduleId": module_id,
        "topicNumber": topic_number,
        "title": title or "Topic",
        "topicSummary": topic_summary,
        "images": [],
        "lessons": [],
        "metadata": {},
    }

    out = json.dumps(topic_json, indent=2, ensure_ascii=False)

    if args.validate:
        uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        required = {"id", "topicNumber", "title", "moduleId"}
        missing = required - set(topic_json.keys())
        if missing:
            print(f"Validation failed: missing required fields {missing}", file=sys.stderr)
            return 1
        if not uuid_re.match(topic_json["id"].lower()) or not uuid_re.match(topic_json["moduleId"].lower()):
            print("Validation failed: id and moduleId must be UUIDs", file=sys.stderr)
            return 1
        if not isinstance(topic_json["topicNumber"], int) or topic_json["topicNumber"] < 1:
            print("Validation failed: topicNumber must be an integer >= 1", file=sys.stderr)
            return 1
        if not isinstance(topic_json["title"], str):
            print("Validation failed: title must be a string", file=sys.stderr)
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
