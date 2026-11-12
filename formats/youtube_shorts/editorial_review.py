"""youtube_shorts: editorial review. Existing engine and widget contracts retained."""

def render(context):
    BytesIO = context['BytesIO']
    DEFAULT_PICTURE_BOOK_PAGE_SIZE = context['DEFAULT_PICTURE_BOOK_PAGE_SIZE']
    Document = context['Document']
    Inches = context['Inches']
    PICTURE_BOOK_LAYOUT_TEMPLATES = context['PICTURE_BOOK_LAYOUT_TEMPLATES']
    PICTURE_BOOK_PAGE_SIZES = context['PICTURE_BOOK_PAGE_SIZES']
    Pt = context['Pt']
    ai_output_is_usable = context['ai_output_is_usable']
    build_audiobook_production_docx_bytes = context['build_audiobook_production_docx_bytes']
    build_picture_book_cue_script = context['build_picture_book_cue_script']
    build_picture_book_layout_docx_bytes = context['build_picture_book_layout_docx_bytes']
    build_picture_book_spreads_locally = context['build_picture_book_spreads_locally']
    can_use_rewrite = context['can_use_rewrite']
    count_words = context['count_words']
    delete_manuscript_version_ids = context['delete_manuscript_version_ids']
    full_version_only_notice = context['full_version_only_notice']
    get_active_project_id = context['get_active_project_id']
    get_audiobook_production_instruction = context['get_audiobook_production_instruction']
    get_automatic_output_label = context['get_automatic_output_label']
    get_manuscript_version_status_stage = context['get_manuscript_version_status_stage']
    get_manuscript_versions_for_current_project = context['get_manuscript_versions_for_current_project']
    get_picture_book_page_size_spec = context['get_picture_book_page_size_spec']
    get_project_title = context['get_project_title']
    get_project_title_for_display = context['get_project_title_for_display']
    get_text_signature = context['get_text_signature']
    html = context['html']
    normalize_picture_book_spreads = context['normalize_picture_book_spreads']
    persist_project_integrity_in_current_version = context['persist_project_integrity_in_current_version']
    picture_book_cues_docx_bytes = context['picture_book_cues_docx_bytes']
    project_integrity_review_applies = context['project_integrity_review_applies']
    re = context['re']
    render_picture_book_template_preview = context['render_picture_book_template_preview']
    render_project_integrity_report_html = context['render_project_integrity_report_html']
    render_project_title_banner = context['render_project_title_banner']
    require_product_access = context['require_product_access']
    run_project_integrity_final_review = context['run_project_integrity_final_review']
    safe_download_stem = context['safe_download_stem']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    save_manuscript_checkpoint = context['save_manuscript_checkpoint']
    save_picture_book_layout_to_supabase = context['save_picture_book_layout_to_supabase']
    save_project_draft_to_supabase = context['save_project_draft_to_supabase']
    save_stage5_lettered_revision = context['save_stage5_lettered_revision']
    scene_blocks = context['scene_blocks']
    scene_manuscript = context['scene_manuscript']
    scene_outline_parts = context['scene_outline_parts']
    st = context['st']
    wbs_clear_new_project_ui_state = context['wbs_clear_new_project_ui_state']
    wbs_ir_go_to_scene = context['wbs_ir_go_to_scene']
    wbs_ir_located_issues = context['wbs_ir_located_issues']
    wbs_ir_parse_actionable_finding = context['wbs_ir_parse_actionable_finding']
    wbs_request_stage_change = context['wbs_request_stage_change']
    wbs_stage4_accept_and_save = context['wbs_stage4_accept_and_save']
    wbs_stage4_confirm_and_save_from_checkbox = context['wbs_stage4_confirm_and_save_from_checkbox']
    wbs_stage4_final_status = context['wbs_stage4_final_status']
    wbs_stage4_save_final_acceptance = context['wbs_stage4_save_final_acceptance']
    wbs_stage4_save_manuscript_corrections = context['wbs_stage4_save_manuscript_corrections']
    wbs_stage4_title_input_key = context['wbs_stage4_title_input_key']
    wbs_stage4_valid_approvals = context['wbs_stage4_valid_approvals']
    require_product_access('safety')
    if st.session_state.get('export_view', False):
        from core.workflow_runtime import run_workflow
        run_workflow('final_manuscript', context)
    if st.session_state.get('export_view', False):
        if st.session_state.get('demo_mode'):
            st.header('📤 Stage 6: Manuscript Review')
            st.markdown('##### Review the completed manuscript. Final manuscript saving and printout are available in the full Writer Edition.')
        else:
            st.header('📤 Stage 6: FINAL OUTPUT')
            st.markdown('##### Stage 6 is final manuscript output. Save the final manuscript before downloading or starting a new project.')
        render_project_title_banner('step_8_manuscript_output')
    else:
        st.markdown('<style>\n        [data-testid="stMainBlockContainer"] {padding-top: 0 !important;}\n        [data-testid="stMainBlockContainer"] h2 {margin-top: 0 !important;}\n        </style>', unsafe_allow_html=True)
        st.header('🛡️ Stage 4: Editorial & Publisher Review')
        render_project_title_banner('step_5_script_lock')
        current_source = str(st.session_state.get('current_draft_output') or '').strip()
        source_signature = get_text_signature(current_source)
        _wbs_novel_active = False
        _wbs_review_blocks = scene_blocks(st.session_state.get('scene_blocks') or {})
        _wbs_novel_complete = False
        _wbs_exact_four = set(_wbs_review_blocks) == {1, 2, 3, 4} and current_source == scene_manuscript(_wbs_review_blocks)
        st.markdown('### Complete Manuscript — Review & Correct')
        st.caption('The full story is shown in order with permanent scene labels. Edit any or all scenes here, then click Save Manuscript Corrections once. No AI is used when saving; run Integrity again after the save.')
        if _wbs_exact_four:
            _wbs_scene_titles = scene_outline_parts(st.session_state.get('plot_outline') or '')
            _wbs_editor_tag = str(get_active_project_id() or '') + '_' + str(st.session_state.get('_wbs_active_saved_session_row_id') or '') + '_' + source_signature[:18]
            with st.form(key='wbs_stage4_entire_story_editor_' + _wbs_editor_tag):
                _wbs_corrections = {}
                for _n in range(1, 5):
                    _title = _wbs_scene_titles.get(_n, (f'Scene {_n}', '', ''))[0]
                    st.markdown(f'#### Scene {_n} — {html.escape(str(_title))}')
                    _wbs_corrections[_n] = st.text_area(f'Scene {_n} story text', value=_wbs_review_blocks[_n], height=max(200, min(500, 140 + count_words(_wbs_review_blocks[_n]) // 2)), key=f'wbs_stage4_edit_scene_{_n}_{_wbs_editor_tag}', disabled=bool(st.session_state.get('demo_mode')), help='Edit this scene directly. Scene labels are not saved as story text.')
                _wbs_save_corrections = st.form_submit_button('Optional: Review And Save Any Final Manuscript Changes', type='primary', use_container_width=True, disabled=bool(st.session_state.get('demo_mode')))
            if _wbs_save_corrections:
                try:
                    _changed = wbs_stage4_save_manuscript_corrections(_wbs_corrections, current_source, _wbs_review_blocks)
                except Exception as _save_exc:
                    st.error(f'Manuscript corrections were not saved: {_save_exc}')
                else:
                    if _changed:
                        st.session_state['_wbs_stage4_corrections_notice'] = 'All four scenes saved to the current revision. Run Project Integrity again to verify your corrections.'
                    else:
                        st.session_state['_wbs_stage4_corrections_notice'] = 'No changes detected. No save or AI call was needed.'
                    st.rerun()
        elif current_source:
            st.text_area('Entire manuscript (read-only)', value=current_source, height=640, disabled=True, key=f'wbs_stage4_entire_manuscript_{source_signature[:12]}')
            st.info('Inline scene corrections are available when the four saved scene blocks match this manuscript. Existing text is protected.')
        else:
            st.warning('No complete manuscript is available. Return to Scene Scripting.')
        _notice = st.session_state.pop('_wbs_stage4_corrections_notice', None)
        if _notice:
            st.success(_notice)
        _wbs_scene_review_required = _wbs_exact_four
        _wbs_scene_review_complete = True
        if _wbs_scene_review_required:
            _wbs_scene_review_complete = False
            if not _wbs_exact_four:
                st.warning('All four saved scenes must match the working manuscript. Return to Scene Scripting to save the missing or edited scene. No replacement text will be generated here.')
                if st.button('Return to Scene Scripting', key='wbs_stage4_return_incomplete', use_container_width=True):
                    wbs_request_stage_change('Plot Architect')
            else:
                _approved = wbs_stage4_valid_approvals(st.session_state.get('wbs_stage4_scene_approvals'), _wbs_review_blocks, current_source)
                _wbs_scene_review_complete = _approved == {1, 2, 3, 4}
                st.caption(f'{count_words(current_source):,} words · Four scenes assembled in order · No AI regeneration or change to the saved story')
                st.caption('Complete story is ready for Project Integrity review below. Final acceptance is located after the review results.')
        if project_integrity_review_applies():
            st.subheader('🛡️ Project Integrity / Final Review')
            st.caption('Whole-manuscript quality control before Final Output. It checks continuity, names, timeline, repetition, POV/tense drift, unresolved placeholders, missing/duplicate sections, structure, and other inconsistencies. This review does not rewrite or alter your manuscript.')
            integrity_is_current = bool(str(st.session_state.get('project_integrity_report') or '').strip() and st.session_state.get('project_integrity_source_signature') == source_signature)
            if not integrity_is_current and st.session_state.get('project_integrity_report'):
                st.info('The manuscript has changed since the last Project Integrity review. Run the review again for the current manuscript.')
            _wbs_report_visible = integrity_is_current
            _wbs_run_integrity = st.button('Run Project Integrity Report', key='run_project_integrity_final_review', type='primary', use_container_width=True)
            if _wbs_run_integrity:
                with st.spinner('Running whole-manuscript Project Integrity review...'):
                    try:
                        integrity_report = run_project_integrity_final_review(current_source)
                    except Exception as exc:
                        st.error(f'Project Integrity review failed: {exc}')
                    else:
                        st.session_state.project_integrity_report = integrity_report
                        st.session_state.project_integrity_source_signature = source_signature
                        first_line = integrity_report.splitlines()[0].strip().upper() if integrity_report else ''
                        integrity_status = 'PASS' if 'OVERALL STATUS: PASS' in first_line else 'REVIEW INCONCLUSIVE' if 'OVERALL STATUS: REVIEW INCONCLUSIVE' in first_line else 'WARNINGS'
                        st.session_state.project_integrity_status = integrity_status
                        try:
                            persist_project_integrity_in_current_version(integrity_report, source_signature, integrity_status)
                        except Exception as save_exc:
                            st.error(f'Review completed but could not auto-save: {save_exc}')
                        else:
                            st.success('Project Integrity saved in the current version — no new version created.')
                        st.rerun()
            if integrity_is_current and _wbs_report_visible:
                if st.session_state.get('project_integrity_status') == 'PASS':
                    st.success('Project Integrity Review: PASS')
                elif st.session_state.get('project_integrity_status') == 'REVIEW INCONCLUSIVE':
                    st.warning('Project Integrity Review: INCONCLUSIVE — proposed warnings did not meet the evidence requirements. Review the report before Final Output.')
                else:
                    st.warning('Project Integrity Review: WARNINGS — review the report before Final Output.')
                _ir_matches = wbs_ir_located_issues(st.session_state.get('project_integrity_report', ''), _wbs_review_blocks, scene_outline_parts(st.session_state.get('plot_outline') or ''), manuscript_text=current_source) if _wbs_review_blocks else []
                if _ir_matches:
                    st.markdown('### Integrity Warnings — Scene Locations')
                    for _ir_index, _ir_issue in enumerate(_ir_matches):
                        st.markdown(f"**Scene {_ir_issue['scene']} — {_ir_issue['title']}**")
                        _wbs_finding = wbs_ir_parse_actionable_finding(_ir_issue['issue'])
                        st.markdown('**Why this scene was flagged:**')
                        if _wbs_finding:
                            st.write(_wbs_finding['ISSUE'] + ' — ' + _wbs_finding['WHY'])
                            st.markdown('**Specific suggested correction (optional):**')
                            st.write(_wbs_finding['SUGGESTED FIX'])
                        else:
                            st.warning('This older warning does not give a verified, specific correction. Do not alter your story on the basis of this excerpt alone.')
                            st.write(_ir_issue['issue'])
                        if _ir_issue['quote']:
                            st.caption('Passage used to locate the warning (not necessarily erroneous): “' + _ir_issue['quote'] + '”')
                        if st.button(f"Modify This Scene {_ir_issue['scene']}", key=f'wbs_integrity_modify_scene_{_ir_index}_{source_signature[:12]}', use_container_width=False):
                            wbs_ir_go_to_scene(_ir_issue['scene'])
                        st.divider()
                elif _wbs_review_blocks and st.session_state.get('project_integrity_status') != 'PASS':
                    st.info("No scene location could be verified from the report's exact quotes. Use Stage 3 Scene Scripting to inspect the passage; no scene number has been guessed.")
                if 'OVERALL STATUS: WARNINGS' in str(st.session_state.get('project_integrity_report') or '') and '| SUGGESTED FIX:' not in str(st.session_state.get('project_integrity_report') or ''):
                    st.info('This report predates the stricter evidence checks. A quoted passage does not by itself prove a problem; you can run a new review if you want verified, specific recommendations.')
                st.markdown('**Project Integrity Report:**')
                st.markdown(render_project_integrity_report_html(st.session_state.get('project_integrity_report', ''), located_issues=_ir_matches), unsafe_allow_html=True)
            elif not integrity_is_current:
                st.info('Run Project Integrity for the current saved manuscript. It reads your saved corrections but does not alter them.')
                if str(st.session_state.get('project_integrity_report') or '').strip():
                    with st.expander('Previous Integrity Report — before manuscript corrections', expanded=False):
                        st.markdown(render_project_integrity_report_html(st.session_state.get('project_integrity_report', '')), unsafe_allow_html=True)
            st.markdown('---')
        _wbs_ir_ready = not project_integrity_review_applies() or bool(str(st.session_state.get('project_integrity_report') or '').strip() and st.session_state.get('project_integrity_source_signature') == source_signature)
        if _wbs_scene_review_required and _wbs_exact_four:
            st.subheader('For Final Editorial Acceptance, Check Each Button Below')
            st.caption('The existing project title is verified against its saved record. Confirm the completed manuscript and current Integrity Report below. Each acceptance also confirms the saved title without renaming or changing V-number.')
            if not _wbs_ir_ready:
                st.info('The saved Integrity Report does not match this manuscript (or no current report exists). Click Run Project Integrity Report above. Once it completes, check each box to activate its red Save button. Your story is unchanged.')
            _saved_title = get_project_title()
            _proposed_title = re.sub('\\s+', ' ', str(st.session_state.get(wbs_stage4_title_input_key()) or '')).strip() or _saved_title
            _wbs_current_status = wbs_stage4_final_status(st.session_state.get('wbs_stage4_final_acceptance'), _saved_title, current_source, st.session_state.get('project_integrity_report') or '', st.session_state.get('project_integrity_source_signature'), _wbs_scene_review_complete, get_active_project_id(), st.session_state.get('_wbs_active_saved_session_row_id'))
            _stage4_scope = str(get_active_project_id() or 'new') + '_' + str(st.session_state.get('_wbs_active_saved_session_row_id') or 'none') + '_' + get_text_signature(st.session_state.get('project_integrity_report') or '')[:16]
            st.markdown('<style>\n            /* Make the two remaining approval checkboxes visible on the charcoal theme. */\n            [class*="st-key-wbs_stage4_confirm_"] label[data-baseweb="checkbox"] > div:first-child,\n            [class*="st-key-wbs_stage4_confirm_"] label[data-baseweb="checkbox"] input[type="checkbox"] + div,\n            [class*="st-key-wbs_stage4_confirm_"] label[data-baseweb="checkbox"] input[type="checkbox"] + span {\n                outline: 2px solid #ffffff !important;\n                outline-offset: 1px !important;\n                border-radius: 3px !important;\n            }\n            /* Once a confirmation is checked, its button becomes visibly red.\n               The existing disabled gates (e.g., missing Integrity report) remain. */\n            [data-testid="stColumn"]:has([class*="st-key-wbs_stage4_confirm_manuscript_"] input:checked)\n              .st-key-wbs_stage4_accept_full_story button,\n            [data-testid="stColumn"]:has([class*="st-key-wbs_stage4_confirm_integrity_"] input:checked)\n              .st-key-wbs_stage4_accept_integrity button {\n                background-color: #ff4b4b !important;\n                border-color: #ff4b4b !important;\n                color: #ffffff !important;\n                font-weight: 700 !important;\n            }\n            /* Still clearly unavailable when a required review has not run. */\n            [data-testid="stColumn"]:has([class*="st-key-wbs_stage4_confirm_"] input:checked)\n              .stButton button:disabled {\n                opacity: .65 !important;\n                cursor: not-allowed !important;\n            }\n            </style>', unsafe_allow_html=True)
            _manuscript_col, _integrity_col = st.columns(2, gap='small')
            if _wbs_current_status['title'] and _proposed_title == _saved_title:
                st.caption('✓ Existing project title confirmed in the saved revision')
            elif _proposed_title != _saved_title:
                st.caption('A new title has been entered but not saved. Save it above or clear the rename field.')
            else:
                st.caption('The existing saved title will be confirmed when you accept the manuscript or Integrity Report. Renaming is optional.')
            _manuscript_check_key = 'wbs_stage4_confirm_manuscript_' + _stage4_scope
            _integrity_check_key = 'wbs_stage4_confirm_integrity_' + _stage4_scope
            if not _wbs_ir_ready:
                st.session_state[_manuscript_check_key] = False
                st.session_state[_integrity_check_key] = False
            else:
                if _manuscript_check_key not in st.session_state:
                    st.session_state[_manuscript_check_key] = bool(_wbs_current_status['manuscript'])
                if _integrity_check_key not in st.session_state:
                    st.session_state[_integrity_check_key] = bool(_wbs_current_status['integrity'])
            _checkbox_error = st.session_state.pop('_wbs_stage4_checkbox_error', None)
            if _checkbox_error:
                st.error(f'Editorial acceptance was not saved: {_checkbox_error}')
            _checkbox_notice = st.session_state.pop('_wbs_stage4_checkbox_notice', None)
            if _checkbox_notice:
                st.success(_checkbox_notice)
            st.caption('Checking either box saves that approval automatically to the current revision. After both are checked and saved, Stage 5 unlocks. No new V-number is created.')
            with _manuscript_col:
                _confirm_manuscript = st.checkbox('Confirm final manuscript', key=_manuscript_check_key, on_change=wbs_stage4_confirm_and_save_from_checkbox, args=('manuscript', _manuscript_check_key), disabled=not _wbs_ir_ready or bool(st.session_state.get('demo_mode')))
                if st.button('Accept And Save Final Manuscript', type='primary', key='wbs_stage4_accept_full_story', use_container_width=True, disabled=not _wbs_ir_ready or not _confirm_manuscript or bool(st.session_state.get('demo_mode'))):
                    try:
                        _approved = wbs_stage4_accept_and_save()
                        st.session_state['_wbs_stage4_approved_scenes'] = sorted(_approved)
                        wbs_stage4_save_final_acceptance('manuscript')
                    except Exception as exc:
                        st.error(f'Manuscript acceptance was not saved: {exc}')
                    else:
                        st.rerun()
                if _wbs_current_status['manuscript']:
                    st.caption('✓ Final manuscript accepted and saved')
                elif not _wbs_ir_ready:
                    st.caption('Run Integrity before final manuscript acceptance')
            with _integrity_col:
                _confirm_integrity = st.checkbox('Confirm Integrity Report', key=_integrity_check_key, on_change=wbs_stage4_confirm_and_save_from_checkbox, args=('integrity', _integrity_check_key), disabled=not _wbs_ir_ready or bool(st.session_state.get('demo_mode')))
                if st.button('Accept And Save Integrity Report', type='primary', key='wbs_stage4_accept_integrity', use_container_width=True, disabled=not _wbs_ir_ready or not _confirm_integrity or bool(st.session_state.get('demo_mode'))):
                    try:
                        wbs_stage4_save_final_acceptance('integrity')
                    except Exception as exc:
                        st.error(f'Integrity acceptance was not saved: {exc}')
                    else:
                        st.rerun()
                if _wbs_current_status['integrity']:
                    st.caption('✓ Current Integrity Report accepted and saved')
                elif not _wbs_ir_ready:
                    st.caption('Run the current Integrity Report first')
            if all(_wbs_current_status.values()) and _proposed_title == _saved_title:
                st.caption('✓ Both confirmations saved. Stage 5 is unlocked for this revision.')
            else:
                st.caption('Run the current Integrity Check and check both acceptance boxes. The approvals save automatically and Stage 5 unlocks. Scene corrections remain available in Stage 3.')
        st.markdown('---')
        _wbs_final_acceptances = wbs_stage4_final_status(st.session_state.get('wbs_stage4_final_acceptance'), get_project_title(), str(st.session_state.get('current_draft_output') or ''), st.session_state.get('project_integrity_report') or '', st.session_state.get('project_integrity_source_signature'), _wbs_scene_review_complete, get_active_project_id(), st.session_state.get('_wbs_active_saved_session_row_id'))
        _wbs_pending_rename = re.sub('\\s+', ' ', str(st.session_state.get(wbs_stage4_title_input_key()) or '')).strip()
        _wbs_title_has_unsaved_edit = bool(_wbs_pending_rename and _wbs_pending_rename != get_project_title())
        _wbs_ready_for_final = _wbs_scene_review_complete and _wbs_ir_ready and (not _wbs_scene_review_required or (all(_wbs_final_acceptances.values()) and (not _wbs_title_has_unsaved_edit)))
        if st.button('Approve And Save Editorial Review', key='wbs_editorial_to_final', type='primary', disabled=not _wbs_ready_for_final, use_container_width=True):
            if _wbs_ready_for_final:
                if save_current_project_session_to_supabase():
                    from core.stage_navigation import after_approval
                    after_approval(context,4)
        st.stop()
    st.markdown('---')
    if st.session_state.get('export_view', False):
        st.info('✅ FINAL OUTPUT is ready. Save the final manuscript before downloading or starting a new project.')
    else:
        st.info('This is a working draft. Stage 5 provides optional publisher assessment; Stage 6 handles final saving and export.')
    if not st.session_state.get('export_view', False):
        st.markdown('## 📝 DRAFT OUTPUT')
        st.caption('This manuscript is still a working draft. Save it to history before downloading or proceeding if you want this draft preserved.')
        draft_save_notice = st.session_state.pop('draft_save_notice_step5', None)
        if isinstance(draft_save_notice, dict):
            notice_type = draft_save_notice.get('type')
            notice_text = draft_save_notice.get('text') or ''
            if notice_type == 'success':
                st.success(notice_text)
            elif notice_type == 'info':
                st.info(notice_text)
            elif notice_type == 'error':
                st.error(notice_text)
    if st.session_state.get('export_view', False) and (not st.session_state.get('demo_mode')):
        st.markdown('## ✅ FINAL OUTPUT')
        if st.button('💾 SAVE FINAL OUTPUT MANUSCRIPT', key='save_final_output_manuscript_step8', type='primary', use_container_width=True):
            final_result = save_manuscript_checkpoint(status='FINAL', stage_label='Manuscript Output', source_stage='final_output')
            save_result = save_current_project_session_to_supabase()
            if final_result.get('status') == 'saved' and save_result:
                st.success(f"FINAL — Manuscript Output — V{final_result.get('version_number')} saved.")
            elif final_result.get('status') == 'unchanged' and save_result:
                st.info(f"FINAL — Manuscript Output — V{final_result.get('version_number')} is already saved.")
            else:
                st.error('Final manuscript could not be saved completely. No manuscript text was changed.')
    col_left, col_right = st.columns([2, 1])
    with col_left:
        automatic_output_label = get_automatic_output_label()
        if st.session_state.get('demo_mode'):
            st.subheader(f'📋 {automatic_output_label} Review')
        elif st.session_state.get('export_view', False):
            st.subheader(f'📋 FINAL OUTPUT — {automatic_output_label}')
        else:
            st.subheader(f'📋 DRAFT OUTPUT — {automatic_output_label}')
        draft_editor_key = 'final_manuscript_export_view'
        draft_identity = (str(get_active_project_id()), str(st.session_state.get('project_stage') or ''), bool(st.session_state.get('export_view', False)))
        if st.session_state.get('_wbs_stage5_editor_identity') != draft_identity:
            st.session_state[draft_editor_key] = str(st.session_state.current_draft_output or '')
            st.session_state['_wbs_stage5_editor_identity'] = draft_identity

        def _wbs_sync_stage5_manuscript():
            st.session_state.current_draft_output = str(st.session_state.get(draft_editor_key) or '')
        st.text_area('Review Manuscript:', height=500, key=draft_editor_key, on_change=_wbs_sync_stage5_manuscript)
        if not st.session_state.get('export_view', False):
            if st.session_state.get('demo_mode'):
                if st.button('💾 Save This Version 🔒', key='wbs_stage5_revision_trial', use_container_width=True):
                    full_version_only_notice('Saved Versions')
            elif st.button('💾 Save This Version', key='wbs_stage5_revision_save', use_container_width=True):
                _wbs_sync_stage5_manuscript()
                revision = save_stage5_lettered_revision(st.session_state.current_draft_output)
                if revision and revision.get('status') == 'saved':
                    st.success(f"{revision['label']} saved as a separate manuscript revision.")
                elif revision and revision.get('status') == 'unchanged':
                    st.info('This manuscript is already saved as a revision.')
                else:
                    st.error('Revision could not be saved; your text remains in the editor.')
        try:
            current_download_text = str(st.session_state.current_draft_output or '')
            doc = Document()
            doc.add_heading(f'WritersBlock Studios — {automatic_output_label}', level=1)
            doc.add_paragraph(f"Output Status: {('FINAL' if st.session_state.get('export_view', False) else 'DRAFT')}")
            normal_style = doc.styles['Normal']
            normal_style.font.name = 'Courier New' if st.session_state.get('format_type') in {'Screenplay Outline', 'Stage Play / Dramatic Script'} else 'Times New Roman'
            normal_style.font.size = Pt(12)
            section = doc.sections[0]
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            for paragraph in current_download_text.split('\n\n'):
                clean_paragraph = paragraph.strip()
                if clean_paragraph:
                    p = doc.add_paragraph(clean_paragraph)
                    p.paragraph_format.space_after = Pt(8)
                    if st.session_state.get('format_type') in {'Novel / Prose', 'Short Story', 'Novella'}:
                        p.paragraph_format.line_spacing = 2.0
                    elif st.session_state.get('format_type') in {'Screenplay Outline', 'Stage Play / Dramatic Script'}:
                        p.paragraph_format.line_spacing = 1.0
                    else:
                        p.paragraph_format.line_spacing = 1.15
            docx_buffer = BytesIO()
            doc.save(docx_buffer)
            docx_bytes = docx_buffer.getvalue()
            project_stem = safe_download_stem(get_project_title_for_display(), 'writersblock_project')
            format_stem = safe_download_stem(automatic_output_label, 'project_output')
            output_status_stem = 'final' if st.session_state.get('export_view', False) else 'draft'
            safe_filename = f'{project_stem}_{format_stem}_{output_status_stem}'
            if not st.session_state.get('export_view', False):
                if st.session_state.get('demo_mode'):
                    if st.button('💾 SAVE CURRENT DRAFT 🔒', key='save_current_draft_step5_trial', use_container_width=True):
                        full_version_only_notice('Saved Versions')
                elif st.button('💾 SAVE CURRENT DRAFT', key='save_current_draft_step5', type='primary', use_container_width=True):
                    draft_result = save_manuscript_checkpoint(status='DRAFT', stage_label='Script Lock', source_stage='script_lock_draft')
                    save_current_project_session_to_supabase()
                    if draft_result.get('status') == 'saved':
                        st.session_state.draft_save_notice_step5 = {'type': 'success', 'text': f"DRAFT — Script Lock — V{draft_result.get('version_number')} saved to version history."}
                    elif draft_result.get('status') == 'unchanged':
                        st.session_state.draft_save_notice_step5 = {'type': 'info', 'text': f"This DRAFT — Script Lock — V{draft_result.get('version_number')} is already saved."}
                    else:
                        st.session_state.draft_save_notice_step5 = {'type': 'error', 'text': 'Current draft could not be saved to version history.'}
                    st.rerun()
            if st.session_state.get('demo_mode'):
                if st.button(f'Download {automatic_output_label} (.docx) 🔒', key='trial_manuscript_printout_notice', type='primary', use_container_width=True):
                    full_version_only_notice('Manuscript Printout')
            else:
                output_download_prefix = 'Final' if st.session_state.get('export_view', False) else 'Draft'
                st.download_button(label=f'Download {output_download_prefix} {automatic_output_label} (.docx)', data=docx_bytes, file_name=f'{safe_filename}.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', type='primary', use_container_width=True)
            if st.session_state.get('export_view', False) and False:
                st.markdown('---')
                st.subheader("🖼️ Children's Picture Book Layout Draft")
                st.markdown('**Illustration & Page Turn Markers**')
                include_picture_book_cues = st.checkbox('Include [ILLUSTRATION] and [PAGE TURN] planning markers', value=True, key='wbs_picture_book_export_cues')
                prepared_picture_book_script = build_picture_book_cue_script(st.session_state.current_draft_output, include_picture_book_cues)
                st.caption('Markers are planning suggestions, not a finished page design. Turn them off for a clean text-only manuscript. Neither choice changes saved versions.')
                if not st.session_state.get('demo_mode'):
                    st.download_button('Download Picture Book Manuscript (.docx)', data=picture_book_cues_docx_bytes(get_project_title_for_display(), prepared_picture_book_script), file_name=f"{safe_download_stem(get_project_title_for_display(), 'picture_book')}_manuscript.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key='wbs_picture_book_cues_download', use_container_width=True)
                st.caption('The project type selected in Concept Development automatically controls this output. Create the 32-page / 16-spread layout draft, edit story text, and add illustration direction. Layout creation is local and does not call Gemini.')
                page_size_options = list(PICTURE_BOOK_PAGE_SIZES.keys())
                saved_page_size = str(st.session_state.get('picture_book_page_size') or DEFAULT_PICTURE_BOOK_PAGE_SIZE)
                if saved_page_size not in page_size_options:
                    saved_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
                selected_picture_book_page_size = st.selectbox('Picture Book Page Size:', page_size_options, index=page_size_options.index(saved_page_size), key='picture_book_page_size', help='8.5 x 8.5 uses square pages. 10 x 8 uses wider landscape pages. The selected size controls the on-screen spread proportions and layout-draft export.')
                selected_size_spec = get_picture_book_page_size_spec(selected_picture_book_page_size)
                st.caption(f"""Each page: {selected_size_spec['page_width']:g}" × {selected_size_spec['page_height']:g}". Two-page spread: {selected_size_spec['page_width'] * 2:g}" × {selected_size_spec['page_height']:g}".""")
                current_picture_book_signature = get_text_signature(st.session_state.current_draft_output)
                saved_picture_book_signature = st.session_state.get('picture_book_layout_source_signature', '')
                layout_is_current = bool(st.session_state.get('picture_book_layout_spreads') and saved_picture_book_signature and (saved_picture_book_signature == current_picture_book_signature))
                if st.session_state.get('picture_book_layout_spreads') and (not layout_is_current):
                    st.warning('The manuscript has changed since this layout draft was built. Build the layout again before finalizing it.')
                generate_layout_label = 'Rebuild 32-Page Layout — No AI Charge' if st.session_state.get('picture_book_layout_spreads') else 'Build 32-Page Layout — No AI Charge'
                if st.button(generate_layout_label, key='generate_picture_book_layout_local', type='primary', use_container_width=True):
                    require_product_access('safety')
                    if not st.session_state.current_draft_output.strip():
                        st.error('No completed manuscript is available for layout conversion.')
                        st.stop()
                    normalized_layout = build_picture_book_spreads_locally(st.session_state.current_draft_output)
                    st.session_state.picture_book_layout_spreads = normalized_layout
                    st.session_state.picture_book_layout_source_signature = current_picture_book_signature
                    st.session_state.picture_book_layout_preview_id += 1
                    if not st.session_state.get('demo_mode'):
                        save_picture_book_layout_to_supabase(normalized_layout, selected_picture_book_page_size)
                        save_current_project_session_to_supabase()
                    st.rerun()
                if layout_is_current:
                    st.info('32-page planning structure: 16 editable spreads. Each spread can use a different standard layout template.')
                    edited_spreads = []
                    for spread in normalize_picture_book_spreads(st.session_state.picture_book_layout_spreads):
                        spread_number = spread['spread_number']
                        with st.expander(f"Spread {spread_number} — Pages {spread['pages']}", expanded=spread_number == 1):
                            template = st.selectbox('Text / Image Position Template:', PICTURE_BOOK_LAYOUT_TEMPLATES, index=PICTURE_BOOK_LAYOUT_TEMPLATES.index(spread['template']) if spread['template'] in PICTURE_BOOK_LAYOUT_TEMPLATES else 0, key=f'picture_book_template_{st.session_state.picture_book_layout_preview_id}_{spread_number}')
                            render_picture_book_template_preview(template, selected_picture_book_page_size)
                            story_text = st.text_area('Story Text for This Spread:', value=spread.get('story_text', ''), height=130, key=f'picture_book_text_{st.session_state.picture_book_layout_preview_id}_{spread_number}')
                            illustration_direction = st.text_area('Illustration Direction:', value=spread.get('illustration_direction', ''), height=110, key=f'picture_book_illustration_{st.session_state.picture_book_layout_preview_id}_{spread_number}')
                            edited_spreads.append({'spread_number': spread_number, 'pages': spread['pages'], 'template': template, 'story_text': story_text.strip(), 'illustration_direction': illustration_direction.strip()})
                    st.session_state.picture_book_layout_spreads = edited_spreads
                    if st.button('Save Picture Book Layout Draft 💾', key='save_picture_book_layout_edits', use_container_width=True):
                        if st.session_state.get('demo_mode'):
                            full_version_only_notice('Saved Projects')
                        else:
                            result = save_picture_book_layout_to_supabase(edited_spreads, selected_picture_book_page_size)
                            if result:
                                st.session_state.picture_book_layout_preview_id += 1
                                save_current_project_session_to_supabase()
                                st.success("Children's Picture Book layout draft saved.")
                                st.rerun()
                    picture_book_docx_bytes = build_picture_book_layout_docx_bytes(get_project_title_for_display(), edited_spreads, selected_picture_book_page_size)
                    picture_book_stem = safe_download_stem(get_project_title_for_display(), 'children_picture_book')
                    if st.session_state.get('demo_mode'):
                        if st.button('Download Picture Book Layout Draft (.docx) 🔒', key='trial_picture_book_layout_download_notice', type='primary', use_container_width=True):
                            full_version_only_notice('Manuscript Printout')
                    else:
                        st.download_button(label='Download Picture Book Layout Draft (.docx)', data=picture_book_docx_bytes, file_name=f'{picture_book_stem}_layout_draft.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', type='primary', use_container_width=True)
            if st.session_state.get('export_view', False) and False:
                st.markdown('---')
                st.subheader('🎙️ Audiobook Theatre Production Layout')
                st.caption('The Audio Book project type automatically outputs an Audiobook Theatre Production Script. There is no alternate output-format selector.')
                selected_cue_level = st.selectbox('Production Cue Level:', ['Clean Voices Only', 'Voices + Minimal SFX', 'Full Audiobook Theatre Cues'], index=['Clean Voices Only', 'Voices + Minimal SFX', 'Full Audiobook Theatre Cues'].index(st.session_state.get('audiobook_production_cue_level', 'Voices + Minimal SFX') if st.session_state.get('audiobook_production_cue_level', 'Voices + Minimal SFX') in ['Clean Voices Only', 'Voices + Minimal SFX', 'Full Audiobook Theatre Cues'] else 'Voices + Minimal SFX'), key='audiobook_production_cue_level_select')
                current_production_source_signature = get_text_signature(st.session_state.current_draft_output)
                saved_production_signature = st.session_state.get('audiobook_production_source_signature', '')
                production_script_is_current = bool(st.session_state.get('audiobook_production_script', '').strip() and saved_production_signature and (saved_production_signature == current_production_source_signature))
                if st.session_state.get('audiobook_production_script', '').strip() and (not production_script_is_current):
                    st.warning('The manuscript has changed since this production script was generated. Generate it again before downloading or recording.')
                production_button_label = 'Refresh Production Script 🎙️' if st.session_state.get('audiobook_production_script', '').strip() else 'Generate Production Script 🎙️'
                if st.button(production_button_label, key='generate_audiobook_production_script', type='primary', use_container_width=True):
                    require_product_access('safety')
                    if not st.session_state.current_draft_output.strip():
                        st.error('No current manuscript is available for production conversion.')
                        st.stop()
                    with st.spinner('Converting the manuscript into an Audiobook Theatre production layout...'):
                        try:
                            production_output = st.session_state.backend.run_rewrite_engine(source_text=st.session_state.current_draft_output, rewrite_mode='Direct Script Change / Obey My Instructions Exactly', scene_choice='Full Manuscript', custom_instruction=get_audiobook_production_instruction(selected_cue_level), target_length='Keep Current Length', custom_target_word_count=None, tone_style=st.session_state.tone_style, author_style=st.session_state.author_style)
                        except Exception as e:
                            st.error(f'Production layout conversion failed: {e}')
                            st.stop()
                    if not ai_output_is_usable(production_output):
                        st.error('The production layout conversion did not return usable text. The manuscript was not changed and no production script was saved.')
                        st.stop()
                    st.session_state.audiobook_production_script = str(production_output).strip()
                    st.session_state.audiobook_production_source_signature = current_production_source_signature
                    st.session_state.audiobook_production_cue_level = selected_cue_level
                    st.session_state.audiobook_production_preview_id += 1
                    project_id = get_active_project_id()
                    if project_id:
                        save_project_draft_to_supabase(project_id=project_id, draft_title='Audiobook Theatre Production Script', draft_type='audiobook_production_script', draft_content=st.session_state.audiobook_production_script)
                    save_current_project_session_to_supabase()
                    st.rerun()
                if production_script_is_current:
                    edited_production_script = st.text_area('Review / Edit Production Script:', value=st.session_state.audiobook_production_script, height=500, key=f'audiobook_production_script_editor_{st.session_state.audiobook_production_preview_id}')
                    st.session_state.audiobook_production_script = edited_production_script
                    st.caption(f'Production Script Words: {count_words(st.session_state.audiobook_production_script):,}')
                    if st.button('Save Production Script Edits 💾', key='save_audiobook_production_edits', use_container_width=True):
                        project_id = get_active_project_id()
                        if project_id:
                            save_project_draft_to_supabase(project_id=project_id, draft_title='Audiobook Theatre Production Script - Edited', draft_type='audiobook_production_script', draft_content=st.session_state.audiobook_production_script)
                        save_current_project_session_to_supabase()
                        st.success('Production script edits saved.')
                    project_stem = safe_download_stem(get_project_title_for_display(), 'audiobook')
                    production_docx_bytes = build_audiobook_production_docx_bytes(get_project_title_for_display(), st.session_state.audiobook_production_script)
                    if st.session_state.get('demo_mode'):
                        if st.button('Download Audiobook Theatre Production Script (.docx) 🔒', key='trial_audiobook_printout_notice', type='primary', use_container_width=True):
                            full_version_only_notice('Manuscript Printout')
                    else:
                        st.download_button(label='Download Final Audiobook Theatre Production Script (.docx)', data=production_docx_bytes, file_name=f'{project_stem}_audiobook_theatre_production_script.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', type='primary', use_container_width=True)
            if can_use_rewrite:
                if st.button('Proceed to Script Rewrite 🛠️', key='proceed_to_rewrite_from_export', type='primary', use_container_width=True):
                    wbs_request_stage_change('Rewrite Engine')
            else:
                st.button('🔒 Script Rewrite Locked', key='rewrite_locked_from_export', disabled=True, use_container_width=True)
        except Exception as e:
            st.error(f'Failed to generate Word document: {e}')
    with col_right:
        st.subheader('📊 Output Summary')
        compiled_scene_count = len([scene_text for scene_text in st.session_state.get('scene_blocks', {}).values() if str(scene_text or '').strip()])
        if compiled_scene_count == 0 and str(st.session_state.get('current_draft_output', '')).strip():
            compiled_scene_count = max(int(st.session_state.get('current_processing_beat', 1) or 1) - 1, 1)
        st.metric(label='Script Blocks Compiled', value=f'{compiled_scene_count}')
        st.markdown('**Project Memory Cache:**')
        st.text_area('Saved Project Memory:', value=st.session_state.rolling_lore_book, height=200, key='final_lore_view', disabled=True)
        st.write('---')
        st.subheader('🗂️ Saved Versions')
        if st.session_state.get('demo_mode'):
            st.caption('Saved Versions are available in the full Writer Edition.')
            if st.button('Open Saved Versions 🔒', key='trial_output_saved_versions_notice', use_container_width=True):
                full_version_only_notice('Saved Versions')
        else:
            saved_version_count = len(get_manuscript_versions_for_current_project())
            st.caption(f'Saved manuscript versions: {saved_version_count}')
            st.caption('Use Saved Version Manager in the sidebar when you want to review, restore, download, or delete a saved version.')
        st.write('---')
        if st.button('🔄 Start New Project', use_container_width=True):
            wbs_clear_new_project_ui_state()
            st.session_state.project_title = ''
            st.session_state.current_project_id = None
            for _key in ('_wbs_loaded_project_id', '_wbs_loaded_project_title', '_wbs_loaded_saved_session_id', '_wbs_loaded_manuscript_version_id', 'wbs_locked_format_id', '_wbs_locked_project_id'):
                st.session_state.pop(_key, None)
            st.session_state.project_version_name = 'Original'
            st.session_state.project_stage = 'Intake'
            st.session_state.project_scope = 'Standalone Book'
            st.session_state.series_key = ''
            st.session_state.series_name = ''
            st.session_state.series_book_number = 1
            st.session_state.series_continuity_mode = 'Strict'
            st.session_state.series_reference_ids = []
            st.session_state.series_canon_notes = ''
            st.session_state.series_selection_signature = ''
            st.session_state.pop('series_reference_selector', None)
            st.session_state.pop('series_choice_selector', None)
            st.session_state.pop('series_name_input', None)
            st.session_state.sandbox_slates = None
            st.session_state.chosen_option = None
            st.session_state.chosen_option_text = None
            st.session_state.plot_outline = None
            st.session_state.current_draft_output = ''
            st.session_state.rolling_lore_book = ''
            st.session_state.completed_beats = []
            st.session_state.scene_blocks = {}
            st.session_state.current_processing_beat = 1
            st.session_state.rewritten_manuscript = ''
            st.session_state.rewrite_applied_message = ''
            st.session_state.audiobook_production_script = ''
            st.session_state.audiobook_production_source_signature = ''
            st.session_state.audiobook_production_preview_id = 0
            st.session_state.picture_book_layout_spreads = []
            st.session_state.picture_book_layout_source_signature = ''
            st.session_state.picture_book_layout_preview_id = 0
            st.session_state.picture_book_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
            st.session_state.manuscript_version = 0
            st.session_state.current_manuscript_save_status = ''
            st.session_state.current_manuscript_save_stage = ''
            st.session_state.current_manuscript_save_version = 0
            st.session_state.export_view = False
            st.session_state.show_saved_version_manager = False
            st.rerun()
    if st.session_state.get('export_view', False) and st.session_state.get('show_saved_version_manager', False):
        if st.session_state.get('demo_mode'):
            st.markdown('---')
            st.subheader('🗂️ Saved Version Manager')
            st.caption('Saved Versions remain visible during the trial and unlock with the full Writer Edition.')
            if st.button('Open Saved Version Manager 🔒', key='trial_saved_version_manager_page_notice', use_container_width=True):
                full_version_only_notice('Saved Versions')
        else:
            st.markdown('---')
            st.subheader('🗂️ Saved Version Manager')
            st.caption('Review saved manuscript versions here. Nothing changes unless you choose Restore or Delete. Delete removes only the selected saved version after confirmation.')
            manager_versions = get_manuscript_versions_for_current_project()
            if not manager_versions:
                st.info('No saved manuscript versions found yet.')
            else:
                manager_items = []
                for version in manager_versions:
                    project_join = version.get('writersblock_projects') or {}
                    if isinstance(project_join, dict):
                        project_title_for_version = project_join.get('project_title')
                    else:
                        project_title_for_version = None
                    title = str(project_title_for_version or version.get('project_title') or get_project_title_for_display()).strip()
                    version_number = int(version.get('version_number') or 1)
                    created_at = version.get('created_at')
                    word_count = count_words(version.get('manuscript_content', ''))
                    status, stage_label = get_manuscript_version_status_stage(version)
                    label_text = str(version.get('version_label') or 'Saved Version').strip()
                    display_label = f'{title} — {status} V{version_number} — {word_count} words'
                    manager_items.append({'label': display_label, 'version': version, 'title': title, 'version_number': version_number, 'word_count': word_count, 'label_text': label_text})
                manager_labels = [item['label'] for item in manager_items]
                manager_lookup = {item['label']: item for item in manager_items}
                selected_manager_label = st.selectbox('Saved versions:', manager_labels, key=f"saved_version_manager_selector_{st.session_state.get('current_project_id')}")
                selected_manager_item = manager_lookup.get(selected_manager_label)
                selected_manager_version = selected_manager_item['version'] if selected_manager_item else None
                selected_manager_text = str(selected_manager_version.get('manuscript_content') or '') if selected_manager_version else ''
                st.text_area('Selected Version Review:', value=selected_manager_text, height=520, key=f"saved_version_manager_review_box_{st.session_state.get('current_project_id')}", disabled=True)
                col_download, col_restore, col_delete = st.columns(3)
                with col_download:
                    try:
                        version_doc = Document()
                        version_doc.add_heading(f"WritersBlock Studios Manuscript - {selected_manager_item['label']}", level=1)
                        for paragraph in selected_manager_text.split('\n\n'):
                            clean_paragraph = paragraph.strip()
                            if clean_paragraph:
                                p = version_doc.add_paragraph(clean_paragraph)
                                p.paragraph_format.space_after = Pt(8)
                                p.paragraph_format.line_spacing = 1.15
                        version_buffer = BytesIO()
                        version_doc.save(version_buffer)
                        st.download_button(label='Download Selected Version', data=version_buffer.getvalue(), file_name=f"saved_version_v{selected_manager_item['version_number']}.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
                    except Exception as e:
                        st.error(f'Selected version download unavailable: {e}')
                with col_restore:
                    restore_confirmed = st.checkbox('Confirm restore', key=f"confirm_restore_selected_version_{st.session_state.get('current_project_id')}")
                    if st.button('Restore Selected Version', key=f"restore_selected_saved_version_{st.session_state.get('current_project_id')}", disabled=not restore_confirmed, use_container_width=True):
                        st.session_state.current_draft_output = selected_manager_text
                        st.session_state.current_project_id = selected_manager_version.get('project_id')
                        st.session_state.project_title = selected_manager_item.get('title') or get_project_title_for_display()
                        st.session_state.manuscript_version = int(selected_manager_version.get('version_number') or st.session_state.get('manuscript_version', 0) or 0)
                        st.session_state.rewritten_manuscript = ''
                        st.session_state.rewrite_applied_message = 'Selected saved version restored as the current manuscript.'
                        save_current_project_session_to_supabase()
                        st.success('Selected saved version restored as the current manuscript.')
                        st.rerun()
                with col_delete:
                    delete_confirmed = st.checkbox('I understand this will permanently delete the selected saved version.', key=f"confirm_delete_selected_version_{st.session_state.get('current_project_id')}")
                    if st.button('Delete Selected Version', key=f"delete_selected_saved_version_{st.session_state.get('current_project_id')}", disabled=not delete_confirmed, use_container_width=True):
                        delete_manuscript_version_ids([selected_manager_version.get('id')])
                        st.success('Selected saved version deleted.')
                        st.rerun()
