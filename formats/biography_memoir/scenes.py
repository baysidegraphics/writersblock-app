"""Own numbered chapter/unit parser. Never derives scenes from planning text."""
import re

def completed_blocks(source):
    result = {}
    if not isinstance(source, dict): return result
    for key, text in source.items():
        try: number = int(key)
        except (TypeError, ValueError): continue
        if number > 0 and isinstance(text, str) and text.strip(): result[number] = text
    return result

def manuscript(source):
    blocks = completed_blocks(source)
    return '\n\n'.join(blocks[n] for n in sorted(blocks))

def outline_parts(outline):
    result = {}
    for part in re.split(r'(?im)^\s*\[BEAT\s+', str(outline or ''))[1:]:
        match = re.match(r'(\d+)\]', part)
        if match: result[int(match.group(1))] = ('Unit ' + match.group(1), '', part)
    return result
