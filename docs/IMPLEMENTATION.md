# CL PDF Extraction Pipeline — Implementation Guide

> **Version**: 2.0 (FastAPI)
> **Last Updated**: March 2026
> **Framework**: FastAPI + Uvicorn + Jinja2
> **AI Backend**: Google Gemini 2.5 Flash (Vision)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Project Structure](#3-project-structure)
4. [Technology Stack](#4-technology-stack)
5. [Configuration](#5-configuration)
6. [Application Startup Flow](#6-application-startup-flow)
7. [Authentication](#7-authentication)
8. [Pipeline — The 5-Stage Extraction Process](#8-pipeline--the-5-stage-extraction-process)
9. [Schema Assembly — 18 + 1 Output Files](#9-schema-assembly--18--1-output-files)
10. [Merged JSON — Parent-Child Hierarchy](#10-merged-json--parent-child-hierarchy)
11. [API Reference](#11-api-reference)
12. [Frontend Views](#12-frontend-views)
13. [Data Flow Diagrams](#13-data-flow-diagrams)
14. [CL-Json-Schema Hierarchy](#14-cl-json-schema-hierarchy)
15. [File-by-File Reference](#15-file-by-file-reference)
16. [Gemini Extraction Prompt](#16-gemini-extraction-prompt)
17. [Error Handling & Retry Strategy](#17-error-handling--retry-strategy)
18. [Security Considerations](#18-security-considerations)
19. [Setup & Deployment Guide](#19-setup--deployment-guide)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. System Overview

CL PDF Extraction Pipeline is a web application that extracts structured educational content from Carnegie Learning PDF textbooks using Google Gemini Vision AI. It processes each PDF page through a vision model, extracts pedagogical elements (activities, tasks, stems, prompts, standards, images), and produces a set of JSON files conforming to the **CL-Json-Schema** specification.

### What It Does

```
PDF Upload → Page Rendering → AI Extraction → Schema Assembly → 19 JSON Files
                                                                    ↓
                                                           Web Viewer (Editor / Source / PDF)
```

### Key Capabilities

- **PDF → Structured JSON**: Converts educational PDFs into 18 schema-compliant JSON files plus a merged nested JSON
- **AI-Powered Extraction**: Uses Gemini 2.5 Flash Vision to understand page layouts, text, math, graphs, and images
- **Real-Time Progress**: Live pipeline monitoring with 5-stage progress tracking
- **Three-View Results**: Editor (human-readable), Source (raw JSON), PDF (original document)
- **Merged Hierarchy**: Single nested JSON following the full parent-child relationship
- **Extraction Report**: Per-page extraction report tracking attempts, status, page type, timing, and errors — viewable from dashboard and job status page
- **Admin Browse**: View any previously extracted output folder

---

## 2. Architecture Diagram

### High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (Client)                          │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  Login   │ │Dashboard │ │  Upload  │ │ Results  │           │
│  │  Page    │ │  Page    │ │  Page    │ │  Page    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                           │ Editor │ Source│PDF │
└──────────────────────────────────────────────────────────────────┘
                              │  HTTP
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│  │   Auth      │  │    Job       │  │   Static Files     │     │
│  │  Controller │  │  Controller  │  │  (CSS / Theme)     │     │
│  └─────────────┘  └──────────────┘  └────────────────────┘     │
│         │                │                                      │
│         │    ┌───────────┴────────────┐                         │
│         │    │                        │                         │
│         ▼    ▼                        ▼                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│  │  Session    │  │  Pipeline    │  │     Assembler      │     │
│  │ Middleware  │  │  Service     │  │     Service        │     │
│  └─────────────┘  └──────────────┘  └────────────────────┘     │
│                          │                    │                  │
│                          ▼                    ▼                  │
│                   ┌──────────────┐  ┌────────────────────┐     │
│                   │   Gemini     │  │  Schema Chunks     │     │
│                   │   Service    │  │  (18 builders)     │     │
│                   └──────────────┘  └────────────────────┘     │
│                          │                    │                  │
│  ┌─────────────┐         │                    │                  │
│  │  Job Model  │         │                    │                  │
│  │ (In-Memory) │         │                    │                  │
│  └─────────────┘         │                    │                  │
└──────────────────────────────────────────────────────────────────┘
                           │                    │
               ┌───────────┘                    │
               ▼                                ▼
    ┌──────────────────┐             ┌──────────────────────┐
    │  Google Gemini    │             │  File System         │
    │  Vision API       │             │  uploads/ outputs/   │
    │  (2.5 Flash)      │             │  (18 + merged JSON)  │
    └──────────────────┘             └──────────────────────┘
```

### Request Flow Diagram

```
User                Browser              FastAPI              Pipeline Thread
 │                    │                    │                       │
 │── Login ──────────>│                    │                       │
 │                    │── POST /login ────>│                       │
 │                    │<── Session Cookie──│                       │
 │                    │                    │                       │
 │── Upload PDF ─────>│                    │                       │
 │                    │── POST /upload ───>│                       │
 │                    │                    │── Save PDF to disk    │
 │                    │                    │── Create Job record   │
 │                    │                    │── Start pipeline ────>│
 │                    │<── 303 /job/{id} ──│                       │
 │                    │                    │                       │
 │── Monitor ────────>│                    │     ┌─────────────────┤
 │                    │── GET /api/job ───>│     │ Stage 1: Health │
 │                    │<── {progress:25}───│     │ Stage 2: Render │
 │                    │── GET /api/job ───>│     │ Stage 3: Extract│
 │                    │<── {progress:90}───│     │ Stage 4: Assemble
 │                    │── GET /api/job ───>│     │ Stage 5: Done   │
 │                    │<── {status:done} ──│     └─────────────────┤
 │                    │                    │                       │
 │── View Results ───>│                    │                       │
 │                    │── GET /results ───>│                       │
 │                    │<── HTML (3 views)──│                       │
 │                    │                    │                       │
 │                    │── GET /api/editor─>│                       │
 │                    │<── Nested JSON ────│                       │
```

---

## 3. Project Structure

```
cl-pdf-extraction/
├── app.py                          # Application factory & entry point
├── config.py                       # Centralised configuration (env vars)
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables (not in git)
│
├── controllers/                    # Route handlers (MVC Controller layer)
│   ├── __init__.py                 #   Re-exports auth_router, jobs_router
│   ├── auth_controller.py          #   Login / logout / session
│   └── job_controller.py           #   Dashboard, upload, results, APIs
│
├── services/                       # Business logic layer
│   ├── __init__.py                 #   Re-exports service classes
│   ├── gemini_service.py           #   Gemini Vision API wrapper
│   ├── pipeline_service.py         #   5-stage pipeline orchestrator
│   └── assembler.py                #   Builds 18+1 JSON schema files
│
├── models/                         # Data models
│   ├── __init__.py                 #   Re-exports Job, JobStatus, job_repo
│   └── job.py                      #   Job dataclass & in-memory repository
│
├── utils/                          # Stateless utility functions
│   ├── __init__.py                 #   Re-exports helpers
│   ├── file_utils.py               #   PDF page count, JSON I/O, validation
│   └── schema_chunks.py            #   18 build_*() functions for schemas
│
├── templates/                      # Jinja2 HTML templates
│   ├── login.html                  #   Admin login page
│   ├── dashboard.html              #   Job listing dashboard
│   ├── upload.html                 #   PDF upload form
│   ├── job_status.html             #   Live pipeline monitor
│   ├── results.html                #   Editor / Source / PDF results viewer
│   └── browse.html                 #   Browse output folders
│
├── static/                         # Static assets
│   └── css/
│       └── theme.css               #   Purple theme (CSS variables)
│
├── uploads/                        # Uploaded PDFs (runtime, git-ignored)
├── outputs/                        # Extraction outputs (runtime, git-ignored)
│   └── {job_id}/                   #   One folder per job
│       ├── 01_primitives.json
│       ├── 02_enums.json
│       ├── ... (18 schema files)
│       ├── merged.json             #   Single nested hierarchy
│       └── extraction_report.json  #   Per-page extraction report
│
├── docs/                           # Documentation
│   └── IMPLEMENTATION.md           #   This file
│
├── CL-Json-Schema/                 # Schema definitions & documentation
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── SCHEMA_REFERENCE.md
│   ├── IMPLEMENTATION_EXAMPLES.md
│   ├── DATA_ARCHITECTURE.md
│   ├── INDEX.md
│   └── schemas/
│       ├── common/                 #   primitives, enums, metadata
│       ├── content/                #   module, topic, lesson, activity, task, stem
│       ├── resource/               #   resource, page
│       ├── standards/              #   standard, standards-block
│       ├── instructional-guide/    #   instructional-prompt, instructional-segment
│       ├── media/                  #   image
│       └── extraction/             #   extraction-job-result
│
└── theme/                          # Design theme source files
    └── purple-free/                #   Purple theme assets
```

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | FastAPI 0.115+ | Async HTTP server, routing, dependency injection |
| **ASGI Server** | Uvicorn | Production-grade async server with hot reload |
| **Templating** | Jinja2 | Server-side HTML rendering |
| **Session** | Starlette SessionMiddleware + itsdangerous | Signed cookie-based sessions |
| **AI/Vision** | Google Gemini 2.5 Flash | Page image → structured JSON extraction |
| **PDF Rendering** | pdf2image + Poppler | PDF → PNG page images |
| **PDF Parsing** | pypdf | Page count detection |
| **Configuration** | python-dotenv | Environment variable management |
| **Styling** | Custom CSS (Purple Theme) | CSS variables, responsive design |
| **File Upload** | python-multipart | Multipart form data handling |

### System Dependencies

| Dependency | Install Command |
|-----------|----------------|
| Poppler | `brew install poppler` (macOS) / `apt install poppler-utils` (Ubuntu) |
| Python 3.11+ | Required for type hint syntax (`X \| None`) |

---

## 5. Configuration

### Environment Variables (`.env`)

```env
SECRET_KEY=your-secret-key-here          # Session signing key
FLASK_ENV=development                     # development | production
PORT=5000                                 # Server port
ADMIN_USER=admin                          # Login username
ADMIN_PASS=password                       # Login password
GEMINI_API_KEY=AIza...                    # Default Gemini API key
GEMINI_MODEL=gemini-2.5-flash            # Gemini model name
MAX_UPLOAD_MB=100                         # Max PDF file size
PDF_RENDER_DPI=200                        # Page image resolution
```

### Config Class (`config.py`)

The `Config` class loads all environment variables once at import time. Key computed properties:

| Property | Value | Description |
|----------|-------|-------------|
| `BASE_DIR` | `Path(__file__).resolve().parent` | Project root (always absolute) |
| `UPLOAD_DIR` | `BASE_DIR / "uploads"` | Where uploaded PDFs are stored |
| `OUTPUT_DIR` | `BASE_DIR / "outputs"` | Where extraction results are written |
| `MAX_CONTENT_LENGTH` | `MAX_UPLOAD_MB * 1024 * 1024` | Byte limit for uploads |
| `ALLOWED_EXTENSIONS` | `frozenset({"pdf"})` | Only PDFs accepted |

---

## 6. Application Startup Flow

```
python app.py (or uvicorn app:app)
      │
      ▼
  create_app()
      │
      ├── FastAPI(title="CL Pipeline", docs_url=None)
      │
      ├── Add SessionMiddleware(secret_key=...)
      │
      ├── config.init_dirs()
      │       └── Creates uploads/ and outputs/ if missing
      │
      ├── Mount /static → static/ directory
      │
      ├── Include auth_router (/, /login, /logout)
      │
      ├── Include jobs_router (/dashboard, /upload, /job, /results, /api, /browse, /outputs)
      │
      └── Register exception handler for NotAuthenticatedException → redirect to /login
```

---

## 7. Authentication

### Flow

```
                    ┌─────────────┐
                    │  Any Route  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ require_login│ (FastAPI Dependency)
                    │  Depends()  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐        ┌──────────────┐
                    │session has  │──No───>│  Raise       │
                    │logged_in?   │        │  NotAuth     │
                    └──────┬──────┘        │  Exception   │
                           │               └──────┬───────┘
                          Yes                     │
                           │               ┌──────▼───────┐
                    ┌──────▼──────┐        │  Exception   │
                    │  Proceed to │        │  Handler →   │
                    │  Route      │        │  303 /login  │
                    └─────────────┘        └──────────────┘
```

### Implementation

- **Session Store**: Signed cookies via `SessionMiddleware` (14-day expiry)
- **Login Validation**: Simple credential check against `config.ADMIN_USER` / `config.ADMIN_PASS`
- **Auth Dependency**: `require_login()` is injected via `Depends()` on every protected route
- **Unauthenticated Handling**: Custom `NotAuthenticatedException` caught by global handler → 303 redirect to `/login`

### Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Redirect to `/dashboard` if logged in, else `/login` |
| GET | `/login` | No | Render login form |
| POST | `/login` | No | Validate credentials, set session |
| GET | `/logout` | No | Clear session, redirect to `/login` |

---

## 8. Pipeline — The 5-Stage Extraction Process

### Pipeline Stages

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────┐
│ Stage 1  │───>│ Stage 2  │───>│ Stage 3  │───>│ Stage 4   │───>│Stage 5│
│ Health   │    │ Render   │    │ Extract  │    │ Assemble  │    │ Done  │
│ Check    │    │ PDF      │    │ Pages    │    │ Schemas   │    │       │
│ 0-5%    │    │ 5-15%   │    │ 15-85%  │    │ 85-100%  │    │ 100% │
└─────────┘    └─────────┘    └─────────┘    └──────────┘    └──────┘
```

### Stage Details

#### Stage 1: Health Check (`JobStatus.HEALTH_CHECK`)
- Verifies the Gemini API key is valid
- Sends a minimal test prompt ("Reply with exactly one word: OK")
- Raises `RuntimeError` if the key is invalid

#### Stage 2: Render PDF (`JobStatus.RENDERING`)
- Converts PDF to PNG images using `pdf2image.convert_from_path()`
- Resolution controlled by `config.PDF_RENDER_DPI` (default: 200 DPI)
- Records total page count on the job

#### Stage 3: Page Extraction (`JobStatus.EXTRACTING`)
- Iterates each page image sequentially
- Sends image + master prompt to Gemini Vision
- Parses JSON response (strips markdown fences)
- Gemini-level retry: up to 4 attempts with exponential backoff (10s, 20s, 40s, 60s) for rate limits
- Pipeline-level retry: if a page returns `UNKNOWN`, waits 5s and retries the entire extraction once
- Falls back to empty page structure on total failure
- Builds a per-page **extraction report** tracking: page number, attempts, status (ok/failed), page type, errors, and elapsed time (ms)
- Updates `job.progress` proportionally (15% → 85%)
- 1.5s pause between pages to respect API rate limits
- Saves `extraction_report.json` alongside `raw_extractions.json` for debugging

#### Stage 4: Schema Assembly (`JobStatus.ASSEMBLING`)
- Calls `assemble_schemas()` with all raw page data
- Generates canonical UUIDs for resource, module, topic, lesson, standards block
- Builds 18 individual JSON files + 1 merged JSON
- Writes all 19 files to `outputs/{job_id}/`

#### Stage 5: Done (`JobStatus.DONE`)
- Sets progress to 100%
- Records list of output filenames on the job
- Frontend redirects to results page

### Threading Model

```
Main Thread (Uvicorn)          Background Thread (Pipeline)
       │                              │
       │── POST /upload ──>           │
       │   Create Job                 │
       │   Start Thread ─────────────>│
       │<── 303 Redirect              │── Stage 1: Health Check
       │                              │── Stage 2: Render PDF
       │── GET /api/job/{id} ────>    │── Stage 3: Extract Pages
       │<── {progress: 45} ──────     │      (page 1, 2, 3...)
       │── GET /api/job/{id} ────>    │── Stage 4: Assemble
       │<── {progress: 92} ──────     │── Stage 5: Done
       │── GET /api/job/{id} ────>    │
       │<── {status: "done"} ────     │
```

---

## 9. Schema Assembly — 18 + 1 Output Files

### File Manifest

| # | Filename | Schema | Description | Builder Function |
|---|---------|--------|-------------|-----------------|
| 01 | `01_primitives.json` | — | Canonical IDs & run metadata | `build_primitives()` |
| 02 | `02_enums.json` | — | Distinct enum values found | `build_enums()` |
| 03 | `03_resource.json` | `resource.json` | Book/publication entity | `build_resource()` |
| 04 | `04_module.json` | `module.json` | Module entity (with standardsBody, gradeLevel, images, metadata) | `build_module()` |
| 05 | `05_topic.json` | `topic.json` | Topic entity (with topicSummary, images, metadata) | `build_topic()` |
| 06 | `06_lesson.json` | `lesson.json` | Lesson entity + goals (with images, metadata) | `build_lesson()` |
| 07 | `07_activities.json` | `activity.json` | Activity list (with goals, scaffolding refs, images, metadata) | `build_activities_chunk()` |
| 08 | `08_tasks.json` | `task.json` | Task list (with scaffolding refs) | `build_task()` (via activities) |
| 09 | `09_stems.json` | `stem.json` | Stem list with optional responseArea link | `build_stem()` (via activities) |
| 10 | `10_standards.json` | `standard.json` | Education standards | `build_standards_chunk()` |
| 11 | `11_standards_blocks.json` | `standards-block.json` | Grouped standards | `build_standards_blocks()` |
| 12 | `12_images.json` | `image.json` | Image entities with graph details | `build_images_chunk()` |
| 13 | `13_pages.json` | `page.json` | Page entities with layout | `build_pages_chunk()` |
| 14 | `14_instructional_prompts.json` | `instructional-prompt.json` | Sidebar/callout prompts | `build_instructional_prompts_chunk()` |
| 15 | `15_instructional_segments.json` | `instructional-segment.json` | Phase segments (Activate/Explore/Reflect) | `build_instructional_segments()` |
| 16 | `16_practice_sections.json` | `practice-section.json` | Practice sections grouping PRACTICE activities | `build_practice_sections_chunk()` |
| 17 | `17_response_areas.json` | `response-area.json` | Response area definitions linked from stems | (generated in `_build_tasks_for_activity()`) |
| 18 | `18_scaffolding.json` | `scaffolding.json` | Scaffolding items (hints, character support) linked from tasks | (generated in `_build_tasks_for_activity()`) |
| 19 | `merged.json` | — | **Single nested JSON** (full hierarchy) | `_build_merged_json()` |

### Assembly Order & Dependencies

```
extract_lesson_meta(pages)           ← Shared metadata from all pages
        │
        ▼
build_standards_chunk(pages)         ← 10_standards.json
        │
        ▼
build_standards_blocks(...)          ← 11_standards_blocks.json
        │
        ▼
build_activities_chunk(...)          ← 07_activities.json
        │                               08_tasks.json          (side-effect)
        │                               09_stems.json          (side-effect)
        │                               17_response_areas.json (side-effect)
        │                               18_scaffolding.json    (side-effect)
        ▼
build_practice_sections_chunk(...)  ← 16_practice_sections.json
build_images_chunk(pages)            ← 12_images.json
build_pages_chunk(pages)             ← 13_pages.json
build_instructional_prompts(pages)   ← 14_instructional_prompts.json
build_instructional_segments(...)    ← 15_instructional_segments.json
        │
        ▼
build_primitives(...)                ← 01_primitives.json
build_enums(...)                     ← 02_enums.json
build_resource(...)                  ← 03_resource.json
build_module(...)                    ← 04_module.json
build_topic(...)                     ← 05_topic.json
build_lesson(...)                    ← 06_lesson.json
        │
        ▼
   Build merged.json                 ← Nests everything into parent-child tree
        │
        ▼
   Write all 19 files to disk
```

---

## 10. Merged JSON — Parent-Child Hierarchy

The `merged.json` file combines all 18 individual files into a single nested structure following the CL-Json-Schema parent-child relationships.

### Nesting Structure

```
merged.json
├── meta                           (from 01_primitives.json)
├── enums                          (from 02_enums.json)
├── resource                       (from 03_resource.json)
│   └── modules[]                  (from 04_module.json)
│       └── topics[]               (from 05_topic.json)
│           └── lessons[]          (from 06_lesson.json)
│               ├── activities[]   (from 07_activities.json)
│               │   └── tasks[]    (from 08_tasks.json)
│               │       ├── stems[] (from 09_stems.json)
│               │       └── scaffolding[] (from 18_scaffolding.json)
│               ├── practiceSections[]     (from 16)
│               ├── responseAreas[]        (from 17)
│               ├── instructionalPrompts[] (from 14)
│               ├── standards[]    (from 10_standards.json)
│               └── standardsBlocks[]      (from 11)
├── pages[]                        (from 13_pages.json)
├── images[]                       (from 12_images.json)
└── instructionalSegments[]        (from 15)
```

### Merge Algorithm

```python
# Step 1: Group stems by their parent task ID
stems_by_task[taskId] → [stem, stem, ...]

# Step 2: Nest stems into tasks, group tasks by parent activity ID
tasks_by_activity[activityId] → [{...task, stems: [...]}, ...]

# Step 3: Nest tasks into activities, group activities by parent lesson ID
activities_by_lesson[lessonId] → [{...activity, tasks: [...]}, ...]

# Step 4: Build lesson with nested activities + prompts + standards
lesson_nested = {
    ...lesson,
    activities: activities_by_lesson[lessonId],
    instructionalPrompts: [...],
    standards: [...],
    standardsBlocks: [...]
}

# Step 5: Nest into topic → module → resource
topic_nested    = {...topic, lessons: [lesson_nested]}
module_nested   = {...module, topics: [topic_nested]}
resource_nested = {...resource, modules: [module_nested]}

# Step 6: Final structure
merged = {
    meta: primitives,
    enums: enums,
    resource: resource_nested,     ← Contains the full tree
    pages: [...],                   ← Physical layout (separate hierarchy)
    images: [...],
    instructionalSegments: [...]
}
```

### ID Linking (How References Are Resolved)

```
resource.id ──────────> module.resourceId
module.id ────────────> topic.moduleId
topic.id ─────────────> lesson.topicId
lesson.id ────────────> activity.lessonId
activity.id ──────────> task.activityId
task.id ──────────────> stem.taskId
lesson.id ────────────> instructionalPrompt.studentContentReferenceId
resource.id ──────────> page.resourceId
lesson.id ────────────> instructionalSegment.lessonId
```

---

## 11. API Reference

### HTML Pages (Server-Rendered)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Redirect to dashboard/login |
| GET | `/login` | No | Login form |
| POST | `/login` | No | Authenticate |
| GET | `/logout` | No | Clear session |
| GET | `/dashboard` | Yes | List all jobs |
| GET | `/browse` | Yes | List output folders |
| GET | `/upload` | Yes | Upload form |
| POST | `/upload` | Yes | Submit PDF + API key |
| GET | `/job/{job_id}` | Yes | Live pipeline monitor |
| GET | `/results/{job_id}` | Yes | Results viewer (Editor/Source/PDF) |

### JSON APIs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/job/{job_id}` | Yes | Pipeline progress polling (status, progress, logs, extraction_report) |
| GET | `/api/jobs` | Yes | All in-memory jobs for dashboard polling |
| GET | `/api/extraction-report/{job_id}` | Yes | Per-page extraction report (from memory or disk) |
| GET | `/api/results/{job_id}/merged` | Yes | Full merged nested JSON |
| GET | `/api/results/{job_id}/editor` | Yes | Merged JSON + flat lists for editor UI |
| GET | `/api/results/{job_id}/{filename}` | Yes | Single schema JSON file |

### File Serving

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/outputs/{job_id}/pdf` | Yes | Original PDF (inline display) |
| GET | `/outputs/{job_id}/{filename}` | Yes | Download any output file |

### Route Priority (Order Matters)

FastAPI matches routes top-to-bottom. Specific routes must be declared before generic ones:

```
/api/results/{job_id}/merged    ← Matched first (specific)
/api/results/{job_id}/editor    ← Matched second (specific)
/api/results/{job_id}/{filename} ← Matched last (generic catch-all)

/outputs/{job_id}/pdf           ← Matched first (specific)
/outputs/{job_id}/{filename}    ← Matched last (generic catch-all)
```

### Editor API Response Format

```json
{
  "merged": {
    "meta": {...},
    "resource": {
      "modules": [{
        "topics": [{
          "lessons": [{
            "activities": [{
              "tasks": [{
                "stems": [...]
              }]
            }],
            "instructionalPrompts": [...],
            "standards": [...]
          }]
        }]
      }]
    },
    "pages": [...],
    "images": [...]
  },
  "resource": {...},
  "module": {...},
  "topic": {...},
  "lesson": {...},
  "pages": [...],
  "activities": [...],
  "tasks": [...],
  "stems": [...],
  "standards": [...],
  "instructionalPrompts": [...],
  "images": [...],
  "instructionalSegments": [...],
  "practiceSections": [...],
  "responseAreas": [...],
  "scaffolding": [...]
}
```

---

## 12. Frontend Views

### View Architecture

```
results.html
├── Navigation Bar (brand, file count badge, links)
├── Results Header (filename, job ID)
├── View Mode Strip: [ Editor | Source | PDF ]
│
├── Editor View (#view-editor)
│   ├── Dropdown Bar: Module → Resource → Lesson → Page
│   └── Content Area (cards):
│       ├── Resource Card         (schema-tag: resource)
│       ├── Module Card           (schema-tag: module)
│       ├── Topic Card            (schema-tag: topic)
│       ├── Page Card             (schema-tag: page)
│       ├── Lesson Overview Card  (schema-tag: lesson)
│       ├── Learning Goals Card   (schema-tag: learning_goals)
│       ├── Standards Card        (schema-tag: standards)
│       ├── Prompt Cards (×N)     (schema-tag: varies by type)
│       ├── Activities Card       (schema-tag: activities → tasks → stems)
│       │   └── Activity Items
│       │       └── Task Items (with type badges)
│       │           └── Stem Items (with response area badges)
│       │               └── Sub-Task Items
│       └── Images Card           (schema-tag: images)
│
├── Source View (#view-source)
│   ├── Tab Bar: [ ★ Merged | Primitives | Enums | ... 15 tabs ]
│   └── Tab Panels (for each file):
│       ├── Sidebar (filename, size, item count, download link)
│       └── JSON Viewer (syntax highlighted, search, collapse/expand, copy)
│
└── PDF View (#view-pdf)
    └── iframe (lazy-loaded, inline display)
```

### Editor View — Card Rendering

Each section is rendered as a card with a purple schema tag:

```html
┌─────────────────────────────────────────────────────────┐
│  ┌──────────────┐                                       │
│  │ schema-tag   │                         [module]      │
│  └──────────────┘                                       │
│  Module 1                                               │
│  ─────────                                              │
│  Title: Quantities and Relationships                    │
│  ID: 0ad1ddf0-b0f2-445d-a3e5-689225098c85             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Activities (4)                 [activities → tasks → stems] │
│  ─────────────                                          │
│  ┌ ACTIVATE ┐ Ready, Set, Sort!                        │
│  │  • Consider the situation shared by...               │
│  │  ┌ Task ─────────────── SHORT_ANSWER ┐              │
│  │  │  Stem: Consider the situation...   │              │
│  │  │       [TEXT_ONLY]                  │              │
│  │  └────────────────────────────────────┘              │
│  │                                                      │
│  ┌ EXPLORE ┐ Sorting Graphs                            │
│  │  ┌ Task ─────────────── SHORT_ANSWER ┐              │
│  │  │  Stem: Mathematics is the science..│              │
│  │  └────────────────────────────────────┘              │
│  │  ┌ Task ─────────────── OPEN_ENDED ──┐              │
│  │  │  Stem: Record the following...     │              │
│  │  │       [TEXT_WITH_RESPONSE_AREA]     │              │
│  │  │       [OPEN_LINE]                  │              │
│  │  │  Sub-tasks:                        │              │
│  │  │    • Name each group of graphs.    │              │
│  │  │    • List the letters...           │              │
│  │  └────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────┘
```

### Dashboard — Extraction Report

The dashboard's "All Extractions" table includes a **Log** column with a document icon for each completed job that has an extraction report. Clicking the icon opens a modal dialog showing the per-page extraction report:

```
┌─────────────────────────────────────────────────────────────────┐
│  Extraction Report — 3fa85f64…                           [×]   │
│─────────────────────────────────────────────────────────────────│
│  4 pages processed — 3 succeeded, 1 failed                     │
│                                                                 │
│  Page  │ Status │ Page Type        │ Attempts │ Time  │ Details │
│  ──────┼────────┼──────────────────┼──────────┼───────┼──────── │
│  1     │ OK     │ SRB_LESSON_INTRO │ 1        │ 3.2s  │ —       │
│  2     │ OK     │ SRB_LESSON_EXPL  │ 2        │ 14.5s │ •err…   │
│  3     │ OK     │ STANDARDS_PAGE   │ 1        │ 4.1s  │ —       │
│  4     │ FAILED │ UNKNOWN RETRIED  │ 6        │ 82.3s │ •err…   │
└─────────────────────────────────────────────────────────────────┘
```

Report fields:
- **Page**: 1-based page number
- **Status**: `OK` (extracted successfully) or `FAILED` (all retries exhausted)
- **Page Type**: The `page_type` returned by Gemini (e.g. SRB_LESSON_EXPLORE)
- **Attempts**: Total Gemini API calls for this page
- **Time**: Wall-clock time in seconds
- **Details**: Error messages from failed attempts (if any)
- **RETRIED** badge: Shown when the pipeline-level retry was triggered

### Job Status Page — Extraction Report

The job status page shows an expandable "Extraction Report" section once page extraction completes. It contains the same table as the dashboard modal, rendered inline with a toggle to show/hide.

### Source View — JSON Viewer Features

- **Syntax Highlighting**: Keys (cyan), strings (yellow), numbers (purple), booleans (pink), null (gray)
- **Search**: Real-time text search within JSON with yellow highlights
- **Collapse/Expand**: Toggle between compact and pretty-printed
- **Copy**: One-click clipboard copy
- **Size & Count**: Automatic display of file size and item count
- **Lazy Loading**: Panels load JSON only when the tab is first clicked

### PDF View

- **Lazy Loading**: The iframe `src` is set only when the PDF tab is clicked for the first time
- **Inline Display**: Uses `content_disposition_type="inline"` so browsers display the PDF rather than downloading it

---

## 13. Data Flow Diagrams

### Upload → Pipeline → Results

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌────────────┐
│  PDF     │────>│ uploads/ │────>│  pdf2image   │────>│ PNG images │
│  File    │     │ {id}_.pdf│     │  (Poppler)   │     │ (in memory)│
└──────────┘     └──────────┘     └──────────────┘     └──────┬─────┘
                                                              │
                                                    ┌─────────▼─────────┐
                                                    │   Gemini Vision   │
                                                    │   (per page)      │
                                                    │                   │
                                                    │  Image + Prompt   │
                                                    │       → JSON      │
                                                    └─────────┬─────────┘
                                                              │
                                                    ┌─────────▼─────────┐
                                                    │  Raw Page Dicts   │
                                                    │  [{page_number,   │
                                                    │    activities,    │
                                                    │    images, ...}]  │
                                                    └─────────┬─────────┘
                                                              │
                                      ┌───────────────────────▼────────────────────────┐
                                      │              Assembler Service                  │
                                      │                                                │
                                      │  extract_lesson_meta() → shared metadata       │
                                      │  build_standards_chunk() → standards            │
                                      │  build_activities_chunk() → activities+tasks+stems│
                                      │  build_*() × 12 more → remaining entities      │
                                      │  _build_merged_json() → nested hierarchy       │
                                      │                                                │
                                      └───────────────────────┬────────────────────────┘
                                                              │
                                                    ┌─────────▼─────────┐
                                                    │   outputs/{id}/   │
                                                    │                   │
                                                    │  01_primitives         │
                                                    │  02_enums              │
                                                    │  03_resource           │
                                                    │  ...                   │
                                                    │  15_inst_segments      │
                                                    │  16_practice_sections  │
                                                    │  17_response_areas     │
                                                    │  18_scaffolding        │
                                                    │  merged.json           │
                                                    │  extraction_report.json│
                                                    └────────────────────────┘
```

### Editor API Data Flow

```
Browser                    Job Controller                     File System
   │                           │                                   │
   │── GET /api/.../editor ──>│                                   │
   │   (X-Output-Dir header)  │                                   │
   │                          │── _resolve_editor_output() ──────>│
   │                          │   (validate header path OR        │
   │                          │    find output dir by job_id)     │
   │                          │<── output_dir Path ───────────────│
   │                          │                                   │
   │                          │── _read_all_schemas() ───────────>│
   │                          │   (reads all 18 JSON files)       │
   │                          │<── flat dict ─────────────────────│
   │                          │                                   │
   │                          │── _build_merged_json(flat) ──>    │
   │                          │   (nests stems→tasks→activities   │
   │                          │    →lesson→topic→module→resource) │
   │                          │                                   │
   │<── {merged: {...},  ─────│                                   │
   │     resource: {...},     │                                   │
   │     module: {...}, ...}  │                                   │
   │                          │                                   │
   │── Render cards ──>       │                                   │
   │   (JS: renderPageWebView)│                                   │
```

### Output Path Resolution Strategy

```
_resolve_editor_output(request, job_id)
    │
    ├── 1. Check X-Output-Dir header
    │       └── _safe_output_dir_from_header()
    │           ├── Path must exist
    │           ├── Must be under OUTPUT_DIR or BASE_DIR
    │           └── Returns Path or None
    │
    ├── 2. _find_output_dir(job_id)
    │       └── _resolve_output_and_pdf(job_id)
    │           ├── Check job_repo → job.output_dir
    │           ├── Check config.OUTPUT_DIR / job_id
    │           └── Returns (Path, pdf_path) or (None, None)
    │       │
    │       └── Fallback candidates:
    │           ├── BASE_DIR / "outputs" / job_id
    │           ├── OUTPUT_DIR / job_id
    │           └── cwd / "outputs" / job_id
    │
    └── 3. If all fail → HTTPException 404
```

---

## 14. CL-Json-Schema Hierarchy

### Dual Hierarchy System

The CL-Json-Schema defines two parallel hierarchies:

#### Logical Content Hierarchy (What the learner experiences)

```
Resource (Book)
  └── Module (Major unit, e.g., "Module 1")
       └── Topic (Subject area, e.g., "Quantities and Relationships")
            └── Lesson (Instructional session, e.g., "A Sort of Sorts")
                 ├── Activity (Learning experience: ACTIVATE, EXPLORE, REFLECT, PRACTICE)
                 │    └── Task (Question/problem)
                 │         ├── Stem (Individual prompt with optional response area)
                 │         │    ├── Response Area (student input definition)
                 │         │    └── Sub-Tasks (Follow-up questions)
                 │         └── Scaffolding (Hints, character speech bubbles, worked examples)
                 ├── Practice Sections (Groups of PRACTICE activities)
                 ├── Instructional Prompts (Sidebars, callouts, learning goals)
                 ├── Standards (Education standards alignment)
                 └── Standards Blocks (Grouped standards)
```

#### Physical Layout Hierarchy (How content appears in the book)

```
Resource (Book)
  └── Page (Physical page with layout metadata)
       ├── has_sidebar: boolean
       ├── sidebar_position: LEFT_SIDEBAR | RIGHT_SIDEBAR
       ├── column_count: number
       └── content_order: ["activity_1", "image_2", "prompt_1", ...]
```

### Entity Relationship Diagram

```
┌──────────┐ 1   M ┌──────────┐ 1   M ┌──────────┐ 1   M ┌──────────┐
│ Resource │──────>│  Module  │──────>│  Topic   │──────>│  Lesson  │
│          │       │          │       │          │       │          │
│ id       │<──────│ resourceId│<──────│ moduleId │<──────│ topicId  │
│ type     │       │ moduleNum│       │ topicNum │       │ lessonNum│
│ grade    │       │ title    │       │ title    │       │ title    │
│ title    │       │          │       │          │       │ summary  │
└──────────┘       └──────────┘       └──────────┘       │ goals    │
     │ 1                                                  └──────────┘
     │                                                     │ 1     │ 1
     │ M                                                   │       │
┌──────────┐                                        M │    │    M │
│   Page   │                              ┌──────────┐│    │    ┌────────────────┐
│          │                              │ Activity ││    │    │  Instructional │
│ pageNum  │                              │          │┘    │    │  Prompt        │
│ pageType │                              │ actType  │     │    │                │
│ layout   │                              │ title    │     │    │  promptType    │
└──────────┘                              │ tasks[]  │     │    │  title         │
                                          └──────────┘     │    │  content       │
                                           │ 1             │    └────────────────┘
                                           │               │
                                        M │            ┌───┘
                                    ┌──────────┐   ┌──────────────┐
                                    │   Task   │   │  Standards   │
                                    │          │   │  Block       │
                                    │ taskType │   │              │
                                    │ stems[]  │   │ standards[]  │
                                    │ scaff[]  │   └──────────────┘
                                    └──────────┘        │ M
                                     │ 1    │ M     ┌──────────┐
                                     │      │       │ Standard │
                                  M │   ┌────────┐  │ code     │
                                ┌──────┐│Scaffold│  │ fullText │
                                │ Stem ││        │  └──────────┘
                                │      ││ type   │
                                │ type ││ content│
                                │ text │└────────┘
                                │ resp │
                                │ Area │──> Response Area
                                └──────┘    (type, specs)
```

### Activity Types & Flow

```
Lesson Flow:
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ ACTIVATE │───>│ EXPLORE  │───>│ REFLECT  │
  │          │    │          │    │          │
  │ Warm-up  │    │ Main     │    │ Summary  │
  │ activity │    │ learning │    │ Compare  │
  └──────────┘    └──────────┘    └──────────┘

Instructional Segments group activities by phase:
  Segment 1 (ACTIVATE):  [Activity A]
  Segment 2 (EXPLORE):   [Activity B, Activity C]
  Segment 3 (REFLECT):   [Activity D]
```

---

## 15. File-by-File Reference

### `app.py` — Application Factory

| Function | Description |
|----------|-------------|
| `create_app()` | Creates FastAPI instance, adds middleware, mounts static files, includes routers |

### `config.py` — Configuration

| Item | Description |
|------|-------------|
| `Config` class | All env vars as class attributes |
| `config` singleton | Import this everywhere — never use `os.environ` directly |
| `init_dirs()` | Create uploads/ and outputs/ if they don't exist |

### `controllers/auth_controller.py` — Authentication

| Route | Handler | Description |
|-------|---------|-------------|
| `GET /` | `index()` | Redirect based on login state |
| `GET /login` | `login_page()` | Render login form |
| `POST /login` | `login()` | Validate credentials, create session |
| `GET /logout` | `logout()` | Clear session |

### `controllers/job_controller.py` — Job Management

| Function | Type | Description |
|----------|------|-------------|
| `NotAuthenticatedException` | Class | Custom exception for unauthenticated access |
| `require_login()` | Dependency | FastAPI dependency that checks session |
| `_secure_filename()` | Helper | Sanitize uploaded filenames |
| `_resolve_output_and_pdf()` | Helper | Find output dir and PDF path for a job |
| `_job_or_folder_context()` | Helper | Build template context for results page |
| `_find_output_dir()` | Helper | Multi-strategy output directory resolution |
| `_safe_output_dir_from_header()` | Helper | Validate X-Output-Dir header |
| `_resolve_editor_output()` | Helper | Common resolution for editor/merged endpoints |
| `_read_all_schemas()` | Helper | Read all 18 JSON files into flat dict |
| `_build_merged_json()` | Helper | Build nested parent-child JSON |
| `dashboard()` | Route | List all jobs |
| `browse_outputs()` | Route | List output folders for admin |
| `upload_page()` | Route | Render upload form |
| `upload()` | Route | Handle PDF upload, create job, start pipeline |
| `job_monitor()` | Route | Render pipeline monitor page |
| `api_job()` | API | Return job progress for polling (includes extraction_report) |
| `api_jobs()` | API | Return all in-memory jobs for dashboard polling |
| `api_extraction_report()` | API | Return per-page extraction report (from memory or disk) |
| `results()` | Route | Render results viewer |
| `api_merged()` | API | Return merged nested JSON |
| `api_editor_payload()` | API | Return merged + flat data for editor |
| `api_result_file()` | API | Return single JSON file content |
| `serve_job_pdf()` | API | Serve PDF inline |
| `download_output()` | API | Download any output file |

### `services/gemini_service.py` — AI Extraction

| Item | Description |
|------|-------------|
| `MASTER_PROMPT` | Multi-section extraction prompt that defines the JSON structure Gemini must return (including scaffolding) |
| `GeminiService.__init__()` | Configure google-generativeai with API key |
| `health_check()` | Verify API key with minimal generation call |
| `extract_page()` | Send page image + prompt to Gemini, parse JSON, retry on rate limit; returns `(data, report)` tuple |
| `_strip_fences()` | Remove markdown code fences from Gemini response |
| `_is_rate_limit()` | Detect 429/quota errors |
| `_empty_page()` | Fallback empty page structure |

### `services/pipeline_service.py` — Orchestration

| Item | Description |
|------|-------------|
| `PipelineService.start()` | Launch background daemon thread for pipeline |
| `PipelineService._run()` | Execute 5-stage pipeline sequentially |

### `services/assembler.py` — Schema Assembly

| Item | Description |
|------|-------------|
| `assemble_schemas()` | Build and write all 19 files (18 schema + merged) |

### `models/job.py` — Data Model

| Item | Description |
|------|-------------|
| `JobStatus` | String constants for 7 pipeline states |
| `Job` | Dataclass with id, filename, status, progress, logs, extraction_report, etc. |
| `JobRepository` | In-memory dict store with create/get/all methods |
| `job_repo` | Singleton repository instance |

### `utils/file_utils.py` — File Utilities

| Function | Description |
|----------|-------------|
| `is_allowed_file()` | Check if filename has allowed extension |
| `get_pdf_page_count()` | Get PDF page count via pypdf or pdf2image |
| `write_json()` | Write dict as pretty-printed JSON file |
| `read_json()` | Read JSON file into dict |
| `list_output_files()` | List all JSON files in output directory |

### `utils/schema_chunks.py` — Schema Builders

Contains 18+ `build_*()` functions, one per schema file. Also contains:

| Function | Description |
|----------|-------------|
| `gen_id()` | Generate UUID4 string |
| `now_iso()` | Current UTC time as ISO-8601 |
| `extract_lesson_meta()` | Scan all pages for lesson metadata (title, number, goals, etc.) |

---

## 16. Gemini Extraction Prompt

The master prompt sent with each page image instructs Gemini to extract:

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | int | 1-based page index |
| `page_type` | enum | SRB_LESSON_INTRODUCTION, SRB_LESSON_ACTIVATE, SRB_LESSON_EXPLORE, SRB_LESSON_EXPLORE_CONTINUED, SRB_LESSON_REFLECT, SPB_PRACTICE, STANDARDS_PAGE, NON_CONTENT, UNKNOWN |
| `lesson` | object | Lesson metadata (number, title, summary, goals, module/topic info) |
| `standards_block` | object | Standards body, grade level, standard codes + full text |
| `activities[]` | array | Activity type, label, title, direction lines, tasks |
| `activities[].tasks[]` | array | Task number, stem text, response area flags, sub-tasks, scaffolding |
| `images[]` | array | Image type, position, alt text, description, graph details |
| `instructional_prompts[]` | array | Prompt type, display style, title, content, content items |
| `page_layout` | object | Sidebar presence, position, column count, content order |

### Key Prompt Rules

- Return **only valid JSON** — no markdown fences, no explanation
- Use `null` for absent fields, `[]` for absent arrays
- All `id` fields must be empty string `""`
- Math: inline `$...$`, display `$$...$$`
- Preserve exact wording; join multi-line text with `\n`
- For non-content pages: return `page_type: "NON_CONTENT"` with null/empty everything else

---

## 17. Error Handling & Retry Strategy

### Gemini API Retry (per extract_page call)

```
Attempt 1 → API Call
    │
    ├── Success → Parse JSON → Return (data, report{attempts:1, status:"ok"})
    │
    └── Failure
         ├── Rate Limit (429/quota) → Wait 10s → Attempt 2
         │     └── Failure → Wait 20s → Attempt 3
         │           └── Failure → Wait 40s → Attempt 4
         │                 └── Failure → Return (empty_page, report{attempts:4, status:"failed"})
         │
         └── Other Error → Wait 3s → Attempt 2 → ... → Attempt 4 → Return empty page
```

### Pipeline-Level Retry (UNKNOWN page type)

```
extract_page(img, i) → (data, report)
    │
    ├── page_type != "UNKNOWN" → Accept result, append report
    │
    └── page_type == "UNKNOWN"
         └── Wait 5s → extract_page(img, i) again → (retry_data, retry_report)
              ├── retry succeeded → Use retry_data, mark report with pipelineRetry=true
              └── retry still UNKNOWN → Merge attempt counts, mark failed + pipelineRetry=true
```

### Extraction Report

Each page extraction produces a report entry:

| Field | Type | Description |
|-------|------|-------------|
| `page` | int | 1-based page number |
| `attempts` | int | Total Gemini API calls (including retries) |
| `status` | string | `"ok"` or `"failed"` |
| `pageType` | string | Gemini's `page_type` response |
| `errors` | string[] | Error messages from failed attempts |
| `elapsed_ms` | int | Wall-clock time in milliseconds |
| `pipelineRetry` | bool | Present when pipeline-level retry was triggered |

The report is:
- Saved to `extraction_report.json` in the output directory
- Stored on the `Job.extraction_report` field (in-memory)
- Available via `GET /api/extraction-report/{job_id}`
- Displayed in the dashboard modal (Log icon) and job status page (expandable section)

### Pipeline Error Handling

- Each stage wraps in try/except
- On failure: `job.error = str(exc)`, `job.status = "error"`
- Frontend shows error message with pipeline log history
- No automatic retry of the full pipeline — user must re-upload

### Path Resolution Safety

- All file paths resolved to absolute using `Path.resolve()`
- Path traversal prevented via `fpath.relative_to(out_dir)` check
- X-Output-Dir header validated against `OUTPUT_DIR` and `BASE_DIR` boundaries

---

## 18. Security Considerations

| Area | Implementation |
|------|---------------|
| **Authentication** | Session-based with signed cookies (itsdangerous) |
| **Session Expiry** | 14 days maximum |
| **Password Storage** | Plain text in `.env` (suitable for single-admin; use hashing for production) |
| **File Upload** | Extension whitelist (PDF only), size limit (configurable) |
| **Filename Sanitization** | `_secure_filename()` strips Unicode, path separators, special characters |
| **Path Traversal** | `relative_to()` checks on all file-serving routes |
| **API Key** | Stored in session/job; never exposed in API responses |
| **CORS** | Not configured (same-origin only) |
| **Static Files** | Mounted only if directory exists |

---

## 19. Setup & Deployment Guide

### Prerequisites

- Python 3.11+
- Poppler (for PDF rendering)
- Google Gemini API key

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/virendraqbs/idmlExtraction.git
cd idmlExtraction

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Poppler
# macOS:
brew install poppler
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# 5. Create .env file
cat > .env << 'EOF'
SECRET_KEY=change-me-to-a-random-string
FLASK_ENV=development
PORT=5000
ADMIN_USER=admin
ADMIN_PASS=your-password
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
MAX_UPLOAD_MB=100
PDF_RENDER_DPI=200
EOF

# 6. Run the application
python app.py
```

### Accessing the Application

```
http://localhost:5000/login
```

### Production Deployment

```bash
# Run with Uvicorn directly (recommended for production)
uvicorn app:app --host 0.0.0.0 --port 5000 --workers 4

# Or behind a reverse proxy (Nginx, Caddy, etc.)
# Uvicorn handles ASGI; the proxy handles TLS and load balancing
```

---

## 20. Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "Output folder not found" | Output dir path mismatch after restart | Config uses `Path.resolve()` for absolute paths; check `outputs/` exists |
| "Failed to load editor view" | Route ordering bug | Ensure `/editor` and `/merged` routes are declared before `/{filename}` |
| PDF downloads instead of displaying | Missing `content_disposition_type="inline"` | Already fixed in `serve_job_pdf()` |
| "Gemini health check failed" | Invalid API key or quota exhausted | Verify API key; check Google Cloud console for quota |
| Rate limit errors (429) | Too many API calls | Pipeline has built-in 1.5s delay + exponential backoff (10/20/40/60s) + pipeline-level retry for UNKNOWN pages |
| Login redirect loop | Session cookie issues | Clear browser cookies; check `SECRET_KEY` is set |
| Empty extraction results | Non-content pages (TOC, glossary) | Expected — these return `page_type: "NON_CONTENT"` |
| `IndentationError` on startup | Malformed Python | Run `python -m py_compile controllers/job_controller.py` to check |

### Diagnostic Steps

1. **Check server logs**: Uvicorn logs all requests and pipeline progress
2. **Check pipeline logs**: `GET /api/job/{id}` returns last 50 log entries
3. **Check output files**: `ls outputs/{job_id}/` — should have 19+ JSON files (18 schema + merged + extraction_report)
4. **Verify merged.json**: `python -c "import json; json.load(open('outputs/{id}/merged.json'))"` — should parse without errors
5. **Test API directly**: `curl -b cookies.txt http://localhost:5000/api/results/{id}/merged | python -m json.tool`

---

## Appendix: Output File Sizes (Typical)

| File | Typical Size | Description |
|------|-------------|-------------|
| `01_primitives.json` | ~200 B | Just IDs and timestamps |
| `02_enums.json` | ~300 B | Enum values used |
| `03_resource.json` | ~400 B | Book-level entity |
| `04_module.json` | ~300 B | Module entity |
| `05_topic.json` | ~300 B | Topic entity |
| `06_lesson.json` | ~800 B | Lesson with activity refs |
| `07_activities.json` | ~2 KB | Activity details + direction lines |
| `08_tasks.json` | ~1 KB | Task entities |
| `09_stems.json` | ~3 KB | Stem text + sub-tasks |
| `10_standards.json` | ~100 B - 5 KB | Varies by content |
| `11_standards_blocks.json` | ~100 B - 1 KB | Grouped standards |
| `12_images.json` | ~5 KB | Image descriptions + graph details |
| `13_pages.json` | ~2 KB | Page layouts |
| `14_instructional_prompts.json` | ~3 KB | Sidebar/callout content |
| `15_instructional_segments.json` | ~500 B | Phase groupings |
| `16_practice_sections.json` | ~200 B - 1 KB | Practice section entities |
| `17_response_areas.json` | ~100 B - 2 KB | Response area definitions |
| `18_scaffolding.json` | ~100 B - 3 KB | Scaffolding items |
| **`merged.json`** | **~25 KB** | **Full nested hierarchy** |
| `extraction_report.json` | ~1 KB | Per-page extraction report |

---

*This document is auto-maintained. For schema details, see `CL-Json-Schema/SCHEMA_REFERENCE.md`.*
