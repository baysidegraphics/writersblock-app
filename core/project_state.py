"""Authoritative legacy snapshot access and format-owned completion totals."""
from copy import deepcopy

def active_format_id(snapshot):
    fmt = str(snapshot.get("active_format_id") or "")
    from template_registry import FORMAT_REGISTRY
    if fmt not in FORMAT_REGISTRY:
        raise ValueError("Saved format ID missing or unknown; refusing fallback")
    return fmt

def saved_format_state(snapshot):
    fmt = active_format_id(snapshot)
    data = snapshot.get("format_template_values") or {}
    return deepcopy(data.get(fmt) or {})

def compose_format_state(snapshot, format_id, values):
    if format_id != active_format_id(snapshot):
        raise ValueError("Cannot write one format's data into another format")
    result = deepcopy(snapshot)
    existing = result.get("format_template_values") or {}
    result["format_template_values"] = {**existing, format_id: deepcopy(values)}
    return result


def completed_scene_blocks(snapshot):
    """Only explicitly recorded scenes contribute to completion totals.

    Preserve the Short Story four-scene contract and the Novel parser. Planning
    outlines, previews and concept text are never completed writing.
    """
    from core.registry import get_format
    return get_format(active_format_id(snapshot)).completed_scenes(snapshot)


def completed_report(snapshot):
    blocks = completed_scene_blocks(snapshot)
    return _completed_totals(active_format_id(snapshot), tuple(sorted(blocks.items())))


from functools import lru_cache


@lru_cache(maxsize=2048)
def _completed_totals(format_id, scenes):
    counts = _counted_scenes(format_id, scenes)
    return sum(words for _, words in counts), len(counts)


@lru_cache(maxsize=2048)
def _counted_scenes(format_id, scenes):
    from core.text import count_words
    return tuple((number, count_words(text)) for number, text in scenes)


def scene_word_counts(snapshot):
    blocks = completed_scene_blocks(snapshot)
    return dict(_counted_scenes(active_format_id(snapshot), tuple(sorted(blocks.items()))))
