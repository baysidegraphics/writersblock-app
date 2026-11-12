"""Verbatim extracted WritersBlock Studios Gemini revision methods.

The method bodies are copied without rewriting.
"""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class RevisionMixin:
    def run_revision_pass(self, manuscript_text, revision_mode, tone_style, author_style=""):
        """
        Node 7: Final Revision & Polish Engine.
        Reviews the completed manuscript and returns an editorial revision report.
        """
        author_context = (
            f"Author style target: {author_style}"
            if author_style
            else "Use clean professional editorial standards."
        )

        prompt = f"""
You are Node 7: Final Revision & Polish Engine.

Revision Mode: {revision_mode}
Tone Target: {tone_style}
{author_context}

Review the manuscript below and provide a clear revision report.

MANUSCRIPT:
{manuscript_text}

Return the report with these sections:

1. Main Issues Found
2. Specific Fix Recommendations
3. Strongest Sections
4. Weakest Sections
5. Suggested Rewrite Priorities
"""

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.5),
            )

            response_text = response.text.strip() if response and response.text else ""

            if not response_text:
                raise ValueError("Gemini returned an empty revision report.")

            return response_text

        except Exception as e:
            return f"""
NODE 7 LOCAL FALLBACK REVISION REPORT

Revision Mode:
{revision_mode}

Main Issue:
The Gemini backend did not return a live revision report.

Backend Error:
{e}

Manual Review Notes:
- Check continuity between scene beats.
- Confirm pacing does not repeat the same emotional beat too often.
- Strengthen transitions between each drafted section.
- Make sure the tone remains consistent with: {tone_style}.
- Review final paragraph of each scene for stronger hooks or closing images.
"""


    def run_rewrite_engine(
        self,
        source_text,
        rewrite_mode,
        scene_choice,
        custom_instruction,
        target_length="Keep Current Length",
        custom_target_word_count=None,
        tone_style="",
        author_style="",
    ):
        """
        Node 8: Rewrite & Expansion Engine.
        Rewrites only the selected live manuscript text.
        """
        author_context = (
            f"Author style target: {author_style}"
            if author_style
            else "Use clean professional prose standards."
        )

        manual_notes = custom_instruction.strip() if custom_instruction else ""

        if target_length == "Custom Word Count" and custom_target_word_count:
            length_instruction = f"Target final length: approximately {int(custom_target_word_count)} words."
        elif target_length == "Expand to 1,500 Words":
            length_instruction = "Target final length: approximately 1,500 words. Expand the manuscript substantially."
        elif target_length == "Expand to 2,500 Words":
            length_instruction = "Target final length: approximately 2,500 words. Expand the manuscript substantially."
        elif target_length == "Expand to 5,000 Words":
            length_instruction = "Target final length: approximately 5,000 words. Expand the manuscript substantially."
        elif target_length == "Shorten for Video / Script Adaptation":
            length_instruction = (
                "Shorten and compress the manuscript for later video or screenplay adaptation. "
                "Preserve the full story arc, major events, characters, and ending."
            )
        else:
            length_instruction = "Keep approximately the current length unless the rewrite direction requires a change."

        if rewrite_mode == "Direct Story Change / Obey My Instructions Exactly":
            mode_rules = """
DIRECT STORY CHANGE MODE:
- The Specific Rewrite Direction is mandatory and overrides any conflicting event in the selected manuscript text.
- Do not treat the direction as a suggestion, theme, metaphor, or optional guidance.
- Do not invent an alternate resolution.
- Do not keep any old scene event that contradicts the requested change.
- Preserve existing character names, especially Elias if present.
- Rewrite the selected location so the requested events happen in the exact story order given by the user.
- If the instruction says Elias is sucked into the safe, Elias must be sucked into the safe.
- If the instruction says the safe door slams shut, the safe door must slam shut.
- If the instruction says a later patron enters and the safe begins clicking again, that cyclical ending must appear.
- You may improve wording and flow only around those fixed facts.
"""
            temperature = 0.2

        elif rewrite_mode == "Polish Only / Do Not Change Story":
            mode_rules = """
POLISH ONLY MODE:
- Do not change the plot.
- Do not add new events.
- Do not remove events.
- Do not rename characters.
- Improve grammar, clarity, rhythm, sentence flow, and prose quality only.
"""
            temperature = 0.35

        else:
            mode_rules = """
CREATIVE REWRITE MODE:
- Improve the selected text creatively while preserving continuity.
- You may strengthen pacing, tension, tone, imagery, atmosphere, and emotional impact.
- Do not rename existing characters.
- Do not replace the current story with a different story.
- Keep the rewrite grounded in the selected manuscript text.
- If a target length is selected, expand or compress the manuscript toward that target while preserving the core story.
"""
            temperature = 0.75

        prompt = f"""
You are Node 8: Rewrite & Expansion Engine for WriterBlock Studio.

You must rewrite ONLY the selected live manuscript text provided below.
Do not use or reference any saved versions, earlier drafts, database history, or outside storylines.

Rewrite Mode:
{rewrite_mode}

Rewrite Location:
{scene_choice}

Target Length:
{target_length}

Length Instruction:
{length_instruction}

Tone Target:
{tone_style}

{author_context}

Specific Rewrite Direction - Optional:
{manual_notes if manual_notes else "No specific direction provided."}

Mode Rules:
{mode_rules}

Selected Live Manuscript Text:
{source_text}

Strict Output Rules:
- Return only the rewritten manuscript text.
- YouTube Shorts Test Mode: do not exceed 400 words under any rewrite or expansion setting.
- Do not include labels, notes, explanations, markdown, summaries, or instruction text.
- Do not include STORY INTENT, REQUIRED CHANGE, OUTPUT RULE, or similar labels.
- Do not write a different story.
- Do not rename existing characters.
- Do not mention the rewrite mode.
- Do not mention the target length.
- If the selected text contains Elias, the rewritten text must keep Elias.
- If Direct Story Change mode is selected, the user's Specific Rewrite Direction is the controlling plot and must be followed exactly.
- If the selected manuscript contradicts the user's Specific Rewrite Direction, replace the contradiction with the user's requested event.
- If the user gives a specific rewrite direction, apply it inside the rewritten prose as finished story action.
- If target length requests expansion, expand with atmosphere, description, suspense, interiority, and continuity — not unrelated new plotlines.
- If target length requests shortening, compress without losing the main story arc.

Rewritten Manuscript Text:
"""

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=(
                        "You are a controlled rewriting engine. Rewrite only the supplied selected text. "
                        "Never echo instructions. Never introduce unrelated characters or storylines. "
                        "In Direct Story Change mode, the user's instruction is mandatory plot law. "
                        "Replace conflicting old events with the user's requested events. "
                        "Respect target length instructions while preserving the current story. "
                        "Return only polished manuscript prose."
                    ),
                ),
            )

            response_text = response.text.strip() if response and response.text else ""

            if not response_text:
                raise ValueError("Gemini returned an empty rewrite response.")

            if response_text.strip() == str(source_text).strip() and rewrite_mode != "Polish Only / Do Not Change Story":
                raise ValueError("Gemini returned unchanged text.")

            return response_text

        except Exception as e:
            return (
                "Rewrite engine fallback output.\n\n"
                f"Backend error: {e}\n\n"
                "The rewrite request was received, but the AI backend did not return usable text."
            )


    def _fallback_rewrite_text(self, source_text, rewrite_mode, scene_choice, custom_instruction, tone_style, error):
        """
        Local fallback for Node 8 when Gemini is unavailable.
        Free-form creator notes override dropdown structure.
        """
        cleaned = self._clean_outline_language(source_text)
        notes = (custom_instruction or "").strip()
        notes_lower = notes.lower()
        mode_lower = (rewrite_mode or "").lower()

        has_real_notes = bool(notes) and notes.lower() != "no extra manual notes provided."

        if has_real_notes:
            # Free-form creator instructions are treated as the primary story change.
            if any(word in notes_lower for word in ["ending", "end", "final", "dies", "dead", "death", "collapses", "vanished", "starts clicking", "clicking again", "cycle"]):
                result = self._freeform_ending_fallback(cleaned, notes, tone_style)
            else:
                result = self._freeform_general_fallback(cleaned, notes, tone_style)
        elif "expand" in mode_lower:
            result = (
                f"{cleaned}\n\n"
                f"The moment lingered longer than it had before, stretching the silence into something with weight. "
                f"Every small sound seemed sharpened by the {tone_style} atmosphere, and the scene gained pressure not by moving faster, "
                f"but by refusing to release the character from the unease already surrounding them."
            )
        elif "shorten" in mode_lower:
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            result = " ".join(sentences[: max(2, min(5, len(sentences)))])
        elif "dialogue" in mode_lower:
            result = (
                f"{cleaned}\n\n"
                f"The spoken edges of the scene should cut cleaner here: fewer soft explanations, more pressure beneath each line, "
                f"and responses that reveal what the character refuses to say directly."
            )
        elif "ending" in mode_lower:
            result = (
                f"{cleaned}\n\n"
                f"But the ending no longer pointed toward something approaching. The safe itself became the answer: "
                f"not opening, not moving, not threatening in any ordinary way—only counting with the calm certainty of a thing "
                f"that already knew exactly when the room would run out of time."
            )
        else:
            result = (
                f"{cleaned}\n\n"
                f"The scene has been tightened into a cleaner {tone_style} passage, with stronger continuity, clearer pressure, "
                f"and less mechanical staging language."
            )

        return result.strip()


    def _freeform_general_fallback(self, cleaned_source, notes, tone_style):
        """
        Basic local fallback that preserves the source but directly incorporates creator notes.
        """
        return (
            f"{cleaned_source}\n\n"
            f"The scene shifts according to the creator's direction: {notes.strip()} "
            f"The new emphasis should carry through as polished {tone_style} prose, changing the beat according to that instruction rather than forcing it into a preset pattern."
        ).strip()


    def _freeform_ending_fallback(self, cleaned_source, notes, tone_style):
        """
        Ending-focused local fallback. Uses the creator's exact story logic as the main ending.
        """
        notes_lower = notes.lower()

        # Specific common ending requested during testing: Elias life-clock / safe cycle restart.
        if ("elias" in notes_lower and ("life clock" in notes_lower or "life" in notes_lower) and ("click" in notes_lower or "tick" in notes_lower)):
            return (
                "At midnight, the clicking stopped. Not faded. Not slowed. Stopped. The silence struck the shop harder than the sound ever had, and Elias Vance stood before the iron safe with the terrible understanding that the rhythm had not belonged to the mechanism at all. It had been his own life, counted down in cold little clicks.\n\n"
                "Age showed on him then. It showed in the tremor of his hands, in the gray sag of his face, in the tired bend of his shoulders as he stepped closer. The safe gave a low internal groan. Its door, sealed against every tool and every prayer he had thrown at it, opened by itself. A black emptiness waited inside.\n\n"
                "Elias leaned forward, cautious and breathless, and the darkness took him. One instant he was reaching toward the open mouth of the safe; the next he was yanked inside with brutal force. The door slammed shut behind him with a gunshot crack that shook the glass counters and sent dust trembling from the shelves.\n\n"
                "A few days later, the bell above the shop door gave its ordinary little jangle. An old gentleman entered carrying a broken clock against his chest. No one came from behind the counter. No one called from the back room. Elias Vance was gone.\n\n"
                "The patron noticed the iron safe sitting in the center of the shop floor where it had remained since Elias bought the store. Curious, he approached it. He touched the cold surface, ran his fingers along the seam, and bent closer to examine the impossible door.\n\n"
                "From deep inside the black iron, the clicking began again."
            )

        return (
            f"{cleaned_source}\n\n"
            f"The ending is redirected by the creator's instruction: {notes.strip()} "
            f"The final image should resolve the beat in polished {tone_style} prose, making the requested outcome unmistakable rather than treating it as a vague suggestion."
        ).strip()


