# Client Feedback & Schema Fixes

**Branch:** `fix/client-feedback-schema-corrections`
**Date:** 2026-03-19
**Source files:**
- Manual JSON edits: `Feedback/Json files 2/` (compared against `Lesson 1/b4084259.../`)
- Client feedback spreadsheet: `Feedback/json-analysis.xlsx`

---

## Overview

Two rounds of analysis were performed:

1. **Diff analysis** — comparing the generated JSON files against the manually corrected versions to identify systematic patterns in what the client changed.
2. **Client feedback spreadsheet** — 16 specific issues raised by the client against the manually corrected files.

The fixes were applied to `utils/schema_chunks.py`, `services/assembler.py`, and `services/gemini_service.py`.

---

## Client Feedback Spreadsheet — 16 Issues

| # | File | Issue | Status | Fix Applied |
|---|------|-------|--------|-------------|
| 1 | `02_enums` | Invalid JSON — trailing comma in `activityTypes` array | Generator fix | Enum is now built programmatically; no trailing commas possible |
| 2 | `03_resource` | `modules[0].type = "MODULE"` — redundant | **Fixed** | Removed `type` from modules reference |
| 3 | `04_module` | `topics[0].type = "TOPIC"` — redundant | **Fixed** | Removed `type` from topics reference |
| 4 | `05_topic` | Invalid JSON — missing comma in `lessons` array | Generator fix | Generator produces valid JSON; no manual syntax errors |
| 5 | `04_module` | `moduleSummary` is `""` — should be `null` or absent | **Fixed** | Empty string → `null` |
| 6 | `05_topic` | `topicSummary` is `""` — should be `null` or absent | **Fixed** | Empty string → `null` |
| 7 | `05_topic` | `lessons[0].sequenceNumber` not required | **Fixed** | Removed `sequenceNumber` from lesson references in topic |
| 8 | `08_tasks` | `taskNumber: "0"` — all others start at `"1"` | **Fixed** | Blank task number → `"1"` (was `""` then manually `"0"`, which is wrong) |
| 9 | `12_images` | `imageType: "ICON"` + `isDecorative: true` — contradictory | **Fixed** | `ICON` imageType forces `isDecorative: false` |
| 10 | `13_pages` | `pageType: "SPB_LESSON_PRACTICE"` inside a `STUDENT_RESOURCE_BOOK` | **Fixed** | Remapped to `SRB_LESSON_PRACTICE`; added `_PAGE_TYPE_MAP` for all legacy types |
| 11 | `18_scaffolding` | `$ref` → `ScaffoldingType` (PascalCase) vs enum key `scaffoldingType` (camelCase) | Schema issue | Not a code issue — JSON Schema definition needs updating separately |
| 12 | `01_primitives` | Uses `snake_case` keys — schema convention is `camelCase` | **Fixed** | All keys converted to camelCase (`resourceId`, `moduleId`, etc.) |
| 13 | `02_enums` | No schema defines enum catalog wrapper format | Schema issue | Not a code issue — JSON Schema definition needs a wrapper schema |
| 14 | `05_topic` | `topicNumber: 13` — is this correct? | Content question | Extracted from PDF; depends on source content |
| 15 | `06_lesson` | `LessonType` enum exists in enums.json but lesson schema has no `lessonType` | Schema issue | No `lessonType` field added — schema definition should be audited |
| 16 | `07_activities` | `KEY_TERMS` and `ACTIVATE` activities have `tasks: []` | By design | `KEY_TERMS` tasks → direction lines; `ACTIVATE` may have no tasks — correct behavior |

---

## Diff Analysis — Systematic Patterns Fixed

These were identified by comparing generated vs manually corrected JSON files across all 17 file pairs.

### 1. `01_primitives.json` — camelCase keys
**Before:** `resource_id`, `module_id`, `topic_id`, `lesson_id`, `standards_block_id`, `total_pages`, `extracted_at`
**After:** `resourceId`, `moduleId`, `topicId`, `lessonId`, `standardsBlockId`, `totalPages`, `extractedAt`

### 2. `02_enums.json` — Remove `UNREVIEWED` from imageTypes
`UNREVIEWED` is a pipeline-internal marker, not a schema-valid imageType. Filtered out of the `imageTypes` enum list. Images with `UNREVIEWED` type still appear in `12_images.json` for manual review.

### 3. `03_resource.json` — Remove always-null fields
Removed: `subtitle`, `series`, `edition`, `publisher`, `isbn`, `metadata.extractedAt`
These fields are always `null` and add noise to the output.

### 4. `04_module.json` — Multiple fixes
- **Title prefix stripping:** `"Module 1: Searching for Patterns"` → `"Searching for Patterns"` (uses `_strip_entity_number_prefix()`)
- **`moduleSummary`:** empty string → `null`
- **`gradeLevel`:** defaults to `"HS"` (was `""`)
- **`metadata.subtitle`:** removed (was only conditionally added; not a valid schema field)
- **`topics` ref:** `{"id": ..., "type": "TOPIC", "sequenceNumber": 1}` → `{"id": ..., "sequenceNumber": 1}`

### 5. `05_topic.json` — Multiple fixes
- **`topicSummary`:** empty string → `null`
- **`lessons` ref:** removed `sequenceNumber` (not required)
- **`metadata: {}`:** removed empty metadata object

### 6. `08_tasks.json` — Remove `sourcePage`, fix `taskNumber`
- `sourcePage` removed — pipeline-internal field
- Blank `taskNumber` (`""`) → `"1"` (not `"0"`)

### 7. `09_stems.json` — Schema cleanup
Removed fields:
- `sourceePage` — pipeline-internal
- `responseAreaType` — redundant with the `responseArea` UUID reference
- `subTasks` — sub-tasks are promoted to top-level stems during manual review (not auto-flattened)

Changed behavior:
- `ancillaryText` only included when non-null (avoids null noise)

### 8. `10_standards.json` — Remove `hasModelingSymbol`
`hasModelingSymbol` removed from every standard object.

### 9. `11_standards_blocks.json` — Standards reference format
- **Before:** `{"id": ..., "code": "A-SSE.1", "sequenceNumber": 1}`
- **After:** `{"id": ..., "type": "STANDARDS", "sequenceNumber": 1}`
- `pageLocationHelpText: null` removed.

### 10. `12_images.json` — Slimmed schema
**Removed fields** (all were always `null`, redundant, or pipeline-internal):
`technicalArtType`, `url`, `sourceFilename`, `sourceFileUrl`, `caption`, `title`, `format`, `description`, `position`, `containsGraph`, `isResponseArea`, `responseAreaType`, `graphDetails`, `sourcePage` (from output), `pdfPageIndex`, `imagePath`, `pageImagePath`, `copyright` (entire object), `metadata` (entire object), `accessibility.longDescription`, `accessibility.transcriptUrl`

**`ICON` + `isDecorative` fix:**
If `imageType == "ICON"`, `isDecorative` is forced to `false`. ICON images are functional UI elements — marking them decorative is semantically contradictory.

### 11. `13_pages.json` — Restructured metadata
**Removed:** `pageNumber`, `pdfPageIndex`, `layout`
**Added:**
```json
"metadata": {
  "pageNumberRepresentations": { "numeric": <page_number> },
  "lessonContext": {
    "topicNumber": ...,
    "topicTitle": ...,
    "lessonNumber": ...,
    "lessonTitle": ...
  }
}
```

**Page type remapping (`_PAGE_TYPE_MAP`):**
| Old value | New value |
|-----------|-----------|
| `STANDARDS_PAGE` | `SRB_LESSON_INTRODUCTION_ACTIVATE` |
| `SPB_PRACTICE` | `SRB_LESSON_PRACTICE` |

Also updated in MASTER_PROMPT so Gemini emits the correct type directly.

### 12. `18_scaffolding.json` — `image: null` removed
The `image` field was always `null` for most scaffolding items. Removed from output.

---

## Files Changed

| File | Changes |
|------|---------|
| `utils/schema_chunks.py` | All schema builder functions updated (see above) |
| `services/assembler.py` | Pass `lesson_meta` to `build_pages_chunk`; remove `STANDARDS_PAGE` from `_INTRO_PAGE_TYPES` |
| `services/gemini_service.py` | MASTER_PROMPT: `SPB_PRACTICE` → `SRB_LESSON_PRACTICE` in page type list and JSON template |

---

## Open Issues (Not Fixed in Code)

These require schema definition or manual content changes, not code changes:

| Issue | Action Needed |
|-------|---------------|
| `18_scaffolding` — `$ref ScaffoldingType` PascalCase vs camelCase key | Update CL-Json-Schema scaffolding schema definition |
| `02_enums` — no JSON Schema for enum catalog wrapper | Add a schema for the enums catalog format |
| `06_lesson` — `LessonType` enum exists but no `lessonType` field on lesson schema | Audit CL-Json-Schema lesson schema; add field or remove enum |
| `subTasks` flattening | Manual review step; auto-flattening would require stable UUID assignment across re-runs |
