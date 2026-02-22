# CL Three-Phase Schema Extraction

Structured extraction of Carnegie Learning JSON Schema from PDF textbooks in three clean phases.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: Sample JSON Files                                      │
│  15 individual JSON files — one per schema type                  │
│  Purpose: Reference, testing, template for Phase 2 output        │
│  Location: phase1_samples/                                       │
│  No API needed. Static files, run once.                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: Gemini Extraction → Individual JSONs                   │
│  Sends each PDF page to Gemini Vision with schema-specific       │
│  prompts. Writes one JSON file per schema type.                  │
│  Location: phase2_extracted/                                     │
│  Needs: PDF file + Gemini API key                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: Merge → Flat + Nested                                  │
│  Reads all Phase 2 files. Validates all cross-references.        │
│  Outputs:                                                        │
│    merged_flat.json    ← DB-ready flat arrays                    │
│    merged_nested.json  ← Fully embedded for human review         │
│    merge_report.json   ← Stats + alerts + broken references      │
│  Location: phase3_merged/                                        │
│  No API needed.                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 — Sample Files

| File | Schema | Purpose |
|---|---|---|
| `01_primitives.json` | common/primitives | UUID + Reference patterns |
| `02_enums.json` | common/enums | All valid enum values |
| `03_resource.json` | resource/resource | Top-level book resource |
| `04_module.json` | content/module | Module within resource |
| `05_topic.json` | content/topic | Topic within module |
| `06_lesson.json` | content/lesson | Lesson within topic |
| `07_activity.json` | content/activity | Single activity (Explore) |
| `08_task.json` | content/task | Single task within activity |
| `09_stem.json` | content/stem | Single stem within task |
| `10_standard.json` | standards/standard | One CA_CCSS standard |
| `11_standards-block.json` | standards/standards-block | Grouped standards display |
| `12_image.json` | media/image | Image with full metadata |
| `13_page.json` | resource/page | Page with populated contentBlocks |
| `14_instructional-prompt.json` | instructional-guide/instructional-prompt | Teacher TIG prompt |
| `15_instructional-segment.json` | instructional-guide/instructional-segment | Teacher TIG segment |

---

## Phase 2 — Extracted Files

Same 15 schema types but populated from the actual PDF:

| File | Contains |
|---|---|
| `01_primitives_used.json` | All UUIDs generated during extraction |
| `02_enums_used.json` | Enum values observed in this specific PDF |
| `03_resource.json` | Extracted resource metadata |
| `04_module.json` | Extracted module |
| `05_topic.json` | Extracted topic |
| `06_lesson.json` | Extracted lesson with learning goals |
| `07_activities.json` | All activities found (array) |
| `08_tasks.json` | All tasks (array) |
| `09_stems.json` | All stems with response areas (array) |
| `10_standards.json` | All standards with full text (array) |
| `11_standards_blocks.json` | Standards block(s) (array) |
| `12_images.json` | All images with Gemini-generated alt text (array) |
| `13_pages.json` | All pages with populated contentBlocks (array) |
| `14_instructional_prompts.json` | Teacher prompts found (array) |
| `15_instructional_segments.json` | Teacher segments found (array) |

---

## Phase 3 — Merged Output

### merged_flat.json
All entities as top-level arrays. UUIDs link across arrays. Ready for DB ingestion where each array maps to a table.

```json
{
  "resource": { ... },
  "module": { ... },
  "activities": [ {...}, {...} ],
  "tasks": [ {...}, {...} ],
  "stems": [ {...}, {...} ],
  ...
}
```

### merged_nested.json
Fully embedded hierarchy. Every child is inline inside its parent. Ready for human review and rendering.

```json
{
  "resource": {
    "modules": [{
      "topics": [{
        "lessons": [{
          "standardsBlock": { "standards": [{...}, {...}] },
          "activities": [{
            "tasks": [{
              "stems": [{...}]
            }]
          }]
        }]
      }]
    }],
    "pages": [{ "contentBlocks": [...] }]
  }
}
```

### merge_report.json
Validation summary: entity counts, broken references, accessibility alerts, readiness status.

---

## Setup

```bash
pip install google-generativeai pdf2image pdfplumber Pillow python-dotenv

# macOS
brew install poppler
# Ubuntu
sudo apt-get install poppler-utils
```

```bash
cp .env.example .env
# Set GEMINI_API_KEY=AIza...
```

---

## Usage

### Run all 3 phases
```bash
cd scripts/
python run_all.py --pdf ../path/to/lesson.pdf --api-key AIza...
```

### Run Phase 2 only
```bash
python phase2_extract.py --pdf path/to/lesson.pdf --api-key AIza...
```

### Run Phase 3 only (merge existing Phase 2 output)
```bash
python phase3_merge.py --input-dir ../phase2_extracted --output-dir ../phase3_merged
```

### Skip Phase 2, just re-merge
```bash
python run_all.py --skip-phase2
```

---

## Key design decisions

**Phase 2 uses separate Gemini prompts per schema** — Each page is sent to Gemini 8 times with schema-specific prompts. This gives more focused, accurate extraction than one giant prompt, and means cache misses on one schema don't affect others.

**Response caching** — Each (page, schema) combination is cached in `phase2_cache/`. Re-runs are instant and free for already-processed pages.

**Phase 3 validates all references** — Before merging, every UUID reference is checked to exist in the entity store. Broken references are reported in `merge_report.json` rather than silently producing invalid output.

**Two merge formats** — Flat is what goes to a database. Nested is what humans and rendering engines read. Both are generated from the same validated entity store.
