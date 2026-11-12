from core.stage_navigation import after_approval
from core.publisher_assessment import render_stage5
from core.format_services import coach
from core.text import get_text_signature
from .state import is_approved
from . import FORMAT_ID,TEMPLATE

def render(context):
    st=context['st']
    if not is_approved(st.session_state):
        st.warning('Accept and save the current editorial revision before publisher assessment.');return
    state=st.session_state
    passport=(str(state.get('current_project_id') or ''),str(state.get('_wbs_active_saved_session_row_id') or ''),get_text_signature(state.get('current_draft_output') or ''))
    if state.get('_wbs_stage5_passport')!=passport:
        state['_wbs_stage5_passport']=passport
        st.rerun()
    render_stage5(st, on_saved=lambda: after_approval(context,5),supabase=context['supabase'],backend=state.get('backend'),project_id=state.get('current_project_id'),
        user_id=context['get_current_user_id'](),title=state.get('project_title') or '',revision_id=state.get('_wbs_active_saved_session_row_id'),
        format_id=FORMAT_ID,format_name=TEMPLATE['display_name'])
    coach(context)
