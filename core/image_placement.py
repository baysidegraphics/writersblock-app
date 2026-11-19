"""Image-ready positions. No image generation, asset fetching or prose changes."""
from copy import deepcopy
from importlib import import_module
KEY='publication_layout'


def allowed(snapshot):
    return bool(import_module('formats.'+snapshot['active_format_id']+'.publication').SPEC['images'])


def settings(snapshot):
    raw=snapshot.get(KEY) or {};fmt=snapshot['active_format_id']
    if not allowed(snapshot):raise ValueError('Image positions are not supported by this format.')
    return deepcopy(raw) if raw.get('format_id')==fmt and raw.get('project_id') in (None,snapshot.get('current_project_id')) else {'format_id':fmt,'project_id':snapshot.get('current_project_id'),'positions':{}}


def slot(snapshot,anchor):
    raw=settings(snapshot);original=(raw.get('positions') or {}).get(anchor) or {}
    from core.publication_choices import default_image
    photo=default_image(snapshot)
    result={**deepcopy(original),'id':anchor,'anchor':anchor,'enabled':original.get('enabled',photo),
        'description':original.get('description',''),'caption':original.get('caption',''),
        'width':float(original.get('width',4.5)),'height':float(original.get('height',2.2)),
        'alignment':original.get('alignment','center'),'caption_position':'below'}
    if snapshot['active_format_id']=='novel_prose_novella':
        from formats.novel_prose_novella.illustrations import chapter_slot
        return chapter_slot(snapshot,anchor,result,raw)
    return result


def add_docx(doc,snapshot,anchor,resolve_asset=None):
    if not allowed(snapshot):return
    pos=slot(snapshot,anchor)
    if not pos['enabled']:return
    from core.inline_images import SUPPORTED,data as image_data
    if snapshot['active_format_id'] in SUPPORTED and not pos.get('asset_id') and not pos.get('keep_empty'):
        from core.manuscript_structure import unit_plan
        inserted={str(x['unit']) for x in image_data(snapshot).get('insertions',{}).values()}
        if snapshot['active_format_id']=='biography_memoir':covered=anchor.startswith('chapter-') and anchor[8:] in inserted
        elif snapshot['active_format_id']=='youtube_shorts':covered=anchor.startswith('segment-') and anchor[8:] in inserted
        else:covered=any(str(r['unit_id']) in inserted and anchor.endswith('-'+str(r['group_number'])) for r in unit_plan(snapshot))
        if covered:return
    from docx.shared import Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    s=doc.sections[-1];available=(s.page_width-s.left_margin-s.right_margin)/914400
    width=min(pos['width'],available);height=min(pos['height'],(s.page_height-s.top_margin-s.bottom_margin)/914400*.5)
    if width<=0 or height<=0:raise ValueError('Image dimensions must be positive.')
    if resolve_asset and pos.get('asset_id'):
        paragraph=doc.add_paragraph();paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(resolve_asset(pos['asset_id']),width=Inches(width),height=Inches(height))
    else:
        table=doc.add_table(rows=1,cols=1);table.autofit=False;table.columns[0].width=Inches(width)
        from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
        table.alignment={'left':WD_TABLE_ALIGNMENT.LEFT,'right':WD_TABLE_ALIGNMENT.RIGHT}.get(pos['alignment'],WD_TABLE_ALIGNMENT.CENTER)
        if snapshot['active_format_id']=='youtube_shorts':
            no_split=OxmlElement('w:cantSplit');table.rows[0]._tr.get_or_add_trPr().append(no_split)
        table.rows[0].height=Inches(height);cell=table.cell(0,0);cell.width=Inches(width);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        cell.text=(__import__('core.publication_choices',fromlist=['image_label']).image_label(snapshot))+' — '+anchor+'\n'+(pos['description'] or 'Reserved image position')
        borders=OxmlElement('w:tcBorders')
        for edge in ('top','left','bottom','right'):
            border=OxmlElement('w:'+edge);border.set(qn('w:val'),'single');border.set(qn('w:color'),'D9D9D9');border.set(qn('w:sz'),'6');borders.append(border)
        cell._tc.get_or_add_tcPr().append(borders)
    fixture_labels={'Synthetic image position — no image generated','Synthetic illustration position'}
    if pos['caption'] and pos['caption'] not in fixture_labels:doc.add_paragraph(pos['caption'],'Caption')


def controls(context,anchors):
    st=context['st'];state=st.session_state
    if not allowed(state) or not anchors:return
    from core.structure_ui import widget_key
    with st.expander('Image positions and captions — separate from manuscript',expanded=False):
        anchor=st.selectbox('Image position',anchors,key=widget_key(state,'publication_anchor'))
        pos=slot(state,anchor)
        from core.inline_images import SUPPORTED,data as inserted_data
        if state['active_format_id'] in SUPPORTED and inserted_data(state).get('insertions'):
            keep=st.checkbox('Keep a separate empty illustration area',value=bool(pos.get('keep_empty')),key=widget_key(state,'keep_empty_'+anchor))
            if keep!=bool(pos.get('keep_empty')):pos['keep_empty']=keep
        if state['active_format_id']=='novel_prose_novella':
            st.caption(pos['recommendation'])
            places=['chapter_start','chapter_end']
            pos['placement']=st.selectbox('Chapter illustration placement',places,index=places.index(pos.get('placement','chapter_start')),format_func=lambda x:'After chapter heading' if x=='chapter_start' else 'After chapter text',key=widget_key(state,'image_placement_'+anchor))
        pos['enabled']=st.checkbox('Reserve image space',value=bool(pos['enabled']),key=widget_key(state,'image_enabled_'+anchor))
        pos['description']=st.text_area('Image description',value=pos['description'],key=widget_key(state,'image_description_'+anchor))
        pos['caption']=st.text_input('Image caption / source reference',value=pos['caption'],key=widget_key(state,'image_caption_'+anchor))
        pos['width']=st.number_input('Image width (inches)',min_value=.5,max_value=6.5,value=float(pos['width']),key=widget_key(state,'image_width_'+anchor))
        pos['alignment']=st.selectbox('Image alignment',['left','center','right'],index=['left','center','right'].index(pos['alignment']) if pos['alignment'] in ('left','center','right') else 1,key=widget_key(state,'image_alignment_'+anchor))
        pos['height']=st.number_input('Image height (inches)',min_value=.5,max_value=4.0,value=float(pos['height']),key=widget_key(state,'image_height_'+anchor))
        old=slot(state,anchor)
        if pos!=old:
            raw=settings(state);raw['positions'][anchor]=pos;state[KEY]=raw
        if st.button('Save Image Layout to Current Revision',key=widget_key(state,'save_image_layout')):
            if not state.get('_wbs_active_saved_session_row_id') or state.get('demo_mode'):st.warning('Load a saved Writer Edition revision before saving layout.')
            elif context['save_current_project_session_to_supabase']():st.success('Image layout saved without changing writing or V-number.');st.rerun()
            else:st.error('Image layout save failed. Working changes are retained.')
