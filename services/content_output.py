"""
services/content_output.py — Build module/topic JSON that match CL-Json-Schema and write to output/modules, output/topics.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import config
from utils.file_utils import write_json


def safe_content_filename(title: str, max_len: int = 120) -> str:
    """Return a filesystem-safe name from a title (no extension)."""
    if not (title or "").strip():
        return "untitled"
    s = re.sub(r"[^\w\s\-]", "", (title or "").strip())
    s = re.sub(r"[\s_]+", "_", s).strip("_")
    return (s[:max_len] if len(s) > max_len else s) or "untitled"


def build_module_schema_json(
    *,
    module_id: str,
    resource_id: str,
    module_number: int,
    title: str,
    grade_level: str,
    module_summary: str = "",
    standards_body: str | None = None,
    topic_refs: list[dict] | None = None,
) -> dict[str, Any]:
    """Build dict matching CL-Json-Schema/schemas/content/module.json. Required: id, moduleNumber, title, gradeLevel."""
    body = standards_body if standards_body in ("CCSS", "CA_CCSS", "TEKS", "BEST") else None
    return {
        "id": module_id,
        "resourceId": resource_id,
        "standardsBody": body,
        "moduleNumber": module_number,
        "title": title,
        "moduleSummary": module_summary or "",
        "images": [],
        "gradeLevel": grade_level or "1",
        "topics": topic_refs or [],
        "metadata": {"localizationInfo": {"language": "en"}},
    }


def build_topic_schema_json(
    *,
    topic_id: str,
    module_id: str,
    topic_number: int,
    title: str,
    topic_summary: str = "",
) -> dict[str, Any]:
    """Build dict matching CL-Json-Schema/schemas/content/topic.json. Required: id, topicNumber, title, moduleId."""
    return {
        "id": topic_id,
        "moduleId": module_id,
        "topicNumber": topic_number,
        "title": title,
        "topicSummary": topic_summary or "",
        "images": [],
        "lessons": [],
        "metadata": {},
    }


def write_module_output(module_json: dict[str, Any], title: str) -> Path:
    """Write module JSON to output/modules/<safe_title>.json. Returns path written."""
    out_dir = config.OUTPUT_DIR / "modules"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = safe_content_filename(title) + ".json"
    path = out_dir / name
    write_json(path, module_json)
    return path


def write_topic_output(topic_json: dict[str, Any], title: str) -> Path:
    """Write topic JSON to output/topics/<safe_title>.json. Returns path written."""
    out_dir = config.OUTPUT_DIR / "topics"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = safe_content_filename(title) + ".json"
    path = out_dir / name
    write_json(path, topic_json)
    return path
