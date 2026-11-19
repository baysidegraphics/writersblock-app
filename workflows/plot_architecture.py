"""Legacy import path; all implementations are format owned."""
from core.workflow_runtime import run_workflow

def render(context):
    return run_workflow('plot_architecture', context)
