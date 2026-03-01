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

═══ IMAGE & GRAPH EXTRACTION ═══
For EVERY image, graph, chart, diagram, icon on the page:
1. imageType: LESSON_COVER | INSTRUCTIONAL | TECHNICAL_ART | DECORATIVE | ICON | CHARACTER_SUPPORT
2. If coordinate plane / number line / grid: containsGraph: true
3. Describe ALL visible labels, axis values, plotted points precisely in description.
4. Student response areas (blank planes, grids, lines for writing): isResponseArea: true
   responseAreaType: COORDINATE_PLANE | GRID | NUMBER_LINE | TABLE | OPEN_LINE | BOX
5. position: TOP_LEFT | TOP_CENTER | TOP_RIGHT | MIDDLE_LEFT | MIDDLE_CENTER | MIDDLE_RIGHT
             | BOTTOM_LEFT | BOTTOM_CENTER | BOTTOM_RIGHT | LEFT_SIDEBAR | RIGHT_SIDEBAR | FULL_WIDTH

═══ RETURN EXACTLY THIS JSON ═══
{
  "page_number": null,
  "page_type": "SRB_LESSON_INTRODUCTION | SRB_LESSON_ACTIVATE | SRB_LESSON_EXPLORE | SRB_LESSON_EXPLORE_CONTINUED | SRB_LESSON_REFLECT | SPB_PRACTICE | STANDARDS_PAGE | NON_CONTENT | UNKNOWN",
  "lesson": {
    "lesson_number": null, "title": null, "lesson_summary": null,
    "learning_goals": [], "module_title": null, "module_number": null,
    "topic_title": null, "topic_number": null
  },
  "standards_block": {
    "title": null, "standards_body": null, "grade_level": null,
    "subtitle": null, "conceptual_overlay_subtitle": null, "big_ideas": [],
    "standards": [{"code": "", "full_text": "", "domain": null, "cluster": null, "has_modeling_symbol": false}]
  },
  "activities": [{
    "id": "", "activity_type": "ACTIVATE | EXPLORE | REFLECT | PRACTICE",
    "activity_label": "", "title": "", "sequence_number": 1,
    "habits_of_mind": [],
    "direction_lines": [{"sequence_number": 1, "text": ""}],
    "tasks": [{
      "id": "", "task_number": "", "stem_text": "", "ancillary_text": null,
      "has_response_area": false, "response_area_type": null,
      "has_graph": false, "sub_tasks": []
    }]
  }],
  "images": [{
    "id": "", "sequence_on_page": 1, "image_type": "", "position": "",
    "alt_text": "", "description": "",
    "contains_graph": false, "is_decorative": false,
    "is_response_area": false, "response_area_type": null,
    "graph_details": {
      "x_axis_label": null, "x_axis_range": null,
      "y_axis_label": null, "y_axis_range": null,
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
BACKOFF_SECONDS = (10, 20, 40)
MAX_ATTEMPTS = 3


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

    def extract_page(self, page_image: Any, page_number: int) -> dict:
        """
        Send one page image to Gemini and return parsed JSON dict.
        Retries up to MAX_ATTEMPTS times with exponential back-off on 429.
        Falls back to an empty-shell dict after all retries are exhausted.
        """
        model = self._genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.1, "max_output_tokens": 8192},
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response  = model.generate_content([MASTER_PROMPT, page_image])
                raw_text  = (response.text or "").strip()
                cleaned   = _strip_fences(raw_text)
                data      = json.loads(cleaned)
                data["page_number"] = data.get("page_number") or page_number
                return data

            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()

                if _is_rate_limit(msg):
                    delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
                    log.warning("Rate limit on page %d attempt %d — waiting %ds", page_number, attempt, delay)
                    time.sleep(delay)
                else:
                    log.warning("Page %d attempt %d error: %s", page_number, attempt, exc)
                    time.sleep(3)

        log.error("Page %d failed after %d attempts: %s", page_number, MAX_ATTEMPTS, last_error)
        return _empty_page(page_number)


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
    }
