"""Offline test doubles. Never import app.py, create clients, or load secrets."""
import ast
import copy
from datetime import datetime, timezone
import html
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from core.persistence import OwnedClient
from core.saved_scene_state import observe_saved_rows, remember_saved_snapshot
from core.text import count_words, get_text_signature, safe_download_stem
from template_registry import FORMAT_REGISTRY, FORMAT_OPTIONS, get_template, get_quill_instructions, get_format_display_name
from wbs_format_guard import FORMAT_LEGACY, SavedFormatError, prepare_saved_snapshot, validate_format_for_save, project_format_widget_key
from test_format_isolation import Session
ROOT = Path(__file__).resolve().parents[1]
APP_TREE = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))

class Halt(BaseException):
    pass

class UI:

    def __init__(self, state, clicks=()):
        self.session_state = Session(copy.deepcopy(state))
        self.clicks = set(clicks)
        self.trace = []
        self.errors = []
        self.warnings = []
        self.views = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stop(self):
        raise Halt('stop')

    def rerun(self):
        raise Halt('rerun')

    def columns(self, widths, **kw):
        return [self for _ in (range(widths) if isinstance(widths, int) else widths)]

    def empty(self):
        view = SimpleNamespace(markdown=lambda value: self.trace.append(('total', value)))
        self.views.append(view)
        return view

    def button(self, label, **kw):
        self.trace.append(('button', label, kw.get('key')))
        return not kw.get('disabled') and (kw.get('key') in self.clicks or label in self.clicks)

    def form_submit_button(self, label, **kw):
        return self.button(label, **kw)

    def text_area(self, label, value='', **kw):
        return self._value(label, value, kw)

    def text_input(self, label, value='', **kw):
        return self._value(label, value, kw)

    def _value(self, label, value, kw):
        key = kw.get('key')
        result = self.session_state.get(key, value) if key else value
        if key:
            self.session_state[key] = result
        self.trace.append(('field', label, result, key))
        return result

    def selectbox(self, label, options, index=0, **kw):
        return self._value(label, list(options)[index or 0], kw)

    def radio(self, label, options, index=0, **kw):
        return self.selectbox(label, options, index, **kw)

    def number_input(self, label, value=0, **kw):
        return self._value(label, value, kw)

    def checkbox(self, label, value=False, **kw):
        return self._value(label, value, kw)

    def multiselect(self, label, options, default=None, **kw):
        return self._value(label, default or [], kw)

    def data_editor(self, value, **kw):
        return copy.deepcopy(value)

    def file_uploader(self, *a, **kw):
        return None

    def error(self, value):
        self.errors.append(value)
        self.trace.append(('error', value))

    def warning(self, value):
        self.warnings.append(value)
        self.trace.append(('warning', value))

    def __getattr__(self, name):
        if name in {'container', 'expander', 'spinner', 'form', 'popover'}:
            return lambda *a, **kw: self
        if name == 'download_button':
            return lambda *a, **kw: False

        def display(*args, **kw):
            self.trace.append((name,) + args)
        return display

class Query:

    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.filters = []
        self.operation = 'select'
        self.payload = None
        self.maximum = None
        self.sort = None

    def select(self, *a, **kw):
        return self

    def eq(self, key, value):
        self.filters.append(lambda row: row.get(key) == value)
        return self

    def neq(self, key, value):
        self.filters.append(lambda row: row.get(key) != value)
        return self

    def in_(self, key, values):
        self.filters.append(lambda row: row.get(key) in values)
        return self

    def order(self, key, desc=False):
        self.sort = (key, desc)
        return self

    def limit(self, n):
        self.maximum = n
        return self

    def insert(self, payload):
        self.operation = 'insert'
        self.payload = copy.deepcopy(payload)
        return self

    def update(self, payload):
        self.operation = 'update'
        self.payload = copy.deepcopy(payload)
        return self

    def delete(self):
        self.operation = 'delete'
        return self

    def execute(self):
        self.db.queries.append((self.table, self.operation))
        if self.operation != 'select' and self.db.fail_writes:
            raise RuntimeError('Offline injected save failure')
        rows = self.db.rows.setdefault(self.table, [])
        selected = [row for row in rows if all((predicate(row) for predicate in self.filters))]
        if self.sort:
            selected.sort(key=lambda row: row.get(self.sort[0]) or 0, reverse=self.sort[1])
        if self.maximum is not None:
            selected = selected[:self.maximum]
        if self.operation == 'insert':
            selected = self.payload if isinstance(self.payload, list) else [self.payload]
            for row in selected:
                row.setdefault('id', f'row-{self.db.next_id}')
                self.db.next_id += 1
                row.setdefault('created_at', f'2026-11-03T00:00:{self.db.next_id:02d}+00:00')
                rows.append(row)
        elif self.operation == 'update':
            for row in selected:
                row.update(self.payload)
        elif self.operation == 'delete':
            for row in selected:
                rows.remove(row)
        return SimpleNamespace(data=copy.deepcopy(selected))

class Database:

    def rpc(self, name, payload):
        if name != 'wbs_save_project_checkpoint':
            raise ValueError('Unknown isolated RPC')
        db = self

        class Command:

            def execute(self):
                return db.table('writersblock_project_drafts').update({'draft_content': payload['new_content']}).eq('id', payload['target_revision']).eq('project_id', payload['target_project']).eq('user_id', payload['expected_owner']).eq('draft_type', 'project_session').eq('draft_content', payload['expected_content']).execute()
        return Command()

    def __init__(self, snapshot):
        self.next_id = 100
        self.fail_writes = False
        self.queries = []
        self.rows = {'writersblock_projects': [{'id': 'own', 'user_id': 'alice', 'project_title': snapshot['project_title'], 'project_type': snapshot['format_type']}, {'id': 'foreign', 'user_id': 'bob', 'project_title': 'Foreign'}], 'writersblock_project_drafts': [{'id': 'revision-7', 'project_id': 'own', 'user_id': 'alice', 'draft_type': 'project_session', 'version_number': 7, 'draft_content': json.dumps(snapshot, ensure_ascii=False), 'created_at': '2026-11-03T00:00:00+00:00'}], 'writersblock_manuscript_versions': [{'id': 'manuscript-11', 'user_id': 'alice', 'project_id': 'own', 'version_number': 11, 'manuscript_content': snapshot['current_draft_output']}]}

    def table(self, name):
        return Query(self, name)

def snapshot(fmt, scenes=4):
    values = {field['key']: copy.deepcopy(field.get('default', (field.get('options') or ['Original'])[0])) for field in get_template(fmt).get('concept_fields', []) if field.get('key')}
    blocks = {str(i): f'Original scene {i}. The alien waited.\\n\\nNo words were replaced.' for i in range(1, scenes + 1)}
    result = dict(active_format_id=fmt, format_type=FORMAT_LEGACY[fmt], current_project_id='own', project_title="The Alien's Gambit", project_version_name='Original', project_stage='Plot Architect', current_draft_output='\n\n'.join(blocks.values()), scene_blocks=blocks, completed_beats=list(range(1, scenes + 1)), plot_outline='\n'.join((f'[BEAT {i}]\n[SCENE TITLE]: Scene {i}\n[SCENE DETAILS]: {text}\n[CORE OBJECTIVE]: Retain story.' for i, text in blocks.items())), chosen_option='Option C', chosen_option_text="The Alien's Gambit — approved Plot C, exactly.", sandbox_slates={'Option A': 'Original A', 'Option B': 'Original B', 'Option C': "The Alien's Gambit — approved Plot C, exactly.", 'is_fallback': False}, story_seed='Approved original Quill concept.', saved_quill_concept='Approved original Quill concept.', starting_source_mode='Quill Assisted', version_source_mode='Quill Assisted', format_template_values={fmt: values}, manuscript_version=7, current_manuscript_save_version=11, tone_style='Vivid', author_style='', dialogue_style='Balanced', project_scope='Standalone Book', project_integrity_report='Original integrity report', project_integrity_source_signature='', current_processing_beat=0, rolling_lore_book='', export_view=False)
    result['project_integrity_source_signature'] = get_text_signature(result['current_draft_output'])
    return result

def environment(fmt, stage='scene_scripting', clicks=(), scenes=4):
    saved = snapshot(fmt, scenes)
    state = copy.deepcopy(saved)
    state.update(licensed_user_row={'id': 'alice'}, licensed_mode=True, demo_mode=False, backend=None, _wbs_active_saved_session_row_id='revision-7', _wbs_loaded_saved_session_id='revision-7', _wbs_loaded_project_id='own', _wbs_loaded_project_title=saved['project_title'], wbs_locked_format_id=fmt, _wbs_locked_project_id='own', active_format_template=get_template(fmt), quill_format_instructions=get_quill_instructions(fmt), quill_format_name=get_format_display_name(fmt), _wbs_stage3_saved_outline_baseline=saved['plot_outline'], final_output_text='', final_output_source_signature='', final_output_saved_signature='', audiobook_target_word_count=4000, audiobook_length='30 Minutes', picture_book_word_target=800, picture_book_page_size='8.5 x 8.5 Square')
    st = UI(state, clicks)
    db = Database(saved)
    client = OwnedClient(db, lambda: 'alice', lambda table, op, rows, owner: observe_saved_rows(st.session_state, table, op, rows, owner), checkpoint_state=st.session_state)
    remember_saved_snapshot(st.session_state, saved, 'own', 'revision-7', 'alice')
    context = dict(st=st, supabase=client, json=json, re=re, hashlib=hashlib, datetime=datetime, timezone=timezone, SimpleNamespace=SimpleNamespace, SavedFormatError=SavedFormatError, FORMAT_LEGACY=FORMAT_LEGACY, validate_format_for_save=validate_format_for_save, prepare_saved_snapshot=prepare_saved_snapshot, get_wbs_format_template=get_template, get_wbs_quill_instructions=get_quill_instructions, get_wbs_format_display_name=get_format_display_name, WBS_FORMAT_OPTIONS=FORMAT_OPTIONS, WBS_FORMAT_IDS=list(FORMAT_REGISTRY), WBS_LEGACY_FORMAT_BY_TEMPLATE_ID=FORMAT_LEGACY, WBS_TEMPLATE_ID_BY_LEGACY_FORMAT={v: k for k, v in FORMAT_LEGACY.items()}, WBS_SHARED_DEVELOPMENT_KEYS={'project_title', 'dialogue_style', 'story_premise'}, html=html, count_words=count_words, get_text_signature=get_text_signature, safe_download_stem=safe_download_stem, time=SimpleNamespace(sleep=lambda *_: None), create_bridge_adapter=None, WBS_MODEL_IMPORT_ERROR='offline', get_active_project_id=lambda: st.session_state.get('current_project_id'), get_current_user_id=lambda: 'alice', get_project_title=lambda: st.session_state['project_title'], get_project_title_for_display=lambda: st.session_state['project_title'], get_project_title_from_project_id=lambda project: st.session_state['project_title'] if project == 'own' else None, get_effective_format_type=lambda: FORMAT_LEGACY[fmt], is_picture_book_project=lambda: fmt == 'childrens_picture_book', get_dialogue_style_display=lambda: 'Balanced', get_dialogue_style=lambda: 'Balanced', get_dialogue_style_instruction=lambda: 'Preserve dialogue.', get_dialogue_development_packet=lambda: 'Preserve dialogue.', get_active_format_development_context=lambda: 'Original development', get_full_project_continuity_context=lambda: 'Approved continuity', get_plot_dialogue_context=lambda: st.session_state['chosen_option_text'], get_series_aware_story_seed=lambda: st.session_state['story_seed'], refresh_quill_template_context=lambda: {}, get_scripting_format_context=lambda: 'Original format context', get_development_writing_tense=lambda: 'Past', render_project_title_banner=lambda *_: None, require_product_access=lambda *_: None, require_demo_action_available=lambda *_: None, mark_demo_action_used=lambda *_: None, full_version_only_notice=lambda *_: None, set_loaded_concept_version_baseline=lambda *_: None, ensure_project_title_loaded=lambda: None, clean_project_version_name=lambda value: value, get_changed_concept_version_areas=lambda: [], get_suggested_project_version_name=lambda: 'Alternate Version', save_series_metadata_for_project=lambda *_: None, format_field_should_render=lambda *a: True, wbs_save_state_signature=lambda value=None: hashlib.sha256(json.dumps(value or {}, sort_keys=True, default=str).encode()).hexdigest(), wbs_work_has_changed=lambda value=None: True, wbs_has_saved_master=lambda: True, wbs_request_stage_change=lambda *a, **kw: None, ai_output_is_usable=lambda value: isinstance(value, str) and bool(value.strip()), DIALOGUE_STYLE_OPTIONS=['Balanced'], DIALOGUE_STYLE_INSTRUCTIONS={'Balanced': 'Preserve dialogue.'}, FINAL_OUTPUT_FORMAT_OPTIONS=list(FORMAT_LEGACY.values()), PICTURE_BOOK_FORMAT=FORMAT_LEGACY['childrens_picture_book'], DEFAULT_PICTURE_BOOK_PAGE_SIZE='8.5 x 8.5 Square', get_final_output_format=lambda: FORMAT_LEGACY[fmt], get_automatic_output_label=lambda value: value, build_final_output_docx_bytes=lambda *a: b'offline-docx', build_picture_book_spreads_locally=lambda source: [{'text': source}], build_picture_book_layout_docx_bytes=lambda *a: b'offline-docx', project_integrity_review_applies=lambda *a: False, render_save_as_named_version_control=lambda *_: None, wbs_editorial_ready_for_assessment=lambda: True, render_active_format_development_fields=lambda: None, get_active_concept_ui=lambda: {}, get_best_saved_manuscript_source=lambda source=None: (source or st.session_state).get('current_draft_output', ''), clear_concept_widget_state_for_loaded_project=lambda: None, _wbs_restore_missing_concept_fields=lambda value, *a: (value, dict(recovered_setup=False, recovered_series=False, series_conflict=False, history_unavailable=False)), render_quill_for_current_stage=lambda *_a, **_kw: None, extension_quill_renderer=lambda **_kw: None)
    context.update(AUDIOBOOK_LENGTH_OPTIONS={'30 Minutes': {'label': '30 Minutes', 'min_words': 3000, 'max_words': 4500, 'target_words': 4000, 'default_words': 4000}}, PICTURE_BOOK_LAYOUT_TEMPLATES={'Standard': {}}, PICTURE_BOOK_PAGE_SIZES={'8.5 x 8.5 Square': {}}, can_use_rewrite=True, get_active_format_template_values=lambda: st.session_state['format_template_values'][fmt], get_current_project_version_name=lambda: 'Original', get_existing_series_names=lambda: [], get_next_series_book_number=lambda *a: 1, get_saved_projects_versions_dropdown_items=lambda: [], get_series_metadata_by_project=lambda: {}, get_series_reference_candidates=lambda: [], get_unambiguous_series_project_ids=lambda *a: [], make_series_key=lambda value: value, render_save_open_project_to_series=lambda: None, sandbox_output_is_usable=lambda value: bool(value), save_project_to_supabase=lambda **kw: None, wbs_can_generate_first_paths_for_saved_concept=lambda: False, wbs_concept_contains_editorial_commentary=lambda *a: False, wbs_get_saved_concept_setup_audit=lambda: {'ok': True, 'recorded': [], 'missing': []}, extract_uploaded_manuscript_text=lambda *a: '', wbs_stage2_complete_plot_source_packet=lambda: 'Original source', wbs_stage2_render_regenerate_novel_plots=lambda: None, build_audiobook_production_docx_bytes=lambda *a: b'offline-docx', build_picture_book_cue_script=lambda value: value, delete_manuscript_version_ids=lambda *a: None, get_audiobook_length_spec=lambda: {'label': '30 Minutes', 'min_words': 3000, 'max_words': 4500, 'target_words': 4000, 'default_words': 4000}, get_audiobook_production_instruction=lambda *a: 'Report only', get_manuscript_version_status_stage=lambda row: 'Saved', get_manuscript_versions_for_current_project=lambda: [], get_picture_book_page_size_spec=lambda *a: {'width': 8.5, 'height': 8.5}, normalize_picture_book_spreads=lambda value: value, persist_project_integrity_in_current_version=lambda *a: None, picture_book_cues_docx_bytes=lambda *a: b'offline-docx', render_picture_book_template_preview=lambda *a: None, render_project_integrity_report_html=lambda *a, **kw: None, run_project_integrity_final_review=lambda *a: None, save_manuscript_checkpoint=lambda *a: None, save_picture_book_layout_to_supabase=lambda *a: None, save_project_draft_to_supabase=lambda *a: None, save_stage5_lettered_revision=lambda *a: None, wbs_clear_new_project_ui_state=lambda: None, wbs_ir_go_to_scene=lambda *a: None, wbs_ir_located_issues=lambda *a, **kw: [], wbs_ir_parse_actionable_finding=lambda *a: None)
    from io import BytesIO
    context['BytesIO'] = BytesIO
    for name in ('Document', 'Inches', 'Pt'):
        context[name] = lambda *a, **kw: None
    tree = APP_TREE
    names = {'clear_concept_widget_state_for_loaded_project', 'save_project_to_supabase', 'get_project_session_snapshot', 'wbs_merge_live_concept_widgets_into_snapshot', 'wbs_validate_setup_for_save', 'wbs_expected_saved_development_fields', 'save_current_project_session_to_supabase', 'get_next_project_session_internal_version', 'load_saved_project_session_to_state'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'offline-app-functions', 'exec'), context)
    context.update(set_active_format_template_value=lambda key, value: st.session_state['format_template_values'][fmt].__setitem__(key, value), wbs_stage2_regenerated_plots_usable=lambda value: True, wbs_stage2_verify_regen_source=lambda: True, picture_book_age_budget_rules=lambda: (600, 800, '5-9'), picture_book_allocations=lambda: [200, 200, 200, 200], picture_book_target=lambda: 800)
    context['get_active_format_widget_key'] = lambda field: project_format_widget_key(st.session_state.get('current_project_id'), 'revision-7', fmt, field)
    return (saved, st, db, context)
