from core.format_services import coach
from core.saved_scene_state import saved_snapshot_for_session
from .state import is_approved
from .validation import validate
from .exports import build_docx,build_text
from . import TEMPLATE

def render(context):
    st=context['st'];st.header('6. Life-Writing — Printable Final Output')
    from core.image_placement import controls,settings
    from core.publication_layout import anchors,render_preview
    controls(context,anchors(st.session_state))
    saved=saved_snapshot_for_session(st.session_state)
    if not is_approved(st.session_state):
        st.warning('Final output requires editorial acceptance of the exact saved revision.');return
    errors=validate(saved,for_export=True)
    if errors:
        for error in errors:st.warning(error)
        return
    if st.session_state.get('demo_mode'):
        st.info('Printable downloads require the full edition.');return
    render_preview(st,st.session_state)
    if settings(st.session_state)!=settings(saved):
        st.warning('Save the adjusted image layout before downloading.');return
    from core.image_pdf import download
    download(st,build_docx(saved),'biography_memoir','biography_image')
    st.download_button('Download Printable Book (.docx)',data=build_docx(saved),file_name='biography_memoir.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key='biography_memoir_docx')
    st.download_button('Download Accessible Text (.txt)',data=build_text(saved).encode('utf-8'),file_name='biography_memoir.txt',mime='text/plain',key='biography_memoir_txt')
    st.caption("Includes the timeline, source register, interview records and fact-checking appendix.")
    coach(context)
