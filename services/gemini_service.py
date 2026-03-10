"""
services/gemini_service.py — Gemini Vision API service.

Responsibilities:
- Health-check the API key on startup
- Run page-image extraction with retry / back-off
- Parse and clean raw Gemini JSON responses
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from config import config

log = logging.getLogger(__name__)

# ── Master extraction prompt ──────────────────────────────────────────────────
MASTER_PROMPT = """You are a precision structured-data extractor for Carnegie Learning educational PDFs.
You receive ONE page image. Extract EVERYTHING visible — text, math, images, graphs, sidebars, response areas.

═══ OUTPUT RULES ═══
- Return ONLY valid JSON. Zero markdown fences. Zero explanation. Zero trailing commas.
- Use null for invisible/absent scalar fields. Use [] for absent arrays.
- All id fields must be empty string "".
- Math expressions: wrap ALL inline math in $...$ and display math in $$...$$.
- Preserve EXACT wording. For multi-line text join with \\n.

═══ STANDARDS PAGE DETECTION ═══
A page is a STANDARDS_PAGE if it shows educational standards for a state or national body.
Indicators: a bold header like "California High School", "Texas", a state flag/seal image,
sections titled "Big Ideas", "Standards", "Interpreting Functions", numbered standard items, etc.

For STANDARDS_PAGE pages you MUST fully populate the standards_block object:
- title: the main heading (e.g. "California High School")
- standards_body: one of CCSS | CA_CCSS | TEKS | BEST  (infer from context)
- grade_level: e.g. "HS", "K", "3" — infer from the header
- subtitle: sub-heading under title if present (e.g. "Functions Standards")
- conceptual_overlay_subtitle: heading above Big Ideas if present
- big_ideas: array of strings — each "Big Idea" bullet (e.g. ["Function Investigations", "Features of Functions"])
- standards: array of standard items found on the page. Each standard has:
    code: the standard code (e.g. "HSF-IF.A.1", "F-IF.1")
         If no explicit code is visible, synthesize one from the domain+cluster+number.
    full_text: the complete text of the standard — preserve EXACT wording including italics markers
    domain: the domain heading (e.g. "Interpreting Functions")
    cluster: the cluster heading if present (e.g. "Understand the concept of a function")
    has_modeling_symbol: true if a star ★ symbol appears next to the standard

═══ SCAFFOLDING ═══
Detect EVERY sidebar callout, prompt box, speech bubble, or support element on the page.
Include them in the enclosing task's "scaffolding" array (or the activity's if not task-specific).

scaffolding_type mapping — use the FIRST match:
  Heading/label "Take Note"        → HINT
  Heading/label "Ask Yourself"     → GUIDING_QUESTION
  Heading/label "Learning Prompt"  → GUIDING_QUESTION
  Heading/label "Habits of Mind"   → STRATEGY_PROMPT
  "SMP" sidebar label              → STRATEGY_PROMPT
  Heading/label "Remember"         → REMINDER
  Character mascot / speech bubble → CHARACTER_SUPPORT
  Solved/worked example as model   → WORKED_EXAMPLE

content: EXACT full text of the callout — do not paraphrase.
has_image: true if a character illustration or diagram is inside the box, else false.

═══ RESPONSE AREAS ═══
For every task with a blank answer space, box, grid, or number line:
  has_response_area: true
  response_area_type (pick one):
    OPEN_ENDED          → multi-line writing (explain, describe, justify, list)
    SHORT_ANSWER        → single-line / small box (letter, number, brief word)
    GRID                → coordinate grid or fill-in table
    NUMBER_LINE         → printed number line with tick marks
    ALGORITHM_WORKSPACE → column-arithmetic structured workspace
  response_area_description: one sentence — what does the student write here?
  response_area_lines: integer ≥ 1 — count of blank lines printed (estimate 3 if lines not countable)
  allowed_tools: [] unless a tool icon is printed near the task; then include from:
    "CALCULATOR" | "RULER" | "PROTRACTOR" | "COMPASS" | "MANIPULATIVES"

═══ PRACTICE SECTION DETECTION ═══
Detect whether the page contains an independent/take-home practice section.
practice_section_type rules (null when no such section is present):
  "Practice and Apply" / "Independent Practice" heading → LESSON_PRACTICE
  Reference to LiveHint, online platform, QR code       → INTERACTIVE_PRACTICE
  Section addressed to families / parents               → FAMILY_GUIDE

═══ ACTIVITY TYPE DETECTION ═══
Use these rules to set activity_type (pick the FIRST match):
  ACTIVATE   → page_type SRB_LESSON_INTRODUCTION_ACTIVATE or activity is the opening/warm-up activity
  EXPLORE    → page_type SRB_LESSON_EXPLORE; main investigation or problem-solving activity
  REFLECT    → page_type SRB_LESSON_REFLECT; closing/reflection activity
  KEY_TERMS  → section heading is "Key Terms", "Vocabulary", "Glossary Terms" or similar vocabulary list
  KEY_IDEAS  → section heading is "Key Ideas", "Big Ideas", "Summary" or conceptual summary bullets
  PRACTICE_QUESTIONS → section is numbered practice problems / exercises after the main lesson
  PRACTICE_CONVERSATION_STARTERS → section provides discussion prompts or sentence starters for conversation
  GAMES_AND_ADDITIONAL_RESOURCES → section lists games, optional activities, or supplemental resources
Do NOT default to EXPLORE when a more specific type clearly applies.

═══ DIRECTION LINES vs STEM TEXT ═══
direction_lines: ONLY include standalone instructional directions that appear BEFORE the numbered tasks
  and address the student as a group (e.g. "Work with your partner to...", "Use the graph to answer...").
  A direction line is NEVER the same as a task's stem text.
tasks[].stem_text: the exact question or problem text for ONE task/sub-task.
RULE: If a sentence functions as BOTH a direction and the first task's stem, put it ONLY in stem_text.
  Do NOT copy the same sentence into both direction_lines and stem_text.

═══ MODULE AND TOPIC SUMMARIES ═══
When the page shows a module or topic overview (e.g. "About this module", "In this topic", summary paragraph under a module/topic heading), extract that text:
- lesson.module_summary: summary or description of the module when visible.
- lesson.topic_summary: summary or description of the topic when visible.
Use null when no such text is on the page.

═══ IMAGE EXTRACTION (CL-Json-Schema media/image) ═══
For EVERY image, graph, chart, diagram, icon on the page output an object with:

Required / inferred:
- id: ""
- image_type: one of MODULE_COVER | TOPIC_COVER | LESSON_COVER | INSTRUCTIONAL | DECORATIVE | TECHNICAL_ART | CHARACTER_SUPPORT | MANIPULATIVE | ICON
- filename: "" (leave empty; no file from PDF extraction)
- alt_text: alternative text for accessibility; use "" only if image_type is DECORATIVE
- description: full visual description (labels, axis values, plotted points for graphs)

When image_type is TECHNICAL_ART, set technical_art_type to one of:
  NUMBER_LINES | BAR_GRAPHS | WOLS | SHAPES_OUTLINED | SHAPES_FILLED | SHAPES_3D | TABLES | CLOCKS | SHAPES_GRID | PLACE_VALUE | CROSS_NUMBER_PUZZLES | BAR_AND_LINE_GRAPHS | COUNTING_CHART | SPINNER_CHARTS | SHAPES_GRIDS_AND_COUNTERS | SHAPES_ANGLE_MEASUREMENTS

Optional (extract when visible):
- title: image title or name if shown
- caption: caption text below the image
- dimensions: { "width": null, "height": null, "unit": "PIXELS" } or null; estimate if size is obvious
- format: null or one of PNG | JPG | JPEG | SVG | GIF | WEBP if inferable
- accessibility: { "is_decorative": false, "long_description": null } — set long_description to extended description for complex diagrams; is_decorative true only for purely decorative images

Graph/response-area (keep):
- contains_graph: true if coordinate plane / number line / grid
- is_response_area: true for blank planes, grids, lines for student writing
- response_area_type: COORDINATE_PLANE | GRID | NUMBER_LINE | TABLE | OPEN_LINE | BOX when applicable
- position: TOP_LEFT | TOP_CENTER | TOP_RIGHT | MIDDLE_LEFT | MIDDLE_CENTER | MIDDLE_RIGHT | BOTTOM_LEFT | BOTTOM_CENTER | BOTTOM_RIGHT | LEFT_SIDEBAR | RIGHT_SIDEBAR | FULL_WIDTH
- graph_details: { "x_axis_label": null, "x_axis_range": null, "y_axis_label": null, "y_axis_range": null, "plotted_elements": [], "grid_type": null }; fill when contains_graph is true

═══ RETURN EXACTLY THIS JSON ═══
{
  "page_number": null,
  "page_type": "SRB_LESSON_INTRODUCTION | SRB_LESSON_ACTIVATE | SRB_LESSON_EXPLORE | SRB_LESSON_EXPLORE_CONTINUED | SRB_LESSON_REFLECT | SPB_PRACTICE | STANDARDS_PAGE | NON_CONTENT | UNKNOWN",
  "lesson": {
    "lesson_number": null, "title": null, "lesson_summary": null,
    "learning_goals": [], "module_title": null, "module_number": null,
    "topic_title": null, "topic_number": null, "module_summary": null, "topic_summary": null
  },
  "standards_block": {
    "title": null, "standards_body": null, "grade_level": null,
    "subtitle": null, "conceptual_overlay_subtitle": null, "big_ideas": [],
    "standards": [{"code": "", "full_text": "", "domain": null, "cluster": null, "has_modeling_symbol": false}]
  },
  "activities": [{
    "id": "", "activity_type": "ACTIVATE | EXPLORE | REFLECT | KEY_TERMS | KEY_IDEAS | PRACTICE_QUESTIONS | PRACTICE_CONVERSATION_STARTERS | GAMES_AND_ADDITIONAL_RESOURCES",
    "title": "", "sequence_number": 1,
    "habits_of_mind": [],
    "direction_lines": [{"sequence_number": 1, "text": ""}],
    "tasks": [{
      "id": "", "task_number": "", "task_type": "OPEN_ENDED | SHORT_ANSWER | COMPLETION | MULTIPLE_CHOICE | WORD_PROBLEM | STRATEGY_ANALYSIS",
      "stem_text": "", "ancillary_text": null,
      "has_response_area": false,
      "response_area_type": "OPEN_ENDED | SHORT_ANSWER | GRID | NUMBER_LINE | ALGORITHM_WORKSPACE",
      "response_area_description": null,
      "response_area_lines": null,
      "allowed_tools": [],
      "has_graph": false, "sub_tasks": [],
      "scaffolding": [{
        "scaffolding_type": "HINT | GUIDING_QUESTION | STRATEGY_PROMPT | REMINDER | CHARACTER_SUPPORT | WORKED_EXAMPLE",
        "content": "", "has_image": false
      }]
    }]
  }],
  "practice_section": {
    "title": null,
    "practice_section_type": "LESSON_PRACTICE | INTERACTIVE_PRACTICE | FAMILY_GUIDE"
  },
  "images": [{
    "id": "", "sequence_on_page": 1, "image_type": "", "filename": "",
    "technical_art_type": null, "alt_text": "", "caption": null, "title": null,
    "description": "", "dimensions": null, "format": null,
    "accessibility": { "is_decorative": false, "long_description": null },
    "position": "", "contains_graph": false, "is_response_area": false, "response_area_type": null,
    "graph_details": {
      "x_axis_label": null, "x_axis_range": null, "y_axis_label": null, "y_axis_range": null,
      "plotted_elements": [], "grid_type": null
    }
  }],
  "instructional_prompts": [{
    "id": "",
    "prompt_type": "CULTIVATE_CONNECTIONS | STUDENT_LOOK_FORS | HABITS_OF_MIND | LEARNING_GOALS | MULTILINGUAL_LEARNER | DAILY_MATH_ROUTINES | TEACHER_STORY | MATERIALS_LIST | GO_ONLINE | REMEMBER | THINK_ABOUT",
    "display_style": "SIDEBAR | CALLOUT | BOX | INLINE",
    "title": null, "content": null, "content_items": []
  }],
  "page_layout": {
    "has_sidebar": false, "sidebar_position": null,
    "column_count": 1, "content_order": []
  }
}

If this page has NO lesson content (table of contents, glossary, blank),
return page_type "NON_CONTENT" and null/[] for everything else."""

# Retry back-off delays (seconds) for rate-limit errors
BACKOFF_SECONDS = (10, 20, 40, 60)
MAX_ATTEMPTS = 4


class GeminiService:
    """Thin wrapper around google-generativeai for CL Pipeline extraction."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        import google.generativeai as genai

        self._api_key = api_key or config.GEMINI_API_KEY
        genai.configure(api_key=self._api_key)
        self._genai = genai

    # ── Public API ────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """
        Verify the API key is valid by running a minimal generation call.
        Returns True on success, raises RuntimeError on failure.
        """
        try:
            model = self._genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                generation_config={"temperature": 0.0, "max_output_tokens": 10},
            )
            resp = model.generate_content("Reply with exactly one word: OK")
            text = (resp.text or "").strip().upper()
            if "OK" not in text and len(text) > 30:
                raise RuntimeError(f"Unexpected health-check response: {text!r}")
            return True
        except Exception as exc:
            raise RuntimeError(f"Gemini health check failed: {exc}") from exc

    def extract_page(self, page_image: Any, page_number: int) -> tuple[dict, dict]:
        """
        Send one page image to Gemini and return (parsed_data, report).

        The report dict always contains:
            page, attempts, status ("ok"|"failed"), errors, elapsed_ms
        """
        model = self._genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.1, "max_output_tokens": 16384},
        )

        last_error: Optional[Exception] = None
        errors: list[str] = []
        t0 = time.time()

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response  = model.generate_content([MASTER_PROMPT, page_image])
                raw_text  = (response.text or "").strip()
                cleaned   = _strip_fences(raw_text)
                data      = json.loads(cleaned)
                data["page_number"] = data.get("page_number") or page_number
                elapsed = int((time.time() - t0) * 1000)
                report = {
                    "page": page_number,
                    "attempts": attempt,
                    "status": "ok",
                    "pageType": data.get("page_type"),
                    "errors": errors,
                    "elapsed_ms": elapsed,
                }
                return data, report

            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()
                errors.append(f"attempt {attempt}: {exc}")

                if _is_rate_limit(msg):
                    delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
                    log.warning("Rate limit on page %d attempt %d — waiting %ds", page_number, attempt, delay)
                    time.sleep(delay)
                else:
                    log.warning("Page %d attempt %d error: %s", page_number, attempt, exc)
                    time.sleep(3)

        elapsed = int((time.time() - t0) * 1000)
        log.error("Page %d failed after %d attempts: %s", page_number, MAX_ATTEMPTS, last_error)
        report = {
            "page": page_number,
            "attempts": MAX_ATTEMPTS,
            "status": "failed",
            "pageType": "UNKNOWN",
            "errors": errors,
            "elapsed_ms": elapsed,
        }
        return _empty_page(page_number), report


# ── Private helpers ───────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove optional ```json … ``` markdown fences from a Gemini response."""
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
    return text.strip()


def _is_rate_limit(error_msg: str) -> bool:
    return any(k in error_msg for k in ("429", "rate", "quota", "exhausted"))


def _empty_page(page_number: int) -> dict:
    return {
        "page_number":         page_number,
        "page_type":           "UNKNOWN",
        "lesson":              {},
        "standards_block":     None,
        "activities":          [],
        "images":              [],
        "instructional_prompts": [],
        "page_layout":         None,
        "practice_section":    None,
    }
