"""Own compatibility route; no automatic rewriting or generation."""
from .editorial_review import render as _render

def render(context):
    return _render(context)
