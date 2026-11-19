"""Verbatim extracted WritersBlock Studios Gemini plot methods.

The method bodies are copied without rewriting.
"""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class PlotMixin:
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
Alter the order of REVELATION, viewpoint emphasis, or thematic framing, but NEVER
alter the established plot events, identities, causal facts, or stated outcome.

### Option C: The High-Impact Track
Increase urgency and momentum without skipping the original cause of the story,
required intermediate developments, or any aftermath following the climax.

AUTHOR'S PREMISE IS BINDING — ALL WRITING FORMATS:
- The Core Input Seed includes the writer's Story Premise, Central Conflict and
  Subplot and may contain an explicitly labeled Stage 1 specification. Treat all
  three as required source facts, not inspiration to create a substitute storyline.
- Retain every substantive author-supplied occurrence, its cause and consequence,
  including material from the FIRST and LAST paragraphs. Never invent an ending
  that replaces the one the author specified.
- Each option must trace the whole causal sequence: origin/opening, central
  conflict, subplot, complications and twists, crisis, climax, aftermath and
  the actual final outcome. The climax is NOT the ending if the premise continues.
- For every option identify the specific events and their consequences in story
  terms. Do not substitute generic phrases such as 'a shocking final image'.
- A/B/C vary the narrative delivery, pacing and emphasis, NEVER the facts,
  plot destination or resolution supplied by the author.
- Favor inclusion over omission. Develop, connect and enrich all supplied plot
  information; the writer can subsequently remove unwanted details.
- Before replying, cross-check EACH option against every explicit key event in
  the provided Stage 1 material; revise any option with missing plot events.

For EACH option return a title and clear plot-development sections covering:
Opening/Origin; Central Conflict; Subplot; Escalation and Twists; Climax;
Aftermath and Ending. Use concrete events, not generalized marketing language.
Keep each option detailed enough to map the complete intended story, while
remaining a plot plan rather than finished prose. Return all three options in
sections headed exactly '### Option A', '### Option B', and '### Option C'.
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
            # Fail closed. Invented generic fallback plots must never be displayed
            # or mistaken for premise-compliant author choices.
            return {
                "is_fallback": True,
                "error_message": str(e),
                "Option A": "",
                "Option B": "",
                "Option C": "",
            }


    @staticmethod
    def _writer_facing_outline_issues(outline):
        """Fail closed when scene text is planning commentary, not story/script.

        The four tagged metadata fields remain available internally. This read-only
        check examines only SCENE DETAILS & CONFLICT, the writer-facing field.
        It does not rewrite any author's original or previously saved text.
        """
        source = str(outline or "")
        beat_headers = list(re.finditer(r"(?im)^\s*\[BEAT\s+(\d+)\]\s*$", source))
        if [int(m.group(1)) for m in beat_headers] != [1, 2, 3, 4]:
            return ["Exactly four ordered [BEAT 1] through [BEAT 4] blocks are required."]
        issues = []
        editorial_phrases = (
            r"\b(?:the|this|a)\s+(?:scene|beat|story|plot|narrative)"
            r"(?:\s+[a-z]+){0,2}\s+(?:opens|begins|starts|moves|shifts|switches|"
            r"transitions|follows|focuses|shows|reveals|highlights|establishes|"
            r"emphasizes|centers|unfolds|will|should|is\s+designed)\b",
            r"\b(?:the|this)\s+(?:reader|audience|writer|author)\s+"
            r"(?:sees|learns|discovers|understands|knows|will|should|is\s+meant)\b",
            r"\b(?:the|this)\s+(?:protagonist|character)\s+(?:arc|journey)\b",
            r"\b(?:the|this|his|her|their)\s+(?:perspective|point\s+of\s+view)"
            r"(?:\s+[a-z]+){0,2}\s+(?:shifts|switches|takes\s+over)\b",
            r"(?m)^\s*(?:CORE\s+OBJECTIVE|STYLE\s*&\s*SYNTAX\s+DIRECTIVE|"
            r"SCENE\s+DETAILS|THE\s+CONFLICT|DIRECTOR'S\s+NOTE)\s*:",
            r"\b(?:the\s+story\s+transitions|the\s+narrative\s+quickly\s+shifts|"
            r"narrative\s+focus|this\s+beat\s+must|scene\s+objective)\b",
        )
        for i, match in enumerate(beat_headers):
            number = int(match.group(1))
            end = beat_headers[i + 1].start() if i + 1 < len(beat_headers) else len(source)
            block = source[match.end():end]
            for marker in ("SCENE TITLE", "CORE OBJECTIVE", "SCENE DETAILS & CONFLICT", "STYLE & SYNTAX DIRECTIVE"):
                if not re.search(r"\[" + re.escape(marker) + r"\]\s*:", block, re.I):
                    issues.append(f"Beat {number}: missing [{marker}] field.")
            scene = re.search(
                r"(?is)\[SCENE\s+DETAILS\s*&\s*CONFLICT\]\s*:\s*(.*?)"
                r"(?=\[STYLE\s*&\s*SYNTAX\s+DIRECTIVE\]\s*:|\Z)", block)
            if not scene:
                continue
            text = scene.group(1).strip().rstrip("= \t\r\n")
            if len(re.findall(r"\b[\w'-]+\b", text)) < 30:
                issues.append(f"Beat {number}: scene content is too brief to be a narrative passage.")
            for pattern in editorial_phrases:
                if re.search(pattern, text, re.I):
                    issues.append(f"Beat {number}: planning language found inside scene content.")
                    break
            if re.search(r"(?im)^\s*\[(?:BEAT|CORE\s+OBJECTIVE|STYLE\s*&\s*SYNTAX|SCENE\s+TITLE)\b", text):
                issues.append(f"Beat {number}: metadata leaked into scene content.")
        return issues


    def generate_plot_outline(self, chosen_option, option_text, story_seed, format_type, tone_style, author_style=""):
        """Create four scene beats with metadata isolated from *actual* story text.

        Universal backend rule: SCENE DETAILS is writer-facing scene prose or
        corresponding finished script/dialogue, NEVER an outline describing a
        scene. A rejected AI response is not shown or saved as a fallback.
        """
        author_context = (
            f"Apply the writer's selected creative reference: '{author_style}'."
            if author_style else "Use the selected format's natural writing style."
        )
        prompt = f"""
You are the WritersBlock Studios shared Scene Scripting writer. Produce EXACTLY
FOUR linear, numbered beats. The author-approved premise is binding.

SELECTED PLOT: {chosen_option}
SELECTED DIRECTION: {option_text}
AUTHOR'S FULL CONCEPT AND DEVELOPMENT CONDITIONS: {story_seed}
WRITING FORMAT: {format_type}
PROSE TONE: {tone_style}
STYLE REFERENCE: {author_context}

STORY FIDELITY (ALL FORMATS):
Preserve every material event, named character, setting, causal sequence, subplot,
climax, intervention, aftermath and the complete final outcome stated by the author.
The author's last event may come AFTER the apparent climax. Do not stop early.
Different structural approaches may vary emphasis, never the author's fixed facts.

ABSOLUTE WRITER-FACING SCENE RULE (ALL FORMATS):
[SCENE DETAILS & CONFLICT] is the ACTUAL SCENE, not a description of one.
Write the words the reader/audience will experience: concrete character actions,
setting, events, thoughts and dialogue as appropriate to the active writing format.
For prose formats, use continuous immersive fictional prose, not synopsis.
For screenplays/stage plays/video/podcasts, supply actual formatted action and
spoken lines suitable for that format, not a plan for future writing.
NEVER write phrases like "The beat opens", "The scene begins", "The narrative
shifts", "The story follows", "The scene establishes", "This beat shows",
"the reader sees", "the author's intention", or character-arc commentary in
[SCENE DETAILS & CONFLICT]. Never describe what a writer/camera/narrator will do.
DO NOT embed structural labels, planning objectives, instructions or analysis in
scene content. Put any internal planning ONLY in [CORE OBJECTIVE] or
[STYLE & SYNTAX DIRECTIVE]. Story prose must remain separate from metadata.
Do not introduce unsupported events to replace the author's storyline.

Short Story: four sequential, story-driven scenes, with real narrative rather
than beat descriptions; respect its under-1,500-word manuscript limit.
Children's Picture Book: concise child-friendly in-world storytelling suitable
for the intended audience; no layout, illustration or production notes in prose.

REQUIRED EXACT STRUCTURE (repeat for beats 1, 2, 3 and 4):
[BEAT 1]
[SCENE TITLE]: Brief title
[CORE OBJECTIVE]: Internal planning objective (never part of scene prose).
[SCENE DETAILS & CONFLICT]: Actual in-world writing. Characters ACT and SPEAK;
the dramatic events HAPPEN on the page rather than being summarized.
[STYLE & SYNTAX DIRECTIVE]: Internal format/style guidance, never narration.
===

[BEAT 2]
[SCENE TITLE]: ...
[CORE OBJECTIVE]: ...
[SCENE DETAILS & CONFLICT]: ...
[STYLE & SYNTAX DIRECTIVE]: ...
===
[BEAT 3]
[SCENE TITLE]: ...
[CORE OBJECTIVE]: ...
[SCENE DETAILS & CONFLICT]: ...
[STYLE & SYNTAX DIRECTIVE]: ...
===
[BEAT 4]
[SCENE TITLE]: ...
[CORE OBJECTIVE]: ...
[SCENE DETAILS & CONFLICT]: ...
[STYLE & SYNTAX DIRECTIVE]: ...
===

Before replying, verify that EACH SCENE DETAILS field contains actual story/script
text only and no commentary about the scene, beat, narrative or writing process.
"""
        if not self.client:
            raise ValueError("Gemini API key is missing. Scene generation was not saved.")
        last_issues = []
        for attempt in range(2):
            request = prompt
            if attempt:
                request += (
                    "\n\nPREVIOUS RESPONSE REJECTED: " + "; ".join(last_issues[:8])
                    + "\nRewrite ALL four beats. The SCENE DETAILS fields must contain "
                      "actual story events, character action and dialogue, never descriptions "
                      "of what the narrative does. Keep all planning in the other tags."
                )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=request,
                config=types.GenerateContentConfig(temperature=0.55),
            )
            produced = str(getattr(response, "text", "") or "").strip()
            last_issues = self._writer_facing_outline_issues(produced)
            if not last_issues:
                return produced
        # No generic fallback plot. That would hide the failure and contaminate
        # scene narrative with internal instructions in every writing format.
        raise ValueError(
            "Scene generation rejected because it contains outline/planning "
            "language rather than writer-facing story content. No changes were "
            "saved. " + "; ".join(last_issues[:4])
        )


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


