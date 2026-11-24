"""Neutral services for new format workspaces; no sibling format implementations."""
from copy import deepcopy
from importlib import import_module
import hashlib
import json


def data(state, fmt):
    if state.get('active_format_id') != fmt: raise ValueError('Cross-format state access refused')
    values=state.get('format_template_values') or {}
    if not isinstance(values,dict) or not isinstance(values.get(fmt,{}) or {},dict):raise ValueError('Format state must be a record')
    return deepcopy(values.get(fmt) or {})


def put_data(state, fmt, values):
    data(state, fmt)
    state['format_template_values'] = {**(state.get('format_template_values') or {}), fmt: deepcopy(values)}


def key(context, fmt, name):
    state=context['st'].session_state
    return 'format_field_ext_' + '_'.join(str(v) for v in (fmt,state.get('current_project_id') or 'new',state.get('_wbs_active_saved_session_row_id') or 'draft',name))


def edit_fields(context, fmt, fields, columns=1):
    st=context['st'];values=data(st.session_state,fmt)
    def render_field(field):
        name=field['key'];options=field.get('options') or []
        value=st.session_state.get('project_title','') if name=='project_title' else values.get(name,field.get('default',options[0] if options else ''))
        label=field['label'];widget=key(context,fmt,name)
        if field['type']=='select':
            value=st.selectbox(label,options,index=options.index(value) if value in options else 0,key=widget)
        elif field['type']=='text':value=st.text_input(label,value=value or '',key=widget)
        else:value=st.text_area(label,value=value or '',key=widget)
        if name=='project_title':
            if not st.session_state.get('current_project_id'):st.session_state['project_title']=value
            elif value!=st.session_state.get('project_title'):
                st.caption('Use the existing project rename control to change a saved master title.')
        else:values[name]=value
    for start in range(0,len(fields),columns):
        group=fields[start:start+columns]
        if columns==1:
            for field in group:render_field(field)
        else:
            for column,field in zip(st.columns(columns,gap='medium'),group):
                with column:render_field(field)
    put_data(st.session_state,fmt,values)


def edit_table(context,fmt,name,label,columns):
    st=context['st'];values=data(st.session_state,fmt);rows=values.get(name) or []
    st.subheader(label)
    if not isinstance(rows,list):
        st.warning('This saved table is invalid. Its value was preserved; repair it before saving.');return
    edited=st.data_editor(deepcopy(rows) if isinstance(rows,list) and rows else [dict.fromkeys(columns,'')],
                          num_rows='dynamic',key=key(context,fmt,name),hide_index=True)
    if edited is not None:
        if hasattr(edited,'to_dict'):edited=edited.to_dict('records')
        values[name]=[{k:('' if v is None else v) for k,v in row.items()} for row in edited
                      if isinstance(row,dict) and any(str(v or '').strip() for v in row.values())]
        put_data(st.session_state,fmt,values)


def coach(context):
    refresh=context.get('refresh_quill_template_context')
    if refresh:refresh()
    if context['st'].session_state.get('active_format_id') in {'biography_memoir','childrens_interactive_educational'}:
        from core.extended_quill import render
        return render(context)
    render=context.get('render_quill_for_current_stage')
    if render:return render(st_module=context['st'],show_prelude=True)


def save_checkpoint(context,fmt,unlock=None):
    from core.registry import get_format
    st=context['st'];snapshot=dict(st.session_state)
    if st.session_state.get('demo_mode'):
        st.warning('Project saving is available in the full Writer Edition.');return False
    errors=get_format(fmt).validate_snapshot(snapshot)
    if errors:
        for error in errors:st.warning(error)
        return False
    before=data(st.session_state,fmt)
    if unlock:
        updated=deepcopy(before);updated['stage_unlocked']=max(int(before.get('stage_unlocked') or 1),unlock)
        put_data(st.session_state,fmt,updated)
    try:
        result=context['save_current_project_session_to_supabase']()
    except Exception as exc:
        st.error('Project save was not confirmed: '+str(exc))
        result=None
    if not result:
        # Keep author edits in memory; a failed write must not grant a new stage.
        current=data(st.session_state,fmt)
        if unlock:
            if 'stage_unlocked' in before:current['stage_unlocked']=before['stage_unlocked']
            else:current.pop('stage_unlocked',None)
            put_data(st.session_state,fmt,current)
        return False
    if unlock:st.session_state['_wbs_unlocked_saved_stage']=max(int(st.session_state.get('_wbs_unlocked_saved_stage') or 1),min(unlock,5))
    st.success('Saved to the current project revision. Use Save As New Version to create a branch.')
    return True


def advance(context,target,export=False):
    context['wbs_request_stage_change'](target,export_view=export)


def save_scene(context,fmt,number,text):
    from core.registry import get_format
    from core.saved_scene_state import saved_snapshot_for_session
    if not str(text or '').strip():raise ValueError('A saved chapter or unit must contain author text.')
    state=context['st'].session_state
    adapter=get_format(fmt);blocks=adapter.completed_scenes(state)
    scenes=import_module(f'formats.{fmt}.scenes')
    existing=str(state.get('current_draft_output') or '')
    if existing and existing!=scenes.manuscript(blocks):
        if blocks or str(text)!=existing:
            raise ValueError('Existing manuscript text is not mapped to these units. Map it unchanged before editing so no writing is discarded.')
    saved=saved_snapshot_for_session(state)
    if state.get('_wbs_active_saved_session_row_id') and saved.get('current_project_id'):
        # Existing save API preserves version numbering; refuse identity changes.
        if saved.get('active_format_id')!=fmt:raise ValueError('The saved revision belongs to another format.')
    original_blocks=deepcopy(state.get('scene_blocks') or {})
    blocks[int(number)]=str(text)
    state['scene_blocks']=blocks;state['current_draft_output']=scenes.manuscript(blocks)
    if not save_checkpoint(context,fmt,4):
        state['scene_blocks']=original_blocks;state['current_draft_output']=existing
        return False
    return True


def approval_signature(snapshot,fmt):
    values=data(snapshot,fmt)
    for name in ('editorial_approval','stage_unlocked'):values.pop(name,None)
    blocks={str(k):v for k,v in (snapshot.get('scene_blocks') or {}).items()}
    packet=dict(format_id=fmt,project=snapshot.get('current_project_id'),title=snapshot.get('project_title'),
                values=values,scenes=blocks,manuscript=snapshot.get('current_draft_output'),
                approved_plan=snapshot.get('chosen_option_text'),outline=snapshot.get('plot_outline'),
                concept={name:snapshot.get(name) or '' for name in ('story_seed','tone_style','dialogue_style','author_style','project_scope','series_name')},
                starting_source=selected_source(snapshot))
    return hashlib.sha256(json.dumps(packet,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def approved_saved(state,fmt):
    from core.saved_scene_state import saved_snapshot_for_session
    try:
        saved=saved_snapshot_for_session(state);proof=data(saved,fmt).get('editorial_approval') or {}
        return bool(state.get('_wbs_active_saved_session_row_id') and proof.get('revision_id')==str(state.get('_wbs_active_saved_session_row_id'))
                    and proof.get('signature')==approval_signature(saved,fmt)==approval_signature(state,fmt))
    except (ValueError,TypeError,AttributeError):return False


def approve(context,fmt):
    from core.registry import get_format
    state=context['st'].session_state
    from core.integrity_review import ready
    if not ready(state,required=context['project_integrity_review_applies']()):
        context['st'].warning('Run and save a successful Integrity Report before approval.');return False
    errors=get_format(fmt).validate_snapshot(dict(state),for_export=True)
    if errors:
        for error in errors:context['st'].warning(error)
        return False
    row_id=state.get('_wbs_active_saved_session_row_id')
    if not row_id:
        context['st'].warning('Save and load an identified revision before editorial acceptance.');return False
    before=data(state,fmt);candidate=deepcopy(before)
    candidate['editorial_approval']={'revision_id':str(row_id),'signature':approval_signature(dict(state),fmt)}
    put_data(state,fmt,candidate)
    if not save_checkpoint(context,fmt,5):put_data(state,fmt,before);return False
    return True


def show_errors(context,errors):
    for error in errors:context['st'].warning(error)
    if not errors:context['st'].success('Local validation passed. This does not certify external factual accuracy.')


def select_format(context,fmt):
    from template_registry import FORMAT_OPTIONS,get_template,get_quill_instructions,get_format_display_name
    from wbs_format_guard import FORMAT_LEGACY
    st=context['st'];state=st.session_state
    if 'wbs_format_template_selector' not in state:state['wbs_format_template_selector']=fmt
    control,spacer=st.columns([1.6,1.25],gap='small')
    with control:
        if state.get('current_project_id'):
            st.markdown('**'+get_format_display_name(fmt)+'**');return
        options=[name for name,_ in FORMAT_OPTIONS]
        selected=st.selectbox('Choose Writing Format',options,index=options.index(fmt),format_func=get_format_display_name,key='wbs_format_template_selector',label_visibility='collapsed')
    if selected!=fmt:
        state.update(active_format_id=selected,format_type=FORMAT_LEGACY[selected],
            active_format_template=get_template(selected),quill_format_instructions=get_quill_instructions(selected),
            quill_format_name=get_format_display_name(selected))
        st.rerun()


def selected_source(snapshot):
    mode=snapshot.get('version_source_mode') or snapshot.get('starting_source_mode') or 'Custom Plot Line'
    if mode=='Saved Manuscript':text=snapshot.get('saved_version_source_text') or ''
    elif mode in {'Replacement Draft / Manuscript','Existing Draft / Manuscript'}:text=snapshot.get('imported_source_text') or ''
    else:text=snapshot.get('story_seed') or ''
    return {'mode':mode,'text':text}
