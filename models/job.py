"""
models/job.py — Job model and in-memory store.

In production, swap the dict store for a database-backed repository
without changing any controller or service code.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ── Job statuses ─────────────────────────────────────────────────────────────
class JobStatus:
    QUEUED       = "queued"
    HEALTH_CHECK = "health_check"
    RENDERING    = "rendering"
    EXTRACTING   = "extracting"
    ASSEMBLING   = "assembling"
    DONE         = "done"
    ERROR        = "error"


@dataclass
class Job:
    """Represents one PDF-extraction pipeline run."""
    id:           str
    filename:     str
    pdf_path:     str
    api_key:      str
    output_dir:   str
    status:       str         = JobStatus.QUEUED
    progress:     int         = 0
    total:        int         = 0
    current_page: int         = 0
    pages_done:   list[int]   = field(default_factory=list)
    logs:         list[str]   = field(default_factory=list)
    output_files: list[str]   = field(default_factory=list)
    extraction_report: list[dict] = field(default_factory=list)
    error:        Optional[str] = None
    started_at:   float       = field(default_factory=time.time)
    # Optional user-provided metadata at upload (overrides extraction when set)
    book_name:    Optional[str] = None
    module_name:  Optional[str] = None
    module_subtitle: Optional[str] = None
    module_meta:  Optional[str] = None
    # DB IDs selected from dropdowns — used to pull module/topic from database
    selected_module_id: Optional[str] = None
    selected_topic_id:  Optional[str] = None
    # Extraction mode: "SRB" (student resource book) or "TIG" (teacher implementation guide)
    book_type: str = "SRB"

    # ── Helpers ───────────────────────────────────────────────────────────────
    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def set_status(self, status: str) -> None:
        self.status = status

    def to_dict(self, include_logs: bool = True) -> dict:
        d = {
            "id":           self.id,
            "filename":     self.filename,
            "pdf_path":     self.pdf_path,
            "output_dir":   self.output_dir,
            "status":       self.status,
            "progress":     self.progress,
            "total":        self.total,
            "current_page": self.current_page,
            "pages_done":   self.pages_done,
            "output_files": self.output_files,
            "extraction_report": self.extraction_report,
            "error":        self.error,
            "started_at":   self.started_at,
            "book_type":    self.book_type,
        }
        if include_logs:
            d["logs"] = self.logs
        return d

    def to_api_dict(self) -> dict:
        """Slim dict for the polling API — last 50 logs only."""
        return {
            "status":       self.status,
            "progress":     self.progress,
            "total":        self.total,
            "current_page": self.current_page,
            "pages_done":   self.pages_done,
            "logs":         self.logs[-50:],
            "output_files": self.output_files,
            "extraction_report": self.extraction_report,
            "error":        self.error,
            "filename":     self.filename,
            "book_type":    self.book_type,
        }


# ── In-memory repository ──────────────────────────────────────────────────────

class JobRepository:
    """Simple in-memory store.  Replace with SQLite/Redis for persistence."""

    def __init__(self) -> None:
        self._store: dict[str, Job] = {}

    def create(
        self,
        filename: str,
        pdf_path: str,
        api_key: str,
        output_dir: str,
        book_name: Optional[str] = None,
        module_name: Optional[str] = None,
        module_subtitle: Optional[str] = None,
        module_meta: Optional[str] = None,
        selected_module_id: Optional[str] = None,
        selected_topic_id: Optional[str] = None,
        book_type: str = "SRB",
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            filename=filename,
            pdf_path=pdf_path,
            api_key=api_key,
            output_dir=output_dir,
            book_name=book_name or None,
            module_name=module_name or None,
            module_subtitle=module_subtitle or None,
            module_meta=module_meta or None,
            selected_module_id=selected_module_id or None,
            selected_topic_id=selected_topic_id or None,
            book_type=book_type if book_type in ("SRB", "TIG") else "SRB",
        )
        self._store[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._store.get(job_id)

    def all(self) -> list[Job]:
        return sorted(self._store.values(), key=lambda j: j.started_at, reverse=True)


# Singleton — import this everywhere.
job_repo = JobRepository()
