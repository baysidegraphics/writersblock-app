"""Regression tests for all ten WBS formats, stages 1–5, saves, and reloads.
Run: python -m unittest discover -s tests -v
"""
import ast
import json
from pathlib import Path
import sys
import unittest
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from template_registry import FORMAT_OPTIONS, FORMAT_REGISTRY, get_template, get_quill_instructions
from wbs_format_guard import FORMAT_LEGACY, SavedFormatError, PROJECT_RESTORE_DEFAULTS, prepare_saved_snapshot, project_format_widget_key, require_format_id, validate_format_for_save
STAGES_ONE_TO_FIVE = ['Intake', 'Sandbox', 'Plot Architect', 'Drafting Engine', 'Isolation Guardrail']

class Session(dict):

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key, value):
        self[key] = value

class StreamlitStub:

    def __init__(self):
        self.session_state = Session()
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)

def extracted_loader():
    """Exercise the actual app.py loader without executing Streamlit's full UI."""
    source = (BASE / 'app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    needed = {'load_saved_project_session_to_state'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in needed]
    assert len(nodes) == 1, 'Could not extract production loader functions'
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    st = StreamlitStub()
    namespace = {'st': st, 'json': json, 'WBS_FORMAT_IDS': set(FORMAT_REGISTRY), 'WBS_TEMPLATE_ID_BY_LEGACY_FORMAT': {v: k for k, v in FORMAT_LEGACY.items()}, 'WBS_LEGACY_FORMAT_BY_TEMPLATE_ID': FORMAT_LEGACY, '_wbs_restore_missing_concept_fields': lambda snapshot, *a: (snapshot, dict(recovered_setup=False, recovered_series=False, series_conflict=False, history_unavailable=False)), 'get_project_title_from_project_id': lambda pid: None, 'wbs_save_state_signature': lambda snapshot: 'offline-signature', 'clear_concept_widget_state_for_loaded_project': lambda: [st.session_state.pop(k, None) for k in list(st.session_state) if k.startswith('format_field_')], 'clean_project_version_name': lambda value: value, 'get_best_saved_manuscript_source': lambda snapshot: snapshot.get('current_draft_output', ''), 'set_loaded_concept_version_baseline': lambda snapshot: None, 'count_words': __import__('core.text', fromlist=['count_words']).count_words, 'prepare_saved_snapshot': prepare_saved_snapshot, 'SavedFormatError': SavedFormatError, 'get_wbs_format_template': get_template, 'get_wbs_quill_instructions': get_quill_instructions, 'get_wbs_format_display_name': lambda fmt: get_template(fmt)['display_name']}
    exec(compile(module, str(BASE / 'app.py'), 'exec'), namespace)
    return (st, namespace['load_saved_project_session_to_state'])
