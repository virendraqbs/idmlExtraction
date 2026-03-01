# CL Pipeline — MVC Edition

PDF → Gemini 2.5 → 15 CL-Schema JSON files, restructured as a clean MVC FastAPI application.

---

## Project Structure

```
cl-pipeline-mvc/
│
├── app.py                          ← Application factory (entry point)
├── config.py                       ← Central config — reads .env ONCE
├── .env                            ← Credentials & settings (never commit)
├── .env.example                    ← Safe template to commit
├── .gitignore
├── requirements.txt
│
├── controllers/                    ── VIEW layer (routes → templates)
│   ├── auth_controller.py          ← Login / logout
│   └── job_controller.py           ← Upload, dashboard, monitor, results
│
├── models/                         ── MODEL layer (data + repository)
│   └── job.py                      ← Job dataclass + JobRepository (in-memory)
│
├── services/                       ── BUSINESS LOGIC
│   ├── gemini_service.py           ← Gemini API: health check + page extraction
│   ├── assembler.py                ← Calls schema_chunks, writes 15 JSON files
│   └── pipeline_service.py         ← Orchestrates the 5-stage pipeline in a thread
│
├── utils/                          ── UTILITIES
│   ├── file_utils.py               ← File I/O helpers (allowed_file, write_json …)
│   └── schema_chunks.py            ← ★ One build_*() function per JSON file
│
└── templates/                      ← Jinja2 templates
    ├── login.html
    ├── dashboard.html
    ├── upload.html
    ├── job_status.html
    └── results.html
```

---

## Setup

### 1. Create virtual environment & install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt

# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils
```

### 2. Configure `.env`
```bash
cp .env.example .env
# Edit .env — fill in SECRET_KEY, ADMIN_USER, ADMIN_PASS, GEMINI_API_KEY
```

`.env` fields:
```
SECRET_KEY=change-me-in-production
FLASK_ENV=development
PORT=5000

ADMIN_USER=admin
ADMIN_PASS=your-secure-password

GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

MAX_UPLOAD_MB=100
PDF_RENDER_DPI=200
```

### 3. Run
```bash
python app.py
# → http://localhost:5000
```

Or directly with Uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 5000 --reload
```

---

## MVC Responsibilities

| Layer | File(s) | Responsibility |
|---|---|---|
| **Controller** | `controllers/auth_controller.py` | Login / logout / session |
| **Controller** | `controllers/job_controller.py` | Routes for upload, monitor, results |
| **Model** | `models/job.py` | `Job` dataclass + `JobRepository` store |
| **Service** | `services/gemini_service.py` | Gemini Vision API wrapper |
| **Service** | `services/assembler.py` | Calls chunk helpers, writes JSON files |
| **Service** | `services/pipeline_service.py` | Background thread, stages 1–5 |
| **Utility** | `utils/file_utils.py` | Stateless file I/O helpers |
| **Utility** | `utils/schema_chunks.py` | One `build_*()` per JSON schema file |
| **Config** | `config.py` | `.env` loaded once; `config` singleton |

---

## Schema Chunk Helpers (`utils/schema_chunks.py`)

Each function is **isolated, testable, and maps 1-to-1 with an output file**:

| Function | Output file |
|---|---|
| `build_primitives()` | `01_primitives.json` |
| `build_enums()` | `02_enums.json` |
| `build_resource()` | `03_resource.json` |
| `build_module()` | `04_module.json` |
| `build_topic()` | `05_topic.json` |
| `build_lesson()` | `06_lesson.json` |
| `build_activities_chunk()` | `07_activities.json` + side-produces tasks/stems |
| `build_task()` | Used inside `build_activities_chunk` |
| `build_stem()` | Used inside `build_activities_chunk` |
| `build_standards_chunk()` | `10_standards.json` |
| `build_standards_blocks()` | `11_standards_blocks.json` |
| `build_images_chunk()` | `12_images.json` |
| `build_pages_chunk()` | `13_pages.json` |
| `build_instructional_prompts_chunk()` | `14_instructional_prompts.json` |
| `build_instructional_segments()` | `15_instructional_segments.json` |

The `assembler.py` calls them in dependency order and writes all 15 files.

---

## Pipeline Stages

| Stage | Status key | What happens |
|---|---|---|
| 1 | `health_check` | Ping Gemini API — fast sanity check |
| 2 | `rendering` | `pdf2image` renders all pages at `PDF_RENDER_DPI` DPI |
| 3 | `extracting` | One `GeminiService.extract_page()` call per page; 429 → exponential backoff |
| 4 | `assembling` | `assembler.assemble_schemas()` calls all chunk helpers and writes 15 files |
| 5 | `done` | Job marked complete; results available in tabbed viewer |
