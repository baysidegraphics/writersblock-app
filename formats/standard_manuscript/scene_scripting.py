"""standard_manuscript: scene scripting. Existing engine and widget contracts retained."""

def render(context):
    DIALOGUE_STYLE_INSTRUCTIONS = context['DIALOGUE_STYLE_INSTRUCTIONS']
    DIALOGUE_STYLE_OPTIONS = context['DIALOGUE_STYLE_OPTIONS']
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    ai_output_is_usable = context['ai_output_is_usable']
    create_bridge_adapter = context['create_bridge_adapter']
    full_version_only_notice = context['full_version_only_notice']
    get_active_format_development_context = context['get_active_format_development_context']
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_dialogue_style_instruction = context['get_dialogue_style_instruction']
    get_effective_format_type = context['get_effective_format_type']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    get_plot_dialogue_context = context['get_plot_dialogue_context']
    get_series_aware_story_seed = context['get_series_aware_story_seed']
    get_text_signature = context['get_text_signature']
    json = context['json']
    mark_demo_action_used = context['mark_demo_action_used']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_project_title_banner = context['render_project_title_banner']
    require_demo_action_available = context['require_demo_action_available']
    require_product_access = context['require_product_access']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    set_loaded_concept_version_baseline = context['set_loaded_concept_version_baseline']
    st = context['st']
    supabase = context['supabase']
    time = context['time']
    wbs_request_stage_change = context['wbs_request_stage_change']
    wbs_save_state_signature = context['wbs_save_state_signature']
    st.header('🏗️ Step 3: Scene Scripting')
    render_project_title_banner('step_3_plot_architecture')
    st.caption(f'Dialogue Style: {get_dialogue_style_display()} — carried forward from Concept Development. The selected project type controls dialogue formatting.')
    st.markdown(f'**Selected Direction:** `{st.session_state.chosen_option}`')
    st.markdown('---')
    if st.session_state.plot_outline is None:
        require_product_access('plot')
        require_demo_action_available('plot')
        with st.spinner('Locking down scene beats and style directives...'):
            time.sleep(1)
            if create_bridge_adapter is None:
                st.error(f'WritersBlock Model is unavailable. {WBS_MODEL_IMPORT_ERROR}')
                st.stop()
            _wbs_plot_bridge = create_bridge_adapter(backend=st.session_state.backend)
            _wbs_short_story_plot = False
            _wbs_plot_length_guidance = ''
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
    _outline_now = str(st.session_state.get('plot_outline') or '').strip()
    _beat_pattern = '(?im)^\\s*\\[BEAT\\s+(\\d+)\\]'
    _beat_matches = list(re.finditer(_beat_pattern, _outline_now))
    _beat_sections = {}
    for _idx, _hit in enumerate(_beat_matches):
        _section_end = _beat_matches[_idx + 1].start() if _idx + 1 < len(_beat_matches) else len(_outline_now)
        _beat_sections[_hit.group(1)] = _outline_now[_hit.start():_section_end].strip()
    _beat_numbers = list(_beat_sections)
    _locations = [f'Scene Beat {_num}' for _num in _beat_numbers] + ['Full Storyline']
    _source_col, _edit_col = st.columns([1.15, 1], gap='large')
    with _edit_col:
        st.subheader('Edit / Rewrite Storyline')
        _location = st.selectbox('Choose scene / beat to edit', _locations, key='_wbs_stage3_rewrite_location')
    _selected_number = re.search('\\d+', _location).group() if _location != 'Full Storyline' else ''
    _selected_outline = _beat_sections.get(_selected_number, '') if _selected_number else _outline_now
    _edit_signature = get_text_signature(_selected_outline) + '|' + _location
    if st.session_state.get('_wbs_stage3_edit_signature') != _edit_signature:
        st.session_state['_wbs_stage3_edit_source'] = _selected_outline
        st.session_state['_wbs_stage3_edit_signature'] = _edit_signature
    _visible_blocks = st.session_state.get('scene_blocks') or {}
    _visible_beat = int(_selected_number) if _selected_number else None
    _visible_draft = str(_visible_blocks.get(_visible_beat, _visible_blocks.get(str(_visible_beat), '')) or '').strip() if _visible_beat is not None and isinstance(_visible_blocks, dict) else ''
    _visible_draft = _visible_draft if str(st.session_state.get('current_draft_output') or '').strip() else ''
    with _source_col:
        st.subheader(f'Beat {_selected_number} — Scene {_selected_number}' if _selected_number else 'Full Storyline')
        if not _selected_outline:
            st.info('No scene content is available yet.')
        elif _visible_draft:
            st.caption('Current working manuscript scene')
            for _paragraph in _wbs_display_paragraphs(_wbs_reader_scene_text(_visible_draft)):
                if _paragraph.strip():
                    st.write(_paragraph.strip())
        elif _selected_number:
            _title_match = re.search('\\[SCENE TITLE\\]\\s*:\\s*', _selected_outline, flags=re.I)
            _scene_match = re.search('\\[(?:SCENE DETAILS(?:\\s*&\\s*CONFLICT)?|SCENE\\s*\\d*)\\]\\s*:\\s*', _selected_outline, flags=re.I)
            _next_header = re.compile('\\[(?:BEAT\\s*\\d+|SCENE TITLE|CORE OBJECTIVE|SCENE DETAILS(?:\\s*&\\s*CONFLICT)?|SCENE\\s*\\d*|THE\\s+CONFLICT|STYLE\\s*&\\s*SYNTAX DIRECTIVE)\\]', re.I)
            if _title_match:
                _tail = _selected_outline[_title_match.end():]
                _next = _next_header.search(_tail)
                _title = _tail[:_next.start() if _next else len(_tail)].strip().strip('=').strip()
                if _title:
                    st.markdown(f'**{_title}**')
            if _scene_match:
                _tail = _selected_outline[_scene_match.end():]
                _next = _next_header.search(_tail)
                _raw_scene_text = _tail[:_next.start() if _next else len(_tail)].strip().strip('=').strip()
                _scene_text = _wbs_reader_scene_text(_raw_scene_text)
                if _scene_text:
                    st.markdown('**Scene**')
                    for _paragraph in _wbs_display_paragraphs(_scene_text):
                        if _paragraph.strip():
                            st.write(_paragraph.strip())
            elif not _title_match:
                st.info('Scene text is unavailable for this beat.')
        else:
            st.caption('Select an individual beat to read its scene.')
    with _edit_col:
        st.markdown('#### Script Rewrite Controls')
        _mode = st.selectbox('Rewrite Mode', ['Creative Script Rewrite / Improve Scene', 'Polish Only / Do Not Change Story'], key='_wbs_stage3_rewrite_mode')
        _length = st.selectbox('Target Length', ['Keep Current Length', 'Condense for Tighter Pacing', 'Custom Word Count'], key='_wbs_stage3_rewrite_length')
        _custom_words = None
        if _length == 'Custom Word Count':
            _custom_words = st.number_input('Target words', 50, 2500, 400, 25, key='_wbs_stage3_rewrite_custom_words')
        _dialogue = st.selectbox('Dialogue Style for Rewrite', ['Use Current Project Dialogue Style', *DIALOGUE_STYLE_OPTIONS], key='_wbs_stage3_rewrite_dialogue')
        _exact_script_change = st.checkbox('Direct Script Change / Obey My Instructions Exactly', key='_wbs_stage3_direct_script_change', help='Use the text below as an exact replacement rather than a creative rewrite.')
        if _exact_script_change:
            _mode = 'Direct Script Change / Obey My Instructions Exactly'
        rewrite_direction = st.text_area('Replacement Text' if _exact_script_change else 'Specific Rewrite Direction (optional)', key='_wbs_stage3_rewrite_direction', height=130, placeholder='Paste replacement text for the selected scene.' if _exact_script_change else 'Describe changes to the selected beat or entire storyline.')
        _draft_blocks = st.session_state.get('scene_blocks') or {}
        _draft_beat_num = int(_selected_number) if _selected_number else None
        _draft_scene = str(_draft_blocks.get(_draft_beat_num, _draft_blocks.get(str(_draft_beat_num), '')) or '').strip() if _draft_beat_num is not None and isinstance(_draft_blocks, dict) else ''
        _rewrite_existing_draft = bool(_draft_scene and str(st.session_state.get('current_draft_output') or '').strip())
        if _rewrite_existing_draft:
            st.caption('Editing the existing manuscript scene. Accept Rewrite will replace this scene in the working draft.')
        if st.button('Preview Rewritten Storyline', key='_wbs_stage3_rewrite_preview_button', use_container_width=True):
            backend = st.session_state.get('backend')
            client = getattr(backend, 'client', None)
            model = getattr(backend, 'model_name', None)
            if client is None or not model or (not _selected_outline):
                st.error('The source storyline or writing service is unavailable. No changes were made.')
            else:
                _target = f'Aim for about {_custom_words} words.' if _custom_words else _length
                _dialogue_rule = get_dialogue_style_instruction() if _dialogue == 'Use Current Project Dialogue Style' else DIALOGUE_STYLE_INSTRUCTIONS.get(_dialogue, _dialogue)
                _instruction = f"Revise the supplied STORY OUTLINE only, not finished manuscript prose. Return only the complete revised selected outline. Keep every original [BEAT N] heading, [SCENE TITLE], [CORE OBJECTIVE], [SCENE DETAILS & CONFLICT] and [STYLE & SYNTAX DIRECTIVE] so later generation works. Preserve the writer's format, characters, continuity, voice, and development tense. In SCENE DETAILS & CONFLICT write story events only. NEVER add commentary about the scene, narration, objectives, pacing, syntax or writing technique to story text. Put all such instructions solely in CORE OBJECTIVE or STYLE & SYNTAX DIRECTIVE. Mode: {_mode}. Target length: {_target}. Dialogue: {_dialogue_rule}. Development: {get_active_format_development_context()}. Writer's direction: {rewrite_direction or 'Improve selected outline.'}\n\nSOURCE OUTLINE:\n{_selected_outline}"
                if _rewrite_existing_draft:
                    _instruction = f"Rewrite the following FINISHED MANUSCRIPT SCENE according to the writer's instructions. Return only replacement story prose, no headers, beat markers, meta commentary, writing instructions or explanation. Preserve story continuity, characters, format, voice and existing scene length unless requested otherwise. Mode: {_mode}. Target length: {_target}. Dialogue: {_dialogue_rule}. Writer's direction: {rewrite_direction or 'Improve this scene.'}\n\nEXISTING MANUSCRIPT SCENE:\n{_draft_scene}"
                _scene_word_rewrite = bool(_selected_number and _custom_words and (not _rewrite_existing_draft) and False)
                try:
                    _response = client.models.generate_content(model=model, contents=_instruction)
                    _preview = str(getattr(_response, 'text', '') or '').strip()
                    if _rewrite_existing_draft:
                        _valid = bool(_preview) and (not re.search('(?im)^\\s*\\[(?:BEAT|CORE OBJECTIVE|STYLE\\s*&\\s*SYNTAX DIRECTIVE)', _preview))
                    else:
                        _old_ids = re.findall(_beat_pattern, _selected_outline)
                        _new_ids = re.findall(_beat_pattern, _preview)
                        _tags = ('[SCENE TITLE]', '[CORE OBJECTIVE]', '[SCENE DETAILS & CONFLICT]', '[STYLE & SYNTAX DIRECTIVE]')
                        _valid = bool(_preview) and _old_ids == _new_ids and (not any((_preview.upper().count(tag) != len(_old_ids) for tag in _tags)))
                    if not _valid:
                        st.error('The rewrite did not preserve the required scene format. Original retained.')
                    else:
                        st.session_state['_wbs_stage3_rewrite_preview'] = _preview
                        st.session_state['_wbs_stage3_rewrite_origin'] = get_text_signature(_outline_now)
                        st.session_state['_wbs_stage3_rewrite_target'] = _location
                        st.session_state['_wbs_stage3_rewrite_draft_beat'] = _draft_beat_num if _rewrite_existing_draft else None
                        st.session_state['_wbs_stage3_rewrite_draft_signature'] = get_text_signature(_draft_scene) if _rewrite_existing_draft else ''
                except Exception as exc:
                    st.error(f'Rewrite could not be completed: {exc}')
        _preview = str(st.session_state.get('_wbs_stage3_rewrite_preview') or '').strip()
        if _preview:
            st.text_area('Review proposed rewrite before approval', value=_preview if st.session_state.get('_wbs_stage3_rewrite_draft_beat') is not None else _wbs_reader_outline_preview(_preview), height=240, disabled=True, key='_wbs_stage3_rewrite_display')
            _accept, _discard = st.columns(2)
            with _accept:
                if st.button('Accept Rewrite', key='_wbs_stage3_accept_rewritten_outline', use_container_width=True):
                    _original = str(st.session_state.get('plot_outline') or '')
                    if st.session_state.get('_wbs_stage3_rewrite_origin') != get_text_signature(_original):
                        st.error('Source changed. Generate another preview first.')
                    elif st.session_state.get('_wbs_stage3_rewrite_draft_beat') is not None:
                        _n = int(st.session_state['_wbs_stage3_rewrite_draft_beat'])
                        _blocks = st.session_state.get('scene_blocks') or {}
                        _old_scene = str(_blocks.get(_n, _blocks.get(str(_n), '')) or '').strip()
                        if get_text_signature(_old_scene) != st.session_state.get('_wbs_stage3_rewrite_draft_signature'):
                            st.error('The manuscript scene changed. Generate another preview before accepting.')
                        elif _preview != _old_scene:
                            _blocks[_n] = _preview
                            _blocks.pop(str(_n), None)
                            st.session_state.scene_blocks = _blocks
                            st.session_state.current_draft_output = '\n\n'.join((str(_blocks[k]).strip() for k in sorted(_blocks, key=lambda v: int(v)) if str(_blocks[k] or '').strip()))
                            st.session_state['_wbs_stage3_manuscript_rewrite_notice'] = f'Scene {_n} rewrite applied to working manuscript. Save when ready.'
                            for _key in ('_wbs_stage3_rewrite_preview', '_wbs_stage3_rewrite_origin', '_wbs_stage3_rewrite_target', '_wbs_stage3_rewrite_draft_beat', '_wbs_stage3_rewrite_draft_signature'):
                                st.session_state.pop(_key, None)
                            st.rerun()
                    else:
                        _target = st.session_state.get('_wbs_stage3_rewrite_target') or ''
                        if _target == 'Full Storyline':
                            _new_outline = _preview
                        else:
                            _num = re.search('\\d+', _target).group()
                            _match = re.search(f'(?ims)^\\s*\\[BEAT\\s+{_num}\\].*?(?=^\\s*\\[BEAT\\s+\\d+\\]|\\Z)', _original)
                            _new_outline = _original[:_match.start()] + _preview + '\n' + _original[_match.end():] if _match else ''
                        if _new_outline:
                            st.session_state.plot_outline = _new_outline
                            st.session_state['_wbs_stage3_unsaved_changes'] = True
                            for _key in ('_wbs_stage3_rewrite_preview', '_wbs_stage3_rewrite_origin', '_wbs_stage3_rewrite_target', '_wbs_stage3_rewrite_draft_beat', '_wbs_stage3_rewrite_draft_signature'):
                                st.session_state.pop(_key, None)
                            st.rerun()
            with _discard:
                if st.button('Discard', key='_wbs_stage3_discard_rewrite', use_container_width=True):
                    for _key in ('_wbs_stage3_rewrite_preview', '_wbs_stage3_rewrite_origin', '_wbs_stage3_rewrite_target', '_wbs_stage3_rewrite_draft_beat', '_wbs_stage3_rewrite_draft_signature'):
                        st.session_state.pop(_key, None)
                    st.rerun()
    if st.session_state.get('_wbs_stage3_manuscript_rewrite_notice'):
        st.success(st.session_state.pop('_wbs_stage3_manuscript_rewrite_notice'))
    _preview_scene_blocks = st.session_state.get('scene_blocks') or {}
    _preview_scenes = []
    if isinstance(_preview_scene_blocks, dict):
        for _scene_key, _scene_value in sorted(_preview_scene_blocks.items(), key=lambda kv: int(kv[0])):
            _scene_text = str(_scene_value or '').strip()
            if _scene_text:
                _preview_scenes.append((int(_scene_key), _scene_text))
    if _preview_scenes:
        st.markdown('---')
        st.subheader('Final Working Manuscript Preview')
        st.caption('Review all scenes together before saving Plot Architecture. This preview uses the accepted working manuscript; no AI generation.')
        _preview_complete_text = '\n\n'.join((_text for _, _text in _preview_scenes))
        for _scene_id, _scene_text in _preview_scenes:
            st.markdown(f'**Scene {_scene_id}**')
            for _paragraph in _wbs_display_paragraphs(_scene_text):
                if _paragraph.strip():
                    st.write(_paragraph.strip())
        _original_full_draft = str(st.session_state.get('current_draft_output') or '').strip()
        if _original_full_draft != _preview_complete_text:
            st.warning('The working manuscript and scene list do not match. Saving is blocked to avoid losing accepted edits.')
        elif st.button('💾 Save Working Manuscript to Current Revision', key='_wbs_stage3_save_existing_revision', use_container_width=True, disabled=bool(st.session_state.get('demo_mode'))):
            _row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '').strip()
            _project_id = get_active_project_id()
            _user_id = get_current_user_id()
            if not _row_id or not _project_id or (not _user_id):
                st.error('Cannot identify the exact current saved revision. No record changed.')
            else:
                try:
                    _query = supabase.table('writersblock_project_drafts').select('id, draft_content').eq('id', _row_id).eq('project_id', _project_id).eq('user_id', _user_id).eq('draft_type', 'project_session').limit(1).execute()
                    _rows = getattr(_query, 'data', None) or []
                    if not _rows:
                        st.error('The selected saved revision was not found. No record changed.')
                    else:
                        _snapshot = json.loads(_rows[0].get('draft_content') or '{}')
                        if not isinstance(_snapshot, dict):
                            raise ValueError('The existing revision data is invalid')
                        _previous_text = str(_snapshot.get('current_draft_output') or '').strip()
                        _previous_blocks = _snapshot.get('scene_blocks') or {}
                        _new_blocks = {str(_n): _text for _n, _text in _preview_scenes}
                        if _previous_text == _preview_complete_text and _previous_blocks == _new_blocks:
                            st.info('Current revision already contains these scenes. No changes or new version created.')
                        else:
                            _snapshot['current_draft_output'] = _preview_complete_text
                            _snapshot['scene_blocks'] = _new_blocks
                            _snapshot.pop('project_integrity_report', None)
                            _snapshot.pop('project_integrity_source_signature', None)
                            _snapshot.pop('project_integrity_status', None)
                            _updated = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(_snapshot)}).eq('id', _row_id).eq('project_id', _project_id).eq('user_id', _user_id).eq('draft_type', 'project_session').execute()
                            if not getattr(_updated, 'data', None):
                                raise RuntimeError('The database did not confirm the update')
                            st.session_state.current_draft_output = _preview_complete_text
                            st.session_state.pop('project_integrity_report', None)
                            st.session_state.pop('project_integrity_source_signature', None)
                            st.session_state.pop('project_integrity_status', None)
                            st.success('Working manuscript saved to the existing revision. No new version created.')
                            wbs_request_stage_change('Isolation Guardrail', export_view=False)
                except Exception as _save_exc:
                    st.error(f'Manuscript was not saved: {_save_exc}')
    st.markdown('---')
    st.caption('Save and continue. Unchanged storylines retain their existing version number.')
    if st.button('💾 Save Plot Architecture & Continue', key='_wbs_stage3_save_plot_architecture', type='primary', use_container_width=True):
        if st.session_state.get('demo_mode'):
            full_version_only_notice('Save Plot Architecture')
        else:
            _current_outline = str(st.session_state.get('plot_outline') or '').strip()
            _baseline = st.session_state.get('_wbs_stage3_saved_outline_baseline')
            _explicit_edits = bool(st.session_state.get('_wbs_stage3_unsaved_changes', False))
            _project_id = get_active_project_id()
            _requires_first_save = not _project_id
            if _baseline is None and _project_id:
                _baseline = _current_outline if not _explicit_edits else ''
            _changed = _baseline is not None and _current_outline != _baseline
            if not ai_output_is_usable(st.session_state.get('plot_outline')):
                st.error('No usable Plot Architecture is available to save. No work was changed.')
                st.stop()
            if _requires_first_save:
                if not save_current_project_session_to_supabase():
                    st.stop()
                st.session_state['_wbs_stage3_saved_outline_baseline'] = _current_outline
            elif _changed or _explicit_edits:
                _row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '').strip()
                _user_id = get_current_user_id()
                if not (_row_id and _project_id and _user_id):
                    st.error('The exact active revision cannot be verified. Nothing was saved.')
                    st.stop()
                try:
                    _rows = supabase.table('writersblock_project_drafts').select('id, draft_content').eq('id', _row_id).eq('project_id', _project_id).eq('user_id', _user_id).eq('draft_type', 'project_session').limit(1).execute().data or []
                    if len(_rows) != 1:
                        raise ValueError('Saved revision not found')
                    _saved_snapshot = json.loads(_rows[0].get('draft_content') or '{}')
                    if not isinstance(_saved_snapshot, dict):
                        raise ValueError('Invalid saved revision')
                    _previous_outline = str(_saved_snapshot.get('plot_outline') or '').strip()
                    if _previous_outline and _previous_outline != _current_outline:
                        st.error('This revision already contains a different saved Plot Architecture. Save as a new revision to preserve it. No automatic version was created.')
                        st.stop()
                    if not _previous_outline:
                        _saved_snapshot['plot_outline'] = _current_outline
                        _write = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(_saved_snapshot)}).eq('id', _row_id).eq('project_id', _project_id).eq('user_id', _user_id).eq('draft_type', 'project_session').execute()
                        if not getattr(_write, 'data', None):
                            raise ValueError('Database did not confirm save')
                        _check = supabase.table('writersblock_project_drafts').select('draft_content').eq('id', _row_id).eq('project_id', _project_id).eq('user_id', _user_id).eq('draft_type', 'project_session').limit(1).execute().data or []
                        _verified = json.loads(_check[0].get('draft_content') or '{}') if len(_check) == 1 else {}
                        if str(_verified.get('plot_outline') or '').strip() != _current_outline:
                            raise ValueError('Saved outline did not match the current storyline')
                        set_loaded_concept_version_baseline(_verified)
                        st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(_verified)
                        st.session_state['_wbs_last_saved_project_id'] = str(_project_id)
                    st.session_state['_wbs_stage3_saved_outline_baseline'] = _current_outline
                except Exception as _exc:
                    st.error(f'Stage 3 save failed: {_exc}. No new revision was created.')
                    st.stop()
            if not ai_output_is_usable(st.session_state.get('plot_outline')):
                st.error('No usable Plot Architecture is available to continue. No work was changed.')
                st.stop()
            st.session_state['_wbs_stage3_unsaved_changes'] = False
            st.session_state['_wbs_unlocked_saved_stage'] = max(int(st.session_state.get('_wbs_unlocked_saved_stage') or 1), 4)
            if str(st.session_state.get('current_draft_output') or '').strip():
                wbs_request_stage_change('Isolation Guardrail', export_view=False)
            else:
                wbs_request_stage_change('Drafting Engine')
    if st.session_state.get('_wbs_stage3_unsaved_changes'):
        st.caption('There are unsaved changes to the storyline.')
