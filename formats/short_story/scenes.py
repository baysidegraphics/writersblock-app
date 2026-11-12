"""Verbatim extracted WBS pure functions; no story text regeneration."""
import re
import hashlib
import json

def wbs_ss_blocks(source):
    """Return the exact saved scene prose with numeric scene keys, without inventing boundaries."""
    if not isinstance(source, dict):
        return {}
    result = {}
    for key, value in source.items():
        try:
            index = int(key)
        except (ValueError, TypeError):
            continue
        if 1 <= index <= 4 and isinstance(value, str) and value.strip():
            result[index] = value
    return result


def wbs_ss_storyline(source):
    """Produce manuscript from only explicitly created scenes in scene order."""
    blocks = wbs_ss_blocks(source)
    return "\n\n".join(blocks[n] for n in sorted(blocks))


def wbs_ss_outline_parts(outline):
    """Parse actual beat headings/titles and ONLY scene prose, not generator metadata."""
    source = str(outline or "")
    hits = list(re.finditer(r"(?im)^\s*\[BEAT\s+(\d+)\]\s*", source))
    result = {}
    for i, hit in enumerate(hits):
        n = int(hit.group(1))
        if n not in range(1, 5):
            continue
        block = source[hit.end():hits[i+1].start() if i+1 < len(hits) else len(source)]
        title = re.search(r"(?is)\[SCENE TITLE\]\s*:\s*(.*?)(?=\n\s*\[[A-Z][A-Z\s&0-9]*\]\s*:|\Z)", block)
        prose = re.search(r"(?is)\[(?:SCENE DETAILS(?:\s*&\s*CONFLICT)?|SCENE\s*\d*)\]\s*:\s*(.*?)(?=\n\s*\[[A-Z][A-Z\s&0-9]*\]\s*:|\Z)", block)
        title_text = title.group(1).strip().strip("=") if title else f"Scene {n}"
        prose_text = prose.group(1).strip().strip("=") if prose else ""
        # Never display planning directives hidden in a prose field.
        prose_text = re.split(r"(?im)^\s*(?:CORE OBJECTIVE|STYLE\s*&\s*SYNTAX DIRECTIVE|THE CONFLICT)\s*:", prose_text)[0].strip()
        result[n] = (title_text, prose_text, block)
    return result




def completed_blocks(source):
    """Recorded completed scenes for this format; never a plot or preview."""
    return wbs_ss_blocks(source)


def outline_parts(outline):
    return wbs_ss_outline_parts(outline)


def manuscript(source):
    blocks = completed_blocks(source)
    return "\n\n".join(blocks[n] for n in sorted(blocks))
