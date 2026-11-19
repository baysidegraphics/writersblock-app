"""Independent childrens_interactive_educational writing workspace."""
from templates.template_childrens_interactive_educational import TEMPLATE
from format_quill.quill_childrens_interactive_educational import QUILL_INSTRUCTIONS
FORMAT_ID = 'childrens_interactive_educational'

def get_template(): return TEMPLATE

def get_quill_instructions(): return QUILL_INSTRUCTIONS

def run_workflow(name, namespace):
    from core.workflow_runtime import execute_format_workflow
    return execute_format_workflow(FORMAT_ID, name, namespace)

def completed_scenes(snapshot):
    from .state import get_data
    from .scenes import completed_blocks
    get_data(snapshot)
    return completed_blocks(snapshot.get('scene_blocks') or {})

def validate_snapshot(snapshot, for_export=False):
    from .validation import validate
    return validate(snapshot, for_export=for_export)
