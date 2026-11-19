"""screenplay: concept development. Existing engine and widget contracts retained."""

def render(context):
    DEFAULT_PICTURE_BOOK_PAGE_SIZE = context['DEFAULT_PICTURE_BOOK_PAGE_SIZE']
    DIALOGUE_STYLE_OPTIONS = context['DIALOGUE_STYLE_OPTIONS']
    WBS_FORMAT_IDS = context['WBS_FORMAT_IDS']
    WBS_FORMAT_OPTIONS = context['WBS_FORMAT_OPTIONS']
    WBS_LEGACY_FORMAT_BY_TEMPLATE_ID = context['WBS_LEGACY_FORMAT_BY_TEMPLATE_ID']
    WBS_MODEL_IMPORT_ERROR = context['WBS_MODEL_IMPORT_ERROR']
    ai_output_is_usable = context['ai_output_is_usable']
    count_words = context['count_words']
    create_bridge_adapter = context['create_bridge_adapter']
    datetime = context['datetime']
    extract_uploaded_manuscript_text = context['extract_uploaded_manuscript_text']
    get_active_concept_ui = context['get_active_concept_ui']
    get_active_format_development_context = context['get_active_format_development_context']
    get_active_format_template_values = context['get_active_format_template_values']
    get_active_format_widget_key = context['get_active_format_widget_key']
    get_active_project_id = context['get_active_project_id']
    get_current_project_version_name = context['get_current_project_version_name']
    get_current_user_id = context['get_current_user_id']
    get_dialogue_style = context['get_dialogue_style']
    get_dialogue_style_display = context['get_dialogue_style_display']
    get_existing_series_names = context['get_existing_series_names']
    get_full_project_continuity_context = context['get_full_project_continuity_context']
    get_next_series_book_number = context['get_next_series_book_number']
    get_project_title = context['get_project_title']
    get_project_title_for_display = context['get_project_title_for_display']
    get_saved_projects_versions_dropdown_items = context['get_saved_projects_versions_dropdown_items']
    get_scripting_format_context = context['get_scripting_format_context']
    get_series_aware_story_seed = context['get_series_aware_story_seed']
    get_series_metadata_by_project = context['get_series_metadata_by_project']
    get_series_reference_candidates = context['get_series_reference_candidates']
    get_text_signature = context['get_text_signature']
    get_unambiguous_series_project_ids = context['get_unambiguous_series_project_ids']
    get_wbs_format_display_name = context['get_wbs_format_display_name']
    get_wbs_format_template = context['get_wbs_format_template']
    get_wbs_quill_instructions = context['get_wbs_quill_instructions']
    html = context['html']
    make_series_key = context['make_series_key']
    mark_demo_action_used = context['mark_demo_action_used']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    render_active_format_development_fields = context['render_active_format_development_fields']
    render_quill_for_current_stage = context['render_quill_for_current_stage']
    render_save_open_project_to_series = context['render_save_open_project_to_series']
    require_demo_action_available = context['require_demo_action_available']
    require_product_access = context['require_product_access']
    sandbox_output_is_usable = context['sandbox_output_is_usable']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    save_project_to_supabase = context['save_project_to_supabase']
    save_series_metadata_for_project = context['save_series_metadata_for_project']
    st = context['st']
    time = context['time']
    wbs_can_generate_first_paths_for_saved_concept = context['wbs_can_generate_first_paths_for_saved_concept']
    wbs_concept_contains_editorial_commentary = context['wbs_concept_contains_editorial_commentary']
    wbs_get_saved_concept_setup_audit = context['wbs_get_saved_concept_setup_audit']
    wbs_has_saved_master = context['wbs_has_saved_master']
    wbs_request_stage_change = context['wbs_request_stage_change']
    wbs_work_has_changed = context['wbs_work_has_changed']
    st.markdown('\n        <style>\n        /* Keep Quill inside its actual right column so every middle-panel field\n           is physically constrained and can never run underneath it. */\n        div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),\n        div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {\n            position: sticky !important;\n            top: 0.75rem !important;\n            align-self: flex-start !important;\n            max-height: calc(100vh - 1.5rem) !important;\n            overflow-y: auto !important;\n            z-index: 20 !important;\n            background: var(--background-color, transparent);\n        }\n\n        /* Primary Writer navigation and format-selector hierarchy. */\n        [data-testid="stMain"] div[data-testid="stHorizontalBlock"]:first-of-type button p {\n            font-weight: 700 !important;\n            font-size: 1.02rem !important;\n        }\n        .wbs-format-selector-title {\n            font-size: 1.08rem !important;\n            font-weight: 700 !important;\n            line-height: 1.2 !important;\n            margin: 0 0 0.35rem 0 !important;\n        }\n\n        /* Raise the complete Writer workspace to recover vertical real estate. */\n        [data-testid="stMainBlockContainer"] {\n            padding-top: 1.0rem !important;\n        }\n\n        @media (max-width: 1100px) {\n            div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),\n            div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {\n                position: static !important;\n                max-height: none !important;\n                overflow: visible !important;\n            }\n        }\n        </style>\n        ', unsafe_allow_html=True)
    writer_main_col, writer_quill_col = st.columns([2.65, 1.15], gap='large')
    with writer_main_col:
        st.header('🗺️ Step 1: Concept Development')
        current_format_id = 'screenplay'
        if current_format_id not in WBS_FORMAT_IDS:
            current_format_id = 'novel_prose_novella'
        st.markdown(f'### Writing Format — {get_wbs_format_display_name(current_format_id)}')
        if 'wbs_format_template_selector' not in st.session_state:
            st.session_state['wbs_format_template_selector'] = current_format_id
        _format_control_col, _format_spacer_col = st.columns([1.6, 1.25], gap='small')
        with _format_control_col:
            if get_active_project_id():
                st.markdown(f'**{get_wbs_format_display_name(current_format_id)}**')
                selected_format_id = current_format_id
            else:
                selected_format_id = st.selectbox('Choose Writing Format', options=WBS_FORMAT_IDS, index=WBS_FORMAT_IDS.index(current_format_id), format_func=get_wbs_format_display_name, key='wbs_format_template_selector', label_visibility='collapsed')
        if selected_format_id != 'screenplay' and get_active_project_id():
            st.session_state['wbs_format_template_selector'] = 'screenplay'
            st.warning('Saved project formats are protected. Start a new project to use a different writing format.')
            st.rerun()
        if selected_format_id != 'screenplay':
            st.session_state.active_format_id = selected_format_id
            st.session_state.active_format_template = get_wbs_format_template(selected_format_id)
            st.session_state.quill_format_instructions = get_wbs_quill_instructions(selected_format_id)
            st.session_state.quill_format_name = get_wbs_format_display_name(selected_format_id)
            st.session_state.format_type = WBS_LEGACY_FORMAT_BY_TEMPLATE_ID.get(selected_format_id, 'Novel / Prose')
            st.rerun()
        concept_ui = get_active_concept_ui()
        st.markdown(f"##### {concept_ui.get('step_subtitle') or 'Build the foundation for your project.'}")
        _format_title_prefix = next((name for format_id, name in WBS_FORMAT_OPTIONS if format_id == 'screenplay'), 'Project')
        _project_title_label = f'{_format_title_prefix} / Project Title/Revision'
        if get_active_project_id():
            st.caption('Loaded saved project — saved Concept Development choices are restored where recorded.')
            if st.session_state.get('_wbs_saved_concept_missing_fields'):
                with st.expander('Historical Development Setup details', expanded=False):
                    st.caption("Some settings were not included in this saved project's historical records. Those fields show current template defaults, not verified original choices. Loading is read-only.")
            if st.session_state.get('_wbs_series_conflict_for_review'):
                st.caption('Historical series positions differed. Current Book order is managed separately in Series Library; saved stories were not changed.')
            elif st.session_state.get('_wbs_series_recovered_for_review'):
                st.info("Series relationship recovered from this project's saved records; no changes were written to the database.")
            _active_title_project_id = str(get_active_project_id() or '')
            _title_anchor = str(st.session_state.get('_wbs_loaded_project_title') or '').strip() if str(st.session_state.get('_wbs_loaded_project_id') or '') == _active_title_project_id else ''
            if _title_anchor and st.session_state.get('project_title') != _title_anchor:
                st.session_state.project_title = _title_anchor
            _display_master_title = _title_anchor or get_project_title()
            _active_saved_row_id = str(st.session_state.get('_wbs_loaded_saved_session_id') or '')
            _active_manuscript_row_id = str(st.session_state.get('_wbs_loaded_manuscript_version_id') or '')
            _active_project_key = str(get_active_project_id() or '')
            for _saved_entry in get_saved_projects_versions_dropdown_items():
                _saved_row = _saved_entry.get('row') or {}
                if str(_saved_row.get('project_id') or '') != _active_project_key:
                    continue
                _is_active = _saved_entry.get('type') == 'project_session' and _active_saved_row_id and (str(_saved_row.get('id') or '') == _active_saved_row_id) or (_saved_entry.get('type') == 'manuscript_version' and _active_manuscript_row_id and (str(_saved_row.get('id') or '') == _active_manuscript_row_id))
                if _is_active:
                    _version_match = re.search(' — (V-\\d+[A-Z]*) — ', str(_saved_entry.get('label') or ''))
                    if _version_match:
                        _display_master_title += ' — ' + _version_match.group(1)
                    break
            st.markdown(f'**{_project_title_label}**')
            st.markdown('<div style="background:#262730;color:#ffffff;padding:0.65rem 0.8rem;border:1px solid #41444f;border-radius:0.45rem;min-height:2.4rem;">' + html.escape(_display_master_title) + '</div>', unsafe_allow_html=True)
            render_save_open_project_to_series()
        else:
            st.session_state.project_title = st.text_input(_project_title_label, value=st.session_state.get('project_title', ''), placeholder="Example: It's Not Safe", key='project_title_input').strip()
        st.markdown('### ' + str(concept_ui.get('project_connection_heading') or 'Project Relationship'))
        project_scope_options = ['Standalone Book', 'Book in a Series']
        current_project_id = str(get_active_project_id() or '')
        membership = get_series_metadata_by_project() if get_current_user_id() else {}
        current_member = membership.get(current_project_id) or {}
        registered_series = str(current_member.get('series_name') or '').strip()
        saved_scope = 'Book in a Series' if registered_series else 'Standalone Book'
        selected_scope_default = saved_scope if current_project_id else str(st.session_state.get('project_scope') or 'Standalone Book')
        context = f"{current_project_id or 'new'}:{registered_series}"
        if st.session_state.get('_wbs_simple_series_context') != context:
            st.session_state['_wbs_simple_series_context'] = context
            st.session_state['project_scope_selector'] = selected_scope_default
            st.session_state['wbs_confirm_series_link'] = False
            st.session_state['wbs_confirm_series_removal'] = False
            st.session_state.pop('wbs_simple_series_choice', None)
            st.session_state.pop('wbs_simple_series_new_name', None)
        project_scope_labels = concept_ui.get('scope_labels') or {}
        chosen_scope = st.radio('Project Type:', project_scope_options, horizontal=True, key='project_scope_selector', format_func=lambda v: project_scope_labels.get(v, v))
        if current_project_id:
            st.session_state.project_scope = saved_scope
            st.session_state.series_name = registered_series
            st.session_state.series_key = make_series_key(registered_series)
            if registered_series:
                st.session_state.series_book_number = int(current_member.get('series_book_number') or 1)
        else:
            st.session_state.project_scope = chosen_scope
        if chosen_scope == 'Book in a Series':
            known_series = get_existing_series_names()
            choice_options = list(known_series) + ['Create New Series']
            existing_name = registered_series if current_project_id else str(st.session_state.get('series_name') or '').strip()
            if 'wbs_simple_series_choice' not in st.session_state:
                st.session_state['wbs_simple_series_choice'] = existing_name if existing_name in known_series else 'Create New Series'
            with st.columns([1, 1], gap='small')[0]:
                selected_choice = st.selectbox('Select Series:', choice_options, key='wbs_simple_series_choice')
                if selected_choice == 'Create New Series':
                    selected_series = st.text_input('New Series Name:', key='wbs_simple_series_new_name', max_chars=80).strip()
                else:
                    selected_series = selected_choice
            if not current_project_id:
                st.session_state.series_name = selected_series
                st.session_state.series_key = make_series_key(selected_series)
                st.session_state.series_continuity_mode = 'Strict'
                if selected_series:
                    st.session_state.series_book_number = get_next_series_book_number(selected_series)
                    st.caption('This new project will join the selected series when you save its master project.')
                else:
                    st.caption('Enter a series name before saving the project.')
            else:
                pass
        elif not current_project_id:
            st.session_state.series_name = ''
            st.session_state.series_key = ''
        else:
            st.session_state.series_name = ''
            st.session_state.series_key = ''
        if st.session_state.project_scope == 'Book in a Series' and st.session_state.get('series_name'):
            st.session_state.series_continuity_mode = 'Strict'
            candidates = get_series_reference_candidates()
            project_ids = get_unambiguous_series_project_ids(st.session_state.series_key, before_number=st.session_state.get('series_book_number') or 1)
            st.session_state.series_reference_ids = [c['id'] for c in candidates if str(c.get('project_id')) in project_ids]
            st.session_state.series_selection_signature = f"{st.session_state.series_key}:{st.session_state.get('series_book_number') or 1}"
        else:
            st.session_state.series_reference_ids = []
        render_active_format_development_fields()
        tone_options = list(concept_ui.get('tone_options') or ['Professional', 'Warm', 'Serious', 'Humorous', 'Suspenseful', 'Cinematic'])
        if 'Vivid & Descriptive' not in tone_options:
            tone_options.append('Vivid & Descriptive')
        tone_label = str(concept_ui.get('tone_label') or 'Tone / Aesthetic:')
        current_tone = str(st.session_state.get('tone_style') or '')
        if current_tone and current_tone not in tone_options:
            tone_options.append(current_tone)
        default_tone_index = tone_options.index(current_tone) if current_tone in tone_options else 0
        _wbs_tone_widget_key = get_active_format_widget_key('concept_prose_tone')
        if _wbs_tone_widget_key not in st.session_state:
            st.session_state[_wbs_tone_widget_key] = tone_options[default_tone_index]
        _tone_col, _tone_spacer = st.columns([3.0, 1.2])
        with _tone_col:
            st.session_state.tone_style = st.selectbox(tone_label, tone_options, key=_wbs_tone_widget_key)
        _wbs_premise_mode = str(st.session_state.get('version_source_mode') or st.session_state.get('starting_source_mode') or 'Custom Plot Line')
        _wbs_premise_editable = _wbs_premise_mode in ('Custom Plot Line', 'Story Idea')
        _wbs_premise_current = str(st.session_state.get('story_seed') or st.session_state.get('wbs_project_original_concept') or '')
        _wbs_premise_widget_key = get_active_format_widget_key('concept_story_premise')
        if _wbs_premise_widget_key not in st.session_state or not _wbs_premise_editable:
            st.session_state[_wbs_premise_widget_key] = _wbs_premise_current
        st.markdown('#### Story Premise')
        _wbs_premise_text = st.text_area('Story Premise:', height=210, key=_wbs_premise_widget_key, disabled=not _wbs_premise_editable, help="The author's story blueprint. Used with Central Conflict and Subplots to develop Plot A, B and C.")
        if _wbs_premise_editable:
            st.session_state.story_seed = _wbs_premise_text
            _wbs_premise_words = count_words(_wbs_premise_text)
            st.caption(f'{_wbs_premise_words:,} / 1,000 words')
            if _wbs_premise_words > 1000:
                st.warning('This entry exceeds the 1,000-word Concept Development limit.')
        else:
            st.caption('Select the Enter Your Own Premise starting source below to edit this field.')
        dialogue_style_options = DIALOGUE_STYLE_OPTIONS
        current_dialogue_style = get_dialogue_style()
        _podcast_episode_format = str(get_active_format_template_values().get('episode_format') or '')
        _show_dialogue_control = True
        if _show_dialogue_control:
            _dialogue_col, _dialogue_spacer = st.columns([3.0, 1.2])
            with _dialogue_col:
                st.session_state.dialogue_style = st.selectbox(concept_ui.get('dialogue_label') or 'Dialogue Style:', dialogue_style_options, index=dialogue_style_options.index(current_dialogue_style), key='dialogue_style_selector', format_func=get_dialogue_style_display, help='Percentages are approximate targets for the share of finished words that are spoken dialogue. Story-Driven / Automatic has no fixed percentage. The selected project type still controls how dialogue is formatted.')
        st.markdown('---')
        st.markdown(f"### {concept_ui.get('source_heading') or 'Choose a Starting Point'}")
        current_saved_option = '-- Use Current Saved Manuscript / Storyline --'
        custom_plot_option = str(concept_ui.get('custom_option') or '-- Enter Your Own Story / Premise --')
        quill_start_option = '-- Quill-Assisted Starting Point --'
        replacement_draft_option = '-- Upload / Replace with Different Draft / Manuscript --'
        seed_options = [current_saved_option, custom_plot_option, quill_start_option, replacement_draft_option]
        current_seed = str(st.session_state.get('story_seed') or '')
        current_source_mode = str(st.session_state.get('version_source_mode') or st.session_state.get('starting_source_mode') or 'Custom Plot Line')
        if str(st.session_state.get('saved_quill_concept') or '').strip() and str(st.session_state.get('version_source_mode') or '') == 'Quill Assisted':
            default_seed_index = seed_options.index(quill_start_option)
        elif current_source_mode == 'Saved Manuscript':
            default_seed_index = seed_options.index(current_saved_option)
        elif current_source_mode in {'Replacement Draft / Manuscript', 'Existing Draft / Manuscript'}:
            default_seed_index = seed_options.index(replacement_draft_option)
        elif current_source_mode == 'Quill Assisted':
            default_seed_index = seed_options.index(quill_start_option)
        else:
            default_seed_index = seed_options.index(custom_plot_option)
        saved_version_source_text = str(st.session_state.get('saved_version_source_text') or '').strip()
        if saved_version_source_text:
            saved_source_name = str(st.session_state.get('saved_version_source_name') or get_current_project_version_name() or 'Saved Version').strip()
            st.info(f'Saved Version Source: {saved_source_name} — {count_words(saved_version_source_text):,} words. This manuscript is retained and can be selected as the transformation source.')
        selected_seed = st.radio(str(concept_ui.get('source_label') or 'Starting Source:'), seed_options, index=default_seed_index, key=f"starting_source_{'screenplay'}")
        if selected_seed == current_saved_option:
            st.session_state.version_source_mode = 'Saved Manuscript'
            st.session_state.starting_source_mode = 'Saved Manuscript'
            saved_source = str(st.session_state.get('saved_version_source_text') or '').strip()
            if saved_source:
                st.success(f'Using Current Saved Manuscript / Storyline — {count_words(saved_source):,} words')
                st.caption('The loaded manuscript remains the story source. Any Concept Development changes above will be used to transform it into the new version.')
                _src_id = get_text_signature(saved_source)[:12]
                _edit_key = f"wbs_saved_source_edit_{'screenplay'}_{_src_id}"
                st.markdown("**Editable Saved Manuscript — paste Quill's revised text here:**")
                _revised_source = st.text_area('Editable Saved Manuscript:', value=saved_source, height=330, key=_edit_key, label_visibility='collapsed')
                st.caption('Edit or paste a revision. The original remains unchanged until you save a NEW version.')
                if st.button('💾 Save Edited Manuscript As New Version', key=f'wbs_save_edited_source_{_src_id}', type='primary', use_container_width=True, disabled=bool(st.session_state.get('demo_mode'))):
                    if not _revised_source.strip():
                        st.error('The manuscript cannot be empty.')
                    elif _revised_source == saved_source:
                        st.info('No text changes to save.')
                    else:
                        _prev_source = saved_source
                        _prev_draft = st.session_state.get('current_draft_output', '')
                        _prev_name = st.session_state.get('project_version_name', 'Original')
                        _new_name = f'Edited {datetime.now():%m-%d %H%M}'
                        st.session_state.saved_version_source_text = _revised_source
                        st.session_state.saved_version_source_word_count = count_words(_revised_source)
                        st.session_state.saved_version_source_name = _new_name
                        st.session_state.current_draft_output = _revised_source
                        st.session_state.project_version_name = _new_name
                        try:
                            _save_result = save_current_project_session_to_supabase(version_name=_new_name, save_as_new_version=True)
                            if not _save_result:
                                raise RuntimeError('Database did not confirm the save')
                        except Exception as _exc:
                            st.session_state.saved_version_source_text = _prev_source
                            st.session_state.saved_version_source_word_count = count_words(_prev_source)
                            st.session_state.current_draft_output = _prev_draft
                            st.session_state.project_version_name = _prev_name
                            st.error(f'Save failed; original restored: {_exc}')
                        else:
                            st.success('New editable manuscript version saved. The original is preserved.')
                            st.rerun()
            else:
                st.warning('No saved manuscript is loaded. Choose another starting source or load a saved version first.')
        elif selected_seed == custom_plot_option:
            st.session_state.version_source_mode = 'Custom Plot Line'
            st.session_state.starting_source_mode = 'Custom Plot Line'
            st.caption('The Story Premise field is above, alongside the other Stage 1 development information.')
        elif selected_seed == quill_start_option:
            st.session_state.version_source_mode = 'Quill Assisted'
            st.session_state.starting_source_mode = 'Quill Assisted'
            format_name = str((st.session_state.get('active_format_template') or {}).get('display_name') or st.session_state.get('quill_format_name') or 'Writing Project')
            st.caption(f'Quill uses your {format_name} Development Setup above to propose a starting concept. You can edit it or request another suggestion before continuing.')
            st.session_state.quill_starting_direction = ''
            quill_key = f"wbs_quill_starting_concept_{'screenplay'}"
            pending_key = f"_wbs_quill_pending_concept_{'screenplay'}"
            pending_concept = st.session_state.pop(pending_key, None)
            if pending_concept is not None:
                st.session_state[quill_key] = str(pending_concept)
                st.session_state.story_seed = str(pending_concept)
            if quill_key not in st.session_state:
                st.session_state[quill_key] = str(st.session_state.get('saved_quill_concept') or st.session_state.get('story_seed') or '')
            elif not str(st.session_state.get(quill_key) or '').strip() and str(st.session_state.get('saved_quill_concept') or '').strip():
                st.session_state[quill_key] = str(st.session_state['saved_quill_concept'])
            guided_col, original_col = st.columns(2, gap='small')
            with guided_col:
                guided_generation = st.button('Create Story From My Development Setup', key=f"wbs_quill_generate_guided_{'screenplay'}", use_container_width=True)
            with original_col:
                original_generation = st.button('Let Quill Suggest a Story', key=f"wbs_quill_generate_original_{'screenplay'}", use_container_width=True)
            if guided_generation or original_generation:
                require_product_access('sandbox')
                backend = st.session_state.get('backend')
                client = getattr(backend, 'client', None)
                model_name = getattr(backend, 'model_name', None)
                if client is None or not model_name:
                    st.error("Quill's writing service is unavailable. Please try again later.")
                else:
                    development_context = get_active_format_development_context()
                    creative_direction = "Build the story around the writer's specified theme, takeaway, and creative instructions in Development Setup. Honor those choices closely." if guided_generation else 'Invent a fresh, original storyline. Honor the format, age range, genre, and required production constraints, but freely invent characters, conflict, and events rather than relying on a writer-specified theme or takeaway.'
                    prompt = f"You are Quill, writing an original STORY CONCEPT that a writer can edit. Write 100–180 words for {format_name}. Deliver a vivid, self-contained account of WHAT HAPPENS: name the protagonist, establish the situation, show the inciting event, describe concrete choices and consequences, and end with a plausible change or unresolved question. Write paragraphs of story-facing prose, not a lesson, evaluation, outline, creative brief, or discussion of theme. Keep it at concept/synopsis length, not a finished manuscript. Respect relevant development requirements without calling attention to these requirements. NEVER use meta-commentary such as 'this story explores', 'the central idea', 'the narrative should', 'the story will', 'from a first-person perspective', 'the writer', or 'the reader'. Do not add a heading. Begin immediately with the character or unfolding event.\n\nGENERATION DIRECTION: {creative_direction}\n\nDEVELOPMENT SETUP:\n{development_context}\nTone: {st.session_state.get('tone_style', '')}\nDialogue: {get_dialogue_style_display()}\nFormat guidance: {st.session_state.get('quill_format_instructions', '')}"
                    try:
                        with st.spinner('Quill is preparing a starting concept...'):
                            suggestion = client.models.generate_content(model=model_name, contents=prompt)
                            concept = str(getattr(suggestion, 'text', '') or '').strip()
                            if concept and wbs_concept_contains_editorial_commentary(concept):
                                rewrite_prompt = f"Rewrite the following draft as a STORY SYNOPSIS, not commentary about a story. Keep its protagonist, events, conflict, and outcome intact, but express them only as things that happen in the fictional world. Use 100–180 words of fluent prose. Remove references to themes, writing, narrative structure, the reader, genre, viewpoint, and any phrases beginning 'this story', 'the central idea', or 'the narrative'. Return the revised synopsis only, without a heading.\n\nDRAFT:\n{concept}"
                                rewritten = client.models.generate_content(model=model_name, contents=rewrite_prompt)
                                concept = str(getattr(rewritten, 'text', '') or '').strip()
                        if not concept or not ai_output_is_usable(concept) or wbs_concept_contains_editorial_commentary(concept):
                            st.error('Quill could not produce a clean story concept. Please try again.')
                        else:
                            st.session_state[quill_key] = concept
                            st.session_state.story_seed = concept
                            st.session_state.version_source_mode = 'Quill Assisted'
                            st.session_state.starting_source_mode = 'Quill Assisted'
                            st.rerun()
                    except Exception as exc:
                        st.error(f'Quill could not generate a starting concept: {exc}')
            st.session_state.story_seed = st.text_area('Saved / Suggested Story Concept — Edit Before Continuing:', key=quill_key, height=180, placeholder="Choose one of the two buttons above, then edit Quill's suggestion here.")
            st.caption(f'{count_words(st.session_state.story_seed):,} / 1,000 words')
            if count_words(st.session_state.story_seed) > 1000:
                st.warning('Reduce the starting concept to 1,000 words or fewer.')
        elif selected_seed == replacement_draft_option:
            st.session_state.version_source_mode = 'Replacement Draft / Manuscript'
            st.session_state.starting_source_mode = 'Replacement Draft / Manuscript'
            st.warning('Large documents may result in higher API usage during processing.')
            st.markdown('\n                <style>\n                [data-testid="stFileUploaderDropzoneInstructions"] {\n                    display: none !important;\n                }\n                </style>\n                ', unsafe_allow_html=True)
            uploaded_existing_draft = st.file_uploader('Upload / Replace with Different Draft / Manuscript:', type=['docx', 'txt'], key=f"concept_existing_draft_upload_{'screenplay'}", help='Use a DOCX or TXT as the authoritative replacement source for this new version.')
            st.caption('Maximum 120,000 words • DOCX, TXT')
            if uploaded_existing_draft is not None:
                try:
                    extracted_existing_draft = extract_uploaded_manuscript_text(uploaded_existing_draft)
                except Exception as source_error:
                    st.error(f'The document could not be read: {source_error}')
                    extracted_existing_draft = ''
                if extracted_existing_draft.strip():
                    extracted_word_count = count_words(extracted_existing_draft)
                    if extracted_word_count > 120000:
                        st.session_state.imported_source_text = ''
                        st.session_state.imported_source_name = ''
                        st.session_state.imported_source_word_count = 0
                        st.error(f'Document contains {extracted_word_count:,} words. WritersBlock accepts existing drafts up to 120,000 words.')
                    else:
                        st.session_state.imported_source_text = extracted_existing_draft.strip()
                        st.session_state.imported_source_name = str(getattr(uploaded_existing_draft, 'name', 'Existing Draft') or 'Existing Draft')
                        st.session_state.imported_source_word_count = extracted_word_count
                        st.session_state.story_seed = st.session_state.imported_source_text
            imported_source_text = str(st.session_state.get('imported_source_text') or '').strip()
            imported_source_name = str(st.session_state.get('imported_source_name') or '').strip()
            if imported_source_text:
                st.success(f"Replacement Source Loaded: {imported_source_name or 'Uploaded Document'} — {count_words(imported_source_text):,} words")
                st.caption('This source is read-only in Concept Development. WritersBlock will use it as protected starting material while the selected format and its development rules control the project.')
                st.text_area('Replacement Source — Read Only:', value=imported_source_text, height=320, disabled=True, key=f"concept_existing_draft_read_only_preview_{'screenplay'}")
            else:
                st.info('Upload a DOCX or TXT source to use it as the replacement starting material.')
        _wbs_short_story_stage1 = True
        st.markdown('---')
        _ss_master = wbs_has_saved_master()
        _ss_changed = wbs_work_has_changed() if _ss_master is True else True
        _wbs_stage1_save_col, _wbs_stage1_develop_col = st.columns(2, gap='small')
        with _wbs_stage1_save_col:
            _wbs_stage1_save_clicked = st.button('Save And/Or Continue To Next Stage', key='wbs_stage1_save_or_continue', use_container_width=True, type='secondary' if st.session_state.get('_wbs_stage1_continue_approval') == (str(get_active_project_id() or ''), 'screenplay', str(st.session_state.get('_wbs_last_saved_work_signature') or '')) else 'primary')
        if _wbs_stage1_save_clicked:
            if _ss_master is not True or _ss_changed is not False:
                _ss_result = save_current_project_session_to_supabase()
                if not _ss_result:
                    st.stop()
            st.session_state['_wbs_stage1_continue_approval'] = (str(get_active_project_id() or ''), 'screenplay', str(st.session_state.get('_wbs_last_saved_work_signature') or ''))
            st.session_state['_wbs_unlocked_saved_stage'] = max(int(st.session_state.get('_wbs_unlocked_saved_stage') or 1), 2)
            wbs_request_stage_change('Sandbox')
        _ss_approval = st.session_state.get('_wbs_stage1_continue_approval')
        _ss_expected = (str(get_active_project_id() or ''), 'screenplay', str(st.session_state.get('_wbs_last_saved_work_signature') or ''))
        _ss_can_continue = _ss_master is True and _ss_changed is False and (_ss_approval == _ss_expected)
        _wbs_is_loaded_project = bool(get_active_project_id())
        _wbs_has_saved_paths = _wbs_is_loaded_project and isinstance(st.session_state.get('sandbox_slates'), dict) and sandbox_output_is_usable(st.session_state.get('sandbox_slates'))
        _wbs_paths_button_label = 'Continue to Plot Architecture' if _wbs_has_saved_paths and False else 'Continue to Scripting — Existing Paths' if _wbs_has_saved_paths else str(concept_ui.get('button_label') or 'Develop Project Paths 🚀')
        with _wbs_stage1_develop_col:
            _wbs_develop_clicked = st.button(_wbs_paths_button_label, key='generate_sandbox_paths', type='primary' if _ss_can_continue else 'secondary', use_container_width=True, disabled=not _ss_can_continue)
        if _wbs_develop_clicked:
            if _wbs_has_saved_paths:
                if wbs_has_saved_master() is not True or wbs_work_has_changed() is not False:
                    st.error("These scripting paths or concept changes are not yet saved. Use 'Save Project Changes As A New Version' above, then continue to Scripting. No AI regeneration is required.")
                    st.stop()
                wbs_request_stage_change('Sandbox')
                st.stop()
            _wbs_create_saved_first_paths = False
            if _wbs_is_loaded_project:
                _wbs_create_saved_first_paths, _wbs_first_paths_error = wbs_can_generate_first_paths_for_saved_concept()
                if not _wbs_create_saved_first_paths:
                    st.error(_wbs_first_paths_error)
                    st.stop()
                _audit = wbs_get_saved_concept_setup_audit()
                if not _audit.get('ok'):
                    st.error((_audit.get('message') or 'Cannot verify saved setup.') + ' No AI generation was started.')
                    st.stop()
                if _audit.get('missing'):
                    st.error('This saved revision is missing Development Setup selections: ' + ', '.join((label for _, label in _audit['missing'][:12])) + '. The displayed template defaults are NOT proven to be your original instructions. No AI generation was started. Review the saved Setup audit.')
                    st.stop()
            require_product_access('sandbox')
            require_demo_action_available('sandbox')
            selected_source_mode = str(st.session_state.get('version_source_mode') or st.session_state.get('starting_source_mode') or 'Custom Plot Line')
            if selected_source_mode == 'Saved Manuscript':
                selected_source_text = str(st.session_state.get('saved_version_source_text') or '').strip()
                if not selected_source_text:
                    st.error('No current saved manuscript is available. Load a saved version or choose another starting source.')
                    st.stop()
                st.session_state.story_seed = selected_source_text
            elif selected_source_mode in {'Replacement Draft / Manuscript', 'Existing Draft / Manuscript'}:
                selected_source_text = str(st.session_state.get('imported_source_text') or '').strip()
                if not selected_source_text:
                    st.error('Please upload a DOCX or TXT replacement draft before developing this version.')
                    st.stop()
                st.session_state.story_seed = selected_source_text
            elif selected_source_mode in {'Custom Plot Line', 'Quill Assisted'}:
                selected_source_text = str(st.session_state.get('story_seed') or '').strip()
                if not selected_source_text:
                    st.error('Please enter or generate a starting point before continuing.')
                    st.stop()
            st.session_state.plot_outline = None
            st.session_state.current_draft_output = ''
            st.session_state.rewritten_manuscript = ''
            st.session_state.manuscript_text = ''
            st.session_state.current_processing_beat = 0
            st.session_state.total_beats = 0
            st.session_state.manuscript_version = 0
            st.session_state.picture_book_layout_spreads = []
            st.session_state.picture_book_layout_source_signature = ''
            st.session_state.picture_book_layout_preview_id = 0
            st.session_state.picture_book_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
            if not get_project_title():
                st.error('Please name this project before continuing.')
                st.stop()
            if not st.session_state.get('wbs_project_original_concept'):
                st.session_state.wbs_project_original_concept = str(st.session_state.story_seed or '').strip()
            if not st.session_state.story_seed.strip():
                source_noun = str(concept_ui.get('source_noun') or 'project premise')
                st.error(f'Please enter a {source_noun} or upload an existing source before continuing.')
                st.stop()
            if st.session_state.get('version_source_mode') in {'Custom Plot Line', 'Quill Assisted'} and count_words(st.session_state.story_seed) > 1000:
                st.error('Please reduce the Concept Development entry to 1,000 words or fewer before continuing.')
                st.stop()
            with st.spinner(str(concept_ui.get('spinner') or 'Developing project paths...')):
                time.sleep(1)
                if create_bridge_adapter is None:
                    st.error(f'WritersBlock Model is unavailable. {WBS_MODEL_IMPORT_ERROR}')
                    st.stop()
                _wbs_bridge_adapter = create_bridge_adapter(backend=st.session_state.backend)
                _wbs_bridge_result = _wbs_bridge_adapter.execute('Generate sandbox paths', st.session_state, prepared_context={'series_aware_story_seed': get_series_aware_story_seed(), 'scripting_format_context': get_scripting_format_context(), 'format_development_context': get_full_project_continuity_context() + '\n\nSTAGE 2 — THREE SOURCE FIELDS GOVERN THE PLOT (ALL WRITING FORMATS):\n' + 'MANDATORY AUTHOR MATERIAL, verbatim as entered (do not summarize or omit):\n' + 'STORY PREMISE / ORIGINAL SOURCE:\n' + str(st.session_state.get('story_seed') or '') + '\n\nCENTRAL CONFLICT AND SUBPLOT / OTHER STAGE 1 DEVELOPMENT FIELDS:\n' + get_active_format_development_context() + '\n\nNON-NEGOTIABLE GENERATION RULES:\n' + "Treat the author's Story Premise, Central Conflict and Subplot as ONE binding story specification. " + 'Each of the three generated Plot Architecture options (A/B/C) must include ALL explicit substantive ' + 'events and plot facts from ALL THREE fields; inclusion is the default, never condensation by deletion. ' + "Follow the author's actual story sequence and causality from origin through development, climax, aftermath, " + 'and FINAL outcome. Never stop at an earlier dramatic event when the premise continues beyond it. ' + 'A reveal may be moved for suspense only if the original event itself is still depicted or clearly accounted for. ' + 'Keep named characters, their relationships, setting, periods, identity changes, technical discoveries, ' + 'antagonists, supporting characters, subplot beats, consequences and resolutions. ' + 'Do NOT write a loosely inspired interpretation, a replacement story, a generic theme discussion, ' + 'or a different ending. Enhance and connect the supplied material with meaningful additional ' + 'developments, subplots, rising action and twists that DO NOT contradict it. ' + 'Plot A/B/C differ in pacing, scene emphasis, order of revelation and dramatic construction ONLY; ' + "the writer's events and outcome remain the same in every option. " + 'For EACH option, describe explicitly the opening/origin, central conflict, subplot development, ' + 'major turning points, climax, aftermath, and author-specified final outcome IN STORY TERMS. ' + 'Before responding, audit each option against EVERY significant source event and detail, ' + 'especially the FIRST and LAST paragraphs and every stated subplot. Expand missing items before returning. ' + "When the original has no specified outcome, propose one without presenting it as the author's fact. " + 'Do not print these internal instructions; output only the three writer-facing plot options.\n', 'quill_format_instructions': st.session_state.get('quill_format_instructions', ''), 'quill_template_context': refresh_quill_template_context()}, action_payload={'tone_style': st.session_state.tone_style, 'author_style': st.session_state.author_style})
                if not _wbs_bridge_result.success:
                    st.error('WritersBlock Model Bridge could not generate the sandbox paths. ' + (_wbs_bridge_result.error or 'Unknown bridge error.'))
                    st.stop()
                st.session_state.sandbox_slates = _wbs_bridge_result.output
                st.session_state['_wbs_agent_bridge_last_operation'] = _wbs_bridge_result.backend_operation or ''
                st.session_state['_wbs_agent_bridge_last_success'] = True
                if not sandbox_output_is_usable(st.session_state.sandbox_slates):
                    st.error('Quill did not return three usable paths. Nothing was saved.')
                    st.stop()
                mark_demo_action_used('sandbox')
                if _wbs_create_saved_first_paths:
                    first_paths_save = save_current_project_session_to_supabase(version_name='First Scripting Paths', save_as_new_version=False)
                    if not first_paths_save or getattr(first_paths_save, 'unchanged', False):
                        st.error("Generated paths remain in this session but were NOT saved. Use 'Save Project Changes As A New Version' above to retry the save without another AI generation.")
                        st.stop()
                    st.session_state.project_saved_notice = True
                    wbs_request_stage_change('Sandbox')
                    st.stop()
                if get_active_project_id():
                    st.error('Existing project detected. No new project was created or saved.')
                    st.stop()
                new_project_result = save_project_to_supabase(project_title=get_project_title_for_display()[:80], project_type=st.session_state.format_type)
                if not new_project_result or not get_active_project_id():
                    st.error('New project creation could not be confirmed. Scripting was not opened.')
                    st.stop()
                if st.session_state.get('project_scope') == 'Book in a Series':
                    save_series_metadata_for_project(st.session_state.get('current_project_id'))
                paths_checkpoint = save_current_project_session_to_supabase(version_name='First Scripting Paths', save_as_new_version=False)
                if not paths_checkpoint:
                    st.error('Generated paths were not saved. Stage 2 was not opened. Retry saving without regenerating.')
                    st.stop()
                st.session_state.project_saved_notice = True
                wbs_request_stage_change('Sandbox')
    with writer_quill_col:
        if st.session_state.get('licensed_mode') or st.session_state.get('demo_mode'):
            st.markdown('<div class="wbs-writer-quill-sticky-anchor"></div>', unsafe_allow_html=True)
            render_quill_for_current_stage(st_module=st, show_prelude=True)
