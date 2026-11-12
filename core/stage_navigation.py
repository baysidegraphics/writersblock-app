"""Navigation only, after successful existing saves/approvals. No writing or AI."""

ACTIVE_NAV_STYLE='<style>[data-testid="stSidebar"] [class*="st-key-nav_"] button{background-color:#000000!important;border-color:#000000!important;color:white!important;opacity:1!important}[data-testid="stSidebar"] [class*="st-key-nav_"] button:disabled{color:#9ca3af!important}'+','.join('[data-testid="stSidebar"] .st-key-'+key+' button' for key in (
    'nav_intake_active','nav_sandbox_active','nav_plot_active','nav_guard_active',
    'nav_publisher_assessment_active','nav_export_active'))+'{background-color:#ff4b4b!important;border-color:#ff4b4b!important;color:white!important}</style>'

def after_approval(context, stage):
    st=context['st'];state=st.session_state
    if stage==4:
        from core.integrity_review import ready
        if not ready(state,required=context['project_integrity_review_applies']()):return False
        if not context['wbs_editorial_ready_for_assessment']():return False
        identity='_wbs_next_after_review_'+str(state.get('current_project_id'))+'_'+str(state.get('_wbs_active_saved_session_row_id'))+'_'+str(state.get('active_format_id'))
        if state.get(identity)=='Skip optional assessment — Final Manuscript':
            context['wbs_request_stage_change']('Isolation Guardrail',export_view=True)
        else:context['wbs_request_stage_change']('Publisher Assessment',export_view=False)
    else:
        target={1:'Sandbox',2:'Plot Architect',3:'Isolation Guardrail',5:'Isolation Guardrail'}[stage]
        context['wbs_request_stage_change'](target,export_view=stage==5)
    return True


def review_destination(context):
    state=context['st'].session_state
    identity='_wbs_next_after_review_'+str(state.get('current_project_id'))+'_'+str(state.get('_wbs_active_saved_session_row_id'))+'_'+str(state.get('active_format_id'))
    context['st'].radio('After editorial approval and save:',
        ['Optional Publisher Assessment','Skip optional assessment — Final Manuscript'],key=identity)
