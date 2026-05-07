# Canonical Schema Conformance — Design

**Date:** 2026-05-07
**Owner:** Pipeline team
**Status:** Approved (brainstorming → planning)
**Repository:** `carnegielearning-clearmathnational`
**Base branch:** `development`
**Feature branch:** `feat/canonical-schema-conformance`

---

## 1. Problem

The PDF-extraction pipeline produces 19 SRB schema files and 5 TIG schema files that do not validate against the canonical schema delivered by Carnegie Learning at `CL-Json-Schema/schemas/`. The mismatches fall into two categories:

1. **Canonical schema is internally inconsistent.** It declares `array<Reference>` fields for parent-to-child relationships at the resource and module levels, but its `ReferenceType` enum does not include the values (`MODULE`, `TOPIC`, `RESOURCE`) needed to populate those references. The pipeline cannot emit a valid Reference for these arrays without an enum extension.
2. **Canonical `InstructionalPromptType` enum is missing two TIG-specific values.** The pipeline already extracts `CONTENT_CONNECTION` and `COMMON_MISCONCEPTIONS` from teacher-guide PDFs (see `services/tig_extractor.py:74-75`), and the TIG assembler maps them through unchanged. The schema rejects them.

Additionally, the SRB pipeline omits the required `type` field on `resource.modules[]` and `module.topics[]` references entirely. Even with the enum extended, the references are still invalid until the assembler emits the field.

The Carnegie Learning team has signed off on the proposed schema extensions (see `docs/SCHEMA_EXTENSIONS_PROPOSAL.md`).

## 2. Goals

- Every JSON file produced by a fresh pipeline run validates against the (extended) canonical schema.
- Schema extensions are minimal and additive; no canonical values are renamed or removed.
- Implementation is small, surgical, and reviewable in a single PR.

## 3. Non-Goals

- Image rendering on the results page (`imagePath` field). Tracked separately.
- Editor / results UI changes. Tracked separately.
- Backfilling pre-existing job outputs in `outputs/` to the new shape.
- Restructuring activities/tasks/stems content to match the manually corrected Final JSONs (separate scope).

## 4. Architecture

Three discrete changes to the existing codebase. No new files, no new modules.

### 4.1 Canonical schema extensions

File: `CL-Json-Schema/schemas/common/enums.json`

| Enum | Add values |
|------|-----------|
| `ReferenceType` | `RESOURCE`, `MODULE`, `TOPIC` |
| `InstructionalPromptType` | `CONTENT_CONNECTION`, `COMMON_MISCONCEPTIONS` |

Both edits are additive. Existing values are preserved in their existing order; new values are appended.

### 4.2 SRB assembler — populate `type` on parent-child references

File: `utils/schema_chunks.py`

| Line | Current | New |
|------|---------|-----|
| 163 | `"modules": [{"id": module_id}]` | `"modules": [{"id": module_id, "type": "MODULE"}]` |
| 209 | `"topics": [{"id": topic_id, "sequenceNumber": 1}]` | `"topics": [{"id": topic_id, "type": "TOPIC", "sequenceNumber": 1}]` |

No other reference shape changes — `lesson.activities[]`, `topic.lessons[]`, image and standards refs already emit canonical `type` values.

### 4.3 Verification script

File: `scripts/verify_canonical_conformance.py` (new, one-shot)

Loads `CL-Json-Schema/schemas/common/enums.json` plus an extracted job folder. Walks every assembled JSON; for every object that looks like a Reference (`{id, type, ...}`), asserts `type` is in `ReferenceType.enum`. For every `instructionalPromptType` value, asserts membership in the extended enum. Exits non-zero on any violation.

Used during PR review and once per regression check; not part of the CI pipeline (no CI exists in this repo).

## 5. Data Flow (no change)

The pipeline data flow is unchanged:

```
PDF
 → pipeline_service.extract_pages (Gemini Vision, page-by-page)
 → raw_extractions.json
 → assembler.assemble_schemas / tig_assembler.assemble_tig_schemas
 → utils/schema_chunks.build_* (per-entity builders)
 → 19 SRB files / 5 TIG files in outputs/<job>/
```

The only behavioral change is in two builder functions inside `utils/schema_chunks.py` and the static enum file. No new components, no new control flow.

## 6. Error Handling

No new failure modes. The two changed builders are pure dict construction with no I/O or branching. The schema file change is additive and cannot break parsers that already accept the prior set.

The verification script reports violations but does not modify state.

## 7. Testing

- **Unit:** None new. Existing test suite (if any — to be confirmed during planning) re-runs unchanged.
- **Schema validation:** `verify_canonical_conformance.py` run against an SRB job and a TIG job after re-extraction. Manual `python -m json.tool` parse check on the two edited files.
- **Integration / smoke:**
  - Re-run extraction on the existing SRB sample `sourceFile/A1_T13_L1.pdf`. Inspect `outputs/<new-job>/03_resource.json` for `modules[0].type == "MODULE"`. Inspect `04_module.json` for `topics[0].type == "TOPIC"`.
  - Re-run TIG extraction on `sourceFile/tig/EMNA2e_G05_M01_T01_L01_TIG_TAGGED.pdf`. Inspect `14_instructional_prompts.json` — when `CONTENT_CONNECTION` or `COMMON_MISCONCEPTIONS` appear, they validate against the extended enum.

## 8. Migration / Backwards Compatibility

- Schema enum additions are backwards-compatible for any consumer that already accepts the prior set.
- The `type` additions to `modules[]` / `topics[]` references are forward-only. Any consumer that strictly enforced bare `{id}` shape will see an extra key. None known.
- Pre-existing job folders in `outputs/` retain their old shape and are not migrated. Documented in the README.

## 9. Branch + Commit Plan

- Branch from `development`: `feat/canonical-schema-conformance`
- Commit 1: schema enum extensions (`CL-Json-Schema/schemas/common/enums.json`)
- Commit 2: SRB assembler reference-type emission (`utils/schema_chunks.py`)
- Commit 3: verification script (`scripts/verify_canonical_conformance.py`)
- Open PR targeting `development`

## 10. Open Questions

None blocking. Image-rendering field name (`imagePath` vs `filepath`) and TIG `pdfPageIndex`/`sourcePage` gaps will be handled in a separate brainstorm + spec.

## 11. References

- Schema-extension proposal sent to client: `docs/SCHEMA_EXTENSIONS_PROPOSAL.md`
- Canonical schemas: `CL-Json-Schema/schemas/`
- Final JSON reference set: `Feedback/Final JSONs/`
- Reference primitive: `CL-Json-Schema/schemas/common/primitives.json#/definitions/Reference`
- Pipeline entry: `services/pipeline_service.py`
- SRB assembler: `services/assembler.py`, `utils/schema_chunks.py`
- TIG assembler: `services/tig_assembler.py`, `services/tig_extractor.py`
