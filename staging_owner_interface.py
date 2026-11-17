"""Private acceptance adapter. Never install this file in production.

Executes the frozen commercial UI in a separate namespace, not by changing its
files or process-global SDK/module objects. Database access remains SELECT-only.
"""
import ast
import hashlib
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
        return ReadQuery(self._auth.owned_client().table(name))

    def __getattr__(self, name):
        return blocked


class ReadAuth:
    def __init__(self, auth, owner_email):
        self._auth, self._email = auth, owner_email

    def refresh_account(self):
        row = self._auth.refresh_account()
        if self._auth.email != self._email or str(row.get('id')) != str(self._auth.owner_id):
            raise AcceptanceBlocked('Owner binding unavailable.')
        return row

    def require_owner(self):
        self.refresh_account()
        return self._auth.require_owner()

    def owned_client(self, *args, **kwargs):
        return ReadDatabase(self._auth)

    @property
    def access_check(self):
        return self._auth.access_check

    @access_check.setter
    def access_check(self, check):
        self._auth.access_check = check

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
        return self.generic_visit(node)


def run_interface(ui, auth, owner_email, app_path):
    source = Path(app_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != APP_SHA256:
        raise AcceptanceBlocked('Commercial source hash mismatch; interface not opened.')
    owner = ReadAuth(auth, owner_email)
    owner.refresh_account()
    # Do not reuse an initialized provider left by any earlier staging session.
    ui.session_state['backend'] = None
    ui.session_state.pop('_wbs_quill_test_backend', None)
    def no_backend(state, *args, **kwargs):
        state['backend'] = None
        return None
    def quill(*args, **kwargs):
        ui.subheader('Quill — Your Frontline Editor-in-Chief')
        ui.caption('AI requests and voice generation are disabled during read-only acceptance.')
    namespace = {'__name__': '__main__', '__file__': str(Path(app_path).resolve()),
        '_r2_ui': ReadUI(ui), '_r2_controller': lambda *args, **kwargs: owner,
        '_r2_backend': no_backend, '_r2_noop': lambda *args, **kwargs: None,
        '_r2_quill': quill}
    tree = ast.fix_missing_locations(InterfaceImports().visit(ast.parse(source)))
    exec(compile(tree, str(app_path), 'exec'), namespace)
