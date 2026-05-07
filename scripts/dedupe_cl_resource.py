#!/usr/bin/env python3
"""
dedupe_cl_resource.py — collapse duplicate cl_resource rows that share the
same (title, resource_type), repointing all child mappings to a single
keeper row.

Background: prior versions of get_or_create_resource_for_job inserted a fresh
cl_resource row per extraction (PK = JSON-side UUID, which differs every run).
The Resource dropdown on the upload form ended up listing the same book N
times. This script consolidates them.

For each (title, resource_type) group:
  - Pick the OLDEST row by created_at as the keeper.
  - Repoint cl_resource_module_map.resource_id → keeper.id
  - Repoint cl_resource_page_map.resource_id   → keeper.id
  - Delete the duplicate cl_resource rows.

Idempotent. Safe to re-run.

Usage:
    python3 scripts/dedupe_cl_resource.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from database import get_connection  # noqa: E402


def main() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, resource_type, COUNT(*) AS c
                FROM cl_resource
                GROUP BY title, resource_type
                HAVING COUNT(*) > 1
                """
            )
            groups = cur.fetchall()

            if not groups:
                print("No duplicate cl_resource rows. Nothing to do.")
                return 0

            total_removed = 0
            for g in groups:
                title = g["title"]
                rtype = g["resource_type"]
                cur.execute(
                    """
                    SELECT id FROM cl_resource
                    WHERE title = %s AND resource_type = %s
                    ORDER BY created_at, id
                    """,
                    (title, rtype),
                )
                rows = cur.fetchall()
                keeper = rows[0]["id"]
                dup_ids = [r["id"] for r in rows[1:]]
                if not dup_ids:
                    continue

                fmt = ",".join(["%s"] * len(dup_ids))
                cur.execute(
                    f"UPDATE cl_resource_module_map SET resource_id = %s "
                    f"WHERE resource_id IN ({fmt})",
                    (keeper, *dup_ids),
                )
                cur.execute(
                    f"UPDATE cl_resource_page_map SET resource_id = %s "
                    f"WHERE resource_id IN ({fmt})",
                    (keeper, *dup_ids),
                )
                cur.execute(
                    f"DELETE FROM cl_resource WHERE id IN ({fmt})",
                    tuple(dup_ids),
                )
                total_removed += len(dup_ids)
                print(
                    f"{title!r} [{rtype}]: kept {keeper[:8]} — "
                    f"removed {len(dup_ids)} duplicate(s)"
                )

        conn.commit()
        print(f"\nDedupe complete: {total_removed} duplicate row(s) removed.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
