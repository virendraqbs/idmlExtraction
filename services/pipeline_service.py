"""
services/pipeline_service.py — Pipeline orchestration service.

Runs the 5-stage pipeline in a background thread:
  Stage 1 — Health Check (GeminiService)
  Stage 2 — Render PDF → page images (pdf2image)
  Stage 3 — Page-by-page Gemini extraction
  Stage 4 — Assemble 15 JSON schema files (assembler)
  Stage 5 — Mark job done

Controllers start the pipeline via PipelineService.start(job).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from config import config
from models.job import Job, JobStatus, job_repo
from services.gemini_service import GeminiService
from services.tig_extractor import TIGExtractor
from services.assembler import assemble_schemas
from services.tig_assembler import assemble_tig_schemas
from utils.image_extractor import extract_images_from_pdf
from database import get_module, get_topic

log = logging.getLogger(__name__)


class PipelineService:
    """Starts and manages background pipeline workers."""

    @staticmethod
    def start(job: Job) -> None:
        """Kick off the pipeline for *job* in a daemon thread."""
        t = threading.Thread(
            target=PipelineService._run,
            args=(job.id,),
            daemon=True,
            name=f"pipeline-{job.id[:8]}",
        )
        t.start()

    # ── Private: full pipeline ────────────────────────────────────────────────

    @staticmethod
    def _run(job_id: str) -> None:
        job = job_repo.get(job_id)
        if not job:
            log.error("Job %s not found", job_id)
            return

        def log_it(msg: str) -> None:
            job.log(msg)
            log.info("[%s] %s", job_id[:8], msg)

        try:
            is_tig = (job.book_type or "SRB").upper() == "TIG"

            # ── Stage 1: Health check ─────────────────────────────────────
            job.set_status(JobStatus.HEALTH_CHECK)
            log_it(f"Stage 1: Checking Gemini API health... [mode: {job.book_type}]")

            extractor = TIGExtractor(api_key=job.api_key) if is_tig else GeminiService(api_key=job.api_key)
            extractor.health_check()        # raises RuntimeError on failure
            log_it("Gemini API healthy")

            # ── Stage 2: Render pages ─────────────────────────────────────
            job.set_status(JobStatus.RENDERING)
            log_it(f"Stage 2: Rendering PDF to page images ({config.PDF_RENDER_DPI} DPI)...")

            from pdf2image import convert_from_path
            images = convert_from_path(
                job.pdf_path,
                dpi=config.PDF_RENDER_DPI,
                fmt="PNG",
            )
            total = len(images)
            job.total = total
            log_it(f"Rendered {total} page(s)")

            # ── Stage 2b: Render page images dir (full extraction after Gemini) ──
            out_dir = Path(job.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            # ── Stage 3: Page-by-page extraction ─────────────────────────
            job.set_status(JobStatus.EXTRACTING)
            log_it("Stage 3: Extracting content page-by-page with Gemini 2.5...")

            raw_pages: list[dict] = []
            extraction_report: list[dict] = []

            for i, img in enumerate(images, 1):
                job.current_page = i
                log_it(f"Processing page {i}/{total}...")

                page_data, report = extractor.extract_page(img, i)
                page_data["_pdf_page_index"] = i

                if page_data.get("page_type") == "UNKNOWN" and i <= total:
                    log_it(f"Page {i} returned UNKNOWN — retrying once after delay...")
                    time.sleep(5)
                    retry_data, retry_report = extractor.extract_page(img, i)
                    if retry_data.get("page_type") != "UNKNOWN":
                        retry_data["_pdf_page_index"] = i
                        page_data = retry_data
                        log_it(f"Page {i} retry succeeded: {page_data.get('page_type')}")
                        retry_report["pipelineRetry"] = True
                        report = retry_report
                    else:
                        report["attempts"] += retry_report["attempts"]
                        report["errors"].extend(retry_report["errors"])
                        report["elapsed_ms"] += retry_report["elapsed_ms"]
                        report["pipelineRetry"] = True
                        report["status"] = "failed"

                extraction_report.append(report)
                raw_pages.append(page_data)

                job.pages_done.append(i)
                job.progress = int((i / total) * 85)
                time.sleep(1.5)

            log_it(f"Extracted {total} pages")

            job.extraction_report = extraction_report
            report_path = out_dir / "extraction_report.json"
            with open(report_path, "w", encoding="utf-8") as rp:
                json.dump(extraction_report, rp, indent=2, ensure_ascii=False)
            log_it("Saved extraction_report.json")

            # Save raw extractions for debugging
            raw_output = out_dir / "raw_extractions.json"
            with open(raw_output, "w", encoding="utf-8") as rf:
                json.dump(raw_pages, rf, indent=2, ensure_ascii=False)
            log_it("Saved raw_extractions.json for debugging")

            # ── Stage 4: Assemble schema files ────────────────────────────
            job.set_status(JobStatus.ASSEMBLING)
            job.progress = 90

            # Fetch DB records for selected module/topic (if any)
            db_module = get_module(job.selected_module_id) if job.selected_module_id else None
            db_topic  = get_topic(job.selected_topic_id)   if job.selected_topic_id  else None

            if is_tig:
                log_it("Stage 4: Assembling 5 TIG JSON schema files...")
                schema_files = assemble_tig_schemas(
                    pages=raw_pages,
                    out_dir=out_dir,
                    source_filename=Path(job.pdf_path).name,
                    db_module=db_module,
                    db_topic=db_topic,
                )
            else:
                # ── Stage 3b: Extract images (SRB only) ───────────────────
                log_it("Stage 3b: Extracting print-ready images from PDF...")
                image_manifest = extract_images_from_pdf(
                    job.pdf_path, out_dir, gemini_pages=raw_pages,
                )
                log_it(f"Extracted {image_manifest['total_extracted']} images + {len(image_manifest['page_images'])} page renders")

                log_it("Stage 4: Assembling 19 JSON schema files...")
                schema_files = assemble_schemas(
                    pages=raw_pages,
                    out_dir=out_dir,
                    source_filename=Path(job.pdf_path).name,
                    image_manifest=image_manifest,
                    book_name=job.book_name,
                    module_name=job.module_name,
                    module_subtitle=job.module_subtitle,
                    module_meta=job.module_meta,
                    db_module=db_module,
                    db_topic=db_topic,
                )

            # NEW: build page-entity index in MySQL (post-assembly).
            # Failure here must NOT fail the extraction job — JSON is canonical.
            # Skip for TIG jobs — they don't produce 03_resource.json / 12_images.json
            # (page_indexer would early-return with "missing 03_resource.json").
            try:
                if is_tig:
                    raise RuntimeError("skipped — TIG job (no SRB-shape JSON to index)")
                from services.page_indexer import index_job_pages
                report = index_job_pages(job.id, out_dir)
                log_it(
                    f"Indexed pages: {report.pages}, "
                    f"activities={report.activities}, "
                    f"tasks={report.tasks}, stems={report.stems}, "
                    f"images={report.images}, "
                    f"prompts={report.instructional_prompts}, "
                    f"segments={report.instructional_segments}, "
                    f"practice={report.practice_sections}, "
                    f"scaffolding={report.scaffolding}, "
                    f"response_areas={report.response_areas}, "
                    f"lessons={report.lessons}, "
                    f"skipped={report.skipped_no_source_page}"
                )
                if report.errors:
                    for err in report.errors:
                        log_it(f"page-index warning: {err}")
            except Exception as ix_err:
                log_it(f"page-index failed (non-fatal): {ix_err}")

            # ── Stage 5: Done ─────────────────────────────────────────────
            job.progress     = 100
            job.output_files = schema_files
            job.set_status(JobStatus.DONE)
            log_it(f"Pipeline complete! {len(schema_files)} files written.")

        except Exception as exc:
            job.error = str(exc)
            job.set_status(JobStatus.ERROR)
            log_it(f"Pipeline failed: {exc}")
            log.exception("Pipeline error for job %s", job_id)
