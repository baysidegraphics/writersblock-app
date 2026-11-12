from pathlib import Path
from functools import lru_cache
@lru_cache(maxsize=1)
def renderer():
    import streamlit as st
    root=Path(__file__).parent
    return st.components.v2.component('wbs_image_flow_editor',html='<button class="insert" type="button">[Insert Image]</button><div class="canvas" role="textbox" aria-label="Manuscript image editor" contenteditable="plaintext-only" spellcheck="true"></div>',css='\n.canvas{\ncontainer-type:inline-size;white-space:pre-wrap;display:flow-root;background:white;color:#111;border:1px solid #999;padding:16px;min-height:320px;font:16px/1.5 Georgia;}.canvas img{cursor:pointer}.insert{background:#b5121b;color:white;padding:8px;border:0;margin:6px 0;}',js=(root/'editor.js').read_text(encoding='utf8'),isolate_styles=False)

def render(st,text,markup,key,width):
    result=renderer()(key=key,data={'html':markup,'text':text,'width':width},default={'document':{'text':text,'placements':None},'cursor':0},on_document_change=lambda:None,on_cursor_change=lambda:None)
    return getattr(result,'document',{'text':text,'placements':None}),getattr(result,'cursor',0)
