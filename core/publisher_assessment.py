"""Read-only publisher assessment service for the restored Stage 5 dependency.

Uses the existing revision-report engine. Stores assessment artifacts separately;
never changes a project session, manuscript, scene, approved plot or V-number.
"""
import json
from core.text import get_text_signature
from template_registry import FORMAT_REGISTRY


def read_saved_revision(client, project_id, user_id, revision_id, format_id):
    if not all((project_id, user_id, revision_id)) or format_id not in FORMAT_REGISTRY:
        raise ValueError('Load an identified saved revision before assessment.')
    rows = (client.table('writersblock_project_drafts').select('*')
            .eq('id', str(revision_id)).eq('project_id', str(project_id))
            .eq('user_id', str(user_id)).eq('draft_type', 'project_session')
            .limit(1).execute()).data or []
    if len(rows) != 1:
        raise ValueError('The exact saved revision could not be verified.')
    snapshot = json.loads(rows[0].get('draft_content') or '{}')
    if (not isinstance(snapshot, dict) or snapshot.get('active_format_id') != format_id
            or str(snapshot.get('current_project_id') or project_id) != str(project_id)):
        raise ValueError('Saved format or project identity does not match.')
    source = snapshot.get('current_draft_output') or ''
    if not isinstance(source, str) or not source.strip():
        raise ValueError('The saved revision has no manuscript to assess.')
    return rows[0], snapshot, source


def create_assessment(client, backend, *, project_id, user_id, revision_id,
                      format_id, format_name, expected_source):
    row, snapshot, source = read_saved_revision(client, project_id, user_id, revision_id, format_id)
    if source != expected_source:
        raise ValueError('The saved manuscript changed. Reload before assessment.')
    if backend is None:
        raise ValueError('The existing writing engine is unavailable.')
    mode = (f'Publisher and Market Readiness Assessment for {format_name}. '
            'Report only; never rewrite, extend or replace manuscript text. '
            'Assess audience and category fit, structure, originality, presentation, '
            'strengths, submission readiness and concrete next steps for this format. '
            'Separate evidence in the manuscript from uncertain market judgments. '
            'Do not invent sales figures, guarantees, publisher interest or quotations.')
    report = backend.run_revision_pass(source, mode, snapshot.get('tone_style') or '', snapshot.get('author_style') or '')
    if not isinstance(report, str) or not report.strip() or 'LOCAL FALLBACK' in report.upper():
        raise ValueError('No usable publisher assessment was returned. Nothing was saved.')
    # Verify exact text and version once more before storing the separate artifact.
    current, _, current_source = read_saved_revision(client, project_id, user_id, revision_id, format_id)
    if current_source != source or current.get('version_number') != row.get('version_number'):
        raise ValueError('The saved revision changed during assessment. Nothing was saved.')
    artifact = dict(format_id=format_id, revision_id=str(revision_id),
                    source_signature=get_text_signature(source), report=report,
                    version_number=row.get('version_number'))
    result = client.table('writersblock_project_drafts').insert({
        'project_id': str(project_id), 'user_id': str(user_id),
        'draft_type': 'publisher_assessment',
        'version_number': row['version_number'],
        'draft_title': f'Publisher Assessment — {format_name}',
        'draft_content': json.dumps(artifact, ensure_ascii=False),
    }).execute()
    if not getattr(result, 'data', None):
        raise RuntimeError('The database did not confirm the assessment save.')
    return artifact


def render_stage5(st, *, supabase, backend, project_id, user_id, title,
                  revision_id, format_id, format_name, on_saved=None):
    st.header('5. Publisher & Market Readiness')
    st.caption(f'{format_name} · Optional assessment of the saved editorial revision')
    try:
        _, _, source = read_saved_revision(supabase, project_id, user_id, revision_id, format_id)
        if source != str(st.session_state.get('current_draft_output') or ''):
            raise ValueError('The open manuscript differs from its saved revision. Save or reload before assessment.')
        # Visiting this verified revision unlocks the optional next stage. An
        # assessment report is not mandatory, and this proof expires on edits.
        passport = (str(project_id), str(revision_id), get_text_signature(source))
        if st.session_state.get('_wbs_stage5_passport') != passport:
            st.session_state['_wbs_stage5_passport'] = passport
            st.rerun()
        rows = (supabase.table('writersblock_project_drafts').select('*')
                .eq('project_id', str(project_id)).eq('user_id', str(user_id))
                .eq('draft_type', 'publisher_assessment').execute()).data or []
        for row in reversed(rows):
            try:
                item = json.loads(row.get('draft_content') or '{}')
            except (ValueError, TypeError):
                continue
            if (isinstance(item, dict) and item.get('format_id') == format_id
                    and item.get('revision_id') == str(revision_id)
                    and item.get('source_signature') == get_text_signature(source)):
                st.markdown(item.get('report') or '')
                break
        if st.button('Generate And Save Publisher Assessment', key=f'wbs_publisher_assess_{format_id}_{revision_id}',
                     disabled=bool(st.session_state.get('demo_mode')), use_container_width=True):
            artifact = create_assessment(supabase, backend, project_id=project_id,
                user_id=user_id, revision_id=revision_id, format_id=format_id,
                format_name=format_name, expected_source=source)
            st.markdown(artifact['report'])
            st.success('Publisher assessment saved for this revision.')
            if on_saved:on_saved()
        if on_saved and st.button('Skip Optional Assessment — Final Manuscript',key='wbs_skip_optional_assessment',use_container_width=True):
            on_saved()
    except Exception as exc:
        st.warning(str(exc))
