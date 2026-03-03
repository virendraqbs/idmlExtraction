"""
services/assembler.py — Schema assembler service.

Calls each build_*() helper from utils/schema_chunks.py in order,
then writes all 18 JSON files via utils/file_utils.write_json().

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
) -> list[str]:
    """
    Build and write all 18 CL-Json-Schema JSON files.

    Args:
        pages:           Raw per-page dicts from GeminiService.extract_page()
        out_dir:         Directory to write output files into
        source_filename: Original PDF filename (used as resource title)
        image_manifest:  Output from extract_images_from_pdf() — maps pages to
                         extracted image file paths.

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

    # Practice sections (groups PRACTICE activities)
    practice_sections = build_practice_sections_chunk(
        lesson_id=lesson_id, activities=activities,
    )

    # Images, pages, prompts
    images   = build_images_chunk(pages=pages, image_manifest=image_manifest)
    pg_list  = build_pages_chunk(pages=pages, resource_id=resource_id)
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
    )
    resource = build_resource(
        resource_id=resource_id, module_id=module_id,
        source_filename=source_filename, lesson_meta=lesson_meta,
        total_pages=len(pages), extracted_at=extracted_at,
    )
    module = build_module(
        module_id=module_id, resource_id=resource_id,
        topic_id=topic_id, lesson_meta=lesson_meta,
        image_ids=[img["id"] for img in images],
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
