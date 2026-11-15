"""Isolated WBS staging: real Gemini SDK and no remote database."""
from pathlib import Path
import runpy
from unittest.mock import patch
from staging_preview.logo import render as render_staging_logo
from staging_preview.kokoro_diagnostics import synthesize as staging_synthesize
from staging_preview import live_ai

def forbidden_client(*args, **kwargs):
    raise PermissionError("Staging does not permit remote database clients.")

# The SDK must remain real during initialization. The live_ai gateway limits requests.
with patch("supabase.create_client", side_effect=forbidden_client), patch("quill.wbs_quill_streamlit_ui._render_quill_logo", render_staging_logo), patch("quill.wbs_quill_streamlit_ui._generate_quill_voice", staging_synthesize):
    runpy.run_path(str(Path(__file__).parent / "staging_preview" / "preview.py"), run_name="__main__")
