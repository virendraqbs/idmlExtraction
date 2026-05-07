# Proposed Extensions to CL-Json-Schema

**Audience:** Carnegie Learning schema team
**Date:** 2026-05-07
**Status:** Proposal — awaiting client confirmation

---

## 1. Context

We are aligning the PDF extraction pipeline output with the canonical schema delivered by your team at `CL-Json-Schema/`. While auditing the manually corrected sample JSONs (the "Final JSONs" set previously shared with you) against the canonical `schemas/`, we found two gaps where the canonical schema cannot describe values that legitimately appear in the data.

We treat the canonical schema as the source of truth. Rather than route around the gaps in the pipeline, we propose extending the canonical schema and request your sign-off.

---

## 2. Gap A — `ReferenceType` enum is missing parent-entity values

### Observed

The schema defines parent-to-child reference arrays at the resource and module levels:

| Schema file | Field | Item type |
|-------------|-------|-----------|
| `schemas/resource/resource.json` | `modules` | `array<Reference>` |
| `schemas/content/module.json` | `topics` | `array<Reference>` |

A `Reference` requires `{ id: UUID, type: ReferenceType }` per `schemas/common/primitives.json`.

The current canonical `ReferenceType` enum (`schemas/common/enums.json`) lists 13 values:

```
LESSON, ACTIVITY, TASK, STANDARDS_BLOCK, STANDARDS,
INSTRUCTIONAL_GUIDE_PROMPT, GOALS, IMAGE, STEM,
SCAFFOLDING, PAGES, INSTRUCTIONAL_SEGMENT, INSTRUCTIONAL_PROMPT
```

The values needed to populate the `Reference.type` field for `modules[]` and `topics[]` arrays — `MODULE` and `TOPIC` — are **not** in the enum. As a result, the schema is internally inconsistent: it requires references it cannot validly describe.

### Proposed extension

Add the following values to `ReferenceType`:

| Value | Used by |
|-------|---------|
| `RESOURCE` | reverse references to the parent resource |
| `MODULE`   | `resource.modules[].type` |
| `TOPIC`    | `module.topics[].type` |

Updated enum (16 values total):

```
LESSON, ACTIVITY, TASK, STANDARDS_BLOCK, STANDARDS,
INSTRUCTIONAL_GUIDE_PROMPT, GOALS, IMAGE, STEM,
SCAFFOLDING, PAGES, INSTRUCTIONAL_SEGMENT, INSTRUCTIONAL_PROMPT,
RESOURCE, MODULE, TOPIC
```

---

## 3. Gap B — `InstructionalPromptType` is missing TIG-specific prompt categories

### Observed

In the manually corrected TIG `14_instructional_prompts_updated.json`, two prompt-type values appear that are not in the canonical enum:

| Value | Source |
|-------|--------|
| `CONTENT_CONNECTION` | TIG lesson narrative side-bar |
| `COMMON_MISCONCEPTIONS` | TIG misconception callouts |

Current canonical `InstructionalPromptType` enum (10 values):

```
LEARNING_GOALS, LANGUAGE_GOALS, DAILY_MATH_ROUTINES,
MULTILINGUAL_LEARNER_SUPPORT, TEACHER_STORY, HABITS_OF_MIND,
STUDENT_LOOK_FORS, CULTIVATE_CONNECTIONS,
STUDENT_EDITION_PAGE_IMAGE, MATERIALS_LIST
```

### Option 1 — Extend canonical (recommended)

Add `CONTENT_CONNECTION` and `COMMON_MISCONCEPTIONS`. Updated enum (12 values).

### Option 2 — Remap existing values

If your team prefers a fixed enum, please advise the canonical mappings, e.g.:
- `CONTENT_CONNECTION` → `TEACHER_STORY`?
- `COMMON_MISCONCEPTIONS` → `STUDENT_LOOK_FORS`?

Either choice is fine on our side; we need a decision so the extractor emits canonical values.

---

## 4. Items NOT requiring schema change

### `lessonType` is already canonical

`schemas/content/lesson.json` declares the optional property `lessonType` referencing `LessonType` enum (`CONCEPT_LESSON`, `RE-ENGAGEMENT_LESSON`). The pipeline emits this field correctly.

The Final JSON sample previously shared with you had `lessonType` removed during manual editing. We will keep the field in pipeline output per the canonical schema. No schema change required.

### `ScaffoldingType` is already a single canonical value

Canonical `scaffoldingType` enum has one value: `CHARACTER_SUPPORT`. The Final JSONs correctly fold all scaffolding entries to this value. No schema change required.

### Manual JSON syntax issues in Final JSONs (informational only)

The previously shared Final JSON set contained three strict-JSON syntax issues introduced during manual editing (trailing commas, missing comma, blank elements). These are not produced by the pipeline; we list them here for record only:

| File | Issue |
|------|-------|
| `Final JSONs/SRB JSONs/02_enums_updated.json` | trailing comma + blank line in `activityTypes` array (line 9) |
| `Final JSONs/SRB JSONs/05_topic_updated.json` | missing comma between `"type": "LESSON"` and `"sequenceNumber": 1` (line 11) |
| `Final JSONs/TIG JSONs/15_instructional_segments_updated.txt` | trailing comma + blank object element inside `studentQuestions` (~line 130) |

No action requested on the schema. We will produce strict-JSON output from the pipeline.

---

## 5. Summary — what we need from your team

| # | Decision | Default if no response |
|---|----------|------------------------|
| 1 | Approve adding `RESOURCE`, `MODULE`, `TOPIC` to `ReferenceType` | We add these values to our local copy of the schema and proceed |
| 2 | Approve adding `CONTENT_CONNECTION`, `COMMON_MISCONCEPTIONS` to `InstructionalPromptType` (Option 1) **OR** provide canonical remapping (Option 2) | We default to Option 1 |

Once we have your sign-off, we will update the pipeline so all generated SRB and TIG JSON files conform exactly to the canonical schema (with the agreed extensions).

---

## 6. References

- Canonical schemas: `CL-Json-Schema/schemas/`
- Canonical enums: `CL-Json-Schema/schemas/common/enums.json`
- Reference primitive: `CL-Json-Schema/schemas/common/primitives.json#/definitions/Reference`
- Final JSONs reviewed: `Feedback/Final JSONs/`
