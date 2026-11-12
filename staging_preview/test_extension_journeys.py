"""Action-driven, offline extension journeys. No application startup or credentials."""
import ast
import copy
from io import BytesIO
import json
from types import SimpleNamespace
import unittest
import uuid
from core.extended_concept import SOURCE_OPTIONS, LAYOUT_STYLE
from core.extended_quill import ExtensionQuillBridge, ReadOnlyBackendAgent
from core.format_services import key, approval_signature
from core.workflow_runtime import run_workflow
from core.saved_scene_state import saved_snapshot_for_session
from test_new_formats import valid_environment, BIO, EDU
from offline_app import APP_TREE, ROOT, Halt

class Models:

    def __init__(self):
        self.calls = []
        self.fail = False

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError('Offline model failure')
        return SimpleNamespace(text='A proposal based only on the supplied author material.')

class Backend:

    def __init__(self):
        self.client = SimpleNamespace(models=Models())
        self.model_name = 'offline-model'
        self.reports = []

    def run_revision_pass(self, *args):
        self.reports.append(args)
        return 'Read-only publisher assessment of the exact saved manuscript.'

def install_services(context):
    """Load real app navigation/version/change-tracking definitions, never startup."""
    from wbs_format_guard import project_format_widget_key
    context['project_format_widget_key'] = project_format_widget_key
    context['uuid'] = uuid
    from types import ModuleType
    if not isinstance(context['st'], ModuleType):
        context['st'].sidebar = context['st']
    names = {'wbs_reached_review_level', 'wbs_request_stage_change', 'wbs_complete_stage_change', 'wbs_verify_navigation_project_identity', 'wbs_editorial_ready_for_assessment', 'wbs_stage4_final_access_ready', 'wbs_save_state_signature', 'wbs_work_has_changed', 'wbs_has_saved_master', 'get_active_format_widget_key', 'render_save_as_named_version_control', 'refresh_quill_template_context', 'get_active_format_development_context'}
    nodes = [node for node in APP_TREE.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in APP_TREE.body:
        if isinstance(node, ast.Assign) and any((isinstance(t, ast.Name) and t.id == 'WBS_WRITER_CHANGE_KEYS' for t in node.targets)):
            nodes.insert(0, node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'offline-real-navigation', 'exec'), context)

def action(context, stage, clicks=()):
    st = context['st']
    st.clicks = set(clicks)
    try:
        run_workflow(stage, context)
    except Halt:
        pass
    finally:
        st.clicks = set()

def sidebar_action(context, button):
    st = context['st']
    st.clicks = {button}
    start = next((i for i, n in enumerate(APP_TREE.body) if isinstance(n, ast.Assign) and any((isinstance(t, ast.Name) and t.id == '_wbs_stage5_ready' for t in n.targets))))
    end = next((i for i, n in enumerate(APP_TREE.body[start:], start) if isinstance(n, ast.If) and any((isinstance(c, ast.keyword) and c.arg == 'key' and isinstance(c.value, ast.Constant) and (c.value.value == 'nav_export') for c in ast.walk(n)))))
    nodes = APP_TREE.body[start:end + 1]
    try:
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'offline-sidebar', 'exec'), context)
    except Halt:
        pass
    finally:
        st.clicks = set()
