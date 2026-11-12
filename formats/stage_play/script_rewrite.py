"""stage_play: script rewrite. Existing engine and widget contracts retained."""

def render(context):
    BytesIO = context['BytesIO']
    DIALOGUE_STYLE_OPTIONS = context['DIALOGUE_STYLE_OPTIONS']
    Document = context['Document']
    Pt = context['Pt']
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    count_words = context['count_words']
    create_bridge_adapter = context['create_bridge_adapter']
    full_version_only_notice = context['full_version_only_notice']
    get_dialogue_style = context['get_dialogue_style']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_effective_format_type = context['get_effective_format_type']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    get_rewrite_dialogue_instruction = context['get_rewrite_dialogue_instruction']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_project_title_banner = context['render_project_title_banner']
    require_product_access = context['require_product_access']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    save_manuscript_checkpoint = context['save_manuscript_checkpoint']
    st = context['st']
    wbs_request_stage_change = context['wbs_request_stage_change']
    require_product_access('rewrite')
    st.header('🛠️ Stage 4: Optional Script Rewrite')
    render_project_title_banner('step_7_script_rewrite')
    st.markdown('##### Script Rewrite uses the current live manuscript only. Saved versions are available for download, but are not used as the script rewrite source.')
    st.markdown('---')
    if 'rewritten_manuscript' not in st.session_state:
        st.session_state.rewritten_manuscript = ''
    if 'rewrite_preview_id' not in st.session_state:
        st.session_state.rewrite_preview_id = 0
    if 'rewrite_target_length' not in st.session_state:
        st.session_state.rewrite_target_length = 'Keep Current Length'
    manuscript_text = st.session_state.get('current_draft_output', '')

    def split_text_into_scene_chunks(full_text, total_scenes=4):
        full_text = str(full_text or '').strip()
        if not full_text:
            return []
        paragraphs = [p.strip() for p in re.split('\\n\\s*\\n', full_text) if p.strip()]
        if not paragraphs:
            return [full_text]
        total_scenes = max(1, int(total_scenes or 1))
        chunk_size = max(1, (len(paragraphs) + total_scenes - 1) // total_scenes)
        chunks = []
        for i in range(total_scenes):
            start_idx = i * chunk_size
            end_idx = min(len(paragraphs), (i + 1) * chunk_size)
            if start_idx < len(paragraphs):
                chunks.append('\n\n'.join(paragraphs[start_idx:end_idx]).strip())
        return chunks

    def get_scene_beat_text(full_text, beat_number):
        scene_blocks = st.session_state.get('scene_blocks', {})
        stored_scene = scene_blocks.get(int(beat_number)) if isinstance(scene_blocks, dict) else None
        if stored_scene and str(stored_scene).strip():
            return str(stored_scene).strip()
        chunks = split_text_into_scene_chunks(full_text, 4)
        idx = int(beat_number) - 1
        if 0 <= idx < len(chunks):
            return chunks[idx]
        return ''

    def replace_scene_beat_text(full_text, beat_number, replacement_text):
        full_text = str(full_text or '')
        replacement_text = str(replacement_text or '').strip()
        scene_blocks = st.session_state.get('scene_blocks', {})
        stored_scene = None
        if isinstance(scene_blocks, dict):
            stored_scene = scene_blocks.get(int(beat_number))
        if stored_scene and str(stored_scene).strip() and (str(stored_scene).strip() in full_text):
            st.session_state.scene_blocks[int(beat_number)] = replacement_text
            return full_text.replace(str(stored_scene).strip(), replacement_text, 1)
        current_scene_text = get_scene_beat_text(full_text, beat_number)
        if current_scene_text and current_scene_text in full_text:
            if isinstance(scene_blocks, dict):
                st.session_state.scene_blocks[int(beat_number)] = replacement_text
            return full_text.replace(current_scene_text, replacement_text, 1)
        return full_text

    def strip_internal_notices(text):
        text = str(text or '')
        text = re.sub('\\n?\\[LOCAL NODE 8 FALLBACK NOTE:.*?\\]', '', text, flags=re.DOTALL)
        text = re.sub('\\n?\\[LOCAL .*?FALLBACK NOTE:.*?\\]', '', text, flags=re.DOTALL)
        text = re.sub('\\n?NODE 8 TEST OUTPUT.*', '', text, flags=re.DOTALL)
        return text.strip()
    if not manuscript_text.strip():
        st.warning('No manuscript draft found. Return to Creative Draft and complete drafting first.')
    else:
        col_left, col_right = st.columns([2, 1])
        with col_right:
            st.subheader('🛠️ Script Rewrite Controls')
            rewrite_mode = st.selectbox('1) Script Rewrite Mode:', ['Creative Script Rewrite / Improve Scene', 'Direct Script Change / Obey My Instructions Exactly', 'Polish Only / Do Not Change Story'], key='rewrite_mode_select')
            scene_choice = st.selectbox('2) Script Rewrite Location:', ['Full Manuscript', 'Scene Beat 1', 'Scene Beat 2', 'Scene Beat 3', 'Scene Beat 4'], key='rewrite_scene_choice')
            rewrite_target_length = st.selectbox('3) Target Length:', ['Keep Current Length', 'Condense for Tighter Pacing', 'Expand to 400 Words', 'Custom Word Count'], key='rewrite_target_length')
            custom_target_word_count = None
            if rewrite_target_length == 'Custom Word Count':
                custom_target_word_count = st.number_input('Custom Target Word Count:', min_value=50, max_value=2500, value=min(1200, max(50, count_words(st.session_state.current_draft_output))), step=25, key='custom_target_word_count')
            current_project_dialogue_style = get_dialogue_style()
            rewrite_dialogue_options = [f'Use Current Project Dialogue Style — {get_dialogue_style_display(current_project_dialogue_style)}', *DIALOGUE_STYLE_OPTIONS]
            rewrite_dialogue_choice = st.selectbox('4) Dialogue Style for Rewrite:', rewrite_dialogue_options, index=0, key='rewrite_dialogue_style_choice', format_func=lambda option: get_dialogue_style_display(option) if option in DIALOGUE_STYLE_OPTIONS else option, help="Percentages are approximate spoken-dialogue targets. Default preserves the project's current Dialogue Style. Choose another option only when you intentionally want this rewrite to use a different dialogue/narration balance.")
            st.caption(f'Current Project Dialogue Style: {get_dialogue_style_display(current_project_dialogue_style)}. The selected project type remains locked and controls dialogue formatting.')
            custom_rewrite_instruction = st.text_area('5) Specific Script Rewrite Direction - Optional:', value='', height=160, placeholder="Example: Keep the same ending, but expand the story with stronger atmosphere, more antique shop detail, more dread, and more of Elias's physical decline.", key='custom_rewrite_instruction')
            st.markdown('---')
            st.info('Script Rewrite uses only the current live manuscript shown on this page. Saved versions are not used as the script rewrite source. Dialogue Style defaults to the current project setting unless you deliberately choose a rewrite override above.')
        if scene_choice == 'Full Manuscript':
            selected_source_text = manuscript_text
        else:
            beat_number = int(scene_choice.replace('Scene Beat ', ''))
            selected_source_text = get_scene_beat_text(manuscript_text, beat_number)
        with col_left:
            st.subheader('📄 Editable Source Text')
            edited_source_text = st.text_area('Edit selected source text before script rewrite:', value=selected_source_text, height=500, key=f"editable_rewrite_source_{scene_choice.replace(' ', '_')}_{st.session_state.manuscript_version}")
            st.caption(f'Selected Source Words: {count_words(edited_source_text)}')
            st.caption('Save a manual change as a new draft version, or run an optional AI rewrite below.')
            if st.session_state.get('demo_mode'):
                st.button('💾 Save This Version 🔒', key='rewrite_manual_save_locked', disabled=True, use_container_width=True)
            elif st.button('💾 Save This Version', key='rewrite_manual_save', use_container_width=True):
                if not str(edited_source_text or '').strip():
                    st.error('There is no revised text to save.')
                else:
                    if scene_choice == 'Full Manuscript':
                        updated_manuscript = str(edited_source_text).strip()
                    else:
                        updated_manuscript = replace_scene_beat_text(st.session_state.current_draft_output, int(scene_choice.replace('Scene Beat ', '')), str(edited_source_text).strip())
                    if updated_manuscript == st.session_state.current_draft_output:
                        st.info('No changes to save. Your current manuscript is preserved.')
                    else:
                        previous_manuscript = st.session_state.current_draft_output
                        st.session_state.current_draft_output = updated_manuscript
                        try:
                            saved = save_manuscript_checkpoint(status='DRAFT', stage_label='Script Rewrite Manual Edit', source_stage='script_rewrite_manual_edit')
                        except Exception as exc:
                            st.session_state.current_draft_output = previous_manuscript
                            st.error(f'Version save failed: {exc}')
                        else:
                            if saved.get('status') == 'saved':
                                st.success('Edited manuscript saved as a new version. Earlier manuscript versions remain available.')
                                save_current_project_session_to_supabase()
                            else:
                                st.session_state.current_draft_output = previous_manuscript
                                st.error('The edited manuscript was not saved; the previously active text has been restored.')
            st.markdown('---')
            if st.button('Run Script Rewrite 🛠️', key='run_rewrite_engine', type='primary', use_container_width=True):
                require_product_access('rewrite')
                if not edited_source_text.strip():
                    st.error('No source text selected for script rewrite.')
                else:
                    with st.spinner('Running script rewrite...'):
                        try:
                            effective_custom_rewrite_instruction = custom_rewrite_instruction.strip()
                            if 'quill' in effective_custom_rewrite_instruction.lower():
                                quill_creative_suggestion = str(st.session_state.get('_wbs_quill_last_creative_suggestion', '') or '').strip()
                                if not quill_creative_suggestion:
                                    st.warning('No recent Quill creative revision is available in this session. Ask Quill for the revision first, then return to Step 7 and run the rewrite.')
                                    st.stop()
                                effective_custom_rewrite_instruction = effective_custom_rewrite_instruction + '\n\nQUILL CREATIVE SUGGESTION REFERENCED BY THE WRITER:\n' + quill_creative_suggestion + '\n\nApply that Quill material only within the selected Script Rewrite Location. Preserve all other scenes/beats and the balance of the existing manuscript.'
                            rewrite_instruction_packet = get_rewrite_dialogue_instruction(rewrite_dialogue_choice) + '\n\nADDITIONAL CREATOR REWRITE DIRECTION:\n' + (effective_custom_rewrite_instruction if effective_custom_rewrite_instruction else 'No additional rewrite direction provided.')
                            if create_bridge_adapter is None:
                                raise RuntimeError('WritersBlock Model is unavailable. ' + WBS_MODEL_IMPORT_ERROR)
                            _wbs_rewrite_bridge = create_bridge_adapter(backend=st.session_state.backend)
                            _wbs_rewrite_result = _wbs_rewrite_bridge.execute('Rewrite this manuscript', st.session_state, prepared_context={'effective_format_type': get_effective_format_type(), 'format_development_context': get_full_project_continuity_context(), 'quill_format_instructions': st.session_state.get('quill_format_instructions', ''), 'quill_template_context': refresh_quill_template_context()}, action_payload={'source_text': edited_source_text, 'backend_rewrite_mode': rewrite_mode, 'scene_choice': scene_choice, 'custom_instruction': rewrite_instruction_packet, 'target_length': rewrite_target_length, 'custom_target_word_count': custom_target_word_count, 'tone_style': st.session_state.tone_style, 'author_style': st.session_state.author_style})
                            if not _wbs_rewrite_result.success:
                                raise RuntimeError(_wbs_rewrite_result.error or 'WritersBlock Model Bridge returned no rewrite.')
                            st.session_state.rewritten_manuscript = _wbs_rewrite_result.output
                            st.session_state['_wbs_agent_bridge_last_operation'] = _wbs_rewrite_result.backend_operation or ''
                            st.session_state['_wbs_agent_bridge_last_success'] = True
                            st.session_state.rewrite_preview_id += 1
                        except Exception as e:
                            st.session_state.rewritten_manuscript = f'Script rewrite fallback output.\n\nBackend error: {e}\n\nThe script rewrite request was received, but the AI backend did not return usable text.'
                            st.session_state.rewrite_preview_id += 1
                        st.rerun()
            st.caption('If you are satisfied with the current manuscript, skip rewriting and proceed unchanged. No AI rewrite is run and no rewrite credits are used.')
            if st.button('SKIP REWRITE — PROCEED TO FINAL OUTPUT ➡️', key='skip_rewrite_to_final_output', type='primary', use_container_width=True):
                st.session_state.rewritten_manuscript = ''
                st.session_state.rewrite_applied_message = 'Rewrite skipped. Current manuscript preserved unchanged.'
                wbs_request_stage_change('Isolation Guardrail', export_view=True)
        st.markdown('---')
        st.subheader('✍️ Script Rewrite Output')
        st.text_area('Script Rewrite Output:', value=st.session_state.rewritten_manuscript, height=450, label_visibility='collapsed', key=f'rewrite_output_preview_{st.session_state.rewrite_preview_id}')
        preview_words = count_words(st.session_state.rewritten_manuscript)
        if st.session_state.rewritten_manuscript.strip():
            st.caption(f'Script Rewrite Preview Words: {preview_words}')
        if st.session_state.rewrite_applied_message:
            st.success(st.session_state.rewrite_applied_message)
        preview_is_safe_to_apply = st.session_state.rewritten_manuscript.strip() and 'Script rewrite fallback output' not in st.session_state.rewritten_manuscript and ('Backend error:' not in st.session_state.rewritten_manuscript)
        if st.session_state.rewritten_manuscript.strip() and (not preview_is_safe_to_apply):
            st.error('This script rewrite preview could not be used. Please run the script rewrite again.')
        if preview_is_safe_to_apply:
            if st.button('Apply Script Rewrite to Full Manuscript ✅', key='apply_rewrite_to_manuscript', type='primary', use_container_width=True):
                cleaned_rewrite_for_manuscript = strip_internal_notices(st.session_state.rewritten_manuscript)
                if scene_choice == 'Full Manuscript':
                    st.session_state.current_draft_output = cleaned_rewrite_for_manuscript
                    st.session_state.rewrite_applied_message = 'Full manuscript replaced with script rewrite version.'
                else:
                    beat_number = int(scene_choice.replace('Scene Beat ', ''))
                    st.session_state.current_draft_output = replace_scene_beat_text(st.session_state.current_draft_output, beat_number, cleaned_rewrite_for_manuscript)
                    st.session_state.rewrite_applied_message = f'{scene_choice} script rewrite applied to the full manuscript.'
                st.session_state.rewritten_manuscript = ''
                rewrite_checkpoint = save_manuscript_checkpoint(status='DRAFT', stage_label='Script Rewrite', source_stage='script_rewrite_draft')
                st.session_state.rewrite_preview_id += 1
                save_result = save_current_project_session_to_supabase()
                if save_result:
                    st.session_state.rewrite_applied_message = st.session_state.rewrite_applied_message + ' Project saved to the current accepted state.'
                else:
                    st.session_state.rewrite_applied_message = st.session_state.rewrite_applied_message + ' Project session was not saved automatically. Use Save Project Changes As A New Version before leaving.'
                wbs_request_stage_change('Isolation Guardrail', export_view=True)
        st.markdown('---')
        st.markdown('## 📝 DRAFT OUTPUT')
        st.caption('The current manuscript remains a draft until it is saved at Step 8 as the FINAL OUTPUT MANUSCRIPT.')
        if st.session_state.get('demo_mode'):
            if st.button('💾 SAVE CURRENT DRAFT 🔒', key='save_current_draft_rewrite_trial', use_container_width=True):
                full_version_only_notice('Saved Versions')
        elif st.button('💾 SAVE CURRENT DRAFT', key='save_current_draft_rewrite', type='primary', use_container_width=True):
            rewrite_draft_result = save_manuscript_checkpoint(status='DRAFT', stage_label='Script Rewrite', source_stage='script_rewrite_draft')
            save_current_project_session_to_supabase()
            if rewrite_draft_result.get('status') == 'saved':
                st.success(f"DRAFT — Script Rewrite — V{rewrite_draft_result.get('version_number')} saved to version history.")
            elif rewrite_draft_result.get('status') == 'unchanged':
                st.info(f"This DRAFT — Script Rewrite — V{rewrite_draft_result.get('version_number')} is already saved.")
            else:
                st.error('Current rewrite-stage draft could not be saved to version history.')
        try:
            final_doc = Document()
            final_style = final_doc.styles['Normal']
            final_font = final_style.font
            final_font.name = 'Times New Roman'
            final_font.size = Pt(12)
            final_export_text = strip_internal_notices(st.session_state.current_draft_output)
            for line in final_export_text.split('\n'):
                clean_line = line.strip()
                if clean_line:
                    if 'CHAPTER SCENE BEAT' in clean_line:
                        p = final_doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(18)
                        p.paragraph_format.space_after = Pt(6)
                        run = p.add_run(clean_line)
                        run.bold = True
                    elif not clean_line.startswith('='):
                        p = final_doc.add_paragraph(clean_line)
                        p.paragraph_format.space_after = Pt(12)
                        p.paragraph_format.line_spacing = 1.15
            final_buffer = BytesIO()
            final_doc.save(final_buffer)
            final_docx_bytes = final_buffer.getvalue()
            if st.session_state.get('demo_mode'):
                if st.button('Download Current Draft (.docx) 📥 🔒', key='trial_rewrite_manuscript_printout_notice', type='primary', use_container_width=True):
                    full_version_only_notice('Manuscript Printout')
            else:
                st.download_button(label='Download Current Draft (.docx) 📥', data=final_docx_bytes, file_name='manuscript_current_draft.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', type='primary', use_container_width=True)
        except Exception as e:
            st.error(f'Failed to generate revised Word document: {e}')
