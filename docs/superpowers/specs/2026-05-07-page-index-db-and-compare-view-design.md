# Page-Index DB & Side-By-Side HTML↔PDF Compare View — Design

**Date:** 2026-05-07
**Owner:** Pipeline + editor team
**Status:** Revised after DB inspection (brainstorming → planning)
**Repository:** `carnegielearning-clearmathnational`
**Base branch:** `development`
**Feature branch (proposed):** `feat/page-index-db`
**Depends on:** `feat/canonical-schema-conformance` (PR #1, schema enums + Reference.type)

---

## 1. Problem

Reviewers need to verify the extracted JSON faithfully represents the source PDF, page by page. Today the editor's per-page filter relies on a `sourcePage` field stamped onto each activity / image / instructional-prompt during assembly. That approach has problems that block reliable page-wise comparison:

1. `sourcePage` is a pipeline-internal helper, not part of canonical CL-Json-Schema. Strict canonical export removes it.
2. TIG-side activities and prompts lack `sourcePage` entirely.
3. Render order within a page is implicit (array index), so multi-block pages render in the wrong order.
4. No representation for entities that span pages (an EXPLORE activity that starts on page 467 and continues onto 468 loses its continuation link after assembly).
5. Architectural concern raised by the project owner: an activity (or any small entity like a stem, image, prompt) should be **reusable on any page or in any other place**. Embedding page binding into the master entity row makes the entity non-portable. Master rows must stay page-agnostic; all linkage lives in dedicated relation tables.

The deliverable to the client is JSON only. The DB is internal to this project (under development) and may be modified freely.

## 2. Goals

- Reviewers open a job in the editor and see a **side-by-side, page-locked** view: left pane HTML render of all entities on PDF page N; right pane PDF iframe scrolled to page N. A single page selector drives both panes.
- Page binding for every entity that can appear on a page is captured in MySQL (the existing `cl_json_schema` DB), independent of JSON files.
- Master entity tables (`cl_activity`, `cl_image`, `cl_stem`, `cl_task`, `cl_instructional_prompt`, `cl_scaffolding`, `cl_practice_section`, `cl_response_area`, `cl_instructional_segment`, `cl_standards_block`) carry **only intrinsic content**, no page references, no parent IDs.
- All parent↔child and page↔entity links live in dedicated relation tables.
- 19 SRB JSON files and 5 TIG JSON files remain byte-identical to current pipeline output.
- New HTTP endpoint serves a composed per-page payload to the editor.
- Backfill script can index any existing `outputs/<job>/` folder retroactively without re-running extraction.

## 3. Non-Goals

- Stacked / scrolling full-document compare view (deferred).
- OCR-based diff between PDF visible text and extracted JSON (deferred — separate spec).
- Click-to-highlight bounding-box overlay on the PDF iframe (deferred — `metadata` JSON column accommodates bbox for future).
- Image rendering bug (`imagePath` vs `filepath`) — separate spec.
- Replacing the existing single-page editor; this is an additive view inside the same Results page.
- Cross-job page queries.
- Full DB sync (writing every JSON entity to its canonical master table on every job). Current scope writes only `cl_resource`, `cl_module`, `cl_topic`, `cl_lesson`, `cl_page` and the new `cl_page_entity_map`. Master tables for activities/tasks/stems/etc. stay schema-only for now; the editor hydrates entity bodies from JSON files.

## 4. Existing DB context (audited)

The `cl_json_schema` DB already has 36 tables. Master entity tables follow a relation-based design — every master row is page- and parent-agnostic, with linkage in dedicated map tables. Polymorphic many-to-many already used in `cl_image_usage(image_id, entity_type, entity_id, sequence_number)`.

**Single existing violation:** `cl_activity` has a `source_page TINYINT UNSIGNED` column that embeds page binding into the master row. This conflicts with the reuse goal and must be removed.

**No existing page→entity map.** Existing maps cover lesson↔activity, activity↔task, task↔stem, etc., but no map binds a page to its entities. `cl_image_usage` covers image-on-anything, not page-on-anything.

**`cl_page` is too narrow.** Its `page_type` enum has 8 values; canonical CL-Json-Schema declares 32. Needs widening.

**`cl_resource_page_map.sequence_number`** is the natural carrier for `pdf_page_index` (1-based page ordinal within a resource). No new column needed for that.

## 5. Architecture

Three DB changes (all additive or strictly local cleanup). One new pipeline step. One new HTTP endpoint. Existing editor pane refactored to consume the endpoint. One backfill script.

```
PDF
 └─► pipeline_service.run_job
      ├─► assemble_schemas         (writes 19 JSON files — UNCHANGED)
      └─► index_job_pages          (NEW — populates cl_page,
                                    cl_resource_page_map, cl_page_entity_map)

Editor (browser)
 └─► page selector change
      └─► GET /api/results/{job_id}/page/{n}    (NEW)
            ├─► JOIN cl_resource_page_map + cl_page + cl_page_entity_map
            ├─► hydrate entity bodies from JSON
            └─► return composed payload
```

### 5.1 DB changes

#### Change A — drop `cl_activity.source_page`

```sql
ALTER TABLE cl_activity DROP COLUMN source_page;
```

Activity rows become fully page-agnostic and reusable. Pipeline currently never reads the column on the read path; only writes from raw extraction. After change, page binding flows through `cl_page_entity_map` only.

#### Change B — widen `cl_page.page_type` to canonical 32-value enum

```sql
ALTER TABLE cl_page MODIFY page_type VARCHAR(64) NULL;
```

Aligns with `CL-Json-Schema/schemas/common/enums.json#PageType`. We use `VARCHAR(64)` rather than re-declaring a MySQL enum so future canonical extensions don't require another migration. Application-level validation against canonical enum (already provided by `scripts/verify_canonical_conformance.py` from the prior PR).

(Optional, can be deferred:) `ALTER TABLE cl_page ADD COLUMN page_uuid CHAR(36) NULL` to round-trip the JSON-side page id. Not required for MVP.

#### Change C — new polymorphic page→entity map

```sql
CREATE TABLE cl_page_entity_map (
  id               CHAR(36) NOT NULL PRIMARY KEY,
  page_id          CHAR(36) NOT NULL,
  entity_type      VARCHAR(64) NOT NULL,
  -- canonical values: ACTIVITY | TASK | STEM | IMAGE
  --                 | INSTRUCTIONAL_PROMPT | INSTRUCTIONAL_SEGMENT
  --                 | PRACTICE_SECTION | SCAFFOLDING | STANDARDS_BLOCK
  --                 | RESPONSE_AREA | LESSON
  entity_id        CHAR(36) NOT NULL,
  sequence_in_page SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  layout_region    VARCHAR(32) NULL,
  is_continuation  TINYINT(1) NOT NULL DEFAULT 0,
  continues_to_seq SMALLINT UNSIGNED NULL,
  metadata         JSON NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_page_entity (page_id, entity_type, entity_id),
  KEY idx_entity (entity_type, entity_id),
  KEY idx_page_seq (page_id, sequence_in_page),
  CONSTRAINT fk_pem_page FOREIGN KEY (page_id) REFERENCES cl_page(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Polymorphic page→entity binding — order, layout, continuation';
```

Notes:
- Polymorphic table chosen for parity with existing `cl_image_usage` design pattern.
- `entity_id` is **not** an FK — entities live in many different master tables, each with its own UUID space. A polymorphic FK is enforced at the application layer.
- `(page_id, entity_type, entity_id)` uniqueness prevents duplicates if a job is re-indexed.
- `continues_to_seq` is the `cl_resource_page_map.sequence_number` of the next page, not the printed page_number; uses ordinal so book-page ranges stay clean.

#### Why no new `cl_job_page_*` tables

Earlier draft proposed `cl_job_page` + `cl_job_page_entity` per-job tables. Rejected after DB audit: it duplicated `cl_page` and `cl_resource_page_map` and contradicted the project's already-established normalised pattern.

### 5.2 Pipeline integration — `index_job_pages`

New module `services/page_indexer.py` exposing one function:

```
index_job_pages(out_dir: Path, db_resource_id: str | None) -> IndexReport
```

Reads:
- `13_pages.json` → upserts into `cl_page` and `cl_resource_page_map`.
- `07_activities.json` → for each activity with `sourcePage = N`, inserts `cl_page_entity_map(page_id, ACTIVITY, activity_id, ...)`.
- `08_tasks.json` + `cl_activity_task_map` to derive task→page through parent activity → insert TASK rows.
- `09_stems.json` + `cl_task_stem_map` similarly → STEM rows.
- `12_images.json` → IMAGE rows. `position` field of image becomes `layout_region`.
- `14_instructional_prompts.json` → INSTRUCTIONAL_PROMPT rows.
- `15_instructional_segments.json` → INSTRUCTIONAL_SEGMENT rows; multi-page segments produce one row per page in `pages[]`.
- `16_practice_sections.json` → PRACTICE_SECTION rows. Page derived from contained activities (last page typically).
- `17_response_areas.json` → RESPONSE_AREA rows linked via stems.
- `18_scaffolding.json` → SCAFFOLDING rows linked via activity.scaffolding[].
- `06_lesson.json` → single LESSON row on the first page.

Note: until full DB sync is implemented, `cl_activity` / `cl_task` / `cl_stem` / `cl_image` etc. are **not** populated. Their rows do not exist. `cl_page_entity_map.entity_id` references the JSON id directly. Editor read API reads body from JSON file, not from the master tables. This is documented as a transitional state; future PR will close the gap when the team is ready to dual-write.

Behaviour:
- Wrapped in a single MySQL transaction.
- Idempotent: `DELETE FROM cl_page_entity_map WHERE page_id IN (SELECT id FROM cl_page WHERE id IN (?, ?, …))` followed by inserts. Pages and resource_page_map use UPSERT (`INSERT … ON DUPLICATE KEY UPDATE`).
- On error, rollback and surface in extraction_report; **do not fail the extraction job** — JSON is canonical.
- Returns `IndexReport` with counts per entity_type.

Called from `pipeline_service.run_job` after `assemble_schemas` returns. Called from the editor's save handler after a JSON edit (re-index that one job).

### 5.3 HTTP endpoint

```
GET /api/results/{job_id}/page/{n}
```

Where `n` is the 1-based PDF page ordinal (i.e. `cl_resource_page_map.sequence_number`).

Response:

```json
{
  "jobId": "ba323964-d005-4ed5-a16d-437eb81fce9c",
  "pdfPageIndex": 3,
  "pageNumber": 467,
  "pageType": "SRB_LESSON_EXPLORE",
  "pageMeta": { "...metadata..." },
  "contentBlocks": [ "...raw from 13_pages.json..." ],
  "entities": [
    {
      "kind": "ACTIVITY",
      "id": "0846cce3-...",
      "sequenceInPage": 1,
      "layoutRegion": null,
      "isContinuation": false,
      "continuesToSeq": null,
      "metadata": {},
      "body": { "...full activity object from 07_activities.json..." }
    },
    {
      "kind": "IMAGE",
      "id": "c65299f6-...",
      "sequenceInPage": 2,
      "layoutRegion": "TOP_RIGHT",
      "body": { "...image object from 12_images.json..." }
    }
  ]
}
```

Server-side logic:

1. Resolve `(job_id, n)` to `page_id` via `outputs/<job_id>/03_resource.json` → `cl_resource.id` → `cl_resource_page_map WHERE sequence_number=n`. (Job_id-to-resource lookup uses `cl_resource.title` or persisted job→resource mapping; see §5.5.)
2. `SELECT * FROM cl_page WHERE id = page_id` for page-level metadata.
3. `SELECT * FROM cl_page_entity_map WHERE page_id = ? ORDER BY sequence_in_page` for the entity list.
4. Hydrate entity bodies by reading the per-kind JSON file (`07_activities.json`, etc.) once per request and extracting matching ids. In-process LRU keeps repeated lookups cheap.
5. Compose response.

If no rows exist for `(page_id)` (e.g. index has not been built), return HTTP 404 with `{"error": "page index not built — run /api/results/{job_id}/reindex"}`.

`POST /api/results/{job_id}/reindex` — runs `index_job_pages` synchronously; returns `IndexReport`. Used by the editor banner.

### 5.4 Editor UI changes

Existing `templates/results.html` already has a two-pane layout. Changes:

- Page selector `change` handler: replace client-side `samePageNum` filter with a single `fetch('/api/results/' + jobId + '/page/' + n)`.
- Render returned `entities` array in `sequenceInPage` order. Each entity uses its existing renderer (`renderActivityHtml`, `renderImageCard`, etc.).
- PDF iframe `src` updates to `/outputs/{job_id}/pdf#page=` + `pdfPageIndex` — same as today.
- TIG editor (same template, mode flag) gets the new behaviour for free, since the index covers TIG entities.
- Fallback: if API returns 404, show banner `Page index not built — click Rebuild Index` with a button that calls `POST /api/results/{job_id}/reindex`.

### 5.5 Job → resource binding

`cl_resource_page_map` requires a `resource_id`. Today the pipeline calls `database.create_module(...)` and creates `cl_resource_module_map` rows but the resource id assigned to a given job is not always persisted in MySQL (existing controllers do create `cl_resource` rows when the user picks one). For the index step we need:

```
POST /api/results/{job_id}/reindex
  body: { resource_id: "<uuid>" }
```

If not provided, the pipeline upserts a synthetic resource row keyed by `outputs/<job_id>/03_resource.json#id`. The editor's reindex banner sends the user-selected resource id when available.

This is a small extension to existing DB-write paths; not invasive.

### 5.6 Backfill script

`scripts/backfill_page_index.py` — walks `outputs/`, calls `index_job_pages` for every folder containing `13_pages.json`. Used once after first deploy and any time canonical schema changes invalidate prior indexing.

## 6. Data flow summary

```
Extraction:
  PDF → Gemini → 19 JSON files (UNCHANGED) → index_job_pages → MySQL rows in
                                              cl_page,
                                              cl_resource_page_map,
                                              cl_page_entity_map

Read (editor):
  page selector → GET /api/results/{id}/page/{n}
                  → MySQL JOIN
                  → hydrate from JSON files
                  → return composed payload

Edit (editor):
  user edits field → existing /api/results/.../save endpoint
                   → JSON file updated (UNCHANGED)
                   → index_job_pages re-runs (NEW)
                   → MySQL refreshed

Backfill:
  scripts/backfill_page_index.py → for each outputs/<job>/ → index_job_pages
```

## 7. Error handling

| Failure | Behaviour |
|---------|-----------|
| `index_job_pages` raises during extraction | Log warning; leave JSON intact; surface in extraction_report. Job still completes. |
| Editor opens an un-indexed job | API returns 404 with rebuild instructions; UI shows banner with rebuild button. |
| MySQL down | API returns 500; editor shows generic error; reviewer can retry. |
| JSON file corrupt during hydration | Log + skip that entity; return partial payload with `warnings` array. |
| Edit triggers re-index that fails | Save still succeeds (JSON is truth); banner notifies reviewer to rebuild. |
| Resource id ambiguity (multiple `cl_resource` rows match a job) | Pipeline picks the most recent by `updated_at`; logs choice. |

No silent failures.

## 8. Testing

- **Unit (`tests/test_page_indexer.py`):**
  - `index_job_pages` against a fixture directory (committed sample with miniature 19 JSON files) → expected row counts per entity_type.
  - Idempotency: running twice produces identical row set.
  - Edge: entity with `sourcePage = null` produces no row (and no exception).

- **Unit (`tests/test_page_api.py`):**
  - `/api/results/{id}/page/{n}` returns the documented response shape for a known fixture.
  - 404 for missing index.

- **Integration (manual, documented in plan):**
  - Re-extract `sourceFile/A1_T13_L1.pdf`.
  - Assert `cl_page_entity_map` row count matches sum of `sourcePage`-tagged entities in the JSON.
  - Assert `GET /api/results/{job}/page/3` returns the activity ids that JSON's `07_activities.json` lists with the matching `sourcePage`.

- **Backfill:**
  - Run `scripts/backfill_page_index.py` against `outputs/`. Spot-check three jobs.

The repo currently has no test framework. This spec adds `pytest` to a new `requirements-dev.txt` and creates `tests/` with a minimal `conftest.py`. Production runtime stays pytest-free.

## 9. Migration / Backwards Compatibility

- The DB is internal to this project (under development); not shared with the client. Schema may change freely.
- Three DB changes (`ALTER cl_activity DROP source_page`, `ALTER cl_page MODIFY page_type`, `CREATE TABLE cl_page_entity_map`) execute via `database.init_db()` lazy-migration pattern already used for `pdf_path` columns.
- No existing JSON consumers affected (JSON byte-identical guarantee).
- Editor users with pre-indexed jobs: prompted to click Rebuild Index once.
- Existing `cl_page` rows (if any populated during prior development) survive the `MODIFY page_type` change — VARCHAR(64) is a wider type than the 8-value enum.

## 10. Branch + Commit Plan

Base: `development` (after `feat/canonical-schema-conformance` merges; otherwise rebase atop that branch).

Branch: `feat/page-index-db`

Commits (5):

1. `schema(db): cl_page_entity_map + drop cl_activity.source_page + widen cl_page.page_type`
2. `feat(pipeline): index_job_pages step writes per-page entity index`
3. `feat(api): GET /api/results/{id}/page/{n} + POST .../reindex`
4. `feat(editor): side-by-side page-locked view consuming page API`
5. `scripts: backfill_page_index.py + test fixtures + minimal pytest setup`

PR target: `development`.

## 11. Risks

| Risk | Mitigation |
|------|------------|
| JSON edited outside editor → DB drifts stale | Backfill script + Rebuild Index button; documented. |
| Per-page API adds DB round-trip vs current pure-JSON read | Acceptable: pages bounded (≤30 per lesson). Per-request JSON parse cache memoises hydration. |
| TIG entities lack `sourcePage` today; index will be partial for TIG until a separate TIG-side fix lands | Documented limitation. Index gracefully skips entities without sourcePage. |
| Master entity tables remain unpopulated in this PR | API hydrates from JSON; documented transitional state; full DB sync deferred to a separate spec. |
| `cl_activity.source_page` drop conflicts with code reading the column | Audit confirms no production code reads the column today; only writes from raw extraction. Removal is safe. |

## 12. Open Questions

None blocking. Items deferred:
- Bounding-box capture for click-to-highlight (later spec).
- OCR-based discrepancy flagging (later spec).
- Cross-job page queries (model already supports).
- Full DB sync — write all JSON entities to their canonical master tables on every extraction.

## 13. Acceptance Criteria

- [ ] Three DB changes applied via `init_db()` on app start (no manual SQL).
- [ ] After an SRB extraction, `cl_page_entity_map` contains rows for every activity / image / prompt / segment / practice_section / scaffolding / response_area that has `sourcePage` (directly or via parent) in JSON.
- [ ] `GET /api/results/{job_id}/page/{n}` returns a payload matching the documented response shape.
- [ ] Editor page selector switches both HTML pane and PDF iframe to the selected page in a single user action.
- [ ] HTML pane shows entities in `sequence_in_page` order.
- [ ] Re-running extraction on the same job replaces (does not duplicate) index rows.
- [ ] `scripts/backfill_page_index.py outputs/` indexes existing jobs without re-extracting.
- [ ] 19 SRB JSON files and 5 TIG JSON files byte-identical to pre-change pipeline output.
- [ ] `verify_canonical_conformance.py` (from prior PR) still exits 0 on a fresh job.
- [ ] No `cl_activity.source_page` column remains in the schema.
- [ ] All master entity tables (`cl_activity`, `cl_image`, `cl_stem`, `cl_task`, `cl_instructional_prompt`, `cl_scaffolding`, `cl_practice_section`, `cl_response_area`, `cl_instructional_segment`, `cl_standards_block`) carry only intrinsic content — no parent FKs, no page FKs.

## 14. References

- Prior PR: https://github.com/virendraqbs/idmlExtraction/pull/1 (canonical schema conformance).
- Existing DB schema dump: `cl_json_schema.sql`
- Canonical schemas: `CL-Json-Schema/schemas/`
- Pipeline: `services/pipeline_service.py`, `services/assembler.py`, `utils/schema_chunks.py`
- Editor: `templates/results.html`, `controllers/job_controller.py`
- DB layer: `database/__init__.py`
- Polymorphic precedent: `cl_image_usage` (in `cl_json_schema.sql`)
