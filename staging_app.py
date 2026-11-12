"""Temporary in-memory WBS staging entrypoint; no secrets or remote database."""
from pathlib import Path
import runpy
from unittest.mock import patch


def forbidden_client(*args, **kwargs):
    raise PermissionError('Temporary preview does not permit live database or AI clients.')


# Fixture constructs per-session in-memory records and uses actual format workflows.
# Patch scope is restored on Streamlit reruns/exits. No credential file is loaded.
with patch('supabase.create_client', side_effect=forbidden_client), patch('google.genai.Client', side_effect=forbidden_client):
    runpy.run_path(str(Path(__file__).parent/'staging_preview'/'preview.py'), run_name='__main__')
