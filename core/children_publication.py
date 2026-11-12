"""Children's print dimensions and image-ready slots, separate from author prose."""
from copy import deepcopy
import html

FORMATS={'childrens_picture_book','childrens_interactive_educational'}
KEY='children_publication_layout'
SIZES={
 '8.5 x 8.5 Square':(8.5,8.5),'10 x 8 Landscape':(10,8),
 '7 x 7 Square':(7,7),'8 x 8 Square':(8,8),'8.25 x 8.25 Square':(8.25,8.25),
 '8 x 10 Portrait':(8,10),'8.5 x 11 Letter':(8.5,11),
 '6 x 9 Portrait':(6,9),'7 x 10 Portrait':(7,10),
 '11 x 8.5 Landscape':(11,8.5),'A4 Portrait (210 x 297 mm)':(210/25.4,297/25.4),
}


def settings(snapshot):
    fmt=snapshot.get('active_format_id')
    if fmt not in FORMATS:raise ValueError('Children’s publication layout is unavailable for this format.')
    raw=snapshot.get(KEY) or {}
    return deepcopy(raw) if isinstance(raw,dict) and raw.get('format_id')==fmt and raw.get('project_id') in (None,'',snapshot.get('current_project_id')) else {'format_id':fmt,'positions':{}}


def selected(snapshot):
    raw=settings(snapshot)
    value=raw.get('page_size')
    if not value and snapshot['active_format_id']=='childrens_picture_book':value=snapshot.get('picture_book_page_size')
    return value or ('8.5 x 8.5 Square' if snapshot['active_format_id']=='childrens_picture_book' else '8.5 x 11 Letter')


def spec(snapshot):
    name=selected(snapshot)
    if name not in SIZES:raise ValueError('Unknown saved Page Size. Choose a supported size; existing writing was preserved.')
    w,h=SIZES[name];picture=snapshot['active_format_id']=='childrens_picture_book'
    font=16
    if not picture:
        from formats.childrens_interactive_educational.validation import AGE_GUIDANCE
        from core.manuscript_structure import values
        font=AGE_GUIDANCE.get(values(snapshot).get('age_band'),{}).get('font_size',14)
    return dict(name=name,width=w,height=h,margin=.5,font_size=font,
        image_width=w-1,image_height=(h-1)*(.52 if picture else .27),alignment='center',caption_position='below')


def position(snapshot,kind,number):
    ident=kind+'-'+str(number)
    existing=(settings(snapshot).get('positions') or {}).get(ident) or {}
    defaults={k:v for k,v in spec(snapshot).items() if k.startswith('image_') or k in ('alignment','caption_position')}
    from core.children_arrangements import resolve
    return {**defaults,**deepcopy(existing),'id':ident,'anchor':{'kind':kind,'number':number},
            'description':str(existing.get('description') or ''),'layout_geometry':resolve(snapshot,kind,number)}


def set_size(state,name):
    if name not in SIZES:raise ValueError('Unsupported Page Size.')
    raw=settings(state);raw['page_size']=name;raw['project_id']=state.get('current_project_id')
    w,h=SIZES[name]
    for slot in (raw.get('positions') or {}).values():
        slot['image_width']=w-1;slot['image_height']=(h-1)*(.52 if state['active_format_id']=='childrens_picture_book' else .27)
    state[KEY]=raw
    if state['active_format_id']=='childrens_picture_book':state['picture_book_page_size']=name


def save(context):
    state=context['st'].session_state
    if state.get('demo_mode') or not state.get('_wbs_active_saved_session_row_id'):raise ValueError('Load a saved Writer Edition project before saving layout.')
    spec(state)
    raw=settings(state)
    from core.children_arrangements import pages
    anchors=[(p['kind'],p['number']) for p in pages(state)]
    for kind,n in anchors:raw.setdefault('positions',{})[kind+'-'+str(n)]=position(state,kind,n)
    state[KEY]=raw
    if not context['save_current_project_session_to_supabase']():raise ValueError('Layout save failed. Working layout is retained; saved writing was not replaced.')
    return True


def controls(context,stage):
    st=context['st'];state=st.session_state
    from core.structure_ui import widget_key
    current=selected(state);options=list(SIZES)
    if stage=='concept' and not (state.get(KEY) or {}).get('page_size') and current in SIZES:set_size(state,current)
    if current not in options:options.insert(0,current)
    # A size-specific key synchronizes Concept/Final and restored revisions.
    key=widget_key(state,'page_size_'+stage+'_'+current)
    choice=st.selectbox('Page Size',options,index=options.index(current),key=key,
        help='Trim dimensions in inches unless marked mm. Resizes pages without rewriting or deleting text.')
    if choice in SIZES and choice!=current:
        set_size(state,choice);st.rerun()
    st.caption('Selected Page Size: '+current+'. Layout changes do not rewrite your story or create a new version.')
    from core.children_arrangements import controls as arrangement_controls
    arrangement_controls(context,stage)
    if stage=='final':
        if st.button('Save Page Size and Illustration Settings',key=widget_key(state,'save_publication_layout'),type='primary'):
            try:save(context)
            except (ValueError,RuntimeError) as exc:st.error(str(exc))
            else:st.success('Layout saved to the current revision.');st.rerun()
        from core.saved_scene_state import saved_snapshot_for_session
        if settings(state)!=settings(saved_snapshot_for_session(state)):
            st.info('Working layout preview. Save Page Size and Illustration Settings before downloading this adjustment.')


def illustration_controls(context,kind,numbers):
    st=context['st'];state=st.session_state
    from core.structure_ui import widget_key
    with st.expander('Illustration descriptions — separate from story text',expanded=False):
        n=st.selectbox('Illustration position',list(numbers),key=widget_key(state,'illustration_position'))
        slot=position(state,kind,n)
        description=st.text_area('Illustration description',value=slot['description'],key=widget_key(state,'illustration_description_'+slot['id']))
        caption=st.text_input('Illustration caption / source reference',value=slot.get('caption',''),key=widget_key(state,'illustration_caption_'+slot['id']))
        if description!=slot['description'] or caption!=slot.get('caption',''):
            raw=settings(state);raw.setdefault('positions',{})[slot['id']]={**slot,'description':description,'caption':caption};state[KEY]=raw
        st.caption(f"Reserved image area: {slot['image_width']:g} × {slot['image_height']:g} inches. Future images use this stable position and selected page dimensions.")


def apply_docx(doc,snapshot):
    from docx.shared import Inches,Pt
    from docx.enum.section import WD_ORIENT
    s=spec(snapshot)
    for section in doc.sections:
        section.orientation=WD_ORIENT.LANDSCAPE if s['width']>s['height'] else WD_ORIENT.PORTRAIT
        section.page_width=Inches(s['width']);section.page_height=Inches(s['height'])
        section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Inches(s['margin'])
    doc.styles['Normal'].font.size=Pt(s['font_size'])


def add_placeholder(doc,snapshot,kind,number,resolve_asset=None):
    from docx.shared import Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    slot=position(snapshot,kind,number)
    if resolve_asset and slot.get('asset_id'):
        p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(resolve_asset(slot['asset_id']),width=Inches(slot['image_width']),height=Inches(slot['image_height']))
        if slot.get('caption'):doc.add_paragraph(str(slot['caption']),'Caption')
        return slot
    table=doc.add_table(rows=1,cols=1)
    table.autofit=False;table.columns[0].width=Inches(slot['image_width'])
    table.rows[0].height=Inches(slot['image_height'])
    cell=table.cell(0,0);cell.width=Inches(slot['image_width'])
    cell.text='Illustration — '+slot['id']+('\n'+slot['description'] if slot['description'] else '\nReserved illustration area')
    cell.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
    borders=OxmlElement('w:tcBorders')
    for edge in ('top','left','bottom','right'):
        item=OxmlElement('w:'+edge);item.set(qn('w:val'),'single');item.set(qn('w:sz'),'6');item.set(qn('w:color'),'D9D9D9');borders.append(item)
    cell._tc.get_or_add_tcPr().append(borders)
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if slot.get('caption'):doc.add_paragraph(str(slot['caption']),'Caption')
    # Stable ID and dimensions live in metadata; no source image is regenerated.
    return slot


def render_page(st,snapshot,number,text,kind='picture-page',class_name='wbs-manuscript-page',slot_number=None,show_image=True):
    from core.children_arrangements import resolve,STYLES
    s=spec(snapshot);n=number if slot_number is None else slot_number;slot=position(snapshot,kind,n);plan=resolve(snapshot,kind,n,text)
    if kind=='education-guide':
        margin=s['margin']/s['width']*100;size=s['font_size']/(72*s['width'])*100
        st.markdown('<div class="wbs-layout-caption">Page '+str(number)+'  -  Parent / Teacher Guide (flowing text)</div><div style="width:520px;max-width:100%;container-type:inline-size"><article class="wbs-educational-page wbs-guide-continuation" data-page-number="'+str(number)+'" style="box-sizing:border-box;aspect-ratio:'+str(s['width'])+' / '+str(s['height'])+';padding:'+str(margin)+'%;border:1px solid #888;background:white;color:#111;font-size:'+str(size)+'cqw;line-height:1.2;white-space:pre-wrap;overflow-wrap:anywhere">'+html.escape(text)+'</article></div>',unsafe_allow_html=True)
        return

    if plan.get('overflow_warning'):st.warning('Page '+str(number)+': the saved text may overflow this arrangement. Choose a larger page or a different layout; text has not been shortened or removed.')
    def box(rect):return 'left:'+str(rect[0]/s['width']*100)+'%;top:'+str(rect[1]/s['height']*100)+'%;width:'+str(rect[2]/s['width']*100)+'%;min-height:'+str(rect[3]/s['height']*100)+'%;'
    image_title=slot['description'] or 'Reserved illustration area'
    if plan['spread_id']:image_title+='\n'+plan['spread_id']+' — '+plan['spread_side']+' half'
    image=('<div class="wbs-illustration-slot" data-slot-id="'+slot['id']+'" data-spread="'+str(plan['spread_id'] or '')+'" data-side="'+str(plan['spread_side'] or '')+'" style="position:absolute;box-sizing:border-box;border:1px dashed #a5b5aa;background:#e6efeb;display:flex;align-items:center;justify-content:center;text-align:center;white-space:pre-wrap;'+box(plan['image_box'])+'">'+html.escape(image_title)+('<br>'+html.escape(str(slot['caption'])) if slot.get('caption') else '')+('</div>')) if show_image and plan.get('show_art',True) else ''
    title=''
    if plan.get('title_box'):
        title='<div class="wbs-cover-title" style="position:absolute;box-sizing:border-box;font-weight:bold;font-size:'+str(20/(72*s['width'])*100)+'cqw;'+box(plan['title_box'])+'">'+html.escape(str(snapshot.get('project_title') or ''))+'</div>'
    story_html=html.escape(text)
    from core.inline_images import flow_html
    if kind=='picture-page':story_html=flow_html(snapshot,n,text)
    elif kind=='education-unit':
        from core.manuscript_structure import blocks
        raw_text=blocks(snapshot).get(int(n),'')
        if raw_text and raw_text in text:story_html=html.escape(text).replace(html.escape(raw_text),flow_html(snapshot,n,raw_text),1)
    size=s['font_size']/(72*s['width'])*100
    st.markdown('<div class="wbs-layout-caption" style="font-size:.8rem">Page '+str(number)+' — '+STYLES[plan['style']]+'</div><div style="width:520px;max-width:100%;container-type:inline-size"><article class="'+class_name+' wbs-publication-page" data-layout="'+plan['style']+'" data-page-number="'+str(number)+'" data-page-width="'+str(s['width'])+'" data-page-height="'+str(s['height'])+'" style="position:relative;box-sizing:border-box;width:100%;aspect-ratio:'+str(s['width'])+' / '+str(s['height'])+';background:white;color:#111;border:1px solid #888;margin-bottom:1rem;font-size:'+str(size)+'cqw;overflow:visible">'+title+image+'<div class="wbs-positioned-story" style="position:absolute;box-sizing:border-box;white-space:pre-wrap;overflow-wrap:anywhere;background:rgba(255,255,255,.94);padding:.6cqw;'+box(plan['text_box'])+'">'+story_html+'</div></article></div>',unsafe_allow_html=True)


def render_educational(st,snapshot):
    # Preview the actual export contents, including worksheets and adult guide.
    from io import BytesIO
    from docx import Document
    from formats.childrens_interactive_educational.exports import build_docx
    from docx.oxml.ns import qn
    doc=Document(BytesIO(build_docx(snapshot)));parts=[];number=1;display_pages=[]
    from core.children_arrangements import pages
    records=pages(snapshot)
    def emit():
        nonlocal parts,number
        if parts:
            import re
            record=records[number-1] if number<=len(records) else dict(kind='education-continuation',number=number)
            display_pages.append((number,'\n\n'.join(parts),record));number+=1;parts=[]
    for node in doc.element.body:
        if node.tag==qn('w:p'):
            if node.xpath('.//w:br[@w:type="page"]'):emit()
            from docx.text.paragraph import Paragraph
            text=Paragraph(node,doc).text if not node.xpath('.//w:pict') else ''
            if text.strip():parts.append(text)
        elif node.tag==qn('w:tbl'):
            # Illustration is drawn by the preview slot, not repeated in prose.
            text='\n'.join(node.xpath('.//w:t/text()'))
            if text and not text.startswith('Illustration — '):parts.append(text)
    emit()
    # Fixed-position teaching pages retain their plan. Only the adult guide
    # continues through normal-flow pages, matching its DOCX flow behavior.
    continued=[]
    for _,text,record in display_pages:
        pieces=[text]
        if record['kind']=='education-guide':pieces=guide_preview_pages(snapshot,text)
        for piece in pieces:continued.append((len(continued)+1,piece,record))
    display_pages=continued
    from core.children_arrangements import resolve
    default_spreads=any(resolve(snapshot,r['kind'],r['number'],text)['spread_id'] for _,text,r in display_pages)
    spread_key='format_field_educational_spreads_'+str(snapshot.get('current_project_id'))+'_'+str(snapshot.get('_wbs_active_saved_session_row_id'))+'_'+str(bool(default_spreads))
    spreads=st.checkbox('Show two-page spreads',value=bool(default_spreads),key=spread_key)
    def render_one(item):
        n,text,record=item
        render_page(st,snapshot,n,text,record['kind'],'wbs-educational-page',record['number'],True)
    if not spreads:
        for item in display_pages:render_one(item)
    elif display_pages:
        left,right=st.columns(2)
        with right:render_one(display_pages[0])
        for index in range(1,len(display_pages),2):
            left,right=st.columns(2)
            with left:render_one(display_pages[index])
            if index+1<len(display_pages):
                with right:render_one(display_pages[index+1])


def guide_preview_pages(snapshot,text):
    """Conservative preview boundaries; Word determines actual line wrapping."""
    import math
    s=spec(snapshot);chars=max(12,int((s['width']-2*s['margin'])*72/(s['font_size']*.6)))
    lines=max(1,int((s['height']-2*s['margin'])*72/(s['font_size']*1.4))-4)
    result=[];chunk='';used=0
    for line in text.splitlines(keepends=True):
        while line:
            piece=line[:chars];line=line[chars:]
            if used>=lines:result.append(chunk);chunk='';used=0
            chunk+=piece;used+=1
    if chunk:result.append(chunk)
    return result or ['']
