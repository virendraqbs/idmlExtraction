#!/usr/bin/env python3
"""
verify_canonical_conformance.py — validate one job output folder against the
canonical CL-Json-Schema enums.

Walks every JSON file in the given output directory and checks:
  1. Every Reference-shaped object ({id, type, ...}) has a `type` value
     in canonical ReferenceType.enum.
  2. Every `instructionalPromptType` value is in canonical
     InstructionalPromptType.enum.

Exit code 0 = clean. Exit code 1 = at least one violation reported.

Usage:
    python3 scripts/verify_canonical_conformance.py outputs/<job-id>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENUMS_PATH = REPO_ROOT / "CL-Json-Schema" / "schemas" / "common" / "enums.json"


def load_enums() -> tuple[set[str], set[str]]:
    with ENUMS_PATH.open(encoding="utf-8") as f:
        defs = json.load(f)["definitions"]
    return (
        set(defs["ReferenceType"]["enum"]),
        set(defs["InstructionalPromptType"]["enum"]),
    )


def is_reference(obj: object) -> bool:
    """Heuristic: dict containing both `id` and `type` (string) is a Reference."""
    return (
        isinstance(obj, dict)
        and "id" in obj
        and isinstance(obj.get("type"), str)
        and isinstance(obj.get("id"), str)
        and len(obj["id"]) >= 8
    )


def walk(node: object, file: str, path: str, ref_enum: set[str],
         prompt_enum: set[str], violations: list[str]) -> None:
    if isinstance(node, dict):
        # InstructionalPromptType check
        ipt = node.get("instructionalPromptType")
        if isinstance(ipt, str) and ipt not in prompt_enum:
            violations.append(
                f"{file}{path}: instructionalPromptType={ipt!r} not in canonical enum"
            )
        # Reference check (skip nodes whose `type` is for a different enum,
        # e.g. response-area objects whose `type` is ResponseAreaType).
        # We only flag refs that look like cross-entity pointers (have id+type
        # AND no `description`/`specifications`/`text` field that would suggest
        # they are a typed primitive).
        if is_reference(node) and not _is_typed_primitive(node):
            t = node["type"]
            if t not in ref_enum:
                violations.append(
                    f"{file}{path}: Reference.type={t!r} not in canonical ReferenceType"
                )
        for k, v in node.items():
            walk(v, file, f"{path}.{k}", ref_enum, prompt_enum, violations)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, file, f"{path}[{i}]", ref_enum, prompt_enum, violations)


def _is_typed_primitive(obj: dict) -> bool:
    """A response-area, page, or other typed primitive: has id+type but
    also type-specific fields. Canonical Reference shape is {id, type}
    plus optional sequenceNumber — any other domain field implies the
    object is not a pure Reference and its `type` is not from ReferenceType.
    """
    field_signals = {"description", "specifications", "content", "text",
                     "instructionalPromptType", "stemType", "taskType",
                     "activityType", "scaffoldingType", "imageType",
                     "pageType", "pageNumber"}
    return any(k in obj for k in field_signals)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_canonical_conformance.py <output-job-dir>",
              file=sys.stderr)
        return 2
    job_dir = Path(argv[1]).resolve()
    if not job_dir.is_dir():
        print(f"not a directory: {job_dir}", file=sys.stderr)
        return 2

    ref_enum, prompt_enum = load_enums()
    violations: list[str] = []
    # raw_extractions + extraction_report are intermediate; merged.json
    # is a composed view of the other 19 files — scanning it would
    # double-count violations.
    json_files = sorted(p for p in job_dir.glob("*.json")
                        if p.name not in {"raw_extractions.json",
                                          "extraction_report.json",
                                          "merged.json"})
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            violations.append(f"{f.name}: parse error: {e}")
            continue
        walk(data, f.name, "", ref_enum, prompt_enum, violations)

    if violations:
        print(f"FAIL — {len(violations)} violation(s):")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"OK — {len(json_files)} files, all Reference.type and "
          f"instructionalPromptType values canonical.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
