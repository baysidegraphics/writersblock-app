"""WritersBlock Studios Gemini API (backward-compatible mixin facade)."""
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types
from engine.plot import PlotMixin
from engine.scenes import ScenesMixin
from engine.revision import RevisionMixin
from engine.picture_book import PictureBookMixin
from engine.video_director import VideoDirectorMixin


class GeminiWriterBackend(PlotMixin, ScenesMixin, RevisionMixin, PictureBookMixin, VideoDirectorMixin):
    def __init__(self, api_key=None, *, client_factory=None):
        """Existing engine, with optional explicit server-side credential injection.

        Legacy callers retain their loader. Customer startup supplies its own
        approved key and never searches ancestor folders or credential files.
        Constructing the SDK client does not generate content.
        """
        self.api_key = self._load_api_key() if api_key is None else str(api_key).strip()
        options = {'api_key': self.api_key}
        if client_factory is None:
            # A commercial action is one provider attempt, never an implicit retry.
            options['http_options'] = types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1))
        self.client = (client_factory or genai.Client)(**options) if self.api_key else None
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



    def _fallback_draft_chunk(self, current_beat_text, rolling_lore, tone_style, error):
        # Commercial requests must never substitute invented local prose for AI.
        # The original engine remains unchanged for explicitly isolated fixtures.
        if getattr(self, "require_live_generation", False):
            raise RuntimeError("Writing service generation failed. No replacement story was generated; saved writing is unchanged.") from None
        return super()._fallback_draft_chunk(current_beat_text, rolling_lore, tone_style, error)
