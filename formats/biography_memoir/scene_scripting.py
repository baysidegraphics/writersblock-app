from core.format_services import data,key,save_scene,coach,advance
from core.domain_validation import number
from . import FORMAT_ID
from .scenes import completed_blocks

def render(context):
    st=context['st'];st.header('3. Chapter Writing — Biography / Autobiography / Memoir')
    chapters=data(st.session_state,FORMAT_ID).get('chapters') or []
    numbers=sorted({number(row.get('chapter_number')) for row in chapters if number(row.get('chapter_number'))})
    if not numbers:st.info('Create the chapter organization before writing chapters.');return
    selected=st.selectbox('Chapter',numbers,key=key(context,FORMAT_ID,'chapter_selected'))
    blocks=completed_blocks(st.session_state.get('scene_blocks') or {})
    from core.image_editor import edit as image_edit
    text=image_edit(context,selected,blocks.get(selected,st.session_state.get('current_draft_output','') if not blocks else ''),key(context,FORMAT_ID,'chapter_text_'+str(selected)),'Author Chapter Text',460)
    st.caption('Use source notes for factual assertions. Interview notes are not invented dialogue; quotations must retain the supplied wording.')
    if st.button('Save Chapter To Current Revision',key='bio_scene_save'):
        try:
            if save_scene(context,FORMAT_ID,selected,text) and set(numbers)<=set(completed_blocks(st.session_state.get('scene_blocks') or {})):
                advance(context,'Isolation Guardrail')
        except ValueError as exc:st.warning(str(exc))
    if st.button('Open Life-Writing Editorial Review',key='bio_to_review'):advance(context,'Isolation Guardrail')
    coach(context)
