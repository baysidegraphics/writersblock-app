"""Customer startup boundary: explicit server configuration, no synthetic controls."""
import hashlib,os
from pathlib import Path

def load_local_environment():
    from dotenv import load_dotenv
    # Exact app-local file only. Never discover a parent Commercial .env.
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1]/'.env',override=False)

def configured_key(secrets,environ=None):
    environ=os.environ if environ is None else environ
    value=environ.get('GEMINI_API_KEY','')
    if not str(value or '').strip():
        try:value=secrets.get('GEMINI_API_KEY','')
        except Exception:value=''
    value=str(value or '').strip()
    if value and (any(ord(c)<33 or ord(c)>126 for c in value) or '"' in value or "'" in value):
        raise ValueError('Writing service configuration is invalid. Contact the application owner.')
    return value

def customer_backend(state,secrets,environ=None,client_factory=None):
    from gemini_backend import GeminiWriterBackend
    for key in list(state):
        if str(key).startswith('_wbs_quill_test_') or key in ('_wbs_quill_force_test_ai','_staging_context','_staging_db','_staging_original'):
            state.pop(key,None)
    value=configured_key(secrets,environ)
    fingerprint=hashlib.sha256(value.encode()).hexdigest()
    if not isinstance(state.get('backend'),GeminiWriterBackend) or state.get('_wbs_gemini_configuration')!=fingerprint:
        state['backend']=GeminiWriterBackend(api_key=value,client_factory=client_factory)
        state['_wbs_gemini_configuration']=fingerprint
    state['backend'].require_live_generation=True
    return state['backend']
