"""Frozen commercial UI, private read-only acceptance only. Not for production.

No fixture, reconstructed project or generated writing is loaded. The original
314 commercial files stay byte-identical. Private adapters disable integrations
and permit navigation for inspection without saving approval milestones.
"""
import ast
import hashlib
import json
from pathlib import Path
from staging_owner_interface import (
    APP_SHA256, AcceptanceBlocked, ReadAuth, ReadUI, InterfaceImports, ReadDatabase, workflow_records,
)


class CommercialUI(ReadUI):
    # All project switches go through the explicit Projects opening gate.
    NAVIGATION = ReadUI.NAVIGATION - {'sidebar_load_saved_item'}
    def __getattr__(self, name):
        if name == 'sidebar':
            return CommercialUI(self._ui.sidebar)
        if name in {'container', 'expander', 'form', 'popover', 'empty', 'tabs', 'columns'}:
            def containers(*args, **kwargs):
                result = getattr(self._ui, name)(*args, **kwargs)
                return [CommercialUI(item) for item in result] if isinstance(result, list) else CommercialUI(result)
            return containers
        if name in {'button', 'form_submit_button', 'download_button', 'file_uploader',
                    'link_button', 'page_link', 'chat_input'}:
            def action(*args, **kwargs):
                key = str(kwargs.get('key') or '')
                kwargs.pop('on_click', None)
                if name == 'button' and key in self.NAVIGATION:
                    return self._ui.button(*args, **kwargs)
                kwargs['disabled'] = True
                if name in {'link_button', 'page_link'}:
                    return self._ui.button(str(args[0]) if args else 'Unavailable', disabled=True,
                                           key=key or None)
                return getattr(self._ui, name)(*args, **kwargs)
            return action
        if name == 'radio':
            def radio(*args, **kwargs):
                kwargs.pop('on_change', None)
                kwargs['disabled'] = True
                return self._ui.radio(*args, **kwargs)
            return radio
        return super().__getattr__(name)


class CommercialImports(InterfaceImports):
    REPLACEMENTS = {**InterfaceImports.REPLACEMENTS,
        'wbs_streamlit_adapter': {'create_bridge_adapter': '_r2_blocked_bridge'}}
    def visit_With(self, node):
        # Only the redundant commercial activation panel is suppressed. Owner
        # authentication remains in the private staging entrypoint.
        if any(isinstance(i.context_expr, ast.Call)
               and any(isinstance(a, ast.Constant) and a.value == 'License / Trial'
                       for a in i.context_expr.args) for i in node.items):
            return None
        return self.generic_visit(node)

    def visit_If(self, node):
        if any(isinstance(n, ast.Constant) and n.value == 'License: Writer Edition — Active'
               for statement in node.body for n in ast.walk(statement)):
            return ast.copy_location(ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='st', ctx=ast.Load()), attr='caption', ctx=ast.Load()),
                args=[ast.Constant('Verified linked owner — read-only acceptance; no license changed.')], keywords=[])), node)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if names & {'_startup_access_active', '_wbs_stage5_ready', '_wbs_stage6_ready'}:
            node.value = ast.Constant(True)
        if '_wbs_unlocked' in names:
            # Ephemeral UI eligibility only, never a saved approval/passport.
            node.value = ast.Constant(5)
        if '_saved_status_items' in names:
            node.value = ast.Call(func=ast.Name(id='get_saved_projects_versions_dropdown_items', ctx=ast.Load()), args=[], keywords=[])
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == 'wbs_stage2_render_regenerate_novel_plots':
            # The frozen Stage 2 renderers call this compatibility hook even
            # outside Novel/Novella. Do not dispatch a sibling-owned helper.
            node.body.insert(0, ast.If(test=ast.Compare(
                left=ast.Call(func=ast.Attribute(value=ast.Attribute(
                    value=ast.Name(id='st',ctx=ast.Load()),attr='session_state',ctx=ast.Load()),
                    attr='get',ctx=ast.Load()),args=[ast.Constant('active_format_id')],keywords=[]),
                ops=[ast.NotEq()],comparators=[ast.Constant('novel_prose_novella')]),
                body=[ast.Return(value=ast.Constant(None))],orelse=[]))
        if node.name == 'wbs_request_stage_change':
            node.body = [ast.Return(value=ast.Call(
                func=ast.Name(id='_r2_navigate', ctx=ast.Load()),
                args=[ast.Name(id='destination', ctx=ast.Load()), ast.Name(id='export_view', ctx=ast.Load())], keywords=[]))]
        return super().visit_FunctionDef(node)


def project_selection(ui, owner):
    """An explicit owner action is required; merely listing never opens a project."""
    from wbs_format_guard import resolve_saved_format, SavedFormatError
    from template_registry import FORMAT_REGISTRY, get_format_display_name
    state = ui.session_state
    gate = (owner.subject, 'projects-first-v1')
    if state.get('_r2_project_gate') != gate:
        state['_r2_project_gate'] = gate
        state.pop('_r2_project_selection', None)
    chosen = state.get('_r2_project_selection')
    if chosen and chosen.get('subject') == owner.subject:
        return chosen
    ui.header('Projects')
    ui.caption('Choose a project before opening a writing format or stage. This private staging session cannot save changes.')
    action = ui.radio('Choose an action', ['Open an existing saved project', 'Create a new project'],
                      index=None, key='_r2_project_action')
    database = ReadDatabase(owner)
    def rows(table, **filters):
        result = []
        for start in range(0, 10000, 200):
            query = database.table(table).select('*')
            for key, value in filters.items():query = query.eq(key, str(value))
            page = query.order('id').range(start, start + 199).execute().data or []
            result.extend(page)
            if len(page) < 200:return result
        raise AcceptanceBlocked('Project list limit reached.')
    if action == 'Open an existing saved project':
        projects = rows('writersblock_projects')
        if not projects:
            ui.info('No saved projects belong to this linked account.')
            return None
        project_id = ui.selectbox('Saved project', [str(p['id']) for p in projects], index=None,
            format_func=lambda value: next(str(p.get('project_title') or '(saved title missing)') + ' · ' + str(i + 1)
                for i,p in enumerate(projects) if str(p['id']) == value), key='_r2_picker_project')
        if project_id is None:return None
        project = next(p for p in projects if str(p['id']) == project_id)
        drafts = rows('writersblock_project_drafts', project_id=project_id)
        snapshots = workflow_records(drafts, project_id)
        revision = None
        if snapshots:
            ids = [str(r['id']) for r in snapshots]
            key = '_r2_picker_revision_' + project_id
            revision_id = ui.selectbox('Saved workflow revision', ids, index=None,
                format_func=lambda value: next('V' + str(r.get('version_number','')) + ' — ' + str(r.get('draft_title') or 'Saved revision') + ' · ' + str(i + 1)
                    for i,r in enumerate(snapshots) if str(r['id']) == value), key=key)
            if revision_id is None:return None
            revision = next(r for r in snapshots if str(r['id']) == revision_id)
            payload = json.loads(revision['draft_content'])
            fmt = resolve_saved_format(payload)
        else:
            ui.info('No workflow revision is recorded for this project. Opening shows its saved title and format only; separate drafts are not reconstructed into missing stages.')
            try:
                stored_format = project.get('project_type')
                fmt = resolve_saved_format({'active_format_id': stored_format} if stored_format in FORMAT_REGISTRY else {'format_type': stored_format})
            except SavedFormatError:
                ui.warning('The saved writing format is not recognized. This project will not be opened under an assumed format.')
                return None
        if ui.button('Open selected project', key='_r2_open_selected_project'):
            owner.require_owner()
            state['_r2_project_selection'] = dict(kind='existing', subject=owner.subject,
                project=project, revision=revision, format=fmt, title=str(project.get('project_title') or ''))
            ui.rerun()
    elif action == 'Create a new project':
        ui.caption('Creates an unsaved preview in this private browser only. No database project or saved revision is created.')
        with ui.form('_r2_new_project_form'):
            title = ui.text_input('Project title', key='_r2_new_project_title')
            fmt = ui.selectbox('Writing format', list(FORMAT_REGISTRY), index=None,
                               format_func=get_format_display_name, key='_r2_new_project_format')
            create = ui.form_submit_button('Create new project preview')
        if create:
            if not str(title or '').strip() or fmt not in FORMAT_REGISTRY:
                ui.warning('Enter a project title and choose its writing format.')
            else:
                owner.require_owner()
                state['_r2_project_selection'] = dict(kind='new', subject=owner.subject,
                    title=title.strip(), format=fmt, project=None, revision=None)
                ui.rerun()
    return None


def run_interface(ui, auth, owner_email, app_path):
    source = Path(app_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != APP_SHA256:
        raise AcceptanceBlocked('Frozen commercial source mismatch.')
    owner = ReadAuth(auth, owner_email)
    owner.refresh_account()
    state = ui.session_state
    selected = project_selection(ui, owner)
    if selected is None:return
    if selected['kind'] == 'existing':
        boundary = ReadDatabase(owner)
        actual = boundary.table('writersblock_projects').select('*').eq('id',str(selected['project']['id'])).limit(1).execute().data or []
        if len(actual) != 1:
            state.pop('_r2_project_selection', None)
            raise AcceptanceBlocked('Selected project ownership could not be reverified.')
        selected['project'] = actual[0]
        selected['title'] = str(actual[0].get('project_title') or '')
        if selected.get('revision'):
            actual_revision = boundary.table('writersblock_project_drafts').select('*').eq('id',str(selected['revision']['id'])).eq('project_id',str(actual[0]['id'])).limit(1).execute().data or []
            if len(actual_revision) != 1 or not workflow_records(actual_revision,str(actual[0]['id'])):
                state.pop('_r2_project_selection', None)
                raise AcceptanceBlocked('Selected revision ownership or format could not be reverified.')
            selected['revision'] = actual_revision[0]
    if ui.button('Projects', key='_r2_back_to_projects'):
        state.pop('_r2_project_selection', None)
        state.pop('_r2_project_action', None)
        state.pop('_r2_picker_project', None)
        ui.rerun()
    from wbs_format_guard import FORMAT_LEGACY
    record = selected.get('revision')
    project = selected.get('project')
    if record:
        ui.caption('Selected saved workflow revision: V' + str(record.get('version_number','')))
    elif project:
        ui.caption('Existing project — no workflow revision recorded. Existing drafts remain unchanged; no stages have been reconstructed.')
    else:
        ui.caption('New unsaved project preview — no database record or saved revision has been created.')
    workspace = (owner.subject, APP_SHA256, 'native-commercial-ui-projects-v2', selected['kind'],
                 str(project.get('id') if project else ''), str(record.get('id') if record else ''), selected['title'], selected['format'])
    needs_load = state.get('_r2_frozen_acceptance_workspace') != workspace
    if needs_load:
        # Keep earlier inspection state in private session memory. Do not turn
        # its stage records into a new or reconstructed commercial project.
        kept = {'_wbs_auth_controller'}
        old = {k: state[k] for k in list(state)
               if k not in kept and not str(k).startswith(('_r2_', 'r2_'))}
        state['_r2_prior_inspection_workspace'] = old
        for key in old:
            state.pop(key, None)
        state['_r2_frozen_acceptance_workspace'] = workspace
        state['active_format_id'] = selected['format']
        state['format_type'] = FORMAT_LEGACY[selected['format']]
        state['project_title'] = selected['title']
        state['project_title_input'] = selected['title']
        if project:
            state['current_project_id'] = str(project['id'])
            state['_wbs_loaded_project_id'] = str(project['id'])
            state['_wbs_loaded_project_title'] = selected['title']
            state['_wbs_locked_project_id'] = str(project['id'])
            state['wbs_locked_format_id'] = selected['format']
    state['backend'] = None
    rendered_quill = False
    proxy = CommercialUI(ui)

    def no_backend(session, *args, **kwargs):
        session['backend'] = None
        return None

    class BlockedBridge:
        def execute(self, *args, **kwargs):
            raise AcceptanceBlocked('Generation is disabled for private read-only acceptance.')

    def verify_read():
        owner.require_owner()
        return True

    def sync_read_account(session, *args):
        verify_read()
        session['licensed_mode'] = False
        session['demo_mode'] = False
        return True

    def navigate(destination, export_view=None):
        verify_read()
        if destination not in {'Intake', 'Sandbox', 'Plot Architect', 'Isolation Guardrail', 'Publisher Assessment'}:
            raise AcceptanceBlocked('Unknown inspection stage.')
        state['project_stage'] = destination
        state['export_view'] = bool(export_view) if destination == 'Isolation Guardrail' else False
        ui.rerun()

    def load_selected(namespace):
        if needs_load and record:
            if not namespace['load_saved_project_session_to_state'](record):
                state.pop('_r2_frozen_acceptance_workspace', None)
                raise AcceptanceBlocked('Selected saved workflow could not be restored.')

    def render_quill(*args, **kwargs):
        nonlocal rendered_quill
        if rendered_quill:
            return None
        rendered_quill = True
        from quill.wbs_quill_streamlit_ui import render_quill_studio_coach, VOICE_ENABLED_KEY, VOICE_STOP_KEY
        state[VOICE_ENABLED_KEY] = False
        state[VOICE_STOP_KEY] = False
        # Render the approved panel itself without starting the agent/provider.
        # SEND/revision/audio controls are disabled through the UI adapter.
        return render_quill_studio_coach(st_module=proxy, show_prelude=False,
                                        bridge=kwargs.get('bridge'), display_name=kwargs.get('display_name', ''))

    namespace = {'__name__': '__main__', '__file__': str(Path(app_path).resolve()),
        '_r2_ui': proxy, '_r2_controller': lambda *args, **kwargs: owner,
        '_r2_backend': no_backend, '_r2_noop': lambda *args, **kwargs: None,
        '_r2_quill': render_quill, '_r2_sync': sync_read_account,
        '_r2_verify_read': verify_read, '_r2_navigate': navigate,
        '_r2_load_selected': load_selected,
        'extension_quill_renderer': render_quill,
        '_r2_blocked_bridge': lambda *args, **kwargs: BlockedBridge()}
    ui.caption('Frozen R2 commercial interface. Navigation is inspection-only; no Reflections workflow is reconstructed. Writing, approvals, saves, AI, audio generation and payments are disabled.')
    tree = ast.parse(source)
    start = next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='_startup_access_active' for t in n.targets))
    tree.body.insert(start,ast.Expr(value=ast.Call(func=ast.Name(id='_r2_load_selected',ctx=ast.Load()),
        args=[ast.Call(func=ast.Name(id='globals',ctx=ast.Load()),args=[],keywords=[])],keywords=[])))
    tree = ast.fix_missing_locations(CommercialImports().visit(tree))
    try:
        exec(compile(tree, str(app_path), 'exec'), namespace)
    except AcceptanceBlocked:
        ui.info('This stage requires saved or generated writing. Generation and writing are disabled for this read-only acceptance session; no content was created.')
    finally:
        # A legitimate empty-stage stop must not hide the Quill panel.
        if not rendered_quill:
            render_quill()
