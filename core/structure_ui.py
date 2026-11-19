"""Shared presentation/persistence services; terminology is format-owned."""
from copy import deepcopy
import html
import json
from core.manuscript_structure import profile,values,unit_plan,blocks,canonical_plan,commit,approved,pending_edits,unit_heading,KEY


def widget_key(state,name):
    return 'format_field_structure_'+'_'.join(str(x) for x in (
        state['active_format_id'],state.get('current_project_id') or 'new',
        state.get('_wbs_active_saved_session_row_id') or 'draft',name))


def project_header(context):
    st=context['st'];state=st.session_state;revision=None
    project=state.get('current_project_id');row=state.get('_wbs_active_saved_session_row_id')
    if project and row:
        try:
            rows=context['supabase'].table('writersblock_project_drafts').select('version_number,draft_content').eq(
                'id',row).eq('project_id',project).eq('user_id',context['get_current_user_id']()).eq(
                'draft_type','project_session').limit(1).execute().data or []
            if len(rows)==1 and json.loads(rows[0]['draft_content']).get('active_format_id')==state['active_format_id']:
                revision=rows[0]['version_number']
        except (KeyError,ValueError,TypeError,RuntimeError):pass
    label='V-'+str(revision) if revision is not None else 'Unsaved' if not project else 'Revision unverified'
    st.markdown('<div class="wbs-stage-project-identity" style="font-size:1.2rem;font-weight:700;margin-bottom:.6rem">'
        +html.escape(str(state.get('project_title') or 'Untitled Project'))+' &nbsp;|&nbsp; '+html.escape(label)+'</div>',unsafe_allow_html=True)
    context['_wbs_display_revision']=revision


def preferences(context):
    st=context['st'];state=st.session_state;fmt=state['active_format_id'];spec=profile(fmt)
    if fmt=='short_story':return
    with st.expander('Format organization — '+spec['plural'],expanded=False):
        st.caption(spec['description'])
        current=values(state);prefs=deepcopy(current.get('structure_preferences') or {})
        if spec['group']:
            prefs['group_target']=st.number_input('Planned '+spec['group'].lower()+' count (optional)',min_value=0,max_value=None if fmt=='novel_prose_novella' else 1000,
                value=int(prefs.get('group_target') or 0),key=widget_key(state,'group_target'))
        prefs['unit_target']=st.number_input('Planned '+spec['plural'].lower()+' (optional)',min_value=0,max_value=None if fmt=='novel_prose_novella' else 10000,
            value=int(prefs.get('unit_target') or 0),key=widget_key(state,'unit_target'))
        st.caption('Zero means unspecified. Targets do not create text, change completed counts or renumber saved writing.')
        if any(prefs.values()) or current.get('structure_preferences'):
            current['structure_preferences']=prefs
            state['format_template_values']={**(state.get('format_template_values') or {}),fmt:current}


def editor(context):
    st=context['st'];state=st.session_state;spec=profile(state['active_format_id'])
    if not spec['structured_editor'] or not state.get('current_project_id'):return False
    if state.get(widget_key(state,'legacy_tools')):return _editor(context)
    from core.extended_concept import LAYOUT_STYLE
    st.markdown(LAYOUT_STYLE,unsafe_allow_html=True)
    main,quill=st.columns([2.65,1.15],gap='large')
    with main:_editor(context)
    with quill:
        st.markdown('<div class="wbs-writer-quill-sticky-anchor"></div>',unsafe_allow_html=True)
        from core.format_services import coach
        coach(context)
    return True


def _editor(context):
    st=context['st'];state=st.session_state;spec=profile(state['active_format_id'])
    if spec.get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turn_ui import editor as page_editor
        page_editor(context);return True
    if not spec['structured_editor']:return False
    legacy=widget_key(state,'legacy_tools')
    if state.get(legacy):
        if st.button('Return to '+spec['plural'].lower()+' editor',key=widget_key(state,'return_editor')):
            state[legacy]=False;st.rerun()
        return False
    if not state.get('current_project_id'):return False
    st.header('3. '+(spec['group']+'s / ' if spec['group'] else '')+spec['plural']+' — Writing and Organization')
    st.caption(spec['description'])
    plan_key=widget_key(state,'working_plan')
    if spec['unit']=='Page':st.caption('Enter [PAGE TURN] in page text or Page turn notes. Markers are preserved in exports and never split or renumber the approved page plan automatically.')
    if plan_key not in state:state[plan_key]=unit_plan(state) or [dict(unit_id=1,group_number=1,group_title='',unit_number=1,title=spec['unit']+' 1',detail='')]
    rows=st.data_editor(deepcopy(state[plan_key]),num_rows='dynamic',hide_index=True,key=widget_key(state,'plan_editor'),
        column_config={'unit_id':'Saved text ID (stable)','group_number':(spec['group'] or 'Group')+' number',
                       'group_title':(spec['group'] or 'Group')+' title','unit_number':spec['unit']+' number',
                       'title':spec['unit']+' title','detail':spec['detail']},
        column_order=['unit_id']+(['group_number','group_title'] if spec['group'] else [])+['unit_number','title','detail'])
    if hasattr(rows,'to_dict'):rows=rows.to_dict('records')
    state[plan_key]=rows
    st.caption('Saved text IDs stay fixed. Grouping and beat/page-turn notes never rewrite text or Plot A/B/C. Add planned rows explicitly; incomplete units do not count as completed writing.')
    try:plan=canonical_plan(state,rows)
    except (ValueError,TypeError) as exc:
        st.warning(str(exc));plan=[]
    if st.button('Save Organization Settings',key=widget_key(state,'save_plan'),disabled=not bool(plan)):
        try:commit(context,plan)
        except (ValueError,RuntimeError) as exc:st.error(str(exc))
        else:st.success('Organization saved to this revision. Manuscript and selected plot preserved.')
    if plan:
        from core.manuscript_structure import export_plan
        st.download_button('Download Organization Plan (.txt)',data=export_plan(state,plan),
            file_name=state['active_format_id']+'_organization_plan.txt',mime='text/plain',key=widget_key(state,'plan_download'))
        if spec['group']:
            groups=sorted({r['group_number'] for r in plan})
            titles={r['group_number']:r['group_title'] for r in plan}
            group=st.selectbox(spec['group'],groups,format_func=lambda n:spec['group']+' '+str(n)+(' — '+titles[n] if titles[n] else ''),key=widget_key(state,'group_selected'))
            available=[r for r in plan if r['group_number']==group]
        else:available=plan
        by_id={r['unit_id']:r for r in available}
        selected=st.selectbox(spec['unit'],list(by_id),format_func=lambda n:unit_heading(spec,by_id[n]),key=widget_key(state,'unit_selected'))
        buffers_key=widget_key(state,'text_buffers');buffers=deepcopy(state.get(buffers_key) or {})
        writing=blocks(state)
        from core.image_editor import edit as image_edit
        text=image_edit(context,selected,buffers.get(selected,writing.get(selected,state.get('current_draft_output','') if not writing else '')),widget_key(state,'text_'+str(selected)),spec['unit']+' text')
        buffers[selected]=text;state[buffers_key]=buffers
        if st.button('Save '+spec['unit']+' to Current Revision',key=widget_key(state,'save_unit')):
            try:
                commit(context,plan,edit=(selected,text))
                remaining=any(str(t)!=str(blocks(state).get(int(n),'')) for n,t in buffers.items())
                if not remaining:
                    try:canonical_plan(state,plan,complete=True)
                    except ValueError:pass
                    else:context['wbs_request_stage_change']('Isolation Guardrail',export_view=False)
                st.success('Saved to this revision; incomplete or unsaved units remain in the editor.')
            except (ValueError,RuntimeError) as exc:st.error(str(exc))
        if st.button('Approve And Save Completed '+spec['plural'],key=widget_key(state,'save_complete'),type='primary'):
            try:
                if any(str(t)!=str(writing.get(int(n),'')) for n,t in buffers.items()):
                    raise ValueError('Save each edited text unit before approving the completed manuscript.')
                canonical_plan(state,plan,complete=True)
                commit(context,plan)
                context['wbs_request_stage_change']('Isolation Guardrail',export_view=False)
            except (ValueError,RuntimeError) as exc:st.error(str(exc))
    if st.button('Open existing storyline / writing-engine tools',key=widget_key(state,'open_legacy')):
        state[legacy]=True;st.rerun()
    return True


def review(context):
    st=context['st']
    if not profile(st.session_state['active_format_id'])['structured_editor']:return False
    from core.extended_concept import LAYOUT_STYLE
    st.markdown(LAYOUT_STYLE,unsafe_allow_html=True)
    main,quill=st.columns([2.65,1.15],gap='large')
    with main:_review(context)
    with quill:
        st.markdown('<div class="wbs-writer-quill-sticky-anchor"></div>',unsafe_allow_html=True)
        from core.format_services import coach
        coach(context)
    return True


def _review(context):
    st=context['st'];state=st.session_state;spec=profile(state['active_format_id'])
    if not spec['structured_editor']:return False
    st.header('4. '+spec['plural']+' — Editorial Review and Integrity')
    st.caption(spec['description'])
    try:
        plan=canonical_plan(state,unit_plan(state),complete=True)
        from core.manuscript_structure import page_writing
        writing=page_writing(state)
        if '\n\n'.join(writing[n] for n in sorted(writing))!=str(state.get('current_draft_output') or ''):
            raise ValueError('The saved text units do not match the manuscript. No text was changed.')
    except (ValueError,TypeError) as exc:
        st.warning(str(exc));plan=[]
    if spec.get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import render_pages
        render_pages(st,state)
    else:
        from core.publication_layout import render_preview
        if state['active_format_id']=='novel_prose_novella':
            from core.image_placement import controls
            from core.publication_layout import anchors
            controls(context,anchors(state))
        render_preview(st,state)
    st.caption('Structure checks use every planned '+spec['unit'].lower()+', not an assumed four-scene or novel-chapter count.')
    pending=pending_edits(state)
    if pending:st.warning('Unsaved text edits are retained in the editor. Save them before approving this revision.')
    if st.button('Return to '+spec['plural'].lower()+' editing',key=widget_key(state,'back_to_edit')):
        context['wbs_request_stage_change']('Plot Architect',export_view=False)
    if st.button('Run Project Integrity Report',key='run_project_integrity_final_review'):
        try:
            from core.integrity_review import run
            run(context)
            st.rerun()
        except Exception:st.error('Integrity review failed or could not be saved. Approval remains blocked; retry when the review service is available.')
    if state.get('project_integrity_report'):
        report=state['project_integrity_report']
        if spec.get('explicit_page_turns'):
            from formats.childrens_picture_book.page_turns import TOKEN
            report=TOKEN.sub('\n\n---\n\n',report)
        st.markdown(report)
    title_ok=st.checkbox('I confirm the saved project title.',key=widget_key(state,'accept_title'))
    text_ok=st.checkbox('I reviewed all '+spec['plural'].lower()+' and the complete manuscript.',key=widget_key(state,'accept_text'))
    required=context['project_integrity_review_applies']()
    from core.integrity_review import ready
    valid_integrity=ready(state,required=required)
    if not valid_integrity:st.warning('Integrity validation is missing, failed, stale or unsaved. Approval remains blocked; any older report shown above is not current approval evidence.')
    integrity_ok=st.checkbox('I accept the current Integrity Report.',key=widget_key(state,'accept_integrity')) if required else True
    if st.button('Approve And Save Editorial Review',key=widget_key(state,'accept_review'),disabled=not bool(plan and title_ok and text_ok and integrity_ok and valid_integrity and not pending),type='primary'):
        try:commit(context,plan,accept=True)
        except (ValueError,RuntimeError) as exc:st.error(str(exc))
        else:
            from core.stage_navigation import after_approval
            after_approval(context,4)
    return True
