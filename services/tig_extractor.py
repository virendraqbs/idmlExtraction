"""
services/tig_extractor.py — Gemini extraction for Teacher Implementation Guide (TIG) pages.

Drop-in replacement for GeminiService.extract_page() when job.book_type == "TIG".
Returns the same (page_data, report) tuple so PipelineService._run() needs no
structural changes — it just switches which extractor it calls.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from config import config

log = logging.getLogger(__name__)

# ── TIG extraction prompt ─────────────────────────────────────────────────────

TIG_PROMPT = """You are a precision structured-data extractor for Carnegie Learning
Teacher Implementation Guide (TIG) PDFs.
You receive ONE page image from a TIG. Extract EVERYTHING visible.

═══ OUTPUT RULES ═══
- Return ONLY valid JSON. Zero markdown fences. Zero explanation.
- Use null for absent scalar fields. Use [] for absent arrays.
- All id fields must be empty string "".
- Preserve EXACT wording. Multi-line text: join with \\n.

═══ PAGE TYPE ═══
Set page_type to the FIRST matching rule:
  TIG_LESSON_OVERVIEW          → page shows lesson title, learning goals, language goals,
                                  lesson summary, pacing overview, materials list, or
                                  "My Learning Goals" section
  TIG_LESSON_ACTIVATE          → page covers the ACTIVATE activity teacher guidance
  TIG_LESSON_EXPLORE           → page covers EXPLORE activity teacher guidance
  TIG_LESSON_EXPLORE_CONTINUED → continuation of an EXPLORE (no new activity heading at top)
  TIG_LESSON_REFLECT           → page covers REFLECT / closing activity teacher guidance
  TIG_NOTES                    → blank or lined notes page
  NON_CONTENT                  → table of contents, glossary, cover, appendix
  UNKNOWN                      → cannot determine

═══ LESSON METADATA (overview pages only) ═══
lesson.lesson_number   : integer — lesson number shown in header/title
lesson.title           : exact lesson title text
lesson.lesson_summary  : paragraph summarising the lesson (if present)
lesson.learning_goals  : array of "I can…" strings
lesson.module_title    : module title if visible
lesson.module_number   : integer module number if visible
lesson.topic_title     : topic title if visible
lesson.topic_number    : integer topic number if visible

═══ ACTIVITIES ═══
For each ACTIVATE / EXPLORE / REFLECT / KEY_TERMS / PRACTICE_QUESTIONS activity block:
  activity_type  : ACTIVATE | EXPLORE | REFLECT | KEY_TERMS | PRACTICE_QUESTIONS
  title          : activity title text
  sequence_number: integer order within the lesson (1-based)
  teacher_guidance:
    instructional_text: purpose/driver text ("Purpose: To…", "Driver of Investigation: …")
    linked_student_activity_title: the matching student activity title if mentioned
  directions: array of {sequence_number, type:"DIRECTION_LINE", text} — each teacher step
  metadata.pacing_minutes: integer pacing if shown (e.g. "~5 min" → 5), else null

═══ INSTRUCTIONAL PROMPTS ═══
Extract every sidebar/callout/box:
  LEARNING_GOALS              → "My Learning Goals" box
  LANGUAGE_GOALS              → "Language Goal" box
  MULTILINGUAL_LEARNER_SUPPORT→ "Multilingual Learner Support/Supports" box
  HABITS_OF_MIND              → "Habits of Mind" / "Mathematical Practice" box
  STUDENT_LOOK_FORS           → "Student Look-Fors" box
  CULTIVATE_CONNECTIONS       → "Cultivate Connections" / "Make a Connection" box
  COMMON_MISCONCEPTIONS       → "Common Misconception" callout
  CONTENT_CONNECTION          → "Content Connection" box
  DAILY_MATH_ROUTINES         → "Daily Math Routines" / "Math Language Routine" section heading box
  MATERIALS_LIST              → "Materials" list
  TEACHER_STORY               → narrative teacher story or scenario
  STUDENT_EDITION_PAGE_IMAGE  → reference to a student edition page image

For each:
  instructional_prompt_type : one of the types above
  title        : box/callout heading text (or null)
  content      : paragraph content (or null)
  content_items: array of bullet strings (or [])
  display_style: BOX | SIDEBAR | CALLOUT | INLINE
  student_content_reference_title: title of the activity this prompt belongs to (or null)

═══ INSTRUCTIONAL SEGMENTS ═══
Extract structured lesson segments:
  ESSENTIAL_IDEAS             → "Essential Ideas" bulleted list
  ABOUT_THE_MATH              → "About the Math" / math background paragraph
  LESSON_STRUCTURE_AND_PACING → pacing/session breakdown table or list
  SETTING_THE_STAGE           → "Setting the Stage" launch directions
  TASK                        → numbered teacher steps for an activity
  CLOSING                     → "Session Close" / wrap-up directions
  DIFFERENTIATION_STRATEGY    → differentiation / extension notes
  ONGOING_ASSESSMENT          → formative assessment guidance
  LANGUAGE_LINK               → "Language Link" vocabulary note
  MATH_LANGUAGE_ROUTINE       → "Math Language Routine: MLR …" section
  PURPOSEFUL_QUESTIONS        → "Purposeful Questions" list

For each:
  instructional_segment_type : one of the types above
  title: segment heading text (or null)
  student_content_reference_title: activity title this segment belongs to (or null)
  directions: array of {sequence_number, text}

═══ RETURN EXACTLY THIS JSON ═══
{
  "page_number": null,
  "page_type": "TIG_LESSON_OVERVIEW | TIG_LESSON_ACTIVATE | TIG_LESSON_EXPLORE | TIG_LESSON_EXPLORE_CONTINUED | TIG_LESSON_REFLECT | TIG_NOTES | NON_CONTENT | UNKNOWN",
  "lesson": {
    "lesson_number": null, "title": null, "lesson_summary": null,
    "learning_goals": [],
    "module_title": null, "module_number": null,
    "topic_title": null, "topic_number": null
  },
  "activities": [
    {
      "id": "",
      "activity_type": "ACTIVATE | EXPLORE | REFLECT | KEY_TERMS | PRACTICE_QUESTIONS",
      "title": "",
      "sequence_number": 1,
      "teacher_guidance": {
        "instructional_text": null,
        "linked_student_activity_title": null
      },
      "directions": [{"sequence_number": 1, "type": "DIRECTION_LINE", "text": ""}],
      "metadata": {"pacing_minutes": null}
    }
  ],
  "instructional_prompts": [
    {
      "id": "",
      "instructional_prompt_type": "LEARNING_GOALS | LANGUAGE_GOALS | MULTILINGUAL_LEARNER_SUPPORT | HABITS_OF_MIND | STUDENT_LOOK_FORS | CULTIVATE_CONNECTIONS | COMMON_MISCONCEPTIONS | CONTENT_CONNECTION | DAILY_MATH_ROUTINES | MATERIALS_LIST | TEACHER_STORY | STUDENT_EDITION_PAGE_IMAGE",
      "title": null, "content": null, "content_items": [],
      "display_style": "BOX | SIDEBAR | CALLOUT | INLINE",
      "student_content_reference_title": null
    }
  ],
  "instructional_segments": [
    {
      "id": "",
      "instructional_segment_type": "ESSENTIAL_IDEAS | ABOUT_THE_MATH | LESSON_STRUCTURE_AND_PACING | SETTING_THE_STAGE | TASK | CLOSING | DIFFERENTIATION_STRATEGY | ONGOING_ASSESSMENT | LANGUAGE_LINK | MATH_LANGUAGE_ROUTINE | PURPOSEFUL_QUESTIONS",
      "title": null,
      "student_content_reference_title": null,
      "directions": [{"sequence_number": 1, "text": ""}]
    }
  ]
}

If this page has NO teacher content (blank, notes, cover), return page_type "NON_CONTENT"
and null/[] for everything else."""

# Retry back-off delays (seconds)
_BACKOFF = (10, 20, 40, 60)
_MAX_ATTEMPTS = 4


class TIGExtractor:
    """
    Gemini extractor for TIG pages.
    Mirrors the GeminiService interface: health_check() + extract_page().
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        import google.generativeai as genai

        self._api_key = api_key or config.GEMINI_API_KEY
        genai.configure(api_key=self._api_key)
        self._genai = genai

    def health_check(self) -> bool:
        """Verify API key with a minimal generation call. Raises RuntimeError on failure."""
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
        Send one TIG page image to Gemini. Returns (page_data, report).
        Same signature as GeminiService.extract_page() so PipelineService
        can call either interchangeably.
        """
        model = self._genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.1, "max_output_tokens": 16384},
        )

        last_error: Optional[Exception] = None
        errors: list[str] = []
        t0 = time.time()

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = model.generate_content([TIG_PROMPT, page_image])
                raw_text = (response.text or "").strip()
                cleaned  = _strip_fences(raw_text)
                data     = json.loads(cleaned)
                data["page_number"] = data.get("page_number") or page_number
                elapsed = int((time.time() - t0) * 1000)
                report = {
                    "page":     page_number,
                    "attempts": attempt,
                    "status":   "ok",
                    "pageType": data.get("page_type"),
                    "errors":   errors,
                    "elapsed_ms": elapsed,
                }
                return data, report

            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()
                errors.append(f"attempt {attempt}: {exc}")
                if any(k in msg for k in ("429", "rate", "quota", "exhausted")):
                    delay = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
                    log.warning("TIG rate-limit page %d attempt %d — wait %ds", page_number, attempt, delay)
                    time.sleep(delay)
                else:
                    log.warning("TIG page %d attempt %d error: %s", page_number, attempt, exc)
                    time.sleep(3)

        elapsed = int((time.time() - t0) * 1000)
        log.error("TIG page %d failed after %d attempts: %s", page_number, _MAX_ATTEMPTS, last_error)
        report = {
            "page":     page_number,
            "attempts": _MAX_ATTEMPTS,
            "status":   "failed",
            "pageType": "UNKNOWN",
            "errors":   errors,
            "elapsed_ms": elapsed,
        }
        return _empty_tig_page(page_number), report


# ── Private helpers ───────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
    return text.strip()


def _empty_tig_page(page_number: int) -> dict:
    return {
        "page_number":           page_number,
        "page_type":             "UNKNOWN",
        "lesson":                {},
        "activities":            [],
        "instructional_prompts": [],
        "instructional_segments": [],
    }
