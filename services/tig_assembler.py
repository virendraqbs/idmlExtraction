"""
services/tig_assembler.py — Assembles TIG raw Gemini pages into 5 schema JSON files.

Called by PipelineService when job.book_type == "TIG".
Mirrors assemble_schemas() interface: receives raw_pages + out_dir + metadata,
writes files, returns list of written file paths.

Output files:
  06_lesson.json
  07_activities.json
  13_pages.json
  14_instructional_prompts.json
  15_instructional_segments.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from utils.schema_chunks import gen_id

# ── Enum maps — raw Gemini value → schema value ───────────────────────────────

_PROMPT_TYPE_MAP = {
    "LEARNING_GOALS":              "LEARNING_GOALS",
    "LANGUAGE_GOALS":              "LANGUAGE_GOALS",
    "MULTILINGUAL_LEARNER_SUPPORT": "MULTILINGUAL_LEARNER_SUPPORT",
    "HABITS_OF_MIND":              "HABITS_OF_MIND",
    "STUDENT_LOOK_FORS":           "STUDENT_LOOK_FORS",
    "CULTIVATE_CONNECTIONS":       "CULTIVATE_CONNECTIONS",
    "COMMON_MISCONCEPTIONS":       "COMMON_MISCONCEPTIONS",
    "CONTENT_CONNECTION":          "CONTENT_CONNECTION",
    "DAILY_MATH_ROUTINES":         "DAILY_MATH_ROUTINES",
    "MATERIALS_LIST":              "MATERIALS_LIST",
    "TEACHER_STORY":               "TEACHER_STORY",
    "STUDENT_EDITION_PAGE_IMAGE":  "STUDENT_EDITION_PAGE_IMAGE",
}

_SEGMENT_TYPE_MAP = {
    "ESSENTIAL_IDEAS":             "ESSENTIAL_IDEAS",
    "ABOUT_THE_MATH":              "ABOUT_THE_MATH",
    "LESSON_STRUCTURE_AND_PACING": "LESSON_STRUCTURE_AND_PACING",
    "SETTING_THE_STAGE":           "SETTING_THE_STAGE",
    "TASK":                        "TASK",
    "CLOSING":                     "CLOSING",
    "DIFFERENTIATION_STRATEGY":    "DIFFERENTIATION_STRATEGY",
    "ONGOING_ASSESSMENT":          "ONGOING_ASSESSMENT",
    "LANGUAGE_LINK":               "LANGUAGE_LINK",
    "MATH_LANGUAGE_ROUTINE":       "MATH_LANGUAGE_ROUTINE",
    "PURPOSEFUL_QUESTIONS":        "PURPOSEFUL_QUESTIONS",
    "INTRODUCTION":                "INTRODUCTION",
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


# ── Public entry point ────────────────────────────────────────────────────────

def assemble_tig_schemas(
    pages: list[dict],
    out_dir: Path,
    source_filename: str,
    resource_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    db_module: Optional[dict] = None,
    db_topic: Optional[dict] = None,
) -> list[str]:
    """
    Assemble TIG raw pages into 5 schema JSON files written to out_dir.
    Returns list of absolute file paths written.
    """
    resource_id = resource_id or gen_id()
    lesson_id   = lesson_id   or gen_id()
    topic_id    = topic_id    or gen_id()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    output = _build_output(pages, resource_id, lesson_id, topic_id,
                           source_filename, db_module, db_topic)

    file_map = {
        "06_lesson.json":                 output["lesson"],
        "07_activities.json":             output["activities"],
        "13_pages.json":                  output["pages"],
        "14_instructional_prompts.json":  output["instructional_prompts"],
        "15_instructional_segments.json": output["instructional_segments"],
    }

    written: list[str] = []
    for fname, data in file_map.items():
        fpath = out_dir / fname
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(fpath))

    return written


# ── Assembly logic ────────────────────────────────────────────────────────────

def _build_output(
    raw_pages: list[dict],
    resource_id: str,
    lesson_id: str,
    topic_id: str,
    filename: str,
    db_module: Optional[dict],
    db_topic: Optional[dict],
) -> dict[str, Any]:

    # ── Lesson metadata: prefer DB, then Gemini extraction, then filename ──
    lesson_meta = _find_lesson_meta(raw_pages)

    lesson_number  = _int(lesson_meta.get("lesson_number"), 1)
    lesson_title   = _str(lesson_meta.get("title")) or _title_from_filename(filename)
    lesson_summary = _str(lesson_meta.get("lesson_summary"))
    learning_goals = [g for g in (lesson_meta.get("learning_goals") or []) if g]
    pacing_guide   = _collect_pacing_guide(raw_pages)

    # DB overrides
    if db_module:
        module_number = db_module.get("module_number") or lesson_meta.get("module_number")
        module_title  = db_module.get("title")         or _str(lesson_meta.get("module_title"))
    else:
        module_number = lesson_meta.get("module_number")
        module_title  = _str(lesson_meta.get("module_title"))

    if db_topic:
        topic_number = db_topic.get("topic_number") or lesson_meta.get("topic_number")
        topic_title  = db_topic.get("title")        or _str(lesson_meta.get("topic_title"))
    else:
        topic_number = lesson_meta.get("topic_number")
        topic_title  = _str(lesson_meta.get("topic_title"))

    # ── Activities ────────────────────────────────────────────────────────────
    activity_objects: list[dict] = []
    activity_title_to_id: dict[str, str] = {}
    activity_seq = 0

    for p in raw_pages:
        for act in (p.get("activities") or []):
            a_type = _ACTIVITY_TYPE_MAP.get((act.get("activity_type") or "").upper())
            if not a_type:
                continue
            a_title = _str(act.get("title")) or a_type.title()
            if a_title in activity_title_to_id:
                # Merge directions if the existing entry has none yet
                a_id = activity_title_to_id[a_title]
                existing = next(x for x in activity_objects if x["id"] == a_id)
                new_dirs = _build_directions(act.get("directions") or [])
                if new_dirs and not existing.get("directions"):
                    existing["directions"] = new_dirs
                continue
            activity_seq += 1
            a_id = gen_id()
            activity_title_to_id[a_title] = a_id
            tg_raw  = act.get("teacher_guidance") or {}
            pacing  = (act.get("metadata") or {}).get("pacing_minutes")
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

    activity_refs = [
        {"id": a["id"], "type": "ACTIVITY", "sequenceNumber": i + 1}
        for i, a in enumerate(activity_objects)
    ]

    # ── 06_lesson ─────────────────────────────────────────────────────────────
    lesson_json = {
        "id":            lesson_id,
        "topicId":       topic_id,
        "lessonNumber":  lesson_number,
        "title":         lesson_title,
        "lessonSummary": lesson_summary,
        "learningGoals": learning_goals,
        "standardsBlock": gen_id(),   # placeholder; no standards extraction for TIG
        "activities":    activity_refs,
        "lessonStructureAndPacingGuide": pacing_guide,
        "metadata": {
            "moduleNumber": _int(module_number) if module_number else None,
            "moduleTitle":  module_title,
            "topicNumber":  _int(topic_number)  if topic_number  else None,
            "topicTitle":   topic_title,
        },
    }

    # ── 07_activities ─────────────────────────────────────────────────────────
    activities_json = {
        "count":      len(activity_objects),
        "activities": activity_objects,
    }

    # ── 13_pages ──────────────────────────────────────────────────────────────
    page_objects: list[dict] = []
    for p in raw_pages:
        ptype = p.get("page_type") or "UNKNOWN"
        if ptype not in _TIG_PAGE_TYPES:
            continue
        page_objects.append({
            "id":         gen_id(),
            "resourceId": resource_id,
            "pageNumber": p.get("page_number"),
            "pageType":   ptype,
            "contentBlocks": [{"id": lesson_id, "type": "LESSON"}],
            "metadata": {
                "pageNumberRepresentations": {
                    "display": str(p.get("page_number") or "")
                },
                "lessonContext": {
                    "moduleNumber": _int(module_number) if module_number else None,
                    "moduleTitle":  module_title,
                    "topicNumber":  _int(topic_number)  if topic_number  else None,
                    "topicTitle":   topic_title,
                    "lessonNumber": lesson_number,
                    "lessonTitle":  lesson_title,
                },
            },
        })

    pages_json = {"count": len(page_objects), "pages": page_objects}

    # ── 14_instructional_prompts ──────────────────────────────────────────────
    prompt_objects: list[dict] = []
    seen_prompts: set[str] = set()

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
            ref_id    = activity_title_to_id.get(ref_title, "") if ref_title else ""
            prompt_objects.append({
                "id":                        gen_id(),
                "studentContentReferenceId": ref_id or lesson_id,
                "instructionalPromptType":   schema_type,
                "title":                     title,
                "content":                   _str(ip.get("content")),
                "contentItems":              [i for i in (ip.get("content_items") or []) if i],
                "metadata": {"displayStyle": ip.get("display_style") or "BOX"},
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
            title     = _str(seg.get("title"))
            ref_title = _str(seg.get("student_content_reference_title"))
            key = f"{schema_type}:{title}:{ref_title}"
            if key in seen_segments:
                continue
            seen_segments.add(key)
            directions = _build_segment_directions(seg.get("directions") or [])
            if not directions:
                continue
            ref_id = activity_title_to_id.get(ref_title, "") if ref_title else ""
            segment_objects.append({
                "id":                        gen_id(),
                "studentContentReferenceId": ref_id or lesson_id,
                "instructionalSegmentType":  schema_type,
                "title":                     title,
                "directions":                directions,
            })

    instructional_segments_json = {
        "count":                 len(segment_objects),
        "instructionalSegments": segment_objects,
    }

    return {
        "lesson":                 lesson_json,
        "activities":             activities_json,
        "pages":                  pages_json,
        "instructional_prompts":  instructional_prompts_json,
        "instructional_segments": instructional_segments_json,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_lesson_meta(raw_pages: list[dict]) -> dict:
    """Return the lesson dict from the first TIG_LESSON_OVERVIEW page, else first non-empty."""
    for p in raw_pages:
        if p.get("page_type") == "TIG_LESSON_OVERVIEW":
            lm = p.get("lesson") or {}
            if lm.get("title") or lm.get("lesson_number"):
                return lm
    for p in raw_pages:
        lm = p.get("lesson") or {}
        if lm.get("title") or lm.get("lesson_number"):
            return lm
    return {}


def _build_directions(raw: list[dict]) -> list[dict]:
    out = []
    for i, d in enumerate(raw, 1):
        text = _str(d.get("text"))
        if not text:
            continue
        out.append({
            "sequenceNumber": _int(d.get("sequence_number"), i),
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
            "sequenceNumber": _int(d.get("sequence_number"), i),
            "text":           text,
        })
    return out


def _str(v: Any) -> Optional[str]:
    return str(v).strip() if v else None


def _int(v: Any, default: int = 1) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _title_from_filename(filename: str) -> str:
    m = re.search(r"L(\d{1,2})", Path(filename).stem, re.IGNORECASE)
    if m:
        return f"Lesson {int(m.group(1))}"
    return Path(filename).stem.replace("_", " ").strip() or "Lesson"


# ── Lesson Structure and Pacing Guide ─────────────────────────────────────────

_PACING_BLOCK_VALUES = {
    "ACTIVATE": "Activate",
    "EXPLORE AND DEVELOP": "Explore and Develop",
    "EXPLORE": "Explore and Develop",  # tolerant alias
    "REFLECT": "Reflect",
}
_PACING_MODE_VALUES = {"presentation", "book"}


def _collect_pacing_guide(raw_pages: list[dict]) -> list[dict]:
    """
    Walk every page's lesson.lesson_structure_and_pacing_guide array,
    normalize block + mode strings, drop placeholder rows where Gemini
    returned the prompt template literally.
    """
    out: list[dict] = []
    seen: set[tuple] = set()
    for p in raw_pages:
        rows = ((p.get("lesson") or {}).get("lesson_structure_and_pacing_guide") or [])
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            block = (r.get("block") or "").strip()
            block_norm = _PACING_BLOCK_VALUES.get(block.upper())
            if not block_norm:
                continue   # skip placeholder/UNKNOWN/None
            session = r.get("session")
            try:
                session_int = int(session)
            except (TypeError, ValueError):
                continue
            title = _str(r.get("title")) or ""
            duration = _str(r.get("duration")) or ""
            mode_raw = (r.get("mode") or "").strip().lower()
            mode = mode_raw if mode_raw in _PACING_MODE_VALUES else None
            strategies_raw = r.get("strategies") or []
            if isinstance(strategies_raw, str):
                strategies = [s.strip() for s in re.split(r",|\n", strategies_raw) if s.strip()]
            elif isinstance(strategies_raw, list):
                strategies = [str(s).strip() for s in strategies_raw if str(s).strip()]
            else:
                strategies = []
            key = (session_int, block_norm, title)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "session":    session_int,
                "block":      block_norm,
                "title":      title,
                "strategies": strategies,
                "duration":   duration,
                "mode":       mode,
            })
    out.sort(key=lambda r: (r["session"], ["Activate", "Explore and Develop", "Reflect"].index(r["block"])
                            if r["block"] in ("Activate", "Explore and Develop", "Reflect") else 99))
    return out
