"""Adapter registry. Exact IDs from template_registry; no silent fallback."""
from importlib import import_module
from template_registry import FORMAT_REGISTRY

def get_format(format_id):
    if format_id not in FORMAT_REGISTRY:
        raise KeyError(f"Unknown saved writing format: {format_id}")
    return import_module(f"formats.{format_id}")

def registered_format_ids():
    return tuple(FORMAT_REGISTRY)
