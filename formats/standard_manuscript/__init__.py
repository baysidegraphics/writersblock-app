"""Isolated standard_manuscript format identity, using the existing WBS template and Quill."""
from templates.template_standard_manuscript import TEMPLATE
from format_quill.quill_standard_manuscript import QUILL_INSTRUCTIONS
FORMAT_ID = "standard_manuscript"
def get_template():
    return TEMPLATE
def get_quill_instructions():
    return QUILL_INSTRUCTIONS


def run_workflow(name, namespace):
    """Execute this format's own stage function with an isolated context."""
    from core.workflow_runtime import execute_format_workflow
    return execute_format_workflow(FORMAT_ID, name, namespace)


def completed_scenes(snapshot):
    from .scenes import completed_blocks
    if snapshot.get("active_format_id") != FORMAT_ID:
        raise ValueError("Cross-format scene access refused")
    return completed_blocks(snapshot.get("scene_blocks") or {})
