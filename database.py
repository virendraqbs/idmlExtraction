"""
database.py — MySQL persistence for cl_module, cl_topic, and module–topic mapping.
Uses database cl_json_schema; table definitions come from cl_json_schema.sql.
This module only adds optional pdf_path columns if missing and uses existing tables.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from config import config


def get_connection():
    """Return a MySQL connection using config (cl_json_schema, root, etc.)."""
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def _row_to_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert datetime/date in row to ISO strings for JSON/template use."""
    if row is None:
        return None
    out = dict(row)
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%dT%H:%M:%S")
        elif isinstance(v, date):
            out[k] = v.strftime("%Y-%m-%d")
    return out


def init_db() -> None:
    """
    Assume tables exist from cl_json_schema.sql. Optionally add pdf_path
    to cl_module and cl_topic if missing (for app upload storage).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for table, col in (("cl_module", "pdf_path"), ("cl_topic", "pdf_path")):
                try:
                    cur.execute(
                        f"ALTER TABLE `{table}` ADD COLUMN `{col}` VARCHAR(1024) NULL DEFAULT NULL"
                    )
                    conn.commit()
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1060:  # Duplicate column name
                        raise
                    conn.rollback()
    finally:
        conn.close()


def create_module(
    *,
    title: str,
    module_number: int | None = None,
    module_summary: str = "",
    grade_level: str = "",
    standards_body: str = "",
    pdf_path: str | None = None,
) -> dict[str, Any]:
    """Insert a module into cl_module. Returns the created row as dict."""
    uid = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cl_module
                   (id, module_number, title, module_summary, grade_level, standards_body, pdf_path)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    uid,
                    module_number,
                    (title or "").strip() or None,
                    (module_summary or "").strip() or None,
                    (grade_level or "").strip() or None,
                    (standards_body or "").strip() or None,
                    pdf_path,
                ),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_module WHERE id = %s", (uid,))
            row = cur.fetchone()
            return _row_to_dict(row) or {}
    finally:
        conn.close()


def update_module(
    module_id: str,
    *,
    title: str | None = None,
    module_number: int | None = None,
    module_summary: str | None = None,
    grade_level: str | None = None,
    standards_body: str | None = None,
    pdf_path: str | None = None,
) -> bool:
    """Update a module. Returns True if a row was updated."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_module WHERE id = %s", (module_id,))
            row = cur.fetchone()
        if not row:
            return False
        r = dict(row)
        if title is not None:
            r["title"] = (title or "").strip() or None
        if module_number is not None:
            r["module_number"] = module_number
        if module_summary is not None:
            r["module_summary"] = (module_summary or "").strip() or None
        if grade_level is not None:
            r["grade_level"] = (grade_level or "").strip() or None
        if standards_body is not None:
            r["standards_body"] = (standards_body or "").strip() or None
        if pdf_path is not None:
            r["pdf_path"] = pdf_path
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE cl_module SET
                   module_number = %s, title = %s, module_summary = %s, grade_level = %s, standards_body = %s, pdf_path = %s
                   WHERE id = %s""",
                (
                    r["module_number"],
                    r["title"],
                    r["module_summary"],
                    r["grade_level"],
                    r["standards_body"],
                    r.get("pdf_path"),
                    module_id,
                ),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    finally:
        conn.close()


def list_modules() -> list[dict[str, Any]]:
    """Return all modules, most recently updated first."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_module ORDER BY updated_at DESC")
            rows = cur.fetchall()
        return [_row_to_dict(r) or {} for r in rows]
    finally:
        conn.close()


def get_module(module_id: str) -> dict[str, Any] | None:
    """Return one module by id or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_module WHERE id = %s", (module_id,))
            row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def create_topic(
    *,
    title: str,
    topic_number: int | None = None,
    topic_summary: str = "",
    pdf_path: str | None = None,
) -> dict[str, Any]:
    """Insert a topic into cl_topic. Returns the created row as dict."""
    uid = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cl_topic
                   (id, topic_number, title, topic_summary, pdf_path)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    uid,
                    topic_number,
                    (title or "").strip() or None,
                    (topic_summary or "").strip() or None,
                    pdf_path,
                ),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_topic WHERE id = %s", (uid,))
            row = cur.fetchone()
            return _row_to_dict(row) or {}
    finally:
        conn.close()


def update_topic_pdf_path(topic_id: str, pdf_path: str | None) -> bool:
    """Set pdf_path for a topic. Returns True if updated."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cl_topic SET pdf_path = %s WHERE id = %s", (pdf_path, topic_id))
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    finally:
        conn.close()


def update_topic(
    topic_id: str,
    *,
    title: str | None = None,
    topic_number: int | None = None,
    topic_summary: str | None = None,
    pdf_path: str | None = None,
) -> bool:
    """Update a topic. Returns True if a row was updated."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_topic WHERE id = %s", (topic_id,))
            row = cur.fetchone()
        if not row:
            return False
        r = dict(row)
        if title is not None:
            r["title"] = (title or "").strip() or None
        if topic_number is not None:
            r["topic_number"] = topic_number
        if topic_summary is not None:
            r["topic_summary"] = (topic_summary or "").strip() or None
        if pdf_path is not None:
            r["pdf_path"] = pdf_path
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE cl_topic SET topic_number = %s, title = %s, topic_summary = %s, pdf_path = %s
                   WHERE id = %s""",
                (
                    r["topic_number"],
                    r["title"],
                    r["topic_summary"],
                    r.get("pdf_path"),
                    topic_id,
                ),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    finally:
        conn.close()


def link_module_topic(module_id: str, topic_id: str, sequence_number: int = 1) -> None:
    """Create or replace module–topic mapping (table cl_module_topic_map)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cl_module_topic_map (id, module_id, topic_id, sequence_number)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE sequence_number = VALUES(sequence_number)""",
                (str(uuid.uuid4()), module_id, topic_id, sequence_number),
            )
        conn.commit()
    finally:
        conn.close()


def get_topic(topic_id: str) -> dict[str, Any] | None:
    """Return one topic by id or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cl_topic WHERE id = %s", (topic_id,))
            row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_topics_for_module(module_id: str) -> list[dict[str, Any]]:
    """Return topics linked to a module, ordered by sequence_number."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT t.* FROM cl_topic t
                   JOIN cl_module_topic_map mt ON mt.topic_id = t.id
                   WHERE mt.module_id = %s
                   ORDER BY mt.sequence_number, t.topic_number""",
                (module_id,),
            )
            rows = cur.fetchall()
        return [_row_to_dict(r) or {} for r in rows]
    finally:
        conn.close()


def get_module_id_for_topic(topic_id: str) -> str | None:
    """Return the module_id linked to this topic, or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT module_id FROM cl_module_topic_map WHERE topic_id = %s LIMIT 1",
                (topic_id,),
            )
            row = cur.fetchone()
        return row["module_id"] if row else None
    finally:
        conn.close()


def list_topics() -> list[dict[str, Any]]:
    """Return all topics with their linked module_id and module title."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT t.*, mt.module_id,
                   (SELECT m.title FROM cl_module m WHERE m.id = mt.module_id) AS module_title
                   FROM cl_topic t
                   JOIN cl_module_topic_map mt ON mt.topic_id = t.id
                   ORDER BY mt.module_id, mt.sequence_number, t.topic_number"""
            )
            rows = cur.fetchall()
        return [_row_to_dict(r) or {} for r in rows]
    finally:
        conn.close()
