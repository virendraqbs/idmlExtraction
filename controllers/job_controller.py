"""
controllers/job_controller.py — Job management controller.

Routes:
    GET  /dashboard          → list all jobs
    GET  /upload             → upload form
    POST /upload             → save PDF, create job, start pipeline
    GET  /job/{id}           → live monitor page
    GET  /api/job/{id}       → polling API (JSON)
    GET  /results/{id}       → tabbed JSON results viewer
    GET  /api/results/{id}/{file} → serve one result JSON file
    GET  /outputs/{id}/{file}    → download raw output file
"""
from __future__ import annotations

import json
import re
import shutil
import time
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from config import config
from models.job import job_repo
from services.pipeline_service import PipelineService
from utils.file_utils import is_allowed_file


# ── Auth exception & dependency ───────────────────────────────────────────────

class NotAuthenticatedException(Exception):
    """Raised when a route requires login but the session is not authenticated."""


async def require_login(request: Request):
    if not request.session.get("logged_in"):
        raise NotAuthenticatedException()


jobs_router = APIRouter()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def _secure_filename(filename: str) -> str:
    """Sanitise a filename (replaces werkzeug.utils.secure_filename)."""
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")
    filename = filename.replace("/", " ").replace("\\", " ")
    filename = re.sub(r"[^\w\s\-.]", "", filename).strip()
    filename = re.sub(r"[\s]+", "_", filename)
    return filename or "unnamed"


def _resolve_output_and_pdf(job_id: str) -> tuple[Path | None, Path | None]:
    """Resolve output_dir and pdf_path for job_id (from repo or from output folder on disk)."""
    # Use resolve() so we always check absolute paths (avoids cwd-dependent relative paths)
    def abs_path(p: Path) -> Path:
        return p.resolve()

    job = job_repo.get(job_id)
    if job:
        candidates: list[Path] = []
        if job.output_dir:
            candidates.append(abs_path(Path(job.output_dir)))
        candidates.append(abs_path(config.OUTPUT_DIR / job_id))
        for out in candidates:
            if out.exists() and out.is_dir():
                pdf = abs_path(Path(job.pdf_path)) if job.pdf_path else None
                return (out, pdf if (pdf and pdf.exists()) else None)
        return (None, None)

    out_dir = abs_path(config.OUTPUT_DIR / job_id)
    if not out_dir.exists() or not out_dir.is_dir():
        return (None, None)
    # For browse-by-folder: require at least one schema file
    if not (out_dir / "06_lesson.json").exists() and not (out_dir / "01_primitives.json").exists():
        return (None, None)
    pdf_path = None
    if config.UPLOAD_DIR.exists():
        for p in config.UPLOAD_DIR.iterdir():
            if p.name.startswith(job_id + "_") and p.suffix.lower() == ".pdf":
                pdf_path = p
                break
    return (out_dir, pdf_path)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _enrich_folder(p: Path) -> dict:
    """Read page/image counts from a completed output folder."""
    info: dict = {"id": p.name, "path": str(p), "pages": 0, "images": 0, "files": 0,
                  "status": "Completed", "created": "", "has_report": False}
    try:
        info["files"] = sum(1 for f in p.iterdir() if f.suffix == ".json")
        info["created"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
        info["has_report"] = (p / "extraction_report.json").exists()
        pages_file = p / "13_pages.json"
        if pages_file.exists():
            with open(pages_file, encoding="utf-8") as f:
                info["pages"] = json.load(f).get("count", 0)
        images_file = p / "12_images.json"
        if images_file.exists():
            with open(images_file, encoding="utf-8") as f:
                info["images"] = json.load(f).get("count", 0)
    except Exception:
        pass
    return info


def _scan_output_folders() -> list[dict]:
    """Scan the output directory and return enriched folder info, newest first."""
    folders: list[dict] = []
    if config.OUTPUT_DIR.exists():
        for p in sorted(config.OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_dir() and (p / "06_lesson.json").exists():
                folders.append(_enrich_folder(p))
    return folders


@jobs_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _=Depends(require_login)):
    jobs = [j.to_dict(include_logs=False) for j in job_repo.all()]
    folders = _scan_output_folders()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "session": request.session, "jobs": jobs, "folders": folders, "error": None},
    )


@jobs_router.get("/browse", response_class=HTMLResponse)
async def browse_outputs(request: Request, _=Depends(require_login)):
    """List all output folders in a full grid view."""
    folders = _scan_output_folders()
    return templates.TemplateResponse(
        "browse.html",
        {"request": request, "folders": folders},
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@jobs_router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _=Depends(require_login)):
    return templates.TemplateResponse("upload.html", {"request": request, "error": None})


@jobs_router.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    pdf_file: UploadFile | None = File(None),
    api_key: str = Form(""),
    _=Depends(require_login),
):
    api_key = api_key.strip() or config.GEMINI_API_KEY

    if not pdf_file or not pdf_file.filename:
        return templates.TemplateResponse(
            "upload.html", {"request": request, "error": "No file selected."}
        )
    if not is_allowed_file(pdf_file.filename):
        return templates.TemplateResponse(
            "upload.html", {"request": request, "error": "Please upload a valid PDF file."}
        )
    if not api_key:
        return templates.TemplateResponse(
            "upload.html", {"request": request, "error": "Gemini API key is required."}
        )

    filename = _secure_filename(pdf_file.filename)
    job = job_repo.create(
        filename=filename,
        pdf_path="",
        api_key=api_key,
        output_dir="",
    )

    pdf_path = config.UPLOAD_DIR / f"{job.id}_{filename}"
    out_dir = config.OUTPUT_DIR / job.id
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(pdf_path, "wb") as buf:
        shutil.copyfileobj(pdf_file.file, buf)

    job.pdf_path = str(pdf_path)
    job.output_dir = str(out_dir)

    PipelineService.start(job)

    return RedirectResponse(url="/dashboard", status_code=303)


# ── Job monitor ───────────────────────────────────────────────────────────────

@jobs_router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_monitor(request: Request, job_id: str, _=Depends(require_login)):
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        "job_status.html", {"request": request, "job": job.to_dict()}
    )


@jobs_router.get("/api/job/{job_id}")
async def api_job(request: Request, job_id: str, _=Depends(require_login)):
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="not found")
    return job.to_api_dict()


@jobs_router.get("/api/jobs")
async def api_jobs(request: Request, _=Depends(require_login)):
    """Return all in-memory jobs (active + recently completed) for dashboard polling."""
    return [j.to_api_dict() | {"id": j.id} for j in job_repo.all()]


@jobs_router.get("/api/extraction-report/{job_id}")
async def api_extraction_report(request: Request, job_id: str, _=Depends(require_login)):
    """Return the per-page extraction report for a completed job."""
    job = job_repo.get(job_id)
    if job and job.extraction_report:
        return job.extraction_report

    out_dir, _ = _resolve_output_and_pdf(job_id)
    if out_dir:
        report_file = out_dir / "extraction_report.json"
        if report_file.exists():
            return json.loads(report_file.read_text(encoding="utf-8"))

    return []


# ── Results viewer ────────────────────────────────────────────────────────────

def _job_or_folder_context(job_id: str):
    """Resolve job from repo or from output folder on disk (for admin browse)."""
    job = job_repo.get(job_id)
    if job:
        if job.status != "done":
            return None
        d = job.to_dict()
        # Ensure output_dir in context points to an existing path (for editor API X-Output-Dir)
        out_candidates = []
        if job.output_dir:
            out_candidates.append(Path(job.output_dir))
        out_candidates.append(config.OUTPUT_DIR / job_id)
        for p in out_candidates:
            try:
                p = p.resolve()
                if p.exists() and p.is_dir():
                    d["output_dir"] = str(p)
                    return d
            except (OSError, RuntimeError):
                continue
        # Job is done but no output dir found; still return context but editor may 404
        return d
    out_dir = config.OUTPUT_DIR / job_id
    if not out_dir.is_dir():
        return None
    if not (out_dir / "06_lesson.json").exists():
        return None
    output_files = [p.name for p in out_dir.iterdir() if p.suffix == ".json"]
    # Try to find PDF in uploads for this folder (optional)
    pdf_path = ""
    if config.UPLOAD_DIR.exists():
        for p in config.UPLOAD_DIR.iterdir():
            if p.name.startswith(job_id + "_") and p.suffix.lower() == ".pdf":
                pdf_path = str(p)
                break
    return {
        "id": job_id,
        "filename": job_id,
        "pdf_path": pdf_path,
        "output_dir": str(out_dir),
        "status": "done",
        "output_files": sorted(output_files),
    }


@jobs_router.get("/results/{job_id}", response_class=HTMLResponse)
async def results(request: Request, job_id: str, _=Depends(require_login)):
    ctx = _job_or_folder_context(job_id)
    if not ctx:
        job = job_repo.get(job_id)
        if job and job.status != "done":
            return RedirectResponse(url=f"/job/{job_id}", status_code=303)
        raise HTTPException(status_code=404, detail="Job or output folder not found")
    return templates.TemplateResponse(
        "results.html", {"request": request, "job": ctx}
    )


# ── Editor view API — MUST be before the generic /api/results/{job_id}/{filename} route ──

def _find_output_dir(job_id: str) -> Path | None:
    """Return the output directory for job_id, trying multiple resolution strategies."""
    out, _ = _resolve_output_and_pdf(job_id)
    if out:
        return out
    candidates = [
        (config.BASE_DIR / "outputs" / job_id).resolve(),
        (config.OUTPUT_DIR / job_id).resolve(),
        (Path.cwd() / "outputs" / job_id).resolve(),
    ]
    for p in candidates:
        if p.exists() and p.is_dir() and (p / "06_lesson.json").exists():
            return p
    return None


def _safe_output_dir_from_header(header_path: str | None, job_id: str) -> Path | None:
    """If X-Output-Dir is set and points under our OUTPUT_DIR/BASE_DIR, return it as Path."""
    if not header_path or not header_path.strip():
        return None
    try:
        p = Path(header_path.strip()).resolve()
    except (OSError, RuntimeError):
        return None
    if not p.exists() or not p.is_dir():
        return None
    try:
        p.relative_to(config.OUTPUT_DIR.resolve())
        return p
    except ValueError:
        pass
    try:
        p.relative_to(config.BASE_DIR.resolve())
        return p
    except ValueError:
        pass
    return None


def _resolve_editor_output(request: Request, job_id: str) -> Path:
    """Common output dir resolution for editor/merged endpoints."""
    out = None
    x_output_dir = request.headers.get("x-output-dir")
    if x_output_dir:
        out = _safe_output_dir_from_header(x_output_dir, job_id)
    if not out:
        out = _find_output_dir(job_id)
    if not out:
        raise HTTPException(status_code=404, detail="Output folder not found. Run extraction first.")
    return out


def _read_all_schemas(out: Path) -> dict:
    """Read all 18 schema files and return as flat dict."""
    def read_json(name: str) -> dict | list:
        p = out / name
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)

    primitives = read_json("01_primitives.json")
    enums = read_json("02_enums.json")
    resource = read_json("03_resource.json") or {}
    module = read_json("04_module.json") or {}
    topic = read_json("05_topic.json") or {}
    lesson = read_json("06_lesson.json") or {}
    activities_data = read_json("07_activities.json") or {}
    tasks_data = read_json("08_tasks.json") or {}
    stems_data = read_json("09_stems.json") or {}
    standards_data = read_json("10_standards.json") or {}
    std_blocks_data = read_json("11_standards_blocks.json") or {}
    images_data = read_json("12_images.json") or {}
    pages_data = read_json("13_pages.json") or {}
    prompts_data = read_json("14_instructional_prompts.json") or {}
    segments_data = read_json("15_instructional_segments.json") or {}
    practice_data = read_json("16_practice_sections.json") or {}
    resp_areas_data = read_json("17_response_areas.json") or {}
    scaffolding_data = read_json("18_scaffolding.json") or {}

    return {
        "primitives": primitives if isinstance(primitives, dict) else {},
        "enums": enums if isinstance(enums, dict) else {},
        "resource": resource if isinstance(resource, dict) else {},
        "module": module if isinstance(module, dict) else {},
        "topic": topic if isinstance(topic, dict) else {},
        "lesson": lesson if isinstance(lesson, dict) else {},
        "activities": activities_data.get("activities", []) if isinstance(activities_data, dict) else [],
        "tasks": tasks_data.get("tasks", []) if isinstance(tasks_data, dict) else [],
        "stems": stems_data.get("stems", []) if isinstance(stems_data, dict) else [],
        "standards": standards_data.get("standards", []) if isinstance(standards_data, dict) else [],
        "standardsBlocks": std_blocks_data.get("standardsBlocks", []) if isinstance(std_blocks_data, dict) else [],
        "images": images_data.get("images", []) if isinstance(images_data, dict) else [],
        "pages": pages_data.get("pages", []) if isinstance(pages_data, dict) else [],
        "instructionalPrompts": prompts_data.get("instructionalPrompts", []) if isinstance(prompts_data, dict) else [],
        "instructionalSegments": segments_data.get("instructionalSegments", []) if isinstance(segments_data, dict) else [],
        "practiceSections": practice_data.get("practiceSections", []) if isinstance(practice_data, dict) else [],
        "responseAreas": resp_areas_data.get("responseAreas", []) if isinstance(resp_areas_data, dict) else [],
        "scaffolding": scaffolding_data.get("scaffolding", []) if isinstance(scaffolding_data, dict) else [],
    }


def _build_merged_json(flat: dict) -> dict:
    """
    Build a single nested JSON following the parent-child hierarchy:
    Resource → Module[] → Topic[] → Lesson[] → Activity[] → Task[] → Stem[]
    with pages, standards, images, prompts at appropriate levels.
    """
    stems_by_task: dict[str, list] = {}
    for s in flat["stems"]:
        stems_by_task.setdefault(s.get("taskId", ""), []).append(s)

    tasks_by_activity: dict[str, list] = {}
    for t in flat["tasks"]:
        tid = t["id"]
        t_nested = {**t, "stems": stems_by_task.get(tid, [])}
        tasks_by_activity.setdefault(t.get("activityId", ""), []).append(t_nested)

    activities_by_lesson: dict[str, list] = {}
    for a in flat["activities"]:
        aid = a["id"]
        a_nested = {**a, "tasks": tasks_by_activity.get(aid, [])}
        activities_by_lesson.setdefault(a.get("lessonId", ""), []).append(a_nested)

    lesson = flat["lesson"]
    lid = lesson.get("id", "")
    lesson_nested = {
        **lesson,
        "activities": activities_by_lesson.get(lid, []),
        "instructionalPrompts": [p for p in flat["instructionalPrompts"]
                                  if p.get("studentContentReferenceId") == lid],
        "standards": flat["standards"],
        "standardsBlocks": flat["standardsBlocks"],
    }

    topic = flat["topic"]
    topic_nested = {
        **topic,
        "lessons": [lesson_nested],
    }

    module = flat["module"]
    module_nested = {
        **module,
        "topics": [topic_nested],
    }

    resource = flat["resource"]
    resource_nested = {
        **resource,
        "modules": [module_nested],
    }

    return {
        "meta": flat["primitives"],
        "enums": flat["enums"],
        "resource": resource_nested,
        "pages": flat["pages"],
        "images": flat["images"],
        "instructionalSegments": flat["instructionalSegments"],
    }


@jobs_router.get("/api/results/{job_id}/merged")
async def api_merged(request: Request, job_id: str, _=Depends(require_login)):
    """Return all 15 schemas merged into a single nested JSON (parent-child hierarchy)."""
    out = _resolve_editor_output(request, job_id)
    flat = _read_all_schemas(out)
    return _build_merged_json(flat)


@jobs_router.get("/api/results/{job_id}/editor")
async def api_editor_payload(request: Request, job_id: str, _=Depends(require_login)):
    """Return full hierarchy and content for Editor view."""
    out = _resolve_editor_output(request, job_id)
    flat = _read_all_schemas(out)
    merged = _build_merged_json(flat)

    # Editor needs the flat lists too for the dropdowns / quick access
    return {
        "merged": merged,
        "resource": flat["resource"],
        "module": flat["module"],
        "topic": flat["topic"],
        "lesson": flat["lesson"],
        "pages": flat["pages"],
        "standards": flat["standards"],
        "standardsBlocks": flat["standardsBlocks"],
        "instructionalPrompts": flat["instructionalPrompts"],
        "activities": flat["activities"],
        "tasks": flat["tasks"],
        "stems": flat["stems"],
        "images": flat["images"],
        "instructionalSegments": flat["instructionalSegments"],
    }


# ── Generic result file API (after /editor so it doesn't shadow it) ───────────

@jobs_router.get("/api/results/{job_id}/{filename}")
async def api_result_file(
    request: Request, job_id: str, filename: str, _=Depends(require_login)
):
    out_dir, _ = _resolve_output_and_pdf(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="not found")
    fpath = (out_dir / filename).resolve()
    try:
        fpath.relative_to(out_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="file not found")
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="file not found")
    with open(fpath, encoding="utf-8") as fh:
        return json.load(fh)


@jobs_router.get("/outputs/{job_id}/page_images/{page_num}.png")
async def serve_page_image(
    request: Request, job_id: str, page_num: int, _=Depends(require_login)
):
    """Render a single PDF page as PNG, cache it inside outputs/{job_id}/page_images/."""
    out_dir, pdf_path = _resolve_output_and_pdf(job_id)
    if not out_dir or not out_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")
    cache_dir = out_dir / "page_images"
    cache_dir.mkdir(exist_ok=True)
    cached = cache_dir / f"page_{page_num}.png"
    if not cached.exists():
        if not pdf_path or not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")
        from pdf2image import convert_from_path

        imgs = convert_from_path(
            str(pdf_path), dpi=150, first_page=page_num, last_page=page_num, fmt="PNG",
        )
        if not imgs:
            raise HTTPException(status_code=404, detail="Page not found")
        imgs[0].save(str(cached), "PNG")
    return FileResponse(
        path=str(cached), media_type="image/png",
        filename=f"page_{page_num}.png",
    )


# PDF must be declared before the generic outputs route so /outputs/{id}/pdf is matched
@jobs_router.get("/outputs/{job_id}/pdf")
async def serve_job_pdf(request: Request, job_id: str, _=Depends(require_login)):
    """Serve the original uploaded PDF for this job (PDF view tab)."""
    _, pdf_path = _resolve_output_and_pdf(job_id)
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


@jobs_router.get("/outputs/{job_id}/{filename:path}")
async def download_output(
    request: Request, job_id: str, filename: str, _=Depends(require_login)
):
    out_dir, _ = _resolve_output_and_pdf(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Not found")
    fpath = (out_dir / filename).resolve()
    out_resolved = out_dir.resolve()
    try:
        fpath.relative_to(out_resolved)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(fpath), filename=Path(filename).name)


