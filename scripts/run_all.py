"""
run_all.py
==========
Runs all three phases in sequence:
  Phase 1 → Verifies sample JSON files exist (phase1_samples/)
  Phase 2 → Gemini extraction → individual JSONs (phase2_extracted/)
  Phase 3 → Merge → flat + nested (phase3_merged/)

Usage:
  python run_all.py --pdf path/to/lesson.pdf --api-key AIza...
  python run_all.py --pdf path/to/lesson.pdf   # uses .env
  python run_all.py --skip-phase2              # merge existing phase2 output only
"""
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def check_phase1():
    samples_dir = Path("phase1_samples")
    if not samples_dir.exists():
        log.error("phase1_samples/ directory not found.")
        log.error("Expected 15 sample JSON files to be present.")
        return False
    files = list(samples_dir.glob("*.json"))
    log.info(f"Phase 1 ✓ — {len(files)} sample schema files found in phase1_samples/")
    for f in sorted(files):
        log.info(f"  {f.name}")
    return True


def run_phase2(pdf_path: str, api_key: str, model: str):
    sys.path.insert(0, str(Path(__file__).parent))
    from phase2_extract import run
    log.info(f"\n{'='*60}\nPHASE 2: Gemini Extraction\n{'='*60}")
    return run(pdf_path, api_key, model)


def run_phase3(input_dir: str = "phase2_extracted", output_dir: str = "phase3_merged"):
    sys.path.insert(0, str(Path(__file__).parent))
    from phase3_merge import Phase3Merger
    log.info(f"\n{'='*60}\nPHASE 3: Merging\n{'='*60}")
    merger = Phase3Merger(input_dir, output_dir)
    return merger.run()


def print_summary(output_dir: str):
    report_path = Path(output_dir) / "merge_report.json"
    if not report_path.exists():
        return
    with open(report_path) as f:
        report = json.load(f)

    stats = report.get("summary", {})
    readiness = report.get("readiness", "UNKNOWN")
    readiness_icon = "✅" if readiness == "READY_FOR_REVIEW" else "⚠️"

    print(f"""
╔══════════════════════════════════════════════════════╗
║         CL THREE-PHASE EXTRACTION COMPLETE           ║
╠══════════════════════════════════════════════════════╣
║  Phase 1: Sample JSONs          phase1_samples/      ║
║  Phase 2: Extracted JSONs       phase2_extracted/    ║
║  Phase 3: Merged JSONs          phase3_merged/       ║
╠══════════════════════════════════════════════════════╣
║  Activities:   {str(stats.get('activitiesCount',0)).ljust(6)}  Tasks:    {str(stats.get('tasksCount',0)).ljust(6)}           ║
║  Stems:        {str(stats.get('stemsCount',0)).ljust(6)}  Standards:{str(stats.get('standardsCount',0)).ljust(6)}           ║
║  Images:       {str(stats.get('imagesCount',0)).ljust(6)}  Pages:    {str(stats.get('pagesCount',0)).ljust(6)}           ║
╠══════════════════════════════════════════════════════╣
║  Errors:    {str(stats.get('errorCount',0)).ljust(4)}    Warnings: {str(stats.get('warningCount',0)).ljust(4)}                    ║
║  Status:  {readiness_icon}  {readiness.ljust(36)} ║
╚══════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run all 3 CL schema extraction phases")
    parser.add_argument("--pdf", help="Path to PDF file (required for Phase 2)")
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY", ""), help="Gemini API key")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    parser.add_argument("--skip-phase2", action="store_true", help="Skip Phase 2, merge existing phase2_extracted/ output")
    args = parser.parse_args()

    start = datetime.now()

    # Phase 1
    log.info(f"\n{'='*60}\nPHASE 1: Sample Schema Files\n{'='*60}")
    if not check_phase1():
        sys.exit(1)

    # Phase 2
    if not args.skip_phase2:
        if not args.pdf:
            print("❌ --pdf is required for Phase 2. Use --skip-phase2 to merge existing output.")
            sys.exit(1)
        if not args.api_key:
            print("❌ --api-key required or set GEMINI_API_KEY in .env")
            sys.exit(1)
        if not Path(args.pdf).exists():
            print(f"❌ PDF not found: {args.pdf}")
            sys.exit(1)
        run_phase2(args.pdf, args.api_key, args.model)
    else:
        log.info("Phase 2 skipped — using existing phase2_extracted/")

    # Phase 3
    output = run_phase3()

    elapsed = (datetime.now() - start).seconds
    log.info(f"\nTotal time: {elapsed}s")
    print_summary(output)
