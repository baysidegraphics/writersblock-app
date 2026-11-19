"""Native textarea editing with an integrated syntax-colour layer, no CDN."""
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def _renderer():
    import streamlit as st
    root=Path(__file__).parent
    return st.components.v2.component('wbs_author_page_turn_editor',
        html='<div class="wbs-page-editor"><pre aria-hidden="true" class="wbs-page-ink"></pre><textarea aria-label="Story editor with inline page turns" spellcheck="true"></textarea></div><div class="wbs-page-count" aria-live="polite"></div>',
        css=(root/'editor.css').read_text(encoding='utf8'),js=(root/'editor.js').read_text(encoding='utf8'),isolate_styles=False)


def render(st,source,key,working_key):
    def changed():
        value=st.session_state.get(key)
        text=getattr(value,'text',None)
        if isinstance(value,dict):text=value.get('text')
        if isinstance(text,str):st.session_state[working_key]=text
    current=st.session_state.get(working_key,source)
    result=_renderer()(key=key,data={'source':current},
        default={'text':current},on_text_change=changed)
    text=getattr(result,'text',None)
    return text if isinstance(text,str) else st.session_state.get(working_key,source)
