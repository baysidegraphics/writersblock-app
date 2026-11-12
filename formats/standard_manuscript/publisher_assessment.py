from core.stage_navigation import after_approval
"""standard_manuscript: publisher assessment. Existing engine and widget contracts retained."""

def render(context):
    WBS_FORMAT_IDS = context['WBS_FORMAT_IDS']
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_project_title = context['get_project_title']
    get_wbs_format_display_name = context['get_wbs_format_display_name']
    st = context['st']
    supabase = context['supabase']
    wbs_editorial_ready_for_assessment = context['wbs_editorial_ready_for_assessment']
    from core.publisher_assessment import render_stage5
    _wbs_publisher_format = 'standard_manuscript'
    if _wbs_publisher_format not in WBS_FORMAT_IDS:
        st.error('Saved writing format is unavailable. Reload the original project.')
    elif not wbs_editorial_ready_for_assessment():
        st.warning('Complete and save Stage 4 Editorial Review and Integrity before opening Stage 5.')
    else:
        render_stage5(st, on_saved=lambda: after_approval(context,5), supabase=supabase, backend=st.session_state.get('backend'), project_id=get_active_project_id(), user_id=get_current_user_id(), title=get_project_title(), revision_id=st.session_state.get('_wbs_active_saved_session_row_id'), format_id=_wbs_publisher_format, format_name=get_wbs_format_display_name(_wbs_publisher_format))
    st.stop()
