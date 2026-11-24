"""standard_manuscript: script polish. Existing engine and widget contracts retained."""

def render(context):
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    can_use_rewrite = context['can_use_rewrite']
    create_bridge_adapter = context['create_bridge_adapter']
    get_effective_format_type = context['get_effective_format_type']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_project_title_banner = context['render_project_title_banner']
    require_product_access = context['require_product_access']
    st = context['st']
    wbs_request_stage_change = context['wbs_request_stage_change']
    require_product_access('revision')
    st.header('🧠 Stage 4: Optional Script Polish')
    render_project_title_banner('step_6_script_polish')
    st.markdown('##### Review the manuscript for continuity, pacing, tone, and polish opportunities.')
    st.markdown('---')
    if not st.session_state.current_draft_output.strip():
        st.warning('No manuscript draft found. Return to Creative Draft and complete drafting first.')
    else:
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader('📄 Script Under Review')
            st.text_area('Current Manuscript:', value=st.session_state.current_draft_output, height=500, label_visibility='collapsed', disabled=True)
        with col_right:
            st.subheader('🔍 Polish Tools')
            revision_mode = st.selectbox('Choose Polish Pass:', ['Continuity Check', 'Pacing Check', 'Tone & Style Check', 'Character Consistency Check', 'Scene Expansion Suggestions', 'Final Polish Pass'])
            if st.button('Run Script Polish 🧠', key='run_revision_pass', type='primary', use_container_width=True):
                require_product_access('revision')
                with st.spinner('Running polish analysis...'):
                    if create_bridge_adapter is None:
                        st.error(f'WritersBlock Model is unavailable. {WBS_MODEL_IMPORT_ERROR}')
                        st.stop()
                    _wbs_polish_bridge = create_bridge_adapter(backend=st.session_state.backend)
                    _wbs_polish_result = _wbs_polish_bridge.execute('Run Script Polish', st.session_state, prepared_context={'effective_format_type': get_effective_format_type(), 'format_development_context': get_full_project_continuity_context(), 'quill_format_instructions': st.session_state.get('quill_format_instructions', ''), 'quill_template_context': refresh_quill_template_context()}, action_payload={'revision_mode': revision_mode, 'tone_style': st.session_state.tone_style, 'author_style': st.session_state.author_style})
                    if not _wbs_polish_result.success:
                        st.error('WritersBlock Model Bridge could not run Script Polish. ' + (_wbs_polish_result.error or 'Unknown bridge error.'))
                        st.stop()
                    revision_report = _wbs_polish_result.output
                    st.session_state.revision_report = revision_report
                    st.session_state['_wbs_agent_bridge_last_operation'] = _wbs_polish_result.backend_operation or ''
                    st.session_state['_wbs_agent_bridge_last_success'] = True
                    st.rerun()
            st.markdown('---')
            if 'revision_report' not in st.session_state:
                st.session_state.revision_report = ''
            st.text_area('Polish Report:', value=st.session_state.revision_report, height=300, label_visibility='collapsed', disabled=True)
            if can_use_rewrite:
                if st.button('Proceed to Script Rewrite 🛠️', key='proceed_to_rewrite_from_revision', type='primary', use_container_width=True):
                    wbs_request_stage_change('Rewrite Engine')
            else:
                st.button('🔒 Script Rewrite Locked', key='rewrite_locked_from_revision', disabled=True, use_container_width=True)
