"""Presentation-only starting storyline preview. No generation, saving or state writes."""

def starting_storyline_text(state):
    mode = str(state.get('version_source_mode') or state.get('starting_source_mode') or 'Custom Plot Line')
    if mode == 'Saved Manuscript':
        return str(state.get('saved_version_source_text') or '')
    if mode in {'Replacement Draft / Manuscript', 'Existing Draft / Manuscript'}:
        return str(state.get('imported_source_text') or '')
    return str(state.get('story_seed') or '')


def render_starting_storyline_preview(st):
    st.text_area('Starting Storyline — Concept / Quill:',
                 value=starting_storyline_text(st.session_state), height=220, disabled=True,
                 placeholder='Your concept storyline or requested Quill suggestion will appear here.')
