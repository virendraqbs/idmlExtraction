"""
phase2_extract.py
=================
Phase 2: Uses Gemini Vision to extract data from the PDF and write
one populated JSON file per schema entity type.

Output files (in phase2_extracted/):
  resource.json, module.json, topic.json, lesson.json,
  activities.json, tasks.json, stems.json,
  standards.json, standards_blocks.json, images.json,
  pages.json, instructional_prompts.json,
  instructional_segments.json, primitives_used.json, enums_used.json

Usage:
  python phase2_extract.py --pdf path/to/lesson.pdf --api-key AIza...
  python phase2_extract.py --pdf path/to/lesson.pdf   # uses .env GEMINI_API_KEY
"""
import os
import sys
import json
import uuid
import time
import hashlib
import argparse
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("phase2_extracted")
CACHE_DIR  = Path("phase2_cache")

def gen_uuid() -> str:
    return str(uuid.uuid4())

def compute_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

# ── Gemini helpers ─────────────────────────────────────────────────────────────

def init_gemini(api_key: str, model: str):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=model,
        generation_config={"temperature": 0.1, "max_output_tokens": 8192},
        system_instruction=(
            "You are a structured data extractor for Carnegie Learning educational PDFs. "
            "Return ONLY valid JSON. No markdown fences, no explanation."
        )
    )

def call_gemini(model, prompt: str, image, page_num: int, cache_key: str) -> dict:
    """Call Gemini with caching and retry."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        log.info(f"  Page {page_num}: cache hit")
        with open(cache_file) as f:
            return json.load(f)

    for attempt in range(1, 4):
        try:
            time.sleep(4.5)   # respect 15 RPM for Flash
            log.info(f"  Page {page_num}: Gemini call (attempt {attempt})")
            response = model.generate_content([prompt, image])
            text = response.text

            # Strip accidental fences
            text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
            text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

            data = json.loads(text)
            CACHE_DIR.mkdir(exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            return data

        except Exception as e:
            if attempt == 3:
                log.error(f"  Page {page_num}: failed — {e}")
                return {}
            wait = 4 * (2 ** attempt)
            log.warning(f"  Page {page_num}: attempt {attempt} failed, retrying in {wait}s — {e}")
            time.sleep(wait)
    return {}

# ── Per-schema Gemini prompts ──────────────────────────────────────────────────

RESOURCE_PROMPT = """
Extract resource-level metadata from this Carnegie Learning textbook page.
Return ONLY this JSON (null for anything not visible on this page):
{
  "title": "<full book title>",
  "subtitle": "<subtitle if visible>",
  "series": "<series name>",
  "gradeLevel": "<HS | K | 1-12>",
  "publisher": "<publisher name>",
  "resourceType": "STUDENT_RESOURCE_BOOK",
  "copyrightYear": <integer or null>,
  "edition": "<edition string or null>",
  "state": "<2-letter state code or null>",
  "language": "en",
  "locale": "en-US"
}
"""

LESSON_PROMPT = """
Extract lesson metadata from this Carnegie Learning textbook page.
Return ONLY this JSON (null for anything not visible):
{
  "lessonNumber": <integer or null>,
  "title": "<exact lesson title or null>",
  "subtitle": "<subtitle e.g. Recognizing Functions by Characteristics, or null>",
  "moduleNumber": <integer or null>,
  "moduleTitle": "<module title or null>",
  "topicNumber": <integer or null>,
  "topicTitle": "<topic title or null>",
  "learningGoals": ["<exact verbatim text of each My Learning Goals bullet>"],
  "lessonType": "CONCEPT_LESSON"
}
"""

STANDARDS_PROMPT = """
Extract ALL standards from this Carnegie Learning textbook page.
Return ONLY this JSON:
{
  "standardsBody": "<CA_CCSS | CCSS | TEKS | BEST or null>",
  "blockTitle": "<printed block title e.g. California High School or null>",
  "standardsTitle": "<e.g. Functions Standards or null>",
  "clusterTitle": "<e.g. Interpreting Functions or null>",
  "bigIdeaLabel": "<e.g. Big Idea or null>",
  "bigIdeaText": "<e.g. Features of Functions or null>",
  "standards": [
    {
      "standardNumber": "<printed number e.g. 4>",
      "code": "<derived code e.g. F-IF.4>",
      "fullText": "<complete standard text including ★ if present>",
      "hasModelingSymbol": <true|false>
    }
  ]
}
"""

ACTIVITIES_PROMPT = """
Extract ALL activities from this Carnegie Learning textbook page.
Return ONLY this JSON:
{
  "activities": [
    {
      "activityType": "<ACTIVATE|EXPLORE|REFLECT|PRACTICE_QUESTIONS>",
      "activityLabel": "<exact printed label e.g. Explore and Develop | Activity 1>",
      "title": "<exact activity title>",
      "habitsOfMind": ["<exact text of each Habits of Mind bullet>"],
      "directionLines": [
        {
          "sequenceNumber": <integer>,
          "type": "DIRECTION_LINE",
          "text": "<exact direction text>"
        }
      ],
      "tasks": [
        {
          "taskNumber": "<printed number as string>",
          "stemText": "<exact question/instruction text>",
          "ancillaryText": "<Remember or Think About box text adjacent to this task, or null>",
          "hasResponseArea": <true|false>,
          "responseAreaType": "<GRID|OPEN_ENDED|NUMBER_LINE|ALGORITHM_WORKSPACE|STEM|null>",
          "hasGraphGrid": <true|false>,
          "goOnlineNote": "<Go online prompt text or null>"
        }
      ]
    }
  ]
}
"""

IMAGES_PROMPT = """
Identify and describe ALL images on this Carnegie Learning textbook page.
Return ONLY this JSON:
{
  "images": [
    {
      "sequenceOnPage": <integer starting at 1>,
      "imageType": "<LESSON_COVER|ICON|INSTRUCTIONAL|TECHNICAL_ART|DECORATIVE|CHARACTER_SUPPORT>",
      "technicalArtType": "<NUMBER_LINES|BAR_GRAPHS|BAR_AND_LINE_GRAPHS|SHAPES_GRID|TABLES|null>",
      "altText": "<precise accessibility description — required for all non-decorative images>",
      "isDecorative": <true|false>,
      "containsGraph": <true|false>,
      "approximatePosition": "<TOP|MIDDLE|BOTTOM|LEFT_SIDEBAR|RIGHT_SIDEBAR>",
      "estimatedFilename": "<descriptive filename suggestion e.g. alg1-l5-p31-cover.jpg>"
    }
  ]
}
"""

PAGE_PROMPT = """
Identify the page type and all content blocks present on this Carnegie Learning textbook page.
Return ONLY this JSON:
{
  "pageNumber": <printed page number as integer>,
  "pageType": "<SRB_LESSON_INTRODUCTION_ACTIVATE|SRB_LESSON_EXPLORE|SRB_LESSON_EXPLORE_CONTINUED|SRB_LESSON_REFLECT|SPB_LESSON_PRACTICE>",
  "sidebars": [
    {
      "sequenceNumber": <integer>,
      "sidebarType": "<MAKE_A_CONNECTION|LEARNING_PROMPT|REMEMBER|THINK_ABOUT|GO_ONLINE|QUICK_CHECK>",
      "title": "<exact sidebar title>",
      "text": "<exact sidebar body text>"
    }
  ],
  "contentBlocksOrder": [
    {
      "sequenceNumber": <integer>,
      "blockType": "<LESSON_HEADER|IMAGE|LEARNING_GOALS|STANDARDS_BLOCK|SIDEBAR|ACTIVITY_HEADER|DIRECTION_LINE|TASK|GO_ONLINE_PROMPT>",
      "description": "<brief description of what this block contains>"
    }
  ]
}
"""

INSTRUCTIONAL_PROMPT_PROMPT = """
Extract any teacher instructional prompts visible on this Carnegie Learning textbook page.
These include: Habits of Mind boxes, Learning Goals panels, Go Online prompts, Materials Lists, etc.
Return ONLY this JSON:
{
  "instructionalPrompts": [
    {
      "instructionalPromptType": "<LEARNING_GOALS|HABITS_OF_MIND|STUDENT_LOOK_FORS|MULTILINGUAL_LEARNER_SUPPORT|DAILY_MATH_ROUTINES|TEACHER_STORY|MATERIALS_LIST|GO_ONLINE_PROMPT>",
      "title": "<exact title>",
      "content": "<single string content, or null if list form>",
      "contentItems": ["<list items if bullet list>"],
      "displayStyle": "<BOX|SIDEBAR|INLINE|CALLOUT>"
    }
  ]
}
"""

INSTRUCTIONAL_SEGMENT_PROMPT = """
Extract any teacher instructional segment guidance visible on this Carnegie Learning textbook page.
Return ONLY this JSON:
{
  "instructionalSegments": [
    {
      "instructionalSegmentType": "<INTRODUCTION|ABOUT_THE_MATH|SETTING_THE_STAGE|TASK|CLOSING|DIFFERENTIATION_STRATEGY|ONGOING_ASSESSMENT|LANGUAGE_LINK>",
      "directions": [
        {
          "sequenceNumber": <integer>,
          "text": "<teacher direction text>",
          "studentQuestions": [
            {
              "questionText": "<question to ask students>",
              "sampleAnswers": "<expected/sample answer>"
            }
          ]
        }
      ]
    }
  ]
}
"""

# ── Render pages ───────────────────────────────────────────────────────────────

def render_pages(pdf_path: str) -> list:
    from pdf2image import convert_from_path
    from PIL import Image as PILImage
    log.info(f"Rendering PDF pages...")
    images = convert_from_path(pdf_path, dpi=200, fmt="PNG")
    log.info(f"  {len(images)} pages rendered")
    return images  # list of PIL images

# ── Phase 2 main ───────────────────────────────────────────────────────────────

def run(pdf_path: str, api_key: str, model: str):
    OUTPUT_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)

    pdf_hash = compute_hash(pdf_path)
    log.info(f"PDF hash: {pdf_hash}")

    pages = render_pages(pdf_path)
    total_pages = len(pages)
    gemini = init_gemini(api_key, model)
    now = datetime.now(timezone.utc).isoformat()

    # Accumulators — one per schema type
    resource_data       = {}
    lesson_data         = {}
    module_data         = {}
    topic_data          = {}
    all_standards       = []
    all_std_blocks      = []
    all_activities      = []
    all_tasks           = []
    all_stems           = []
    all_images          = []
    all_pages           = []
    all_inst_prompts    = []
    all_inst_segments   = []

    # Fixed UUIDs so references are consistent across files
    resource_id     = gen_uuid()
    module_id       = gen_uuid()
    topic_id        = gen_uuid()
    lesson_id       = gen_uuid()
    std_block_id    = gen_uuid()
    std_id_map      = {}    # code → uuid
    act_id_map      = {}    # (page, seq) → uuid
    task_id_map     = {}    # (act_id, task_num) → uuid
    stem_id_map     = {}    # (task_id, seq) → uuid
    img_id_map      = {}    # (page, seq) → uuid
    page_id_map     = {}    # page_num → uuid

    log.info("Starting per-page extractions...")

    for page_num, page_image in enumerate(pages, start=1):
        log.info(f"Page {page_num}/{total_pages}")
        key = lambda suffix: f"{pdf_hash}_p{page_num:03d}_{suffix}"

        # ── Extract all schemas in parallel prompts for this page ──────────
        res_raw  = call_gemini(gemini, RESOURCE_PROMPT,               page_image, page_num, key("resource"))
        les_raw  = call_gemini(gemini, LESSON_PROMPT,                 page_image, page_num, key("lesson"))
        std_raw  = call_gemini(gemini, STANDARDS_PROMPT,              page_image, page_num, key("standards"))
        act_raw  = call_gemini(gemini, ACTIVITIES_PROMPT,             page_image, page_num, key("activities"))
        img_raw  = call_gemini(gemini, IMAGES_PROMPT,                 page_image, page_num, key("images"))
        pg_raw   = call_gemini(gemini, PAGE_PROMPT,                   page_image, page_num, key("page"))
        ip_raw   = call_gemini(gemini, INSTRUCTIONAL_PROMPT_PROMPT,   page_image, page_num, key("inst_prompt"))
        is_raw   = call_gemini(gemini, INSTRUCTIONAL_SEGMENT_PROMPT,  page_image, page_num, key("inst_segment"))

        # ── Resource (build once from first page that has it) ──────────────
        if not resource_data and res_raw.get("title"):
            resource_data = {
                "_schema": "schemas/resource/resource.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": resource_id,
                "resourceType": res_raw.get("resourceType", "STUDENT_RESOURCE_BOOK"),
                "title": res_raw.get("title"),
                "subtitle": res_raw.get("subtitle"),
                "series": res_raw.get("series"),
                "gradeLevel": res_raw.get("gradeLevel", "HS"),
                "publisher": res_raw.get("publisher"),
                "pages": [],
                "modules": [{"id": module_id, "type": "MODULE", "sequenceNumber": 1}],
                "standards": [],
                "metadata": {
                    "totalPages": total_pages,
                    "subjects": ["Mathematics"],
                    "publishingMetadata": {"status": "IN_PROGRESS", "lastModifiedDate": now},
                    "copyrightInfo": {
                        "year": res_raw.get("copyrightYear"),
                        "holder": res_raw.get("publisher"),
                        "statement": f"© {res_raw.get('publisher', 'Carnegie Learning, Inc.')}"
                    },
                    "localizationInfo": {
                        "language": res_raw.get("language", "en"),
                        "locale": res_raw.get("locale", "en-US"),
                        "state": res_raw.get("state", "CA")
                    }
                }
            }

        # ── Lesson (build once from first page that has it) ────────────────
        if not lesson_data and les_raw.get("lessonNumber"):
            lesson_data = {
                "_schema": "schemas/content/lesson.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": lesson_id,
                "topicId": topic_id,
                "lessonNumber": les_raw.get("lessonNumber"),
                "lessonType": les_raw.get("lessonType", "CONCEPT_LESSON"),
                "title": les_raw.get("title"),
                "lessonSummary": les_raw.get("subtitle"),
                "learningGoals": les_raw.get("learningGoals", []),
                "standardsBlock": std_block_id,
                "activities": [],
                "images": [],
                "metadata": {"pacingEstimate": {"value": 50, "unit": "MINUTES"}}
            }
            # Build module + topic from lesson context
            if not module_data:
                module_data = {
                    "_schema": "schemas/content/module.json",
                    "_phase": "PHASE_2_EXTRACTED",
                    "id": module_id,
                    "resourceId": resource_id,
                    "moduleNumber": les_raw.get("moduleNumber", 1),
                    "title": les_raw.get("moduleTitle", ""),
                    "moduleSummary": None,
                    "gradeLevel": res_raw.get("gradeLevel", "HS"),
                    "standardsBody": std_raw.get("standardsBody", "CA_CCSS"),
                    "topics": [{"id": topic_id, "type": "TOPIC", "sequenceNumber": 1}],
                    "images": [],
                    "metadata": {"pacingEstimate": {"value": 45, "unit": "DAYS"}}
                }
            if not topic_data:
                topic_data = {
                    "_schema": "schemas/content/topic.json",
                    "_phase": "PHASE_2_EXTRACTED",
                    "id": topic_id,
                    "moduleId": module_id,
                    "topicNumber": les_raw.get("topicNumber", 1),
                    "title": les_raw.get("topicTitle", les_raw.get("moduleTitle", "")),
                    "topicSummary": None,
                    "lessons": [{"id": lesson_id, "type": "LESSON", "sequenceNumber": les_raw.get("lessonNumber", 1)}],
                    "images": [],
                    "metadata": {"pacingEstimate": {"value": 9, "unit": "DAYS"}}
                }

        # ── Standards ──────────────────────────────────────────────────────
        seen_codes = {s["code"] for s in all_standards}
        block_std_refs = []
        for std in std_raw.get("standards", []):
            code = std.get("code", "")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            sid = std_id_map.get(code) or gen_uuid()
            std_id_map[code] = sid
            all_standards.append({
                "_schema": "schemas/standards/standard.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": sid,
                "body": std_raw.get("standardsBody", "CA_CCSS"),
                "code": code,
                "gradeLevel": res_raw.get("gradeLevel", "HS"),
                "domain": "Functions",
                "cluster": std_raw.get("clusterTitle", ""),
                "description": (std.get("fullText") or "")[:150],
                "fullText": std.get("fullText", ""),
                "hasModelingSymbol": std.get("hasModelingSymbol", False),
                "metadata": {
                    "officialUrl": "https://www.corestandards.org/Math/Content/HSF-IF/"
                }
            })
            block_std_refs.append({
                "id": sid, "type": "STANDARDS",
                "sequenceNumber": len(block_std_refs) + 1
            })

        if block_std_refs and not any(b["id"] == std_block_id for b in all_std_blocks):
            all_std_blocks.append({
                "_schema": "schemas/standards/standards-block.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": std_block_id,
                "body": std_raw.get("standardsBody", "CA_CCSS"),
                "gradeLevel": res_raw.get("gradeLevel", "HS"),
                "title": std_raw.get("blockTitle", ""),
                "standardsSubtitle": std_raw.get("clusterTitle", ""),
                "standards": block_std_refs,
                "conceptualOverlaySubtitle": std_raw.get("bigIdeaLabel", "Big Idea"),
                "conceptualOverlays": [
                    {"sequenceNumber": 1, "text": std_raw.get("bigIdeaText", "")}
                ] if std_raw.get("bigIdeaText") else [],
                "pageLocationHelpText": f"See student book page {page_num}"
            })

        # ── Activities → Tasks → Stems ────────────────────────────────────
        for act_seq, act in enumerate(act_raw.get("activities", []), start=1):
            act_id = act_id_map.get((page_num, act_seq)) or gen_uuid()
            act_id_map[(page_num, act_seq)] = act_id

            act_task_refs = []
            for task in act.get("tasks", []):
                task_num = str(task.get("taskNumber", "1"))
                task_id = task_id_map.get((act_id, task_num)) or gen_uuid()
                task_id_map[(act_id, task_num)] = task_id

                stem_id = stem_id_map.get((task_id, 1)) or gen_uuid()
                stem_id_map[(task_id, 1)] = stem_id

                has_resp = task.get("hasResponseArea", False)
                ra_id = gen_uuid() if has_resp else None

                all_stems.append({
                    "_schema": "schemas/content/stem.json",
                    "_phase": "PHASE_2_EXTRACTED",
                    "id": stem_id,
                    "taskId": task_id,
                    "stemType": "TEXT_WITH_RESPONSE_AREA" if has_resp else "TEXT_ONLY",
                    "stemText": task.get("stemText", ""),
                    "ancillaryText": task.get("ancillaryText"),
                    "image": None,
                    "responseArea": ra_id,
                    "_meta": {
                        "responseAreaType": task.get("responseAreaType"),
                        "hasGraphGrid": task.get("hasGraphGrid", False),
                        "goOnlineNote": task.get("goOnlineNote")
                    }
                })

                stem_text_lower = (task.get("stemText") or "").lower()
                if any(w in stem_text_lower for w in ["sketch", "create", "draw", "describe"]):
                    task_type = "OPEN_ENDED"
                elif task.get("hasGraphGrid"):
                    task_type = "OPEN_ENDED"
                else:
                    task_type = "SHORT_ANSWER"

                all_tasks.append({
                    "_schema": "schemas/content/task.json",
                    "_phase": "PHASE_2_EXTRACTED",
                    "id": task_id,
                    "activityId": act_id,
                    "taskNumber": task_num,
                    "taskType": task_type,
                    "stems": [{"id": stem_id, "type": "STEM", "sequenceNumber": 1}],
                    "scaffolding": []
                })
                act_task_refs.append({"id": task_id, "type": "TASK", "sequenceNumber": int(task_num)})

            goals = []
            if act.get("habitsOfMind"):
                goals.append({
                    "id": gen_uuid(), "type": "GOALS",
                    "goalType": "HABITS_OF_MIND",
                    "goalItems": act["habitsOfMind"]
                })

            all_activities.append({
                "_schema": "schemas/content/activity.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": act_id,
                "lessonId": lesson_id,
                "activityType": act.get("activityType", "EXPLORE"),
                "activityLabel": act.get("activityLabel"),
                "title": act.get("title"),
                "directions": act.get("directionLines", []),
                "goals": goals,
                "scaffolding": [],
                "images": [],
                "tasks": act_task_refs,
                "metadata": {
                    "pacingEstimate": {"value": max(10, len(act_task_refs) * 5), "unit": "MINUTES"},
                    "sourcePage": page_num
                }
            })
            if lesson_data:
                lesson_data["activities"].append({
                    "id": act_id, "type": "ACTIVITY", "sequenceNumber": len(lesson_data["activities"]) + 1
                })

        # ── Images ────────────────────────────────────────────────────────
        for img_seq, img in enumerate(img_raw.get("images", []), start=1):
            img_id = img_id_map.get((page_num, img_seq)) or gen_uuid()
            img_id_map[(page_num, img_seq)] = img_id
            fname = img.get("estimatedFilename") or f"img-p{page_num}-{img_seq}.png"
            all_images.append({
                "_schema": "schemas/media/image.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": img_id,
                "imageType": img.get("imageType", "INSTRUCTIONAL"),
                "technicalArtType": img.get("technicalArtType"),
                "filename": fname,
                "altText": img.get("altText"),
                "dimensions": {"width": None, "height": None, "unit": "PIXELS"},
                "format": "PNG",
                "usage": {
                    "usedInPages": [page_num],
                    "usedInActivities": [], "usedInTasks": [],
                    "isReusable": False
                },
                "accessibility": {
                    "isDecorative": img.get("isDecorative", False),
                    "longDescription": None
                },
                "metadata": {
                    "tags": [f"page-{page_num}"],
                    "notes": f"Extracted from page {page_num}, sequence {img_seq}. Position: {img.get('approximatePosition')}"
                }
            })

        # ── Page ──────────────────────────────────────────────────────────
        page_id = page_id_map.get(page_num) or gen_uuid()
        page_id_map[page_num] = page_id

        # Build contentBlocks from Gemini's ordering + resolve IDs
        content_blocks = []
        for cb in pg_raw.get("contentBlocksOrder", []):
            bt = cb.get("blockType", "")
            block = {
                "sequenceNumber": cb.get("sequenceNumber", len(content_blocks) + 1),
                "blockType": bt,
                "contentId": None,
                "contentType": None,
                "content": None
            }
            if bt == "IMAGE":
                # assign first unassigned image on this page
                for (pn, seq), iid in img_id_map.items():
                    if pn == page_num:
                        block["contentId"] = iid
                        block["contentType"] = "IMAGE"
                        break
            elif bt == "STANDARDS_BLOCK":
                block["contentId"] = std_block_id
                block["contentType"] = "STANDARDS_BLOCK"
            elif bt == "ACTIVITY_HEADER":
                for (pn, seq), aid in act_id_map.items():
                    if pn == page_num:
                        block["contentId"] = aid
                        block["contentType"] = "ACTIVITY"
                        break
            elif bt == "SIDEBAR":
                sidebars = pg_raw.get("sidebars", [])
                sidebar_idx = len([b for b in content_blocks if b["blockType"] == "SIDEBAR"])
                if sidebar_idx < len(sidebars):
                    sb = sidebars[sidebar_idx]
                    block["content"] = {
                        "sidebarType": sb.get("sidebarType"),
                        "title": sb.get("title"),
                        "text": sb.get("text")
                    }
            elif bt == "LEARNING_GOALS":
                block["content"] = {"goals": lesson_data.get("learningGoals", [])}

            content_blocks.append(block)

        lc = les_raw.get
        all_pages.append({
            "_schema": "schemas/resource/page.json",
            "_phase": "PHASE_2_EXTRACTED",
            "id": page_id,
            "resourceId": resource_id,
            "pageType": pg_raw.get("pageType", "SRB_LESSON_EXPLORE"),
            "contentBlocks": content_blocks,
            "metadata": {
                "pageNumberRepresentations": {"numeric": pg_raw.get("pageNumber", page_num)},
                "lessonContext": {
                    "moduleNumber": les_raw.get("moduleNumber", 1),
                    "moduleTitle": les_raw.get("moduleTitle"),
                    "topicNumber": les_raw.get("topicNumber", 1),
                    "topicTitle": les_raw.get("topicTitle"),
                    "lessonNumber": les_raw.get("lessonNumber"),
                    "lessonTitle": les_raw.get("title")
                }
            }
        })
        if resource_data:
            resource_data["pages"].append({"id": page_id, "type": "PAGES", "sequenceNumber": page_num})

        # ── Instructional Prompts ─────────────────────────────────────────
        for ip in ip_raw.get("instructionalPrompts", []):
            all_inst_prompts.append({
                "_schema": "schemas/instructional-guide/instructional-prompt.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": gen_uuid(),
                "studentContentReferenceId": lesson_id,
                "instructionalPromptType": ip.get("instructionalPromptType"),
                "title": ip.get("title"),
                "content": ip.get("content"),
                "contentItems": ip.get("contentItems", []),
                "images": [],
                "metadata": {"displayStyle": ip.get("displayStyle", "BOX")}
            })

        # ── Instructional Segments ────────────────────────────────────────
        for iseg in is_raw.get("instructionalSegments", []):
            all_inst_segments.append({
                "_schema": "schemas/instructional-guide/instructional-segment.json",
                "_phase": "PHASE_2_EXTRACTED",
                "id": gen_uuid(),
                "studentContentReferenceId": lesson_id,
                "instructionalSegmentType": iseg.get("instructionalSegmentType"),
                "directions": iseg.get("directions", []),
                "images": [],
                "_meta": {"sourcePage": page_num}
            })

    # ── Write individual JSON files ────────────────────────────────────────────
    log.info("Writing individual schema JSON files...")

    def write(filename: str, data):
        path = OUTPUT_DIR / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"  Wrote: {path} ({len(json.dumps(data))} bytes)")

    write("01_primitives_used.json", {
        "_schema": "schemas/common/primitives.json",
        "_phase": "PHASE_2_EXTRACTED",
        "_description": "All UUIDs and Reference objects generated during this extraction",
        "resource_id": resource_id,
        "module_id": module_id,
        "topic_id": topic_id,
        "lesson_id": lesson_id,
        "standards_block_id": std_block_id,
        "standard_ids": std_id_map,
        "activity_ids": {f"p{k[0]}_seq{k[1]}": v for k, v in act_id_map.items()},
        "task_ids": {f"act_{k[0]}_task_{k[1]}": v for k, v in task_id_map.items()},
        "image_ids": {f"p{k[0]}_seq{k[1]}": v for k, v in img_id_map.items()},
        "page_ids": page_id_map
    })

    write("02_enums_used.json", {
        "_schema": "schemas/common/enums.json",
        "_phase": "PHASE_2_EXTRACTED",
        "_description": "Enum values observed in this extraction",
        "standardsBody": module_data.get("standardsBody"),
        "resourceType": resource_data.get("resourceType"),
        "activityTypes": list({a["activityType"] for a in all_activities}),
        "taskTypes": list({t["taskType"] for t in all_tasks}),
        "stemTypes": list({s["stemType"] for s in all_stems}),
        "imageTypes": list({i["imageType"] for i in all_images}),
        "pageTypes": list({p["pageType"] for p in all_pages})
    })

    write("03_resource.json", resource_data)
    write("04_module.json", module_data)
    write("05_topic.json", topic_data)
    write("06_lesson.json", lesson_data)
    write("07_activities.json", {"_schema": "schemas/content/activity.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_activities), "activities": all_activities})
    write("08_tasks.json", {"_schema": "schemas/content/task.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_tasks), "tasks": all_tasks})
    write("09_stems.json", {"_schema": "schemas/content/stem.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_stems), "stems": all_stems})
    write("10_standards.json", {"_schema": "schemas/standards/standard.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_standards), "standards": all_standards})
    write("11_standards_blocks.json", {"_schema": "schemas/standards/standards-block.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_std_blocks), "standardsBlocks": all_std_blocks})
    write("12_images.json", {"_schema": "schemas/media/image.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_images), "images": all_images})
    write("13_pages.json", {"_schema": "schemas/resource/page.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_pages), "pages": all_pages})
    write("14_instructional_prompts.json", {"_schema": "schemas/instructional-guide/instructional-prompt.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_inst_prompts), "instructionalPrompts": all_inst_prompts})
    write("15_instructional_segments.json", {"_schema": "schemas/instructional-guide/instructional-segment.json", "_phase": "PHASE_2_EXTRACTED", "_count": len(all_inst_segments), "instructionalSegments": all_inst_segments})

    log.info(f"\n✅ Phase 2 complete — {len(list(OUTPUT_DIR.glob('*.json')))} files in {OUTPUT_DIR}/")
    return str(OUTPUT_DIR)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Phase 2: Gemini PDF → individual schema JSONs")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY", ""), help="Gemini API key")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    args = parser.parse_args()

    if not args.api_key:
        print("❌ Error: --api-key required or set GEMINI_API_KEY in .env")
        sys.exit(1)

    run(args.pdf, args.api_key, args.model)
