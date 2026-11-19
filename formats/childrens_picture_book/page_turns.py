"""Authoring source is immutable except on explicit author save; one paginator."""
from copy import deepcopy
import hashlib
import html
import re

MARKER='[Page Turn]'
TOKEN=re.compile(r'\[Page Turn\]|\[PAGE TURN\]')  # Legacy spelling is read-compatible.
SOURCE='page_turn_source'


def supports(snapshot):
    from core.manuscript_structure import profile
    return bool(profile(snapshot['active_format_id']).get('explicit_page_turns'))


def working_key(state):
    return 'format_field_page_turn_'+str(state.get('current_project_id') or 'new')+'_'+str(state.get('_wbs_active_saved_session_row_id') or 'draft')+'_source'


def pages(source):
    # Do not strip whitespace, collapse paragraphs, or discard blank pages.
    return TOKEN.split(str(source))


def author_source(snapshot):
    if not supports(snapshot):raise ValueError('Explicit page turns are unavailable for this format.')
    from core.manuscript_structure import values
    current=values(snapshot)
    if SOURCE in current:return str(current[SOURCE])
    raw=snapshot.get('scene_blocks') or {}
    ordered=[str(raw[n]) for n in sorted(raw,key=lambda n:int(n)) if str(n).isdigit() and isinstance(raw[n],str)]
    if not ordered:return str(snapshot.get('current_draft_output') or '')
    source=ordered[0];previous=ordered[0]
    for text in ordered[1:]:
        # Existing saved page boundaries become editable separators in the
        # editor only. Never duplicate a legacy end-of-page marker.
        source+=('' if re.search(r'(?:\[Page Turn\]|\[PAGE TURN\])\s*$',previous) else MARKER)+text
        previous=text
    return source


def active(snapshot):
    from core.manuscript_structure import values
    return supports(snapshot) and SOURCE in values(snapshot)


def display_source(snapshot):
    return '\f'.join(pages(author_source(snapshot)))


def save(context,source,save_as_new_version=False,version_name=None):
    from core.manuscript_structure import values,KEY,PROOF
    state=context['st'].session_state
    if not supports(state):raise ValueError('Cross-format page-turn write refused.')
    if state.get('demo_mode') or not state.get('_wbs_active_saved_session_row_id'):
        raise ValueError('Load an identified saved revision before saving.')
    if not isinstance(source,str) or not any(p.strip() for p in pages(source)):
        raise ValueError('Story text is required.')
    before={k:deepcopy(state.get(k)) for k in ('format_template_values','scene_blocks','current_draft_output',
        'project_integrity_report','project_integrity_source_signature','project_integrity_status')}
    current=values(state);old_source=author_source(state);parts=pages(source)
    if SOURCE not in current:
        current['page_turn_legacy_structure']=deepcopy(current.get(KEY))
    current[SOURCE]=source
    old_rows=(current.get(KEY) or {}).get('units') or []
    current[KEY]={'format_id':state['active_format_id'],'version':1,
        'pagination_signature':hashlib.sha256(source.encode()).hexdigest(),
        'units':[dict(unit_id=i,group_number=1,group_title='',unit_number=i,
            title=str(old_rows[i-1].get('title') or 'Page '+str(i)) if len(old_rows)==len(parts) else 'Page '+str(i),detail='')
            for i in range(1,len(parts)+1)]}
    current['structure_preferences']={**(current.get('structure_preferences') or {}),'unit_target':len(parts)}
    current.pop(PROOF,None)
    try:
        state['format_template_values']={**(state.get('format_template_values') or {}),state['active_format_id']:current}
        state['scene_blocks']={i:text for i,text in enumerate(parts,1)}
        state['current_draft_output']='\n\n'.join(parts)
        if source!=old_source or SOURCE not in ((before['format_template_values'] or {}).get(state['active_format_id']) or {}):
            for k in ('project_integrity_report','project_integrity_source_signature','project_integrity_status'):state.pop(k,None)
        if not context['save_current_project_session_to_supabase'](version_name=version_name,save_as_new_version=save_as_new_version):raise ValueError('Save was not confirmed. Your working text is retained.')
    except Exception:
        for k,v in before.items():
            if v is None:state.pop(k,None)
            else:state[k]=v
        raise
    # Obsolete editor buffers must not override the new author-controlled source.
    prefix='format_field_structure_'+state['active_format_id']+'_'+str(state['current_project_id'])+'_'+str(state['_wbs_active_saved_session_row_id'])+'_'
    for key in (prefix+'working_plan',prefix+'text_buffers'):state.pop(key,None)
    state[working_key(state)]=source
    return True


def render_pages(st,snapshot,show_controls=True):
    from core.children_publication import render_page
    parts=pages(author_source(snapshot))
    from core.children_arrangements import resolve
    default_spreads=any(resolve(snapshot,'picture-page',n,t)['spread_id'] for n,t in enumerate(parts,1))
    key='format_field_picture_spreads_'+str(snapshot.get('current_project_id','preview'))+'_'+str(snapshot.get('_wbs_active_saved_session_row_id','working'))+'_'+str(bool(default_spreads))
    spreads=st.checkbox('Show two-page spreads',value=bool(default_spreads),key=key) if show_controls else False
    if not spreads:
        for n,text in enumerate(parts,1):render_page(st,snapshot,n,text)
    else:
        st.caption('Recto cover on the right; even-numbered pages left, odd-numbered pages right. No extra story page is added.')
        left,right=st.columns(2)
        with right:render_page(st,snapshot,1,parts[0])
        for index in range(1,len(parts),2):
            left,right=st.columns(2)
            with left:render_page(st,snapshot,index+1,parts[index])
            if index+1<len(parts):
                with right:render_page(st,snapshot,index+2,parts[index+1])


def export_text(snapshot):
    return str(snapshot.get('project_title') or '')+'\n\n'+'\f'.join('Page '+str(n)+'\n'+text for n,text in enumerate(pages(author_source(snapshot)),1))


def export_docx(snapshot,base_bytes=None,resolve_asset=None):
    from io import BytesIO
    from docx import Document
    from core.print_export import document,bytes_for
    doc=Document(BytesIO(base_bytes)) if base_bytes else document(snapshot.get('project_title'))
    if base_bytes:
        for child in list(doc.element.body):
            if child.tag.rsplit('}',1)[-1]!='sectPr':doc.element.body.remove(child)
        doc.add_heading(str(snapshot.get('project_title') or ''),0)
    from core.children_publication import apply_docx,add_placeholder
    apply_docx(doc,snapshot)
    for number,text in enumerate(pages(author_source(snapshot)),1):
        if number>1:doc.add_page_break()
        page_heading=doc.add_heading('Page '+str(number),1)
        from core.children_arrangements import word_art,word_frame
        plan=word_art(doc,snapshot,'picture-page',number,text,resolve_asset)
        if number==1:
            from docx.shared import Pt
            title=next(p for p in doc.paragraphs if p.style.name=='Title')
            word_frame(title,plan['title_box'])
            title.paragraph_format.keep_with_next=False
            for run in title.runs:run.font.size=Pt(20)
            band=plan['title_box'];word_frame(page_heading,[band[0],band[1]+band[3],band[2],.2])
            for run in page_heading.runs:run.font.size=Pt(9)
        word_frame(doc.add_paragraph(text),plan['text_box'])
    from core.publication_layout import decorate_document
    decorate_document(doc,snapshot)
    from core.inline_images import apply_to_doc
    apply_to_doc(doc,snapshot)
    return bytes_for(doc)


def rewrite_preserving_turns(source,rewrite):
    pieces=TOKEN.split(source);separators=TOKEN.findall(source);result=[]
    for index,text in enumerate(pieces):
        rewritten=rewrite(text) if text.strip() else text
        if not isinstance(rewritten,str) or TOKEN.search(rewritten):raise ValueError('Rewrite changed page-turn controls; no writing was applied.')
        result.append(rewritten)
        if index<len(separators):result.append(separators[index])
    return ''.join(result)


def rewrite_page(source,number,rewrite):
    if not 1<=number<=len(pages(source)):raise ValueError('Unknown page.')
    parts=TOKEN.split(source);separators=TOKEN.findall(source)
    replacement=rewrite(parts[number-1])
    if not isinstance(replacement,str) or TOKEN.search(replacement):raise ValueError('Rewrite changed page-turn controls; no writing was applied.')
    parts[number-1]=replacement
    return ''.join(text+(separators[i] if i<len(separators) else '') for i,text in enumerate(parts))
