"""Temporary in-memory WBS staging entrypoint; no secrets or remote database."""
from pathlib import Path
import runpy
from unittest.mock import patch
from staging_preview.logo import render as render_staging_logo
from staging_preview.kokoro_diagnostics import synthesize as staging_synthesize


def forbidden_client(*args, **kwargs):
    raise PermissionError('Temporary preview does not permit live database or AI clients.')


# Fixture constructs per-session in-memory records and uses actual format workflows.
# Patch scope is restored on Streamlit reruns/exits. No credential file is loaded.
with patch('supabase.create_client', side_effect=forbidden_client), patch('google.genai.Client', side_effect=forbidden_client), patch('quill.wbs_quill_streamlit_ui._render_quill_logo', render_staging_logo), patch('quill.wbs_quill_streamlit_ui._generate_quill_voice', staging_synthesize):
    runpy.run_path(str(Path(__file__).parent/'staging_preview'/'preview.py'), run_name='__main__')
