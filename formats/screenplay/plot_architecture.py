"""screenplay: plot architecture. Existing engine and widget contracts retained."""

def render(context):
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_next_project_session_internal_version = context['get_next_project_session_internal_version']
    json = context['json']
    render_project_title_banner = context['render_project_title_banner']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    set_loaded_concept_version_baseline = context['set_loaded_concept_version_baseline']
    st = context['st']
    supabase = context['supabase']
    wbs_request_stage_change = context['wbs_request_stage_change']
    wbs_save_state_signature = context['wbs_save_state_signature']
    wbs_stage2_render_regenerate_novel_plots = context['wbs_stage2_render_regenerate_novel_plots']
    st.header('🗺️ Step 2: Plot Architecture')
    render_project_title_banner('step_2_scripting')
    st.markdown('##### Shape the first working script paths from your concept.')
    st.caption(f'Dialogue Style: {get_dialogue_style_display()} — inherited from Concept Development. Project type controls dialogue formatting.')
    st.markdown('---')
    if st.session_state.get('project_saved_notice'):
        st.session_state.project_saved_notice = False
    _wbs_novel_plot_mode = False
    wbs_stage2_render_regenerate_novel_plots()
    sandbox_slates = st.session_state.get('sandbox_slates', {})
    _wbs_plot_display_identity = (str(get_active_project_id() or ''), str(st.session_state.get('_wbs_active_saved_session_row_id') or ''), 'screenplay', '')
    _wbs_saved_novel_paths = False
    _wbs_saved_novel_choice = False
    _wbs_show_novel_plots = st.session_state.get('_wbs_stage2_novel_visible') == _wbs_plot_display_identity or _wbs_saved_novel_paths
    if not sandbox_slates:
        st.warning('No story paths are available yet. Return to Concept Development and generate story paths first.')
    else:
        if sandbox_slates.get('is_fallback', False):
            st.warning('AI connection issue detected. Temporary local story paths are being shown.')
        _wbs_stage2_options = (('Option A', 'Classic Structure', 'A clear, traditional story path.'), ('Option B', 'Twisted Perspective', 'A stranger version with a hidden truth or reversal.'), ('Option C', 'High-Impact Version', 'A faster, more intense story path.'))
        _wbs_choice = str(st.session_state.get('chosen_option') or '').split(':', 1)[0].strip()
        _wbs_text = str(st.session_state.get('chosen_option_text') or '')
        _wbs_valid = _wbs_choice in ('Option A', 'Option B', 'Option C') and bool(_wbs_text.strip()) and (_wbs_text == str(sandbox_slates.get(_wbs_choice) or '') or False)
        _wbs_review = bool(_wbs_valid and st.session_state.get('_wbs_active_saved_session_row_id') and (not st.session_state.get('_wbs_stage2_choose_new')))
        if _wbs_review:
            st.success(f'Saved selection: {_wbs_choice}')
            st.markdown(f'### {_wbs_choice}')
            st.info(_wbs_text)
            _wbs_next, _wbs_new = st.columns(2, gap='small')
            with _wbs_next:
                if st.button('Continue to Stage 3', key='wbs_stage2_saved_continue', type='primary', use_container_width=True):
                    wbs_request_stage_change('Plot Architect')
            with _wbs_new:
                if st.button('Select a New Plot', key='wbs_stage2_choose_new', use_container_width=True):
                    st.session_state['_wbs_stage2_choose_new'] = True
                    st.session_state.pop('_wbs_stage2_pending_path', None)
                    st.rerun()
        else:
            if st.session_state.get('_wbs_active_saved_session_row_id') and (not _wbs_valid) and (not st.session_state.get('_wbs_stage2_regen_unsaved')):
                st.warning('Original selection was not saved in this revision. All three paths are shown; no original choice is assumed.')
            if st.session_state.get('_wbs_stage2_choose_new'):
                st.info('Choose a plot. Nothing changes in the database until you click Save Current Version or Save Version As.')
            _wbs_cols = st.columns(3)
            for _wbs_i, (_wbs_col, (_wbs_opt, _wbs_name, _wbs_subtitle)) in enumerate(zip(_wbs_cols, _wbs_stage2_options), 1):
                with _wbs_col:
                    st.subheader(f'{_wbs_opt}: {_wbs_name}')
                    st.markdown(f'*{_wbs_subtitle}*')
                    st.info(sandbox_slates.get(_wbs_opt, ''))
                    if st.button(f'Select Path {_wbs_opt[-1]}', key=f'wbs_stage2_select_{_wbs_opt[-1]}', type='primary' if st.session_state.get('_wbs_stage2_pending_path') == _wbs_opt else 'secondary', use_container_width=True):
                        st.session_state['_wbs_stage2_pending_path'] = _wbs_opt
                        st.rerun()
            _wbs_pending = st.session_state.get('_wbs_stage2_pending_path')
            st.markdown('---')
            _wbs_row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
            _wbs_current_revision = str(context.get('_active_version_number') or st.session_state.get('current_version_number') or '').replace('V-', '')
            if not _wbs_current_revision.isdigit() and _wbs_row_id:
                try:
                    _wbs_rev_rows = supabase.table('writersblock_project_drafts').select('version_number').eq('id', _wbs_row_id).eq('project_id', get_active_project_id()).eq('user_id', get_current_user_id()).eq('draft_type', 'project_session').limit(1).execute().data or []
                    _wbs_current_revision = str(_wbs_rev_rows[0]['version_number']) if len(_wbs_rev_rows) == 1 else ''
                except Exception:
                    _wbs_current_revision = ''
            _wbs_next_rev = get_next_project_session_internal_version(get_active_project_id()) if get_active_project_id() else 1
            _wbs_saved_path = ''
            _wbs_saved_path_check_ok = not bool(_wbs_row_id)
            if _wbs_row_id:
                try:
                    _wbs_guard_rows = supabase.table('writersblock_project_drafts').select('draft_content').eq('id', _wbs_row_id).eq('project_id', get_active_project_id()).eq('user_id', get_current_user_id()).eq('draft_type', 'project_session').limit(1).execute().data or []
                    if len(_wbs_guard_rows) == 1:
                        _wbs_guard_snapshot = json.loads(_wbs_guard_rows[0].get('draft_content') or '{}')
                        if isinstance(_wbs_guard_snapshot, dict):
                            _wbs_saved_path = str(_wbs_guard_snapshot.get('chosen_option') or '').split(':', 1)[0].strip()
                            _wbs_saved_path_check_ok = True
                except Exception:
                    pass
            _wbs_is_plot_change = bool(_wbs_saved_path in ('Option A', 'Option B', 'Option C'))
            if _wbs_pending and _wbs_is_plot_change and (_wbs_pending != _wbs_saved_path):
                st.info(f'This revision currently has {_wbs_saved_path}. Save Current Version replaces its selected path only when you click Save; Save Version As creates a separate revision only when requested.')
            elif _wbs_pending and (not _wbs_saved_path_check_ok):
                st.warning('Saved revision could not be verified. Saving to the current revision is disabled.')
            if _wbs_pending:
                st.markdown('<div style="text-align:center;color:#ffffff;font-weight:700;margin:10px 0 12px 0">Save To Revision</div>', unsafe_allow_html=True)
            _wbs_left, _wbs_right = st.columns(2, gap='small')
            with _wbs_left:
                _wbs_save_current = st.button(f'Save Current Version (V-{_wbs_current_revision})' if _wbs_current_revision else 'Save Current Version', key='wbs_stage2_save_current', type='primary' if _wbs_pending else 'secondary', disabled=not bool(_wbs_pending and _wbs_row_id and _wbs_current_revision and _wbs_saved_path_check_ok), use_container_width=True)
            with _wbs_right:
                _wbs_save_new = st.button(f'Save Version As (V-{_wbs_next_rev})', key='wbs_stage2_save_new', type='primary' if _wbs_pending else 'secondary', disabled=not bool(_wbs_pending), use_container_width=True)
            if _wbs_save_current or _wbs_save_new:
                _wbs_selected_text = str(sandbox_slates.get(_wbs_pending) or '')
                if not _wbs_selected_text.strip():
                    st.error('Selected path has no text; nothing was saved.')
                    st.stop()
                _wbs_title = next((f'{key}: {name}' for key, name, _ in _wbs_stage2_options if key == _wbs_pending))
                if _wbs_save_current:
                    try:
                        _wbs_saved_rows = supabase.table('writersblock_project_drafts').select('id, version_number, draft_content').eq('id', _wbs_row_id).eq('project_id', get_active_project_id()).eq('user_id', get_current_user_id()).eq('draft_type', 'project_session').limit(1).execute().data or []
                        if len(_wbs_saved_rows) != 1:
                            raise ValueError('The exact revision was not found')
                        _wbs_original = json.loads(_wbs_saved_rows[0]['draft_content'] or '{}')
                        if not isinstance(_wbs_original, dict):
                            raise ValueError('Invalid saved revision')
                        if str(_wbs_original.get('active_format_id') or '') != 'screenplay':
                            raise ValueError('Saved writing format differs from active format')
                        if str(_wbs_original.get('story_seed') or '').strip() != str(st.session_state.get('story_seed') or '').strip():
                            raise ValueError('Saved premise differs from the open revision; reload before saving')
                        _wbs_original['sandbox_slates'] = dict(sandbox_slates)
                        _wbs_original['chosen_option'] = _wbs_title
                        _wbs_original['chosen_option_text'] = _wbs_selected_text
                        _wbs_write = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(_wbs_original)}).eq('id', _wbs_row_id).eq('project_id', get_active_project_id()).eq('user_id', get_current_user_id()).eq('draft_type', 'project_session').execute()
                        if not getattr(_wbs_write, 'data', None):
                            raise ValueError('Database did not confirm the update')
                    except Exception as _wbs_exc:
                        st.error(f'Current revision was not confirmed: {_wbs_exc}')
                        st.stop()
                else:
                    if not _wbs_saved_path_check_ok:
                        st.error('Cannot verify the saved revision; no new revision was written.')
                        st.stop()
                    st.session_state.chosen_option = _wbs_title
                    st.session_state.chosen_option_text = _wbs_selected_text
                    st.session_state.plot_outline = None
                    st.session_state.current_draft_output = None
                    st.session_state.rewritten_manuscript = None
                    st.session_state.final_output_text = None
                    _wbs_reason = f'Plot Change ({_wbs_saved_path} → {_wbs_pending})' if _wbs_is_plot_change and _wbs_saved_path != _wbs_pending else 'Path Selection'
                    _wbs_result = save_current_project_session_to_supabase(version_name=_wbs_reason, save_as_new_version=True)
                    if not _wbs_result or getattr(_wbs_result, 'unchanged', False):
                        st.error('New revision was not confirmed; no further navigation permitted.')
                        st.stop()
                    _wbs_row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
                try:
                    _wbs_rows = supabase.table('writersblock_project_drafts').select('id, project_id, draft_content').eq('id', _wbs_row_id).eq('project_id', get_active_project_id()).eq('user_id', get_current_user_id()).eq('draft_type', 'project_session').limit(1).execute().data or []
                    _wbs_verified = json.loads(_wbs_rows[0]['draft_content']) if len(_wbs_rows) == 1 else {}
                except Exception as _wbs_exc:
                    st.error(f'Path write could not be verified: {_wbs_exc}. Do not advance.')
                    st.stop()
                if _wbs_verified.get('chosen_option') != _wbs_title or _wbs_verified.get('chosen_option_text') != _wbs_selected_text:
                    st.error('Saved revision does not contain the exact selected path. Do not advance.')
                    st.stop()
                st.session_state.chosen_option = _wbs_title
                st.session_state.chosen_option_text = _wbs_selected_text
                if _wbs_save_current:
                    set_loaded_concept_version_baseline(_wbs_verified)
                    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(_wbs_verified)
                    st.session_state['_wbs_last_saved_project_id'] = str(get_active_project_id())
                st.session_state.pop('_wbs_stage2_regen_unsaved', None)
                st.session_state.pop('_wbs_stage2_regen_preview', None)
                st.session_state.pop('_wbs_stage2_pending_path', None)
                st.session_state.pop('_wbs_stage2_choose_new', None)
                st.session_state['_wbs_unlocked_saved_stage'] = max(int(st.session_state.get('_wbs_unlocked_saved_stage') or 1), 3)
                wbs_request_stage_change('Plot Architect')
