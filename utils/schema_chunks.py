"""
utils/schema_chunks.py — Schema-chunk helpers.

Each public function builds ONE of the 15 CL-Json-Schema output objects
from the raw per-page Gemini extractions.  The assembler in
services/assembler.py calls them in order so logic stays isolated,
testable, and easy to maintain.

Naming convention:
    build_<schema_name>(...)  →  returns a plain dict ready for JSON serialisation.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

# ── ID helpers ────────────────────────────────────────────────────────────────

def gen_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
        "resource_id":       resource_id,
        "module_id":         module_id,
        "topic_id":          topic_id,
        "lesson_id":         lesson_id,
        "standards_block_id": std_block_id,
        "total_pages":       total_pages,
        "extracted_at":      extracted_at,
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
) -> dict:
    """
    02_enums.json
    Distinct enum values actually present in this extraction run.
    Useful for validation and UI filter-lists.
    """
    return {
        "activityTypes":   _unique(activities, "activityType"),
        "taskTypes":       _unique(tasks,      "taskType"),
        "stemTypes":       _unique(stems,      "stemType"),
        "imageTypes":      _unique(images,     "imageType"),
        "pageTypes":       _unique(pages,      "pageType"),
        "standardsBodies": _unique(standards,  "body"),
    }


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
) -> dict:
    """
    03_resource.json
    Top-level book/resource entity.
    """
    return {
        "id":           resource_id,
        "resourceType": "STUDENT_RESOURCE_BOOK",
        "title":        source_filename.replace(".pdf", ""),
        "gradeLevel":   lesson_meta.get("grade_level", "HS"),
        "modules":      [{"id": module_id, "type": "MODULE"}],
        "metadata": {
            "totalPages":  total_pages,
            "subjects":    ["Mathematics"],
            "extractedAt": extracted_at,
        },
    }


# ── 04 — Module ───────────────────────────────────────────────────────────────

def build_module(
    *,
    module_id: str,
    resource_id: str,
    topic_id: str,
    lesson_meta: dict,
) -> dict:
    """
    04_module.json
    Module entity — sits between Resource and Topic.
    """
    return {
        "id":           module_id,
        "resourceId":   resource_id,
        "moduleNumber": lesson_meta.get("module_number", 1),
        "title":        lesson_meta.get("module_title", ""),
        "topics":       [{"id": topic_id, "type": "TOPIC", "sequenceNumber": 1}],
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
    return {
        "id":          topic_id,
        "moduleId":    module_id,
        "topicNumber": lesson_meta.get("topic_number", 1),
        "title":       lesson_meta.get("topic_title", ""),
        "lessons": [{
            "id":             lesson_id,
            "type":           "LESSON",
            "sequenceNumber": lesson_meta.get("lesson_number", 1),
        }],
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
) -> dict:
    """
    06_lesson.json
    Lesson entity with learning goals and activity references.
    """
    learning_goals = lesson_meta.get("learning_goals") or []
    if isinstance(learning_goals, str):
        learning_goals = [learning_goals]

    return {
        "id":            lesson_id,
        "topicId":       topic_id,
        "lessonNumber":  lesson_meta.get("lesson_number"),
        "title":         lesson_meta.get("title"),
        "lessonSummary": lesson_meta.get("lesson_summary"),
        "learningGoals": learning_goals,
        "standardsBlock": std_block_id if has_standards else None,
        "activities": [
            {"id": a["id"], "type": "ACTIVITY", "sequenceNumber": a["sequenceNumber"]}
            for a in activities
        ],
    }


# ── 07 — Activities ───────────────────────────────────────────────────────────

def build_activities_chunk(
    *,
    lesson_id: str,
    raw_activities: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    07_activities.json  (also produces raw tasks + stems as side-effect)

    Returns:
        activities  — list of assembled activity dicts
        tasks       — flat list of task dicts
        stems       — flat list of stem dicts
    """
    activities: list[dict] = []
    tasks:      list[dict] = []
    stems:      list[dict] = []

    for seq, raw_act in enumerate(raw_activities, 1):
        act_id    = gen_id()
        task_refs = _build_tasks_for_activity(act_id, raw_act.get("tasks") or [], tasks, stems)

        activities.append({
            "id":             act_id,
            "lessonId":       lesson_id,
            "activityType":   raw_act.get("activity_type", "EXPLORE"),
            "activityLabel":  raw_act.get("activity_label"),
            "title":          raw_act.get("title"),
            "sequenceNumber": raw_act.get("sequence_number", seq),
            "habitsOfMind":   raw_act.get("habits_of_mind", []),
            "directionLines": raw_act.get("direction_lines", []),
            "tasks":          task_refs,
        })

    return activities, tasks, stems


def _build_tasks_for_activity(
    act_id: str,
    raw_tasks: list[dict],
    tasks_acc: list[dict],
    stems_acc: list[dict],
) -> list[dict]:
    """Build task + stem entities for one activity; append to accumulators."""
    task_refs: list[dict] = []

    for raw_task in raw_tasks:
        task_id  = gen_id()
        stem_id  = gen_id()
        has_resp = raw_task.get("has_response_area", False)

        stems_acc.append(build_stem(
            stem_id=stem_id,
            task_id=task_id,
            raw_task=raw_task,
        ))
        tasks_acc.append(build_task(
            task_id=task_id,
            act_id=act_id,
            stem_id=stem_id,
            raw_task=raw_task,
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
) -> dict:
    """
    08_tasks.json  (single task entity — called inside build_activities_chunk)
    Separated so it can be unit-tested or called independently.
    """
    has_resp = raw_task.get("has_response_area", False)
    return {
        "id":         task_id,
        "activityId": act_id,
        "taskNumber": raw_task.get("task_number", ""),
        "taskType":   "OPEN_ENDED" if has_resp else "SHORT_ANSWER",
        "stems":      [{"id": stem_id, "type": "STEM", "sequenceNumber": 1}],
    }


# ── 09 — Stems ────────────────────────────────────────────────────────────────

def build_stem(
    *,
    stem_id: str,
    task_id: str,
    raw_task: dict,
) -> dict:
    """
    09_stems.json  (single stem entity — called inside build_activities_chunk)
    Math is already wrapped in $...$ / $$...$$ by the Gemini prompt.
    """
    has_resp = raw_task.get("has_response_area", False)
    return {
        "id":               stem_id,
        "taskId":           task_id,
        "stemType":         "TEXT_WITH_RESPONSE_AREA" if has_resp else "TEXT_ONLY",
        "stemText":         raw_task.get("stem_text", ""),
        "ancillaryText":    raw_task.get("ancillary_text"),
        "responseAreaType": raw_task.get("response_area_type"),
        "hasGraph":         raw_task.get("has_graph", False),
        "subTasks":         raw_task.get("sub_tasks", []),
    }


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
                "id":               gen_id(),
                "body":             sb.get("standards_body", "CA_CCSS"),
                "code":             code,
                "gradeLevel":       sb.get("grade_level", "HS"),
                "fullText":         std.get("full_text", ""),
                "domain":           std.get("domain"),
                "cluster":          std.get("cluster"),
                "hasModelingSymbol": std.get("has_modeling_symbol", False),
            })

    return standards


# ── 11 — Standards Blocks ─────────────────────────────────────────────────────

def build_standards_blocks(
    *,
    std_block_id: str,
    standards: list[dict],
    lesson_meta: dict,
) -> list[dict]:
    """
    11_standards_blocks.json
    One block per extraction run (aggregated from all standards pages).
    """
    if not standards:
        return []
    return [{
        "id":         std_block_id,
        "body":       "CA_CCSS",
        "gradeLevel": lesson_meta.get("grade_level", "HS"),
        "standards":  [{"id": s["id"], "code": s["code"]} for s in standards],
    }]


# ── 12 — Images ───────────────────────────────────────────────────────────────

def build_images_chunk(*, pages: list[dict]) -> list[dict]:
    """
    12_images.json
    All image entities, preserving graph_details and response-area flags.
    """
    images: list[dict] = []
    for page in pages:
        page_num = page.get("page_number")
        for raw_img in page.get("images") or []:
            images.append({
                "id":              gen_id(),
                "imageType":       raw_img.get("image_type", "INSTRUCTIONAL"),
                "position":        raw_img.get("position"),
                "altText":         raw_img.get("alt_text", ""),
                "description":     raw_img.get("description", ""),
                "containsGraph":   raw_img.get("contains_graph", False),
                "isDecorative":    raw_img.get("is_decorative", False),
                "isResponseArea":  raw_img.get("is_response_area", False),
                "responseAreaType": raw_img.get("response_area_type"),
                "graphDetails":    raw_img.get("graph_details"),
                "sourcePage":      page_num,
            })
    return images


# ── 13 — Pages ────────────────────────────────────────────────────────────────

def build_pages_chunk(*, pages: list[dict], resource_id: str) -> list[dict]:
    """
    13_pages.json
    Page entities with layout metadata and content-order array.
    """
    return [
        {
            "id":         gen_id(),
            "resourceId": resource_id,
            "pageNumber": page.get("page_number"),
            "pageType":   page.get("page_type", "UNKNOWN"),
            "layout":     page.get("page_layout"),
        }
        for page in pages
    ]


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
        for ip in page.get("instructional_prompts") or []:
            prompts.append({
                "id":                         gen_id(),
                "studentContentReferenceId":  lesson_id,
                "instructionalPromptType":    ip.get("prompt_type"),
                "displayStyle":               ip.get("display_style", "BOX"),
                "title":                      ip.get("title"),
                "content":                    ip.get("content"),
                "contentItems":               ip.get("content_items", []),
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


# ── Lesson-meta extractor (shared utility) ────────────────────────────────────

def extract_lesson_meta(pages: list[dict]) -> dict:
    """
    Walk all pages and collect the first non-null value for each lesson
    metadata field.  Returns a flat dict used by build_resource / build_lesson.
    """
    fields = [
        "lesson_number", "title", "lesson_summary", "learning_goals",
        "module_title", "module_number", "topic_title", "topic_number",
        "grade_level",
    ]
    meta: dict[str, Any] = {}
    for page in pages:
        les = page.get("lesson") or {}
        # Also check standards_block for grade_level
        sb = page.get("standards_block") or {}
        les["grade_level"] = les.get("grade_level") or sb.get("grade_level")

        for f in fields:
            if f not in meta or meta[f] in (None, [], ""):
                val = les.get(f)
                if val not in (None, [], ""):
                    meta[f] = val
        if len(meta) == len(fields) and all(meta.get(f) not in (None, [], "") for f in fields):
            break   # all fields filled — no need to keep scanning

    return meta
