"""Frozen commercial UI, private read-only acceptance only. Not for production.

No fixture, reconstructed project or generated writing is loaded. The original
314 commercial files stay byte-identical. Private adapters disable integrations
and permit navigation for inspection without saving approval milestones.
"""
import ast
import hashlib
from pathlib import Path
from staging_owner_interface import (
    APP_SHA256, AcceptanceBlocked, ReadAuth, ReadUI, InterfaceImports,
)


class CommercialUI(ReadUI):
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
        if node.name == 'wbs_request_stage_change':
            node.body = [ast.Return(value=ast.Call(
                func=ast.Name(id='_r2_navigate', ctx=ast.Load()),
                args=[ast.Name(id='destination', ctx=ast.Load()), ast.Name(id='export_view', ctx=ast.Load())], keywords=[]))]
        return super().visit_FunctionDef(node)


def run_interface(ui, auth, owner_email, app_path):
    source = Path(app_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != APP_SHA256:
        raise AcceptanceBlocked('Frozen commercial source mismatch.')
    owner = ReadAuth(auth, owner_email)
    owner.refresh_account()
    state = ui.session_state
    workspace = (owner.subject, APP_SHA256, 'native-commercial-ui-v1')
    if state.get('_r2_frozen_acceptance_workspace') != workspace:
        # Keep earlier inspection state in private session memory. Do not turn
        # its stage records into a new or reconstructed commercial project.
        kept = {'_wbs_auth_controller'}
        old = {k: state[k] for k in list(state)
               if k not in kept and not str(k).startswith(('_r2_', 'r2_'))}
        state['_r2_prior_inspection_workspace'] = old
        for key in old:
            state.pop(key, None)
        state['_r2_frozen_acceptance_workspace'] = workspace
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
        'extension_quill_renderer': render_quill,
        '_r2_blocked_bridge': lambda *args, **kwargs: BlockedBridge()}
    ui.caption('Frozen R2 commercial interface. Navigation is inspection-only; no Reflections workflow is reconstructed. Writing, approvals, saves, AI, audio generation and payments are disabled.')
    tree = ast.fix_missing_locations(CommercialImports().visit(ast.parse(source)))
    try:
        exec(compile(tree, str(app_path), 'exec'), namespace)
    except AcceptanceBlocked:
        ui.info('This stage requires saved or generated writing. Generation and writing are disabled for this read-only acceptance session; no content was created.')
    finally:
        # A legitimate empty-stage stop must not hide the Quill panel.
        if not rendered_quill:
            render_quill()
