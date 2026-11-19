"""screenplay: final manuscript. Existing engine and widget contracts retained."""

def render(context):
    DEFAULT_PICTURE_BOOK_PAGE_SIZE = context['DEFAULT_PICTURE_BOOK_PAGE_SIZE']
    FINAL_OUTPUT_FORMAT_OPTIONS = context['FINAL_OUTPUT_FORMAT_OPTIONS']
    PICTURE_BOOK_FORMAT = context['PICTURE_BOOK_FORMAT']
    build_final_output_docx_bytes = context['build_final_output_docx_bytes']
    build_picture_book_layout_docx_bytes = context['build_picture_book_layout_docx_bytes']
    build_picture_book_spreads_locally = context['build_picture_book_spreads_locally']
    count_words = context['count_words']
    full_version_only_notice = context['full_version_only_notice']
    get_automatic_output_label = context['get_automatic_output_label']
    get_final_output_format = context['get_final_output_format']
    get_project_title_for_display = context['get_project_title_for_display']
    get_text_signature = context['get_text_signature']
    project_integrity_review_applies = context['project_integrity_review_applies']
    render_project_title_banner = context['render_project_title_banner']
    safe_download_stem = context['safe_download_stem']
    st = context['st']
    st.header('📤 Stage 6: Manuscript Review' if st.session_state.get('demo_mode') else '✅ Stage 6: Final Manuscript')
    render_project_title_banner('step_8_final_output_conversion')
    st.markdown('---')
    current_source = str(st.session_state.get('current_draft_output') or '').strip()
    if not current_source:
        st.warning('No working manuscript is available for Final Output.')
        st.stop()
    selected_final_format = str(st.session_state.get('format_type') or 'Novel / Prose').strip()
    if selected_final_format not in FINAL_OUTPUT_FORMAT_OPTIONS:
        selected_final_format = get_final_output_format()
    st.session_state.final_output_format = selected_final_format
    source_signature = get_text_signature(current_source)
    if st.session_state.get('final_output_source_signature') != source_signature or str(st.session_state.get('final_output_text') or '').strip() != current_source:
        st.session_state.final_output_text = current_source
        st.session_state.final_output_source_signature = source_signature
        st.session_state.final_output_saved_signature = ''
    st.subheader(f'📋 FINAL MANUSCRIPT — {get_automatic_output_label(selected_final_format)}')
    st.caption(f'{count_words(current_source):,} words · Prepared directly from the approved manuscript · No AI regeneration')
    st.text_area('Final Manuscript', value=current_source, height=520, disabled=True, key=f'wbs_final_manuscript_readonly_{source_signature}')
    _wbs_final_integrity_current = not project_integrity_review_applies() or (bool(str(st.session_state.get('project_integrity_report') or '').strip()) and st.session_state.get('project_integrity_source_signature') == source_signature)
    if not _wbs_final_integrity_current:
        st.warning('Return to Stage 4 and run Project Integrity before downloading the final manuscript.')
    st.caption('Your final manuscript was already saved and approved in Stage 4; no additional save is needed.')
    if st.session_state.get('demo_mode'):
        if st.button('Download / Print Manuscript (.docx) 🔒', type='primary', key='trial_download_final_converted_output', use_container_width=True):
            full_version_only_notice('Manuscript Printout')
    else:
        if selected_final_format == PICTURE_BOOK_FORMAT:
            spreads = build_picture_book_spreads_locally(current_source)
            docx_bytes = build_picture_book_layout_docx_bytes(get_project_title_for_display(), spreads, st.session_state.get('picture_book_page_size', DEFAULT_PICTURE_BOOK_PAGE_SIZE))
        else:
            docx_bytes = build_final_output_docx_bytes(get_project_title_for_display(), current_source, selected_final_format)
        project_stem = safe_download_stem(get_project_title_for_display(), 'writersblock_project')
        format_stem = safe_download_stem(get_automatic_output_label(selected_final_format), 'final_output')
        st.download_button(label='🖨️ Download / Print Manuscript (.docx)', data=docx_bytes, file_name=f'{project_stem}_{format_stem}_final.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', type='primary', use_container_width=True)
    st.stop()
