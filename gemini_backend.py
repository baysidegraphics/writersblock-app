import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class GeminiWriterBackend:
    def __init__(self):
        """
        Pulls Gemini credentials from Google Studio API Key.txt first,
        then falls back to the GEMINI_API_KEY environment variable.
        """
        self.api_key = self._load_api_key()
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = "gemini-2.5-flash"

    def _load_api_key(self):
        possible_files = [
            Path("Google Studio API Key.txt"),
            Path("Google Studio API Key.text"),
            Path("GoogleStudioAPIKey.txt"),
            Path("api_key.txt"),
        ]

        for key_file in possible_files:
            if key_file.exists():
                key_text = key_file.read_text(encoding="utf-8", errors="ignore")
                keys = re.findall(r"AIza[0-9A-Za-z_\-]{20,}", key_text)

                if keys:
                    return keys[-1].strip()

        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        keys = re.findall(r"AIza[0-9A-Za-z_\-]{20,}", env_key)

        if keys:
            return keys[-1].strip()

        return env_key

    def generate_sandbox_slates(self, story_seed, format_type, tone_style, author_style=""):
        """
        Node 3: Scenario Sandbox Engine.
        Generates 3 strategic structural overviews.
        """
        author_context = (
            f"Target Author Style to emulate: {author_style}"
            if author_style
            else "Standard professional delivery."
        )

        prompt = f"""
You are the engine for Node 3 (Interactive Scenario Sandbox) of an Automated Writing Machine.

Core Input Seed: {story_seed}
Format Target: {format_type}
Tone/Aesthetic Base: {tone_style}
{author_context}
Audio Short Story Rule:
If Format Target is "Audio Short Story — 15–30 min", shape all three sandbox options as narration-ready short audio fiction designed for a 15–30 minute listening experience.
Keep the structure simple, the cast limited, scene changes clear, pacing smooth, and the ending complete.
Avoid overcomplicated timelines, dense exposition, or visual-only storytelling that would be confusing when heard aloud.

Children’s Picture Book Standard:
If Format Target is "Children's Picture Book (32-Page Layout)", shape all sandbox options as a concise children’s picture book intended for a 32-page, 8.5 x 8.5 square planning layout.
Keep the story visually driven, child-friendly, and suitable for approximately 500–800 finished story words.
Plan for strong page-turn moments and illustration opportunities, but do not embed page-layout metadata or illustration prompts in the story itself.

Generate exactly 3 unique narrative direction slates matching these distinct structural strategies:

### Option A: The Structural Core
Classic, genre-compliant, stable framework maximizing standard user/audience expectations.

### Option B: The Conceptual Subversion
Inverted framework, ironic twists, altered perspectives, or non-linear setups.

### Option C: The High-Impact Track
Pacing-forward framework, heavy sensory engagement, rapid escalation, immediate hooks.

For each option, provide 2-3 strong paragraphs with this structure:
- Title line
- Overview paragraph
- Narrative Direction paragraph
- Tone / Structure paragraph

Each option must be detailed enough for a creator to choose a story direction.
Do not write the full story. Do not be vague. Do not shorten to only 2-3 sentences.
"""

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            response_text = response.text.strip() if response and response.text else ""

            if not response_text:
                raise ValueError("Gemini returned an empty sandbox response.")

            slates = self._parse_slates(response_text)

            if not slates.get("Option A") or not slates.get("Option B") or not slates.get("Option C"):
                raise ValueError("Gemini response could not be parsed into all 3 sandbox options.")

            slates["is_fallback"] = False
            return slates

        except Exception as e:
            return {
                "is_fallback": True,
                "error_message": str(e),
                "Option A": (
                    f"FALLBACK OPTION A — Structural Core\n\n"
                    f"Overview: This path treats the seed as a clean four-act short story built around a strong central mystery: '{story_seed}'. "
                    f"The creator gets a reliable dramatic spine: a clear opening hook, a steadily tightening second act, a third-act revelation that changes the meaning of the event, and a final consequence that leaves the reader with a strong last image.\n\n"
                    f"Narrative Direction: Beat 1 establishes the ordinary world and the impossible intrusion. Beat 2 removes easy explanations and increases pressure. Beat 3 reveals that the anomaly is not random but connected to a hidden truth, past crime, curse, machine, memory, or character secret. Beat 4 resolves the immediate story while leaving a final sting, reversal, or consequence.\n\n"
                    f"Tone / Structure: Keep the {tone_style} tone consistent while making each beat serve a different purpose. Do not let the scenes repeat the same escalation. The structure should feel classic, readable, and creator-friendly, with enough room for later free-form rewrite instructions."
                ),
                "Option B": (
                    f"FALLBACK OPTION B — Conceptual Subversion\n\n"
                    f"Overview: This path reframes the premise from an unexpected angle. Instead of treating '{story_seed}' as a straightforward mystery, the story gradually reveals that the apparent threat may be a mirror, trap, confession, test, or punishment designed around the protagonist’s own hidden history.\n\n"
                    f"Narrative Direction: Beat 1 begins with the object/event appearing external and unexplained. Beat 2 makes the protagonist investigate while unknowingly exposing personal guilt, obsession, or denial. Beat 3 twists the story by revealing that the anomaly is responding to the protagonist, not merely happening around them. Beat 4 concludes with a reversal: the protagonist is judged, replaced, consumed, or forced to understand the truth too late.\n\n"
                    f"Tone / Structure: Use the {tone_style} atmosphere to make the reader question what is real, what is remembered, and what is being hidden. The story should still resolve clearly, but the emotional meaning should shift in the third act."
                ),
                "Option C": (
                    f"FALLBACK OPTION C — High-Impact Track\n\n"
                    f"Overview: This path begins close to the crisis and uses the seed as an immediate pressure device: '{story_seed}'. The story should feel urgent, visual, and hook-heavy, built for strong reader momentum.\n\n"
                    f"Narrative Direction: Beat 1 opens with the problem already active. Beat 2 accelerates sensory pressure and forces desperate action. Beat 3 delivers a hard reveal or reversal that makes the protagonist’s earlier choices dangerous. Beat 4 lands with a sharp final consequence, preferably a memorable last image or cyclical ending that suggests the danger continues.\n\n"
                    f"Tone / Structure: Preserve the {tone_style} mood but avoid slow setup. Each beat should increase urgency in a different way: physical pressure, psychological pressure, revelation, then consequence."
                ),
            }

    def generate_plot_outline(self, chosen_option, option_text, story_seed, format_type, tone_style, author_style=""):
        """
        Node 4: Plot Architect Engine.
        Generates a 4-beat granular production blueprint matching formatting constraints.
        """
        author_context = (
            f"Analyze and apply style syntax rules for: '{author_style}'."
            if author_style
            else "Apply clean, standard medium rules."
        )

        prompt = f"""
You are the Node 4 Plot Architect Engine of the Automated Writing Machine.
Construct an outline detailing exactly 4 critical, linear structural Scene Beats.

TRACK: {chosen_option}
PROFILE: {option_text}
SEED: {story_seed}
FORMAT: {format_type}
TONE: {tone_style}

Audio Short Story Rule:
If FORMAT is "Audio Short Story — 15–30 min", construct the outline as a narration-ready short audio story designed for a 15–30 minute listening experience.
Use clear linear scene beats, limited cast, smooth pacing, simple transitions, and a complete ending.
Do not create a complex multi-thread novel outline or screenplay-style visual-only structure.
Children’s Picture Book Standard:
If FORMAT is "Children's Picture Book (32-Page Layout)", construct exactly 4 structural story beats for a concise 32-page children’s picture book.
Treat each structural beat as approximately 4 two-page spreads / 8 pages of story progression.
Keep the total finished story suitable for approximately 500–800 words, with clear visual action and purposeful page-turn moments.
Do not include illustration-placement metadata here; the dedicated layout-draft stage will assign text/image positions after the manuscript is finished.
For each Scene Beat, output strictly using this bracketed data format:

[BEAT 1]
[SCENE TITLE]: Incident Introduction
[CORE OBJECTIVE]: Establish foundational narrative variables
[SCENE DETAILS & CONFLICT]: Initial encounter with the core hook.
[STYLE & SYNTAX DIRECTIVE]: Maintain active syntax pacing matching {tone_style}. {author_context}
===

Repeat this structure precisely for [BEAT 2], [BEAT 3], and [BEAT 4].
"""

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )

            response_text = response.text.strip() if response and response.text else ""

            if not response_text:
                raise ValueError("Gemini returned an empty plot outline.")

            return response_text

        except Exception:
            return f"""
[BEAT 1]
[SCENE TITLE]: Inciting Hook — The First Impossible Signal
[CORE OBJECTIVE]: Establish the protagonist, the ordinary world, and the impossible intrusion that begins the story.
[SCENE DETAILS & CONFLICT]: Begin with the core premise: {story_seed}. The protagonist encounters the first unmistakable sign that something is wrong. The conflict should be small enough to question, but strange enough to haunt the scene.
[STYLE & SYNTAX DIRECTIVE]: Use controlled sensory detail and restrained {tone_style} tension. This beat should open the door, not explain the mystery.
===
[BEAT 2]
[SCENE TITLE]: Escalation — False Explanations Collapse
[CORE OBJECTIVE]: Increase pressure and remove the obvious explanations.
[SCENE DETAILS & CONFLICT]: The protagonist tests the problem logically, searches for mechanical or ordinary causes, and tries to regain control. Each attempt fails. The situation becomes more personal, more urgent, and harder to dismiss.
[STYLE & SYNTAX DIRECTIVE]: Increase pacing through sharper observations, shorter actions, and stronger internal pressure. This beat should escalate, not reveal the final truth.
===
[BEAT 3]
[SCENE TITLE]: Third-Act Twist — The Hidden Meaning
[CORE OBJECTIVE]: Reveal a pattern, secret, reversal, or hidden truth that changes what the audience thought the story was about.
[SCENE DETAILS & CONFLICT]: The protagonist discovers the anomaly is not random. It connects to a buried event, old record, forgotten victim, personal guilt, repeating cycle, or dangerous truth. This beat must change the meaning of the first two beats.
[STYLE & SYNTAX DIRECTIVE]: Use investigative tension, pattern recognition, and dread. This is the twist/reversal beat, not another escalation beat.
===
[BEAT 4]
[SCENE TITLE]: Final Consequence — The Last Image
[CORE OBJECTIVE]: Deliver the climax, consequence, and final image.
[SCENE DETAILS & CONFLICT]: The truth reaches its consequence. The protagonist must face what the mystery was counting toward. End with a clear conclusion, final reversal, death, release, punishment, or cyclical image that gives the short story a finished ending.
[STYLE & SYNTAX DIRECTIVE]: Build toward a memorable final image. This beat must conclude the story, not simply continue the mystery.
"""

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

    def _parse_slates(self, text):
        slates = {"Option A": "", "Option B": "", "Option C": ""}

        opt_a = re.search(r"###\s*Option A[:\s]*(.*?)(?=###\s*Option B|$)", text, re.DOTALL)
        opt_b = re.search(r"###\s*Option B[:\s]*(.*?)(?=###\s*Option C|$)", text, re.DOTALL)
        opt_c = re.search(r"###\s*Option C[:\s]*(.*)", text, re.DOTALL)

        if opt_a:
            slates["Option A"] = opt_a.group(1).strip()
        if opt_b:
            slates["Option B"] = opt_b.group(1).strip()
        if opt_c:
            slates["Option C"] = opt_c.group(1).strip()

        return slates
