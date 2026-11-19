"""Own compatibility route; no automatic rewriting or generation."""
from .scene_scripting import render as _render

def render(context):
    return _render(context)
