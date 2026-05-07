# Canonical Schema Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PDF-extraction pipeline emit JSON that validates against the canonical CL-Json-Schema by extending two enums and adding the missing `type` field to two parent-child references.

**Architecture:** Three additive, surgical changes in three commits on a new feature branch. (1) Extend `ReferenceType` and `InstructionalPromptType` in `CL-Json-Schema/schemas/common/enums.json`. (2) Patch two builder functions in `utils/schema_chunks.py` to emit the canonical `type` field on `resource.modules[]` and `module.topics[]`. (3) Add a one-shot verification script that walks an output job folder and validates every Reference and InstructionalPrompt enum value.

**Tech Stack:** Python 3.12, FastAPI pipeline, JSON Schema draft-07, pdf2image + Gemini Vision (no code path changes), no test framework currently in repo (script doubles as runtime check).

**Spec:** `docs/superpowers/specs/2026-05-07-canonical-schema-conformance-design.md`

**Repo:** `/Users/virendrapratapsingh/Projects/carnegielearning-clearmathnational`
**Base branch:** `development`
**Feature branch:** `feat/canonical-schema-conformance`
**Spec/proposal commit (already on `tig-extraction`):** `c2cf892`

---

## File Structure

| Path | Action | Responsibility |
|------|--------|----------------|
| `CL-Json-Schema/schemas/common/enums.json` | Modify | Add 3 values to `ReferenceType.enum`, 2 values to `InstructionalPromptType.enum` |
| `utils/schema_chunks.py` | Modify | `build_resource()` line ~163: add `"type": "MODULE"` to modules ref. `build_module()` line ~209: add `"type": "TOPIC"` to topics ref |
| `scripts/verify_canonical_conformance.py` | Create | Walk a job output folder; validate every Reference and `instructionalPromptType` value against canonical enums; exit 1 on first violation |

No new modules, no schema-validator dependency, no test framework introduced.

---

## Task 0: Confirm Clean Working State and Cut Feature Branch

**Files:** none (git only)

- [ ] **Step 0.1: Verify current branch and clean tree**

```bash
cd /Users/virendrapratapsingh/Projects/carnegielearning-clearmathnational
git status
git branch --show-current
```

Expected: branch is `tig-extraction`. Working tree may have unrelated `M` files (templates/results.html, services/assembler.py, utils/schema_chunks.py, controllers/job_controller.py, README.md from prior work). Stash them so the new branch starts clean.

- [ ] **Step 0.2: Stash any uncommitted changes**

```bash
git stash push -u -m "pre-feat-canonical-schema work"
git status
```

Expected: clean working tree. Note: this stash includes prior uncommitted SRB fixes (sourcePage / pageNumber). They are unrelated to this plan and stay stashed.

- [ ] **Step 0.3: Fetch and cut feature branch from `development`**

```bash
git fetch origin
git checkout -b feat/canonical-schema-conformance origin/development
```

Expected: switched to new branch, tracking `origin/development`. If `origin/development` does not exist, fall back to local `development`:

```bash
git checkout -b feat/canonical-schema-conformance development
```

- [ ] **Step 0.4: Verify branch baseline**

```bash
git log --oneline -3
git status
```

Expected: HEAD is the latest commit on `development`, working tree clean.

---

## Task 1: Extend `ReferenceType` Enum

**Files:**
- Modify: `CL-Json-Schema/schemas/common/enums.json` (block at line 237)

- [ ] **Step 1.1: Apply the edit**

Find the `ReferenceType` block (currently 13 values ending with `"INSTRUCTIONAL_PROMPT"`). Append three values.

Old:
```json
    "ReferenceType": {
      "type": "string",
      "enum": [
        "LESSON",
        "ACTIVITY",
        "TASK",
        "STANDARDS_BLOCK",
        "STANDARDS",
        "INSTRUCTIONAL_GUIDE_PROMPT",
        "GOALS",
        "IMAGE",
        "STEM",
        "SCAFFOLDING",
        "PAGES",
        "INSTRUCTIONAL_SEGMENT",
        "INSTRUCTIONAL_PROMPT"
      ]
    },
```

New:
```json
    "ReferenceType": {
      "type": "string",
      "enum": [
        "LESSON",
        "ACTIVITY",
        "TASK",
        "STANDARDS_BLOCK",
        "STANDARDS",
        "INSTRUCTIONAL_GUIDE_PROMPT",
        "GOALS",
        "IMAGE",
        "STEM",
        "SCAFFOLDING",
        "PAGES",
        "INSTRUCTIONAL_SEGMENT",
        "INSTRUCTIONAL_PROMPT",
        "RESOURCE",
        "MODULE",
        "TOPIC"
      ]
    },
```

- [ ] **Step 1.2: Verify file still parses as strict JSON**

```bash
python3 -m json.tool CL-Json-Schema/schemas/common/enums.json > /dev/null && echo OK
```

Expected: `OK` printed, exit 0.

- [ ] **Step 1.3: Verify the new values are present**

```bash
python3 -c "
import json
e = json.load(open('CL-Json-Schema/schemas/common/enums.json'))['definitions']['ReferenceType']['enum']
for v in ('RESOURCE', 'MODULE', 'TOPIC'):
    assert v in e, f'{v} missing'
print('ReferenceType len:', len(e))
"
```

Expected: prints `ReferenceType len: 16`.

---

## Task 2: Extend `InstructionalPromptType` Enum and Commit Schema Changes

**Files:**
- Modify: `CL-Json-Schema/schemas/common/enums.json` (block at line 203)

- [ ] **Step 2.1: Apply the edit**

Find the `InstructionalPromptType` block (currently 10 values ending with `"MATERIALS_LIST"`). Append two values.

Old:
```json
    "InstructionalPromptType": {
      "type": "string",
      "enum": [
        "LEARNING_GOALS",
        "LANGUAGE_GOALS",
        "DAILY_MATH_ROUTINES",
        "MULTILINGUAL_LEARNER_SUPPORT",
        "TEACHER_STORY",
        "HABITS_OF_MIND",
        "STUDENT_LOOK_FORS",
        "CULTIVATE_CONNECTIONS",
        "STUDENT_EDITION_PAGE_IMAGE",
        "MATERIALS_LIST"
      ]
    },
```

New:
```json
    "InstructionalPromptType": {
      "type": "string",
      "enum": [
        "LEARNING_GOALS",
        "LANGUAGE_GOALS",
        "DAILY_MATH_ROUTINES",
        "MULTILINGUAL_LEARNER_SUPPORT",
        "TEACHER_STORY",
        "HABITS_OF_MIND",
        "STUDENT_LOOK_FORS",
        "CULTIVATE_CONNECTIONS",
        "STUDENT_EDITION_PAGE_IMAGE",
        "MATERIALS_LIST",
        "CONTENT_CONNECTION",
        "COMMON_MISCONCEPTIONS"
      ]
    },
```

- [ ] **Step 2.2: Verify file still parses + new values present**

```bash
python3 -m json.tool CL-Json-Schema/schemas/common/enums.json > /dev/null && echo OK
python3 -c "
import json
e = json.load(open('CL-Json-Schema/schemas/common/enums.json'))['definitions']['InstructionalPromptType']['enum']
for v in ('CONTENT_CONNECTION', 'COMMON_MISCONCEPTIONS'):
    assert v in e, f'{v} missing'
print('InstructionalPromptType len:', len(e))
"
```

Expected: `OK` then `InstructionalPromptType len: 12`.

- [ ] **Step 2.3: Commit (commit 1 of 3)**

```bash
git add CL-Json-Schema/schemas/common/enums.json
git diff --cached --stat
git commit -m "schema: extend ReferenceType and InstructionalPromptType enums

ReferenceType += RESOURCE, MODULE, TOPIC — required for canonical
parent-child references (resource.modules[], module.topics[]).

InstructionalPromptType += CONTENT_CONNECTION, COMMON_MISCONCEPTIONS —
TIG callouts already extracted by services/tig_extractor.py but
previously rejected by canonical schema.

Both changes additive; existing values preserved in order.

Refs: docs/SCHEMA_EXTENSIONS_PROPOSAL.md"
```

Expected: commit succeeds, `1 file changed`.

---

## Task 3: Emit `type` on `resource.modules[]` Reference

**Files:**
- Modify: `utils/schema_chunks.py` line 162-163 (`build_resource()`)

- [ ] **Step 3.1: Apply the edit**

Old (lines 162-163):
```python
        # type field omitted — can only be a module (issue #2)
        "modules":      [{"id": module_id}],
```

New:
```python
        # Reference type required by canonical schema (ReferenceType.MODULE)
        "modules":      [{"id": module_id, "type": "MODULE"}],
```

- [ ] **Step 3.2: Verify the file still imports cleanly**

```bash
python3 -c "from utils import schema_chunks; print('imports OK')"
```

Expected: `imports OK`. If `ImportError` mentions a missing third-party package (e.g. `pymysql`), it is a pre-existing environment issue unrelated to this edit — skip and rely on the smoke run in Task 6 instead.

- [ ] **Step 3.3: Inline test of `build_resource` output**

```bash
python3 -c "
from utils.schema_chunks import build_resource
out = build_resource(
    resource_id='r1', module_id='m1', lesson_meta={},
    page_refs=[], total_pages=0, source_filename='x.pdf',
    book_name=None, db_module=None,
)
mod = out['modules'][0]
assert mod == {'id': 'm1', 'type': 'MODULE'}, mod
print('build_resource modules ref OK:', mod)
"
```

Expected: `build_resource modules ref OK: {'id': 'm1', 'type': 'MODULE'}`.

If `build_resource` signature is different from what is shown above, inspect with:
```bash
python3 -c "import inspect; from utils.schema_chunks import build_resource; print(inspect.signature(build_resource))"
```
Then call with the correct kwargs. The only assertion that matters is `modules[0] == {'id': 'm1', 'type': 'MODULE'}`.

---

## Task 4: Emit `type` on `module.topics[]` Reference and Commit Code Changes

**Files:**
- Modify: `utils/schema_chunks.py` line 208-209 (`build_module()`)

- [ ] **Step 4.1: Apply the edit**

Old (lines 208-209):
```python
        # type field omitted — can only be a topic (issue #3)
        "topics":        [{"id": topic_id, "sequenceNumber": 1}],
```

New:
```python
        # Reference type required by canonical schema (ReferenceType.TOPIC)
        "topics":        [{"id": topic_id, "type": "TOPIC", "sequenceNumber": 1}],
```

- [ ] **Step 4.2: Inline test of `build_module` output**

```bash
python3 -c "
from utils.schema_chunks import build_module
out = build_module(
    module_id='m1', resource_id='r1', topic_id='t1',
    lesson_meta={'standards_body': 'CCSS', 'module_number': 1},
)
top = out['topics'][0]
assert top == {'id': 't1', 'type': 'TOPIC', 'sequenceNumber': 1}, top
print('build_module topics ref OK:', top)
"
```

Expected: `build_module topics ref OK: {'id': 't1', 'type': 'TOPIC', 'sequenceNumber': 1}`.

If the signature differs, inspect with `inspect.signature` as in Step 3.3 and adjust kwargs. The assertion stays the same.

- [ ] **Step 4.3: Commit (commit 2 of 3)**

```bash
git add utils/schema_chunks.py
git diff --cached
git commit -m "feat(srb): emit canonical Reference.type on resource.modules and module.topics

build_resource() now writes {id, type: 'MODULE'} on resource.modules[].
build_module() now writes {id, type: 'TOPIC', sequenceNumber} on
module.topics[].

The Reference primitive in CL-Json-Schema requires {id, type}.
Previously these references were emitted with only {id}, making the
output invalid against the canonical schema. Schema enum was extended
in the prior commit to include MODULE and TOPIC values.

Refs: docs/superpowers/specs/2026-05-07-canonical-schema-conformance-design.md"
```

Expected: commit succeeds, `1 file changed`.

---

## Task 5: Add Verification Script

**Files:**
- Create: `scripts/verify_canonical_conformance.py`

- [ ] **Step 5.1: Create the script**

```python
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
    """A response-area or other typed primitive: has id+type but also
    type-specific fields. ReferenceType strings are short uppercase."""
    field_signals = {"description", "specifications", "content", "text",
                     "instructionalPromptType", "stemType", "taskType",
                     "activityType", "scaffoldingType", "imageType", "pageType"}
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
```

- [ ] **Step 5.2: Make script executable + smoke-check it loads enums**

```bash
chmod +x scripts/verify_canonical_conformance.py
python3 scripts/verify_canonical_conformance.py 2>&1 | head -3
```

Expected: prints `usage: verify_canonical_conformance.py <output-job-dir>`, exit code 2.

- [ ] **Step 5.3: Confirm script runs against the canonical Final-shape baseline**

Pick one existing job folder. The PRE-FIX outputs were written before the `type` field was added to modules/topics references — they SHOULD report violations. This confirms the script catches real problems.

```bash
python3 scripts/verify_canonical_conformance.py outputs/ba323964-d005-4ed5-a16d-437eb81fce9c
echo "exit=$?"
```

Expected: prints either `OK` (if existing output already happened to be valid) or `FAIL` listing violations. Either result is informational only — it does not block this task. The authoritative run happens in Task 6 against a freshly-extracted job.

---

## Task 6: Smoke-Run a Fresh SRB Extraction and Verify Conformance

**Files:** none (runtime verification only)

This task confirms the changes from Tasks 1–4 produce conformant output on a fresh PDF. The pipeline is heavyweight (calls Gemini API, takes minutes per job, costs API tokens), so this task is **optional but strongly recommended** before opening the PR. If skipped, document the skip in the PR description.

- [ ] **Step 6.1: Identify a sample SRB PDF**

```bash
ls sourceFile/*.pdf
```

Expected: includes at minimum `sourceFile/A1_T13_L1.pdf`. Use that one.

- [ ] **Step 6.2: Pre-flight check — confirm `.env` has `GOOGLE_API_KEY`**

```bash
grep -E "^GOOGLE_API_KEY|^GEMINI_API_KEY" .env 2>/dev/null | head -1
```

Expected: a non-empty line. If missing, the run cannot proceed — report to the user and stop here.

- [ ] **Step 6.3: Run the SRB CLI extractor**

```bash
python3 scripts/extract_module_pdf.py sourceFile/A1_T13_L1.pdf
```

Wait for completion (5–15 min depending on page count). Note the `outputs/<new-job-id>/` directory printed at the end.

If `scripts/extract_module_pdf.py` requires different flags, run `python3 scripts/extract_module_pdf.py --help` first.

- [ ] **Step 6.4: Run the verification script against the new job**

```bash
NEW_JOB=$(ls -td outputs/*/ | head -1)
echo "verifying: $NEW_JOB"
python3 scripts/verify_canonical_conformance.py "$NEW_JOB"
echo "exit=$?"
```

Expected: `OK — N files, all Reference.type and instructionalPromptType values canonical.`, exit 0.

- [ ] **Step 6.5: Spot-check the two patched references in the new output**

```bash
python3 -c "
import json, sys, glob
job = sorted(glob.glob('outputs/*/'), key=lambda p: -__import__('os').path.getmtime(p))[0]
print('job:', job)
r = json.load(open(job + '03_resource.json'))
print('resource.modules[0]:', r['modules'][0])
m = json.load(open(job + '04_module.json'))
print('module.topics[0]:', m['topics'][0])
assert r['modules'][0].get('type') == 'MODULE', 'modules[0].type wrong'
assert m['topics'][0].get('type') == 'TOPIC', 'topics[0].type wrong'
print('spot check OK')
"
```

Expected: prints both refs with `type` populated; final line `spot check OK`.

If verification fails, do NOT proceed to Task 7. Investigate which builder still emits the old shape and fix before continuing.

---

## Task 7: (Optional) TIG Smoke-Run and Commit Verification Script

**Files:** none for runtime; commit `scripts/verify_canonical_conformance.py`

- [ ] **Step 7.1: (Optional) TIG smoke run**

If a TIG run is feasible in this session (API budget + time), run it; otherwise skip and note skip in PR description.

```bash
python3 scripts/extract_tig_pdf.py "sourceFile/tig/EMNA2e_G05_M01_T01_L01_TIG_TAGGED.pdf"
NEW_TIG=$(ls -td outputs/*/ | head -1)
python3 scripts/verify_canonical_conformance.py "$NEW_TIG"
echo "exit=$?"
```

Expected: `OK`, exit 0. Any `CONTENT_CONNECTION` or `COMMON_MISCONCEPTIONS` prompts in the output are now valid per the extended enum.

- [ ] **Step 7.2: Commit verification script (commit 3 of 3)**

```bash
git add scripts/verify_canonical_conformance.py
git diff --cached --stat
git commit -m "scripts: add verify_canonical_conformance.py

One-shot validator for an output job folder. Walks every JSON file
and checks every Reference.type and instructionalPromptType against
the canonical enums in CL-Json-Schema/schemas/common/enums.json.
Exits 0 on clean, 1 on any violation.

Usage: python3 scripts/verify_canonical_conformance.py outputs/<job-id>

Refs: docs/superpowers/specs/2026-05-07-canonical-schema-conformance-design.md"
```

Expected: commit succeeds, `1 file changed`.

---

## Task 8: Push Branch and Open Pull Request

**Files:** none (git/GitHub only)

- [ ] **Step 8.1: Verify three-commit history on the branch**

```bash
git log --oneline development..HEAD
```

Expected: exactly 3 commits, in order:
1. `schema: extend ReferenceType and InstructionalPromptType enums`
2. `feat(srb): emit canonical Reference.type on resource.modules and module.topics`
3. `scripts: add verify_canonical_conformance.py`

- [ ] **Step 8.2: Push to origin with upstream tracking**

```bash
git push -u origin feat/canonical-schema-conformance
```

Expected: branch published, upstream set.

- [ ] **Step 8.3: Open the pull request via gh CLI**

```bash
gh pr create --base development --head feat/canonical-schema-conformance \
  --title "Canonical schema conformance: extend enums + emit Reference.type" \
  --body "$(cat <<'EOF'
## Summary
- Extends `ReferenceType` enum with `RESOURCE`, `MODULE`, `TOPIC` and `InstructionalPromptType` with `CONTENT_CONNECTION`, `COMMON_MISCONCEPTIONS` in `CL-Json-Schema/schemas/common/enums.json`.
- `build_resource()` now emits `{id, type: "MODULE"}` on `resource.modules[]`; `build_module()` now emits `{id, type: "TOPIC", sequenceNumber}` on `module.topics[]`.
- Adds `scripts/verify_canonical_conformance.py` to validate any output job folder against the canonical enums.

## Why
Canonical Reference primitive requires `{id, type}` but the SRB pipeline omitted `type` on the two parent-child arrays. Canonical `ReferenceType` enum also lacked the values needed to populate them. TIG side already emits `CONTENT_CONNECTION`/`COMMON_MISCONCEPTIONS` (see `services/tig_extractor.py:74-75`); only the schema needed updating to accept them.

Spec: `docs/superpowers/specs/2026-05-07-canonical-schema-conformance-design.md`
Client proposal: `docs/SCHEMA_EXTENSIONS_PROPOSAL.md`

## Out of scope
- Image rendering bug (`imagePath` vs `filepath`)
- Editor / results-page UI changes
- Backfilling pre-existing job folders
- Restructuring activities/tasks/stems content to match Final JSONs

## Test plan
- [ ] `python3 -m json.tool CL-Json-Schema/schemas/common/enums.json` parses
- [ ] `python3 scripts/verify_canonical_conformance.py outputs/<fresh-srb-job>` exits 0
- [ ] `outputs/<fresh-job>/03_resource.json` has `modules[0].type == "MODULE"`
- [ ] `outputs/<fresh-job>/04_module.json` has `topics[0].type == "TOPIC"`
- [ ] (if run) `python3 scripts/verify_canonical_conformance.py outputs/<fresh-tig-job>` exits 0
EOF
)"
```

Expected: PR URL printed. Done.

- [ ] **Step 8.4: Print PR URL for the user**

The previous step prints the URL. Copy it into the final report.

---

## Self-Review Notes

- Spec section 4.1 (schema extensions) → Tasks 1, 2 ✓
- Spec section 4.2 (SRB ref-type emission) → Tasks 3, 4 ✓
- Spec section 4.3 (verification script) → Tasks 5, 7.2 ✓
- Spec section 7 (test plan) → Tasks 6, 7.1 ✓
- Spec section 9 (branch + commit plan) → Tasks 0, 2.3, 4.3, 7.2, 8 ✓
- Out-of-scope items from spec section 3 not introduced anywhere in plan ✓
- Three commits on the branch match design's commit plan ✓
- Each task has exact file paths, exact code blocks where code changes, exact commands with expected output ✓
- No "TBD"/"TODO"/"add appropriate"/"similar to Task N" placeholders ✓
- Type/method consistency: `build_resource`, `build_module`, `verify_canonical_conformance.py`, `outputs/<job-id>/` used consistently across tasks ✓
