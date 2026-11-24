"""short_story: scene scripting. Existing engine and widget contracts retained."""

def render(context):
    DIALOGUE_STYLE_INSTRUCTIONS = context['DIALOGUE_STYLE_INSTRUCTIONS']
    DIALOGUE_STYLE_OPTIONS = context['DIALOGUE_STYLE_OPTIONS']
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    ai_output_is_usable = context['ai_output_is_usable']
    count_words = context['count_words']
    create_bridge_adapter = context['create_bridge_adapter']
    get_active_format_development_context = context['get_active_format_development_context']
    get_dialogue_development_packet = context['get_dialogue_development_packet']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_dialogue_style_instruction = context['get_dialogue_style_instruction']
    get_effective_format_type = context['get_effective_format_type']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    get_plot_dialogue_context = context['get_plot_dialogue_context']
    get_series_aware_story_seed = context['get_series_aware_story_seed']
    get_text_signature = context['get_text_signature']
    mark_demo_action_used = context['mark_demo_action_used']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_project_title_banner = context['render_project_title_banner']
    require_demo_action_available = context['require_demo_action_available']
    require_product_access = context['require_product_access']
    scene_blocks = context['scene_blocks']
    scene_manuscript = context['scene_manuscript']
    scene_outline_parts = context['scene_outline_parts']
    st = context['st']
    time = context['time']
    wbs_request_stage_change = context['wbs_request_stage_change']
    wbs_ss_capture_draft_on_selection_change = context['wbs_ss_capture_draft_on_selection_change']
    wbs_ss_revision_identity = context['wbs_ss_revision_identity']
    wbs_ss_safe_scene_draft = context['wbs_ss_safe_scene_draft']
    wbs_ss_save_scene_to_current_revision = context['wbs_ss_save_scene_to_current_revision']
    st.header('🏗️ Step 3: Scene Scripting')
    render_project_title_banner('step_3_plot_architecture')
    st.caption(f'Dialogue Style: {get_dialogue_style_display()} — carried forward from Concept Development. The selected project type controls dialogue formatting.')
    st.markdown(f'**Selected Direction:** `{st.session_state.chosen_option}`')
    st.markdown('---')
    if st.session_state.plot_outline is None:
        st.info('The selected Plot Architecture is ready. Generate its scene structure when you choose; scenes will not be scripted automatically.')
        if not st.button('Prepare Scene Structure', key='wbs_ss_explicit_outline', type='primary'):
            st.stop()
        require_product_access('plot')
        require_demo_action_available('plot')
        with st.spinner('Locking down scene beats and style directives...'):
            time.sleep(1)
            if create_bridge_adapter is None:
                st.error(f'WritersBlock Model is unavailable. {WBS_MODEL_IMPORT_ERROR}')
                st.stop()
            _wbs_plot_bridge = create_bridge_adapter(backend=st.session_state.backend)
            _wbs_short_story_plot = True
            _wbs_plot_length_guidance = 'SHORT STORY INITIAL PLOT ARCHITECTURE: Write FOUR scenes, with at least 250 words of actual story narrative in each scene (approximately 1,000 words total), staying below the 1,500-word short-story cap. Exclude titles, planning commentary, scene objectives and style directives from narrative word counts. Put planning directives in their dedicated metadata fields, never in scene prose. The author may shorten or lengthen scenes later.'
            _wbs_plot_result = _wbs_plot_bridge.execute('Generate plot outline', st.session_state, prepared_context={'series_aware_story_seed': get_series_aware_story_seed(), 'effective_format_type': get_effective_format_type(), 'format_development_context': get_full_project_continuity_context(), 'quill_format_instructions': st.session_state.get('quill_format_instructions', ''), 'quill_template_context': refresh_quill_template_context(), 'initial_scene_length_guidance': _wbs_plot_length_guidance}, action_payload={'initial_scene_length_guidance': _wbs_plot_length_guidance, 'chosen_option': st.session_state.chosen_option, 'chosen_option_text': get_plot_dialogue_context(), 'tone_style': st.session_state.tone_style, 'author_style': st.session_state.author_style})
            if not _wbs_plot_result.success:
                st.error('WritersBlock Model Bridge could not generate Plot Architecture. ' + (_wbs_plot_result.error or 'Unknown bridge error.'))
                st.stop()
            st.session_state.plot_outline = _wbs_plot_result.output
            st.session_state['_wbs_stage3_saved_outline_baseline'] = ''
            st.session_state['_wbs_stage3_unsaved_changes'] = True
            st.session_state['_wbs_agent_bridge_last_operation'] = _wbs_plot_result.backend_operation or ''
            st.session_state['_wbs_agent_bridge_last_success'] = True
            st.session_state.project_stage = 'Plot Architect'
            st.session_state.chosen_option = st.session_state.get('chosen_option')
            st.session_state.chosen_option_text = st.session_state.get('chosen_option_text')
            st.session_state['_wbs_agent_bridge_plot_stage_pinned'] = True
        if ai_output_is_usable(st.session_state.plot_outline):
            mark_demo_action_used('plot')
        if not ai_output_is_usable(st.session_state.get('plot_outline')):
            st.error('Plot generation did not produce a usable result. Return to Scripting and select a path again.')
            st.stop()

    def _wbs_reader_scene_text(raw):
        raw = str(raw or '').strip()
        raw = re.sub('(?is)(?:^|(?<=[.!?])\\s+)["“]?\\s*(?:Her|His|Their|The character\\\'s|The protagonist\\\'s)\\s+conflict\\s+is\\s+(?:purely|primarily|largely)\\s+(?:internal|external).*?(?:[.!?](?=\\s|$)|$)["”]?', ' ', raw)
        raw = re.sub('(?is)(?:^|(?<=[.!?])\\s+)(?:The scene (?:emphasizes|focuses on|is carried|will be|relies on|should|uses|highlights|establishes)|Narration (?:carries|highlights|focuses|will|should|describes)|The narration (?:carries|highlights|focuses|will|should|describes)|This (?:beat|scene) (?:emphasizes|focuses|should|uses|is designed)|(?:Use|Maintain|Employ|Apply|Analyze and apply) (?:active syntax|descriptive|style syntax|narration|dialogue)).*?(?:[.!?](?=\\s|$)|$)', ' ', raw)
        return re.sub('[ \\t]{2,}', ' ', raw).strip()

    def _wbs_display_paragraphs(raw):
        """Presentation-only paragraph layout; never mutates the saved manuscript.

        Existing author paragraph breaks are authoritative. For a single long
        prose block, group sentences into readable paragraphs without changing
        the words or punctuation. This is a visual aid, not semantic editing.
        """
        raw = str(raw or '').strip()
        if not raw:
            return []
        original_paragraphs = re.split('\\n\\s*\\n', raw)
        output = []
        for paragraph in original_paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if '\n' in paragraph or len(paragraph.split()) < 105:
                output.append(paragraph)
                continue
            sentences = re.split('(?<=[.!?])\\s+(?=[A-Z“\\"])', paragraph)
            if len(sentences) < 4:
                output.append(paragraph)
                continue
            group, count = ([], 0)
            for sentence in sentences:
                group.append(sentence)
                count += len(sentence.split())
                if count >= 65 and len(group) >= 2:
                    output.append(' '.join(group))
                    group, count = ([], 0)
            if group:
                if output and count < 22 and (len(original_paragraphs) == 1):
                    output[-1] += ' ' + ' '.join(group)
                else:
                    output.append(' '.join(group))
        return output

    def _wbs_reader_outline_preview(raw):
        beats = re.split('(?im)^\\s*\\[BEAT\\s+\\d+\\]\\s*', str(raw or ''))
        displayed = []
        for section in beats:
            title = re.search('(?is)\\[SCENE TITLE\\]\\s*:\\s*(.*?)(?=\\[[A-Z][A-Z\\s&0-9]*\\]\\s*:|$)', section)
            scene = re.search('(?is)\\[(?:SCENE DETAILS(?:\\s*&\\s*CONFLICT)?|SCENE\\s*\\d*)\\]\\s*:\\s*(.*?)(?=\\[[A-Z][A-Z\\s&0-9]*\\]\\s*:|$)', section)
            if scene:
                prose = _wbs_reader_scene_text(scene.group(1))
                if prose:
                    displayed.append((title.group(1).strip() + '\n\n' if title else '') + prose)
        return '\n\n'.join(displayed)
    _ss_parts = scene_outline_parts(st.session_state.get('plot_outline') or '')
    _ss_identity = wbs_ss_revision_identity()
    if st.session_state.get('_wbs_ss_editor_identity') != _ss_identity:
        for _key in ('_wbs_ss_edit_buffers', '_wbs_ss_selected', '_wbs_ss_previous_selection', '_wbs_ss_editor_widget_key', '_wbs_ss_db_scene_baseline', '_wbs_ss_rewrite_preview', '_wbs_ss_last_configs'):
            st.session_state.pop(_key, None)
        st.session_state['_wbs_ss_editor_identity'] = _ss_identity
        st.session_state['_wbs_ss_initial_loaded_blocks'] = scene_blocks(st.session_state.get('scene_blocks') or {})
    _ss_blocks = scene_blocks(st.session_state.get('scene_blocks') or {})
    _ss_seed_one = _wbs_reader_scene_text(_ss_parts.get(1, ('', '', ''))[1])
    if 1 not in _ss_blocks and (not _ss_seed_one):
        st.warning('Scene 1 has no story text in this revision. Restore its original storyline before continuing.')
        st.stop()
    _ss_available = sorted(set(_ss_blocks) | {1})
    _ss_pending_jump = st.session_state.pop('_wbs_ss_jump_to', None)
    if _ss_pending_jump in _ss_available:
        st.session_state['_wbs_ss_selected'] = _ss_pending_jump
    _ss_selected_default = st.session_state.get('_wbs_ss_selected')
    if _ss_selected_default not in _ss_available:
        st.session_state['_wbs_ss_selected'] = _ss_available[0]
    st.markdown('### Scene Scripting — Four Scenes')
    st.caption('Open written scenes in any order. Navigation does not save, generate, or create another V-number.')
    st.markdown('#### Choose an existing scene')
    _ss_selected = st.selectbox('Choose an existing scene', _ss_available, key='_wbs_ss_selected', format_func=lambda n: f"Scene {n} — {_ss_parts.get(n, (f'Scene {n}', '', ''))[0]}", on_change=wbs_ss_capture_draft_on_selection_change, label_visibility='collapsed')
    _ss_title = _ss_parts.get(_ss_selected, (f'Scene {_ss_selected}', '', ''))[0]
    _ss_original = _ss_blocks.get(_ss_selected, _ss_seed_one if _ss_selected == 1 else '')
    _ss_buffer = dict(st.session_state.get('_wbs_ss_edit_buffers') or {})
    _ss_widget_key = f'wbs_ss_text_{_ss_identity[0]}_{_ss_identity[1]}_{_ss_selected}_{get_text_signature(_ss_original)[:12]}'
    _ss_pending_accept = st.session_state.pop('_wbs_ss_pending_accept', None)
    if isinstance(_ss_pending_accept, (tuple, list)) and len(_ss_pending_accept) == 2 and (_ss_pending_accept[0] == _ss_selected):
        _ss_buffer[_ss_selected] = _ss_pending_accept[1]
        st.session_state[_ss_widget_key] = _ss_pending_accept[1]
        st.session_state['_wbs_ss_edit_buffers'] = _ss_buffer
    _ss_buffer[_ss_selected] = wbs_ss_safe_scene_draft(_ss_buffer.get(_ss_selected), _ss_original)
    st.session_state[_ss_widget_key] = wbs_ss_safe_scene_draft(st.session_state.get(_ss_widget_key, _ss_buffer[_ss_selected]), _ss_buffer[_ss_selected])
    st.session_state['_wbs_ss_edit_buffers'] = _ss_buffer
    st.session_state['_wbs_ss_previous_selection'] = _ss_selected
    st.session_state['_wbs_ss_editor_widget_key'] = _ss_widget_key
    _ss_working = str(st.session_state.get(_ss_widget_key, _ss_original) or '')
    _ss_changed = _ss_working != _ss_original
    _ss_left, _ss_right = st.columns([1.15, 1], gap='large')
    with _ss_left:
        st.subheader(f'Scene {_ss_selected} — {_ss_title}')
        if _ss_changed:
            st.caption(f'Edited working scene · {count_words(_ss_working):,} words · Not yet saved')
        elif _ss_selected in _ss_blocks:
            st.caption(f'Saved working scene · {count_words(_ss_working):,} words')
        else:
            st.caption('Original story from the selected plot — save before advancing')
        for _p in _wbs_display_paragraphs(_ss_working):
            if _p.strip():
                st.write(_p)
    with _ss_right:
        st.markdown('#### Script Rewrite Controls')
        _ss_mode = st.selectbox('Rewrite Mode', ['Creative Script Rewrite / Improve Scene', 'Polish Only / Do Not Change Story'], key=f'wbs_ss_rewrite_mode_{_ss_selected}')
        _ss_length = st.selectbox('Target Length', ['Keep Current Length', 'Condense for Tighter Pacing', 'Custom Word Count'], key=f'wbs_ss_rewrite_length_{_ss_selected}')
        _ss_custom_words = None
        if _ss_length == 'Custom Word Count':
            _ss_custom_words = st.number_input('Target words', min_value=50, max_value=2500, value=max(50, min(2500, count_words(_ss_working) or 250)), step=25, key=f'wbs_ss_rewrite_custom_words_{_ss_selected}')
        _ss_dialogue = st.selectbox('Dialogue Style for Rewrite', ['Use Current Project Dialogue Style', *DIALOGUE_STYLE_OPTIONS], key=f'wbs_ss_rewrite_dialogue_{_ss_selected}')
        _ss_exact = st.checkbox('Direct Script Change / Obey My Instructions Exactly', key=f'wbs_ss_direct_{_ss_selected}', help='Apply only the requested changes, without creative additions.')
        _ss_rewrite_direction = st.text_area('Specific Rewrite Direction (optional)', key=f'wbs_ss_rewrite_direction_{_ss_selected}', height=130, placeholder='Describe the change you want to this scene.')
        _ss_control_values = (_ss_mode, _ss_length, _ss_custom_words, _ss_dialogue, _ss_exact)
        _ss_config_key = (str(_ss_identity), _ss_selected)
        _ss_previous_configs = dict(st.session_state.get('_wbs_ss_last_configs') or {})
        _ss_previous_config = _ss_previous_configs.get(str(_ss_config_key))
        _ss_dropdown_changed = _ss_previous_config is not None and tuple(_ss_previous_config) != _ss_control_values
        _ss_previous_configs[str(_ss_config_key)] = _ss_control_values
        st.session_state['_wbs_ss_last_configs'] = _ss_previous_configs
        _ss_request_signature = get_text_signature(repr((_ss_selected, _ss_working, _ss_control_values, _ss_rewrite_direction)))
        _ss_preview_clicked = st.button('Preview Rewritten Storyline', key=f'wbs_ss_preview_{_ss_selected}', use_container_width=True)
        _ss_previous_proposal = st.session_state.get('_wbs_ss_rewrite_preview')
        _ss_rewrite_again = False
        if isinstance(_ss_previous_proposal, (tuple, list)) and len(_ss_previous_proposal) == 4 and (_ss_previous_proposal[0] == _ss_selected) and (_ss_previous_proposal[3] == _ss_request_signature):
            st.markdown('##### Preview Rewritten Storyline')
            st.text_area('Proposed scene — review before accepting', value=_ss_previous_proposal[2], disabled=True, height=230, key=f'wbs_ss_proposal_read_{_ss_selected}_{get_text_signature(_ss_previous_proposal[2])[:14]}')
            _ss_accept_col, _ss_again_col = st.columns(2)
            with _ss_accept_col:
                if st.button('✓ Accept Rewrite', key=f'wbs_ss_accept_{_ss_selected}', type='primary', use_container_width=True):
                    if _ss_working != _ss_previous_proposal[1]:
                        st.error('The original scene changed; generate another preview before accepting.')
                    else:
                        st.session_state['_wbs_ss_pending_accept'] = (_ss_selected, _ss_previous_proposal[2])
                        st.session_state.pop('_wbs_ss_rewrite_preview', None)
                        st.rerun()
            with _ss_again_col:
                _ss_rewrite_again = st.button('↻ Rewrite Again', key=f'wbs_ss_again_{_ss_selected}', use_container_width=True)
        elif _ss_previous_proposal and _ss_previous_proposal[0] == _ss_selected:
            st.session_state.pop('_wbs_ss_rewrite_preview', None)
        if _ss_dropdown_changed or _ss_preview_clicked or _ss_rewrite_again:
            _backend = st.session_state.get('backend')
            _client = getattr(_backend, 'client', None)
            _model = getattr(_backend, 'model_name', None)
            if not _ss_working.strip():
                st.error('This scene has no story text to revise.')
            elif _ss_exact and (not _ss_rewrite_direction.strip()):
                st.error('Describe the exact change before requesting a rewrite.')
            elif not _client or not _model:
                st.error('The writing service is unavailable. Your existing scene was not changed.')
            else:
                try:
                    _ss_dialogue_rule = get_dialogue_style_instruction() if _ss_dialogue == 'Use Current Project Dialogue Style' else DIALOGUE_STYLE_INSTRUCTIONS.get(_ss_dialogue, _ss_dialogue)
                    _ss_target = f'Target approximately {_ss_custom_words} words.' if _ss_custom_words else _ss_length + '.'
                    _ss_directive = "Follow the writer's change instructions EXACTLY. Do not add creative changes or alter unrelated passages. " if _ss_exact else 'Revise this scene according to the selected rewrite mode. '
                    _ss_prompt = 'You are rewriting ONLY ONE scene of an existing FOUR-scene short story. ' + _ss_directive + f"Return ONLY finished narrative prose. No titles, scene numbers, meta-commentary, objectives, formatting tags, or writing directions. Preserve voice, characters, tense, plot continuity, and key events unless the writer explicitly requests otherwise. Mode: {_ss_mode}. Length: {_ss_target} Dialogue: {_ss_dialogue_rule}. Writer direction: {_ss_rewrite_direction or 'Improve the prose while preserving the story.'}\n\nSCENE {_ss_selected} ORIGINAL:\n{_ss_working}"
                    with st.spinner('Preparing rewrite preview...'):
                        _ss_res = _client.models.generate_content(model=_model, contents=_ss_prompt)
                    _ss_proposed = str(getattr(_ss_res, 'text', '') or '').strip()
                    if not _ss_proposed or re.search('(?im)^\\s*\\[(BEAT|CORE OBJECTIVE|STYLE)', _ss_proposed):
                        raise ValueError('The writer did not return clean story prose')
                    st.session_state['_wbs_ss_rewrite_preview'] = (_ss_selected, _ss_working, _ss_proposed, _ss_request_signature)
                    st.rerun()
                except Exception as exc:
                    st.session_state.pop('_wbs_ss_rewrite_preview', None)
                    st.error(f'Rewrite unavailable: {exc}')
        with st.expander('Edit Scene Text Manually', expanded=False):
            _ss_manual_edit = st.text_area('Editable scene text', height=220, key=_ss_widget_key)
            st.caption(f'Working words: {count_words(_ss_manual_edit):,}')
            if st.button(f'Save Scene {_ss_selected} to Current Revision', key=f'wbs_ss_save_{_ss_selected}', use_container_width=True, disabled=bool(st.session_state.get('demo_mode'))):
                try:
                    wbs_ss_save_scene_to_current_revision(_ss_selected, _ss_manual_edit)
                except Exception as exc:
                    st.error(f'Scene was not saved: {exc}')
                else:
                    _ss_blocks[_ss_selected] = _ss_manual_edit
                    st.session_state.scene_blocks = _ss_blocks
                    if set(_ss_blocks) == {1, 2, 3, 4}:
                        st.session_state.current_draft_output = scene_manuscript(_ss_blocks)
                    _ss_buffer.pop(_ss_selected, None)
                    st.session_state['_wbs_ss_edit_buffers'] = _ss_buffer
                    st.session_state.pop('_wbs_ss_rewrite_preview', None)
                    if set(_ss_blocks) == {1, 2, 3, 4} and not any(str(v)!=str(_ss_blocks.get(int(n),'')) for n,v in _ss_buffer.items() if str(n) in ('1','2','3','4')):
                        wbs_request_stage_change('Isolation Guardrail', export_view=False)
                    st.rerun()
        if _ss_changed:
            st.caption('Accepted edits appear on the left. Save Scene or use the bottom button to save them to this revision.')
    _ss_next_missing = next((n for n in range(2, 5) if n not in _ss_blocks), None)
    if set(_ss_blocks) == {1, 2, 3, 4} and st.button('Approve And Save Completed Scenes',key='wbs_ss_save_stage',type='primary',use_container_width=True,disabled=bool(st.session_state.get('demo_mode'))):
        _stage_buffers=st.session_state.get('_wbs_ss_edit_buffers') or {}
        if _ss_changed or any(str(value)!=str(_ss_blocks.get(int(number),'')) for number,value in _stage_buffers.items() if str(number) in ('1','2','3','4')):
            st.warning('Save each edited scene before approving the completed manuscript.')
        elif context['save_current_project_session_to_supabase']():
            wbs_request_stage_change('Isolation Guardrail',export_view=False)
    _ss_destinations = [('scene', n) for n in sorted(set(_ss_blocks) | {1})]
    if _ss_next_missing is not None:
        _ss_destinations.append(('generate', _ss_next_missing))
    if set(_ss_blocks) == {1, 2, 3, 4}:
        _ss_destinations.append(('review', 4))

    def _ss_destination_label(value):
        if value is None:
            return 'Choose a scene or Editorial Review...'
        kind, number = value
        if kind == 'review':
            return 'Stage 4 — Editorial & Publisher Review'
        title = _ss_parts.get(number, (f'Scene {number}', '', ''))[0]
        if kind == 'generate':
            return f'Generate Scene {number} — {title}'
        return f'Scene {number} — {title}'
    _ss_destination = None
    _ss_continue_col, _ss_integrity_col = st.columns(2, gap='small')
    with _ss_continue_col:
        with st.popover(f'Save Scene {_ss_selected} And Continue To:', type='primary', use_container_width=True, disabled=bool(st.session_state.get('demo_mode')), help='Save this scene to the current revision, then open the chosen scene or Editorial Review.'):
            for _ss_kind, _ss_number in _ss_destinations:
                if st.button(_ss_destination_label((_ss_kind, _ss_number)), key=f'wbs_ss_go_{_ss_selected}_{_ss_kind}_{_ss_number}', use_container_width=True, disabled=bool(st.session_state.get('demo_mode'))):
                    _ss_destination = (_ss_kind, _ss_number)
    with _ss_integrity_col:
        _ss_integrity_clicked = st.button(f'Save Scene {_ss_selected} And Return To Integrity Report', key=f'wbs_ss_save_return_integrity_{_ss_selected}', type='primary', use_container_width=True, disabled=bool(st.session_state.get('demo_mode')))
    if _ss_destination is not None or _ss_integrity_clicked:
        _ss_final_text = wbs_ss_safe_scene_draft(st.session_state.get(_ss_widget_key), _ss_blocks.get(_ss_selected, _ss_seed_one if _ss_selected == 1 else ''))
        if not str(_ss_final_text or '').strip():
            st.error('This scene has no story text. Nothing was saved.')
        else:
            try:
                _ss_saved_baseline = st.session_state.get('_wbs_ss_db_scene_baseline')
                if _ss_saved_baseline is None:
                    _ss_saved_baseline = st.session_state.get('_wbs_ss_initial_loaded_blocks') or {}
                _ss_saved_baseline = scene_blocks(_ss_saved_baseline)
                _ss_needs_save = _ss_saved_baseline.get(_ss_selected) != _ss_final_text
                if _ss_needs_save:
                    wbs_ss_save_scene_to_current_revision(_ss_selected, _ss_final_text)
            except Exception as _ss_save_exc:
                st.error(f'Scene {_ss_selected} could not be saved: {_ss_save_exc}')
            else:
                _ss_blocks[_ss_selected] = _ss_final_text
                st.session_state.scene_blocks = _ss_blocks
                _ss_saved_buffers = dict(st.session_state.get('_wbs_ss_edit_buffers') or {})
                _ss_saved_buffers[_ss_selected] = _ss_final_text
                st.session_state['_wbs_ss_edit_buffers'] = _ss_saved_buffers
                if set(_ss_blocks) == {1, 2, 3, 4}:
                    st.session_state.current_draft_output = scene_manuscript(_ss_blocks)
                st.session_state.pop('_wbs_ss_rewrite_preview', None)
                if _ss_integrity_clicked or _ss_destination[0] == 'review':
                    st.session_state.pop('_wbs_ss_integrity_return_context', None)
                    st.session_state['_wbs_unlocked_saved_stage'] = max(int(st.session_state.get('_wbs_unlocked_saved_stage') or 1), 4)
                    wbs_request_stage_change('Isolation Guardrail', export_view=False)
                elif _ss_destination[0] == 'scene':
                    st.session_state['_wbs_ss_jump_to'] = _ss_destination[1]
                    st.rerun()
                elif _ss_destination[0] == 'generate':
                    _ss_target_scene = _ss_destination[1]
                    _ss_beat = _ss_parts.get(_ss_target_scene, ('', '', ''))[2]
                    if not _ss_beat:
                        st.error(f'Scene {_ss_target_scene} has no saved plot beat; no scene was generated.')
                    else:
                        _ss_backend = st.session_state.get('backend')
                        _ss_client = getattr(_ss_backend, 'client', None)
                        _ss_model = getattr(_ss_backend, 'model_name', None)
                        if not _ss_client or not _ss_model:
                            st.error('Writing service is unavailable; preceding scene was saved.')
                        else:
                            try:
                                require_product_access('drafting')
                                _ss_prompt = f'Write ONLY Scene {_ss_target_scene} of a FOUR-SCENE short story. Return ONLY complete, finished narrative prose in natural paragraphs. No tags, titles, writing directives, recap or explanations. Preserve characters, continuity, voice, dialogue style and tense. Do not repeat earlier scenes. Aim for 200–350 words unless the scene requires otherwise.\n\nDIALOGUE: {get_dialogue_development_packet()}\nDEVELOPMENT: {get_active_format_development_context()}\nSCENE PLAN (internal only):\n{_ss_beat}\n\nPRECEDING MANUSCRIPT:\n{scene_manuscript(_ss_blocks)}'
                                _ss_response = _ss_client.models.generate_content(model=_ss_model, contents=_ss_prompt)
                                _ss_text = str(getattr(_ss_response, 'text', '') or '').strip()
                                if not _ss_text or re.search('(?im)^\\s*\\[(BEAT|CORE OBJECTIVE|STYLE)', _ss_text):
                                    raise ValueError('The generator did not return clean scene prose')
                            except Exception as _ss_gen_exc:
                                st.error(f'Scene {_ss_target_scene} was not created: {_ss_gen_exc}')
                            else:
                                _ss_blocks[_ss_target_scene] = _ss_text
                                st.session_state.scene_blocks = _ss_blocks
                                _ss_next_buffers = dict(st.session_state.get('_wbs_ss_edit_buffers') or {})
                                _ss_next_buffers[_ss_target_scene] = _ss_text
                                st.session_state['_wbs_ss_edit_buffers'] = _ss_next_buffers
                                if set(_ss_blocks) == {1, 2, 3, 4}:
                                    st.session_state.current_draft_output = scene_manuscript(_ss_blocks)
                                st.session_state['_wbs_ss_jump_to'] = _ss_target_scene
                                st.success(f'Scene {_ss_target_scene} generated as working text. Review it before saving.')
                                st.rerun()
    st.stop()
