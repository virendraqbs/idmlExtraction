#!/usr/bin/env python3
"""
backfill_page_index.py — Walk an outputs/ directory and run index_job_pages
for every job folder containing 13_pages.json. Safe to re-run.

Usage:
    python3 scripts/backfill_page_index.py [outputs/]

If no path is given, defaults to ./outputs/.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.page_indexer import index_job_pages  # noqa: E402


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "outputs"
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    attempted = 0
    failures = 0
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        if not (sub / "13_pages.json").exists():
            continue
        job_id = sub.name
        attempted += 1
        try:
            r = index_job_pages(job_id, sub)
            entities = (
                r.activities + r.tasks + r.stems + r.images
                + r.instructional_prompts + r.instructional_segments
                + r.practice_sections + r.scaffolding + r.response_areas
                + r.lessons
            )
            print(f"{job_id}: pages={r.pages} entities={entities} "
                  f"skipped={r.skipped_no_source_page} "
                  f"errors={len(r.errors)}")
            if r.errors:
                failures += 1
        except Exception as e:
            print(f"{job_id}: FAIL — {e}", file=sys.stderr)
            failures += 1

    print(f"\nBackfill complete: {attempted} jobs attempted, {failures} with errors.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
