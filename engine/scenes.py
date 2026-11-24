"""Verbatim extracted WritersBlock Studios Gemini scenes methods.

The method bodies are copied without rewriting.
"""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class ScenesMixin:
    def execute_recursive_draft_chunk(self, current_beat_text, rolling_lore, format_type, tone_style, author_style=""):
        """
        Node 5: Recursive Drafting Engine.
        Assembles full narrative text for a given beat while keeping layout data clean.
        """
        author_directive = (
            f"Mimic the linguistic profiles of: {author_style}."
            if author_style
            else "Cinematic industry-standard delivery."
        )

        screenplay_terms = ["screenplay", "script", "youtube script", "short-form video", "tiktok", "shorts"]
        is_screenplay_style = any(term in str(format_type).lower() for term in screenplay_terms)

        format_layout = (
            "Use screenplay/script formatting with clear scene action and dialogue."
            if is_screenplay_style
            else (
                "Use polished story prose only. Do not output scene labels, objective labels, "
                "outline labels, beat labels, planning notes, screenplay notes, or bracketed metadata."
            )
        )

        prompt = f"""
You are the Node 5 Recursive Drafting Engine.
Transform this scene beat into highly polished, production-ready narrative content:
Audio Short Story Rule:
If format_type is "Audio Short Story — 15–30 min", write narration-ready prose designed to be heard aloud.
Use smooth sentence rhythm, clear transitions, limited character confusion, natural pauses, and complete short-story pacing.
Do not use screenplay formatting, shot directions, bracketed labels, narrator labels, production notes, or sound effect instructions.
Children’s Picture Book Standard:
If format_type is "Children's Picture Book (32-Page Layout)", write only polished child-friendly story prose for this structural beat.
Keep the full manuscript concise enough to finish at approximately 500–800 words across all four beats.
Use concrete visual action, read-aloud rhythm, simple transitions, and natural page-turn opportunities.
Do not output page numbers, spread labels, illustration notes, image-placement notes, or illustration prompts.
The dedicated Children’s Picture Book Layout Draft stage will divide the finished manuscript into 32 pages / 16 spreads and assign layout templates afterward.
{current_beat_text}

LORE BOOK MEMORY:
{rolling_lore if rolling_lore else "Opening sequence."}

STYLING MATRIX:
- Tone: {tone_style}
- Voice: {author_directive}
- Layout: {format_layout}

CRITICAL OUTPUT FORMAT INSTRUCTION:
Output polished creative writing first.

If the format target is NOT screenplay/script/video:
- Write ONLY finished story prose.
- Do NOT write planning text.
- Do NOT write scene labels.
- Do NOT write outline labels.
- Do NOT write beat labels.
- Do NOT write objective labels.
- Do NOT write bracketed metadata.
- Do NOT write "Scene Title:", "Objective:", "Core Objective:", "Scene Details:", "Style Directive:", or "Beat:".
- Convert all supplied outline material into natural paragraphs.
- The reader should see only finished fiction, not the construction notes.
- Each scene beat must have a different dramatic purpose and different final paragraph.
- Beat 1 should establish the hook.
- Beat 2 should escalate pressure.
- Beat 3 should reveal a pattern, secret, or third-act twist.
- Beat 4 should deliver the ending, consequence, or final image.
- Do not reuse the same closing sentence, same final image, or same emotional beat from earlier scenes.

If the format target IS screenplay/script/video:
- Use appropriate script/action formatting.

When the creative text is completely finished, print the exact text '=== LORE UPDATE ===' on its own blank line.
Directly below that marker, list the updated core lore bullet points.
Do not use markdown code blocks.
"""

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    system_instruction=(
                        "You are a precise parsing engine. Never wrap structural split markers "
                        "in markdown quotes or code blocks."
                    ),
                ),
            )

            response_text = response.text.strip() if response and response.text else ""

            if not response_text:
                raise ValueError("Gemini returned an empty draft response.")

            return self._clean_draft_response(response_text, format_type)

        except Exception as e:
            return self._fallback_draft_chunk(current_beat_text, rolling_lore, tone_style, e)


    def _clean_draft_response(self, response_text, format_type):
        """
        Cleans accidental outline/screenplay planning language from Node 5 prose output
        while preserving the LORE UPDATE section.
        """
        screenplay_terms = ["screenplay", "script", "youtube script", "short-form video", "tiktok", "shorts"]
        is_screenplay_style = any(term in str(format_type).lower() for term in screenplay_terms)

        if is_screenplay_style:
            return response_text

        marker_match = re.search(r"===?\s*LORE\s+UPDATE\s*===?", response_text or "", re.IGNORECASE)

        if marker_match:
            story_part = response_text[:marker_match.start()].strip()
            lore_part = response_text[marker_match.end():].strip()
        else:
            story_part = str(response_text or "").strip()
            lore_part = "- Lore update marker was missing; context preserved from generated prose."

        cleaned_story = self._clean_outline_language(story_part)

        return f"{cleaned_story}\n\n=== LORE UPDATE ===\n{lore_part}".strip()


    def _clean_outline_language(self, text):
        """
        Removes outline/screenplay planning labels from prose selections.
        """
        lines = []
        for line in str(text or "").splitlines():
            clean = line.strip()
            if not clean:
                lines.append("")
                continue

            if re.match(r"=+", clean):
                continue
            if re.match(r"(?i)^CHAPTER\s+SCENE\s+BEAT\s+\d+", clean):
                continue
            if re.match(r"(?i)^(Scene Title|Objective|Core Objective|Scene Details|Style Directive|Beat)\s*:", clean):
                continue
            if re.match(r"(?i)^\[(SCENE TITLE|CORE OBJECTIVE|SCENE DETAILS|STYLE|BEAT)", clean):
                continue

            lines.append(line)

        return "\n".join(lines).strip()


    def _fallback_draft_chunk(self, current_beat_text, rolling_lore, tone_style, error):
        """
        Local fallback that varies by beat instead of repeating the same paragraph.
        """
        beat_num = self._extract_beat_number(current_beat_text)
        scene_title = self._extract_field(current_beat_text, "SCENE TITLE") or f"Fallback Scene Beat {beat_num}"
        objective = self._extract_field(current_beat_text, "CORE OBJECTIVE") or "Continue the narrative progression."
        conflict = self._extract_field(current_beat_text, "SCENE DETAILS & CONFLICT") or current_beat_text.strip()

        fallback_openings = {
            1: (
                "The antique shop had already gone quiet when the first impossible sound began. "
                "Behind the counter, beneath the amber cone of a tired desk lamp, the iron safe sat like a thing that had been waiting longer than any object had a right to wait."
            ),
            2: (
                "By the second night, the ticking was no longer faint enough to ignore. "
                "It pressed through the floorboards, the shelves, and the owner's skull with a rhythm that felt less mechanical than intentional."
            ),
            3: (
                "The pattern revealed itself only after he stopped listening like a frightened man and started listening like a witness. "
                "The safe was not merely ticking faster; it was counting toward something."
            ),
            4: (
                "At midnight, every clock in the shop seemed to surrender to the sound inside the iron safe. "
                "The final sequence came so quickly that the individual ticks blurred into one continuous metallic breath."
            ),
        }

        cleaned_conflict = self._clean_outline_language(conflict)

        fallback_closings = {
            1: (
                "He told himself it was only old metal cooling in an old room, but he still locked the front door twice before leaving. "
                "Behind him, in the dark, the safe answered with one more patient tick."
            ),
            2: (
                "By dawn, he had stopped asking whether the sound was real. The only question left was why it seemed to know exactly when he was listening."
            ),
            3: (
                "Then the pattern broke open: the ticks were not counting seconds at all. They were matching dates, names, and payments from the old ledger—each beat pointing to someone who had disappeared after touching the safe."
            ),
            4: (
                "At midnight, the final tick did not come from inside the safe. It came from behind him, soft and intimate, followed by the slow turning of a lock he had never opened."
            ),
        }

        narrative_text = f"""
{fallback_openings.get(beat_num, fallback_openings[1])}

{cleaned_conflict}

{fallback_closings.get(beat_num, fallback_closings[1])}
""".strip()

        lore_update = f"""
- Current fallback beat processed: Beat {beat_num}
- Scene title: {scene_title}
- Core objective: {objective}
- Backend issue: {error}
- Previous lore preserved: {rolling_lore if rolling_lore else "Opening sequence initialized."}
""".strip()

        return f"{narrative_text}\n\n=== LORE UPDATE ===\n{lore_update}"


    def _extract_beat_number(self, text):
        match = re.search(r"(?i)\bBEAT\s+(\d+)", text or "")
        return int(match.group(1)) if match else 1


    def _extract_field(self, text, field_name):
        pattern = rf"\[{re.escape(field_name)}\]\s*:\s*(.*)"
        match = re.search(pattern, text or "", re.IGNORECASE)
        return match.group(1).strip() if match else ""


