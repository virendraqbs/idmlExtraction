"""
phase3_merge.py
===============
Phase 3: Reads all 15 individual Phase 2 JSON files and produces:

  phase3_merged/
    merged_flat.json      ← All entities as top-level arrays (DB ingestion ready)
    merged_nested.json    ← Fully embedded hierarchy (human review ready)
    merge_report.json     ← Stats, broken references, validation alerts

Usage:
  python phase3_merge.py
  python phase3_merge.py --input-dir phase2_extracted --output-dir phase3_merged
"""
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size = path.stat().st_size
    log.info(f"  Wrote: {path}  ({size / 1024:.1f} KB)")


class Phase3Merger:

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir  = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.now = datetime.now(timezone.utc).isoformat()

        # All entity stores — keyed by id
        self.resource           = {}
        self.module             = {}
        self.topic              = {}
        self.lesson             = {}
        self.activities         = {}   # id → activity
        self.tasks              = {}   # id → task
        self.stems              = {}   # id → stem
        self.standards          = {}   # id → standard
        self.standards_blocks   = {}   # id → block
        self.images             = {}   # id → image
        self.pages              = {}   # id → page
        self.inst_prompts       = {}   # id → prompt
        self.inst_segments      = {}   # id → segment

        # Broken reference tracker for report
        self.broken_refs = []
        self.alerts      = []

    # ── Load ──────────────────────────────────────────────────────────────────

    def load_all(self):
        log.info(f"Loading Phase 2 files from {self.input_dir}...")

        files = sorted(self.input_dir.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"No JSON files found in {self.input_dir}")

        for path in files:
            data = load_json(path)
            schema = data.get("_schema", "")
            log.info(f"  Loading: {path.name}  ({schema})")

            if "resource.json" in schema and "module" not in schema:
                self.resource = data
            elif "module.json" in schema:
                self.module = data
            elif "topic.json" in schema:
                self.topic = data
            elif "lesson.json" in schema:
                self.lesson = data
            elif "activity.json" in schema:
                for a in data.get("activities", []):
                    self.activities[a["id"]] = a
            elif "task.json" in schema:
                for t in data.get("tasks", []):
                    self.tasks[t["id"]] = t
            elif "stem.json" in schema:
                for s in data.get("stems", []):
                    self.stems[s["id"]] = s
            elif "standards-block.json" in schema:
                for sb in data.get("standardsBlocks", []):
                    self.standards_blocks[sb["id"]] = sb
            elif "standard.json" in schema:
                for s in data.get("standards", []):
                    self.standards[s["id"]] = s
            elif "image.json" in schema:
                for i in data.get("images", []):
                    self.images[i["id"]] = i
            elif "page.json" in schema:
                for p in data.get("pages", []):
                    self.pages[p["id"]] = p
            elif "instructional-prompt.json" in schema:
                for ip in data.get("instructionalPrompts", []):
                    self.inst_prompts[ip["id"]] = ip
            elif "instructional-segment.json" in schema:
                for iseg in data.get("instructionalSegments", []):
                    self.inst_segments[iseg["id"]] = iseg

        log.info(f"  Loaded: {len(self.activities)} activities, {len(self.tasks)} tasks, "
                 f"{len(self.stems)} stems, {len(self.standards)} standards, "
                 f"{len(self.images)} images, {len(self.pages)} pages")

    # ── Validate references ────────────────────────────────────────────────────

    def validate_references(self):
        log.info("Validating cross-references...")

        def check(ref_id, store, context):
            if ref_id and ref_id not in store:
                self.broken_refs.append({
                    "context": context,
                    "missingId": ref_id,
                    "store": store.__class__.__name__
                })

        # Lesson → standards_block
        check(self.lesson.get("standardsBlock"), self.standards_blocks, "lesson.standardsBlock")
        # Lesson → activities
        for ref in self.lesson.get("activities", []):
            check(ref["id"], self.activities, f"lesson.activities[{ref['id']}]")
        # Activities → tasks
        for act in self.activities.values():
            for ref in act.get("tasks", []):
                check(ref["id"], self.tasks, f"activity[{act['id']}].tasks")
        # Tasks → stems
        for task in self.tasks.values():
            for ref in task.get("stems", []):
                check(ref["id"], self.stems, f"task[{task['id']}].stems")
        # Standards block → standards
        for sb in self.standards_blocks.values():
            for ref in sb.get("standards", []):
                check(ref["id"], self.standards, f"standards_block[{sb['id']}].standards")
        # Images missing alt text
        for img in self.images.values():
            if not img.get("accessibility", {}).get("isDecorative") and not img.get("altText"):
                self.alerts.append({
                    "level": "WARNING",
                    "field": f"image[{img.get('filename')}].altText",
                    "message": "Non-decorative image missing altText — accessibility violation"
                })

        if self.broken_refs:
            log.warning(f"  Found {len(self.broken_refs)} broken reference(s)")
            for br in self.broken_refs:
                self.alerts.append({
                    "level": "ERROR",
                    "field": br["context"],
                    "message": f"Reference {br['missingId']} not found"
                })
        else:
            log.info("  All references valid ✓")

    # ── Phase 3A: Flat merged JSON ─────────────────────────────────────────────

    def build_flat(self) -> dict:
        """
        Flat structure — all entities as top-level arrays with UUID links.
        Ideal for database ingestion, each array maps to a DB table.
        """
        return {
            "_phase": "PHASE_3_MERGED_FLAT",
            "_description": "All CL schema entities as flat arrays. UUIDs link between entities. Suitable for DB ingestion.",
            "_generatedAt": self.now,
            "_stats": self._stats(),

            "resource":             self.resource,
            "module":               self.module,
            "topic":                self.topic,
            "lesson":               self.lesson,

            "activities":           list(self.activities.values()),
            "tasks":                list(self.tasks.values()),
            "stems":                list(self.stems.values()),

            "standards":            list(self.standards.values()),
            "standardsBlocks":      list(self.standards_blocks.values()),

            "images":               list(self.images.values()),
            "pages":                list(self.pages.values()),

            "instructionalPrompts":   list(self.inst_prompts.values()),
            "instructionalSegments":  list(self.inst_segments.values()),

            "alerts":               self.alerts
        }

    # ── Phase 3B: Nested merged JSON ──────────────────────────────────────────

    def build_nested(self) -> dict:
        """
        Fully embedded hierarchy — every child entity embedded inside its parent.
        Ideal for human review, rendering, and export to external systems.
        """

        def embed_stem(stem_ref):
            s = self.stems.get(stem_ref["id"], {})
            return {**s, "_embedded": True}

        def embed_task(task_ref):
            t = dict(self.tasks.get(task_ref["id"], {}))
            t["stems"] = [embed_stem(sr) for sr in t.get("stems", [])]
            t["_embedded"] = True
            return t

        def embed_activity(act_ref):
            a = dict(self.activities.get(act_ref["id"], {}))
            a["tasks"] = [embed_task(tr) for tr in a.get("tasks", [])]
            a["_embedded"] = True
            return a

        def embed_standards_block(block_id):
            sb = dict(self.standards_blocks.get(block_id, {}))
            sb["standards"] = [
                {**self.standards.get(sr["id"], {}), "_embedded": True}
                for sr in sb.get("standards", [])
            ]
            sb["_embedded"] = True
            return sb

        def embed_page(page_ref):
            p = dict(self.pages.get(page_ref["id"], {}))
            enriched_blocks = []
            for block in p.get("contentBlocks", []):
                b = dict(block)
                cid = b.get("contentId")
                ct  = b.get("contentType")
                if ct == "IMAGE" and cid in self.images:
                    b["_embeddedContent"] = self.images[cid]
                elif ct == "STANDARDS_BLOCK" and cid in self.standards_blocks:
                    b["_embeddedContent"] = embed_standards_block(cid)
                elif ct == "ACTIVITY" and cid in self.activities:
                    b["_embeddedContent"] = {"id": cid, "title": self.activities[cid].get("title")}
                enriched_blocks.append(b)
            p["contentBlocks"] = enriched_blocks
            p["_embedded"] = True
            return p

        # Build embedded lesson
        lesson = dict(self.lesson)
        lesson["standardsBlock"] = embed_standards_block(lesson.get("standardsBlock"))
        lesson["activities"]     = [embed_activity(ar) for ar in lesson.get("activities", [])]
        lesson["_embedded"]      = True

        # Build embedded topic
        topic = dict(self.topic)
        topic["lessons"] = [lesson]
        topic["_embedded"] = True

        # Build embedded module
        module = dict(self.module)
        module["topics"] = [topic]
        module["_embedded"] = True

        # Build embedded resource with pages
        resource = dict(self.resource)
        resource["modules"] = [module]
        resource["pages"]   = [embed_page(pr) for pr in resource.get("pages", [])]
        resource["_embedded"] = True

        return {
            "_phase": "PHASE_3_MERGED_NESTED",
            "_description": "Fully embedded hierarchy. Every child is nested inside its parent. Suitable for human review and rendering.",
            "_generatedAt": self.now,
            "_stats": self._stats(),

            "resource": resource,

            "images":                 list(self.images.values()),
            "instructionalPrompts":   list(self.inst_prompts.values()),
            "instructionalSegments":  list(self.inst_segments.values()),

            "alerts": self.alerts
        }

    # ── Report ─────────────────────────────────────────────────────────────────

    def build_report(self) -> dict:
        warnings = [a for a in self.alerts if a["level"] == "WARNING"]
        errors   = [a for a in self.alerts if a["level"] == "ERROR"]

        return {
            "_phase": "PHASE_3_MERGE_REPORT",
            "_generatedAt": self.now,
            "summary": {
                **self._stats(),
                "brokenReferences": len(self.broken_refs),
                "totalAlerts": len(self.alerts),
                "errorCount": len(errors),
                "warningCount": len(warnings)
            },
            "referenceValidation": {
                "passed": len(self.broken_refs) == 0,
                "brokenReferences": self.broken_refs
            },
            "alerts": self.alerts,
            "readiness": "READY_FOR_REVIEW" if not errors else "NEEDS_ATTENTION"
        }

    def _stats(self) -> dict:
        return {
            "activitiesCount":          len(self.activities),
            "tasksCount":               len(self.tasks),
            "stemsCount":               len(self.stems),
            "standardsCount":           len(self.standards),
            "standardsBlocksCount":     len(self.standards_blocks),
            "imagesCount":              len(self.images),
            "pagesCount":               len(self.pages),
            "instructionalPromptsCount":  len(self.inst_prompts),
            "instructionalSegmentsCount": len(self.inst_segments)
        }

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self):
        self.load_all()
        self.validate_references()

        log.info("Building flat merged JSON...")
        flat = self.build_flat()
        write_json(self.output_dir / "merged_flat.json", flat)

        log.info("Building nested merged JSON...")
        nested = self.build_nested()
        write_json(self.output_dir / "merged_nested.json", nested)

        log.info("Building merge report...")
        report = self.build_report()
        write_json(self.output_dir / "merge_report.json", report)

        log.info(f"\n✅ Phase 3 complete — 3 files written to {self.output_dir}/")
        log.info(f"   merged_flat.json     — flat arrays for DB ingestion")
        log.info(f"   merged_nested.json   — fully embedded for human review")
        log.info(f"   merge_report.json    — validation report")

        if report["referenceValidation"]["passed"]:
            log.info(f"   Reference validation: ✓ All references valid")
        else:
            log.warning(f"   Reference validation: ✗ {len(self.broken_refs)} broken reference(s)")

        errors = [a for a in self.alerts if a["level"] == "ERROR"]
        warnings = [a for a in self.alerts if a["level"] == "WARNING"]
        if errors:
            log.error(f"   ⛔ {len(errors)} ERROR(s) — review merge_report.json")
        if warnings:
            log.warning(f"   ⚠  {len(warnings)} WARNING(s)")

        return str(self.output_dir)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3: Merge all schema JSONs → flat + nested")
    parser.add_argument("--input-dir",  default="phase2_extracted", help="Phase 2 output directory")
    parser.add_argument("--output-dir", default="phase3_merged",    help="Where to write merged files")
    args = parser.parse_args()

    if not Path(args.input_dir).exists():
        print(f"❌ Input directory not found: {args.input_dir}")
        print(f"   Run phase2_extract.py first.")
        sys.exit(1)

    merger = Phase3Merger(args.input_dir, args.output_dir)
    merger.run()
