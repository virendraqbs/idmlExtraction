"""
services/page_indexer.py — Build the per-job page→entity index in MySQL.

Reads the 19 JSON files written by services.assembler and populates:
  - cl_page  (one row per page, tagged with job_id for re-index isolation)
  - cl_resource_page_map  (resource_id, page_id, sequence_number=pdf_page_index)
  - cl_page_entity_map    (polymorphic page→entity rows, ordered by sequence_in_page)

The function is idempotent: rows for the given job_id are deleted first,
then re-inserted from the current JSON state.

Master entity tables (cl_activity, cl_image, cl_stem, ...) are NOT populated
in this round. Editor read API hydrates entity bodies from JSON directly.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymysql

from database import get_connection, get_or_create_resource_for_job

log = logging.getLogger(__name__)


@dataclass
class IndexReport:
    pages: int = 0
    activities: int = 0
    tasks: int = 0
    stems: int = 0
    images: int = 0
    instructional_prompts: int = 0
    instructional_segments: int = 0
    practice_sections: int = 0
    scaffolding: int = 0
    response_areas: int = 0
    lessons: int = 0
    skipped_no_source_page: int = 0
    errors: list[str] = field(default_factory=list)


_JSON_FILES = {
    "resource":  "03_resource.json",
    "lesson":    "06_lesson.json",
    "activities": "07_activities.json",
    "tasks":     "08_tasks.json",
    "stems":     "09_stems.json",
    "images":    "12_images.json",
    "pages":     "13_pages.json",
    "prompts":   "14_instructional_prompts.json",
    "segments":  "15_instructional_segments.json",
    "practice":  "16_practice_sections.json",
    "response":  "17_response_areas.json",
    "scaffolding": "18_scaffolding.json",
}


def _load(out_dir: Path, key: str) -> Any:
    """Load one JSON file. Returns None if missing or unreadable."""
    p = out_dir / _JSON_FILES[key]
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.warning("page_indexer: %s parse error: %s", p.name, e)
        return None


def _arr(payload: Any, key: str) -> list[dict]:
    """Extract `key` array from a {"count": N, key: [...]} wrapper or accept raw list."""
    if isinstance(payload, dict):
        v = payload.get(key)
        return v if isinstance(v, list) else []
    if isinstance(payload, list):
        return payload
    return []


def index_job_pages(job_id: str, out_dir: Path) -> IndexReport:
    """
    Build the page-entity index for one extraction job. Idempotent — wipes
    prior rows for this job_id before inserting fresh ones.

    job_id is the outputs/<job_id>/ folder name. out_dir is its absolute Path.
    """
    report = IndexReport()

    resource_payload = _load(out_dir, "resource")
    pages_payload   = _load(out_dir, "pages")
    if not resource_payload or not pages_payload:
        report.errors.append("missing 03_resource.json or 13_pages.json")
        return report

    resource_id = get_or_create_resource_for_job(resource_payload)
    pages = _arr(pages_payload, "pages")

    activities = _arr(_load(out_dir, "activities"), "activities")
    tasks      = _arr(_load(out_dir, "tasks"),      "tasks")
    stems      = _arr(_load(out_dir, "stems"),      "stems")
    images     = _arr(_load(out_dir, "images"),     "images")
    prompts    = _arr(_load(out_dir, "prompts"),    "instructionalPrompts")
    segments   = _arr(_load(out_dir, "segments"),   "instructionalSegments")
    practice   = _arr(_load(out_dir, "practice"),   "practiceSections")
    response   = _arr(_load(out_dir, "response"),   "responseAreas")
    scaffolding = _arr(_load(out_dir, "scaffolding"), "scaffolding")
    lesson_payload = _load(out_dir, "lesson") or {}

    # Build map sourcePage -> page row for quick lookup
    page_by_number: dict[int, dict] = {}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. Wipe prior rows for this job (cascade-aware order)
            cur.execute(
                "SELECT id FROM cl_page WHERE job_id = %s", (job_id,)
            )
            old_page_ids = [r["id"] for r in cur.fetchall()]
            if old_page_ids:
                fmt = ",".join(["%s"] * len(old_page_ids))
                cur.execute(
                    f"DELETE FROM cl_page_entity_map WHERE page_id IN ({fmt})",
                    tuple(old_page_ids),
                )
                cur.execute(
                    f"DELETE FROM cl_resource_page_map WHERE page_id IN ({fmt})",
                    tuple(old_page_ids),
                )
                cur.execute(
                    "DELETE FROM cl_page WHERE job_id = %s", (job_id,)
                )

            # 2. Insert fresh cl_page rows
            for ordinal, p in enumerate(pages, start=1):
                page_id = p.get("id") or str(uuid.uuid4())
                page_number = p.get("pageNumber")
                if page_number is None:
                    # Fall back to metadata.pageNumberRepresentations.numeric
                    meta = p.get("metadata") or {}
                    pnr = meta.get("pageNumberRepresentations") or {}
                    page_number = pnr.get("numeric")
                if not isinstance(page_number, int):
                    page_number = ordinal  # last-resort: use ordinal
                page_type = p.get("pageType")
                cur.execute(
                    "INSERT INTO cl_page (id, page_number, page_type, job_id) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "  page_number = VALUES(page_number), "
                    "  page_type   = VALUES(page_type), "
                    "  job_id      = VALUES(job_id)",
                    (page_id, page_number, page_type, job_id),
                )
                # 3. cl_resource_page_map row (sequence_number = pdf ordinal)
                cur.execute(
                    "INSERT INTO cl_resource_page_map "
                    "(id, resource_id, page_id, sequence_number) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "  sequence_number = VALUES(sequence_number)",
                    (str(uuid.uuid4()), resource_id, page_id, ordinal),
                )
                page_by_number[int(page_number)] = {
                    "id": page_id, "page_number": page_number,
                    "ordinal": ordinal,
                }
                report.pages += 1

            # 4. cl_page_entity_map rows — one per (page, entity)
            def insert_entity_row(page_id: str, entity_type: str,
                                  entity_id: str, seq: int,
                                  layout_region: str | None = None,
                                  metadata: dict | None = None) -> None:
                cur.execute(
                    "INSERT IGNORE INTO cl_page_entity_map "
                    "(id, page_id, entity_type, entity_id, sequence_in_page, "
                    " layout_region, metadata) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()), page_id, entity_type, entity_id,
                        seq, layout_region,
                        json.dumps(metadata) if metadata else None,
                    ),
                )

            # Group entities per page so we can assign sequence_in_page within page.
            per_page_seq: dict[str, int] = {}

            def next_seq(page_id: str) -> int:
                per_page_seq[page_id] = per_page_seq.get(page_id, 0) + 1
                return per_page_seq[page_id]

            def emit(entity_type: str, entity: dict, ent_id: str,
                     layout_region: str | None = None,
                     metadata: dict | None = None) -> bool:
                src_page = entity.get("sourcePage")
                if src_page is None:
                    report.skipped_no_source_page += 1
                    return False
                page = page_by_number.get(int(src_page))
                if not page:
                    report.skipped_no_source_page += 1
                    return False
                insert_entity_row(
                    page["id"], entity_type, ent_id,
                    next_seq(page["id"]), layout_region, metadata,
                )
                return True

            # Lesson — single row on the first page (using resolved page_number key)
            lesson_id = lesson_payload.get("id")
            first_key = min(page_by_number) if page_by_number else None
            first = page_by_number.get(first_key) if first_key is not None else None
            if lesson_id and first:
                insert_entity_row(
                    first["id"], "LESSON", lesson_id, next_seq(first["id"]),
                )
                report.lessons += 1

            for a in activities:
                if emit("ACTIVITY", a, a.get("id", "")):
                    report.activities += 1

            # Build activity-by-id lookup for practice + scaffolding cross-refs.
            activity_by_id: dict[str, dict] = {a.get("id"): a for a in activities if a.get("id")}

            # Tasks/stems inherit page binding from parent activity via maps
            # in JSON: activity.tasks[] holds task references {id, type}.
            task_to_page_id: dict[str, str] = {}
            for a in activities:
                src = a.get("sourcePage")
                if src is None:
                    continue
                page = page_by_number.get(int(src))
                if not page:
                    continue
                for tref in (a.get("tasks") or []):
                    tid = tref.get("id") if isinstance(tref, dict) else None
                    if tid:
                        task_to_page_id[tid] = page["id"]

            for t in tasks:
                tid = t.get("id")
                pid = task_to_page_id.get(tid or "")
                if not pid:
                    report.skipped_no_source_page += 1
                    continue
                insert_entity_row(pid, "TASK", tid, next_seq(pid))
                report.tasks += 1

            stem_to_page_id: dict[str, str] = {}
            for t in tasks:
                pid = task_to_page_id.get(t.get("id") or "")
                if not pid:
                    continue
                for sref in (t.get("stems") or []):
                    sid = sref.get("id") if isinstance(sref, dict) else None
                    if sid:
                        stem_to_page_id[sid] = pid

            for s in stems:
                sid = s.get("id")
                pid = stem_to_page_id.get(sid or "")
                if not pid:
                    report.skipped_no_source_page += 1
                    continue
                insert_entity_row(pid, "STEM", sid, next_seq(pid))
                report.stems += 1

            for img in images:
                if emit("IMAGE", img, img.get("id", ""),
                        layout_region=img.get("position")):
                    report.images += 1

            for p in prompts:
                if emit("INSTRUCTIONAL_PROMPT", p, p.get("id", "")):
                    report.instructional_prompts += 1

            for seg in segments:
                # Multi-page segment: emit one row per page in segment.pages[]
                seg_pages = seg.get("pages") or []
                seg_id = seg.get("id", "")
                emitted_any = False
                for spn in seg_pages:
                    page = page_by_number.get(int(spn))
                    if not page:
                        continue
                    insert_entity_row(
                        page["id"], "INSTRUCTIONAL_SEGMENT",
                        seg_id, next_seq(page["id"]),
                    )
                    emitted_any = True
                if emitted_any:
                    report.instructional_segments += 1
                else:
                    report.skipped_no_source_page += 1

            for ps in practice:
                # Practice section page: derive from contained activities (last)
                act_ids = [
                    (x.get("id") if isinstance(x, dict) else x)
                    for x in (ps.get("activities") or [])
                ]
                page_ids = []
                for aref in act_ids:
                    a = activity_by_id.get(aref)
                    if a is None:
                        continue
                    sp = a.get("sourcePage")
                    if sp is not None:
                        page = page_by_number.get(int(sp))
                        if page:
                            page_ids.append(page["id"])
                if page_ids:
                    pid = page_ids[-1]  # last page that hosts an activity
                    insert_entity_row(
                        pid, "PRACTICE_SECTION", ps.get("id", ""),
                        next_seq(pid),
                    )
                    report.practice_sections += 1
                else:
                    report.skipped_no_source_page += 1

            for sc in scaffolding:
                # Scaffolding page = its parent activity's page
                parent_act_id = sc.get("activityId") or sc.get("activity_id")
                pid = None
                if parent_act_id:
                    a = activity_by_id.get(parent_act_id)
                    if a is not None:
                        sp = a.get("sourcePage")
                        if sp is not None:
                            page = page_by_number.get(int(sp))
                            if page:
                                pid = page["id"]
                if pid:
                    insert_entity_row(
                        pid, "SCAFFOLDING", sc.get("id", ""), next_seq(pid),
                    )
                    report.scaffolding += 1
                else:
                    report.skipped_no_source_page += 1

            for ra in response:
                # Response area page = its stem's page
                stem_id = ra.get("stemId") or ra.get("stem_id")
                pid = stem_to_page_id.get(stem_id or "")
                if pid:
                    insert_entity_row(
                        pid, "RESPONSE_AREA", ra.get("id", ""), next_seq(pid),
                    )
                    report.response_areas += 1
                else:
                    report.skipped_no_source_page += 1

        conn.commit()
    except pymysql.MySQLError as e:
        conn.rollback()
        report.errors.append(f"db error: {e}")
        log.exception("page_indexer: rollback after MySQL error")
    finally:
        conn.close()

    return report
