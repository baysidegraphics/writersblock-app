from core.format_services import data,put_data,save_checkpoint,show_errors,approve,coach,key
from . import FORMAT_ID
from .validation import validate

def render(context):
    if context['st'].session_state.get('export_view',False):
        from .final_manuscript import render as render_final
        return render_final(context)
    st=context['st'];st.header('4. Educational, Accessibility and Adult Review')
    from core.integrity_review import panel
    integrity_ready=panel(context)
    from core.children_publication import render_educational
    try:render_educational(st,st.session_state)
    except ValueError as exc:st.warning(str(exc))
    values=data(st.session_state,FORMAT_ID)
    values['adult_review_complete']=st.checkbox('Adult review completed: vocabulary, inclusion, accessibility, instructions and material safety.',value=bool(values.get('adult_review_complete')),key=key(context,FORMAT_ID,'adult_review_complete'))
    if values.get('subject_area')=='Science & Discovery':
        values['science_accuracy_review']=st.checkbox('Science explanations checked against the recorded sources.',value=bool(values.get('science_accuracy_review')),key=key(context,FORMAT_ID,'science_accuracy_review'))
    put_data(st.session_state,FORMAT_ID,values)
    if st.button('Validate Learning Book And Printed Choices',key='edu_validate'):show_errors(context,validate(dict(st.session_state),for_export=True))
    if st.button('Save Educational Review Work',key='edu_review_save'):save_checkpoint(context,FORMAT_ID)
    accepted=st.checkbox('I approve this story, its learning activities, adult guide and printable exercises.',key=key(context,FORMAT_ID,'editorial_confirm'))
    if st.button('Accept And Save Educational Editorial Review',key='edu_accept',disabled=not (accepted and integrity_ready)):
        if approve(context,FORMAT_ID):
            from core.stage_navigation import after_approval
            after_approval(context,4)
    coach(context)
