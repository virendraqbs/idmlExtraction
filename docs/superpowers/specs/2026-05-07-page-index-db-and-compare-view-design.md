# Page-Index DB & Side-By-Side HTML↔PDF Compare View — Design

**Date:** 2026-05-07
**Owner:** Pipeline + editor team
**Status:** Awaiting approval (brainstorming → planning)
**Repository:** `carnegielearning-clearmathnational`
**Base branch:** `development`
**Feature branch (proposed):** `feat/page-index-db`
**Depends on:** `feat/canonical-schema-conformance` (PR #1, schema enums + Reference.type)

---

## 1. Problem

Reviewers need to verify that the extracted JSON faithfully represents the source PDF, page by page. Today the editor's per-page filter relies on a `sourcePage` field stamped onto each activity / image / instructional-prompt during assembly. That approach has four problems that block reliable page-wise comparison:

1. `sourcePage` is a pipeline-internal helper, **not** part of the canonical CL-Json-Schema. Future canonical-strict export will need to drop it.
2. TIG-side activities and prompts currently lack `sourcePage` entirely (separate gap, see PENDING_TASKS).
3. JSON arrays carry render order *implicitly* (array index). There is no explicit "this is the third block on the page, in the right sidebar". Multi-block pages render in the wrong order.
4. There is no representation for entities that **continue** across pages (an EXPLORE activity that starts on page 467 and continues onto 468). The current model loses the continuation link after assembly.

The client requirement is unambiguous: **JSON output must remain byte-identical to the canonical-schema deliverable**. Any extra page-binding metadata must live elsewhere.

## 2. Goals

- Reviewers open a job in the editor and see a **side-by-side, page-locked** view: left pane HTML render of all entities on PDF page N; right pane PDF iframe scrolled to page N. A single page selector drives both panes.
- Page binding for every entity that can appear on a page is captured in **MySQL** (the existing `cl_json_schema` DB), independent of JSON files.
- 19 SRB JSON files and 5 TIG JSON files remain byte-identical to current pipeline output. No new fields added, none removed.
- A new HTTP endpoint serves a composed per-page payload to the editor.
- A backfill script can index any existing `outputs/<job>/` folder retroactively without re-running extraction.

## 3. Non-Goals

- Stacked / scrolling full-document compare view (deferred).
- OCR-based diff between PDF visible text and extracted JSON (deferred — separate spec).
- Click-to-highlight bounding-box overlay on the PDF iframe (deferred — model accommodates it via `metadata` column, but UI scope is later).
- Image rendering bug (`imagePath` vs `filepath`) — separate spec.
- Replacing the existing single-page editor; this is an additive view inside the same Results page.
- Cross-job page queries ("find all lessons that include printed page 465") — out of scope but the schema supports it later.

## 4. Architecture

Two new MySQL tables. One new pipeline step. One new HTTP endpoint. One existing editor pane refactored to consume the endpoint. One backfill script.

```
PDF
 └─► pipeline_service.run_job
      ├─► assemble_schemas         (writes 19 JSON files — UNCHANGED)
      └─► index_job_pages          (NEW — writes cl_job_page + cl_job_page_entity rows)

Editor (browser)
 └─► page selector change
      └─► GET /api/results/{job_id}/page/{n}     (NEW)
            ├─► SELECT FROM cl_job_page_entity   (DB)
            ├─► hydrate entity bodies from JSON  (existing files)
            └─► return composed payload
```

### 4.1 DB schema

Two tables in the existing `cl_json_schema` database.

#### `cl_job_page` — one row per (job, PDF page)

```
cl_job_page
  id               CHAR(36)     PK     -- UUID
  job_id           VARCHAR(64)  NOT NULL    -- outputs/<job>/ folder name
  page_uuid        CHAR(36)     NOT NULL    -- the id from 13_pages.json[i].id
  pdf_page_index   INT          NOT NULL    -- 1-based PDF position
  page_number      INT          NULL        -- printed book page number (e.g. 465)
  page_type        VARCHAR(64)  NULL        -- canonical PageType enum value
  content_blocks   JSON         NULL        -- raw 13_pages.json contentBlocks for replay
  metadata         JSON         NULL        -- pageNumberRepresentations, lessonContext, etc.
  created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
  updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

  UNIQUE KEY uniq_job_page (job_id, pdf_page_index)
  INDEX idx_job (job_id)
```

#### `cl_job_page_entity` — many rows per page; one row per entity rendered on that page

```
cl_job_page_entity
  id                CHAR(36)     PK
  job_id            VARCHAR(64)  NOT NULL
  pdf_page_index    INT          NOT NULL
  page_number       INT          NULL          -- denormalized for fast filter
  entity_kind       VARCHAR(32)  NOT NULL      -- ACTIVITY|TASK|STEM|IMAGE|INSTRUCTIONAL_PROMPT|
                                                -- INSTRUCTIONAL_SEGMENT|STANDARDS_BLOCK|
                                                -- PRACTICE_SECTION|SCAFFOLDING|RESPONSE_AREA|LESSON
  entity_id         CHAR(36)     NOT NULL      -- the id from the corresponding JSON file
  sequence_in_page  INT          NOT NULL DEFAULT 0   -- render order within the page
  is_continuation   TINYINT(1)   NOT NULL DEFAULT 0   -- 1 if this entity began on a prior page
  continues_to      INT          NULL                  -- next pdf_page_index if entity spans pages
  layout_region     VARCHAR(32)  NULL                  -- TOP_LEFT|MIDDLE|SIDEBAR|FOOTER|...
  metadata          JSON         NULL                  -- bbox, side-panel role, future use
  created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP

  UNIQUE KEY uniq_entity_per_job (job_id, entity_kind, entity_id, pdf_page_index)
  INDEX idx_page (job_id, pdf_page_index, sequence_in_page)
  INDEX idx_entity (entity_id)
  INDEX idx_kind (job_id, entity_kind)
```

**Notes on schema choices:**
- `job_id` is the existing `outputs/<job>/` folder name (a UUID for jobs from the web UI; or a custom string for batch CLI runs). Treated as opaque string; no FK to a non-existent `cl_job` table.
- `entity_id` is **not** an FK — JSON entities don't live in MySQL today, only the resource/module/topic/lesson hierarchy does. We deliberately keep this loose so the table indexes JSON regardless of how the canonical hierarchy evolves.
- `(job_id, entity_kind, entity_id, pdf_page_index)` is the uniqueness key, not just `(entity_id, pdf_page_index)`, because UUID collisions across jobs are theoretically possible and the index is per-job anyway.
- `continues_to` lets multi-page activities link forward without duplicating bodies. The same `entity_id` may have two rows: one with `is_continuation=0, continues_to=N+1` on page N, another with `is_continuation=1, continues_to=NULL` on page N+1.

### 4.2 Pipeline integration — `index_job_pages`

New function in `services/page_indexer.py`:

```
index_job_pages(job_id: str, out_dir: Path) -> IndexReport
```

Reads:
- `13_pages.json` — drives row insertion into `cl_job_page`.
- `07_activities.json` — `sourcePage` → `cl_job_page_entity` rows with kind=ACTIVITY.
- `08_tasks.json` — tasks inherit page binding from their parent activity; one row per task with kind=TASK.
- `09_stems.json` — same, kind=STEM.
- `12_images.json` — `sourcePage` → kind=IMAGE rows. Position metadata captured in `layout_region`.
- `14_instructional_prompts.json` — `sourcePage` → kind=INSTRUCTIONAL_PROMPT.
- `15_instructional_segments.json` — kind=INSTRUCTIONAL_SEGMENT (multi-page; one row per page in `pages[]`).
- `16_practice_sections.json` — kind=PRACTICE_SECTION (typically last page; resolved via activities).
- `17_response_areas.json` — kind=RESPONSE_AREA (linked via stem.responseAreaId).
- `18_scaffolding.json` — kind=SCAFFOLDING (linked via activity.scaffolding[]).
- `06_lesson.json` — single LESSON row on the first page.

Behaviour:
- Wrapped in a single MySQL transaction.
- Idempotent via `DELETE FROM cl_job_page WHERE job_id=?; DELETE FROM cl_job_page_entity WHERE job_id=?` followed by inserts. (Upsert is also fine but delete-then-insert avoids stale-row hazards.)
- On any error, rollback and report; **do not fail the extraction job**. JSON is canonical; the index can be rebuilt later from JSON.
- Returns an `IndexReport` with counts: pages, activities, tasks, stems, images, prompts, segments, practice_sections, response_areas, scaffolding, lessons.

Called from `pipeline_service.run_job` immediately after `assemble_schemas` returns. Called from the editor's save handler after a JSON edit (re-index that one job).

### 4.3 HTTP endpoint

```
GET /api/results/{job_id}/page/{n}
```

Where `n` is the 1-based PDF page index.

Response body:

```json
{
  "jobId": "ba323964-d005-4ed5-a16d-437eb81fce9c",
  "pdfPageIndex": 3,
  "pageNumber": 467,
  "pageType": "SRB_LESSON_EXPLORE",
  "pageMeta": { "pageNumberRepresentations": {...}, "lessonContext": {...} },
  "contentBlocks": [ ...raw from 13_pages.json... ],
  "entities": [
    {
      "kind": "ACTIVITY",
      "id": "0846cce3-...",
      "sequenceInPage": 1,
      "isContinuation": false,
      "continuesTo": null,
      "layoutRegion": null,
      "metadata": {},
      "body": { ...full activity object from 07_activities.json... }
    },
    {
      "kind": "IMAGE",
      "id": "c65299f6-...",
      "sequenceInPage": 2,
      "layoutRegion": "TOP_RIGHT",
      "body": { ...image object from 12_images.json... }
    }
    /* ... more entities ordered by sequenceInPage ... */
  ]
}
```

Server-side logic:
1. Query `cl_job_page` for `(job_id, pdf_page_index=n)` — page-level metadata.
2. Query `cl_job_page_entity` for `(job_id, pdf_page_index=n)` ordered by `sequence_in_page` — list of (kind, id) tuples.
3. Hydrate entity bodies by reading the per-kind JSON file (`07_activities.json`, etc.) once and extracting matching ids. Cache the parsed JSON in-process for the request lifetime.
4. Compose response.

If no rows exist for `(job_id, n)` (e.g. index has not been built), return HTTP 404 with `{"error": "page index not built — run backfill"}` rather than crashing or falling back to legacy filter logic. Cleaner error surface.

### 4.4 Editor UI changes

Existing `templates/results.html` already has a two-pane layout with a left content area and right PDF iframe. Changes:

- Page selector `change` handler: replace the current "filter all entities by `samePageNum`" client-side logic with a single `fetch('/api/results/' + jobId + '/page/' + n)` call.
- Render the returned `entities` array in `sequence_in_page` order. Each entity uses its existing renderer (renderActivityHtml, renderImageCard, etc.) — these functions already exist.
- PDF iframe `src` updates to `/outputs/{job_id}/pdf#page=` + `pdfPageIndex` — same as today.
- TIG editor (`templates/results.html` covers both via mode flag) gets the same behaviour for free, since the new index covers TIG entities too.
- **Fallback:** if the API returns 404, show a banner "Page index not built — click Rebuild Index" with a button that calls `POST /api/results/{job_id}/reindex`.

### 4.5 Backfill / re-index endpoint and script

- `POST /api/results/{job_id}/reindex` — runs `index_job_pages(job_id, outputs/<job_id>/)` synchronously; returns the `IndexReport`. Used by the editor banner above.
- `scripts/backfill_page_index.py` — walks `outputs/`, calls `index_job_pages` for every folder containing `13_pages.json`. Used once after first deploy and any time canonical schema changes invalidate prior indexing.

## 5. Data Flow Summary

```
Extraction:
  PDF → Gemini → 19 JSON files (UNCHANGED) → index_job_pages → MySQL rows

Read (editor):
  page selector → GET /api/results/{id}/page/{n}
                  → MySQL: SELECT cl_job_page + cl_job_page_entity
                  → hydrate from JSON files
                  → return composed payload

Edit (editor):
  user edits field → existing /api/results/.../save endpoint
                   → JSON file updated (UNCHANGED)
                   → index_job_pages(job_id, out_dir) re-runs (NEW)
                   → MySQL refreshed

Backfill:
  scripts/backfill_page_index.py → for each outputs/<job>/ → index_job_pages
```

## 6. Error Handling

| Failure | Behaviour |
|---------|-----------|
| `index_job_pages` raises during extraction | Log warning, leave JSON intact, surface in extraction_report. Job still completes. |
| Editor opens an un-indexed job | API returns 404 with rebuild instructions; UI shows banner with rebuild button. |
| MySQL down | API returns 500; editor shows generic error; reviewer can retry. |
| JSON file corrupt during hydration | Log + skip that entity; return partial payload with `warnings` array. |
| Edit triggers re-index that fails | Save still succeeds (JSON is truth); banner notifies reviewer to rebuild. |

No silent failures.

## 7. Testing

- **Unit (`tests/test_page_indexer.py`):**
  - `index_job_pages` against a fixture directory (committed sample with miniature 19 JSON files) → expected row counts per kind.
  - Idempotency: running twice produces identical row set.
  - Edge case: entity with `sourcePage = null` produces no row (and no exception).

- **Unit (`tests/test_page_api.py`):**
  - `/api/results/{id}/page/{n}` returns shape matching the response schema above for a known fixture.
  - 404 for missing index.

- **Integration:**
  - Re-extract `sourceFile/A1_T13_L1.pdf` end-to-end (manual; documented in plan).
  - For PDF page 3, assert API returns the same activity ids that `outputs/<job>/07_activities.json` lists with `sourcePage == 467`.

- **Backfill:**
  - Run `scripts/backfill_page_index.py` against `outputs/`. Spot-check three jobs.

The repo currently has no test framework. This spec adds `pytest` to `requirements-dev.txt` (new file) and creates `tests/` directory with a minimal `conftest.py`. Production runtime stays pytest-free.

## 8. Migration / Backwards Compatibility

- New tables added via `init_db()` — same lazy-create pattern already used for the `pdf_path` columns. No Alembic introduction in this PR.
- No existing JSON consumers affected (JSON unchanged).
- Editor users with pre-indexed jobs: prompted to click Rebuild Index once.

## 9. Branch + Commit Plan

- Branch from `development` (after `feat/canonical-schema-conformance` merges; otherwise from that branch with rebase planned): `feat/page-index-db`
- Commits (5):
  1. `schema(db): add cl_job_page + cl_job_page_entity tables and init_db hooks`
  2. `feat(pipeline): index_job_pages step writes per-page entity index`
  3. `feat(api): GET /api/results/{id}/page/{n} + POST .../reindex`
  4. `feat(editor): side-by-side page-locked view consuming page API`
  5. `scripts: backfill_page_index.py + test fixtures + minimal pytest setup`
- PR target: `development`

## 10. Risks

| Risk | Mitigation |
|------|------------|
| JSON edited outside editor → DB drifts stale | Backfill script + Rebuild Index button; document in operator runbook. |
| Per-page API adds DB round-trip vs current pure-JSON read | Acceptable: pages are bounded (≤30 per lesson). Hydration cache memo keeps JSON re-parse to once per request. |
| TIG entities lack `sourcePage` today; index will be partial | Documented limitation. Separate spec covers TIG sourcePage backfill (see PENDING_TASKS). Index gracefully skips entities without sourcePage. |
| New tables grow unbounded (one row per entity per page across all jobs) | At 1000 jobs × 200 entities/job = 200k rows. Trivial for MySQL. Indices on (job_id, pdf_page_index) keep per-page reads O(log N). |
| Editor save handler must re-index — adds latency to save | Mitigation: re-index runs synchronously but only touches one job's rows; expect <100ms on typical lesson. If slow, queue async. |

## 11. Open Questions

None blocking. Items deferred:
- Bounding-box capture for click-to-highlight (later spec).
- OCR-based discrepancy flagging (later spec).
- Cross-job page queries (model already supports; UI deferred).

## 12. Acceptance Criteria

- [ ] Two new MySQL tables created automatically on app start (no manual SQL).
- [ ] After an SRB extraction, `cl_job_page_entity` contains rows for every activity / image / prompt that has `sourcePage` in JSON.
- [ ] `GET /api/results/{job_id}/page/{n}` returns a payload matching the spec response shape.
- [ ] Editor page selector switches both HTML pane and PDF iframe to selected page in one user action.
- [ ] HTML pane shows entities in `sequence_in_page` order (not raw JSON array order).
- [ ] Re-running extraction on the same job replaces (does not duplicate) index rows.
- [ ] `scripts/backfill_page_index.py outputs/` indexes existing jobs without re-extracting.
- [ ] 19 SRB JSON files and 5 TIG JSON files byte-identical to pre-change pipeline output (verified via diff).
- [ ] `verify_canonical_conformance.py` (from prior PR) still exits 0 on a fresh job.

## 13. References

- Prior PR: https://github.com/virendraqbs/idmlExtraction/pull/1 (canonical schema conformance — schema enums + Reference.type).
- Canonical schema: `CL-Json-Schema/schemas/`
- Existing pipeline: `services/pipeline_service.py`, `services/assembler.py`, `utils/schema_chunks.py`
- Editor: `templates/results.html`, `controllers/job_controller.py`
- DB layer: `database/__init__.py`
