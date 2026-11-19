"""Verbatim extracted WritersBlock Studios Gemini picture_book methods.

The method bodies are copied without rewriting.
"""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class PictureBookMixin:
    def generate_picture_book_layout(
        self,
        manuscript_text,
        project_title="",
        tone_style="",
        author_style="",
    ):
        """Build a creator-editable 32-page / 16-spread picture-book planning layout."""
        author_context = (
            f"Author style reference: {author_style}."
            if author_style
            else "Use clear professional children's publishing language."
        )

        prompt = f"""
You are the Children's Picture Book Layout Planner for WritersBlock Studios.

PROJECT TITLE: {project_title or "Untitled Children's Picture Book"}
TONE: {tone_style}
{author_context}

SOURCE MANUSCRIPT:
{manuscript_text}

TASK:
Convert the supplied finished manuscript into exactly 16 sequential two-page spreads representing a 32-page, 8.5 x 8.5 square CHILDREN'S PICTURE BOOK PRODUCTION LAYOUT DRAFT.
This is NOT a print-ready file. It is a planning handoff for the author, illustrator, designer, or publisher.

ALLOWED LAYOUT TEMPLATES — use only one of these exact values for each spread:
1. Full Illustration — Text Top
2. Full Illustration — Text Bottom
3. Text Left — Illustration Right
4. Illustration Left — Text Right
5. Two-Page Illustration — Text Overlay
6. Spot Illustration — Open Text Area

RULES:
- Preserve the actual story, characters, chronology, ending, and wording as closely as practical.
- Do not invent a different story.
- Divide the manuscript for strong picture-book pacing and page turns.
- Keep story text concise enough to work visually with illustration.
- Create a specific illustration direction for every spread.
- Use page-turn notes only where a reveal, surprise, joke, emotional beat, or transition benefits from the turn.
- Cover/title/copyright/back-cover production can be added later; these 16 spreads are the editable 32-page story-layout working draft.
- Return JSON only. No markdown and no commentary.

RETURN EXACTLY THIS JSON SHAPE:
{{
  "spreads": [
    {{
      "spread_number": 1,
      "pages": "1-2",
      "template": "Full Illustration — Text Bottom",
      "story_text": "...",
      "illustration_direction": "...",
      "page_turn_note": "..."
    }}
  ]
}}

Return exactly 16 spread objects numbered 1 through 16, covering pages 1-2 through 31-32.
""".strip()

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.35,
                    response_mime_type="application/json",
                ),
            )

            response_text = response.text.strip() if response and response.text else ""
            if not response_text:
                raise ValueError("Gemini returned an empty picture-book layout response.")

            data = json.loads(response_text)
            spreads = data.get("spreads") if isinstance(data, dict) else None
            if not isinstance(spreads, list) or len(spreads) != 16:
                raise ValueError("Gemini did not return exactly 16 picture-book spreads.")

            allowed_templates = {
                "Full Illustration — Text Top",
                "Full Illustration — Text Bottom",
                "Text Left — Illustration Right",
                "Illustration Left — Text Right",
                "Two-Page Illustration — Text Overlay",
                "Spot Illustration — Open Text Area",
            }

            cleaned = []
            for idx, spread in enumerate(spreads, start=1):
                if not isinstance(spread, dict):
                    raise ValueError(f"Spread {idx} is not a valid object.")
                template = str(spread.get("template") or "").strip()
                if template not in allowed_templates:
                    template = "Full Illustration — Text Bottom"
                cleaned.append({
                    "spread_number": idx,
                    "pages": f"{idx * 2 - 1}-{idx * 2}",
                    "template": template,
                    "story_text": str(spread.get("story_text") or "").strip(),
                    "illustration_direction": str(spread.get("illustration_direction") or "").strip(),
                    "page_turn_note": str(spread.get("page_turn_note") or "").strip(),
                })

            return {"spreads": cleaned}

        except Exception as e:
            paragraphs = [
                p.strip()
                for p in re.split(r"\n\s*\n", str(manuscript_text or ""))
                if p.strip()
            ]
            if not paragraphs:
                paragraphs = [str(manuscript_text or "").strip()]

            chunks = [[] for _ in range(16)]
            for idx, paragraph in enumerate(paragraphs):
                target = min(15, int(idx * 16 / max(1, len(paragraphs))))
                chunks[target].append(paragraph)

            templates = [
                "Full Illustration — Text Bottom",
                "Text Left — Illustration Right",
                "Illustration Left — Text Right",
                "Two-Page Illustration — Text Overlay",
                "Spot Illustration — Open Text Area",
                "Full Illustration — Text Top",
            ]

            fallback_spreads = []
            for idx in range(16):
                story_text = "\n\n".join(chunks[idx]).strip()
                fallback_spreads.append({
                    "spread_number": idx + 1,
                    "pages": f"{idx * 2 + 1}-{idx * 2 + 2}",
                    "template": templates[idx % len(templates)],
                    "story_text": story_text,
                    "illustration_direction": (
                        "Add an illustration that directly supports the action, setting, characters, "
                        "and emotional beat described in this spread."
                    ),
                    "page_turn_note": "",
                })

            return {
                "spreads": fallback_spreads,
                "is_fallback": True,
                "error_message": str(e),
            }


