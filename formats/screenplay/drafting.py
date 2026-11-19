"""screenplay: drafting. Existing engine and widget contracts retained."""

def render(context):
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    ai_output_is_usable = context['ai_output_is_usable']
    build_series_context_text = context['build_series_context_text']
    count_words = context['count_words']
    create_bridge_adapter = context['create_bridge_adapter']
    datetime = context['datetime']
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_development_writing_tense = context['get_development_writing_tense']
    get_dialogue_development_packet = context['get_dialogue_development_packet']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_effective_format_type = context['get_effective_format_type']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    get_text_signature = context['get_text_signature']
    mark_demo_action_used = context['mark_demo_action_used']
    picture_book_allocations = context['picture_book_allocations']
    picture_book_target = context['picture_book_target']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_project_title_banner = context['render_project_title_banner']
    require_demo_action_available = context['require_demo_action_available']
    require_product_access = context['require_product_access']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    st = context['st']
    supabase = context['supabase']
    wbs_request_stage_change = context['wbs_request_stage_change']
    require_product_access('drafting')
    _wbs_novel_draft = False
    _wbs_unit = 'Scene Block'
    st.header('📄 Generating Your Creative Draft')
    st.caption('WBS is writing the approved story sections in sequence and preserving continuity. Each section is generated only once.')
    render_project_title_banner('step_4_creative_draft')
    st.caption(f'Dialogue Style: {get_dialogue_style_display()} — applied to every scene block. Project type controls how dialogue is written and formatted.')
    if 'current_draft_output' not in st.session_state:
        st.session_state.current_draft_output = ''
    if 'rolling_lore_book' not in st.session_state:
        st.session_state.rolling_lore_book = ''
    if 'current_processing_beat' not in st.session_state:
        st.session_state.current_processing_beat = 1
    plot_outline_text = st.session_state.get('plot_outline', '')

    def split_plot_outline_into_beats(outline_text):
        text = str(outline_text or '').strip()
        if not text:
            return []
        beat_pattern = re.compile('(?im)^\\s*\\[BEAT\\s+(\\d+)\\]\\s*$')
        matches = list(beat_pattern.finditer(text))
        if matches:
            beats = []
            for idx, match in enumerate(matches):
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                beat_block = text[match.start():end].strip()
                if beat_block:
                    beats.append(beat_block)
            return beats
        legacy_beats = [beat.strip() for beat in text.split('===') if beat.strip()]
        if len(legacy_beats) > 1:
            return legacy_beats
        plain_pattern = re.compile('(?im)^\\s*BEAT\\s+(\\d+)\\s*:?\\s*$')
        plain_matches = list(plain_pattern.finditer(text))
        if plain_matches:
            beats = []
            for idx, match in enumerate(plain_matches):
                end = plain_matches[idx + 1].start() if idx + 1 < len(plain_matches) else len(text)
                beat_block = text[match.start():end].strip()
                if beat_block:
                    beats.append(beat_block)
            return beats
        return [text]
    filtered_beats = split_plot_outline_into_beats(plot_outline_text)
    total_beats = len(filtered_beats)
    st.session_state.total_beats = total_beats
    if total_beats == 0:
        st.warning('No plot outline beats found. Return to Plot Architect and create an outline first.')
    else:
        if 'scene_blocks' not in st.session_state:
            st.session_state.scene_blocks = {}
        saved_scene_numbers = [int(scene_number) for scene_number, scene_text in st.session_state.scene_blocks.items() if str(scene_text or '').strip()]
        next_missing_scene = None
        for scene_number in range(1, total_beats + 1):
            if scene_number not in saved_scene_numbers:
                next_missing_scene = scene_number
                break
        if next_missing_scene is not None:
            st.session_state.current_processing_beat = next_missing_scene
        else:
            st.session_state.current_processing_beat = total_beats + 1
        recommended_scene_word_count = 1200
        audiobook_scene_instruction = ''
        if st.session_state.get('_wbs_last_draft_budget_notice'):
            st.info(st.session_state.pop('_wbs_last_draft_budget_notice'))
        with st.expander('✏️ Edit Saved Scene Beat / Manuscript', expanded=False):
            _existing_blocks = st.session_state.get('scene_blocks') or {}
            _scene_numbers = sorted((int(k) for k, v in _existing_blocks.items() if str(k).isdigit() and str(v or '').strip()))
            _labels = [f'Scene Beat {k}' for k in _scene_numbers]
            if str(st.session_state.get('current_draft_output') or '').strip():
                _labels.append('Full Manuscript')
            if not _labels:
                st.info('Load an existing manuscript or generate a scene first.')
            else:
                _chosen = st.selectbox('Select section to revise', _labels, key='wbs_scene_edit_choice')
                _beat_no = None if _chosen == 'Full Manuscript' else int(_chosen.rsplit(' ', 1)[-1])
                _old_text = str(st.session_state.get('current_draft_output') or '') if _beat_no is None else str(_existing_blocks.get(_beat_no, _existing_blocks.get(str(_beat_no), '')))
                _sig = get_text_signature(_old_text)[:12]
                _edited = st.text_area("Editable scene text — paste Quill's revision here", value=_old_text, height=320, key=f'wbs_scene_edit_{_beat_no}_{_sig}')
                if st.button('💾 Save This Version', key='wbs_scene_save_revision', type='primary', disabled=bool(st.session_state.get('demo_mode'))):
                    if not _edited.strip():
                        st.error('Empty text cannot be saved.')
                    elif _edited == _old_text:
                        st.info('No changes to save.')
                    else:
                        _old_draft = st.session_state.get('current_draft_output', '')
                        _old_blocks = dict(_existing_blocks)
                        _old_branch = st.session_state.get('project_version_name', 'Original')
                        if _beat_no is None:
                            st.session_state.current_draft_output = _edited
                            st.session_state.scene_blocks = {}
                        else:
                            st.session_state.scene_blocks[_beat_no] = _edited
                            st.session_state.current_draft_output = '\n\n'.join((str(v).strip() for k, v in sorted(st.session_state.scene_blocks.items(), key=lambda kv: int(kv[0])) if str(v or '').strip()))
                        _new_branch = f'Edited {datetime.now():%m-%d %H%M}'
                        try:
                            _result = save_current_project_session_to_supabase(version_name=_new_branch, save_as_new_version=True)
                            if not _result:
                                raise RuntimeError('Database save was not confirmed')
                        except Exception as _exc:
                            st.session_state.current_draft_output = _old_draft
                            st.session_state.scene_blocks = _old_blocks
                            st.session_state.project_version_name = _old_branch
                            st.error(f'Unable to save; previous content restored: {_exc}')
                        else:
                            st.success('Edited manuscript saved as a new version; previous version preserved.')
                            st.rerun()
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader('📄 Draft Output Canvas')
            latest_scene_number = max(1, int(st.session_state.get('current_processing_beat', 1) or 1) - 1)
            latest_scene_text = ''
            if isinstance(st.session_state.get('scene_blocks'), dict):
                latest_scene_text = st.session_state.scene_blocks.get(latest_scene_number, '')
            st.text_area('Latest Scene Output:', value=latest_scene_text or st.session_state.current_draft_output, height=500, label_visibility='collapsed', disabled=True)
            st.subheader('⚙️ Chapter / Scene Settings')
            chapter_title = st.text_input('Chapter / Scene Title:', value=f'{_wbs_unit} {st.session_state.current_processing_beat}', key=f'chapter_title_{st.session_state.current_processing_beat}')
            target_word_count = st.number_input('Target Word Count Per Scene Block:', min_value=50, max_value=2500, value=recommended_scene_word_count, step=25, key=f'target_word_count_{st.session_state.current_processing_beat}')
            pov_choice = st.selectbox('Point of View:', ['Third Person Limited', 'Third Person Omniscient', 'First Person'], key=f'pov_choice_{st.session_state.current_processing_beat}')
            _preview_index = int(st.session_state.current_processing_beat) - 1
            if 0 <= _preview_index < len(filtered_beats):
                _preview_beat = str(filtered_beats[_preview_index] or '')

                def _preview_field(label):
                    _match = re.search(f'(?ims)^\\s*\\[{label}\\]\\s*:\\s*(.*?)(?=^\\s*\\[[A-Z][^\\n]*\\]\\s*:|^\\s*\\[BEAT\\s+\\d+\\]|^\\s*===|\\Z)', _preview_beat)
                    return _match.group(1).strip() if _match else ''
                _preview_title = _preview_field('SCENE TITLE')
                _preview_goal = _preview_field('CORE OBJECTIVE')
                _preview_detail = _preview_field('SCENE DETAILS\\s*&\\s*CONFLICT') or _preview_field('SCENE DETAILS')
                st.markdown(f'**Upcoming Scene {_preview_index + 1} of {total_beats} — Story Plan**')
                if _preview_title:
                    st.markdown(f'**{_preview_title}**')
                if _preview_goal:
                    st.markdown(_preview_goal)
                if _preview_detail:
                    st.markdown(_preview_detail)
                if not (_preview_title or _preview_goal or _preview_detail):
                    st.caption("This scene's detailed plan is not available in the loaded outline.")
                st.caption('Read-only scene plan from Stage 3. The scene will be drafted from this outline; review wording after the draft is assembled.')
            st.markdown('---')
        _wbs_pb_fast_ready = False
        if st.session_state.current_processing_beat <= total_beats:
            current_scene_number = st.session_state.current_processing_beat
            if current_scene_number in st.session_state.scene_blocks and str(st.session_state.scene_blocks.get(current_scene_number, '')).strip():
                st.info(f'Scene Block {current_scene_number} is already written.')
                st.stop()
            _pending = st.session_state.get('_wbs_overbudget_scene')
            if isinstance(_pending, dict) and _pending.get('beat') == current_scene_number and False:
                _beat_limit = picture_book_allocations()[current_scene_number - 1]
                _book_remaining = max(0, picture_book_target() - count_words(st.session_state.current_draft_output))
                _effective_limit = min(_beat_limit, _book_remaining)
                st.warning(f'Scene {current_scene_number} needs shortening to {_effective_limit} words or fewer before it can be added.')
                _review = st.text_area('Edit generated scene to fit the word budget', value=str(_pending.get('text') or ''), height=300, key=f"wbs_overbudget_review_{current_scene_number}_{_pending['token']}")
                _review_count = count_words(_review)
                st.caption(f'Scene words: {_review_count} / {_effective_limit} allowed · {max(0, _review_count - _effective_limit)} words to remove')
                _accept, _discard = st.columns(2)
                with _accept:
                    if st.button('✅ Accept Edited Scene', key=f'wbs_accept_overbudget_{current_scene_number}', disabled=not 0 < _review_count <= _effective_limit, use_container_width=True):
                        if current_scene_number in st.session_state.scene_blocks:
                            st.warning('This scene was already added. The edit was not duplicated.')
                            st.stop()
                        _project_id = get_active_project_id()
                        if _project_id:
                            try:
                                supabase.table('writersblock_project_drafts').insert({'project_id': _project_id, 'user_id': get_current_user_id(), 'draft_title': f'{_wbs_unit} {current_scene_number}', 'draft_type': 'scene_draft', 'draft_content': _review, 'version_number': current_scene_number}).execute()
                            except Exception as _exc:
                                st.error(f'Scene could not be saved: {_exc}')
                                st.stop()
                        st.session_state.scene_blocks[current_scene_number] = _review
                        st.session_state.current_draft_output = '\n\n'.join((str(v).strip() for _, v in sorted(st.session_state.scene_blocks.items(), key=lambda kv: int(kv[0])) if str(v or '').strip()))
                        if _pending.get('lore'):
                            st.session_state.rolling_lore_book = _pending['lore']
                        mark_demo_action_used('draft_scene')
                        st.session_state.pop('_wbs_overbudget_scene', None)
                        _next = next((i for i in range(1, total_beats + 1) if not str(st.session_state.scene_blocks.get(i, '')).strip()), None)
                        if _next is None:
                            st.session_state.current_processing_beat = total_beats + 1
                            wbs_request_stage_change('Isolation Guardrail', export_view=False)
                        else:
                            st.session_state.current_processing_beat = _next
                        st.rerun()
                with _discard:
                    if st.button('Discard and Regenerate', key=f'wbs_discard_overbudget_{current_scene_number}', use_container_width=True):
                        st.session_state.pop('_wbs_overbudget_scene', None)
                        st.rerun()
                st.info('Your generated scene has not been added. Edit and accept it, or discard and regenerate.')
            btn_label = f'Execute {_wbs_unit} {current_scene_number} of {total_beats} ⚡'
            if st.button(f'Develop {_wbs_unit} {current_scene_number} — Writer Approval Required', key=f'wbs_manual_scene_{current_scene_number}', use_container_width=True):
                require_product_access('drafting')
                require_demo_action_available('draft_scene', current_scene_number)
                current_beat_data = filtered_beats[current_scene_number - 1]
                series_drafting_context = build_series_context_text(max_total_chars=18000, per_source_chars=8000)
                drafting_instruction_packet = f"\n{audiobook_scene_instruction}\nCHAPTER / SCENE SETTINGS:\nChapter / Scene Title: {chapter_title}\nTarget Word Count: Approximately {target_word_count} words\nPicture Book Word Budget (if applicable): {'Not applicable'}\nPoint of View: {pov_choice}\nTense (set in Development Setup; maintain consistently): {get_development_writing_tense()}\n\nDIALOGUE / NARRATION REQUIREMENT:\n{get_dialogue_development_packet()}\nApply this requirement to the current scene. Preserve the selected project type and its dialogue conventions.\n\nSERIES CONTINUITY REFERENCE:\n{series_drafting_context or 'This is a standalone book with no series reference package.'}\n\nPROJECT-WIDE CREATIVE CONTINUITY:\n{get_full_project_continuity_context()}\n\nCURRENT OUTLINE BEAT:\n{current_beat_data}\n\nIMPORTANT OUTPUT RULE:\nWrite ONLY this single scene block. Do not repeat earlier scenes. Do not summarize the full manuscript. Do not include manuscript output, prior scene text, headings, or any material outside this current scene block. End with a LORE UPDATE only if needed.\n"
                with st.spinner(f'Drafting scene block {current_scene_number}...'):
                    try:
                        if create_bridge_adapter is None:
                            st.error(f'WritersBlock Model is unavailable. {WBS_MODEL_IMPORT_ERROR}')
                            st.stop()
                        _wbs_draft_bridge = create_bridge_adapter(backend=st.session_state.backend)
                        _wbs_draft_result = _wbs_draft_bridge.execute('Continue drafting', st.session_state, prepared_context={'effective_format_type': get_effective_format_type(), 'dialogue_development_packet': get_dialogue_development_packet(), 'format_development_context': get_full_project_continuity_context(), 'quill_format_instructions': st.session_state.get('quill_format_instructions', ''), 'quill_template_context': refresh_quill_template_context()}, action_payload={'current_beat_text': drafting_instruction_packet, 'rolling_lore': st.session_state.rolling_lore_book, 'format_type': get_effective_format_type(), 'tone_style': st.session_state.tone_style, 'author_style': st.session_state.author_style})
                        if not _wbs_draft_result.success:
                            raise RuntimeError(_wbs_draft_result.error or 'WritersBlock Model Bridge returned no draft.')
                        raw_response = _wbs_draft_result.output
                        st.session_state['_wbs_agent_bridge_last_operation'] = _wbs_draft_result.backend_operation or ''
                        st.session_state['_wbs_agent_bridge_last_success'] = True
                    except Exception as e:
                        st.error(f'Drafting failed. No scene text was saved. Backend error: {e}')
                        st.stop()
                    if not ai_output_is_usable(raw_response):
                        st.error('Drafting failed. Gemini did not return usable scene text. No scene text was saved.')
                        st.stop()
                    lore_marker_match = re.search('===?\\s*LORE\\s+UPDATE\\s*===?', str(raw_response), re.IGNORECASE)
                    if lore_marker_match:
                        start_idx, end_idx = lore_marker_match.span()
                        narrative_text = str(raw_response)[:start_idx].strip()
                        new_lore = str(raw_response)[end_idx:].strip()
                    else:
                        narrative_text = str(raw_response).strip()
                        new_lore = st.session_state.rolling_lore_book if st.session_state.rolling_lore_book else '- Active context state synchronized.'
                    if narrative_text and False:
                        _suggested = picture_book_allocations()[current_scene_number - 1]
                        _scene_words = count_words(narrative_text)
                        if _scene_words > _suggested:
                            st.session_state['_wbs_last_draft_budget_notice'] = f'Scene {current_scene_number}: {_scene_words} words, above its suggested {_suggested}-word allocation. The scene was kept intact. Review total length in Stage 5 or rewrite in Stage 7.'
                    if narrative_text:
                        if 'scene_blocks' not in st.session_state:
                            st.session_state.scene_blocks = {}
                        if current_scene_number in st.session_state.scene_blocks:
                            st.warning(f'Scene Block {current_scene_number} was already written. It was not added twice.')
                            st.stop()
                        st.session_state.scene_blocks[current_scene_number] = narrative_text
                        ordered_scene_texts = []
                        for scene_idx in sorted(st.session_state.scene_blocks.keys()):
                            scene_text = str(st.session_state.scene_blocks.get(scene_idx) or '').strip()
                            if scene_text:
                                ordered_scene_texts.append(scene_text)
                        st.session_state.current_draft_output = '\n\n'.join(ordered_scene_texts)
                    if new_lore:
                        st.session_state.rolling_lore_book = new_lore
                    if narrative_text:
                        mark_demo_action_used('draft_scene')
                    active_project_id = get_active_project_id()
                    if active_project_id and narrative_text:
                        supabase.table('writersblock_project_drafts').insert({'project_id': active_project_id, 'user_id': get_current_user_id(), 'draft_title': f'{_wbs_unit} {current_scene_number}', 'draft_type': 'scene_draft', 'draft_content': narrative_text, 'version_number': current_scene_number}).execute()
                    saved_scene_numbers = [int(scene_number) for scene_number, scene_text in st.session_state.scene_blocks.items() if str(scene_text or '').strip()]
                    next_missing_scene = None
                    for scene_number in range(1, total_beats + 1):
                        if scene_number not in saved_scene_numbers:
                            next_missing_scene = scene_number
                            break
                    if next_missing_scene is None:
                        st.session_state.current_processing_beat = total_beats + 1
                        wbs_request_stage_change('Isolation Guardrail', export_view=False)
                    else:
                        st.session_state.current_processing_beat = next_missing_scene
                    st.rerun()
        with col_right:
            st.subheader('🧠 Rolling Lore Memory')
            st.text_area('Rolling Lore Memory:', value=st.session_state.rolling_lore_book, height=250, label_visibility='collapsed', disabled=True)
            st.markdown('---')
            saved_scene_count = len([scene_text for scene_text in st.session_state.scene_blocks.values() if str(scene_text or '').strip()])
            st.metric('Current Scene Beat', f'{saved_scene_count} / {total_beats}')
            st.markdown('---')
            for idx in range(1, total_beats + 1):
                scene_is_saved = idx in st.session_state.scene_blocks and str(st.session_state.scene_blocks.get(idx, '')).strip()
                if scene_is_saved:
                    st.markdown(f'✅ Scene Block {idx}: Written')
                elif idx == st.session_state.current_processing_beat:
                    st.markdown(f'🔷 Scene Block {idx}: Ready')
                else:
                    st.markdown(f'⚪ Scene Block {idx}: Pending')
