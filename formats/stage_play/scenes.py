import re
"""Format-owned saved-scene normalization, assembly and outline parsing."""


def completed_blocks(source):
    """Recorded completed scenes for this format; never a plot or preview."""
    if not isinstance(source, dict):
        return {}
    result = {}
    for key, value in source.items():
        try:
            number = int(key)
        except (TypeError, ValueError):
            continue
        if number > 0 and isinstance(value, str) and value.strip():
            result[number] = value
    return result


def outline_parts(outline):
    """Parse actual beat headings/titles and ONLY scene prose, not generator metadata."""
    source = str(outline or '')
    hits = list(re.finditer('(?im)^\\s*\\[BEAT\\s+(\\d+)\\]\\s*', source))
    result = {}
    for i, hit in enumerate(hits):
        n = int(hit.group(1))
        block = source[hit.end():hits[i + 1].start() if i + 1 < len(hits) else len(source)]
        title = re.search('(?is)\\[SCENE TITLE\\]\\s*:\\s*(.*?)(?=\\n\\s*\\[[A-Z][A-Z\\s&0-9]*\\]\\s*:|\\Z)', block)
        prose = re.search('(?is)\\[(?:SCENE DETAILS(?:\\s*&\\s*CONFLICT)?|SCENE\\s*\\d*)\\]\\s*:\\s*(.*?)(?=\\n\\s*\\[[A-Z][A-Z\\s&0-9]*\\]\\s*:|\\Z)', block)
        title_text = title.group(1).strip().strip('=') if title else f'Scene {n}'
        prose_text = prose.group(1).strip().strip('=') if prose else ''
        prose_text = re.split('(?im)^\\s*(?:CORE OBJECTIVE|STYLE\\s*&\\s*SYNTAX DIRECTIVE|THE CONFLICT)\\s*:', prose_text)[0].strip()
        result[n] = (title_text, prose_text, block)
    return result


def manuscript(source):
    blocks = completed_blocks(source)
    return "\n\n".join(blocks[n] for n in sorted(blocks))
