"""Format-owned organization over existing saved text IDs. Never generate prose."""
from copy import deepcopy
from importlib import import_module
import hashlib
import json

KEY='manuscript_structure'
PROOF='structure_editorial_approval'


def profile(fmt):
    from core.registry import get_format
    get_format(fmt)
    return deepcopy(import_module('formats.'+fmt+'.structure').PROFILE)


def values(snapshot):
    from core.project_state import active_format_id
    return deepcopy((snapshot.get('format_template_values') or {}).get(active_format_id(snapshot)) or {})


def blocks(snapshot):
    from core.project_state import completed_scene_blocks
    return completed_scene_blocks(snapshot)


def page_writing(snapshot):
    from formats.childrens_picture_book.page_turns import active,pages,author_source
    if active(snapshot):return dict(enumerate(pages(author_source(snapshot)),1))
    return blocks(snapshot)


def configured(snapshot):
    return bool(values(snapshot).get(KEY))


def positive(value):
    if isinstance(value,bool):raise ValueError('Numbers must be positive integers.')
    number=int(value)
    if number<1 or str(value).strip() not in (str(number),str(number)+'.0'):
        raise ValueError('Numbers must be positive integers.')
    return number


def unit_plan(snapshot):
    existing=values(snapshot).get(KEY)
    fmt=snapshot['active_format_id'];spec=profile(fmt)
    if existing:
        if not isinstance(existing,dict) or existing.get('format_id')!=fmt:
            raise ValueError('Structure belongs to another writing format.')
        return deepcopy(existing.get('units') or [])
    result=[]
    for index,n in enumerate(sorted(blocks(snapshot)),1):
        per_group=spec.get('legacy_group_per_unit')
        result.append(dict(unit_id=n,group_number=index if per_group else 1,
            group_title='',unit_number=1 if per_group else index,
            title=spec['unit']+' '+str(1 if per_group else index),detail=''))
    return result


def canonical_plan(snapshot,rows,complete=False,writing=None):
    spec=profile(snapshot['active_format_id'])
    if not spec['structured_editor']:raise ValueError('This format retains its existing structure workflow.')
    if not isinstance(rows,list) or not rows:raise ValueError('Add at least one '+spec['unit'].lower()+'.')
    result=[];ids=set();locations=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Structure rows must be records.')
        n=positive(row.get('unit_id'));group=positive(row.get('group_number',1));position=positive(row.get('unit_number'))
        if not spec['group'] and group!=1:raise ValueError('This format uses pages without chapter groups.')
        if n in ids or (group,position) in locations:raise ValueError('Text IDs and positions must be unique.')
        ids.add(n);locations.add((group,position))
        result.append(dict(unit_id=n,group_number=group,group_title=str(row.get('group_title') or ''),
            unit_number=position,title=str(row.get('title') or spec['unit']+' '+str(position)),detail=str(row.get('detail') or '')))
    result.sort(key=lambda r:r['unit_id'])
    for group in {r['group_number'] for r in result}:
        titles={r['group_title'].strip() for r in result if r['group_number']==group and r['group_title'].strip()}
        if len(titles)>1:raise ValueError('A '+str(spec['group'] or 'page group').lower()+' cannot have conflicting titles.')
        title=next(iter(titles),'')
        for row in result:
            if row['group_number']==group:row['group_title']=title
    if [(r['group_number'],r['unit_number']) for r in result]!=sorted(locations):
        raise ValueError('Grouping must retain the saved text order; no manuscript was reordered.')
    saved=page_writing(snapshot) if writing is None else writing
    if spec.get("explicit_page_turns"):
        from formats.childrens_picture_book.page_turns import active
        if active(snapshot):
            actual={int(n):text for n,text in (snapshot.get("scene_blocks") or {}).items()}
            if actual!=page_writing(snapshot) or "\n\n".join(actual[n] for n in sorted(actual))!=snapshot.get("current_draft_output"):
                raise ValueError("Saved pagination and manuscript differ. Save the working story before approval.")
    if not set(saved)<=ids:raise ValueError('Every saved text unit must remain mapped; no writing may be removed.')
    if complete and set(saved)!=ids:raise ValueError('Write and save every planned '+spec['unit'].lower()+' before editorial approval.')
    if complete:
        prefs=values(snapshot).get('structure_preferences') or {}
        if prefs.get('unit_target') and int(prefs['unit_target'])!=len(result):
            raise ValueError('The planned '+spec['unit'].lower()+' count does not match the saved organization.')
        if spec['group'] and prefs.get('group_target') and int(prefs['group_target'])!=len({r['group_number'] for r in result}):
            raise ValueError('The planned '+spec['group'].lower()+' count does not match the organization.')
    return result


def signature(snapshot):
    packet={k:str(snapshot.get(k) or '') for k in ('active_format_id','current_project_id','project_title',
        'current_draft_output','chosen_option','chosen_option_text','plot_outline','story_seed',
        'tone_style','dialogue_style','author_style','project_integrity_report','project_integrity_source_signature')}
    packet['scene_blocks']={str(n):text for n,text in blocks(snapshot).items()}
    packet['settings']=values(snapshot)
    for k in (PROOF,'editorial_approval','stage_unlocked'):packet['settings'].pop(k,None)
    return hashlib.sha256(json.dumps(packet,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def approved(snapshot):
    from core.saved_scene_state import saved_snapshot_for_session
    try:
        saved=saved_snapshot_for_session(snapshot);proof=values(saved).get(PROOF) or {}
        canonical_plan(saved,unit_plan(saved),complete=True)
        return bool(not pending_edits(snapshot) and proof.get('revision_id')==str(snapshot.get('_wbs_active_saved_session_row_id'))
            and proof.get('signature')==signature(saved)==signature(snapshot))
    except (ValueError,TypeError,KeyError):return False


def pending_edits(snapshot):
    if profile(snapshot['active_format_id']).get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import working_key,author_source
        return snapshot.get(working_key(snapshot),author_source(snapshot))!=author_source(snapshot)
    scope='format_field_structure_'+'_'.join(str(x) for x in (snapshot['active_format_id'],
        snapshot.get('current_project_id') or 'new',snapshot.get('_wbs_active_saved_session_row_id') or 'draft'))+'_'
    draft=snapshot.get(scope+'working_plan')
    if draft is not None:
        try:
            if canonical_plan(snapshot,draft)!=canonical_plan(snapshot,unit_plan(snapshot)):return True
        except (ValueError,TypeError):return True
    saved=blocks(snapshot)
    return any(str(text)!=str(saved.get(int(n),'')) for n,text in (snapshot.get(scope+'text_buffers') or {}).items())


def approved_payload(snapshot):
    """Validate a standalone exported snapshot; UI access still uses saved proof."""
    proof=values(snapshot).get(PROOF) or {}
    try:canonical_plan(snapshot,unit_plan(snapshot),complete=True)
    except (ValueError,TypeError):return False
    return bool(proof.get('revision_id') and proof.get('signature')==signature(snapshot))


def commit(context,rows,edit=None,accept=False):
    """Use the existing owned/CAS checkpoint save; never insert a new version."""
    st=context['st'];state=st.session_state;fmt=state['active_format_id']
    if state.get('demo_mode'):raise ValueError('Saving requires the full Writer Edition.')
    if not state.get('_wbs_active_saved_session_row_id'):raise ValueError('Load an identified saved revision first.')
    if accept and pending_edits(state):raise ValueError('Save every edited text unit before editorial approval; working edits are preserved.')
    original={k:deepcopy(state.get(k)) for k in ('scene_blocks','current_draft_output','format_template_values',
        'project_integrity_report','project_integrity_source_signature','project_integrity_status')}
    writing=page_writing(state);source=str(state.get('current_draft_output') or '')
    assembled='\n\n'.join(writing[n] for n in sorted(writing))
    if writing and assembled!=source:raise ValueError('Saved text units do not match the manuscript. Map the original text explicitly; nothing was replaced.')
    if edit is not None:
        n,text=edit;n=positive(n)
        if not str(text).strip():raise ValueError('A saved text unit cannot be empty.')
        writing[n]=str(text)
    assembled='\n\n'.join(writing[n] for n in sorted(writing))
    if source and not blocks(state) and assembled!=source:
        raise ValueError('The unmapped manuscript must first be mapped verbatim; no saved writing was replaced.')
    plan=canonical_plan(state,rows,complete=accept,writing=writing)
    current=values(state);changed=current.get(KEY)!={'format_id':fmt,'version':1,'units':plan} or source!=assembled
    current[KEY]={**(current.get(KEY) or {}),'format_id':fmt,'version':1,'units':plan}
    current.pop(PROOF,None)
    try:
        state['format_template_values']={**(state.get('format_template_values') or {}),fmt:current}
        state['scene_blocks']=writing;state['current_draft_output']=assembled
        if changed and not accept:
            for k in ('project_integrity_report','project_integrity_source_signature','project_integrity_status'):state.pop(k,None)
        if accept:
            from core.integrity_review import ready
            if not ready(state,required=context['project_integrity_review_applies']()):
                raise ValueError('Run and save Project Integrity for the current manuscript first.')
            current[PROOF]={'revision_id':str(state['_wbs_active_saved_session_row_id']),'signature':signature(state)}
            state['format_template_values']={**state['format_template_values'],fmt:current}
        result=context['save_current_project_session_to_supabase']()
        if not result:raise ValueError('The current revision save was not confirmed; navigation remains blocked.')
    except Exception:
        for k,v in original.items():
            if v is None:state.pop(k,None)
            else:state[k]=v
        raise
    return True


def export_text(snapshot):
    if not approved_payload(snapshot):raise ValueError('Approve the exact saved structure and manuscript before export.')
    spec=profile(snapshot['active_format_id']);writing=blocks(snapshot)
    if spec.get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import export_text as page_export
        return page_export(snapshot)
    rows=canonical_plan(snapshot,unit_plan(snapshot),complete=True)
    parts=[str(snapshot.get('project_title') or '')];group=None
    for row in rows:
        if spec['group'] and row['group_number']!=group:
            group=row['group_number'];parts.append(spec['group']+' '+str(group)+(' — '+row['group_title'] if row['group_title'] else ''))
        parts.extend([unit_heading(spec,row),writing[row['unit_id']]])
        if spec['unit']=='Page' and row['detail'] and row['detail'] not in writing[row['unit_id']]:
            parts.append(row['detail'])
    return '\n\n'.join(parts)


def export_docx(snapshot,base_bytes=None):
    export_text(snapshot)  # Existing exact-saved editorial gate, no bypass.
    if profile(snapshot['active_format_id']).get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import export_docx as page_export
        return page_export(snapshot,base_bytes)
    from core.publication_layout import structured_docx
    return structured_docx(snapshot,base_bytes)


def export_plan(snapshot,rows=None):
    if profile(snapshot['active_format_id']).get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import pages,author_source
        return str(snapshot.get('project_title') or '')+'\n\n'+'\n'.join('Page '+str(n) for n in range(1,len(pages(author_source(snapshot)))+1))
    spec=profile(snapshot['active_format_id'])
    plan=canonical_plan(snapshot,unit_plan(snapshot) if rows is None else rows)
    output=[str(snapshot.get('project_title') or ''),'Organization plan — '+spec['description']]
    for row in plan:
        parent=(spec['group']+' '+str(row['group_number'])+(' — '+row['group_title'] if row['group_title'] else '')+' / ') if spec['group'] else ''
        output.extend([parent+unit_heading(spec,row),
            spec['detail']+': '+row['detail']])
    return '\n\n'.join(output)


def unit_heading(spec,row):
    label=spec['unit']+' '+str(row['unit_number'])
    return label if row['title'].strip()==label else label+' — '+row['title']


def integrity_context(snapshot):
    if profile(snapshot['active_format_id']).get('explicit_page_turns'):
        from formats.childrens_picture_book.page_turns import pages,author_source
        return '\n\n'.join('[PAGE '+str(n)+']\n'+text for n,text in enumerate(pages(author_source(snapshot)),1)), 'Use the supplied page numbers and exact quotations; page boundaries are author approved.'
    spec=profile(snapshot['active_format_id']);writing=blocks(snapshot)
    plan=canonical_plan(snapshot,unit_plan(snapshot))
    annotated=[]
    for row in plan:
        parent=(spec['group']+' '+str(row['group_number'])+' / ') if spec['group'] else ''
        label=parent+spec['unit']+' '+str(row['unit_number'])+'; TEXT ID '+str(row['unit_id'])
        annotated.append('['+label+']\n'+writing.get(row['unit_id'],'[UNWRITTEN PLANNED UNIT]')+'\n[END '+label+']')
    return '\n\n'.join(annotated),spec['description']+' Use supplied boundaries and exact quotations; never invent four scenes or novel chapters. Labels are audit context only.'
