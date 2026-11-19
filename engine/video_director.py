"""Verbatim extracted WritersBlock Studios Gemini video_director methods.

The method bodies are copied without rewriting.
"""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types


class VideoDirectorMixin:
    def _video_director_contents(self, prompt, images=None):
        """Build a Gemini multimodal request from Streamlit-uploaded image payloads."""
        contents = [str(prompt or "").strip()]

        for image in images or []:
            if not isinstance(image, dict):
                continue

            data = image.get("data")
            mime_type = str(image.get("mime_type") or "image/jpeg").strip()

            if not data:
                continue

            try:
                contents.append(
                    types.Part.from_bytes(
                        data=data,
                        mime_type=mime_type,
                    )
                )
            except Exception:
                # One unreadable image must not prevent script generation.
                continue

        return contents


    def answer_video_director_quill(
        self,
        question,
        project_title="Untitled Video Project",
        video_style="Social Media Reel",
        video_format="16:9 Landscape",
        target_duration_seconds=30,
        script_text="",
        outline_text="",
        image_count=0,
        voice="Female — Marin",
        voice_vibe="",
    ):
        """
        Video Director — Quill Coach.
        Dedicated Video Director guidance that must never fall back to the
        Writer Edition concept/scripting/plot/manuscript workflow.
        """
        prompt = f"""
You are Quill, the Studio Coach inside WritersBlock Studios — Video Director Edition.

THIS IS VIDEO DIRECTOR, NOT WRITER EDITION.

Never refer to:
- Concept Development
- Scripting sandbox paths
- Plot Architecture
- Creative Draft
- Script Lock
- manuscript workflow
unless the user explicitly asks about the separate Writer Edition.

CURRENT VIDEO DIRECTOR PROJECT:
Project title: {project_title}
Video style: {video_style}
Format: {video_format}
Target length: {target_duration_seconds} seconds
Uploaded images: {image_count}
Narration voice: {voice}
Voice vibe: {voice_vibe or "Not selected yet"}

CURRENT IDEA / OUTLINE:
{outline_text or "None yet"}

CURRENT SCRIPT:
{script_text or "None yet"}

USER QUESTION:
{question}

VIDEO DIRECTOR WORKFLOW:
1. Project title
2. Video style
3. Format
4. Target video length
5. Add or upload still images when available
6. Start from either an idea or an existing script
7. Generate / polish / fit the script to video length
8. Select narration voice and voice vibe
9. Generate narration and measure actual audio duration
10. Assign image timing and motion
11. Apply transitions
12. Add music if desired
13. Render the final MP4 through FFmpeg

RULES:
- Answer the user's actual question directly.
- Keep the response brief and pointed by default.
- If the user asks for detail, give more detail.
- Use Video Director terminology only.
- Do not invent project facts.
- Images are not required before script creation.
- Target length guides script creation; actual narration duration becomes the final production timing clock.
- Edition 1 is a static-image FFmpeg production platform.
""".strip()

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.35),
            )

            response_text = response.text.strip() if response and response.text else ""
            if not response_text:
                raise ValueError("Gemini returned an empty Video Director Quill response.")

            return response_text

        except Exception as exc:
            raise RuntimeError(f"Video Director Quill failed: {exc}") from exc


    def generate_video_script(
        self,
        outline_text,
        video_style,
        video_format,
        target_duration_seconds=30,
        images=None,
    ):
        """
        Video Director — Outline to Script.
        Uses the creator's outline plus uploaded images as visual context.
        Returns clean narration/script text only; image mapping stays internal.
        """
        prompt = f"""
You are Quill working inside WritersBlock Studios — Video Director Edition.

VIDEO STYLE:
{video_style}

VIDEO FORMAT:
{video_format}

TARGET VIDEO LENGTH:
{target_duration_seconds} seconds

CREATOR'S SCRIPT OUTLINE:
{outline_text}

The creator has also uploaded still images for the project. Study those images as visual context.
Use them to understand the people, places, objects, mood, sequence possibilities, and visual emphasis
that should influence the finished script.

TASK:
Write the complete video narration/script from the creator's outline.

STRICT RULES:
- Return ONLY the clean user-facing narration/script.
- Do NOT write @image labels, image numbers, filenames, shot numbers, scene numbers, production notes,
  camera instructions, motion directions, timing instructions, transition notes, music notes, or explanations.
- Do NOT tell the creator where images go.
- Image-to-script placement will be handled internally later by Video Director.
- Preserve the creator's intent and facts.
- Match the selected video style.
- Write naturally for spoken narration unless the creator's outline clearly requires on-screen wording.
- Write to approximately {target_duration_seconds} seconds of spoken narration.
- Use a natural commercial narration pace of roughly 2.1 to 2.4 spoken words per second as a guide.
- Stay close to the target duration rather than producing an unnecessarily long script.
""".strip()

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self._video_director_contents(prompt, images),
                config=types.GenerateContentConfig(temperature=0.65),
            )

            response_text = response.text.strip() if response and response.text else ""
            if not response_text:
                raise ValueError("Gemini returned an empty Video Director script.")

            return response_text

        except Exception as exc:
            raise RuntimeError(f"Video Director script generation failed: {exc}") from exc


    def revise_video_script(
        self,
        script_text,
        action,
        video_style,
        video_format,
        target_duration_seconds=30,
        images=None,
    ):
        """
        Video Director — Quill Assisted Script.
        Revises the visible script while using uploaded images as visual context.
        """
        action_name = str(action or "suggest").strip().lower()

        action_rules = {
            "suggest": (
                f"Develop the user's starting text into a complete narration targeted to approximately "
                f"{target_duration_seconds} seconds. Strengthen clarity, flow, hook, emotional impact, "
                "and fit with the supplied images while preserving the creator's core message."
            ),
            "polish": (
                f"Polish the existing script without changing its core message and keep it targeted to "
                f"approximately {target_duration_seconds} seconds. Improve wording, rhythm, clarity, "
                "natural spoken delivery, transitions, and professional finish."
            ),
            "fit_to_length": (
                f"Fit the script to approximately {target_duration_seconds} seconds of spoken narration. "
                "If it is too long, tighten it while preserving the essential message, strongest ideas, "
                "important facts, and natural spoken flow. If it is already close to the target, make only "
                "minor timing edits. If it is materially too short, expand it naturally enough to approach "
                "the target without adding filler or inventing facts."
            ),
        }

        directive = action_rules.get(action_name, action_rules["suggest"])

        prompt = f"""
You are Quill working inside WritersBlock Studios — Video Director Edition.

VIDEO STYLE:
{video_style}

VIDEO FORMAT:
{video_format}

TARGET VIDEO LENGTH:
{target_duration_seconds} seconds

CURRENT USER SCRIPT:
{script_text}

The creator has uploaded still images for the project. Study those images as visual context.

TASK:
{directive}

STRICT RULES:
- Return ONLY the revised clean user-facing narration/script.
- Do NOT write @image labels, image numbers, filenames, scene numbers, shot numbers, production notes,
  camera directions, motion notes, timing notes, transition notes, music notes, or explanations.
- Do NOT expose the internal image-to-script mapping.
- Preserve names, facts, offers, dates, locations, and other concrete information already supplied unless
  correction is clearly required by the creator's own text.
- Keep the revised result appropriate to the selected video style.
- Use a natural commercial narration pace of roughly 2.1 to 2.4 spoken words per second as a guide.
- Keep the result close to the {target_duration_seconds}-second target.
""".strip()

        try:
            if not self.client:
                raise ValueError("Gemini API key is missing. Add Google Studio API Key.txt beside app.py.")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self._video_director_contents(prompt, images),
                config=types.GenerateContentConfig(
                    temperature=0.55 if action_name != "suggest" else 0.7
                ),
            )

            response_text = response.text.strip() if response and response.text else ""
            if not response_text:
                raise ValueError("Gemini returned an empty Video Director revision.")

            return response_text

        except Exception as exc:
            raise RuntimeError(f"Video Director script revision failed: {exc}") from exc


    def suggest_video_voice_vibe(
        self,
        script_text,
        video_style,
        selected_voice,
    ):
        """Return a concise narration-direction description for OpenAI TTS."""
        prompt = f"""
You are Quill working inside WritersBlock Studios — Video Director Edition.

VIDEO STYLE:
{video_style}

SELECTED VOICE:
{selected_voice}

SCRIPT:
{script_text}

Write one concise narration Voice Vibe description suitable for a text-to-speech engine.

Return ONLY the vibe description. No heading, bullets, explanation, quotation marks, or production notes.
Describe delivery qualities such as warmth, energy, pacing, polish, emotion, restraint, commercial tone,
cinematic quality, whimsy, authority, intimacy, or enthusiasm as appropriate.
""".strip()

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
                raise ValueError("Gemini returned an empty voice-vibe suggestion.")

            return response_text

        except Exception as exc:
            raise RuntimeError(f"Video Director voice-vibe suggestion failed: {exc}") from exc


