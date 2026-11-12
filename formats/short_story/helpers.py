"""Format-owned save, review and callback functions; no sibling imports."""

def wbs_ss_set_integrity_return_context(context, scene_number):
    """Enable the one-click return only for this project's exact saved revision.

    This is temporary navigation state, never a saved manuscript field. It does
    not change stage IDs, review content, or the user's V-number.
    """
    get_active_project_id = context['get_active_project_id']
    st = context['st']
    st.session_state['_wbs_ss_integrity_return_context'] = {'project_id': str(get_active_project_id() or ''), 'saved_row_id': str(st.session_state.get('_wbs_active_saved_session_row_id') or ''), 'format_id': str(st.session_state.get('active_format_id') or ''), 'scene_number': int(scene_number)}

def wbs_ss_is_integrity_return_context(context):
    """Reject a return shortcut left over from another project or revision."""
    get_active_project_id = context['get_active_project_id']
    st = context['st']
    ctx = st.session_state.get('_wbs_ss_integrity_return_context')
    return isinstance(ctx, dict) and bool(ctx.get('project_id') and ctx.get('saved_row_id')) and (ctx.get('project_id') == str(get_active_project_id() or '')) and (ctx.get('saved_row_id') == str(st.session_state.get('_wbs_active_saved_session_row_id') or '')) and (ctx.get('format_id') == str(st.session_state.get('active_format_id') or ''))

def wbs_stage4_title_input_key(context):
    """Title-editor state stays with one project and one saved revision."""
    get_active_project_id = context['get_active_project_id']
    re = context['re']
    st = context['st']
    project = re.sub('[^A-Za-z0-9_-]', '_', str(get_active_project_id() or 'new'))
    revision = re.sub('[^A-Za-z0-9_-]', '_', str(st.session_state.get('_wbs_active_saved_session_row_id') or 'none'))
    return f'wbs_stage4_new_title_v1_{project}_{revision}'

def wbs_stage4_save_renamed_title_as_new_v1(context, new_title):
    """Create a NEW project V-1 from the selected saved revision; never rename V-6.

    The new project has a different ID. Existing saved sessions, manuscripts,
    scene blocks, titles and versions are left completely untouched.
    """
    datetime = context['datetime']
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_project_title = context['get_project_title']
    json = context['json']
    scene_blocks = context['scene_blocks']
    st = context['st']
    supabase = context['supabase']
    timezone = context['timezone']
    wbs_save_state_signature = context['wbs_save_state_signature']
    old_project = str(get_active_project_id() or '')
    old_row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
    user = str(get_current_user_id() or '')
    old_title = str(get_project_title() or '')
    fmt = 'short_story'
    if not all((old_project, old_row_id, user, old_title, fmt)):
        raise ValueError('Load an existing saved project revision before renaming it.')
    if str(new_title).casefold() == old_title.casefold():
        return False
    parent_rows = supabase.table('writersblock_projects').select('id,project_title,project_type').eq('id', old_project).eq('user_id', user).limit(1).execute().data or []
    old_rows = supabase.table('writersblock_project_drafts').select('id,project_id,draft_content').eq('id', old_row_id).eq('project_id', old_project).eq('user_id', user).eq('draft_type', 'project_session').limit(1).execute().data or []
    if len(parent_rows) != 1 or len(old_rows) != 1 or parent_rows[0].get('project_title') != old_title:
        raise ValueError('Cannot verify the current project and saved revision; no title was changed.')
    snapshot = json.loads(old_rows[0].get('draft_content') or '{}')
    if not isinstance(snapshot, dict) or str(snapshot.get('current_project_id') or old_project) != old_project or snapshot.get('project_title') != old_title or (snapshot.get('active_format_id') != fmt):
        raise ValueError("The saved revision's project identity or format does not match.")
    current_story = str(st.session_state.get('current_draft_output') or '')
    saved_story = str(snapshot.get('current_draft_output') or '')
    if saved_story != current_story:
        raise ValueError('Save manuscript corrections first, then rename this saved project.')
    if scene_blocks(snapshot.get('scene_blocks') or {}) != scene_blocks(st.session_state.get('scene_blocks') or {}):
        raise ValueError('Save the scene changes first, then rename this saved project.')
    existing = supabase.table('writersblock_projects').select('id').eq('user_id', user).eq('project_title', new_title).limit(1).execute().data or []
    if existing:
        raise ValueError('A project with that title already exists. Choose a different title.')
    cloned = dict(snapshot)
    cloned['project_title'] = new_title
    cloned['project_version_name'] = 'Original'
    cloned['concept_change_areas'] = []
    cloned['saved_at'] = datetime.now(timezone.utc).isoformat()
    cloned.pop('wbs_stage4_final_acceptance', None)
    cloned.pop('wbs_stage4_scene_approvals', None)
    new_id = None
    try:
        new_project = supabase.table('writersblock_projects').insert({'user_id': user, 'project_title': new_title, 'project_type': parent_rows[0].get('project_type') or snapshot.get('format_type') or 'story', 'project_status': 'active'}).execute()
        created = getattr(new_project, 'data', None) or []
        if len(created) != 1 or not created[0].get('id'):
            raise RuntimeError("The renamed project's new master record was not confirmed.")
        new_id = str(created[0]['id'])
        cloned['current_project_id'] = new_id
        draft = supabase.table('writersblock_project_drafts').insert({'project_id': new_id, 'user_id': user, 'draft_title': 'Saved Project Session — Original', 'draft_type': 'project_session', 'draft_content': json.dumps(cloned, ensure_ascii=False), 'version_number': 1}).execute()
        saved_rows = getattr(draft, 'data', None) or []
        if len(saved_rows) != 1 or not saved_rows[0].get('id'):
            raise RuntimeError("The renamed project's new V-1 record was not confirmed.")
        new_row_id = str(saved_rows[0]['id'])
    except Exception:
        if new_id:
            try:
                supabase.table('writersblock_projects').delete().eq('id', new_id).eq('user_id', user).execute()
            except Exception:
                pass
        raise
    st.session_state['project_title'] = new_title
    st.session_state['current_project_id'] = new_id
    st.session_state['project_version_name'] = 'Original'
    st.session_state['wbs_stage4_final_acceptance'] = {}
    st.session_state['wbs_stage4_scene_approvals'] = {}
    st.session_state['_wbs_loaded_project_id'] = new_id
    st.session_state['_wbs_locked_project_id'] = new_id
    st.session_state['wbs_locked_format_id'] = fmt
    st.session_state['_wbs_loaded_project_title'] = new_title
    st.session_state['_wbs_loaded_saved_session_id'] = new_row_id
    st.session_state['_wbs_active_saved_session_row_id'] = new_row_id
    st.session_state['_wbs_last_saved_project_id'] = new_id
    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(cloned)
    st.session_state['_wbs_saved_session_to_select'] = new_row_id
    st.session_state['last_saved_project_at'] = cloned['saved_at']
    st.session_state.pop('_wbs_stage4_approved_scenes', None)
    st.session_state.pop('_wbs_stage4_review_identity', None)
    return True

def wbs_stage4_final_status(context, record, title, manuscript, report, report_source_signature, scene_approval_complete, project_id=None, revision_id=None):
    """Pure, fail-closed proof that each *explicit* acceptance is still current."""
    get_text_signature = context['get_text_signature']
    record = record if isinstance(record, dict) else {}
    if record.get('project_id') != str(project_id or '') or record.get('revision_id') != str(revision_id or ''):
        record = {}
    signature = get_text_signature(str(manuscript or ''))
    report = str(report or '')
    report_current = bool(report.strip() and report_source_signature == signature)
    return {'title': bool(title and record.get('title') == title), 'manuscript': bool(scene_approval_complete and record.get('manuscript_signature') == signature), 'integrity': bool(report_current and record.get('integrity_source_signature') == signature and (record.get('integrity_report_signature') == get_text_signature(report)))}

def wbs_stage4_save_final_acceptance(context, component):
    """Record one approval on the selected existing revision, NEVER an INSERT.

    The approval record is independent of the saved story, format-specific
    configuration and Project Integrity AI generation.
    """
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    get_project_title = context['get_project_title']
    get_project_title_from_project_id = context['get_project_title_from_project_id']
    get_text_signature = context['get_text_signature']
    json = context['json']
    scene_blocks = context['scene_blocks']
    scene_manuscript = context['scene_manuscript']
    st = context['st']
    supabase = context['supabase']
    wbs_save_state_signature = context['wbs_save_state_signature']
    wbs_stage4_valid_approvals = context['wbs_stage4_valid_approvals']
    if component not in ('title', 'manuscript', 'integrity'):
        raise ValueError('Unknown acceptance control')
    row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
    project_id = str(get_active_project_id() or '')
    user_id = str(get_current_user_id() or '')
    active_format = 'short_story'
    if not all((row_id, project_id, user_id, active_format)):
        raise ValueError('Load a saved project revision before accepting.')
    master_title = str(get_project_title_from_project_id(project_id) or '').strip()
    if not master_title or master_title != get_project_title():
        raise ValueError('The saved project title changed. Reload before accepting.')
    manuscript = str(st.session_state.get('current_draft_output') or '')
    blocks = scene_blocks(st.session_state.get('scene_blocks') or {})
    if component != 'title' and (set(blocks) != {1, 2, 3, 4} or scene_manuscript(blocks) != manuscript):
        raise ValueError('All four saved scenes must match the manuscript.')
    source_signature = get_text_signature(manuscript)
    report = str(st.session_state.get('project_integrity_report') or '')
    report_signature = str(st.session_state.get('project_integrity_source_signature') or '')
    rows = supabase.table('writersblock_project_drafts').select('id, draft_content').eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').limit(1).execute().data or []
    if len(rows) != 1:
        raise ValueError('The selected saved revision could not be verified.')
    snapshot = json.loads(rows[0].get('draft_content') or '{}')
    if not isinstance(snapshot, dict) or str(snapshot.get('current_project_id') or project_id) != project_id or str(snapshot.get('active_format_id') or '') != active_format or (str(snapshot.get('project_title') or '') != master_title):
        raise ValueError('Saved project identity, title or format does not match.')
    if component != 'title' and (scene_blocks(snapshot.get('scene_blocks') or {}) != blocks or str(snapshot.get('current_draft_output') or '') != manuscript):
        raise ValueError('Saved manuscript has changed. Reload before accepting.')
    if component == 'manuscript':
        approved = wbs_stage4_valid_approvals(snapshot.get('wbs_stage4_scene_approvals'), blocks, manuscript)
        if approved != {1, 2, 3, 4}:
            raise ValueError('Accept the current four-scene manuscript first.')
    if component == 'integrity':
        if not report.strip() or report_signature != source_signature or snapshot.get('project_integrity_report') != report or (snapshot.get('project_integrity_source_signature') != source_signature):
            raise ValueError('Run and save Integrity for the current manuscript before accepting it.')
    record = snapshot.get('wbs_stage4_final_acceptance')
    record = dict(record) if isinstance(record, dict) else {}
    if record.get('project_id') != project_id or record.get('revision_id') != row_id:
        record = {}
    record['project_id'] = project_id
    record['revision_id'] = row_id
    record['title'] = master_title
    if component == 'manuscript':
        record['manuscript_signature'] = source_signature
    else:
        record['integrity_source_signature'] = source_signature
        record['integrity_report_signature'] = get_text_signature(report)
    snapshot['wbs_stage4_final_acceptance'] = record
    changed = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(snapshot, ensure_ascii=False)}).eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').execute()
    if not getattr(changed, 'data', None):
        raise ValueError('Acceptance was not confirmed by the database.')
    st.session_state['wbs_stage4_final_acceptance'] = record
    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(snapshot)
    st.session_state['_wbs_last_saved_project_id'] = project_id
    return True

def wbs_stage4_confirm_and_save_from_checkbox(context, component, widget_key):
    """Save a checked Stage 4 approval immediately, scoped to current V-n.

    The checkbox itself is an explicit writer acceptance; the UI's two red
    buttons remain available for manual re-confirmation. Never generate a
    manuscript, call the AI or insert a new project/revision here.
    """
    get_text_signature = context['get_text_signature']
    st = context['st']
    wbs_stage4_accept_and_save = context['wbs_stage4_accept_and_save']
    wbs_stage4_save_final_acceptance = context['wbs_stage4_save_final_acceptance']
    if not st.session_state.get(widget_key):
        return
    try:
        manuscript = str(st.session_state.get('current_draft_output') or '')
        report = str(st.session_state.get('project_integrity_report') or '')
        if not manuscript.strip() or not report.strip() or st.session_state.get('project_integrity_source_signature') != get_text_signature(manuscript):
            raise ValueError('Run Integrity for the current saved manuscript first.')
        if st.session_state.get('demo_mode'):
            raise ValueError('Saving approvals requires the full edition.')
        if component == 'manuscript':
            approved = wbs_stage4_accept_and_save()
            st.session_state['_wbs_stage4_approved_scenes'] = sorted(approved)
        wbs_stage4_save_final_acceptance(component)
        st.session_state.pop('_wbs_stage4_checkbox_error', None)
        st.session_state['_wbs_stage4_checkbox_notice'] = 'Final manuscript acceptance saved to this revision.' if component == 'manuscript' else 'Integrity Report acceptance saved to this revision.'
    except Exception as exc:
        st.session_state[widget_key] = False
        st.session_state['_wbs_stage4_checkbox_error'] = str(exc)

def wbs_stage4_final_access_ready(context):
    """Stage 5 gate available even before Stage 3 helper definitions are reached.

    Protect every format that uses four exact saved scenes. Legacy non-scene
    formats keep their existing Final Manuscript path.
    """
    get_text_signature = context['get_text_signature']
    st = context['st']
    raw = st.session_state.get('scene_blocks') or {}
    blocks = {}
    if isinstance(raw, dict):
        for key, text in raw.items():
            try:
                number = int(key)
            except (ValueError, TypeError):
                continue
            if number in (1, 2, 3, 4) and isinstance(text, str) and text.strip():
                blocks[number] = text
    manuscript = str(st.session_state.get('current_draft_output') or '')
    exact_four = set(blocks) == {1, 2, 3, 4} and manuscript == '\n\n'.join((blocks[n] for n in range(1, 5)))
    requires_review = True
    if not requires_review:
        return True
    if not exact_four:
        return False
    approval = st.session_state.get('wbs_stage4_scene_approvals') or {}
    if not isinstance(approval, dict):
        return False
    return approval.get('source_signature') == get_text_signature(manuscript) and approval.get('scene_signatures') == {str(n): get_text_signature(blocks[n]) for n in range(1, 5)} and (set(approval.get('approved') or []) == {1, 2, 3, 4})

def wbs_ss_revision_identity(context):
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    st = context['st']
    return (str(st.session_state.get('_wbs_active_saved_session_row_id') or ''), str(get_active_project_id() or ''), str(get_current_user_id() or ''))

def wbs_ss_save_scene_to_current_revision(context, scene_number, scene_text):
    """Explicit user save only; UPDATE exact revision, never create or renumber a revision.

    Reject concurrent/stale changes and mismatched project/format identifiers.
    Only the selected scene and working manuscript are written; siblings are preserved.
    """
    json = context['json']
    st = context['st']
    supabase = context['supabase']
    wbs_save_state_signature = context['wbs_save_state_signature']
    wbs_ss_blocks = context['wbs_ss_blocks']
    wbs_ss_revision_identity = context['wbs_ss_revision_identity']
    wbs_ss_storyline = context['wbs_ss_storyline']
    row_id, project_id, user_id = wbs_ss_revision_identity()
    if not all((row_id, project_id, user_id)):
        raise ValueError('Load the exact saved project revision before saving a scene.')
    if st.session_state.get('active_format_id') != 'short_story':
        raise ValueError('Short Story scene saving cannot be used for another writing format.')
    if scene_number not in range(1, 5) or not str(scene_text).strip():
        raise ValueError('Select a numbered scene containing story text.')
    rows = supabase.table('writersblock_project_drafts').select('id, draft_content, version_number').eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').limit(1).execute().data or []
    if len(rows) != 1:
        raise ValueError('The exact saved revision was not found; nothing was changed.')
    snapshot = json.loads(rows[0].get('draft_content') or '{}')
    if not isinstance(snapshot, dict) or str(snapshot.get('current_project_id') or project_id) != project_id:
        raise ValueError('Saved project identity mismatch; no record was changed.')
    if snapshot.get('active_format_id') != 'short_story':
        raise ValueError('Saved format is not Short Story; no record was changed.')
    saved_outline = str(snapshot.get('plot_outline') or '')
    working_outline = str(st.session_state.get('plot_outline') or '')
    if saved_outline and saved_outline != working_outline:
        raise ValueError('Saved plot architecture differs from the working copy. Reload before saving.')
    stored = wbs_ss_blocks(snapshot.get('scene_blocks') or {})
    previously_assembled = wbs_ss_storyline(stored)
    saved_manuscript = str(snapshot.get('current_draft_output') or '')
    if saved_manuscript.strip() and saved_manuscript.strip() != previously_assembled.strip() and (not str(snapshot.get('wbs_ss_original_manuscript_backup') or '').strip()):
        snapshot['wbs_ss_original_manuscript_backup'] = saved_manuscript
    expected = st.session_state.get('_wbs_ss_db_scene_baseline')
    if expected is None:
        loaded = wbs_ss_blocks(st.session_state.get('_wbs_ss_initial_loaded_blocks') or {})
        if any((loaded.get(i, '') != stored.get(i, '') for i in range(1, 5))):
            raise ValueError('Saved scenes differ from the loaded revision. Reload before saving.')
    elif any((str(expected.get(i, '')) != str(stored.get(i, '')) for i in range(1, 5))):
        raise ValueError('The saved scene data changed elsewhere. Reload to avoid overwriting it.')
    stored[scene_number] = str(scene_text)
    if not saved_outline and working_outline:
        snapshot['plot_outline'] = working_outline
    snapshot['scene_blocks'] = {str(k): v for k, v in sorted(stored.items())}
    if set(stored) == {1, 2, 3, 4}:
        snapshot['current_draft_output'] = wbs_ss_storyline(stored)
    elif not saved_manuscript.strip() or saved_manuscript.strip() == previously_assembled.strip():
        snapshot['current_draft_output'] = wbs_ss_storyline(stored)
    for field in ('project_integrity_report', 'project_integrity_source_signature', 'project_integrity_status'):
        snapshot.pop(field, None)
    updated = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(snapshot, ensure_ascii=False)}).eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').execute()
    if not getattr(updated, 'data', None):
        raise ValueError('The database did not confirm the scene save.')
    st.session_state['_wbs_ss_db_scene_baseline'] = dict(stored)
    st.session_state['_wbs_ss_initial_loaded_blocks'] = dict(stored)
    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(snapshot)
    st.session_state['_wbs_last_saved_project_id'] = str(project_id)
    return stored

def wbs_ss_safe_scene_draft(context, draft, recorded_scene):
    """Never let an empty transient editor buffer conceal existing scene prose.

    Streamlit can retain an empty widget value while a generated or saved scene
    already exists. A blank is not a valid scene save, so restore the intact
    generated/saved text; do not change either the database or V-number here.
    Nonempty edits, including accepted rewrite previews, are kept exactly.
    """
    if not str(draft or '').strip() and str(recorded_scene or '').strip():
        return recorded_scene
    return draft if draft is not None else recorded_scene

def wbs_ss_capture_draft_on_selection_change(context):
    """Keep scene edits in session while navigating, without saving a revision."""
    st = context['st']
    wbs_ss_blocks = context['wbs_ss_blocks']
    wbs_ss_safe_scene_draft = context['wbs_ss_safe_scene_draft']
    old_n = st.session_state.get('_wbs_ss_previous_selection')
    old_widget = st.session_state.get('_wbs_ss_editor_widget_key')
    if old_n in (1, 2, 3, 4) and old_widget and (old_widget in st.session_state):
        buffers = dict(st.session_state.get('_wbs_ss_edit_buffers') or {})
        existing = wbs_ss_blocks(st.session_state.get('scene_blocks') or {}).get(old_n, '')
        buffers[old_n] = wbs_ss_safe_scene_draft(st.session_state[old_widget], existing)
        st.session_state['_wbs_ss_edit_buffers'] = buffers

def wbs_ss_approved_for_final(context):
    get_text_signature = context['get_text_signature']
    st = context['st']
    wbs_ss_blocks = context['wbs_ss_blocks']
    wbs_ss_storyline = context['wbs_ss_storyline']
    wbs_stage4_valid_approvals = context['wbs_stage4_valid_approvals']
    blocks = wbs_ss_blocks(st.session_state.get('scene_blocks') or {})
    if set(blocks) != {1, 2, 3, 4}:
        return False
    if str(st.session_state.get('current_draft_output') or '') != wbs_ss_storyline(blocks):
        return False
    signature = get_text_signature(wbs_ss_storyline(blocks))
    identity = (str(st.session_state.get('_wbs_active_saved_session_row_id') or ''), signature, tuple(((i, get_text_signature(blocks[i])) for i in range(1, 5))))
    persisted = wbs_stage4_valid_approvals(st.session_state.get('wbs_stage4_scene_approvals'), blocks, st.session_state.get('current_draft_output'))
    return persisted == {1, 2, 3, 4} or (st.session_state.get('_wbs_stage4_review_identity') == identity and set(st.session_state.get('_wbs_stage4_approved_scenes') or []) == {1, 2, 3, 4})

def wbs_stage4_approval_record(context, blocks, manuscript):
    """Expected proof of exactly which four scene texts are being accepted."""
    get_text_signature = context['get_text_signature']
    scene_blocks = context['scene_blocks']
    scene_manuscript = context['scene_manuscript']
    actual = scene_blocks(blocks)
    if set(actual) != {1, 2, 3, 4} or scene_manuscript(actual) != str(manuscript or ''):
        raise ValueError('All four original scenes must match the current manuscript before approval.')
    return {'source_signature': get_text_signature(manuscript), 'scene_signatures': {str(n): get_text_signature(actual[n]) for n in range(1, 5)}}

def wbs_stage4_valid_approvals(context, approvals, blocks, manuscript):
    """Only trust approvals for these EXACT scene boundaries and story contents."""
    wbs_stage4_approval_record = context['wbs_stage4_approval_record']
    if not isinstance(approvals, dict):
        return set()
    try:
        proof = wbs_stage4_approval_record(blocks, manuscript)
    except ValueError:
        return set()
    if approvals.get('source_signature') != proof['source_signature'] or approvals.get('scene_signatures') != proof['scene_signatures']:
        return set()
    approved = approvals.get('approved') or []
    if not isinstance(approved, list):
        return set()
    return {int(n) for n in approved if str(n) in {'1', '2', '3', '4'}}

def wbs_stage4_accept_and_save(context, scene_number=None):
    """Accept the complete four-scene story with a SINGLE exact-revision update.

    A numbered scene is supported for backward compatibility, but Stage 4's
    user-facing approval now signs off the entire manuscript at once. The
    original scene text, format, and V-number are never changed here.
    """
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    json = context['json']
    scene_blocks = context['scene_blocks']
    st = context['st']
    supabase = context['supabase']
    wbs_save_state_signature = context['wbs_save_state_signature']
    wbs_stage4_approval_record = context['wbs_stage4_approval_record']
    wbs_stage4_valid_approvals = context['wbs_stage4_valid_approvals']
    number = int(scene_number) if scene_number is not None else None
    if number is not None and number not in (1, 2, 3, 4):
        raise ValueError('Choose a scene from 1 to 4.')
    row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
    project_id = str(get_active_project_id() or '')
    user_id = str(get_current_user_id() or '')
    active_format = 'short_story'
    if not (row_id and project_id and user_id and active_format):
        raise ValueError('Load the exact saved revision before accepting a scene.')
    manuscript = str(st.session_state.get('current_draft_output') or '')
    blocks = scene_blocks(st.session_state.get('scene_blocks') or {})
    proof = wbs_stage4_approval_record(blocks, manuscript)
    query = supabase.table('writersblock_project_drafts').select('id, draft_content, version_number').eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').limit(1).execute()
    rows = getattr(query, 'data', None) or []
    if len(rows) != 1:
        raise ValueError('The selected saved revision was not found. Nothing was saved.')
    snapshot = json.loads(rows[0].get('draft_content') or '{}')
    if not isinstance(snapshot, dict) or str(snapshot.get('current_project_id') or project_id) != project_id or snapshot.get('active_format_id') != active_format:
        raise ValueError('Project or format mismatch; approval was not saved.')
    if scene_blocks(snapshot.get('scene_blocks')) != blocks or str(snapshot.get('current_draft_output') or '') != manuscript:
        raise ValueError('The saved scenes have changed. Reload the revision before accepting.')
    stored = wbs_stage4_valid_approvals(snapshot.get('wbs_stage4_scene_approvals'), blocks, manuscript)
    if number is None:
        stored.update((1, 2, 3, 4))
    else:
        stored.add(number)
    approval = {**proof, 'approved': sorted(stored)}
    snapshot['wbs_stage4_scene_approvals'] = approval
    updated = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(snapshot, ensure_ascii=False)}).eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').execute()
    if not getattr(updated, 'data', None):
        raise ValueError('The saved revision did not confirm this approval.')
    st.session_state['wbs_stage4_scene_approvals'] = approval
    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(snapshot)
    st.session_state['_wbs_last_saved_project_id'] = project_id
    return stored

def wbs_stage4_save_manuscript_corrections(context, edited_blocks, expected_manuscript, expected_blocks):
    """Save all four author-edited scenes into the CURRENT revision in one DB update.

    No AI call, new revision, changed format, generated scene, or Quill change.
    Refuse to overwrite an out-of-date or different project session.
    Existing integrity reviews and approvals remain historical, but are NOT
    valid for revised text until a fresh review and editorial acceptance.
    """
    get_active_project_id = context['get_active_project_id']
    get_current_user_id = context['get_current_user_id']
    json = context['json']
    scene_blocks = context['scene_blocks']
    scene_manuscript = context['scene_manuscript']
    st = context['st']
    supabase = context['supabase']
    wbs_save_state_signature = context['wbs_save_state_signature']
    row_id = str(st.session_state.get('_wbs_active_saved_session_row_id') or '')
    project_id = str(get_active_project_id() or '')
    user_id = str(get_current_user_id() or '')
    active_format = 'short_story'
    if not all((row_id, project_id, user_id, active_format)):
        raise ValueError('Load the exact saved revision before editing the full manuscript.')
    if not isinstance(edited_blocks, dict) or len(edited_blocks) != 4 or {str(k) for k in edited_blocks} != {'1', '2', '3', '4'}:
        raise ValueError('Only the original four scenes can be edited here.')
    original = scene_blocks(expected_blocks)
    revised = scene_blocks(edited_blocks)
    if set(original) != {1, 2, 3, 4} or set(revised) != {1, 2, 3, 4}:
        raise ValueError('Each of the four scenes must contain text. No changes saved.')
    if scene_manuscript(original) != str(expected_manuscript or ''):
        raise ValueError('Scene boundaries no longer match this manuscript. Reload before editing.')
    if scene_blocks(st.session_state.get('scene_blocks') or {}) != original or str(st.session_state.get('current_draft_output') or '') != expected_manuscript:
        raise ValueError('The working story changed since this page opened. Reload and review before saving.')
    if revised == original:
        return False
    result = supabase.table('writersblock_project_drafts').select('id, draft_content, version_number').eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').limit(1).execute()
    rows = getattr(result, 'data', None) or []
    if len(rows) != 1:
        raise ValueError('The selected saved revision could not be verified. Nothing was saved.')
    snapshot = json.loads(rows[0].get('draft_content') or '{}')
    if not isinstance(snapshot, dict) or str(snapshot.get('current_project_id') or project_id) != project_id or str(snapshot.get('active_format_id') or '') != active_format:
        raise ValueError('Saved project identity or format mismatch. Nothing was changed.')
    if scene_blocks(snapshot.get('scene_blocks') or {}) != original or str(snapshot.get('current_draft_output') or '') != expected_manuscript:
        raise ValueError('The saved manuscript has changed elsewhere. Reload before saving corrections.')
    updated_story = scene_manuscript(revised)
    snapshot['scene_blocks'] = {str(n): revised[n] for n in range(1, 5)}
    snapshot['current_draft_output'] = updated_story
    snapshot.pop('wbs_stage4_scene_approvals', None)
    snapshot.pop('wbs_stage4_final_acceptance', None)
    persisted = supabase.table('writersblock_project_drafts').update({'draft_content': json.dumps(snapshot, ensure_ascii=False)}).eq('id', row_id).eq('project_id', project_id).eq('user_id', user_id).eq('draft_type', 'project_session').execute()
    if not getattr(persisted, 'data', None):
        raise ValueError('The database did not confirm the corrections save.')
    st.session_state['scene_blocks'] = dict(revised)
    st.session_state['current_draft_output'] = updated_story
    st.session_state['wbs_stage4_scene_approvals'] = {}
    st.session_state.pop('wbs_stage4_final_acceptance', None)
    st.session_state.pop('_wbs_stage4_approved_scenes', None)
    st.session_state.pop('_wbs_stage4_review_identity', None)
    st.session_state.pop('_wbs_final_saved_proof', None)
    st.session_state.pop('_wbs_ss_edit_buffers', None)
    st.session_state.pop('_wbs_ss_editor_widget_key', None)
    st.session_state.pop('_wbs_ss_rewrite_preview', None)
    st.session_state['_wbs_ss_db_scene_baseline'] = dict(revised)
    st.session_state['_wbs_ss_initial_loaded_blocks'] = dict(revised)
    st.session_state['_wbs_last_saved_work_signature'] = wbs_save_state_signature(snapshot)
    st.session_state['_wbs_last_saved_project_id'] = project_id
    return True

def render_active_format_development_fields(context):
    datetime = context['datetime']
    format_field_should_render = context['format_field_should_render']
    get_active_format_template_values = context['get_active_format_template_values']
    get_active_format_widget_key = context['get_active_format_widget_key']
    re = context['re']
    refresh_quill_template_context = context['refresh_quill_template_context']
    set_active_format_template_value = context['set_active_format_template_value']
    st = context['st']
    template = st.session_state.get('active_format_template') or {}
    fields = [f for f in template.get('concept_fields') or [] if isinstance(f, dict)]
    if not fields:
        return
    shared_keys = {'project_title', 'dialogue_style', 'story_premise', 'premise', 'logline', 'story_idea', 'objective', 'core_premise'}
    values = get_active_format_template_values()
    render_fields = [f for f in fields if str(f.get('key')) not in shared_keys and format_field_should_render(f, values)]
    if not render_fields:
        return
    setup_name = str(template.get('display_name') or st.session_state.get('quill_format_name') or 'Format').strip()
    st.markdown(f'### {setup_name} Development Setup')
    st.caption(str(template.get('description') or ''))
    for i in range(0, len(render_fields), 2):
        row = render_fields[i:i + 2]
        cols = st.columns(2, gap='medium')
        for col, field in zip(cols, row):
            key = str(field.get('key') or '').strip()
            if not key:
                continue
            label = str(field.get('label') or key)
            help_text = str(field.get('help') or '') or None
            widget_key = get_active_format_widget_key(key)
            existing = values.get(key, '')
            with col:
                if field.get('type') == 'select':
                    options = list(field.get('options') or [])
                    if 'author' in key.lower() or 'author' in label.lower() or key == 'production_influence' or ('writing influence' in label.lower()):
                        if 'Arthur C. Clarke' not in options:
                            custom_index = next((i for i, item in enumerate(options) if 'custom' in str(item).lower() or 'other' == str(item).strip().lower()), len(options))
                            options.insert(custom_index, 'Arthur C. Clarke')
                    if ('genre' in key.lower() or 'genre' in label.lower()) and 'Spiritual' not in options:
                        options.append('Spiritual')
                    if key == 'production_influence':
                        custom_option = 'Custom Influence / Other'
                        if custom_option not in options:
                            options.append(custom_option)
                    age_field = False
                    if age_field:
                        options = list(dict.fromkeys(options + ['0-2', '2-5', '3-8', '5-9', '6-10', '8-12', 'Custom age range']))
                    if not options:
                        continue
                    chosen_age = existing
                    if age_field and existing not in options and str(existing).strip():
                        chosen_age = 'Custom age range'
                    index = options.index(chosen_age) if chosen_age in options else 0
                    value = st.selectbox(label, options, index=index, key=widget_key, help=help_text)
                    if age_field and value == 'Custom age range':
                        from_age, to_age = st.columns(2)
                        found = re.search('(\\d+)\\s*[-–]\\s*(\\d+)', str(existing or ''))
                        start_age = int(found.group(1)) if found else 3
                        end_age = int(found.group(2)) if found else 8
                        with from_age:
                            lower_age = st.number_input('From age', 0, 18, start_age, key=f'{widget_key}_from')
                        with to_age:
                            upper_age = st.number_input('To age', 0, 18, end_age, key=f'{widget_key}_to')
                        if lower_age > upper_age:
                            st.warning('The ending age must be at least the starting age.')
                            value = str(existing or '')
                        else:
                            value = f'{lower_age}-{upper_age}'
                elif field.get('type') == 'date':
                    try:
                        existing_date = datetime.strptime(str(existing), '%Y-%m-%d').date() if existing else datetime.now().date()
                    except Exception:
                        existing_date = datetime.now().date()
                    selected_date = st.date_input(label, value=existing_date, key=widget_key, help=help_text)
                    value = selected_date.isoformat() if selected_date else ''
                elif field.get('type') == 'textarea':
                    value = st.text_area(label, value=str(existing or ''), height=95, key=widget_key, help=help_text)
                else:
                    value = st.text_input(label, value=str(existing or ''), key=widget_key, help=help_text)
                set_active_format_template_value(key, value)
                if key == 'production_influence':
                    custom_key = 'production_influence_custom'
                    custom_option = 'Custom Influence / Other'
                    if value == custom_option:
                        custom_widget_key = get_active_format_widget_key(custom_key)
                        custom_existing = values.get(custom_key, '')
                        custom_value = st.text_input('Custom Influence', value=str(custom_existing or ''), key=custom_widget_key, help='Enter an author, director, playwright, filmmaker, or creative style not listed above.', placeholder='Enter the influence you want WritersBlock to use')
                        set_active_format_template_value(custom_key, custom_value)
                        st.session_state.author_style = str(custom_value or '').strip()
                    else:
                        set_active_format_template_value(custom_key, '')
                        st.session_state.author_style = str(value or '').strip()
                elif key == 'visual_style':
                    st.session_state.author_style = str(value or '')
                elif key == 'narration_type':
                    st.session_state.author_style = f'Narration Type: {value}' if value else ''
    refresh_quill_template_context()

def render_format_template_save_reminder(context):
    """One master Save Project, then non-destructive new versions (all formats)."""
    full_version_only_notice = context['full_version_only_notice']
    get_project_title = context['get_project_title']
    render_save_as_named_version_control = context['render_save_as_named_version_control']
    save_current_project_session_to_supabase = context['save_current_project_session_to_supabase']
    st = context['st']
    wbs_has_saved_master = context['wbs_has_saved_master']
    st.markdown('---')
    with st.container(border=True):
        if st.session_state.get('demo_mode'):
            st.caption('Project saving is available in the full Writer Edition.')
            if st.button('💾 Save Project 🔒', key='template_save_project_trial', use_container_width=True):
                full_version_only_notice('Saved Projects')
            return
        has_master = wbs_has_saved_master()
        if has_master is None:
            st.warning("Cannot verify this project's save history. Saving is disabled until the connection is restored.")
        elif has_master:
            render_save_as_named_version_control(f"concept_{st.session_state.get('active_format_id', 'format')}")
        elif st.button('💾 Save Project — Create Master', key=f"template_save_project_{st.session_state.get('active_format_id', 'format')}", use_container_width=True, type='secondary'):
            if not get_project_title():
                st.warning('Name the new project before saving.')
                return
            result = save_current_project_session_to_supabase()
            if result and (not getattr(result, 'unchanged', False)):
                st.success('Master project saved. Future changes are new versions.')
                st.rerun()
