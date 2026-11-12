"""Loopback-only integration harness. No application startup, secrets or live clients.

This deliberately does not pretend to authenticate a real user. It loads an
explicit synthetic session and preapproves synthetic writing using real callbacks.
"""
from pathlib import Path
import ast
import copy
import json
import sys
import os
import streamlit as st
ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'staging_preview'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
st.set_page_config(page_title='WBS Local Isolated Staging', layout='wide')
st.warning('TEMPORARY SYNTHETIC PREVIEW — no Supabase or production connection. Saving and revisions remain in this browser session only. Synthetic test data resets on server restart, session loss or reconnect. Gemini and Quill AI responses are simulated; Kokoro speech remains available.')
from synthetic_projects import project, install_exports
from offline_app import APP_TREE
from test_extension_journeys import install_services
from core.workflow_runtime import run_workflow, call_format_helper
from core.extended_quill import ExtensionQuillBridge, ReadOnlyBackendAgent
from quill.wbs_quill_runtime_bridge import QuillRuntimeBridge
from quill.wbs_quill_streamlit_ui import render_quill_studio_coach, VOICE_ENABLED_KEY
from sidebar.summary import render_saved_scene_total
from template_registry import FORMAT_REGISTRY, get_format_display_name
from types import SimpleNamespace

class LocalModels:

    def __init__(self):
        self.calls = []
        self.fail = False

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError('Injected isolated model outage')
        return SimpleNamespace(text='LOCAL MOCK RESPONSE: Review the supplied writing and keep the approved plot unchanged.')
from engine.revision import RevisionMixin

class LocalBackend(RevisionMixin):

    def __init__(self):
        self.client = SimpleNamespace(models=LocalModels())
        self.model_name = 'isolated-mock'

    def run_revision_pass(self, *args):
        return self.client.models.generate_content(contents=str(args)).text
route = st.query_params.get('format', 'biography_memoir')
fmt, _, route_view = str(route).partition(':')
if fmt not in FORMAT_REGISTRY:
    st.error('Unknown isolated format.')
    st.stop()
_preview_globals = {'_preview_format_selector', '_preview_workspaces', '_preview_active_format'}
if '_preview_format_selector' not in st.session_state:
    st.session_state['_preview_format_selector'] = fmt

def switch_preview_format():
    state = st.session_state
    selected = state['_preview_format_selector']
    if selected not in FORMAT_REGISTRY:
        raise ValueError('Unknown preview format')
    previous = state.get('_preview_active_format')
    if previous == selected:
        return
    workspaces = state.get('_preview_workspaces', {})
    if previous and '_staging_context' in state:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        runtime = get_script_run_ctx().session_state._state
        transient = {runtime._key_id_mapper.id_key_mapping.get(widget_id) for widget_id, metadata in runtime._new_widget_state.widget_metadata.items() if metadata.value_type in {'trigger_value', 'string_trigger_value', 'chat_input_value', 'file_uploader_state_value'} or type(getattr(metadata.deserializer, '__self__', None)).__name__ == 'DataEditorSerde'}
        workspaces[previous] = {k: v for k, v in state.items() if k not in _preview_globals and k not in transient}
    for name in list(state):
        if name not in _preview_globals:
            del state[name]
    if selected in workspaces:
        state.update(workspaces[selected])
    state['_preview_workspaces'] = workspaces
    state['_preview_active_format'] = selected
    st.query_params['format'] = selected
    if 'view' in st.query_params:
        del st.query_params['view']
with st.sidebar:
    st.selectbox('Preview writing format', list(FORMAT_REGISTRY), format_func=get_format_display_name, key='_preview_format_selector', on_change=switch_preview_format)
    st.caption('Each format has its own synthetic V7 project, saved revisions and working edits. Switching preserves them in this browser session.')
fmt = st.session_state['_preview_format_selector']
st.session_state['_preview_active_format'] = fmt
if '_staging_context' not in st.session_state:
    saved, fake, db, context = project(fmt)
    if fmt == 'childrens_picture_book' and st.query_params.get('pages') == '32':
        saved['scene_blocks'] = {str(i): 'Synthetic page ' + str(i) + '. The fox waits by the door.' for i in range(1, 33)}
        saved['current_draft_output'] = '\n\n'.join(saved['scene_blocks'].values())
        saved['format_template_values'][fmt]['structure_preferences'] = {'unit_target': 32}
        fake.session_state.update(copy.deepcopy(saved))
        db.rows['writersblock_project_drafts'][0]['draft_content'] = json.dumps(saved)
    if st.query_params.get('image_demo') == '1':
        from core.inline_images import SUPPORTED, upload, place
        if fmt in SUPPORTED:
            from PIL import Image, ImageDraw
            from io import BytesIO
            image = Image.new('RGB', (300, 180), '#164859')
            paint = ImageDraw.Draw(image)
            paint.ellipse((200, 20, 250, 70), fill='#ffcf64')
            paint.polygon([(0, 180), (100, 70), (240, 180)], fill='#52ad83')
            stream = BytesIO()
            image.save(stream, format='PNG')
            unit = next(iter(saved['scene_blocks']))
            text = saved['scene_blocks'][unit]
            asset = upload(saved, stream.getvalue(), 'staging_image.png')
            align = st.query_params.get('image_align', 'Left')
            place(saved, unit, text, text.find(' ') + 1, asset, 'Medium', align if align in ('Left', 'Center', 'Right') else 'Left')
            fake.session_state.update(copy.deepcopy(saved))
            db.rows['writersblock_project_drafts'][0]['draft_content'] = json.dumps(saved)
    st.session_state.update(copy.deepcopy(dict(fake.session_state)))
    fake.session_state = st.session_state
    context['supabase']._checkpoint_state = st.session_state
    context['st'] = st
    install_services(context)
    install_exports(context)
    context['get_dialogue_style_display'] = lambda value=None: 'Story-Driven / Automatic'
    context['get_dialogue_style'] = lambda: st.session_state.get('dialogue_style', 'Story-Driven / Automatic')
    context['DIALOGUE_STYLE_OPTIONS'] = ['Story-Driven / Automatic']
    context['DIALOGUE_STYLE_INSTRUCTIONS'] = {'Story-Driven / Automatic': 'Preserve the supplied dialogue.'}
    context['access_allows'] = lambda *_: True
    context['wbs_stage4_final_status'] = lambda *a, **kw: call_format_helper('wbs_stage4_final_status', context, *a, **kw)
    context['get_saved_projects_versions_dropdown_items'] = lambda: [{'type': 'project_session', 'row': r, 'label': f"Synthetic V-{r.get('version_number')}"} for r in db.rows['writersblock_project_drafts'] if r.get('draft_type') == 'project_session']
    context['load_saved_project_session_to_state'](copy.deepcopy(db.rows['writersblock_project_drafts'][0]))
    if fmt in {'biography_memoir', 'childrens_interactive_educational'}:
        from core.format_services import approve
        if not approve(context, fmt):
            st.error('Synthetic approval setup failed.')
            st.stop()
    elif fmt != 'novel_prose_novella' and (not (fmt == 'childrens_picture_book' and st.query_params.get('pages') == '32')):
        call_format_helper('wbs_stage4_accept_and_save', context)
        for component in ('title', 'manuscript', 'integrity'):
            call_format_helper('wbs_stage4_save_final_acceptance', context, component)
    st.session_state.backend = LocalBackend()
    st.session_state[VOICE_ENABLED_KEY] = False
    if st.query_params.get('voice_test') in {'Male', 'Female'}:
        from quill.modular_context import prepare
        prepare(st.session_state)
        from quill.wbs_quill_streamlit_ui import initialize_quill_state
        initialize_quill_state(st.session_state)
        from quill.wbs_quill_streamlit_ui import VOICE_GENDER_KEY, LAST_RESPONSE_KEY, CHAT_HISTORY_KEY
        sample = 'This is Quill, your Frontline Editor in Chief. Voice playback is optional. This is the complete synthetic test response.'
        st.session_state[VOICE_ENABLED_KEY] = True
        st.session_state[VOICE_GENDER_KEY] = st.query_params['voice_test']
        st.session_state[LAST_RESPONSE_KEY] = sample
        st.session_state[CHAT_HISTORY_KEY] = [{'role': 'assistant', 'content': sample, 'source': 'synthetic_voice_test'}]
    receipt_path = os.environ.get('WBS_QUILL_LIVE_RESULT')
    st.session_state['_staging_context'] = context
    st.session_state['_staging_db'] = db
    st.session_state['_staging_original'] = copy.deepcopy(saved)
context = st.session_state['_staging_context']
db = st.session_state['_staging_db']
context['_wbs_scene_total_views'] = []

def synthetic_integrity(text):
    if st.session_state.get('_staging_fail_integrity'):
        raise RuntimeError('Injected synthetic integrity outage')
    from core.integrity_review import numbered_context
    annotated = numbered_context(st.session_state)
    return 'OVERALL STATUS: PASS\nSYNTHETIC MOCK ONLY — format boundaries reviewed offline.\n' + annotated
context['run_project_integrity_final_review'] = synthetic_integrity
context['render_project_integrity_report_html'] = lambda report, **kw: '<pre>' + __import__('html').escape(report) + '</pre>'
context['project_integrity_review_applies'] = lambda *a: True
from synthetic_projects import install_app_definitions
install_app_definitions(context, {'persist_project_integrity_in_current_version'})
st.caption('LOCAL ISOLATED STAGING · synthetic session · in-memory database · mocked AI · no real authentication · RUN ' + os.environ.get('WBS_LOCAL_STAGING_RUN', 'AppTest'))

def render_quill(**kwargs):
    bridge = kwargs.get('bridge')
    if bridge is None:
        quill_backend = st.session_state.get('_wbs_quill_test_backend') if st.session_state.get('_wbs_quill_test_mode') else st.session_state.backend
        agent = ReadOnlyBackendAgent(quill_backend)
        bridge = ExtensionQuillBridge(agent) if fmt in {'biography_memoir', 'childrens_interactive_educational'} else QuillRuntimeBridge(agent)
    return render_quill_studio_coach(bridge=bridge, st_module=st, show_prelude=False, display_name='Staging Tester')
context['extension_quill_renderer'] = render_quill
context['render_quill_for_current_stage'] = render_quill
context['render_project_title_banner'] = lambda *_: render_quill()
requested_view = route_view or st.query_params.get('view', '1')
if requested_view not in {'1', '2', '3', '4', '5', '6'}:
    st.error('Unknown isolated verification view.')
    st.stop()
if '_staging_view_initialized' not in st.session_state:
    st.session_state['_staging_view_initialized'] = True
    if requested_view in {'2', '3', '4'}:
        context['wbs_request_stage_change']({'2': 'Sandbox', '3': 'Plot Architect', '4': 'Isolation Guardrail'}[requested_view], export_view=False)
    elif requested_view == '5':
        st.session_state.project_stage = 'Publisher Assessment'
    elif requested_view == '6':
        from core.integrity_review import run as run_integrity
        run_integrity(context)
        from core.manuscript_structure import profile, configured, commit, unit_plan
        if profile(fmt)['structured_editor']:
            commit(context, unit_plan(st.session_state), accept=True)
        elif fmt in {'biography_memoir', 'childrens_interactive_educational'}:
            from core.format_services import approve
            if not approve(context, fmt):
                st.error('Synthetic final approval failed.')
                st.stop()
        else:
            call_format_helper('wbs_stage4_accept_and_save', context)
            for component in ('title', 'manuscript', 'integrity'):
                call_format_helper('wbs_stage4_save_final_acceptance', context, component)
        from core.publisher_assessment import read_saved_revision
        from core.text import get_text_signature
        row_id = st.session_state['_wbs_active_saved_session_row_id']
        _, _, source = read_saved_revision(context['supabase'], 'own', 'alice', row_id, fmt)
        st.session_state['_wbs_stage5_passport'] = ('own', row_id, get_text_signature(source))
        context['wbs_request_stage_change']('Isolation Guardrail', export_view=True)
active = st.session_state.get('_wbs_active_saved_session_row_id')
context['_active_version_number'] = next((r.get('version_number') for r in db.rows['writersblock_project_drafts'] if r['id'] == active), '')

def checkpoint_control():
    result = context['save_current_project_session_to_supabase']()
    st.session_state['_staging_notice'] = 'Synthetic checkpoint confirmed' if result else 'Synthetic checkpoint failed'

def branch_control():
    st.session_state.author_style = 'Synthetic staging editorial preference'
    result = context['save_current_project_session_to_supabase']('Browser staging branch', True)
    st.session_state['_staging_notice'] = 'Synthetic branch confirmed' if result else 'Synthetic branch failed'
with st.sidebar:
    st.markdown('### Temporary preview saves')
    st.caption('Synthetic account only. No real authentication or remote storage.')
    rows = [r for r in db.rows['writersblock_project_drafts'] if r.get('draft_type') == 'project_session']
    selected = st.selectbox('Saved synthetic revision', [r['id'] for r in rows], key='_staging_revision')
    if st.button('Reload saved revision', key='_staging_reload'):
        context['load_saved_project_session_to_state'](copy.deepcopy(next(r for r in rows if r['id'] == selected)))
        st.rerun()
    st.button('Save checkpoint', key='_staging_checkpoint', on_click=checkpoint_control)
    st.button('Create synthetic revision', key='_staging_branch', on_click=branch_control)
    if st.session_state.get('_staging_notice'):
        st.caption(st.session_state['_staging_notice'])
    render_saved_scene_total(st, context)

start = next((i for i, n in enumerate(APP_TREE.body) if isinstance(n, ast.Assign) and any((isinstance(t, ast.Name) and t.id == '_wbs_unlocked' for t in n.targets))))
end = next((i for i, n in enumerate(APP_TREE.body[start:], start) if isinstance(n, ast.If) and any((isinstance(c, ast.keyword) and c.arg == 'key' and isinstance(c.value, ast.Constant) and (c.value.value == 'nav_export') for c in ast.walk(n)))))
exec(compile(ast.Module(body=APP_TREE.body[start:end + 1], type_ignores=[]), 'isolated-real-sidebar', 'exec'), context)
stage = st.session_state.project_stage
name = {'Intake': 'concept_development', 'Sandbox': 'plot_architecture', 'Plot Architect': 'scene_scripting', 'Publisher Assessment': 'publisher_assessment'}.get(stage, 'final_manuscript' if st.session_state.get('export_view') else 'editorial_review')
if name == 'final_manuscript' and st.query_params.get('legacy_final') == '1':
    name = 'editorial_review'
run_workflow(name, context)
