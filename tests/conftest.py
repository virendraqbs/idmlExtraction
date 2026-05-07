"""Pytest fixtures for page-index tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_job_dir() -> Path:
    """Path to the bundled minimal job fixture (4 JSON files)."""
    return Path(__file__).parent / "fixtures" / "sample_job"


@pytest.fixture
def fixture_job_id() -> str:
    return "test-fixture-job"


@pytest.fixture(autouse=True)
def _stub_pwd(monkeypatch):
    """Make sure tests run from repo root regardless of CWD."""
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
