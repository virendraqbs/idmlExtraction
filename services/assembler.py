"""
services/assembler.py — Schema assembler service.

Calls each build_*() helper from utils/schema_chunks.py in order,
then writes all 19 JSON files via utils/file_utils.write_json().

This is the only place that knows about:
  - the ORDER in which files are written
  - which chunk-helpers depend on the output of other chunk-helpers
"""
from __future__ import annotations

import logging
from pathlib import Path

from utils.file_utils import write_json
from utils.schema_chunks import (
    gen_id, now_iso,
    extract_lesson_meta,
    build_primitives,
    build_enums,
    build_resource,
    build_module,
    build_topic,
    build_lesson,
    build_activities_chunk,
    build_activity_goals_chunk,
    build_standards_chunk,
    build_standards_blocks,
    build_images_chunk,
    build_pages_chunk,
    build_instructional_prompts_chunk,
    build_instructional_segments,
    build_practice_sections_chunk,
)

log = logging.getLogger(__name__)


def assemble_schemas(
    pages: list[dict],
    out_dir: Path,
    source_filename: str,
    image_manifest: dict | None = None,
    book_name: str | None = None,
    module_name: str | None = None,
    module_subtitle: str | None = None,
    module_meta: str | None = None,
) -> list[str]:
    """
    Build and write all 19 CL-Json-Schema JSON files (including 19_activity_goals.json).

    Args:
        pages:           Raw per-page dicts from GeminiService.extract_page()
        out_dir:         Directory to write output files into
        source_filename: Original PDF filename (used as resource title)
        image_manifest:  Output from extract_images_from_pdf() — maps pages to
                         extracted image file paths.
        book_name:       Optional user-provided resource/book title override.
        module_name:     Optional user-provided module title override.
        module_subtitle: Optional user-provided module subtitle.
        module_meta:     Optional user-provided module meta (JSON string or text).

    Returns:
        List of filenames written (18 items).
    """
    extracted_at = now_iso()

    # ── Canonical document-level IDs ──────────────────────────────────────────
    resource_id  = gen_id()
    module_id    = gen_id()
    topic_id     = gen_id()
    lesson_id    = gen_id()
    std_block_id = gen_id()

    # ── Shared metadata extracted from pages ──────────────────────────────────
    lesson_meta = extract_lesson_meta(pages)

    # ── Build entity lists (order matters — activities produces tasks+stems) ──

    # Standards
    standards     = build_standards_chunk(pages=pages)
    std_blocks    = build_standards_blocks(
                        std_block_id=std_block_id,
                        standards=standards,
                        lesson_meta=lesson_meta,
                        pages=pages,
                    )

    # Activities (also populates tasks + stems as side-effects)
    all_raw_activities = []
    for page in pages:
        pn = page.get("page_number")
        for act in page.get("activities") or []:
            act["_source_page"] = pn
            all_raw_activities.append(act)
    activities, tasks, stems, response_areas, scaffolding_items = build_activities_chunk(
        lesson_id=lesson_id,
        raw_activities=all_raw_activities,
    )

    # Merge continuation activities: if an activity has no title AND same activityType
    # as the immediately preceding activity, it is a page-overflow continuation.
    # Merge its tasks, directions, and _habitsOfMind into the preceding activity.
    merged_activities: list[dict] = []
    tasks_by_act: dict[str, list[dict]] = {}
    for t in tasks:
        tasks_by_act.setdefault(t.get("activityId", ""), []).append(t)

    for act in activities:
        is_continuation = (
            act.get("title") is None
            and merged_activities
            and act.get("activityType") == merged_activities[-1].get("activityType")
        )
        if is_continuation:
            prev = merged_activities[-1]
            # Re-parent tasks from this continuation activity to the previous one
            continuation_task_ids = {ref["id"] for ref in (act.get("tasks") or [])}
            for t in tasks:
                if t.get("activityId") == act["id"]:
                    t["activityId"] = prev["id"]
            # Merge task references
            existing_task_ids = {ref["id"] for ref in prev.get("tasks", [])}
            for ref in act.get("tasks", []):
                if ref["id"] not in existing_task_ids:
                    prev["tasks"].append(ref)
            # Merge directions (renumber)
            existing_dir_count = len(prev.get("directions", []))
            for i, d in enumerate(act.get("directions", []), existing_dir_count + 1):
                d["sequenceNumber"] = i
                prev["directions"].append(d)
            # Merge habits_of_mind
            prev_habits = prev.get("_habitsOfMind") or []
            for h in (act.get("_habitsOfMind") or []):
                if h not in prev_habits:
                    prev_habits.append(h)
            prev["_habitsOfMind"] = prev_habits
            # Do NOT add continuation activity to merged list
        else:
            merged_activities.append(act)

    activities = merged_activities

    # Activity goals (from _habitsOfMind); patch activity["goals"] with refs
    activity_goals, goal_refs_by_act_id = build_activity_goals_chunk(activities)
    for act in activities:
        act["goals"] = goal_refs_by_act_id.get(act["id"], [])
        # Remove internal-only field used during assembly
        act.pop("_habitsOfMind", None)

    # Practice sections (groups PRACTICE activities; uses page-level detection first)
    practice_sections = build_practice_sections_chunk(
        lesson_id=lesson_id, activities=activities, pages=pages,
    )

    # Images, pages, prompts
    images   = build_images_chunk(pages=pages, image_manifest=image_manifest, out_dir=out_dir)

    # Link images to activities by matching source page; populate activity["images"]
    # and image["usage"]["usedInActivities"] with cross-references.
    activities_by_page: dict[int, list[dict]] = {}
    for act in activities:
        pg = act.get("sourcePage")
        if pg is not None:
            activities_by_page.setdefault(pg, []).append(act)
    for img in images:
        img_page = img.get("sourcePage")
        if img_page is None:
            continue
        acts_on_page = activities_by_page.get(img_page, [])
        for act in acts_on_page:
            # Add image reference to activity if not already present
            img_ref = {"id": img["id"], "type": "IMAGE"}
            if img_ref not in act["images"]:
                act["images"].append(img_ref)
            # Add activity reference to image usage
            act_ref = {"id": act["id"], "type": "ACTIVITY"}
            used_in = img["usage"]["usedInActivities"]
            if act_ref not in used_in:
                used_in.append(act_ref)

    pg_list  = build_pages_chunk(
        pages=pages, resource_id=resource_id,
        lesson_id=lesson_id, activities=activities,
    )
    prompts  = build_instructional_prompts_chunk(pages=pages, lesson_id=lesson_id)
    segments = build_instructional_segments(lesson_id=lesson_id, activities=activities)

    # ── Singleton entities ────────────────────────────────────────────────────
    primitives = build_primitives(
        resource_id=resource_id, module_id=module_id,
        topic_id=topic_id, lesson_id=lesson_id,
        std_block_id=std_block_id,
        total_pages=len(pages), extracted_at=extracted_at,
    )
    enums = build_enums(
        activities=activities, tasks=tasks, stems=stems,
        images=images, pages=pg_list, standards=standards,
        goals=activity_goals,
    )
    resource = build_resource(
        resource_id=resource_id, module_id=module_id,
        source_filename=source_filename, lesson_meta=lesson_meta,
        total_pages=len(pages), extracted_at=extracted_at,
        book_name_override=book_name,
    )
    # Module only gets module-level images; lesson images stay on activities/pages
    module = build_module(
        module_id=module_id, resource_id=resource_id,
        topic_id=topic_id, lesson_meta=lesson_meta,
        image_ids=[],
        module_name_override=module_name,
        module_subtitle_override=module_subtitle,
        module_meta_override=module_meta,
    )
    topic = build_topic(
        topic_id=topic_id, module_id=module_id,
        lesson_id=lesson_id, lesson_meta=lesson_meta,
    )
    lesson = build_lesson(
        lesson_id=lesson_id, topic_id=topic_id,
        std_block_id=std_block_id, lesson_meta=lesson_meta,
        activities=activities, has_standards=bool(std_blocks),
    )

    # ── Write files ───────────────────────────────────────────────────────────
    schema_manifest: list[tuple[str, object]] = [
        ("01_primitives.json",            primitives),
        ("02_enums.json",                 enums),
        ("03_resource.json",              resource),
        ("04_module.json",                module),
        ("05_topic.json",                 topic),
        ("06_lesson.json",                lesson),
        ("07_activities.json",            {"count": len(activities), "activities": activities}),
        ("08_tasks.json",                 {"count": len(tasks),      "tasks":      tasks}),
        ("09_stems.json",                 {"count": len(stems),      "stems":      stems}),
        ("10_standards.json",             {"count": len(standards),  "standards":  standards}),
        ("11_standards_blocks.json",      {"count": len(std_blocks), "standardsBlocks": std_blocks}),
        ("12_images.json",                {"count": len(images),     "images":     images}),
        ("13_pages.json",                 {"count": len(pg_list),    "pages":      pg_list}),
        ("14_instructional_prompts.json", {"count": len(prompts),    "instructionalPrompts": prompts}),
        ("15_instructional_segments.json",{"count": len(segments),           "instructionalSegments": segments}),
        ("16_practice_sections.json",    {"count": len(practice_sections),  "practiceSections":      practice_sections}),
        ("17_response_areas.json",       {"count": len(response_areas),     "responseAreas":         response_areas}),
        ("18_scaffolding.json",          {"count": len(scaffolding_items),  "scaffolding":           scaffolding_items}),
        ("19_activity_goals.json",       {"count": len(activity_goals),     "goals":                 activity_goals}),
    ]

    files_written: list[str] = []
    for fname, data in schema_manifest:
        write_json(out_dir / fname, data)
        files_written.append(fname)
        log.info("Wrote %s", fname)

    # ── Build and write merged nested JSON (parent-child hierarchy) ─────────
    stems_by_task: dict[str, list] = {}
    for s in stems:
        stems_by_task.setdefault(s.get("taskId", ""), []).append(s)

    tasks_nested_by_activity: dict[str, list] = {}
    for t in tasks:
        t_nested = {**t, "stems": stems_by_task.get(t["id"], [])}
        tasks_nested_by_activity.setdefault(t.get("activityId", ""), []).append(t_nested)

    activities_nested = []
    for a in activities:
        activities_nested.append({**a, "tasks": tasks_nested_by_activity.get(a["id"], [])})

    lesson_nested = {
        **lesson,
        "activities": activities_nested,
        "instructionalPrompts": prompts,
        "standards": standards,
        "standardsBlocks": std_blocks,
    }

    topic_nested = {**topic, "lessons": [lesson_nested]}
    module_nested = {**module, "topics": [topic_nested]}
    resource_nested = {**resource, "modules": [module_nested]}

    merged = {
        "meta": primitives,
        "enums": enums,
        "resource": resource_nested,
        "pages": pg_list,
        "images": images,
        "instructionalSegments": segments,
    }

    write_json(out_dir / "merged.json", merged)
    files_written.append("merged.json")
    log.info("Wrote merged.json (nested hierarchy)")

    return files_written
