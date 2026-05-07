#!/usr/bin/env python3
"""
Extract Teacher Implementation Guide (TIG) data from a CL TIG PDF and output
JSON files matching CL-Json-Schema structure.

Produces (to --output-dir or stdout when --single):
  06_lesson.json               – lesson + learningGoals
  07_activities.json           – activities with directions + teacherGuidance
  13_pages.json                – TIG page objects (TIG_LESSON_* page types)
  14_instructional_prompts.json – LEARNING_GOALS, HABITS_OF_MIND, COMMON_MISCONCEPTIONS, etc.
  15_instructional_segments.json – ABOUT_THE_MATH, LESSON_STRUCTURE_AND_PACING, TASK, etc.

Usage:
  python scripts/extract_tig_pdf.py sourceFile/tig/"A1 T13 L1 TG.pdf"
  python scripts/extract_tig_pdf.py sourceFile/tig/"A1 T13 L1 TG.pdf" --output-dir outputs/tig_test
  python scripts/extract_tig_pdf.py sourceFile/tig/"A1 T13 L1 TG.pdf" --no-gemini
  python scripts/extract_tig_pdf.py sourceFile/tig/"A1 T13 L1 TG.pdf" --max-pages 5 --validate

Requires: GEMINI_API_KEY in .env (or pass --api-key). Poppler must be installed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import config
from utils.schema_chunks import gen_id, now_iso


# ─────────────────────────────────────────────────────────────────────────────
# TIG Gemini prompt
# ─────────────────────────────────────────────────────────────────────────────

TIG_PROMPT = """You are a precision structured-data extractor for Carnegie Learning
Teacher Implementation Guide (TIG) PDFs.
You receive ONE page image from a TIG. Extract EVERYTHING visible.

═══ OUTPUT RULES ═══
- Return ONLY valid JSON. Zero markdown fences. Zero explanation.
- Use null for absent scalar fields. Use [] for absent arrays.
- All id fields must be empty string "".
- Preserve EXACT wording. Multi-line text: join with \\n.

═══ PAGE TYPE ═══
Set page_type to the FIRST matching rule:
  TIG_LESSON_OVERVIEW          → page shows lesson title, learning goals, language goals,
                                  lesson summary, pacing overview, materials list, or
                                  "My Learning Goals" section
  TIG_LESSON_ACTIVATE          → page covers the ACTIVATE activity teacher guidance
  TIG_LESSON_EXPLORE           → page covers EXPLORE activity teacher guidance
  TIG_LESSON_EXPLORE_CONTINUED → continuation of an EXPLORE (no new activity heading at top)
  TIG_LESSON_REFLECT           → page covers REFLECT / closing activity teacher guidance
  TIG_NOTES                    → blank or lined notes page
  NON_CONTENT                  → table of contents, glossary, cover, appendix
  UNKNOWN                      → cannot determine

═══ LESSON METADATA (overview pages only) ═══
lesson.lesson_number   : integer — lesson number shown in header/title
lesson.title           : exact lesson title text
lesson.lesson_summary  : paragraph summarising the lesson (if present)
lesson.learning_goals  : array of "I can…" strings
lesson.module_title    : module title if visible
lesson.module_number   : integer module number if visible
lesson.topic_title     : topic title if visible
lesson.topic_number    : integer topic number if visible

═══ ACTIVITIES ═══
For each ACTIVATE / EXPLORE / REFLECT / KEY_TERMS / PRACTICE_QUESTIONS activity block:
  activity_type  : ACTIVATE | EXPLORE | REFLECT | KEY_TERMS | PRACTICE_QUESTIONS
  title          : activity title text
  sequence_number: integer order within the lesson (1-based)
  teacher_guidance:
    instructional_text: purpose/driver text ("Purpose: To…", "Driver of Investigation: …")
    linked_student_activity_title: the matching student activity title if mentioned
  directions: array of {sequence_number, type:"DIRECTION_LINE", text} — each teacher step

═══ INSTRUCTIONAL PROMPTS ═══
Extract every sidebar/callout/box that belongs to one of these types:
  LEARNING_GOALS            → "My Learning Goals" box
  LANGUAGE_GOALS            → "Language Goal" box
  MULTILINGUAL_LEARNER_SUPPORT → "Multilingual Learner Support/Supports" box
  HABITS_OF_MIND            → "Habits of Mind" / "Mathematical Practice" box
  STUDENT_LOOK_FORS         → "Student Look-Fors" box
  CULTIVATE_CONNECTIONS     → "Cultivate Connections" box
  COMMON_MISCONCEPTIONS     → "Common Misconception" callout
  CONTENT_CONNECTION        → "Content Connection" box
  DAILY_MATH_ROUTINES       → "Daily Math Routines" / "Math Language Routine" box
  MATERIALS_LIST            → "Materials" list
  TEACHER_STORY             → narrative teacher story or scenario

For each prompt:
  instructional_prompt_type: one of the types above
  title       : box/callout heading text
  content     : paragraph content (or null)
  content_items: array of bullet strings (or [])
  display_style: BOX | SIDEBAR | CALLOUT | INLINE

═══ INSTRUCTIONAL SEGMENTS ═══
Extract structured lesson segments from the page:
  ESSENTIAL_IDEAS           → "Essential Ideas" bulleted list
  ABOUT_THE_MATH            → "About the Math" / math background paragraph
  LESSON_STRUCTURE_AND_PACING → pacing/session breakdown table or list
  SETTING_THE_STAGE         → "Setting the Stage" directions for launching the lesson
  TASK                      → per-activity instructional steps (numbered steps for teacher)
  CLOSING                   → "Session Close" / wrap-up directions
  DIFFERENTIATION_STRATEGY  → differentiation / extension notes
  ONGOING_ASSESSMENT        → formative assessment guidance
  LANGUAGE_LINK             → "Language Link" vocabulary note
  MATH_LANGUAGE_ROUTINE     → "Math Language Routine: MLR …" section
  PURPOSEFUL_QUESTIONS      → "Purposeful Questions" list

For each segment:
  instructional_segment_type: one of the types above
  title: segment heading text (or null)
  student_content_reference_title: title of the activity/lesson this segment applies to (or null)
  directions: array of {sequence_number, text} — each instruction line or bullet

═══ RETURN EXACTLY THIS JSON ═══
{
  "page_number": null,
  "page_type": "TIG_LESSON_OVERVIEW | TIG_LESSON_ACTIVATE | TIG_LESSON_EXPLORE | TIG_LESSON_EXPLORE_CONTINUED | TIG_LESSON_REFLECT | TIG_NOTES | NON_CONTENT | UNKNOWN",
  "lesson": {
    "lesson_number": null, "title": null, "lesson_summary": null,
    "learning_goals": [],
    "module_title": null, "module_number": null,
    "topic_title": null, "topic_number": null
  },
  "activities": [
    {
      "id": "",
      "activity_type": "ACTIVATE | EXPLORE | REFLECT | KEY_TERMS | PRACTICE_QUESTIONS",
      "title": "",
      "sequence_number": 1,
      "teacher_guidance": {
        "instructional_text": null,
        "linked_student_activity_title": null
      },
      "directions": [
        {"sequence_number": 1, "type": "DIRECTION_LINE", "text": ""}
      ],
      "metadata": {"pacing_minutes": null}
    }
  ],
  "instructional_prompts": [
    {
      "id": "",
      "instructional_prompt_type": "LEARNING_GOALS | LANGUAGE_GOALS | MULTILINGUAL_LEARNER_SUPPORT | HABITS_OF_MIND | STUDENT_LOOK_FORS | CULTIVATE_CONNECTIONS | COMMON_MISCONCEPTIONS | CONTENT_CONNECTION | DAILY_MATH_ROUTINES | MATERIALS_LIST | TEACHER_STORY",
      "title": null,
      "content": null,
      "content_items": [],
      "display_style": "BOX | SIDEBAR | CALLOUT | INLINE",
      "student_content_reference_title": null
    }
  ],
  "instructional_segments": [
    {
      "id": "",
      "instructional_segment_type": "ESSENTIAL_IDEAS | ABOUT_THE_MATH | LESSON_STRUCTURE_AND_PACING | SETTING_THE_STAGE | TASK | CLOSING | DIFFERENTIATION_STRATEGY | ONGOING_ASSESSMENT | LANGUAGE_LINK | MATH_LANGUAGE_ROUTINE | PURPOSEFUL_QUESTIONS",
      "title": null,
      "student_content_reference_title": null,
      "directions": [
        {"sequence_number": 1, "text": ""}
      ]
    }
  ]
}

If this page has NO teacher content (blank, notes, cover), return page_type "NON_CONTENT"
and null/[] for everything else."""


# ─────────────────────────────────────────────────────────────────────────────
# Gemini extraction
# ─────────────────────────────────────────────────────────────────────────────

import time as _time
import logging

log = logging.getLogger(__name__)
_BACKOFF = (10, 20, 40, 60)


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
    return text.strip()


def extract_tig_page(page_image: Any, page_number: int, model: Any) -> dict:
    """Send one TIG page image to Gemini; return parsed dict."""
    last_err = None
    for attempt in range(1, 5):
        try:
            resp = model.generate_content([TIG_PROMPT, page_image])
            raw  = _strip_fences((resp.text or "").strip())
            data = json.loads(raw)
            data["page_number"] = data.get("page_number") or page_number
            return data
        except Exception as exc:
            last_err = exc
            msg = str(exc).lower()
            if any(k in msg for k in ("429", "rate", "quota", "exhausted")):
                delay = _BACKOFF[min(attempt - 1, 3)]
                print(f"  [rate-limit] page {page_number} attempt {attempt} — wait {delay}s", file=sys.stderr)
                _time.sleep(delay)
            else:
                print(f"  [error] page {page_number} attempt {attempt}: {exc}", file=sys.stderr)
                _time.sleep(3)
    print(f"  [failed] page {page_number} after 4 attempts: {last_err}", file=sys.stderr)
    return {"page_number": page_number, "page_type": "UNKNOWN",
            "lesson": {}, "activities": [], "instructional_prompts": [],
            "instructional_segments": []}


# ─────────────────────────────────────────────────────────────────────────────
# Assembly helpers — build schema-compliant JSON from raw pages
# ─────────────────────────────────────────────────────────────────────────────

# Map raw Gemini instructional_prompt_type → schema InstructionalPromptType
_PROMPT_TYPE_MAP = {
    "LEARNING_GOALS":             "LEARNING_GOALS",
    "LANGUAGE_GOALS":             "LANGUAGE_GOALS",
    "MULTILINGUAL_LEARNER_SUPPORT": "MULTILINGUAL_LEARNER_SUPPORT",
    "HABITS_OF_MIND":             "HABITS_OF_MIND",
    "STUDENT_LOOK_FORS":          "STUDENT_LOOK_FORS",
    "CULTIVATE_CONNECTIONS":      "CULTIVATE_CONNECTIONS",
    "COMMON_MISCONCEPTIONS":      "COMMON_MISCONCEPTIONS",
    "CONTENT_CONNECTION":         "CONTENT_CONNECTION",
    "DAILY_MATH_ROUTINES":        "DAILY_MATH_ROUTINES",
    "MATERIALS_LIST":             "MATERIALS_LIST",
    "TEACHER_STORY":              "TEACHER_STORY",
    "STUDENT_EDITION_PAGE_IMAGE": "STUDENT_EDITION_PAGE_IMAGE",
}

_SEGMENT_TYPE_MAP = {
    "ESSENTIAL_IDEAS":            "ESSENTIAL_IDEAS",
    "ABOUT_THE_MATH":             "ABOUT_THE_MATH",
    "LESSON_STRUCTURE_AND_PACING": "LESSON_STRUCTURE_AND_PACING",
    "SETTING_THE_STAGE":          "SETTING_THE_STAGE",
    "TASK":                       "TASK",
    "CLOSING":                    "CLOSING",
    "DIFFERENTIATION_STRATEGY":   "DIFFERENTIATION_STRATEGY",
    "ONGOING_ASSESSMENT":         "ONGOING_ASSESSMENT",
    "LANGUAGE_LINK":              "LANGUAGE_LINK",
    "MATH_LANGUAGE_ROUTINE":      "MATH_LANGUAGE_ROUTINE",
    "PURPOSEFUL_QUESTIONS":       "PURPOSEFUL_QUESTIONS",
    "INTRODUCTION":               "INTRODUCTION",
}

_ACTIVITY_TYPE_MAP = {
    "ACTIVATE":           "ACTIVATE",
    "EXPLORE":            "EXPLORE",
    "REFLECT":            "REFLECT",
    "KEY_TERMS":          "KEY_TERMS",
    "PRACTICE_QUESTIONS": "PRACTICE_QUESTIONS",
}

_TIG_PAGE_TYPES = {
    "TIG_LESSON_OVERVIEW",
    "TIG_LESSON_ACTIVATE",
    "TIG_LESSON_EXPLORE",
    "TIG_LESSON_EXPLORE_CONTINUED",
    "TIG_LESSON_REFLECT",
    "TIG_NOTES",
}


def _coerce_int(v: Any, default: int = 1) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _str(v: Any) -> str | None:
    return str(v).strip() if v else None


def assemble_tig_json(
    raw_pages: list[dict],
    resource_id: str,
    lesson_id: str,
    topic_id: str,
    filename: str,
) -> dict[str, Any]:
    """
    Assemble all raw TIG pages into schema-compliant output objects.
    Returns a dict with keys: lesson, activities, pages, instructional_prompts,
    instructional_segments.
    """

    # ── Gather lesson metadata from the first overview page ──
    lesson_meta: dict = {}
    for p in raw_pages:
        if p.get("page_type") == "TIG_LESSON_OVERVIEW":
            lesson_meta = p.get("lesson") or {}
            break
    if not lesson_meta:
        # Fallback: first page with any lesson data
        for p in raw_pages:
            lm = p.get("lesson") or {}
            if lm.get("title") or lm.get("lesson_number"):
                lesson_meta = lm
                break

    lesson_number  = _coerce_int(lesson_meta.get("lesson_number"), 1)
    lesson_title   = _str(lesson_meta.get("title")) or _parse_title_from_filename(filename)
    lesson_summary = _str(lesson_meta.get("lesson_summary"))
    learning_goals = [g for g in (lesson_meta.get("learning_goals") or []) if g]
    module_number  = lesson_meta.get("module_number")
    module_title   = _str(lesson_meta.get("module_title"))
    topic_number   = lesson_meta.get("topic_number")
    topic_ttl      = _str(lesson_meta.get("topic_title"))

    # ── 06_lesson ──────────────────────────────────────────────────────────────
    activity_refs: list[dict] = []
    activity_objects: list[dict] = []
    seen_activity_titles: dict[str, str] = {}  # title → id
    activity_seq = 0

    for p in raw_pages:
        for act in (p.get("activities") or []):
            a_type = _ACTIVITY_TYPE_MAP.get((act.get("activity_type") or "").upper())
            if not a_type:
                continue
            a_title = _str(act.get("title")) or a_type.title()
            # Deduplicate by title
            if a_title in seen_activity_titles:
                a_id = seen_activity_titles[a_title]
                # Merge directions if new ones found
                existing = next(x for x in activity_objects if x["id"] == a_id)
                new_dirs = _build_directions(act.get("directions") or [])
                if new_dirs and not existing.get("directions"):
                    existing["directions"] = new_dirs
                continue
            activity_seq += 1
            a_id = gen_id()
            seen_activity_titles[a_title] = a_id
            tg_raw   = act.get("teacher_guidance") or {}
            pacing   = (act.get("metadata") or {}).get("pacing_minutes")
            activity_objects.append({
                "id":           a_id,
                "lessonId":     lesson_id,
                "activityType": a_type,
                "title":        a_title,
                "directions":   _build_directions(act.get("directions") or []),
                "teacherGuidance": {
                    "linkedStudentActivity": {
                        "studentActivityId": "",
                        "linkType": "SUPPORTS",
                    },
                    "instructionalText": _str(tg_raw.get("instructional_text")),
                } if tg_raw else None,
                "metadata": {"pacingEstimate": {"minutes": int(pacing)}} if pacing else {},
            })
            activity_refs.append({
                "id":             a_id,
                "type":           "ACTIVITY",
                "sequenceNumber": activity_seq,
            })

    standards_block_id = gen_id()  # placeholder — no standards extraction in TIG script

    lesson_json = {
        "id":             lesson_id,
        "topicId":        topic_id,
        "lessonNumber":   lesson_number,
        "title":          lesson_title,
        "lessonSummary":  lesson_summary,
        "learningGoals":  learning_goals,
        "standardsBlock": standards_block_id,
        "activities":     activity_refs,
        "metadata": {
            "moduleNumber": _coerce_int(module_number) if module_number else None,
            "moduleTitle":  module_title,
            "topicNumber":  _coerce_int(topic_number) if topic_number else None,
            "topicTitle":   topic_ttl,
        },
    }

    # ── 07_activities ──────────────────────────────────────────────────────────
    activities_json = {
        "count":      len(activity_objects),
        "activities": activity_objects,
    }

    # ── 13_pages ───────────────────────────────────────────────────────────────
    page_objects: list[dict] = []
    seen_page_types: dict[str, int] = {}  # track occurrence count per type
    for p in raw_pages:
        ptype = p.get("page_type") or "UNKNOWN"
        if ptype not in _TIG_PAGE_TYPES:
            continue
        seen_page_types[ptype] = seen_page_types.get(ptype, 0) + 1
        page_objects.append({
            "id":           gen_id(),
            "resourceId":   resource_id,
            "pageNumber":   p.get("page_number"),
            "pageType":     ptype,
            "contentBlocks": [{"id": lesson_id, "type": "LESSON"}],
            "metadata": {
                "pageNumberRepresentations": {
                    "display": str(p.get("page_number") or "")
                },
                "lessonContext": {
                    "moduleNumber": _coerce_int(module_number) if module_number else None,
                    "moduleTitle":  module_title,
                    "topicNumber":  _coerce_int(topic_number) if topic_number else None,
                    "topicTitle":   topic_ttl,
                    "lessonNumber": lesson_number,
                    "lessonTitle":  lesson_title,
                },
            },
        })

    pages_json = {
        "count": len(page_objects),
        "pages": page_objects,
    }

    # ── 14_instructional_prompts ───────────────────────────────────────────────
    prompt_objects: list[dict] = []
    seen_prompts: set[str] = set()  # deduplicate by type+title

    for p in raw_pages:
        for ip in (p.get("instructional_prompts") or []):
            raw_type = (ip.get("instructional_prompt_type") or "").upper()
            schema_type = _PROMPT_TYPE_MAP.get(raw_type)
            if not schema_type:
                continue
            title = _str(ip.get("title"))
            key = f"{schema_type}:{title}"
            if key in seen_prompts:
                continue
            seen_prompts.add(key)
            ref_title = _str(ip.get("student_content_reference_title"))
            # Resolve student_content_ref_id from activity title if possible
            ref_id = seen_activity_titles.get(ref_title, "") if ref_title else ""
            prompt_objects.append({
                "id":                       gen_id(),
                "studentContentReferenceId": ref_id or lesson_id,
                "instructionalPromptType":  schema_type,
                "title":                    title,
                "content":                  _str(ip.get("content")),
                "contentItems":             [i for i in (ip.get("content_items") or []) if i],
                "metadata": {
                    "displayStyle": ip.get("display_style") or "BOX"
                },
            })

    instructional_prompts_json = {
        "count":               len(prompt_objects),
        "instructionalPrompts": prompt_objects,
    }

    # ── 15_instructional_segments ─────────────────────────────────────────────
    segment_objects: list[dict] = []
    seen_segments: set[str] = set()

    for p in raw_pages:
        for seg in (p.get("instructional_segments") or []):
            raw_type = (seg.get("instructional_segment_type") or "").upper()
            schema_type = _SEGMENT_TYPE_MAP.get(raw_type)
            if not schema_type:
                continue
            title = _str(seg.get("title"))
            ref_title = _str(seg.get("student_content_reference_title"))
            key = f"{schema_type}:{title}:{ref_title}"
            if key in seen_segments:
                continue
            seen_segments.add(key)
            ref_id = seen_activity_titles.get(ref_title, "") if ref_title else ""
            directions = _build_segment_directions(seg.get("directions") or [])
            if not directions:
                continue  # skip empty segments
            segment_objects.append({
                "id":                        gen_id(),
                "studentContentReferenceId":  ref_id or lesson_id,
                "instructionalSegmentType":   schema_type,
                "title":                      title,
                "directions":                 directions,
            })

    instructional_segments_json = {
        "count":                 len(segment_objects),
        "instructionalSegments": segment_objects,
    }

    return {
        "lesson":                   lesson_json,
        "activities":               activities_json,
        "pages":                    pages_json,
        "instructional_prompts":    instructional_prompts_json,
        "instructional_segments":   instructional_segments_json,
    }


def _build_directions(raw: list[dict]) -> list[dict]:
    out = []
    for i, d in enumerate(raw, 1):
        text = _str(d.get("text"))
        if not text:
            continue
        out.append({
            "sequenceNumber": _coerce_int(d.get("sequence_number"), i),
            "type":           "DIRECTION_LINE",
            "text":           text,
        })
    return out


def _build_segment_directions(raw: list[dict]) -> list[dict]:
    out = []
    for i, d in enumerate(raw, 1):
        text = _str(d.get("text"))
        if not text:
            continue
        out.append({
            "sequenceNumber": _coerce_int(d.get("sequence_number"), i),
            "text":           text,
        })
    return out


def _parse_title_from_filename(filename: str) -> str:
    """e.g. 'A1 T13 L1 TG.pdf' → 'Lesson 1'."""
    m = re.search(r"L(\d{1,2})", Path(filename).stem, re.IGNORECASE)
    if m:
        return f"Lesson {int(m.group(1))}"
    return Path(filename).stem.replace("_", " ").strip() or "Lesson"


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

def _is_uuid(v: Any) -> bool:
    return bool(v and isinstance(v, str) and _UUID_RE.match(v.lower()))


def validate_output(output: dict) -> list[str]:
    """Return a list of validation error strings (empty = pass)."""
    errors = []

    lesson = output.get("lesson", {})
    if not _is_uuid(lesson.get("id")):
        errors.append("lesson.id must be a UUID")
    if not _is_uuid(lesson.get("topicId")):
        errors.append("lesson.topicId must be a UUID")
    if not isinstance(lesson.get("lessonNumber"), int):
        errors.append("lesson.lessonNumber must be an integer")
    if not lesson.get("title"):
        errors.append("lesson.title is required")

    for i, act in enumerate(output.get("activities", {}).get("activities", [])):
        if not _is_uuid(act.get("id")):
            errors.append(f"activities[{i}].id must be a UUID")
        if not _is_uuid(act.get("lessonId")):
            errors.append(f"activities[{i}].lessonId must be a UUID")
        if not act.get("activityType"):
            errors.append(f"activities[{i}].activityType is required")

    for i, pg in enumerate(output.get("pages", {}).get("pages", [])):
        if not _is_uuid(pg.get("id")):
            errors.append(f"pages[{i}].id must be a UUID")
        if not pg.get("pageType"):
            errors.append(f"pages[{i}].pageType is required")

    for i, ip in enumerate(output.get("instructional_prompts", {}).get("instructionalPrompts", [])):
        if not _is_uuid(ip.get("id")):
            errors.append(f"instructional_prompts[{i}].id must be a UUID")
        if not ip.get("instructionalPromptType"):
            errors.append(f"instructional_prompts[{i}].instructionalPromptType is required")

    for i, seg in enumerate(output.get("instructional_segments", {}).get("instructionalSegments", [])):
        if not _is_uuid(seg.get("id")):
            errors.append(f"instructional_segments[{i}].id must be a UUID")
        if not seg.get("instructionalSegmentType"):
            errors.append(f"instructional_segments[{i}].instructionalSegmentType is required")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract TIG PDF → schema-compliant JSON (lesson, activities, pages, "
                    "instructional_prompts, instructional_segments).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the TIG PDF (absolute or relative to project root)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Directory to write JSON files. If omitted, prints single combined JSON to stdout.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit pages sent to Gemini (useful for quick tests; default: all pages)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API key (default: GEMINI_API_KEY from .env)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini model name (default: GEMINI_MODEL from .env)",
    )
    parser.add_argument(
        "--resource-id",
        default=None,
        help="Resource UUID to embed in page objects (default: generate)",
    )
    parser.add_argument(
        "--lesson-id",
        default=None,
        help="Lesson UUID (default: generate)",
    )
    parser.add_argument(
        "--topic-id",
        default=None,
        help="Topic UUID (default: generate)",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Skip Gemini; build skeleton JSON from filename only (for structure testing)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run schema validation on output and report errors",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Also save raw Gemini page-by-page responses to <output-dir>/raw_pages.json",
    )

    args = parser.parse_args()

    # ── Resolve paths ──
    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = _PROJECT_ROOT / pdf_path
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    api_key   = args.api_key or config.GEMINI_API_KEY
    model_name = args.model or config.GEMINI_MODEL or "gemini-2.5-flash"

    if not args.no_gemini and not api_key:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set it in .env.", file=sys.stderr)
        return 1

    resource_id = args.resource_id or gen_id()
    lesson_id   = args.lesson_id   or gen_id()
    topic_id    = args.topic_id    or gen_id()

    # ── Render PDF pages ──
    raw_pages: list[dict] = []

    if args.no_gemini:
        print("[no-gemini] Building skeleton from filename only.", file=sys.stderr)
        raw_pages = [{
            "page_number": 1,
            "page_type": "TIG_LESSON_OVERVIEW",
            "lesson": {
                "lesson_number": None,
                "title": _parse_title_from_filename(pdf_path.name),
                "lesson_summary": None,
                "learning_goals": [],
                "module_title": None, "module_number": None,
                "topic_title": None,  "topic_number": None,
            },
            "activities": [],
            "instructional_prompts": [],
            "instructional_segments": [],
        }]
    else:
        print(f"Rendering PDF: {pdf_path.name}", file=sys.stderr)
        try:
            from pdf2image import convert_from_path
        except ImportError:
            print("Error: pdf2image not installed. Run: pip install pdf2image", file=sys.stderr)
            return 1

        try:
            images = convert_from_path(str(pdf_path), dpi=config.PDF_RENDER_DPI, fmt="PNG")
        except Exception as exc:
            print(f"Error rendering PDF: {exc}", file=sys.stderr)
            return 1

        n_pages = len(images)
        if args.max_pages:
            n_pages = min(n_pages, args.max_pages)
        print(f"Extracted {len(images)} page(s); processing {n_pages}.", file=sys.stderr)

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"temperature": 0.1, "max_output_tokens": 16384},
            )
        except Exception as exc:
            print(f"Error initialising Gemini: {exc}", file=sys.stderr)
            return 1

        for i in range(n_pages):
            pg_num = i + 1
            print(f"  Page {pg_num}/{n_pages}…", file=sys.stderr, end=" ")
            page_data = extract_tig_page(images[i], pg_num, model)
            ptype = page_data.get("page_type", "UNKNOWN")
            print(ptype, file=sys.stderr)
            raw_pages.append(page_data)

    # ── Assemble output ──
    print("Assembling JSON…", file=sys.stderr)
    output = assemble_tig_json(raw_pages, resource_id, lesson_id, topic_id, pdf_path.name)

    # ── Validate ──
    if args.validate:
        errors = validate_output(output)
        if errors:
            print("\nValidation FAILED:", file=sys.stderr)
            for e in errors:
                print(f"  ✗ {e}", file=sys.stderr)
        else:
            print("Validation OK — all required fields present.", file=sys.stderr)

    # ── Write output ──
    file_map = {
        "06_lesson.json":                   output["lesson"],
        "07_activities.json":               output["activities"],
        "13_pages.json":                    output["pages"],
        "14_instructional_prompts.json":    output["instructional_prompts"],
        "15_instructional_segments.json":   output["instructional_segments"],
    }

    if args.output_dir:
        out_dir = Path(args.output_dir)
        if not out_dir.is_absolute():
            out_dir = _PROJECT_ROOT / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        for fname, data in file_map.items():
            fpath = out_dir / fname
            fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Wrote {fpath.relative_to(_PROJECT_ROOT)}", file=sys.stderr)

        if args.raw:
            raw_path = out_dir / "raw_pages.json"
            raw_path.write_text(json.dumps(raw_pages, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Wrote {raw_path.relative_to(_PROJECT_ROOT)}", file=sys.stderr)

        print(f"\nDone. {len(file_map)} files written to {out_dir.relative_to(_PROJECT_ROOT)}/", file=sys.stderr)
    else:
        # Single combined JSON to stdout
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
