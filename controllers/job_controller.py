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
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from config import config
from database import (
    create_module,
    create_topic,
    get_module,
    get_module_by_title,
    get_module_id_for_topic,
    get_resource_id_for_module,
    get_topic,
    get_topic_by_title,
    link_module_topic,
    link_resource_module,
    list_modules,
    list_modules_for_resource,
    list_resources,
    list_topics,
    list_topics_for_module,
    list_topics_with_module,
    set_topic_module,
    update_module,
    update_topic,
)
from models.job import job_repo
from services.content_output import (
    build_module_schema_json,
    build_topic_schema_json,
    write_module_output,
    write_topic_output,
)
from services.module_extractor import extract_module_from_pdf
from services.pipeline_service import PipelineService
from services.topic_extractor import extract_topic_from_pdf
from utils.file_utils import is_allowed_file, read_json


# ── Auth exception & dependency ───────────────────────────────────────────────

class NotAuthenticatedException(Exception):
    """Raised when a route requires login but the session is not authenticated."""


async def require_login(request: Request):
    if not request.session.get("logged_in"):
        raise NotAuthenticatedException()


jobs_router = APIRouter()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def _parse_module_title_from_filename(filename: str) -> str:
    """e.g. SM5e_A1_SE_MI_M01 1.pdf -> Module 1."""
    base = Path(filename).stem
    m = re.search(r"M(\d{1,2})(?:\s|_|$)", base, re.IGNORECASE)
    if m:
        return f"Module {int(m.group(1))}"
    return base.replace("_", " ").strip() or "Module"


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

def _source_filename_for_folder(folder_id: str) -> str:
    """Resolve display name for the source PDF: from job if available, else from uploads dir."""
    job = job_repo.get(folder_id)
    if job and job.filename and not _looks_like_uuid(job.filename):
        return job.filename
    if config.UPLOAD_DIR.exists():
        prefix = folder_id + "_"
        for f in config.UPLOAD_DIR.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                return f.name[len(prefix):] or ""
    return ""


def _looks_like_uuid(s: str) -> bool:
    if not s or len(s) < 30:
        return False
    s = s.strip().lower()
    if len(s) == 36 and s.count("-") == 4:
        return all(c in "0123456789abcdef-" for c in s)
    return False


def _enrich_folder(p: Path) -> dict:
    """Read page/image counts and source filename from a completed output folder."""
    info: dict = {"id": p.name, "path": str(p), "pages": 0, "images": 0, "files": 0,
                  "status": "Completed", "created": "", "has_report": False, "filename": ""}
    try:
        info["filename"] = _source_filename_for_folder(p.name)
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


def _dashboard_response(request: Request, error: str | None = None, msg: str | None = None):
    """Render dashboard with optional error or success message."""
    jobs = [j.to_dict(include_logs=False) for j in job_repo.all()]
    folders = _scan_output_folders()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "session": request.session,
            "jobs": jobs,
            "folders": folders,
            "error": error,
            "success_msg": msg,
        },
    )


@jobs_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _=Depends(require_login)):
    jobs = [j.to_dict(include_logs=False) for j in job_repo.all()]
    folders = _scan_output_folders()
    error = None
    success_msg = None
    if request.query_params.get("msg") == "module_saved":
        success_msg = "Module saved successfully. Data was extracted from the PDF and stored in the system."
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "session": request.session, "jobs": jobs, "folders": folders, "error": error, "success_msg": success_msg},
    )


@jobs_router.get("/api/topics")
async def api_list_topics(request: Request, _=Depends(require_login)):
    """Return topics: if module_id given, topics for that module; else all topics (id, title, topic_number)."""
    module_id = (request.query_params.get("module_id") or "").strip()
    if module_id:
        topics = list_topics_for_module(module_id)
    else:
        topics = list_topics()
    return JSONResponse(content=[{"id": t["id"], "title": t.get("title") or t["id"], "topic_number": t.get("topic_number")} for t in topics])


@jobs_router.get("/api/modules")
async def api_modules(request: Request, _=Depends(require_login)):
    """Return modules for topic upload. If resource_id given, modules linked to that resource; else all modules."""
    resource_id = (request.query_params.get("resource_id") or "").strip()
    if resource_id:
        modules = list_modules_for_resource(resource_id)
        if not modules:
            modules = list_modules()
    else:
        modules = list_modules()
    return JSONResponse(content=[{"id": m["id"], "title": m.get("title") or m["id"], "module_number": m.get("module_number")} for m in modules])


# ── Module Management ───────────────────────────────────────────────────────────

def _modules_page_context(request: Request, modules: list, error: str | None = None, success_msg: str | None = None):
    resources = list_resources()
    if success_msg is None and request.query_params.get("msg") == "saved":
        success_msg = "Module saved successfully."
    return {
        "request": request,
        "session": request.session,
        "modules": modules,
        "resources": resources,
        "error": error,
        "success_msg": success_msg,
    }


@jobs_router.get("/modules", response_class=HTMLResponse)
async def modules_list(request: Request, _=Depends(require_login)):
    modules = list_modules()
    return templates.TemplateResponse("modules_list.html", _modules_page_context(request, modules))


@jobs_router.get("/modules/add", response_class=HTMLResponse)
async def module_add_redirect(request: Request, _=Depends(require_login)):
    return RedirectResponse(url="/modules", status_code=303)


@jobs_router.post("/modules/add", response_class=HTMLResponse)
async def module_add_submit(
    request: Request,
    pdf_file: UploadFile | None = File(None),
    resource_id: str = Form(""),
    api_key: str = Form(""),
    _=Depends(require_login),
):
    api_key = (api_key or "").strip() or config.GEMINI_API_KEY
    modules = list_modules()
    if not resource_id or not resource_id.strip():
        return templates.TemplateResponse(
            "modules_list.html",
            _modules_page_context(request, modules, error="Please select a resource."),
        )
    if not pdf_file or not pdf_file.filename:
        return templates.TemplateResponse(
            "modules_list.html",
            _modules_page_context(request, modules, error="Please select a PDF file."),
        )
    if not is_allowed_file(pdf_file.filename):
        return templates.TemplateResponse(
            "modules_list.html",
            _modules_page_context(request, modules, error="Please upload a valid PDF file."),
        )
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = _secure_filename(pdf_file.filename)
    temp_path = config.UPLOAD_DIR / f"_module_{filename}"
    try:
        with open(temp_path, "wb") as buf:
            shutil.copyfileobj(pdf_file.file, buf)
        extracted = extract_module_from_pdf(temp_path, api_key=api_key or None, max_pages=5)
        title = (extracted.get("title") or "").strip() or _parse_module_title_from_filename(filename)
        if get_module_by_title(title):
            temp_path.unlink(missing_ok=True)
            return templates.TemplateResponse(
                "modules_list.html",
                _modules_page_context(request, modules, error="Data already exists."),
            )
        mod = create_module(
            title=title,
            module_number=extracted.get("module_number"),
            module_summary=extracted.get("module_summary") or "",
            grade_level=extracted.get("grade_level") or "",
            standards_body=extracted.get("standards_body") or "",
            pdf_path=None,
        )
        pdf_dest = config.UPLOAD_DIR / f"module_{mod['id']}_{filename}"
        shutil.move(str(temp_path), str(pdf_dest))
        update_module(mod["id"], pdf_path=str(pdf_dest))
        if resource_id and resource_id.strip():
            link_resource_module(resource_id.strip(), mod["id"], sequence_number=1)
        res_id = resource_id.strip() if resource_id and resource_id.strip() else str(uuid.uuid4())
        module_json = build_module_schema_json(
            module_id=mod["id"],
            resource_id=res_id,
            module_number=extracted.get("module_number") or 1,
            title=title,
            grade_level=extracted.get("grade_level") or "1",
            module_summary=extracted.get("module_summary") or "",
            standards_body=extracted.get("standards_body"),
        )
        write_module_output(module_json, title)
        return RedirectResponse(url="/modules?msg=saved", status_code=303)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return templates.TemplateResponse(
            "modules_list.html",
            _modules_page_context(request, modules, error=str(e)),
        )


@jobs_router.get("/modules/{module_id}/edit", response_class=HTMLResponse)
async def module_edit_page(request: Request, module_id: str, _=Depends(require_login)):
    mod = get_module(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    return templates.TemplateResponse(
        "module_edit.html",
        {"request": request, "session": request.session, "module": mod},
    )


@jobs_router.post("/modules/{module_id}/edit", response_class=HTMLResponse)
async def module_edit_submit(
    request: Request,
    module_id: str,
    title: str = Form(""),
    module_number: str = Form(""),
    module_summary: str = Form(""),
    grade_level: str = Form(""),
    standards_body: str = Form(""),
    _=Depends(require_login),
):
    mod = get_module(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    num = None
    if module_number.strip():
        try:
            num = int(module_number.strip())
        except ValueError:
            pass
    update_module(
        module_id,
        title=title.strip() or None,
        module_number=num,
        module_summary=module_summary.strip() or None,
        grade_level=grade_level.strip() or None,
        standards_body=standards_body.strip() or None,
    )
    mod = get_module(module_id)
    if mod:
        res_id = get_resource_id_for_module(module_id) or str(uuid.uuid4())
        module_json = build_module_schema_json(
            module_id=module_id,
            resource_id=res_id,
            module_number=mod.get("module_number") or 1,
            title=(mod.get("title") or "").strip() or "Module",
            grade_level=(mod.get("grade_level") or "").strip() or "1",
            module_summary=(mod.get("module_summary") or "").strip() or "",
            standards_body=(mod.get("standards_body") or "").strip() or None,
        )
        write_module_output(module_json, (mod.get("title") or "").strip() or "Module")
    return RedirectResponse(url="/modules?msg=saved", status_code=303)


# ── Topic Management ─────────────────────────────────────────────────────────────

def _topics_page_context(request: Request, topics: list, error: str | None = None, success_msg: str | None = None):
    resources = list_resources()
    if success_msg is None and request.query_params.get("msg") == "saved":
        success_msg = "Topic saved successfully."
    return {
        "request": request,
        "session": request.session,
        "topics": topics,
        "resources": resources,
        "error": error,
        "success_msg": success_msg,
    }


@jobs_router.get("/topics", response_class=HTMLResponse)
async def topics_list(request: Request, _=Depends(require_login)):
    topics = list_topics_with_module()
    return templates.TemplateResponse("topics_list.html", _topics_page_context(request, topics))


@jobs_router.get("/topics/add", response_class=HTMLResponse)
async def topic_add_redirect(request: Request, _=Depends(require_login)):
    return RedirectResponse(url="/topics", status_code=303)


def _parse_topic_title_from_filename(filename: str) -> str:
    base = Path(filename).stem
    m = re.search(r"T(\d{1,2})(?:\s|_|$)", base, re.IGNORECASE)
    if m:
        return f"Topic {int(m.group(1))}"
    return base.replace("_", " ").strip() or "Topic"


def _parse_topic_number_from_filename(filename: str) -> int | None:
    m = re.search(r"T(\d{1,2})(?:\s|_|$)", Path(filename).stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


@jobs_router.post("/topics/add", response_class=HTMLResponse)
async def topic_add_submit(
    request: Request,
    resource_id: str = Form(""),
    module_id: str = Form(""),
    pdf_file: UploadFile | None = File(None),
    title: str = Form(""),
    topic_number: str = Form(""),
    api_key: str = Form(""),
    _=Depends(require_login),
):
    topics = list_topics_with_module()
    if not resource_id or not resource_id.strip():
        return templates.TemplateResponse(
            "topics_list.html",
            _topics_page_context(request, topics, error="Please select a resource."),
        )
    if not module_id or not module_id.strip():
        return templates.TemplateResponse(
            "topics_list.html",
            _topics_page_context(request, topics, error="Please select a module."),
        )
    if not pdf_file or not pdf_file.filename:
        return templates.TemplateResponse(
            "topics_list.html",
            _topics_page_context(request, topics, error="Please select a PDF file."),
        )
    if not is_allowed_file(pdf_file.filename):
        return templates.TemplateResponse(
            "topics_list.html",
            _topics_page_context(request, topics, error="Please upload a valid PDF file."),
        )
    api_key = (api_key or "").strip() or config.GEMINI_API_KEY
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = _secure_filename(pdf_file.filename)
    temp_path = config.UPLOAD_DIR / f"_topic_{filename}"
    try:
        with open(temp_path, "wb") as buf:
            shutil.copyfileobj(pdf_file.file, buf)
        extracted = extract_topic_from_pdf(temp_path, api_key=api_key or None, max_pages=5)
        title_val = (title or "").strip() or (extracted.get("title") or "").strip() or _parse_topic_title_from_filename(filename)
        if get_topic_by_title(title_val):
            temp_path.unlink(missing_ok=True)
            return templates.TemplateResponse(
                "topics_list.html",
                _topics_page_context(request, topics, error="Data already exists."),
            )
        num = extracted.get("topic_number")
        if num is None and (topic_number or "").strip():
            try:
                num = int(topic_number.strip())
            except ValueError:
                num = None
        num = num if num is not None else _parse_topic_number_from_filename(filename) or 1
        topic_summary_val = (extracted.get("topic_summary") or "").strip()
        topic = create_topic(title=title_val, topic_number=num, pdf_path=None)
        pdf_dest = config.UPLOAD_DIR / f"topic_{topic['id']}_{filename}"
        shutil.move(str(temp_path), str(pdf_dest))
        update_topic(topic["id"], pdf_path=str(pdf_dest), topic_summary=topic_summary_val or None)
        set_topic_module(topic["id"], module_id.strip(), sequence_number=1)
        topic_json = build_topic_schema_json(
            topic_id=topic["id"],
            module_id=module_id.strip(),
            topic_number=num,
            title=title_val,
            topic_summary=topic_summary_val,
        )
        write_topic_output(topic_json, title_val)
        return RedirectResponse(url="/topics?msg=saved", status_code=303)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return templates.TemplateResponse(
            "topics_list.html",
            _topics_page_context(request, topics, error=str(e)),
        )


@jobs_router.get("/topics/{topic_id}/edit", response_class=HTMLResponse)
async def topic_edit_page(request: Request, topic_id: str, _=Depends(require_login)):
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    modules = list_modules()
    current_module_id = get_module_id_for_topic(topic_id)
    return templates.TemplateResponse(
        "topic_edit.html",
        {"request": request, "session": request.session, "topic": topic, "modules": modules, "current_module_id": current_module_id or ""},
    )


@jobs_router.post("/topics/{topic_id}/edit", response_class=HTMLResponse)
async def topic_edit_submit(
    request: Request,
    topic_id: str,
    module_id: str = Form(""),
    title: str = Form(""),
    topic_number: str = Form(""),
    topic_summary: str = Form(""),
    _=Depends(require_login),
):
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    num = None
    if (topic_number or "").strip():
        try:
            num = int(topic_number.strip())
        except ValueError:
            pass
    update_topic(
        topic_id,
        title=title.strip() or None,
        topic_number=num,
        topic_summary=topic_summary.strip() or None,
    )
    if module_id and module_id.strip():
        set_topic_module(topic_id, module_id.strip(), sequence_number=1)
    topic = get_topic(topic_id)
    if topic:
        mid = get_module_id_for_topic(topic_id) or module_id.strip() if module_id and module_id.strip() else ""
        if mid:
            topic_json = build_topic_schema_json(
                topic_id=topic_id,
                module_id=mid,
                topic_number=topic.get("topic_number") or 1,
                title=(topic.get("title") or "").strip() or "Topic",
                topic_summary=(topic.get("topic_summary") or "").strip() or "",
            )
            write_topic_output(topic_json, (topic.get("title") or "").strip() or "Topic")
    return RedirectResponse(url="/topics?msg=saved", status_code=303)


@jobs_router.get("/browse", response_class=HTMLResponse)
async def browse_outputs(request: Request, _=Depends(require_login)):
    """List all output folders in a full grid view."""
    folders = _scan_output_folders()
    return templates.TemplateResponse(
        "browse.html",
        {"request": request, "session": request.session, "folders": folders},
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@jobs_router.get("/api/modules")
async def api_list_modules(_=Depends(require_login)):
    """List all modules from cl_module for Topic flow and lesson-upload dropdown."""
    modules = list_modules()
    return JSONResponse(content=[{"id": m["id"], "title": m["title"], "module_number": m["module_number"]} for m in modules])


@jobs_router.get("/api/topics")
async def api_list_topics(request: Request, _=Depends(require_login)):
    """List topics for a module (for lesson-upload Topic dropdown)."""
    module_id = (request.query_params.get("module_id") or "").strip()
    if not module_id:
        return JSONResponse(content=[])
    topics = get_topics_for_module(module_id)
    return JSONResponse(content=[{"id": t["id"], "title": t["title"], "topic_number": t.get("topic_number")} for t in topics])


@jobs_router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _=Depends(require_login)):
    return templates.TemplateResponse("upload.html", {"request": request, "error": None})


@jobs_router.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    pdf_file: UploadFile | None = File(None),
    api_key: str = Form(""),
    upload_type: str = Form(""),
    book_name: str = Form(""),
    module_name: str = Form(""),
    module_subtitle: str = Form(""),
    module_meta: str = Form(""),
    selected_resource_id: str = Form(""),
    selected_resource_title: str = Form(""),
    selected_module_id: str = Form(""),
    selected_module_title: str = Form(""),
    selected_topic_id: str = Form(""),
    selected_topic_title: str = Form(""),
    topic_module_id: str = Form(""),
    _=Depends(require_login),
):
    api_key = api_key.strip() or config.GEMINI_API_KEY
    content_type = (upload_type or "").strip().upper()

    # ── SRB / TIG only (Module/Topic managed in /modules and /topics) ─────────
    if content_type not in ("SRB", "TIG"):
        return _dashboard_response(
            request,
            error="Please select a content type: SRB or TIG.",
        )

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

    # Prefer selected resource/module titles from dropdowns for extraction metadata
    book_name = (book_name or selected_resource_title or "").strip() or None
    module_name = (module_name or selected_module_title or "").strip() or None
    # module_subtitle is the module summary — do NOT source it from selected_topic_title
    # (topic title is a different field; DB will provide topic data via selected_topic_id)
    module_subtitle = module_subtitle.strip() or None

    filename = _secure_filename(pdf_file.filename)
    job = job_repo.create(
        filename=filename,
        pdf_path="",
        api_key=api_key,
        output_dir="",
        book_name=book_name,
        module_name=module_name,
        module_subtitle=module_subtitle,
        module_meta=module_meta.strip() or None,
        selected_module_id=selected_module_id.strip() or None,
        selected_topic_id=selected_topic_id.strip() or None,
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


# ── Module Management ───────────────────────────────────────────────────────

@jobs_router.get("/modules", response_class=HTMLResponse)
async def modules_list(request: Request, _=Depends(require_login)):
    """List all modules with nav."""
    modules = list_modules()
    return templates.TemplateResponse(
        "modules_list.html",
        {"request": request, "session": request.session, "modules": modules},
    )


@jobs_router.get("/modules/add", response_class=HTMLResponse)
async def module_add_page(request: Request, _=Depends(require_login)):
    return templates.TemplateResponse(
        "module_add.html",
        {"request": request, "session": request.session, "error": None},
    )


@jobs_router.post("/modules/add", response_class=HTMLResponse)
async def module_add(
    request: Request,
    pdf_file: UploadFile | None = File(None),
    _=Depends(require_login),
):
    if not pdf_file or not pdf_file.filename or not is_allowed_file(pdf_file.filename):
        return templates.TemplateResponse(
            "module_add.html",
            {"request": request, "session": request.session, "error": "Please upload a valid PDF file."},
        )
    fn = _secure_filename(pdf_file.filename)
    title = (fn or "Untitled").replace(".pdf", "").replace(".PDF", "").strip() or "Untitled"
    mod = create_module(title=title)
    pdf_path = str(config.UPLOAD_DIR / f"module_{mod['id']}_{fn}")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(pdf_path, "wb") as buf:
        shutil.copyfileobj(pdf_file.file, buf)
    update_module(mod["id"], pdf_path=pdf_path)
    return RedirectResponse(url="/modules?msg=added", status_code=303)


@jobs_router.get("/modules/{module_id}/edit", response_class=HTMLResponse)
async def module_edit_page(request: Request, module_id: str, _=Depends(require_login)):
    mod = get_module(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    return templates.TemplateResponse(
        "module_edit.html",
        {"request": request, "session": request.session, "module": mod, "error": None},
    )


@jobs_router.post("/modules/{module_id}/edit", response_class=HTMLResponse)
async def module_edit(
    request: Request,
    module_id: str,
    title: str = Form(""),
    module_number: str = Form(""),
    module_summary: str = Form(""),
    grade_level: str = Form(""),
    standards_body: str = Form(""),
    pdf_file: UploadFile | None = File(None),
    _=Depends(require_login),
):
    mod = get_module(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    num = None
    if module_number.strip():
        try:
            num = int(module_number.strip())
        except ValueError:
            pass
    update_module(
        module_id,
        title=(title or mod["title"] or "").strip() or "Untitled",
        module_number=num,
        module_summary=(module_summary or "").strip(),
        grade_level=(grade_level or "").strip(),
        standards_body=(standards_body or "").strip(),
    )
    if pdf_file and pdf_file.filename and is_allowed_file(pdf_file.filename):
        fn = _secure_filename(pdf_file.filename)
        pdf_path = str(config.UPLOAD_DIR / f"module_{module_id}_{fn}")
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with open(pdf_path, "wb") as buf:
            shutil.copyfileobj(pdf_file.file, buf)
        update_module(module_id, pdf_path=pdf_path)
    return RedirectResponse(url="/modules?msg=updated", status_code=303)


# ── Topic Management ─────────────────────────────────────────────────────────

@jobs_router.get("/topics", response_class=HTMLResponse)
async def topics_list(request: Request, _=Depends(require_login)):
    """List all topics with module title and nav."""
    topics = list_topics()
    return templates.TemplateResponse(
        "topics_list.html",
        {"request": request, "session": request.session, "topics": topics},
    )


@jobs_router.get("/topics/add", response_class=HTMLResponse)
async def topic_add_page(request: Request, _=Depends(require_login)):
    modules = list_modules()
    return templates.TemplateResponse(
        "topic_add.html",
        {"request": request, "session": request.session, "modules": modules, "error": None},
    )


@jobs_router.post("/topics/add", response_class=HTMLResponse)
async def topic_add(
    request: Request,
    module_id: str = Form(""),
    pdf_file: UploadFile | None = File(None),
    _=Depends(require_login),
):
    mod_id = (module_id or "").strip()
    if not mod_id:
        modules = list_modules()
        return templates.TemplateResponse(
            "topic_add.html",
            {"request": request, "session": request.session, "modules": modules, "error": "Please select a module."},
        )
    if not get_module(mod_id):
        modules = list_modules()
        return templates.TemplateResponse(
            "topic_add.html",
            {"request": request, "session": request.session, "modules": modules, "error": "Selected module not found."},
        )
    if not pdf_file or not pdf_file.filename or not is_allowed_file(pdf_file.filename):
        modules = list_modules()
        return templates.TemplateResponse(
            "topic_add.html",
            {"request": request, "session": request.session, "modules": modules, "error": "Please upload a valid PDF file."},
        )
    fn = _secure_filename(pdf_file.filename)
    title = (fn or "Untitled").replace(".pdf", "").replace(".PDF", "").strip() or "Untitled"
    topic = create_topic(title=title)
    link_module_topic(mod_id, topic["id"])
    pdf_path = str(config.UPLOAD_DIR / f"topic_{topic['id']}_{fn}")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(pdf_path, "wb") as buf:
        shutil.copyfileobj(pdf_file.file, buf)
    update_topic_pdf_path(topic["id"], pdf_path)
    return RedirectResponse(url="/topics?msg=added", status_code=303)


@jobs_router.get("/topics/{topic_id}/edit", response_class=HTMLResponse)
async def topic_edit_page(request: Request, topic_id: str, _=Depends(require_login)):
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    modules = list_modules()
    current_module_id = get_module_id_for_topic(topic_id)
    return templates.TemplateResponse(
        "topic_edit.html",
        {
            "request": request,
            "session": request.session,
            "topic": topic,
            "modules": modules,
            "current_module_id": current_module_id or "",
            "error": None,
        },
    )


@jobs_router.post("/topics/{topic_id}/edit", response_class=HTMLResponse)
async def topic_edit(
    request: Request,
    topic_id: str,
    title: str = Form(""),
    topic_number: str = Form(""),
    topic_summary: str = Form(""),
    module_id: str = Form(""),
    pdf_file: UploadFile | None = File(None),
    _=Depends(require_login),
):
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    num = None
    if topic_number.strip():
        try:
            num = int(topic_number.strip())
        except ValueError:
            pass
    update_topic(
        topic_id,
        title=(title or topic.get("title") or "").strip() or "Untitled",
        topic_number=num,
        topic_summary=(topic_summary or "").strip(),
    )
    mod_id = (module_id or "").strip()
    if mod_id and get_module(mod_id):
        link_module_topic(mod_id, topic_id, sequence_number=1)
    if pdf_file and pdf_file.filename and is_allowed_file(pdf_file.filename):
        fn = _secure_filename(pdf_file.filename)
        pdf_path = str(config.UPLOAD_DIR / f"topic_{topic_id}_{fn}")
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with open(pdf_path, "wb") as buf:
            shutil.copyfileobj(pdf_file.file, buf)
        update_topic_pdf_path(topic_id, pdf_path)
    return RedirectResponse(url="/topics?msg=updated", status_code=303)


def _collect_upload_options() -> dict:
    """Scan existing output folders for resource/module metadata to suggest in upload form."""
    book_names: set[str] = set()
    module_names: set[str] = set()
    module_subtitles: set[str] = set()
    module_meta_list: set[str] = set()
    out_dir = config.OUTPUT_DIR
    if not out_dir.exists():
        return {"bookNames": [], "moduleNames": [], "moduleSubtitles": [], "moduleMetaList": []}
    for child in out_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            res_path = child / "03_resource.json"
            if res_path.exists():
                data = read_json(res_path)
                if isinstance(data, dict) and data.get("title"):
                    book_names.add((data.get("title") or "").strip())
            mod_path = child / "04_module.json"
            if mod_path.exists():
                data = read_json(mod_path)
                if isinstance(data, dict):
                    if data.get("title"):
                        module_names.add((data.get("title") or "").strip())
                    meta = data.get("metadata") or {}
                    if meta.get("subtitle"):
                        module_subtitles.add((meta.get("subtitle") or "").strip())
                    if meta.get("userMeta"):
                        module_meta_list.add((meta.get("userMeta") or "").strip())
        except Exception:
            continue
    return {
        "bookNames": sorted(book_names),
        "moduleNames": sorted(module_names),
        "moduleSubtitles": sorted(module_subtitles),
        "moduleMetaList": sorted(module_meta_list),
    }


@jobs_router.get("/api/upload-options")
async def api_upload_options(request: Request, _=Depends(require_login)):
    """Return suggested book/module names from previous extractions for upload form dropdowns."""
    return _collect_upload_options()


def _load_source_structure() -> dict:
    """Return resources from database for dashboard resource dropdown. Modules/topics loaded via /api/modules and /api/topics."""
    resources = list_resources()
    return {"resources": [{"id": r["id"], "title": r.get("title") or r["id"]} for r in resources]}


@jobs_router.get("/api/source-structure")
async def api_source_structure(request: Request, _=Depends(require_login)):
    """Return resources from DB for Extract PDF resource → module → topic selection. Modules/topics loaded per selection."""
    return _load_source_structure()


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


@jobs_router.delete("/api/results/{job_id}/images/{image_id}")
async def delete_image(request: Request, job_id: str, image_id: str, _=Depends(require_login)):
    """Delete an extracted image: remove from 12_images.json, merged.json, and disk."""
    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="Images file not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    img_list = images_data.get("images", [])
    target = None
    remaining = []
    for img in img_list:
        if img.get("id") == image_id:
            target = img
        else:
            remaining.append(img)

    if not target:
        raise HTTPException(status_code=404, detail="Image not found")

    # Remove image file from disk
    img_path = target.get("imagePath")
    if img_path:
        abs_path = (out_dir / img_path).resolve()
        try:
            abs_path.relative_to(out_dir.resolve())
            if abs_path.exists():
                abs_path.unlink()
        except (ValueError, OSError):
            pass

    # Update 12_images.json
    images_data["images"] = remaining
    images_data["count"] = len(remaining)
    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    # Update merged.json if it exists
    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            with open(merged_file, encoding="utf-8") as fh:
                merged = json.load(fh)
            if "images" in merged:
                merged["images"] = [i for i in merged["images"] if i.get("id") != image_id]
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"status": "deleted", "imageId": image_id, "remaining": len(remaining)}


@jobs_router.post("/api/results/{job_id}/images/map")
async def map_image(request: Request, job_id: str, _=Depends(require_login)):
    """Manually map an unmatched extracted image to a Gemini-described image.

    Body: { "geminiImageId": "<id of image with no file>",
            "extractedImageId": "<id of UNREVIEWED image with file>" }

    Merges the extracted image's file path into the Gemini entry and removes
    the UNREVIEWED entry.
    """
    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    body = await request.json()
    gemini_id = body.get("geminiImageId")
    extracted_id = body.get("extractedImageId")
    if not gemini_id or not extracted_id:
        raise HTTPException(status_code=400, detail="Both geminiImageId and extractedImageId are required")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="Images file not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    img_list = images_data.get("images", [])
    gemini_entry = None
    extracted_entry = None
    for img in img_list:
        if img.get("id") == gemini_id:
            gemini_entry = img
        if img.get("id") == extracted_id:
            extracted_entry = img

    if not gemini_entry:
        raise HTTPException(status_code=404, detail="Gemini image not found")
    if not extracted_entry:
        raise HTTPException(status_code=404, detail="Extracted image not found")

    gemini_entry["imagePath"] = extracted_entry.get("imagePath")
    if extracted_entry.get("dimensions"):
        gemini_entry["dimensions"] = extracted_entry["dimensions"]

    remaining = [img for img in img_list if img.get("id") != extracted_id]
    images_data["images"] = remaining
    images_data["count"] = len(remaining)

    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            merged = json.loads(merged_file.read_text(encoding="utf-8"))
            if "images" in merged:
                for mi in merged["images"]:
                    if mi.get("id") == gemini_id:
                        mi["imagePath"] = gemini_entry["imagePath"]
                        if gemini_entry.get("dimensions"):
                            mi["dimensions"] = gemini_entry["dimensions"]
                merged["images"] = [i for i in merged["images"] if i.get("id") != extracted_id]
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {
        "status": "mapped",
        "geminiImageId": gemini_id,
        "extractedImageId": extracted_id,
        "imagePath": gemini_entry["imagePath"],
        "remaining": len(remaining),
    }


@jobs_router.post("/api/results/{job_id}/images/swap")
async def swap_images(request: Request, job_id: str, _=Depends(require_login)):
    """Swap imagePath + dimensions between two image entries.

    Body: { "imageIdA": "<id>", "imageIdB": "<id>" }
    """
    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    body = await request.json()
    id_a = body.get("imageIdA")
    id_b = body.get("imageIdB")
    if not id_a or not id_b:
        raise HTTPException(status_code=400, detail="Both imageIdA and imageIdB are required")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="Images file not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    img_list = images_data.get("images", [])
    entry_a = next((i for i in img_list if i.get("id") == id_a), None)
    entry_b = next((i for i in img_list if i.get("id") == id_b), None)

    if not entry_a:
        raise HTTPException(status_code=404, detail=f"Image {id_a} not found")
    if not entry_b:
        raise HTTPException(status_code=404, detail=f"Image {id_b} not found")

    # Swap imagePath and dimensions
    entry_a["imagePath"], entry_b["imagePath"] = entry_b.get("imagePath"), entry_a.get("imagePath")
    entry_a["dimensions"], entry_b["dimensions"] = entry_b.get("dimensions"), entry_a.get("dimensions")

    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    # Update merged.json
    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            merged = json.loads(merged_file.read_text(encoding="utf-8"))
            if "images" in merged:
                for mi in merged["images"]:
                    if mi.get("id") == id_a:
                        mi["imagePath"] = entry_a.get("imagePath")
                        if entry_a.get("dimensions"):
                            mi["dimensions"] = entry_a["dimensions"]
                        else:
                            mi.pop("dimensions", None)
                    elif mi.get("id") == id_b:
                        mi["imagePath"] = entry_b.get("imagePath")
                        if entry_b.get("dimensions"):
                            mi["dimensions"] = entry_b["dimensions"]
                        else:
                            mi.pop("dimensions", None)
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {
        "status": "swapped",
        "imageIdA": id_a,
        "imageIdB": id_b,
        "imagePathA": entry_a.get("imagePath"),
        "imagePathB": entry_b.get("imagePath"),
    }


@jobs_router.post("/api/results/{job_id}/images/unassign")
async def unassign_image(request: Request, job_id: str, _=Depends(require_login)):
    """Remove only the imagePath from an image entry, keeping all text metadata.

    Body: { "imageId": "<id>" }
    """
    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    body = await request.json()
    image_id = body.get("imageId")
    if not image_id:
        raise HTTPException(status_code=400, detail="imageId is required")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="Images file not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    entry = next((i for i in images_data.get("images", []) if i.get("id") == image_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Image not found")

    entry.pop("imagePath", None)
    entry.pop("dimensions", None)

    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            merged = json.loads(merged_file.read_text(encoding="utf-8"))
            for mi in merged.get("images", []):
                if mi.get("id") == image_id:
                    mi.pop("imagePath", None)
                    mi.pop("dimensions", None)
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"status": "unassigned", "imageId": image_id}


@jobs_router.post("/api/results/{job_id}/images/update-field")
async def update_image_field(request: Request, job_id: str, _=Depends(require_login)):
    """Update a single text field on an image entry.

    Body: { "imageId": "<id>", "field": "altText"|"description", "value": "<new text>" }
    """
    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    body = await request.json()
    image_id = body.get("imageId")
    field = body.get("field")
    value = body.get("value", "")

    ALLOWED_FIELDS = {"altText", "description"}
    if not image_id or field not in ALLOWED_FIELDS:
        raise HTTPException(status_code=400, detail=f"imageId and field ({', '.join(ALLOWED_FIELDS)}) are required")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="Images file not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    entry = next((i for i in images_data.get("images", []) if i.get("id") == image_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Image not found")

    entry[field] = value

    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            merged = json.loads(merged_file.read_text(encoding="utf-8"))
            for mi in merged.get("images", []):
                if mi.get("id") == image_id:
                    mi[field] = value
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"status": "updated", "imageId": image_id, "field": field, "value": value}


@jobs_router.get("/api/gemini/status")
async def api_gemini_status(request: Request, _=Depends(require_login)):
    """Return Gemini API key validity + session usage stats."""
    import google.generativeai as genai

    api_key = config.GEMINI_API_KEY
    key_valid = False
    key_error = None

    if api_key:
        try:
            genai.configure(api_key=api_key)
            # list_models is lightweight — no generation tokens consumed
            list(genai.list_models())
            key_valid = True
        except Exception as exc:
            key_error = str(exc)

    # Aggregate stats from disk (output folders) — survives server restarts
    total_jobs = 0
    pages_extracted = 0
    failed_pages = 0
    rate_limit_hits = 0
    if config.OUTPUT_DIR.exists():
        for p in config.OUTPUT_DIR.iterdir():
            if not p.is_dir():
                continue
            pages_file = p / "13_pages.json"
            report_file = p / "extraction_report.json"
            if not pages_file.exists() and not report_file.exists():
                continue
            total_jobs += 1
            if pages_file.exists():
                try:
                    pages_extracted += read_json(pages_file).get("count", 0)
                except Exception:
                    pass
            if report_file.exists():
                try:
                    report = read_json(report_file)
                    for r in (report if isinstance(report, list) else []):
                        if r.get("status") == "failed":
                            failed_pages += 1
                        for err in r.get("errors", []):
                            if any(k in err.lower() for k in ("429", "rate", "quota", "exhausted")):
                                rate_limit_hits += 1
                                break
                except Exception:
                    pass

    return {
        "configured": bool(api_key),
        "key_valid": key_valid,
        "key_error": key_error,
        "model": config.GEMINI_MODEL,
        "session": {
            "total_jobs": total_jobs,
            "pages_extracted": pages_extracted,
            "failed_pages": failed_pages,
            "rate_limit_hits": rate_limit_hits,
        },
    }


@jobs_router.get("/api/s3/config")
async def api_s3_config(request: Request, _=Depends(require_login)):
    """Return whether S3 is configured (never exposes credentials)."""
    return {"configured": config.s3_configured, "bucket": config.S3_BUCKET if config.s3_configured else ""}


@jobs_router.post("/api/results/{job_id}/images/upload")
async def upload_images_to_s3(request: Request, job_id: str, _=Depends(require_login)):
    """Upload selected images to S3.

    Body: { "imageIds": ["id1", "id2", ...] }

    Returns: { "status": "completed",
               "uploaded": [ { "imageId": "...", "s3Url": "...", "s3Key": "..." }, ... ],
               "errors":   [ { "imageId": "...", "error": "..." }, ... ] }
    """
    if not config.s3_configured:
        raise HTTPException(status_code=503, detail="S3 is not configured. Set AWS credentials and S3_BUCKET in .env.")

    out_dir = _find_output_dir(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    body = await request.json()
    image_ids: list[str] = body.get("imageIds", [])
    if not image_ids:
        raise HTTPException(status_code=400, detail="imageIds must be a non-empty list")

    images_file = out_dir / "12_images.json"
    if not images_file.exists():
        raise HTTPException(status_code=404, detail="12_images.json not found")

    with open(images_file, encoding="utf-8") as fh:
        images_data = json.load(fh)

    img_map = {img["id"]: img for img in images_data.get("images", [])}

    # Build upload batch; skip images without a local file or already uploaded
    batch: list[dict] = []
    skipped: list[dict] = []
    for img_id in image_ids:
        img = img_map.get(img_id)
        if not img:
            skipped.append({"imageId": img_id, "error": "Image ID not found in 12_images.json"})
            continue
        img_path = img.get("imagePath")
        if not img_path:
            skipped.append({"imageId": img_id, "error": "No local file for this image"})
            continue
        if img.get("s3Url"):
            # Already uploaded — skip re-upload
            skipped.append({"imageId": img_id, "error": "Already uploaded", "s3Url": img["s3Url"]})
            continue
        local_path = str((out_dir / img_path).resolve())
        filename = Path(img_path).name
        s3_key = f"{job_id}/images/{filename}"
        batch.append({"imageId": img_id, "localPath": local_path, "s3Key": s3_key, "imagePath": img_path})

    from utils.s3_uploader import S3Uploader
    uploader = S3Uploader()
    uploaded, errors = uploader.upload_batch(batch)

    # Update 12_images.json with s3Url / s3Key for successfully uploaded images
    url_map = {r["imageId"]: r for r in uploaded}
    for img in images_data.get("images", []):
        if img["id"] in url_map:
            img["s3Url"] = url_map[img["id"]]["s3Url"]
            img["s3Key"] = url_map[img["id"]]["s3Key"]
            img["url"] = url_map[img["id"]]["s3Url"]  # schema-compliant url field

    with open(images_file, "w", encoding="utf-8") as fh:
        json.dump(images_data, fh, indent=2, ensure_ascii=False)

    # Update merged.json if it exists
    merged_file = out_dir / "merged.json"
    if merged_file.exists():
        try:
            merged = json.loads(merged_file.read_text(encoding="utf-8"))
            if "images" in merged:
                for mi in merged["images"]:
                    if mi.get("id") in url_map:
                        mi["s3Url"] = url_map[mi["id"]]["s3Url"]
                        mi["s3Key"] = url_map[mi["id"]]["s3Key"]
                        mi["url"] = url_map[mi["id"]]["s3Url"]
            with open(merged_file, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Save s3_uploads.json manifest
    import datetime
    manifest = {
        "jobId": job_id,
        "uploadedAt": datetime.datetime.utcnow().isoformat() + "Z",
        "bucket": config.S3_BUCKET,
        "images": [
            {
                "imageId": r["imageId"],
                "localPath": next((b["imagePath"] for b in batch if b["imageId"] == r["imageId"]), ""),
                "s3Key": r["s3Key"],
                "s3Url": r["s3Url"],
            }
            for r in uploaded
        ],
    }
    existing_manifest_file = out_dir / "s3_uploads.json"
    if existing_manifest_file.exists():
        try:
            existing = json.loads(existing_manifest_file.read_text(encoding="utf-8"))
            existing_ids = {i["imageId"] for i in existing.get("images", [])}
            existing.setdefault("images", []).extend(
                [i for i in manifest["images"] if i["imageId"] not in existing_ids]
            )
            existing["uploadedAt"] = manifest["uploadedAt"]
            manifest = existing
        except Exception:
            pass
    with open(existing_manifest_file, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    return {
        "status": "completed",
        "uploaded": uploaded,
        "errors": errors + skipped,
    }


@jobs_router.post("/api/results/{job_id}/reextract-images")
async def reextract_images(request: Request, job_id: str, _=Depends(require_login)):
    """Re-run image extraction on an existing output using saved raw_extractions.json.

    This re-extracts raster + vector images from the PDF, maps them to Gemini
    alt-text via position matching, and rebuilds 12_images.json + merged.json.
    No Gemini API calls are made.
    """
    out_dir, pdf_path = _resolve_output_and_pdf(job_id)
    if not out_dir:
        raise HTTPException(status_code=404, detail="Output folder not found")

    raw_file = out_dir / "raw_extractions.json"
    if not raw_file.exists():
        raise HTTPException(status_code=404, detail="raw_extractions.json not found")
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Original PDF not found")

    import threading

    def _run():
        from utils.image_extractor import extract_images_from_pdf
        from utils.schema_chunks import build_images_chunk, gen_id

        raw_pages = json.loads(raw_file.read_text(encoding="utf-8"))

        # Re-extract images with enhanced extractor + Gemini mapping
        image_manifest = extract_images_from_pdf(
            pdf_path, out_dir, gemini_pages=raw_pages,
        )

        # Rebuild 12_images.json
        images = build_images_chunk(pages=raw_pages, image_manifest=image_manifest)
        images_data = {"count": len(images), "images": images}
        with open(out_dir / "12_images.json", "w", encoding="utf-8") as fh:
            json.dump(images_data, fh, indent=2, ensure_ascii=False)

        # Update merged.json
        merged_file = out_dir / "merged.json"
        if merged_file.exists():
            try:
                merged = json.loads(merged_file.read_text(encoding="utf-8"))
                merged["images"] = images
                with open(merged_file, "w", encoding="utf-8") as fh:
                    json.dump(merged, fh, indent=2, ensure_ascii=False)
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=60)

    if t.is_alive():
        return {"status": "processing", "message": "Image extraction still running in background"}

    # Read back results
    images_data = json.loads((out_dir / "12_images.json").read_text(encoding="utf-8"))
    total = images_data.get("count", 0)
    with_path = sum(1 for i in images_data.get("images", []) if i.get("imagePath"))
    return {
        "status": "done",
        "totalImages": total,
        "withExtractedFile": with_path,
        "message": f"Re-extracted {with_path} images with files out of {total} total",
    }


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
    """Read all 19 schema files and return as flat dict."""
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
    activity_goals_data = read_json("19_activity_goals.json") or {}

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
        "activityGoals": activity_goals_data.get("goals", []) if isinstance(activity_goals_data, dict) else [],
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
        "activityGoals": flat["activityGoals"],
    }


# ── Content field update ──────────────────────────────────────────────────────

_CONTENT_FILE_MAP: dict[str, tuple[str, str, str | None]] = {
    # fileKey → (filename, mode, list_key)  mode: "single" | "list"
    "lesson":       ("06_lesson.json",                 "single", None),
    "module":       ("04_module.json",                 "single", None),
    "topic":        ("05_topic.json",                  "single", None),
    "activity":     ("07_activities.json",             "list",   "activities"),
    "prompt":       ("14_instructional_prompts.json",  "list",   "instructionalPrompts"),
    "activityGoal": ("19_activity_goals.json",         "list",   "goals"),
}


@jobs_router.post("/api/results/{job_id}/update-content")
async def update_content(request: Request, job_id: str, _=Depends(require_login)):
    """Update text fields in a content entity (lesson, module, topic, activity, prompt, activityGoal)."""
    out = _resolve_editor_output(request, job_id)
    body = await request.json()
    file_key: str = body.get("fileKey", "")
    entity_id: str = body.get("entityId", "")
    fields: dict = body.get("fields", {})

    if file_key not in _CONTENT_FILE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown fileKey: {file_key!r}")
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    fname, mode, list_key = _CONTENT_FILE_MAP[file_key]
    fpath = out / fname
    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"{fname} not found")

    with open(fpath, encoding="utf-8") as fh:
        data = json.load(fh)

    if mode == "single":
        entity = data
    else:
        items: list = data.get(list_key, [])
        entity = next((x for x in items if x.get("id") == entity_id), None)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found in {fname}")

    for k, v in fields.items():
        # directionLines arrives as list[str] from the front-end — convert to objects
        if k == "directionLines" and isinstance(v, list) and v and isinstance(v[0], str):
            v = [{"text": t, "sequenceNumber": i + 1, "directionType": "DIRECTION_LINE"}
                 for i, t in enumerate(v)]
        entity[k] = v

    with open(fpath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    return {"ok": True}


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


# ── Page-locked compare view (added by feat/page-index-db) ────────────────────

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


def _load_entity_dict(out_dir: Path, kind: str) -> dict[str, dict]:
    """Return {id: entity_dict} for the JSON file backing this entity kind."""
    if kind not in _PAGE_KIND_TO_FILE:
        return {}
    fname, key = _PAGE_KIND_TO_FILE[kind]
    p = out_dir / fname
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
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
async def api_results_page(job_id: str, n: int, request: Request,
                           _=Depends(require_login)):
    """Return the composed page payload (cl_page_entity_map rows
    + JSON-hydrated entity bodies) for editor's compare view."""
    out_dir = config.OUTPUT_DIR / job_id
    if not out_dir.is_dir():
        return JSONResponse({"error": "job not found"}, status_code=404)

    from database import get_connection
    conn = get_connection()
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
            meta = json.loads(meta_raw) if meta_raw else {}
        except (json.JSONDecodeError, TypeError):
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

    # Hydrate page-level metadata + contentBlocks from 13_pages.json.
    page_meta: dict = {}
    content_blocks: list = []
    pages_path = out_dir / "13_pages.json"
    if pages_path.exists():
        try:
            pages_doc = json.loads(pages_path.read_text(encoding="utf-8"))
            pages_arr = pages_doc.get("pages") if isinstance(pages_doc, dict) else pages_doc
            if isinstance(pages_arr, list):
                ordinal = page_row["sequence_number"]
                if 1 <= ordinal <= len(pages_arr):
                    p = pages_arr[ordinal - 1]
                    if isinstance(p, dict):
                        page_meta = p.get("metadata") or {}
                        cb = p.get("contentBlocks")
                        if isinstance(cb, list):
                            content_blocks = cb
        except json.JSONDecodeError:
            pass

    return JSONResponse({
        "jobId": job_id,
        "pdfPageIndex": page_row["sequence_number"],
        "pageNumber": page_row["page_number"],
        "pageType": page_row["page_type"],
        "pageMeta": page_meta,
        "contentBlocks": content_blocks,
        "entities": entities,
    })


@jobs_router.post("/api/results/{job_id}/reindex")
async def api_results_reindex(job_id: str, request: Request,
                              _=Depends(require_login)):
    """Re-run services.page_indexer.index_job_pages for one job. Returns
    IndexReport as JSON; 207 if any entity inserts errored, 500 on raise."""
    out_dir = config.OUTPUT_DIR / job_id
    if not out_dir.is_dir():
        return JSONResponse({"error": "job not found"}, status_code=404)

    from services.page_indexer import index_job_pages
    try:
        report = index_job_pages(job_id, out_dir)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    payload = {
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
    }
    # Return 207 Multi-Status when individual entity inserts produced errors.
    status = 207 if report.errors else 200
    return JSONResponse(payload, status_code=status)


