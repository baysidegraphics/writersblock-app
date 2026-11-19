from core.format_services import data,key,edit_table,save_scene,coach,advance
from core.domain_validation import number
from . import FORMAT_ID
from .scenes import completed_blocks
from .validation import AGE_GUIDANCE

def render(context):
    st=context['st'];st.header('3. Educational Story, Questions and Printable Exercises')
    values=data(st.session_state,FORMAT_ID)
    st.caption(AGE_GUIDANCE.get(values.get('age_band'),{}).get('guidance','Choose ages 3–9 in Learning Setup.'))
    numbers=sorted({number(row.get('unit_number')) for row in values.get('units') or [] if number(row.get('unit_number'))})
    if not numbers:st.info('Organize learning units before writing the story.');return
    selected=st.selectbox('Learning Unit',numbers,key=key(context,FORMAT_ID,'unit_selected'))
    blocks=completed_blocks(st.session_state.get('scene_blocks') or {})
    from core.image_editor import edit as image_edit
    text=image_edit(context,selected,blocks.get(selected,st.session_state.get('current_draft_output','') if not blocks else ''),key(context,FORMAT_ID,'unit_text_'+str(selected)),'Author Story Text',360)
    edit_table(context,FORMAT_ID,'questions','Questions and Adult Answer Guidance',('question_id','unit_number','prompt','answer_or_guidance'))
    edit_table(context,FORMAT_ID,'activities','Printable Activities and Exercises',('activity_id','unit_number','title','instructions','materials','adult_steps','answer_or_observation','safety_notes','exercise_type'))
    if st.button('Save Story Unit And Activities',key='edu_scene_save'):
        try:
            if save_scene(context,FORMAT_ID,selected,text) and set(numbers)<=set(completed_blocks(st.session_state.get('scene_blocks') or {})):
                advance(context,'Isolation Guardrail')
        except ValueError as exc:st.warning(str(exc))
    if st.button('Open Educational Editorial Review',key='edu_to_review'):advance(context,'Isolation Guardrail')
    coach(context)
