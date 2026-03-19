"""
utils/schema_chunks.py — Schema-chunk helpers.

Each public function builds ONE of the 18 CL-Json-Schema output objects
from the raw per-page Gemini extractions.  The assembler in
services/assembler.py calls them in order so logic stays isolated,
testable, and easy to maintain.

Naming convention:
    build_<schema_name>(...)  →  returns a plain dict ready for JSON serialisation.
"""
from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

# ── ID helpers ────────────────────────────────────────────────────────────────

def gen_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Matches generic placeholder names like "Module 1", "Topic 2", "Lesson 3",
# "Module", "Topic", "Lesson" (with or without a trailing number/whitespace).
_GENERIC_NAME_RE = re.compile(
    r"^\s*(module|topic|lesson|unit|chapter|section)\s*\d*\s*$",
    re.IGNORECASE,
)

# Matches "Module 1: ", "Topic 3: " etc. prefixes in titles
_ENTITY_NUMBER_PREFIX_RE = re.compile(
    r"^(module|topic|lesson|unit|chapter|section)\s+\d+\s*:\s*",
    re.IGNORECASE,
)


def _strip_generic_name(value: str | None) -> str | None:
    """Return None if value is a generic placeholder name (e.g. 'Module 1')."""
    if value and isinstance(value, str) and _GENERIC_NAME_RE.match(value.strip()):
        return None
    return value


def _strip_entity_number_prefix(value: str) -> str:
    """Strip 'Module N: ', 'Topic N: ', 'Lesson N: ' prefixes from titles.

    e.g. 'Module 1: Searching for Patterns' → 'Searching for Patterns'
    """
    return _ENTITY_NUMBER_PREFIX_RE.sub("", value).strip()


# ── 01 — Primitives ───────────────────────────────────────────────────────────

def build_primitives(
    *,
    resource_id: str,
    module_id: str,
    topic_id: str,
    lesson_id: str,
    std_block_id: str,
    total_pages: int,
    extracted_at: str,
) -> dict:
    """
    01_primitives.json
    All canonical UUIDs and run-level metadata in one place so downstream
    consumers can look up IDs without parsing the full entity files.
    """
    return {
        "resourceId":       resource_id,
        "moduleId":         module_id,
        "topicId":          topic_id,
        "lessonId":         lesson_id,
        "standardsBlockId": std_block_id,
        "totalPages":       total_pages,
        "extractedAt":      extracted_at,
    }


# ── 02 — Enums ────────────────────────────────────────────────────────────────

def build_enums(
    *,
    activities: list[dict],
    tasks: list[dict],
    stems: list[dict],
    images: list[dict],
    pages: list[dict],
    standards: list[dict],
    goals: list[dict] | None = None,
) -> dict:
    """
    02_enums.json
    Distinct enum values actually present in this extraction run.
    Useful for validation and UI filter-lists.
    """
    out: dict = {
        "activityTypes":   _unique(activities, "activityType"),
        "taskTypes":       _unique(tasks,      "taskType"),
        "stemTypes":       _unique(stems,      "stemType"),
        # UNREVIEWED is a pipeline-internal marker, not a schema-valid imageType
        "imageTypes":      [t for t in _unique(images, "imageType") if t != "UNREVIEWED"],
        "pageTypes":       _unique(pages,      "pageType"),
        "standardsBodies": _unique(standards,  "body"),
    }
    if goals:
        out["goalTypes"] = _unique(goals, "goalType")
    return out


def _unique(items: list[dict], key: str) -> list[str]:
    seen: set = set()
    out: list[str] = []
    for item in items:
        v = item.get(key)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ── 03 — Resource ─────────────────────────────────────────────────────────────

def build_resource(
    *,
    resource_id: str,
    module_id: str,
    source_filename: str,
    lesson_meta: dict,
    total_pages: int,
    extracted_at: str,
    book_name_override: str | None = None,
    pages: list[dict] | None = None,
) -> dict:
    """
    03_resource.json
    Top-level book/resource entity.
    """
    title = (book_name_override or source_filename or "").strip()
    if not title and source_filename:
        title = source_filename.replace(".pdf", "")
    page_refs = [
        {"id": p["id"], "type": "PAGE", "pageNumber": p.get("pageNumber")}
        for p in (pages or [])
    ]
    return {
        "id":           resource_id,
        "resourceType": "STUDENT_RESOURCE_BOOK",
        "title":        title or "Untitled Resource",
        "gradeLevel":   lesson_meta.get("grade_level", "HS"),
        "pages":        page_refs,
        # type field omitted — can only be a module (issue #2)
        "modules":      [{"id": module_id}],
        "standards":    [],
        "metadata": {
            "totalPages": total_pages,
            "subjects":   ["Mathematics"],
        },
    }


# ── 04 — Module ───────────────────────────────────────────────────────────────

def build_module(
    *,
    module_id: str,
    resource_id: str,
    topic_id: str,
    lesson_meta: dict,
    module_name_override: str | None = None,
    module_subtitle_override: str | None = None,
    module_meta_override: str | None = None,
) -> dict:
    """
    04_module.json
    Module entity — sits between Resource and Topic.
    Images belong to activities, not modules.
    """
    raw_title = (module_name_override or lesson_meta.get("module_title") or "").strip()
    title = _strip_entity_number_prefix(raw_title) if raw_title else ""
    # Use null for empty summary — empty string is invalid (issue #5)
    raw_summary = (module_subtitle_override or lesson_meta.get("module_summary") or "").strip()
    module_summary = raw_summary or None
    metadata: dict[str, Any] = {"localizationInfo": {"language": "en"}}
    if module_meta_override:
        metadata["userMeta"] = module_meta_override
    return {
        "id":            module_id,
        "resourceId":    resource_id,
        "standardsBody": lesson_meta.get("standards_body"),
        "moduleNumber":  lesson_meta.get("module_number", 1),
        "title":         title,
        "moduleSummary": module_summary,
        # Default to "HS" — grade level extraction often returns raw number (issue from diff)
        "gradeLevel":    lesson_meta.get("grade_level", "HS"),
        # type field omitted — can only be a topic (issue #3)
        "topics":        [{"id": topic_id, "sequenceNumber": 1}],
        "metadata":      metadata,
    }


# ── 05 — Topic ────────────────────────────────────────────────────────────────

def build_topic(
    *,
    topic_id: str,
    module_id: str,
    lesson_id: str,
    lesson_meta: dict,
) -> dict:
    """
    05_topic.json
    Topic entity — groups lessons within a module.
    """
    # Use null for empty summary — empty string is invalid (issue #6)
    raw_summary = (lesson_meta.get("topic_summary") or "").strip()
    topic_summary = raw_summary or None
    return {
        "id":           topic_id,
        "moduleId":     module_id,
        "topicNumber":  lesson_meta.get("topic_number", 1),
        "title":        lesson_meta.get("topic_title", ""),
        "topicSummary": topic_summary,
        "images":       [],
        # sequenceNumber not required in topic's lesson references (issue #7)
        "lessons": [{"id": lesson_id, "type": "LESSON"}],
    }


# ── 06 — Lesson ───────────────────────────────────────────────────────────────

def build_lesson(
    *,
    lesson_id: str,
    topic_id: str,
    std_block_id: str,
    lesson_meta: dict,
    activities: list[dict],
    has_standards: bool,
    banner_images: list[dict] | None = None,
) -> dict:
    """
    06_lesson.json
    Lesson entity with learning goals and activity references.
    banner_images: list of {"id": ..., "type": "IMAGE"} refs for the lesson banner/cover image(s).
    """
    learning_goals = lesson_meta.get("learning_goals") or []
    if isinstance(learning_goals, str):
        learning_goals = [learning_goals]

    return {
        "id":             lesson_id,
        "topicId":       topic_id,
        "lessonNumber":  lesson_meta.get("lesson_number"),
        "title":         lesson_meta.get("title"),
        "lessonSummary": lesson_meta.get("lesson_summary"),
        "images":        banner_images or [],
        "learningGoals": learning_goals,
        "standardsBlock": std_block_id if has_standards else None,
        "activities": [
            {"id": a["id"], "type": "ACTIVITY", "sequenceNumber": a["sequenceNumber"]}
            for a in activities
        ],
        "metadata":      {},
    }


# ── 07 — Activities ───────────────────────────────────────────────────────────

def build_activities_chunk(
    *,
    lesson_id: str,
    raw_activities: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """
    07_activities.json  (also produces tasks, stems, response areas,
    and scaffolding as side-effects)

    Returns:
        activities      — list of assembled activity dicts
        tasks           — flat list of task dicts
        stems           — flat list of stem dicts
        response_areas  — flat list of response area dicts
        scaffolding     — flat list of scaffolding dicts
    """
    activities:     list[dict] = []
    tasks:          list[dict] = []
    stems:          list[dict] = []
    response_areas: list[dict] = []
    scaffolding:    list[dict] = []

    for seq, raw_act in enumerate(raw_activities, 1):
        act_id       = gen_id()
        src_page     = raw_act.get("_source_page")
        activity_type = raw_act.get("activity_type", "EXPLORE")

        # For KEY_TERMS activities, Gemini emits each term as a task.
        # Convert those task stem_texts into DIRECTION_LINE entries instead;
        # no tasks/stems are generated for KEY_TERMS activities.
        is_key_terms = activity_type == "KEY_TERMS"
        if is_key_terms:
            task_refs = []
            extra_direction_terms = [
                t.get("stem_text", "")
                for t in (raw_act.get("tasks") or [])
                if t.get("stem_text")
            ]
        else:
            task_refs = _build_tasks_for_activity(
                act_id, raw_act.get("tasks") or [],
                tasks, stems, response_areas, scaffolding, src_page,
            )
            extra_direction_terms = []

        raw_direction_lines = raw_act.get("direction_lines") or []
        directions = []
        for i, line in enumerate(raw_direction_lines):
            if isinstance(line, dict):
                text = line.get("text") or line.get("direction_text") or ""
                directions.append({
                    "sequenceNumber": i + 1,
                    "type": "DIRECTION_LINE",
                    "text": text,
                })
            elif isinstance(line, str):
                directions.append({
                    "sequenceNumber": i + 1,
                    "type": "DIRECTION_LINE",
                    "text": line,
                })

        # Append key terms as direction lines (numbered after any existing directions)
        offset = len(directions)
        for j, term in enumerate(extra_direction_terms):
            directions.append({
                "sequenceNumber": offset + j + 1,
                "type": "DIRECTION_LINE",
                "text": term,
            })

        activities.append({
            "id":             act_id,
            "lessonId":       lesson_id,
            "activityType":   activity_type,
            "title":          raw_act.get("title"),
            "sequenceNumber": raw_act.get("sequence_number", seq),
            "directions":     directions,
            "tasks":          task_refs,
            "goals":          [],
            "scaffolding":    [],
            "images":         [],
            "metadata":       {},
            # Internal-only fields used during assembly (stripped before writing output)
            "_habitsOfMind":  raw_act.get("habits_of_mind", []),
            "_sourcePage":    src_page,
        })

    return activities, tasks, stems, response_areas, scaffolding


def build_activity_goals_chunk(activities: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """
    19_activity_goals.json
    One goal entry per activity. Activities with habits_of_mind get goalType HABITS_OF_MIND;
    all others get goalType ACTIVITY_GOAL with an empty goalItems list so every activity
    is represented. Returns (goals_list, refs_by_activity_id).
    """
    goals: list[dict] = []
    refs_by_activity_id: dict[str, list[dict]] = {}
    for act in activities:
        act_id = act.get("id")
        if not act_id:
            continue
        habits = act.get("_habitsOfMind") or []
        goal_items = [h if isinstance(h, str) else str(h) for h in habits]
        goal_id = gen_id()
        goals.append({
            "id":         goal_id,
            "activityId": act_id,
            "goalType":   "HABITS_OF_MIND" if goal_items else "ACTIVITY_GOAL",
            "goalItems":  goal_items,
            "standards":  [],
        })
        refs_by_activity_id.setdefault(act_id, []).append({"id": goal_id, "type": "GOALS"})
    return goals, refs_by_activity_id


_VALID_TOOLS = {"CALCULATOR", "RULER", "PROTRACTOR", "COMPASS", "MANIPULATIVES"}

_VALID_SCAFFOLDING_TYPES = {
    "HINT", "GUIDING_QUESTION", "STRATEGY_PROMPT",
    "REMINDER", "CHARACTER_SUPPORT", "WORKED_EXAMPLE",
}

_VALID_RESPONSE_AREA_TYPES = {
    "OPEN_ENDED", "SHORT_ANSWER", "GRID", "NUMBER_LINE", "ALGORITHM_WORKSPACE",
}

# Legacy image-level types Gemini may still return → normalize to schema types
_RESPONSE_AREA_TYPE_MAP = {
    "COORDINATE_PLANE": "GRID",
    "TABLE":            "GRID",
    "OPEN_LINE":        "SHORT_ANSWER",
    "BOX":              "SHORT_ANSWER",
    "STEM":             "SHORT_ANSWER",
}


def _normalize_response_area_type(raw: str | None) -> str:
    if not raw:
        return "OPEN_ENDED"
    upper = raw.upper()
    if upper in _VALID_RESPONSE_AREA_TYPES:
        return upper
    return _RESPONSE_AREA_TYPE_MAP.get(upper, "OPEN_ENDED")


def _build_tasks_for_activity(
    act_id: str,
    raw_tasks: list[dict],
    tasks_acc: list[dict],
    stems_acc: list[dict],
    response_areas_acc: list[dict],
    scaffolding_acc: list[dict],
    source_page: Any = None,
) -> list[dict]:
    """Build task + stem + response-area + scaffolding entities for one activity."""
    task_refs: list[dict] = []

    for raw_task in raw_tasks:
        task_id  = gen_id()
        stem_id  = gen_id()

        resp_area_id = None
        if raw_task.get("has_response_area"):
            resp_area_id = gen_id()
            ra_type  = _normalize_response_area_type(raw_task.get("response_area_type"))
            lines    = raw_task.get("response_area_lines")
            tools    = raw_task.get("allowed_tools") or []
            response_areas_acc.append({
                "id":          resp_area_id,
                "type":        ra_type,
                "description": raw_task.get("response_area_description") or "",
                "specifications": {
                    "textAreaLines": int(lines) if lines else 1,
                    "allowedTools":  [t for t in tools if t in _VALID_TOOLS],
                },
            })

        scaff_refs: list[dict] = []
        for raw_scaff in raw_task.get("scaffolding") or []:
            if not raw_scaff or not raw_scaff.get("content"):
                continue
            scaff_id    = gen_id()
            scaff_type  = raw_scaff.get("scaffolding_type", "CHARACTER_SUPPORT")
            if scaff_type not in _VALID_SCAFFOLDING_TYPES:
                scaff_type = "CHARACTER_SUPPORT"
            scaffolding_acc.append({
                "id":              scaff_id,
                "scaffoldingType": scaff_type,
                "content":         raw_scaff.get("content", ""),
                "image":           None,
            })
            scaff_refs.append({"id": scaff_id, "type": "SCAFFOLDING"})

        stems_acc.append(build_stem(
            stem_id=stem_id,
            task_id=task_id,
            raw_task=raw_task,
            source_page=source_page,
            response_area_id=resp_area_id,
        ))
        tasks_acc.append(build_task(
            task_id=task_id,
            act_id=act_id,
            stem_id=stem_id,
            raw_task=raw_task,
            source_page=source_page,
            scaffolding_refs=scaff_refs,
        ))
        task_refs.append({
            "id":             task_id,
            "type":           "TASK",
            "sequenceNumber": len(task_refs) + 1,
        })

    return task_refs


# ── 08 — Tasks ────────────────────────────────────────────────────────────────

def build_task(
    *,
    task_id: str,
    act_id: str,
    stem_id: str,
    raw_task: dict,
    source_page: Any = None,
    scaffolding_refs: list[dict] | None = None,
) -> dict:
    """
    08_tasks.json  (single task entity — called inside build_activities_chunk)
    """
    has_resp = raw_task.get("has_response_area", False)
    # Prefer Gemini-extracted task_type; fall back to inferring from has_response_area
    _VALID_TASK_TYPES = {
        "OPEN_ENDED", "SHORT_ANSWER", "COMPLETION",
        "MULTIPLE_CHOICE", "WORD_PROBLEM", "STRATEGY_ANALYSIS", "CALCULATION",
    }
    raw_task_type = (raw_task.get("task_type") or "").upper()
    task_type = raw_task_type if raw_task_type in _VALID_TASK_TYPES else (
        "OPEN_ENDED" if has_resp else "SHORT_ANSWER"
    )
    # Blank task numbers default to "1" — "0" is invalid per schema (issue #8)
    raw_task_number = raw_task.get("task_number", "")
    task_number = raw_task_number if raw_task_number else "1"
    return {
        "id":          task_id,
        "activityId":  act_id,
        "taskNumber":  task_number,
        "taskType":    task_type,
        "stems":       [{"id": stem_id, "type": "STEM", "sequenceNumber": 1}],
        "scaffolding": scaffolding_refs or [],
        # sourcePage removed — pipeline-internal field, not part of output schema
    }


# ── 09 — Stems ────────────────────────────────────────────────────────────────

def build_stem(
    *,
    stem_id: str,
    task_id: str,
    raw_task: dict,
    source_page: Any = None,
    response_area_id: str | None = None,
) -> dict:
    """
    09_stems.json  (single stem entity — called inside build_activities_chunk)
    """
    has_resp = raw_task.get("has_response_area", False)
    stem: dict = {
        "id":           stem_id,
        "taskId":       task_id,
        "stemType":     "TEXT_WITH_RESPONSE_AREA" if has_resp else "TEXT_ONLY",
        "stemText":     raw_task.get("stem_text", ""),
        "image":        None,
        "responseArea": response_area_id,
        # responseAreaType removed — redundant with responseArea object (diff analysis)
        # subTasks removed — sub-tasks are promoted to top-level stems during review
        # sourcePage removed — pipeline-internal field
    }
    # Only include ancillaryText when present (avoid null noise)
    ancillary = raw_task.get("ancillary_text")
    if ancillary is not None:
        stem["ancillaryText"] = ancillary
    return stem


# ── 10 — Standards ────────────────────────────────────────────────────────────

def build_standards_chunk(
    *,
    pages: list[dict],
) -> list[dict]:
    """
    10_standards.json
    Deduplicated standards extracted across all pages.
    """
    standards: list[dict] = []
    seen_codes: set[str] = set()

    for page in pages:
        sb = page.get("standards_block")
        if not (sb and isinstance(sb, dict)):
            continue
        for std in sb.get("standards") or []:
            code = std.get("code", "")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            standards.append({
                "id":          gen_id(),
                "body":        sb.get("standards_body", "CA_CCSS"),
                "code":        code,
                "gradeLevel":  sb.get("grade_level", "HS"),
                "fullText":    std.get("full_text", ""),
                "domain":      std.get("domain"),
                "cluster":     std.get("cluster"),
                "description": std.get("full_text", ""),
                # hasModelingSymbol removed — not part of output schema (diff analysis)
            })

    return standards


def _collect_standards_block_meta(pages: list[dict]) -> dict:
    """Collect aggregated standards block metadata from all pages with standards_block."""
    meta: dict[str, Any] = {
        "title": None,
        "body": "CA_CCSS",
        "gradeLevel": "HS",
        "subtitle": None,
        "conceptualOverlaySubtitle": None,
        "bigIdeas": [],
        "conceptualOverlays": [],
    }
    for page in pages:
        sb = page.get("standards_block")
        if not (sb and isinstance(sb, dict)):
            continue
        if sb.get("title") and not meta["title"]:
            meta["title"] = sb["title"]
        if sb.get("standards_body"):
            meta["body"] = sb["standards_body"]
        if sb.get("grade_level"):
            meta["gradeLevel"] = sb["grade_level"]
        if sb.get("subtitle") and not meta["subtitle"]:
            meta["subtitle"] = sb["subtitle"]
        if sb.get("conceptual_overlay_subtitle") and not meta["conceptualOverlaySubtitle"]:
            meta["conceptualOverlaySubtitle"] = sb["conceptual_overlay_subtitle"]
        for idea in sb.get("big_ideas") or []:
            if idea and idea not in meta["bigIdeas"]:
                meta["bigIdeas"].append(idea)
    return meta


# ── 11 — Standards Blocks ─────────────────────────────────────────────────────

def build_standards_blocks(
    *,
    std_block_id: str,
    standards: list[dict],
    lesson_meta: dict,
    pages: list[dict],
) -> list[dict]:
    """
    11_standards_blocks.json
    One block per extraction run with full metadata from the standards pages.
    """
    if not standards:
        return []
    sb_meta = _collect_standards_block_meta(pages)
    seq = 1
    std_refs = []
    for s in standards:
        # code removed from ref; type added — aligns with schema (diff analysis)
        std_refs.append({"id": s["id"], "type": "STANDARDS", "sequenceNumber": seq})
        seq += 1

    block: dict[str, Any] = {
        "id":                        std_block_id,
        "body":                      sb_meta["body"],
        "gradeLevel":                sb_meta["gradeLevel"] or lesson_meta.get("grade_level", "HS"),
        "title":                     sb_meta["title"],
        "standardsSubtitle":         sb_meta["subtitle"],
        "conceptualOverlaySubtitle": sb_meta["conceptualOverlaySubtitle"],
        "standards":                 std_refs,
        # pageLocationHelpText removed — always null, not required (diff analysis)
    }
    if sb_meta["bigIdeas"]:
        block["conceptualOverlays"] = [
            {"sequenceNumber": i + 1, "text": t}
            for i, t in enumerate(sb_meta["bigIdeas"])
        ]
    return [block]


# ── 12 — Images (CL-Json-Schema schemas/media/image.json) ─────────────────────

def _file_size(out_dir: Path | None, rel_path: str | None) -> dict | None:
    """Return fileSize dict {bytes, formatted} for a relative image path, or None."""
    if not out_dir or not rel_path:
        return None
    try:
        size = (out_dir / rel_path).stat().st_size
    except OSError:
        return None
    if size < 1024:
        formatted = f"{size} B"
    elif size < 1024 * 1024:
        formatted = f"{size / 1024:.1f} KB"
    else:
        formatted = f"{size / (1024 * 1024):.1f} MB"
    return {"bytes": size, "formatted": formatted}


def build_images_chunk(
    *,
    pages: list[dict],
    image_manifest: dict | None = None,
    out_dir: Path | None = None,
) -> list[dict]:
    """
    12_images.json — aligned with CL-Json-Schema media/image.json.

    Combines two sources:
    1. Gemini-described images (alt_text, description, image_type, graph_details)
    2. Physically extracted images from image_manifest (raster + vector crops)

    Images are linked by position-based matching done in the image extractor.
    Unmatched extracted images are added as additional entries so users can
    review and delete irrelevant ones from the UI.
    """
    extracted = (image_manifest or {}).get("extracted", {})
    used_paths: set[str] = set()

    images: list[dict] = []

    for page in pages:
        page_num = page.get("page_number")
        pdf_idx = page.get("_pdf_page_index")
        page_num_val = page_num if page_num is not None else ""
        page_image_path = (
            f"page_images/{pdf_idx}.png" if pdf_idx
            else (f"page_images/{page_num_val}.png" if page_num_val else None)
        )

        lookup_key = pdf_idx if pdf_idx is not None else page_num
        page_extracted = extracted.get(lookup_key, []) if lookup_key is not None else []

        # Build a map: extracted images that matched a Gemini image → the ext entry
        matched_ext_by_gemini_pos: dict[str, dict] = {}
        for ext in page_extracted:
            gm = ext.get("matched_gemini")
            if gm:
                pos = (gm.get("position") or "").upper()
                matched_ext_by_gemini_pos[pos] = ext

        # 1. Gemini-described images: try to link to an extracted file
        for raw_img in page.get("images") or []:
            acc = raw_img.get("accessibility") or {}
            pos = (raw_img.get("position") or "").upper()

            image_path = None
            ext_entry = matched_ext_by_gemini_pos.get(pos)
            if ext_entry:
                image_path = ext_entry["path"]
                used_paths.add(image_path)

            # Use Gemini dimensions if present, otherwise fall back to extracted pixel dims
            dimensions = raw_img.get("dimensions")
            if not dimensions and ext_entry:
                dimensions = {
                    "width":  ext_entry.get("width"),
                    "height": ext_entry.get("height"),
                    "unit":   "PIXELS",
                }

            image_type = raw_img.get("image_type", "INSTRUCTIONAL")
            raw_decorative = acc.get("is_decorative", raw_img.get("is_decorative", False))
            # ICON type is functional — marking it decorative is contradictory (issue #9)
            is_decorative = False if image_type == "ICON" else bool(raw_decorative)
            img = {
                "id":        gen_id(),
                "imageType": image_type,
                "filename":  raw_img.get("filename", ""),
                "filepath":  image_path,
                "altText":   raw_img.get("alt_text", ""),
                "dimensions": dimensions,
                "fileSize":  _file_size(out_dir, image_path),
                "usage": {
                    "usedInPages":      [page_num] if page_num is not None else [],
                    "usedInActivities": [],
                    "usedInTasks":      [],
                    "isReusable":       False,
                },
                "accessibility": {
                    "isDecorative": is_decorative,
                },
                # sourcePage kept as internal field for activity/page cross-linking in assembler
                "sourcePage": page_num,
            }
            images.append(img)

        # 2. Unmatched extracted images: add as separate entries for user review
        for ext in page_extracted:
            if ext["path"] in used_paths:
                continue
            gm = ext.get("matched_gemini")
            if gm:
                continue

            img = {
                "id":        gen_id(),
                # UNREVIEWED flags images needing manual classification
                "imageType": "UNREVIEWED",
                "filename":  "",
                "filepath":  ext["path"],
                "altText":   "",
                "dimensions": {"width": ext.get("width"), "height": ext.get("height"), "unit": "PIXELS"},
                "fileSize":  _file_size(out_dir, ext["path"]),
                "usage": {
                    "usedInPages":      [page_num] if page_num is not None else [],
                    "usedInActivities": [],
                    "usedInTasks":      [],
                    "isReusable":       False,
                },
                "accessibility": {
                    "isDecorative": False,
                },
                # sourcePage kept as internal field for activity/page cross-linking in assembler
                "sourcePage": page_num,
            }
            images.append(img)

    return images


# ── 13 — Pages ────────────────────────────────────────────────────────────────

_PAGE_TYPE_MAP = {
    # Legacy page types → current schema values (diff analysis + issue #10)
    "STANDARDS_PAGE": "SRB_LESSON_INTRODUCTION_ACTIVATE",
    "SPB_PRACTICE":   "SRB_LESSON_PRACTICE",
}


def build_pages_chunk(
    *,
    pages: list[dict],
    resource_id: str,
    lesson_id: str | None = None,
    activities: list[dict] | None = None,
    lesson_meta: dict | None = None,
) -> list[dict]:
    """
    13_pages.json
    Page entities with layout metadata and contentBlocks (references to
    lesson/activities on this page). Pages reference content; they do not
    duplicate activity content (that stays in 07_activities.json).
    pdfPageIndex is the 1-based page index within the PDF file itself.
    """
    activities = activities or []
    # Map page_number -> list of (sequenceNumber, activity) for ordering
    by_page: dict[int | None, list[tuple[int, dict]]] = {}
    for act in activities:
        pn = act.get("_sourcePage")
        if pn is None:
            continue
        seq_raw = act.get("sequenceNumber")
        seq = seq_raw if isinstance(seq_raw, int) else 0
        by_page.setdefault(pn, []).append((seq, act))
    for pn in by_page:
        by_page[pn].sort(key=lambda x: x[0])

    out: list[dict] = []
    for page in pages:
        pn = page.get("page_number") or page.get("_pdf_page_index")
        content_blocks: list[dict] = []
        if lesson_id:
            content_blocks.append({"id": lesson_id, "type": "LESSON"})
        for _seq, act in by_page.get(pn, []):
            content_blocks.append({"id": act["id"], "type": "ACTIVITY"})
        raw_page_type = page.get("page_type", "UNKNOWN")
        # Remap legacy page types to current schema values
        page_type = _PAGE_TYPE_MAP.get(raw_page_type, raw_page_type)

        meta: dict[str, Any] = {
            "pageNumberRepresentations": {"numeric": pn},
        }
        if lesson_meta:
            meta["lessonContext"] = {
                "topicNumber":  lesson_meta.get("topic_number"),
                "topicTitle":   lesson_meta.get("topic_title"),
                "lessonNumber": lesson_meta.get("lesson_number"),
                "lessonTitle":  lesson_meta.get("title"),
            }

        out.append({
            "id":            gen_id(),
            "resourceId":    resource_id,
            "pageType":      page_type,
            "contentBlocks": content_blocks,
            "metadata":      meta,
            # pdfPageIndex / pageNumber / layout removed — replaced by metadata (diff analysis)
        })
    return out


# ── 14 — Instructional Prompts ────────────────────────────────────────────────

def build_instructional_prompts_chunk(
    *,
    pages: list[dict],
    lesson_id: str,
) -> list[dict]:
    """
    14_instructional_prompts.json
    Sidebars, callouts, Make a Connection, Learning Goals boxes, etc.
    """
    prompts: list[dict] = []
    for page in pages:
        page_num = page.get("page_number")
        for ip in page.get("instructional_prompts") or []:
            display_style = ip.get("display_style", "BOX")
            prompts.append({
                "id":                         gen_id(),
                "studentContentReferenceId":  lesson_id,
                "instructionalPromptType":    ip.get("prompt_type"),
                "displayStyle":               display_style,
                "title":                      ip.get("title"),
                "content":                    ip.get("content"),
                "contentItems":               ip.get("content_items", []),
                "sourcePage":                 page_num,
                "metadata":                   {"displayStyle": display_style} if display_style else {},
            })
    return prompts


# ── 15 — Instructional Segments ───────────────────────────────────────────────

def build_instructional_segments(
    *,
    lesson_id: str,
    activities: list[dict],
) -> list[dict]:
    """
    15_instructional_segments.json
    High-level segments grouping activities by phase (ACTIVATE / EXPLORE / REFLECT).
    One segment per distinct activity_type encountered.
    """
    segments: list[dict] = []
    seen_types: dict[str, str] = {}   # activity_type → segment_id

    for activity in activities:
        act_type = activity.get("activityType", "EXPLORE")
        if act_type not in seen_types:
            seg_id = gen_id()
            seen_types[act_type] = seg_id
            segments.append({
                "id":              seg_id,
                "lessonId":        lesson_id,
                "segmentType":     act_type,
                "sequenceNumber":  len(segments) + 1,
                "activityIds":     [],
            })
        # append this activity's id to its segment
        seg = next(s for s in segments if s["id"] == seen_types[act_type])
        seg["activityIds"].append(activity["id"])

    return segments


# ── 16 — Practice Sections ────────────────────────────────────────────────────

_VALID_PRACTICE_TYPES = {"LESSON_PRACTICE", "INTERACTIVE_PRACTICE", "FAMILY_GUIDE"}


def build_practice_sections_chunk(
    *,
    lesson_id: str,
    activities: list[dict],
    pages: list[dict] | None = None,
) -> list[dict]:
    """
    16_practice_sections.json
    First looks for Gemini-extracted practice_section objects at the page level
    (populated when the Gemini prompt detected a "Practice and Apply" heading, a
    LiveHint reference, or a family-guide section).  Falls back to grouping any
    activities whose activityType is PRACTICE.
    """
    _PRACTICE_ACTIVITY_TYPES = {"PRACTICE", "LESSON_PRACTICE", "SPB_PRACTICE"}
    practice_acts = [a for a in activities if a.get("activityType") in _PRACTICE_ACTIVITY_TYPES]

    # ── Path 1: use Gemini page-level practice_section objects ────────────────
    if pages:
        seen_types: set[str] = set()
        sections: list[dict] = []
        for page in pages:
            ps = page.get("practice_section")
            if not (ps and isinstance(ps, dict)):
                continue
            ps_type = (ps.get("practice_section_type") or "").upper()
            if ps_type not in _VALID_PRACTICE_TYPES or ps_type in seen_types:
                continue
            seen_types.add(ps_type)
            title = ps.get("title") or "Practice"
            sections.append({
                "id":                  gen_id(),
                "parentId":            lesson_id,
                "practiceSectionType": ps_type,
                "title":               title,
                "activities": [
                    {"id": a["id"], "type": "ACTIVITY", "sequenceNumber": i + 1}
                    for i, a in enumerate(practice_acts)
                ],
            })
        if sections:
            return sections

    # ── Path 2: fallback — group PRACTICE activities under one section ────────
    if not practice_acts:
        return []

    return [{
        "id":                  gen_id(),
        "parentId":            lesson_id,
        "practiceSectionType": "LESSON_PRACTICE",
        "title":               "Practice",
        "activities": [
            {"id": a["id"], "type": "ACTIVITY", "sequenceNumber": i + 1}
            for i, a in enumerate(practice_acts)
        ],
    }]


# ── Lesson-meta extractor (shared utility) ────────────────────────────────────

def extract_lesson_meta(pages: list[dict]) -> dict:
    """
    Walk all pages and collect the first non-null value for each lesson
    metadata field.  Returns a flat dict used by build_resource / build_lesson.
    """
    fields = [
        "lesson_number", "title", "lesson_summary", "learning_goals",
        "module_title", "module_number", "topic_title", "topic_number",
        "grade_level", "module_summary", "topic_summary", "standards_body",
    ]
    meta: dict[str, Any] = {}
    for page in pages:
        les = page.get("lesson") or {}
        sb = page.get("standards_block") or {}
        les["grade_level"] = les.get("grade_level") or sb.get("grade_level")
        les["standards_body"] = les.get("standards_body") or sb.get("standards_body")

        for f in fields:
            if f not in meta or meta[f] in (None, [], ""):
                val = les.get(f)
                if val not in (None, [], ""):
                    # Strip generic placeholder names for title fields
                    if f in ("title", "module_title", "topic_title"):
                        val = _strip_generic_name(val)
                    if val not in (None, [], ""):
                        meta[f] = val
        if len(meta) == len(fields) and all(meta.get(f) not in (None, [], "") for f in fields):
            break   # all fields filled — no need to keep scanning

    return meta
