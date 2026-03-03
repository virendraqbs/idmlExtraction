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
from services.assembler import assemble_schemas
from utils.image_extractor import extract_images_from_pdf

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
            # ── Stage 1: Health check ─────────────────────────────────────
            job.set_status(JobStatus.HEALTH_CHECK)
            log_it("Stage 1: Checking Gemini API health...")

            gemini = GeminiService(api_key=job.api_key)
            gemini.health_check()           # raises RuntimeError on failure
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

            # ── Stage 2b: Extract embedded images from PDF ─────────────
            log_it("Stage 2b: Extracting embedded images from PDF...")
            out_dir = Path(job.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            image_manifest = extract_images_from_pdf(job.pdf_path, out_dir)
            log_it(f"Extracted {image_manifest['total_extracted']} embedded images + {len(image_manifest['page_images'])} page renders")

            # ── Stage 3: Page-by-page extraction ─────────────────────────
            job.set_status(JobStatus.EXTRACTING)
            log_it("Stage 3: Extracting content page-by-page with Gemini 2.5...")

            raw_pages: list[dict] = []
            extraction_report: list[dict] = []

            for i, img in enumerate(images, 1):
                job.current_page = i
                log_it(f"Processing page {i}/{total}...")

                page_data, report = gemini.extract_page(img, i)
                page_data["_pdf_page_index"] = i

                if page_data.get("page_type") == "UNKNOWN" and i <= total:
                    log_it(f"Page {i} returned UNKNOWN — retrying once after delay...")
                    time.sleep(5)
                    retry_data, retry_report = gemini.extract_page(img, i)
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
            log_it("Stage 4: Assembling 18 JSON schema files...")
            job.progress = 90

            schema_files = assemble_schemas(
                pages=raw_pages,
                out_dir=out_dir,
                source_filename=Path(job.pdf_path).name,
                image_manifest=image_manifest,
            )

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
