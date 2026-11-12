"""Image editor/preview integration, using only embedded project assets."""
import base64,html,hashlib
from copy import deepcopy
from .inline_images import *


def paragraph_html(p,scale=64):
    result=[]
    for run in p.runs:
        for drawing in run._r.xpath('.//w:drawing'):
            blips=drawing.xpath('.//a:blip/@r:embed');extents=drawing.xpath('.//wp:extent')
            if not blips or not extents:continue
            blob=p.part.related_parts[blips[0]].blob;extent=extents[0];width=int(extent.get('cx'))/914400*scale
            alignment=drawing.xpath('.//wp:positionH/wp:align/text()')
            align=alignment[0] if alignment else 'center'
            style='float:'+align+';margin:6px;' if align!='center' else 'display:block;clear:both;margin:6px auto;'
            result.append('<img class="wbs-inserted-image" src="data:image/png;base64,'+base64.b64encode(blob).decode()+'" style="'+style+'width:'+str(width)+'px;max-width:100%;height:auto;break-inside:avoid">')
        if run.text:
            style=('font-weight:'+('700' if run.bold else '400')+';' if run.bold is not None else '')+('font-style:'+('italic' if run.italic else 'normal')+';' if run.italic is not None else '')
            result.append('<span style="'+style+'">'+html.escape(run.text)+'</span>')
    return ''.join(result) or html.escape(p.text)


def update_from_editor(state,unit,old,text,placements):
    if placements is None:return
    raw=data(state);current={i:x for i,x in raw.get('insertions',{}).items() if x['unit']==str(unit)}
    if not set(placements)<=set(current):raise ValueError('Unknown image anchor received.')
    for ident,item in current.items():
        if ident not in placements:
            latest=data(state);latest['insertions'].pop(ident,None);state['publication_layout']=latest
        else:place(state,unit,text,int(placements[ident]),item['asset'],item['size'],item['align'],ident)


def edit(context,unit,source,key,label='Manuscript text',height=400):
    st=context['st'];state=st.session_state
    if state.get('active_format_id') not in SUPPORTED:return st.text_area(label,value=source,height=height,key=key)
    from core.publication_layout import specification
    spec=specification(state);usable=spec['page_width']-spec['margins'][0]-spec['margins'][1]
    rich=st.checkbox('Edit with images',key=key+'_rich')
    if rich:
        from components.image_flow_editor import render
        blocked=False
        try:markup=flow_html(state,unit,source,usable)
        except ValueError as exc:st.warning(str(exc));markup=html.escape(source);blocked=True
        config=hashlib.sha256(str({i:{k:v for k,v in x.items() if k in ('asset','unit','size','align')} for i,x in data(state).get('insertions',{}).items()}).encode()).hexdigest()[:12]
        document,cursor=render(st,source,markup,key+'_image_canvas_'+config,None)
        text=document.get('text',source)
        if not blocked:update_from_editor(state,unit,source,text,document.get('placements'))
        state[key]=text
    else:text=st.text_area(label,value=source,height=height,key=key);cursor=0
    panel(context,unit,text,key,cursor)
    return text


def panel(context,unit,text,key,cursor=0):
    st=context['st'];state=st.session_state
    if state.get('active_format_id') not in SUPPORTED:return
    with st.expander('[Insert Image] — upload and placement',expanded=False):
        st.caption('In the image editor, put the caret in your text and click [Insert Image]. Or choose an exact character position below. Save text and images with the existing current-revision save command.')
        offset=st.number_input('Insertion position (characters)',min_value=0,max_value=len(text),value=min(int(cursor or 0),len(text)),key=key+'_image_offset_'+str(cursor)+'_'+str(len(text)))
        file=st.file_uploader('Upload JPG, PNG or WEBP',type=['jpg','jpeg','png','webp'],key=key+'_upload')
        size=st.selectbox('Image size',list(SIZES),index=1,key=key+'_size')
        st.caption('Small 25%, Medium 40%, Large 60% of usable page width, after left/right margins.')
        align=st.selectbox('Image position',['Left','Center','Right'],index=1,key=key+'_align')
        if align!='Center':st.caption('Left/right anchors use a whole-word boundary and preserve the surrounding paragraph.')
        if align=='Center':st.caption('Centered images appear between paragraphs, after the paragraph containing your insertion point. Sentences remain intact.')
        if st.button('Place Uploaded Image',key=key+'_place',disabled=file is None):
            try:
                asset=upload(state,file.getvalue(),file.name);place(state,unit,text,int(offset),asset,size,align)
            except ValueError as exc:st.error(str(exc))
            else:st.success('Image inserted in working copy. Save the current text unit to persist it.');st.rerun()
        raw=data(state);items=[(i,x) for i,x in raw.get('insertions',{}).items() if x['unit']==str(unit)]
        if items:
            ident=st.selectbox('Inserted image',[i for i,x in items],format_func=lambda i:raw['assets'][raw['insertions'][i]['asset']]['name'],key=key+'_selected_image')
            item=raw['insertions'][ident]
            size=st.selectbox('Change image size',list(SIZES),index=list(SIZES).index(item['size']),key=key+'_change_size_'+ident)
            align=st.selectbox('Change image position',['Left','Center','Right'],index=['Left','Center','Right'].index(item['align']),key=key+'_change_align_'+ident)
            if st.button('Update / Reanchor Image',key=key+'_update'):
                place(state,unit,text,int(offset),item['asset'],size,align,ident);st.rerun()
            if st.button('Remove Image',key=key+'_remove'):
                raw['insertions'].pop(ident);state['publication_layout']=raw;st.rerun()
        from core.publication_layout import specification
        spec=specification(state);usable=spec['page_width']-spec['margins'][0]-spec['margins'][1]
        try:markup=flow_html(state,unit,text,usable)
        except ValueError as exc:st.warning(str(exc))
        else:st.markdown('<div class="wbs-image-editing-preview" style="container-type:inline-size;white-space:pre-wrap;display:flow-root;background:white;color:#111;padding:1rem">'+markup+'</div>',unsafe_allow_html=True)
