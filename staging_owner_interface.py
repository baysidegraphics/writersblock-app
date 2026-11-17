"""Private acceptance adapter. Never install this file in production.

Executes the frozen commercial UI in a separate namespace, not by changing its
files or process-global SDK/module objects. Database access remains SELECT-only.
"""
import ast
import hashlib
import json
from pathlib import Path

APP_SHA256 = '3559ca04947c985688b0f3c8c7f7694e04ce4f31362773d2ea73fe3df0490614'


class AcceptanceBlocked(PermissionError):
    pass


def blocked(*args, **kwargs):
    raise AcceptanceBlocked('Disabled during read-only owner acceptance.')


class ReadQuery:
    METHODS = frozenset({'select', 'eq', 'neq', 'in_', 'is_', 'not_', 'or_',
        'order', 'range', 'limit', 'single', 'maybe_single', 'filter', 'ilike',
        'like', 'gt', 'gte', 'lt', 'lte', 'contains'})

    def __init__(self, query):
        self._query = query
        self._selected = False

    def __getattr__(self, name):
        if name not in self.METHODS:
            raise AcceptanceBlocked('Database operation disabled.')
        def chained(*args, **kwargs):
            if name == 'select':
                self._selected = True
            self._query = getattr(self._query, name)(*args, **kwargs)
            return self
        return chained

    def execute(self):
        if not self._selected:
            raise AcceptanceBlocked('SELECT required.')
        return self._query.execute()


class ReadDatabase:
    def __init__(self, auth):
        self._auth = auth

    def table(self, name):
        # Profiles come exclusively from the safe authenticated-account RPC;
        # never SELECT legacy verification tokens or access codes.
        if name not in {'writersblock_projects', 'writersblock_project_drafts',
                        'writersblock_manuscript_versions'}:
            raise AcceptanceBlocked('Table unavailable in acceptance.')
        from core.persistence import OwnedClient
        # Read-only acceptance is authorized by the verified owner mapping, not
        # by a purchased writing entitlement. The commercial write client and
        # its entitlement callback are never reused or changed here.
        boundary = OwnedClient(self._auth._auth._client,
            lambda: self._auth.owner_id, authorize=self._auth.require_owner)
        return ReadQuery(boundary.table(name))

    def __getattr__(self, name):
        return blocked


class ReadAuth:
    def __init__(self, auth, owner_email):
        self._auth, self._email = auth, owner_email
        self._access_check = None

    def refresh_account(self):
        row = self._auth.refresh_account()
        if self._auth.email != self._email or str(row.get('id')) != str(self._auth.owner_id):
            raise AcceptanceBlocked('Owner binding unavailable.')
        return row

    def require_owner(self):
        self.refresh_account()
        return self._auth.owner_id

    def owned_client(self, *args, **kwargs):
        return ReadDatabase(self)

    @property
    def access_check(self):
        return self._access_check

    @access_check.setter
    def access_check(self, check):
        self._access_check = check

    def __getattr__(self, name):
        if name in {'subject', 'email', 'owner_id', 'account', 'verify'}:
            return getattr(self._auth, name)
        return blocked


class ReadUI:
    """Disable action controls while retaining session-only browsing widgets."""
    NAVIGATION = {'sidebar_load_saved_item', 'nav_intake', 'nav_sandbox',
                  'nav_plot', 'nav_guard', 'nav_publisher_assessment', 'nav_export'}

    def __init__(self, ui):
        self._ui = ui

    def __enter__(self):
        self._ui.__enter__()
        return self

    def __exit__(self, *args):
        return self._ui.__exit__(*args)

    def __getattr__(self, name):
        if name == 'sidebar':
            return ReadUI(self._ui.sidebar)
        if name in {'container', 'expander', 'form', 'popover', 'empty', 'tabs', 'columns'}:
            def containers(*args, **kwargs):
                result = getattr(self._ui, name)(*args, **kwargs)
                return [ReadUI(item) for item in result] if isinstance(result, list) else ReadUI(result)
            return containers
        if name in {'button', 'form_submit_button', 'download_button', 'file_uploader',
                    'link_button', 'page_link', 'chat_input'}:
            def action(*args, **kwargs):
                key = kwargs.get('key')
                if name == 'button' and key in self.NAVIGATION:
                    kwargs.pop('on_click', None)
                    return self._ui.button(*args, **kwargs)
                # Do not evaluate a callback or create a working outbound link.
                label = str(args[0]) if args else str(kwargs.get('label', 'Action'))
                if name == 'form_submit_button':
                    return self._ui.form_submit_button(label + ' — disabled for acceptance', disabled=True)
                self._ui.button(label + ' — disabled for acceptance', disabled=True,
                                key=('r2_disabled_' + str(key)) if key else None)
                return None if name in {'file_uploader', 'chat_input'} else False
            return action
        if name in {'text_input', 'text_area', 'number_input', 'slider', 'checkbox',
                    'toggle', 'data_editor', 'date_input', 'time_input', 'color_picker'}:
            def readonly(*args, **kwargs):
                kwargs['disabled'] = True
                kwargs.pop('on_change', None)
                return getattr(self._ui, name)(*args, **kwargs)
            return readonly
        if name in {'selectbox', 'radio', 'multiselect', 'select_slider'}:
            def selection(*args, **kwargs):
                # These selections may change only this private browser's state.
                kwargs.pop('on_change', None)
                return getattr(self._ui, name)(*args, **kwargs)
            return selection
        if name in {'markdown', 'html', 'write'}:
            def display(*args, **kwargs):
                import re
                values = tuple(re.sub(r'https?://[^\s<>\"\)]+', '#', value)
                               if isinstance(value, str) else value for value in args)
                return getattr(self._ui, name)(*values, **kwargs)
            return display
        if name in {'set_page_config', 'balloons', 'snow'}:
            return lambda *args, **kwargs: None
        return getattr(self._ui, name)


class InterfaceImports(ast.NodeTransformer):
    """Replace only integration imports in this private execution namespace."""
    REPLACEMENTS = {
        'core.authentication': {'session_controller': '_r2_controller'},
        'core.auth_ui': {'sync_access_state': '_r2_sync', 'render_auth_access': '_r2_noop'},
        'core.runtime_startup': {'customer_backend': '_r2_backend', 'load_local_environment': '_r2_noop'},
        'quill': {'render_quill_for_current_stage': '_r2_quill'},
        'wbs_streamlit_adapter': {'create_bridge_adapter': '_r2_noop'},
    }

    def visit_Import(self, node):
        if any(alias.name == 'streamlit' for alias in node.names):
            return ast.copy_location(ast.Assign(
                targets=[ast.Name(id='st', ctx=ast.Store())],
                value=ast.Name(id='_r2_ui', ctx=ast.Load())), node)
        return node

    def visit_ImportFrom(self, node):
        replacements = self.REPLACEMENTS.get(node.module, {})
        kept, assignments = [], []
        for alias in node.names:
            if alias.name in replacements:
                assignments.append(ast.copy_location(ast.Assign(
                    targets=[ast.Name(id=alias.asname or alias.name, ctx=ast.Store())],
                    value=ast.Name(id=replacements[alias.name], ctx=ast.Load())), node))
            else:
                kept.append(alias)
        return ([ast.copy_location(ast.ImportFrom(module=node.module, names=kept, level=node.level), node)]
                if kept else []) + assignments

    def visit_FunctionDef(self, node):
        if node.name == 'track_affitor_lead':
            node.body = [ast.Return(value=ast.Constant(False))]
        if node.name in {'access_allows', 'require_product_access', 'enforce_evaluation_session'}:
            node.body = [ast.Return(value=ast.Call(func=ast.Name(id='_r2_verify_read', ctx=ast.Load()), args=[], keywords=[]))]
        return self.generic_visit(node)


def workflow_records(drafts, project_id):
    """Find actual saved snapshots by content, not only a newer draft_type label.

    Never convert plain manuscripts or per-scene saves into invented sessions.
    Validation runs on a copy; the original row/content/ID/version is retained.
    """
    from copy import deepcopy
    from wbs_format_guard import prepare_saved_snapshot, SavedFormatError
    result = []
    for row in drafts:
        try:
            value = row.get('draft_content')
            payload = json.loads(value) if isinstance(value, str) else deepcopy(value)
            if not isinstance(payload, dict):
                continue
            if not any(key in payload for key in ('story_seed', 'plot_outline', 'scene_blocks',
                                                  'current_draft_output', 'format_template_values')):
                continue
            prepare_saved_snapshot(deepcopy(payload), project_id)
            result.append(row)
        except (ValueError, TypeError, SavedFormatError):
            continue
    return result


def saved_record_label(item, number):
    table, row, content_key = item
    kind = row.get('draft_type') if content_key == 'draft_content' else row.get('source_stage')
    title = row.get('draft_title') or row.get('version_label') or 'Saved record'
    return (str(number + 1) + '. ' + str(title) + ' — ' + str(kind or 'Unclassified')
            + ' · stored version_number: ' + str(row.get('version_number', '')))


def show_saved_records(ui, project_id, drafts, manuscripts, stage_index, project):
    """Expose exact stored evidence without reconstructing missing stages."""
    records = [('writersblock_project_drafts', row, 'draft_content') for row in drafts]
    records += [('writersblock_manuscript_versions', row, 'manuscript_content') for row in manuscripts]
    snapshots = workflow_records(drafts, project_id)
    with ui.expander('Saved record inventory', expanded=not bool(snapshots)):
        ui.caption('Read-only queries use the linked owner and selected project ID. Same-titled projects stay separate. No records are reassigned or regenerated.')
        ui.text('writersblock_project_drafts: ' + str(len(drafts)))
        ui.text('writersblock_manuscript_versions: ' + str(len(manuscripts)))
        ui.text('Recognized saved workflow snapshots: ' + str(len(snapshots)))
        ui.text('Stored project stage: ' + str(project.get('current_stage') or 'Not recorded'))
        ui.text('External storage reference recorded: ' + ('Yes' if project.get('storage_path') else 'No'))
        ui.caption('External storage is not opened. Only existing database records are inspected.')
        counts = {}
        for table, row, key in records:
            kind = str((row.get('draft_type') if key == 'draft_content' else row.get('source_stage')) or '')
            label = table + ' / ' + (kind or 'Unclassified')
            counts[label] = counts.get(label, 0) + 1
        for label, count in sorted(counts.items()):
            ui.text(label + ': ' + str(count))
        if records:
            selected = ui.selectbox('Inspect any original saved record', range(len(records)),
                format_func=lambda n: saved_record_label(records[n], n), key='_r2_record_' + project_id)
            table, row, key = records[selected]
            ui.caption('Original content from ' + table + '.' + key + '. Stored record numbers are not changed or deduplicated.')
            value = row.get(key)
            ui.text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) if value is not None else '')
    kinds = [
        {'concept', 'concept_development', 'intake', 'premise'},
        {'sandbox', 'plot_architecture', 'plot_outline', 'plot_architect', 'plot'},
        {'scene_draft', 'scene_scripting', 'drafting', 'drafting_engine', 'audiobook_production_script'},
        {'script_lock_draft', 'script_lock_revision', 'script_rewrite_draft',
         'script_rewrite_manual_edit', 'rewrite_engine', 'editorial_review', 'integrity_review'},
        {'publisher_assessment', 'publisher_review'},
        {'final_output', 'final_output_conversion', 'existing_manuscript_import'},
    ][stage_index]
    matches = [item for item in records if str((item[1].get('draft_type') if item[2] == 'draft_content'
                                               else item[1].get('source_stage')) or '').lower() in kinds]
    return matches


def run_interface(ui, auth, owner_email, app_path):
    source = Path(app_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != APP_SHA256:
        raise AcceptanceBlocked('Commercial source hash mismatch; interface not opened.')
    owner = ReadAuth(auth, owner_email)
    owner.refresh_account()
    database = ReadDatabase(owner)
    def read_rows(table, **filters):
        result = []
        for start in range(0, 10000, 200):
            query = database.table(table).select('*')
            for name, value in filters.items():
                query = query.eq(name, str(value))
            page = query.order('id').range(start, start + 199).execute().data or []
            result.extend(page)
            if len(page) < 200:
                return result
        raise AcceptanceBlocked('Listing limit reached; partial access not presented.')
    projects = read_rows('writersblock_projects')
    if not projects:
        ui.info('No projects belong to this verified linked owner. No other account was substituted.')
        return
    with ui.sidebar:
        ui.success('Verified linked owner — read-only acceptance')
        project_id = ui.selectbox('Existing project', [str(p['id']) for p in projects],
            format_func=lambda value: next(str(p.get('project_title') or 'Untitled project') + ' · Project ' + str(i + 1)
                                          for i, p in enumerate(projects) if str(p['id']) == value),
            key='_r2_inspect_project')
        # Legacy WBS saves stage drafts separately and stores manuscript versions
        # in another table. A project_session-only filter hides these records.
        drafts = read_rows('writersblock_project_drafts', project_id=project_id)
        manuscripts = read_rows('writersblock_manuscript_versions', project_id=project_id)
        revisions = workflow_records(drafts, project_id)
        revision_ids = [str(row['id']) for row in revisions]
        if ui.session_state.get('_r2_inspect_revision') not in revision_ids:
            ui.session_state.pop('_r2_inspect_revision', None)
        row_id = None
        if revisions:
            row_id = ui.selectbox('Existing saved revision', revision_ids,
                format_func=lambda value: next('V' + str(row.get('version_number', '')) + ' — ' + str(row.get('draft_title') or 'Saved revision') + ' · ' + str(i + 1)
                    for i, row in enumerate(revisions) if str(row['id']) == value), key='_r2_inspect_revision')
        stages = ['1. Concept Development', '2. Plot Architecture', '3. Scene Scripting',
                  '4. Editorial Review', '5. Publisher Assessment', '6. Final Manuscript']
        stage = ui.selectbox('Read-only stage inspection', stages, key='_r2_inspect_stage')
        ui.caption('Inspection does not approve stages, activate a license or save changes. Unapproved outputs may show their existing approval warning.')
    stage_index = stages.index(stage)
    stage_records = show_saved_records(ui, project_id, drafts, manuscripts, stage_index,
                                      next(p for p in projects if str(p['id']) == project_id))
    if not revisions:
        ui.warning('No complete workflow snapshot was found among this project’s saved drafts. Existing stage records and manuscripts are still accessible; missing workflow fields will not be invented.')
        ui.header(stage)
        if stage_records:
            for item in stage_records:
                ui.subheader(saved_record_label(item, drafts.index(item[1]) if item[2] == 'draft_content' else manuscripts.index(item[1])))
                value = item[1].get(item[2])
                ui.text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) if value is not None else '')
        else:
            ui.info('No separately saved record is labelled for this stage. Inspect any original saved record in the inventory above; this does not mean manuscript text was deleted.')
        return
    selected = next(row for row in revisions if str(row['id']) == row_id)
    saved = json.loads(selected.get('draft_content') or '{}')
    if not isinstance(saved, dict) or str(saved.get('current_project_id') or project_id) != project_id:
        raise AcceptanceBlocked('Saved project identity mismatch.')
    # Do not reuse an initialized provider left by any earlier staging session.
    ui.session_state['backend'] = None
    ui.session_state.pop('_wbs_quill_test_backend', None)
    def no_backend(state, *args, **kwargs):
        state['backend'] = None
        return None
    def quill(*args, **kwargs):
        ui.subheader('Quill — Your Frontline Editor-in-Chief')
        ui.caption('AI requests and voice generation are disabled during read-only acceptance.')
    def sync_read_account(state, *args):
        owner.refresh_account()
        # These are real commercial entitlement flags, never fabricated for
        # acceptance. Owner inspection has a separate SELECT-only authorization.
        state['licensed_mode'] = False
        state['demo_mode'] = False
        return True
    def verify_read():
        owner.require_owner()
        return True
    namespace = {'__name__': '__main__', '__file__': str(Path(app_path).resolve()),
        '_r2_ui': ReadUI(ui), '_r2_controller': lambda *args, **kwargs: owner,
        '_r2_backend': no_backend, '_r2_noop': lambda *args, **kwargs: None,
        '_r2_quill': quill, '_r2_sync': sync_read_account, '_r2_verify_read': verify_read,
        '_active_version_number': selected.get('version_number')}
    tree = ast.parse(source)
    # Suppress the commercial account/license/sidebar interaction block. Keep
    # its definitions and constants; the private selectors above replace its UI.
    start = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == '_startup_access_active' for t in n.targets))
    filtered = []
    for node in tree.body:
        dispatch = isinstance(node, ast.If) and any(
            isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
            and child.func.id == 'run_workflow' for child in ast.walk(node))
        if dispatch or (node.lineno >= start and isinstance(node, (ast.If, ast.With, ast.Expr))):
            continue
        filtered.append(node)
    tree.body = filtered
    tree = ast.fix_missing_locations(InterfaceImports().visit(tree))
    exec(compile(tree, str(app_path), 'exec'), namespace)
    state = ui.session_state
    identity = (owner.subject, project_id, row_id,
                hashlib.sha256(str(selected.get('draft_content') or '').encode()).hexdigest())
    if (state.get('_r2_inspection_loaded') != identity
            or str(state.get('current_project_id') or '') != project_id
            or str(state.get('_wbs_active_saved_session_row_id') or '') != row_id):
        if not namespace['load_saved_project_session_to_state'](selected):
            raise AcceptanceBlocked('The exact saved workflow snapshot could not be restored.')
        state['_r2_inspection_loaded'] = identity
    # This changes only the private viewing route, never saved progress,
    # approval records, revision identity or manuscript contents.
    index = stages.index(stage)
    state['project_stage'] = ['Intake', 'Sandbox', 'Plot Architect',
                              'Isolation Guardrail', 'Publisher Assessment', 'Isolation Guardrail'][index]
    state['export_view'] = index == 5
    from core.workflow_runtime import run_workflow
    run_workflow(['concept_development', 'plot_architecture', 'scene_scripting',
                  'editorial_review', 'publisher_assessment', 'final_manuscript'][index], namespace)
