from core.format_services import coach

from core.saved_scene_state import saved_snapshot_for_session

from .state import is_approved

from .validation import validate

from .exports import build_docx,build_text

from . import TEMPLATE



def render(context):

    st=context['st'];st.header('6. Educational Activity Book — Printable Final Output')

    from core.children_publication import controls,illustration_controls,render_educational,settings
    controls(context,'final')
    units=((st.session_state.get('format_template_values') or {}).get('childrens_interactive_educational') or {}).get('units') or []
    if units:illustration_controls(context,'education-unit',[int(u['unit_number']) for u in units])
    saved=saved_snapshot_for_session(st.session_state)

    if not is_approved(st.session_state):

        st.warning('Final output requires editorial acceptance of the exact saved revision.');return

    errors=validate(saved,for_export=True)

    if errors:

        for error in errors:st.warning(error)

        return

    if st.session_state.get('demo_mode'):

        st.info('Printable downloads require the full edition.');return

    render_educational(st,st.session_state)
    if settings(st.session_state)!=settings(saved) or __import__('core.inline_images',fromlist=['data']).data(st.session_state)!=__import__('core.inline_images',fromlist=['data']).data(saved):
        st.warning('Save the adjusted layout before downloading.');return
    from core.image_pdf import download
    download(st,build_docx(saved),'childrens_educational','education_image')
    st.download_button('Download Printable Book (.docx)',data=build_docx(saved),file_name='childrens_interactive_educational.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key='childrens_interactive_educational_docx')

    st.download_button('Download Accessible Text (.txt)',data=build_text(saved).encode('utf-8'),file_name='childrens_interactive_educational.txt',mime='text/plain',key='childrens_interactive_educational_txt')

    st.caption("Digital interactive output is design-only. Clickable choices, learner tracking and a digital player are not implemented.")

    from .digital_output import interface_blueprint

    import json

    st.download_button('Download Digital Interface Blueprint (.json) — Design Only',data=json.dumps(interface_blueprint(saved),ensure_ascii=False,indent=2).encode('utf-8'),file_name='educational_digital_design.json',mime='application/json',key='edu_design_blueprint')

    coach(context)

