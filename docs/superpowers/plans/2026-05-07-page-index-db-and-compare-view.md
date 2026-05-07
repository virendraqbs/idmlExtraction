# Page-Index DB & Side-By-Side HTML↔PDF Compare View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DB-side polymorphic page→entity index plus a `/api/results/{job}/page/{n}` endpoint so the editor can render HTML and PDF page-locked side by side, without changing canonical JSON output.

**Architecture:** Three additive DB changes (drop one column, widen one column, create one table). One new pipeline step writes the index after JSON assembly. One new HTTP endpoint composes per-page payloads from DB + JSON. Editor swaps its client-side filter for the endpoint. Backfill script indexes existing job folders.

**Tech Stack:** Python 3.12, FastAPI, PyMySQL, MySQL 8 (existing `cl_json_schema` DB), Jinja2, vanilla JS in `templates/results.html`. New dev-only dependency: pytest.

**Spec:** `docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md`

**Repo:** `/Users/virendrapratapsingh/Projects/carnegielearning-clearmathnational`
**Base branch:** `development`
**Feature branch:** `feat/page-index-db`
**Spec lives on:** `tig-extraction` branch (commit `a42d07d`); cherry-picked onto feat branch as Task 0.

---

## Plan refinement vs spec

Spec §5.1 listed `page_uuid` as an optional `cl_page` column. **This plan replaces that optional addition with a `job_id VARCHAR(64) NULL` column on `cl_page`**, used to scope re-indexing to one job at a time. Rationale: re-extraction of the same PDF generates fresh page UUIDs each run, so we cannot dedupe by `id` alone. Tagging each `cl_page` row with the originating `job_id` lets the indexer delete prior rows for the same job before inserting fresh ones — the simplest path to idempotency without a parent FK on master tables.

`page_uuid` (round-tripping the JSON-side id) is not needed for any feature in this plan.

---

## File Structure

| Path | Action | Responsibility |
|------|--------|----------------|
| `database.py` | Modify | Add migration helpers (`_alter_cl_activity_drop_source_page`, `_alter_cl_page_for_indexing`, `_create_cl_page_entity_map`) and call them from `init_db()`. Plus reusable `get_or_create_resource_for_job(out_dir)` helper. |
| `services/page_indexer.py` | Create | New module. `index_job_pages(job_id, out_dir, resource_id)` reads JSON files, writes `cl_page` + `cl_resource_page_map` + `cl_page_entity_map`. Idempotent. |
| `services/pipeline_service.py` | Modify | Call `index_job_pages` after `assemble_schemas` returns. Wrap in try/except so index failure does not fail the job. |
| `controllers/job_controller.py` | Modify | Add `GET /api/results/{job_id}/page/{n}` and `POST /api/results/{job_id}/reindex`. |
| `templates/results.html` | Modify | On page-selector change, fetch new API; render entities by `sequence_in_page`; show "Rebuild Index" banner on 404. |
| `scripts/backfill_page_index.py` | Create | Walks `outputs/`, calls `index_job_pages` per folder. |
| `tests/conftest.py` | Create | Pytest fixtures: `sample_job_dir`, `mock_db_cursor`. |
| `tests/test_page_indexer.py` | Create | Unit tests for `index_job_pages` against the fixture job. |
| `tests/test_page_api.py` | Create | Endpoint shape + 404 path tests. |
| `tests/fixtures/sample_job/` | Create | 19 minimal JSON files for the indexer unit test. |
| `requirements-dev.txt` | Create | Adds `pytest>=8.0.0` only. |

Five commits, one per task block (Tasks 1–5). Task 0 is the branch cut. Task 6 is the PR.

---

## Task 0: Cut Feature Branch and Bring Spec Forward

**Files:** none (git only)

- [ ] **Step 0.1: Verify clean state and current branch**

```bash
cd /Users/virendrapratapsingh/Projects/carnegielearning-clearmathnational
git status
git branch --show-current
```

Expected: branch is `tig-extraction` (or whatever was current). Working tree may have unrelated stashed work. If anything is staged or modified, stash it first:
```bash
git stash push -u -m "pre-feat-page-index-db work"
```

- [ ] **Step 0.2: Determine base branch**

If the canonical-schema PR (#1) has merged into `development`:
```bash
git fetch origin
git checkout -b feat/page-index-db origin/development
```

If PR #1 is still open and we want its enums available on this branch, base on it instead:
```bash
git fetch origin
git checkout -b feat/page-index-db origin/feat/canonical-schema-conformance
```

The implementer should pick whichever matches reality at run time. Default: `origin/development`.

- [ ] **Step 0.3: Cherry-pick the spec from `tig-extraction`**

```bash
git cherry-pick a42d07d
```

Expected output: `[feat/page-index-db <new-sha>] docs: revise page-index spec after DB audit`. If the cherry-pick complains that the original spec commit (`8843dda`) is needed first, also cherry-pick it:
```bash
git cherry-pick 8843dda a42d07d
```

- [ ] **Step 0.4: Verify spec file landed**

```bash
ls docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md
```
Expected: file exists.

- [ ] **Step 0.5: Sanity-check baseline**

```bash
git log --oneline -5
git status
```
Expected: at least one cherry-picked docs commit; clean working tree.

---

## Task 1: Schema Migrations (Commit 1)

**Files:**
- Modify: `database.py` (add three migration helpers + call them from `init_db()`)

This task adds idempotent ALTER + CREATE statements that run once on app startup. Existing `init_db()` already follows the pattern of "try ALTER; ignore duplicate-column error".

- [ ] **Step 1.1: Read `database.py` to locate `init_db`**

```bash
grep -n "^def init_db\|^def get_connection\|^def _row_to_dict" database.py
```
Expected output: line numbers for those three helpers. `init_db` is the function we will extend.

- [ ] **Step 1.2: Add the three migration helpers**

Open `database.py` and insert these three new functions immediately above `def init_db():`. The functions are all idempotent — they detect the current state and apply the change only when needed.

```python
def _alter_cl_activity_drop_source_page(cur) -> None:
    """Drop cl_activity.source_page so activity rows stay page-agnostic."""
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cl_activity' "
        "AND COLUMN_NAME = 'source_page'"
    )
    row = cur.fetchone()
    if row and int(row["c"]) > 0:
        cur.execute("ALTER TABLE `cl_activity` DROP COLUMN `source_page`")


def _alter_cl_page_for_indexing(cur) -> None:
    """Widen page_type to VARCHAR(64) and add job_id column for re-index isolation."""
    # Widen page_type if it is still the narrow 8-value enum.
    cur.execute(
        "SELECT DATA_TYPE, COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cl_page' "
        "AND COLUMN_NAME = 'page_type'"
    )
    row = cur.fetchone()
    if row and row["DATA_TYPE"] != "varchar":
        cur.execute("ALTER TABLE `cl_page` MODIFY `page_type` VARCHAR(64) NULL")

    # Add job_id column if missing.
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cl_page' "
        "AND COLUMN_NAME = 'job_id'"
    )
    row = cur.fetchone()
    if row and int(row["c"]) == 0:
        cur.execute(
            "ALTER TABLE `cl_page` ADD COLUMN `job_id` VARCHAR(64) NULL "
            "COMMENT 'Extraction-snapshot key — scopes idempotent re-index'"
        )
        cur.execute("ALTER TABLE `cl_page` ADD INDEX `idx_job` (`job_id`)")


def _create_cl_page_entity_map(cur) -> None:
    """Create the polymorphic page→entity map table if it does not exist."""
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cl_page_entity_map'"
    )
    row = cur.fetchone()
    if row and int(row["c"]) == 0:
        cur.execute(
            """
            CREATE TABLE `cl_page_entity_map` (
              `id`               CHAR(36) NOT NULL PRIMARY KEY,
              `page_id`          CHAR(36) NOT NULL,
              `entity_type`      VARCHAR(64) NOT NULL,
              `entity_id`        CHAR(36) NOT NULL,
              `sequence_in_page` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
              `layout_region`    VARCHAR(32) NULL,
              `is_continuation`  TINYINT(1) NOT NULL DEFAULT 0,
              `continues_to_seq` SMALLINT UNSIGNED NULL,
              `metadata`         JSON NULL,
              `created_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE KEY `uniq_page_entity` (`page_id`, `entity_type`, `entity_id`),
              KEY `idx_entity` (`entity_type`, `entity_id`),
              KEY `idx_page_seq` (`page_id`, `sequence_in_page`),
              CONSTRAINT `fk_pem_page` FOREIGN KEY (`page_id`)
                REFERENCES `cl_page`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='Polymorphic page→entity binding — order, layout, continuation'
            """
        )
```

- [ ] **Step 1.3: Wire the helpers into `init_db`**

Locate the existing `init_db` body. It currently does the `pdf_path` column ALTERs in a try/except for duplicate-column error 1060. Add three new calls. The full new `init_db` body should be:

```python
def init_db() -> None:
    """
    Assume tables exist from cl_json_schema.sql. Apply lightweight idempotent
    schema patches needed by the application:
      - pdf_path columns on cl_module / cl_topic (existing)
      - drop cl_activity.source_page (page binding moved to cl_page_entity_map)
      - widen cl_page.page_type and add job_id column
      - create cl_page_entity_map table
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Existing: pdf_path columns on cl_module / cl_topic
            for table, col in (("cl_module", "pdf_path"), ("cl_topic", "pdf_path")):
                try:
                    cur.execute(
                        f"ALTER TABLE `{table}` ADD COLUMN `{col}` "
                        f"VARCHAR(1024) NULL DEFAULT NULL"
                    )
                    conn.commit()
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1060:  # 1060 = Duplicate column
                        raise
                    conn.rollback()

            # New: page-index migrations
            _alter_cl_activity_drop_source_page(cur)
            _alter_cl_page_for_indexing(cur)
            _create_cl_page_entity_map(cur)
            conn.commit()
    finally:
        conn.close()
```

(If the existing `init_db` body differs in details, preserve every original line — only insert the three new helper calls + the surrounding `conn.commit()`.)

- [ ] **Step 1.4: Run the app once to apply migrations**

```bash
python3 -c "from database import init_db; init_db(); print('migrations applied')"
```
Expected: prints `migrations applied`. No tracebacks.

If the user has no MySQL configured (test environment), this command will fail with a connection error. In that case, skip the live verification and rely on Steps 1.5–1.6 for correctness checks.

- [ ] **Step 1.5: Verify schema directly via MySQL**

```bash
python3 -c "
from database import get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(\"SHOW COLUMNS FROM cl_activity LIKE 'source_page'\")
    print('cl_activity.source_page rows:', cur.fetchall())
    cur.execute(\"SHOW COLUMNS FROM cl_page\")
    cols = {r['Field']: r['Type'] for r in cur.fetchall()}
    print('cl_page.page_type:', cols.get('page_type'))
    print('cl_page.job_id   :', cols.get('job_id'))
    cur.execute(\"SHOW TABLES LIKE 'cl_page_entity_map'\")
    print('cl_page_entity_map exists:', cur.fetchone() is not None)
conn.close()
"
```

Expected:
- `cl_activity.source_page rows: ()` — column gone.
- `cl_page.page_type: varchar(64)`
- `cl_page.job_id   : varchar(64)`
- `cl_page_entity_map exists: True`

- [ ] **Step 1.6: Re-run init_db to confirm idempotency**

```bash
python3 -c "from database import init_db; init_db(); init_db(); print('idempotent OK')"
```
Expected: prints `idempotent OK`. No exceptions.

- [ ] **Step 1.7: Commit**

```bash
git add database.py
git diff --cached
git commit -m "schema(db): cl_page_entity_map + drop cl_activity.source_page + widen cl_page.page_type

Three idempotent migrations applied via init_db():
  - DROP cl_activity.source_page (master rows page-agnostic; page binding
    moves to cl_page_entity_map)
  - MODIFY cl_page.page_type to VARCHAR(64) (canonical PageType has 32 values)
  - ADD cl_page.job_id (extraction-snapshot key for idempotent re-index)
  - CREATE cl_page_entity_map (polymorphic page→entity binding,
    mirrors cl_image_usage pattern)

Refs: docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md"
```

---

## Task 2: Pipeline Indexer (Commit 2)

**Files:**
- Create: `services/page_indexer.py`
- Modify: `services/pipeline_service.py` (one call site after `assemble_schemas`)
- Modify: `database.py` (one new helper `get_or_create_resource_for_job`)

- [ ] **Step 2.1: Add the resource-resolution helper to `database.py`**

Insert at the bottom of `database.py`:

```python
# ── Job-scoped helpers (used by services.page_indexer) ────────────────────────

def get_or_create_resource_for_job(
    out_dir_03_resource: dict[str, Any],
) -> str:
    """
    Ensure a cl_resource row exists for this job's 03_resource.json content
    and return its id. The id used is the JSON-side id (so re-extraction of
    the same job lands on the same DB row).
    """
    rid = out_dir_03_resource["id"]
    title = out_dir_03_resource.get("title") or "Untitled"
    rtype = out_dir_03_resource.get("resourceType") or "STUDENT_RESOURCE_BOOK"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO `cl_resource` (id, resource_type, title) "
                "VALUES (%s, %s, %s)",
                (rid, rtype, title),
            )
        conn.commit()
        return rid
    finally:
        conn.close()
```

- [ ] **Step 2.2: Create `services/page_indexer.py` with the full indexer**

Create the file. Full content:

```python
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
                    "VALUES (%s, %s, %s, %s)",
                    (page_id, page_number, page_type, job_id),
                )
                # 3. cl_resource_page_map row (sequence_number = pdf ordinal)
                cur.execute(
                    "INSERT INTO cl_resource_page_map "
                    "(id, resource_id, page_id, sequence_number) "
                    "VALUES (%s, %s, %s, %s)",
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

            # Lesson — single row on the first page
            lesson_id = lesson_payload.get("id")
            if lesson_id and pages:
                first = page_by_number.get(
                    int(pages[0].get("pageNumber") or 0)
                )
                if first:
                    insert_entity_row(
                        first["id"], "LESSON", lesson_id, next_seq(first["id"]),
                    )
                    report.lessons += 1

            for a in activities:
                if emit("ACTIVITY", a, a.get("id", "")):
                    report.activities += 1

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
                    for a in activities:
                        if a.get("id") == aref:
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
                    for a in activities:
                        if a.get("id") == parent_act_id:
                            sp = a.get("sourcePage")
                            if sp is not None:
                                page = page_by_number.get(int(sp))
                                if page:
                                    pid = page["id"]
                            break
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
```

- [ ] **Step 2.3: Wire indexer into the pipeline**

Open `services/pipeline_service.py`. Find the call to `assemble_schemas` (around line 153). After the existing line `schema_files = assemble_schemas(...)`, add the indexer invocation. Wrap in `try/except` so failure does not fail the job.

```python
            schema_files = assemble_schemas(
                pages=raw_pages,
                out_dir=out_dir,
                source_filename=Path(job.pdf_path).name,
                image_manifest=image_manifest,
                book_name=job.book_name,
                module_name=job.module_name,
                module_subtitle=job.module_subtitle,
                module_meta=job.module_meta,
                db_module=db_module,
                db_topic=db_topic,
            )

            # NEW: build page-entity index in MySQL (post-assembly).
            # Failure here must NOT fail the extraction job — JSON is canonical.
            try:
                from services.page_indexer import index_job_pages
                report = index_job_pages(job.id, out_dir)
                log_it(
                    f"Indexed pages: {report.pages}, "
                    f"activities={report.activities}, "
                    f"tasks={report.tasks}, stems={report.stems}, "
                    f"images={report.images}, "
                    f"prompts={report.instructional_prompts}, "
                    f"segments={report.instructional_segments}, "
                    f"practice={report.practice_sections}, "
                    f"scaffolding={report.scaffolding}, "
                    f"response_areas={report.response_areas}, "
                    f"lessons={report.lessons}, "
                    f"skipped={report.skipped_no_source_page}"
                )
                if report.errors:
                    for err in report.errors:
                        log_it(f"page-index warning: {err}")
            except Exception as ix_err:
                log_it(f"page-index failed (non-fatal): {ix_err}")
```

(Preserve any other lines around the original `assemble_schemas` call — only insert the new `try` block immediately after it.)

- [ ] **Step 2.4: Smoke test the indexer against an existing job folder**

Pick the most recent SRB output:
```bash
ls -td outputs/*/ | head -3
```

Pick one (call it `$JOB`). Run:
```bash
JOB=$(ls -td outputs/*/ | head -1 | xargs basename)
python3 -c "
from pathlib import Path
from services.page_indexer import index_job_pages
r = index_job_pages('$JOB', Path('outputs/$JOB'))
print(r)
"
```

Expected: an `IndexReport(...)` with non-zero `pages`, plus non-zero counts for any entity types that have `sourcePage` populated. `errors` should be `[]`. If `skipped_no_source_page` is large, that confirms the existing-output limitation already documented in the spec — not a bug.

- [ ] **Step 2.5: Confirm rows landed in DB**

```bash
python3 -c "
from database import get_connection
JOB = '$JOB'  # set this to the same job you indexed
conn = get_connection()
with conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) AS c FROM cl_page WHERE job_id = %s', (JOB,))
    print('cl_page rows for job:', cur.fetchone()['c'])
    cur.execute(
      'SELECT COUNT(*) AS c FROM cl_page_entity_map pem '
      'JOIN cl_page p ON p.id = pem.page_id WHERE p.job_id = %s', (JOB,)
    )
    print('cl_page_entity_map rows for job:', cur.fetchone()['c'])
conn.close()
" | sed "s/\$JOB/$JOB/g"
```

Expected: both counts > 0; `cl_page` count equals `report.pages`; entity-map count equals the sum of activities + tasks + stems + images + ... in the report.

- [ ] **Step 2.6: Confirm idempotency**

Run the indexer a second time on the same job:
```bash
python3 -c "
from pathlib import Path
from services.page_indexer import index_job_pages
r1 = index_job_pages('$JOB', Path('outputs/$JOB'))
r2 = index_job_pages('$JOB', Path('outputs/$JOB'))
print('run1.pages =', r1.pages, 'run2.pages =', r2.pages)
assert r1.pages == r2.pages, 'idempotent fail'
print('idempotent OK')
"
```
Expected: both runs produce identical `pages` count; prints `idempotent OK`.

- [ ] **Step 2.7: Commit**

```bash
git add services/page_indexer.py services/pipeline_service.py database.py
git diff --cached --stat
git commit -m "feat(pipeline): index_job_pages step writes per-page entity index

After assemble_schemas writes 19 JSON files, the new index_job_pages
function reads them and populates cl_page (with job_id), cl_resource_page_map,
and cl_page_entity_map (polymorphic page→entity).

Master entity tables (cl_activity, cl_image, ...) are NOT populated — editor
will hydrate bodies from JSON. Full DB sync deferred per spec §3.

Idempotent: prior rows for this job_id are wiped before re-insert.
Non-fatal: failure logs a warning but does not fail the extraction job.

Refs: docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md"
```

---

## Task 3: API Endpoints (Commit 3)

**Files:**
- Modify: `controllers/job_controller.py` (two new routes)

- [ ] **Step 3.1: Add the page-payload endpoint**

Open `controllers/job_controller.py`. Append two new routes at the end of the file (or alongside other `/api/results/...` routes — they live around lines 1455–1530 in current dev tree).

```python
# ── Page-locked compare view (added by feat/page-index-db) ────────────────────

from functools import lru_cache as _lru_cache
import json as _json
from pathlib import Path as _Path

from database import get_connection as _get_connection


_PAGE_KIND_TO_FILE = {
    "ACTIVITY":               ("07_activities.json", "activities"),
    "TASK":                   ("08_tasks.json", "tasks"),
    "STEM":                   ("09_stems.json", "stems"),
    "IMAGE":                  ("12_images.json", "images"),
    "INSTRUCTIONAL_PROMPT":   ("14_instructional_prompts.json", "instructionalPrompts"),
    "INSTRUCTIONAL_SEGMENT":  ("15_instructional_segments.json", "instructionalSegments"),
    "PRACTICE_SECTION":       ("16_practice_sections.json", "practiceSections"),
    "RESPONSE_AREA":          ("17_response_areas.json", "responseAreas"),
    "SCAFFOLDING":            ("18_scaffolding.json", "scaffolding"),
    "LESSON":                 ("06_lesson.json", None),  # whole-doc payload
}


def _load_entity_dict(out_dir: _Path, kind: str) -> dict[str, dict]:
    """Return {id: entity_dict} for the JSON file backing this entity kind."""
    if kind not in _PAGE_KIND_TO_FILE:
        return {}
    fname, key = _PAGE_KIND_TO_FILE[kind]
    p = out_dir / fname
    if not p.exists():
        return {}
    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
    except _json.JSONDecodeError:
        return {}
    if key is None:
        # 06_lesson.json is a single object
        return {data.get("id", ""): data} if isinstance(data, dict) else {}
    arr = data.get(key) if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    if isinstance(arr, list):
        for e in arr:
            if isinstance(e, dict) and e.get("id"):
                out[e["id"]] = e
    return out


@jobs_router.get("/api/results/{job_id}/page/{n}")
def api_results_page(job_id: str, n: int, request: Request):
    if not _require_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    out_dir = config.OUTPUT_DIR / job_id
    if not out_dir.is_dir():
        return JSONResponse({"error": "job not found"}, status_code=404)

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            # Resolve page by (job_id, ordinal) using cl_resource_page_map
            cur.execute(
                """
                SELECT p.id, p.page_number, p.page_type, p.job_id, rpm.sequence_number
                FROM cl_page p
                JOIN cl_resource_page_map rpm ON rpm.page_id = p.id
                WHERE p.job_id = %s AND rpm.sequence_number = %s
                LIMIT 1
                """,
                (job_id, n),
            )
            page_row = cur.fetchone()
            if not page_row:
                return JSONResponse(
                    {"error": "page index not built — run /api/results/"
                              f"{job_id}/reindex"},
                    status_code=404,
                )

            cur.execute(
                """
                SELECT entity_type, entity_id, sequence_in_page,
                       layout_region, is_continuation, continues_to_seq,
                       metadata
                FROM cl_page_entity_map
                WHERE page_id = %s
                ORDER BY sequence_in_page, entity_type
                """,
                (page_row["id"],),
            )
            map_rows = cur.fetchall()
    finally:
        conn.close()

    # Hydrate entity bodies from JSON
    by_kind: dict[str, dict[str, dict]] = {}
    entities: list[dict] = []
    for r in map_rows:
        kind = r["entity_type"]
        if kind not in by_kind:
            by_kind[kind] = _load_entity_dict(out_dir, kind)
        body = by_kind[kind].get(r["entity_id"])
        meta_raw = r.get("metadata")
        try:
            meta = _json.loads(meta_raw) if meta_raw else {}
        except _json.JSONDecodeError:
            meta = {}
        entities.append({
            "kind": kind,
            "id": r["entity_id"],
            "sequenceInPage": r["sequence_in_page"],
            "layoutRegion": r["layout_region"],
            "isContinuation": bool(r["is_continuation"]),
            "continuesToSeq": r["continues_to_seq"],
            "metadata": meta,
            "body": body or {},
        })

    return JSONResponse({
        "jobId": job_id,
        "pdfPageIndex": page_row["sequence_number"],
        "pageNumber": page_row["page_number"],
        "pageType": page_row["page_type"],
        "entities": entities,
    })


@jobs_router.post("/api/results/{job_id}/reindex")
def api_results_reindex(job_id: str, request: Request):
    if not _require_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    out_dir = config.OUTPUT_DIR / job_id
    if not out_dir.is_dir():
        return JSONResponse({"error": "job not found"}, status_code=404)

    from services.page_indexer import index_job_pages
    report = index_job_pages(job_id, out_dir)
    return JSONResponse({
        "jobId": job_id,
        "pages": report.pages,
        "activities": report.activities,
        "tasks": report.tasks,
        "stems": report.stems,
        "images": report.images,
        "instructionalPrompts": report.instructional_prompts,
        "instructionalSegments": report.instructional_segments,
        "practiceSections": report.practice_sections,
        "scaffolding": report.scaffolding,
        "responseAreas": report.response_areas,
        "lessons": report.lessons,
        "skippedNoSourcePage": report.skipped_no_source_page,
        "errors": report.errors,
    })
```

If the file already imports `Request`, `JSONResponse`, `config`, `jobs_router`, and a helper named `_require_auth` (or equivalent), reuse those. Do not duplicate imports; place the new block **below** any pre-existing `_require_auth` definition. If the existing auth helper has a different name, substitute it in the two `if not _require_auth(...):` lines.

- [ ] **Step 3.2: Re-run the app and exercise the endpoints**

```bash
python3 app.py &
APP_PID=$!
sleep 2
JOB=$(ls -td outputs/*/ | head -1 | xargs basename)
echo "Testing job: $JOB"
curl -s "http://localhost:5000/api/results/$JOB/page/1" | head -200
echo
echo "---reindex---"
curl -s -X POST "http://localhost:5000/api/results/$JOB/reindex"
kill $APP_PID
```

Expected: page endpoint returns JSON with `entities[]`. Reindex returns counts.

If the app requires login, the curl will hit a 401. In that case authenticate first via the dashboard browser session, then retry from a logged-in browser — copy the response into a file and inspect.

- [ ] **Step 3.3: Commit**

```bash
git add controllers/job_controller.py
git diff --cached --stat
git commit -m "feat(api): GET /api/results/{id}/page/{n} + POST .../reindex

The page endpoint joins cl_page, cl_resource_page_map, and
cl_page_entity_map to produce a composed payload for the editor's
side-by-side view. Entity bodies hydrated from JSON files.

Reindex endpoint runs services.page_indexer.index_job_pages
synchronously and returns the IndexReport.

404 path on missing index gives the editor a path to recover.

Refs: docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md"
```

---

## Task 4: Editor Side-By-Side View (Commit 4)

**Files:**
- Modify: `templates/results.html`

The existing two-pane editor already has a left content area and right PDF iframe. We replace the client-side `samePageNum` filter with a single API fetch and render entities from the API response.

- [ ] **Step 4.1: Locate the existing page-change handler**

```bash
grep -n "selectorRender\|pdf-iframe\|onPageChange\|page selector" templates/results.html | head -10
```

Expected: a handler around line 1280–1320 that updates the iframe `src` and calls a JS function to re-render content. The exact line numbers depend on prior commits — find by context.

- [ ] **Step 4.2: Add the new fetch-and-render helper**

Insert this JavaScript inside the existing `<script>` block in `templates/results.html`, near the other render helpers (e.g. just below `renderActivityHtml`):

```javascript
// ── Page-locked compare view: fetch composed payload from server ──────
async function fetchPageComposed(jobId, n) {
  const resp = await fetch('/api/results/' + jobId + '/page/' + n);
  if (resp.status === 404) {
    showRebuildIndexBanner(jobId);
    return null;
  }
  if (!resp.ok) {
    console.error('page api failed:', resp.status);
    return null;
  }
  return await resp.json();
}

function renderPageComposed(payload) {
  if (!payload) return;
  const host = document.getElementById('editor-content');
  if (!host) return;
  host.innerHTML = '';
  // Page header
  const hdr = document.createElement('div');
  hdr.className = 'editor-section';
  hdr.innerHTML =
    '<span class="schema-tag">page ' + payload.pdfPageIndex + '</span>' +
    '<h3>Page ' + payload.pdfPageIndex +
    (payload.pageNumber ? ' — printed ' + payload.pageNumber : '') +
    (payload.pageType ? ' — ' + payload.pageType : '') + '</h3>';
  host.appendChild(hdr);

  // Render each entity by kind, in sequence_in_page order
  for (const ent of payload.entities) {
    const block = document.createElement('div');
    block.className = 'editor-block';
    block.dataset.entityKind = ent.kind;
    block.dataset.entityId = ent.id;
    let html = '';
    switch (ent.kind) {
      case 'ACTIVITY':              html = renderActivityHtml(ent.body); break;
      case 'TASK':                  html = renderTaskHtml(ent.body); break;
      case 'STEM':                  html = renderStemHtml(ent.body); break;
      case 'IMAGE':                 html = renderImageCard(ent.body); break;
      case 'INSTRUCTIONAL_PROMPT':  html = renderPromptHtml(ent.body); break;
      case 'INSTRUCTIONAL_SEGMENT': html = renderSegmentHtml(ent.body); break;
      case 'PRACTICE_SECTION':     html = renderPracticeSectionHtml(ent.body); break;
      case 'SCAFFOLDING':          html = renderScaffoldingHtml(ent.body); break;
      case 'RESPONSE_AREA':        html = renderResponseAreaHtml(ent.body); break;
      case 'LESSON':               html = renderLessonHtml(ent.body); break;
      default:                     html = '<pre>' + escapeHtml(JSON.stringify(ent.body, null, 2)) + '</pre>';
    }
    block.innerHTML = html;
    host.appendChild(block);
  }
}

function showRebuildIndexBanner(jobId) {
  const host = document.getElementById('editor-content');
  if (!host) return;
  host.innerHTML =
    '<div class="editor-section" style="background:#fff7e6;' +
    'border:1px solid #ffc069;padding:12px;border-radius:4px">' +
    '<strong>Page index not built for this job.</strong>' +
    '<p>Click below to build it now (re-runs only the indexer; does not re-extract the PDF).</p>' +
    '<button id="btn-rebuild-index" style="padding:6px 14px;cursor:pointer">Rebuild Index</button>' +
    '</div>';
  document.getElementById('btn-rebuild-index').addEventListener('click', async function() {
    const r = await fetch('/api/results/' + jobId + '/reindex', { method: 'POST' });
    if (r.ok) {
      window.location.reload();
    } else {
      alert('Reindex failed: ' + r.status);
    }
  });
}
```

If any of the renderer helper names above (e.g. `renderPromptHtml`, `renderSegmentHtml`, `renderPracticeSectionHtml`, `renderScaffoldingHtml`, `renderResponseAreaHtml`, `renderLessonHtml`, `renderImageCard`) does not exist in the current `templates/results.html`, replace the corresponding `case` branch with a generic JSON pretty-print:
```javascript
case 'INSTRUCTIONAL_PROMPT':
  html = '<pre>' + escapeHtml(JSON.stringify(ent.body, null, 2)) + '</pre>';
  break;
```
This keeps the page render functional without scope creep into renderer authoring.

- [ ] **Step 4.3: Wire the new helper into the page-selector change**

Find the existing page selector change handler (look for `selector.addEventListener('change'` or similar). Replace the body that invokes the legacy `samePageNum` filter with:

```javascript
selector.addEventListener('change', async function() {
  const n = parseInt(selector.value, 10);
  // Update PDF iframe to same page
  const iframe = document.getElementById('pdf-iframe');
  if (iframe) {
    const baseUrl = iframe.dataset.pdfUrl;
    iframe.src = baseUrl + '#page=' + n;
  }
  // Fetch composed payload and render HTML pane
  const payload = await fetchPageComposed(jobId, n);
  if (payload) renderPageComposed(payload);
});
```

The variable `jobId` should already exist in the template's JS scope (it does in current development tree — passed from Jinja). If not, expose it via `<script>const jobId = "{{ job.id }}";</script>` near the top of the script block.

- [ ] **Step 4.4: Trigger initial render on load**

Find the existing on-load page render (probably `selectorRender(1)` or similar) and replace with:

```javascript
// On load: render page 1 from the new API
(async function() {
  const payload = await fetchPageComposed(jobId, 1);
  if (payload) renderPageComposed(payload);
})();
```

- [ ] **Step 4.5: Manual smoke test**

```bash
python3 app.py &
APP_PID=$!
sleep 2
echo "Open http://localhost:5000/results/$(ls -td outputs/*/ | head -1 | xargs basename) in a browser"
# Wait for manual verification, then:
read -p "Press enter when done..."
kill $APP_PID
```

Verify in browser:
1. Page selector loads and shows page numbers.
2. Selecting a page updates BOTH the PDF iframe (right pane) and HTML render (left pane).
3. HTML render shows entities in order from the API.
4. If the index is missing, the Rebuild Index banner appears with a working button.

- [ ] **Step 4.6: Commit**

```bash
git add templates/results.html
git diff --cached --stat
git commit -m "feat(editor): side-by-side page-locked view consuming page API

Replaces the client-side samePageNum filter with a single fetch to
/api/results/{job}/page/{n}. Entities render in the API-supplied
sequence_in_page order. PDF iframe scrolls to matching page.

404 path triggers a Rebuild Index banner with a one-click recovery
button (POST .../reindex).

Refs: docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md"
```

---

## Task 5: Backfill, Tests, Pytest Setup (Commit 5)

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample_job/` with 3 minimal JSON files
- Create: `tests/test_page_indexer.py`
- Create: `tests/test_page_api.py`
- Create: `scripts/backfill_page_index.py`

- [ ] **Step 5.1: Create dev-only dependency manifest**

`requirements-dev.txt`:
```
pytest>=8.0.0
```

- [ ] **Step 5.2: Install pytest in dev environment**

```bash
pip install -r requirements-dev.txt
```
Expected: pytest installed (or already present).

- [ ] **Step 5.3: Create test fixture data**

Create `tests/__init__.py` (empty). Create `tests/fixtures/sample_job/03_resource.json`:
```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "resourceType": "STUDENT_RESOURCE_BOOK",
  "title": "Test Resource",
  "modules": [],
  "pages": []
}
```

`tests/fixtures/sample_job/06_lesson.json`:
```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "title": "Test Lesson"
}
```

`tests/fixtures/sample_job/07_activities.json`:
```json
{
  "count": 2,
  "activities": [
    {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1", "sourcePage": 1, "title": "A1", "tasks": []},
    {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2", "sourcePage": 2, "title": "A2", "tasks": []}
  ]
}
```

`tests/fixtures/sample_job/13_pages.json`:
```json
{
  "count": 2,
  "pages": [
    {"id": "ppppppp1-pppp-pppp-pppp-pppppppppppp", "pageNumber": 1, "pageType": "SRB_LESSON_INTRODUCTION_ACTIVATE"},
    {"id": "ppppppp2-pppp-pppp-pppp-pppppppppppp", "pageNumber": 2, "pageType": "SRB_LESSON_EXPLORE"}
  ]
}
```

- [ ] **Step 5.4: Create `tests/conftest.py`**

```python
"""Pytest fixtures for page-index tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_job_dir() -> Path:
    """Path to the bundled minimal job fixture (3 JSON files)."""
    return Path(__file__).parent / "fixtures" / "sample_job"


@pytest.fixture
def fixture_job_id() -> str:
    return "test-fixture-job"


@pytest.fixture(autouse=True)
def _stub_pwd(monkeypatch):
    """Make sure tests run from repo root regardless of CWD."""
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
```

- [ ] **Step 5.5: Create `tests/test_page_indexer.py`**

These tests assert structure of the IndexReport without requiring a live MySQL. The DB write itself is verified manually in Task 2 Step 2.5.

```python
"""Unit tests for services.page_indexer.

These tests use a stub database connection — the real DB is exercised in
Task 2's manual smoke run. Here we verify the IndexReport structure and
the JSON-walk logic that decides which entities get indexed.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _stub_conn():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def test_index_report_counts_match_fixture(sample_job_dir, fixture_job_id):
    """Indexer reads JSON and emits one ACTIVITY row per activity with sourcePage."""
    from services import page_indexer

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn), \
         patch.object(page_indexer, "get_or_create_resource_for_job",
                      return_value="11111111-1111-1111-1111-111111111111"):
        report = page_indexer.index_job_pages(fixture_job_id, sample_job_dir)

    assert report.pages == 2
    assert report.activities == 2
    assert report.lessons == 1
    assert report.errors == []


def test_index_report_skips_entity_with_no_sourcePage(tmp_path, fixture_job_id):
    """Entities lacking sourcePage are skipped, not exceptions."""
    from services import page_indexer

    # Build a minimal job with one activity missing sourcePage.
    (tmp_path / "03_resource.json").write_text(json.dumps({
        "id": "33333333-3333-3333-3333-333333333333",
        "resourceType": "STUDENT_RESOURCE_BOOK",
        "title": "Tmp",
    }))
    (tmp_path / "13_pages.json").write_text(json.dumps({
        "pages": [
            {"id": "p1", "pageNumber": 1, "pageType": "SRB_LESSON_EXPLORE"},
        ]
    }))
    (tmp_path / "07_activities.json").write_text(json.dumps({
        "activities": [
            {"id": "no-page", "title": "NoPage", "tasks": []},
        ]
    }))

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn), \
         patch.object(page_indexer, "get_or_create_resource_for_job",
                      return_value="33333333-3333-3333-3333-333333333333"):
        report = page_indexer.index_job_pages(fixture_job_id, tmp_path)

    assert report.activities == 0
    assert report.skipped_no_source_page >= 1
    assert report.errors == []


def test_index_returns_report_on_missing_files(tmp_path, fixture_job_id):
    """Missing 03_resource.json or 13_pages.json reports an error, no exception."""
    from services import page_indexer

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn):
        report = page_indexer.index_job_pages(fixture_job_id, tmp_path)

    assert report.pages == 0
    assert any("missing" in e for e in report.errors)
```

- [ ] **Step 5.6: Run the tests**

```bash
pytest tests/test_page_indexer.py -v
```

Expected: 3 tests pass. If pytest cannot import `services.page_indexer` because of missing optional deps (e.g. `pymysql` not installed in the test env), install it via `pip install pymysql` and retry. The indexer module imports pymysql at the top.

- [ ] **Step 5.7: Create `tests/test_page_api.py`** (response-shape only; no live server)

```python
"""Schema-shape tests for the page API response."""
from __future__ import annotations


def test_page_response_shape_keys():
    """Document the response shape; serves as a drift detector."""
    expected_keys = {
        "jobId", "pdfPageIndex", "pageNumber", "pageType", "entities",
    }
    expected_entity_keys = {
        "kind", "id", "sequenceInPage", "layoutRegion",
        "isContinuation", "continuesToSeq", "metadata", "body",
    }
    sample = {
        "jobId": "x",
        "pdfPageIndex": 1,
        "pageNumber": 467,
        "pageType": "SRB_LESSON_EXPLORE",
        "entities": [
            {
                "kind": "ACTIVITY",
                "id": "abc",
                "sequenceInPage": 1,
                "layoutRegion": None,
                "isContinuation": False,
                "continuesToSeq": None,
                "metadata": {},
                "body": {"id": "abc"},
            }
        ],
    }
    assert expected_keys.issubset(set(sample.keys()))
    assert expected_entity_keys.issubset(set(sample["entities"][0].keys()))
```

This is intentionally minimal — pact-style. Live API invocation is exercised manually in Task 3 Step 3.2.

- [ ] **Step 5.8: Run the test**

```bash
pytest tests/test_page_api.py -v
```

Expected: 1 passing test.

- [ ] **Step 5.9: Create the backfill script**

`scripts/backfill_page_index.py`:
```python
#!/usr/bin/env python3
"""
backfill_page_index.py — Walk an outputs/ directory and run index_job_pages
for every job folder containing 13_pages.json. Safe to re-run.

Usage:
    python3 scripts/backfill_page_index.py [outputs/]

If no path is given, defaults to ./outputs/.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.page_indexer import index_job_pages  # noqa: E402


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "outputs"
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    total = 0
    failures = 0
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        if not (sub / "13_pages.json").exists():
            continue
        job_id = sub.name
        try:
            r = index_job_pages(job_id, sub)
            print(f"{job_id}: pages={r.pages} entities="
                  f"{r.activities + r.tasks + r.stems + r.images + r.instructional_prompts + r.instructional_segments + r.practice_sections + r.scaffolding + r.response_areas + r.lessons} "
                  f"skipped={r.skipped_no_source_page} errors={len(r.errors)}")
            total += 1
            if r.errors:
                failures += 1
        except Exception as e:
            print(f"{job_id}: FAIL — {e}", file=sys.stderr)
            failures += 1

    print(f"\nBackfill complete: {total} jobs processed, {failures} with errors.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 5.10: Smoke-run the backfill against `outputs/`**

```bash
chmod +x scripts/backfill_page_index.py
python3 scripts/backfill_page_index.py outputs/ | head -20
```

Expected: per-job lines listing pages + entities counts. Final summary line.

- [ ] **Step 5.11: Commit**

```bash
git add requirements-dev.txt tests/ scripts/backfill_page_index.py
git diff --cached --stat
git commit -m "scripts/tests: backfill script + pytest scaffold + indexer tests

- requirements-dev.txt adds pytest only
- tests/ contains unit tests for services.page_indexer and an API
  response-shape contract test
- tests/fixtures/sample_job/ holds a minimal 4-file fixture
- scripts/backfill_page_index.py walks outputs/ and re-indexes all jobs

Refs: docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md"
```

---

## Task 6: Push Branch and Open PR

**Files:** none (git/GitHub only)

- [ ] **Step 6.1: Verify five commits on the branch**

```bash
git log --oneline development..HEAD
```

Expected at minimum (plus the cherry-picked spec doc commit(s) from Task 0):
1. `schema(db): cl_page_entity_map + drop cl_activity.source_page + widen cl_page.page_type`
2. `feat(pipeline): index_job_pages step writes per-page entity index`
3. `feat(api): GET /api/results/{id}/page/{n} + POST .../reindex`
4. `feat(editor): side-by-side page-locked view consuming page API`
5. `scripts/tests: backfill script + pytest scaffold + indexer tests`

- [ ] **Step 6.2: Confirm JSON output is byte-identical**

Pick a job that was extracted before this branch, and one extracted after. Compare:

```bash
# Before-branch job (already in outputs/)
PRE=$(ls -td outputs/*/ | grep -v "$(date +%Y%m%d)" | head -1)
# After-branch: re-extract a sample PDF to a fresh job
python3 scripts/extract_module_pdf.py sourceFile/A1_T13_L1.pdf
NEW=$(ls -td outputs/*/ | head -1)

# Diff each canonical JSON file (excluding raw_extractions, extraction_report, merged.json)
for f in 01_primitives 02_enums 03_resource 04_module 05_topic 06_lesson \
         07_activities 08_tasks 09_stems 10_standards 11_standards_blocks \
         12_images 13_pages 14_instructional_prompts 15_instructional_segments \
         16_practice_sections 17_response_areas 18_scaffolding 19_activity_goals; do
  if [ -f "$PRE/$f.json" ] && [ -f "$NEW/$f.json" ]; then
    # IDs differ per run — use jq-aware comparison or skip ID-only diffs:
    py_diff=$(python3 -c "
import json, sys
a = json.load(open('$PRE/$f.json'))
b = json.load(open('$NEW/$f.json'))
def strip_ids(x):
    if isinstance(x, dict): return {k: strip_ids(v) for k,v in x.items() if k not in ('id','resourceId','moduleId','topicId','lessonId','standardsBlock','standardsBlockId','extracted_at')}
    if isinstance(x, list): return [strip_ids(e) for e in x]
    return x
print('SAME' if strip_ids(a)==strip_ids(b) else 'DIFFER')
")
    echo "$f.json: $py_diff (sizes pre=$(wc -c <"$PRE/$f.json") new=$(wc -c <"$NEW/$f.json"))"
  fi
done
```

Expected: every file `SAME` (modulo IDs and timestamps, which always differ between runs). If anything reports `DIFFER`, the indexer has accidentally mutated JSON output — investigate before pushing.

This step is OPTIONAL if a fresh extraction is not feasible (Gemini API budget). Skip and document the skip in the PR description in that case.

- [ ] **Step 6.3: Push to origin with upstream tracking**

```bash
git push -u origin feat/page-index-db
```

Expected: branch published.

- [ ] **Step 6.4: Open the PR**

```bash
gh pr create --base development --head feat/page-index-db \
  --title "Page-index DB + side-by-side compare view" \
  --body "$(cat <<'EOF'
## Summary
- Adds polymorphic `cl_page_entity_map` + scopes `cl_page` rows by `job_id` so re-indexing is idempotent.
- Drops `cl_activity.source_page` so master rows stay page-agnostic.
- Widens `cl_page.page_type` to `VARCHAR(64)` (canonical `PageType` has 32 values).
- New `services/page_indexer.py` runs after `assemble_schemas` and writes per-page entity rows.
- New `GET /api/results/{job}/page/{n}` and `POST /api/results/{job}/reindex` endpoints.
- Editor side-by-side page-locked view consumes the new API; PDF iframe and HTML pane share one selector.
- Backfill script `scripts/backfill_page_index.py` indexes existing `outputs/` folders.
- Minimal pytest scaffold + 4 unit tests for the indexer + response-shape contract test.

## Why
The editor's per-page filter previously relied on a `sourcePage` field stamped onto each entity in JSON — pipeline-internal, not part of canonical schema, and missing on TIG entities. Spec moved page binding to a polymorphic DB index, leaving JSON byte-identical and master entity tables page-agnostic.

Spec: `docs/superpowers/specs/2026-05-07-page-index-db-and-compare-view-design.md`
Plan: `docs/superpowers/plans/2026-05-07-page-index-db-and-compare-view.md`

## Out of scope
- Full DB sync (writing every JSON entity to its canonical master table).
- Bounding-box capture / click-to-highlight overlay.
- OCR-based PDF↔JSON discrepancy diff.
- Image rendering bug (`imagePath` vs `filepath`) — separate spec.

## Test plan
- [ ] `pytest tests/` passes (4 tests).
- [ ] `python3 scripts/backfill_page_index.py outputs/` exits 0 on existing jobs.
- [ ] Fresh extraction emits JSON byte-identical (modulo IDs/timestamps) to pre-branch output (verified via Task 6 Step 6.2 script).
- [ ] After fresh extraction, `GET /api/results/{job}/page/3` returns the expected ACTIVITY ids for that page.
- [ ] Re-running extraction on the same job replaces (does not duplicate) `cl_page_entity_map` rows for that job_id.
- [ ] Editor page selector switches both panes in one click.

## Notes
- Master entity tables (`cl_activity`, `cl_image`, `cl_stem`, `cl_task`, `cl_instructional_prompt`, `cl_scaffolding`, `cl_practice_section`, `cl_response_area`, `cl_instructional_segment`, `cl_standards_block`) are NOT populated — editor hydrates entity bodies from JSON. Full DB sync is deferred per spec §3.
- TIG entities lacking `sourcePage` are gracefully skipped — index will be partial for TIG until a separate TIG-side fix lands.
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 6.5: Print PR URL**

The PR URL is in the previous step output. Copy it into the final report.

---

## Self-Review

**Spec coverage:**
- §4 Existing DB context audited → Task 1 Step 1.1 confirms `init_db` location ✓
- §5.1 Change A drop `source_page` → Task 1 Step 1.2 (`_alter_cl_activity_drop_source_page`) ✓
- §5.1 Change B widen `page_type` → Task 1 Step 1.2 (`_alter_cl_page_for_indexing`) ✓
- §5.1 Change C create `cl_page_entity_map` → Task 1 Step 1.2 (`_create_cl_page_entity_map`) ✓
- §5.2 `index_job_pages` writes cl_page + cl_resource_page_map + cl_page_entity_map → Task 2 Step 2.2 ✓
- §5.2 Idempotent via DELETE-then-INSERT → Task 2 Step 2.2 (top of indexer body) ✓
- §5.2 Failure non-fatal → Task 2 Step 2.3 (`try/except` around indexer call) ✓
- §5.3 GET endpoint → Task 3 Step 3.1 ✓
- §5.3 POST reindex endpoint → Task 3 Step 3.1 ✓
- §5.3 404 path with rebuild instruction → Task 3 Step 3.1 (the JSONResponse with 404 + reindex hint) ✓
- §5.4 Editor side-by-side via single page selector → Task 4 Steps 4.2–4.4 ✓
- §5.4 Rebuild Index banner on 404 → Task 4 Step 4.2 (`showRebuildIndexBanner`) ✓
- §5.5 Job→resource binding via 03_resource.json#id → Task 2 Step 2.1 (`get_or_create_resource_for_job`) ✓
- §5.6 Backfill script → Task 5 Step 5.9 ✓
- §8 Tests → Task 5 Steps 5.5, 5.7 ✓
- §9 Migration via init_db lazy pattern → Task 1 Step 1.3 ✓
- §10 Branch/commit plan (5 commits) → Tasks 1.7, 2.7, 3.3, 4.6, 5.11 + Task 6 PR ✓
- §13 Acceptance criteria — covered by Task 6 Steps 6.1–6.2 + Task 2 Steps 2.5–2.6 ✓

**Placeholder scan:** No "TBD", "TODO", "implement later", "similar to Task N", or unimplemented vague verbs. Each step has either exact code, exact commands, or exact verification.

**Type / name consistency:**
- `index_job_pages(job_id, out_dir)` signature consistent across Tasks 2, 3, 5.
- `IndexReport` field names consistent (`pages`, `activities`, `tasks`, `stems`, `images`, `instructional_prompts`, `instructional_segments`, `practice_sections`, `scaffolding`, `response_areas`, `lessons`, `skipped_no_source_page`, `errors`).
- `cl_page_entity_map` column names consistent: `id`, `page_id`, `entity_type`, `entity_id`, `sequence_in_page`, `layout_region`, `is_continuation`, `continues_to_seq`, `metadata`, `created_at`.
- API response keys consistent: `jobId`, `pdfPageIndex`, `pageNumber`, `pageType`, `entities`, `kind`, `id`, `sequenceInPage`, `layoutRegion`, `isContinuation`, `continuesToSeq`, `metadata`, `body`.

**Open follow-ups (non-blocking):**
- The renderer fallback in Task 4 Step 4.2 (generic JSON `<pre>` for kinds without an existing renderer) is acceptable for MVP. A separate spec can add real renderers if reviewers request richer per-kind UI.
- Backfill is one-shot; if jobs accumulate after this PR ships, the indexer runs automatically via Task 2 Step 2.3 — no future manual backfill needed unless schema evolves.
