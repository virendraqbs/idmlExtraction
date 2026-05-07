"""Unit tests for services.page_indexer.

These tests use a stub database connection — the real DB is exercised in
Task 2's manual smoke run. Here we verify the IndexReport structure and
the JSON-walk logic that decides which entities get indexed.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _stub_conn():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def test_index_report_counts_match_fixture(sample_job_dir, fixture_job_id):
    """Indexer reads JSON and emits one ACTIVITY row per activity with sourcePage."""
    from services import page_indexer

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn), \
         patch.object(page_indexer, "get_or_create_resource_for_job",
                      return_value="11111111-1111-1111-1111-111111111111"):
        report = page_indexer.index_job_pages(fixture_job_id, sample_job_dir)

    assert report.pages == 2
    assert report.activities == 2
    assert report.lessons == 1
    assert report.errors == []


def test_index_report_skips_entity_with_no_sourcePage(tmp_path, fixture_job_id):
    """Entities lacking sourcePage are skipped, not exceptions."""
    from services import page_indexer

    # Build a minimal job with one activity missing sourcePage.
    (tmp_path / "03_resource.json").write_text(json.dumps({
        "id": "33333333-3333-3333-3333-333333333333",
        "resourceType": "STUDENT_RESOURCE_BOOK",
        "title": "Tmp",
    }))
    (tmp_path / "13_pages.json").write_text(json.dumps({
        "pages": [
            {"id": "p1", "pageNumber": 1, "pageType": "SRB_LESSON_EXPLORE"},
        ]
    }))
    (tmp_path / "07_activities.json").write_text(json.dumps({
        "activities": [
            {"id": "no-page", "title": "NoPage", "tasks": []},
        ]
    }))

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn), \
         patch.object(page_indexer, "get_or_create_resource_for_job",
                      return_value="33333333-3333-3333-3333-333333333333"):
        report = page_indexer.index_job_pages(fixture_job_id, tmp_path)

    assert report.activities == 0
    assert report.skipped_no_source_page >= 1
    assert report.errors == []


def test_index_returns_report_on_missing_files(tmp_path, fixture_job_id):
    """Missing 03_resource.json or 13_pages.json reports an error, no exception."""
    from services import page_indexer

    conn, cur = _stub_conn()
    with patch.object(page_indexer, "get_connection", return_value=conn):
        report = page_indexer.index_job_pages(fixture_job_id, tmp_path)

    assert report.pages == 0
    assert any("missing" in e for e in report.errors)


def test_index_is_idempotent(sample_job_dir, fixture_job_id):
    """Running indexer twice produces identical IndexReport AND second run exercises DELETE branch."""
    from services import page_indexer

    conn, cur = _stub_conn()
    # First call: no prior rows (fetchall returns []).
    with patch.object(page_indexer, "get_connection", return_value=conn), \
         patch.object(page_indexer, "get_or_create_resource_for_job",
                      return_value="11111111-1111-1111-1111-111111111111"):
        report1 = page_indexer.index_job_pages(fixture_job_id, sample_job_dir)

        # Second call: pretend prior page rows exist so DELETE path runs.
        cur.fetchall.return_value = [
            {"id": "ppppppp1-pppp-pppp-pppp-pppppppppppp"},
            {"id": "ppppppp2-pppp-pppp-pppp-pppppppppppp"},
        ]
        report2 = page_indexer.index_job_pages(fixture_job_id, sample_job_dir)

    # DELETE path was exercised — verify by counting DELETE statements issued.
    delete_calls = [
        c.args[0] for c in cur.execute.call_args_list
        if isinstance(c.args[0], str) and c.args[0].lstrip().upper().startswith("DELETE")
    ]
    assert any("cl_page_entity_map" in d for d in delete_calls), \
        "second call should DELETE prior cl_page_entity_map rows"
    assert any("cl_resource_page_map" in d for d in delete_calls), \
        "second call should DELETE prior cl_resource_page_map rows"
    assert any("cl_page" in d and "cl_page_entity_map" not in d
               and "cl_resource_page_map" not in d for d in delete_calls), \
        "second call should DELETE prior cl_page rows"

    # Reports identical
    assert report1.pages == report2.pages
    assert report1.activities == report2.activities
    assert report1.lessons == report2.lessons
    assert report1.images == report2.images
    assert report1.tasks == report2.tasks
    assert report1.stems == report2.stems
    assert report1.errors == report2.errors == []
