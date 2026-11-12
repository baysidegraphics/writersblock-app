"""Author-selected children's arrangements. Deterministic, no AI or prose writes."""
from copy import deepcopy
import html,re

STYLES={'classic':'Classic Illustrated','full_page':'Full-Page Illustration','split':'Split Layout','spread':'Double-Page Spread','adaptive':'Story-Adaptive Layout'}
DEFAULT='adaptive'


def data(snapshot):
    from core.children_publication import settings
    return settings(snapshot)


def pages(snapshot):
    if snapshot['active_format_id']=='childrens_picture_book':
        from formats.childrens_picture_book.page_turns import author_source,pages as split
        return [dict(kind='picture-page',number=n,label='Page '+str(n),text=t,activity=False) for n,t in enumerate(split(author_source(snapshot)),1)]
    from core.manuscript_structure import values,blocks
    v=values(snapshot);b=blocks(snapshot);result=[dict(kind='education-intro',number=1,label='Opening teaching page',text=str(v.get('learning_goals') or ''),activity=False)]
    for u in sorted(v.get('units') or [],key=lambda x:int(x['unit_number'])):
        n=int(u['unit_number']);result.append(dict(kind='education-unit',number=n,label='Learning unit '+str(n),text=b.get(n,''),activity=any(str(a.get('unit_number'))==str(n) for a in v.get('activities') or [])))
        for a in v.get('activities') or []:
            if str(a.get('unit_number'))==str(n):result.append(dict(kind='education-activity',number=str(a.get('activity_id') or a.get('title')),label='Exercise — '+str(a.get('title')),text=str(a.get('instructions') or ''),activity=True))
    result.append(dict(kind='education-guide',number=1,label='Parent / teacher guide',text=str(v.get('adult_role') or ''),activity=True))
    return result


def anchor(kind,number):return kind+'-'+str(number)


def set_overall(state,style):
    from core.children_publication import KEY
    if style not in STYLES:raise ValueError('Unknown illustrated layout.')
    raw=data(state);raw['overall_layout']=style;state[KEY]=raw


def set_override(state,kind,number,style):
    from core.children_publication import KEY
    if style not in STYLES and style!='inherit':raise ValueError('Unknown page layout.')
    raw=data(state);slot=deepcopy((raw.get('positions') or {}).get(anchor(kind,number)) or {})
    if style=='inherit':slot.pop('layout_override',None)
    else:slot['layout_override']=style
    raw.setdefault('positions',{})[anchor(kind,number)]=slot;state[KEY]=raw


def _spread_recommendation(snapshot,item,index,text,count):
    return not item['activity'] and len(text.split())<=70 and ('?' in text or '!' in text or (index is not None and index>=count*.65 and (index+1)%2==0 and re.search(r'\b(reveal|climax|surprise|discovery)\b',str(snapshot.get('chosen_option_text') or '')+' '+str(snapshot.get('plot_outline') or ''),re.I)))


def resolve(snapshot,kind,number,text=None):
    from core.children_publication import spec
    raw=data(snapshot);allpages=pages(snapshot);ident=anchor(kind,number)
    index=next((i for i,p in enumerate(allpages) if anchor(p['kind'],p['number'])==ident),None)
    item=allpages[index] if index is not None else dict(text=text or '',activity=False)
    actual_text=item['text'] if text is None else str(text)
    # Recommendations use the saved page narrative/activity, not incidental
    # headings introduced by an export renderer. Geometry is stable on reload.
    text=item['text'] if index is not None else actual_text
    stored=(raw.get('positions') or {}).get(ident) or {}
    requested=stored.get('layout_override',raw.get('overall_layout',DEFAULT))
    if requested not in STYLES:raise ValueError('Saved illustration layout is unknown; original metadata was preserved.')
    reason='Author-selected arrangement.';style=requested
    if style=='adaptive':
        if kind in {'education-intro','education-guide'}:style='classic';reason='Teaching reference page: retain a full-width reading area.'
        elif item['activity']:style='split';reason='Saved exercise or learning activity: keep instructions beside the illustration.'
        elif len(text.split())>70:style='classic';reason='Longer saved text: reserve a generous reading area below the image.'
        elif not text.strip():style='full_page';reason='Image-only page retained at its existing page-turn location.'
        elif _spread_recommendation(snapshot,item,index,text,len(allpages)):
            style='spread';reason='Question or reveal at an existing story boundary: recommend a facing-page illustration.'
        elif len(text.split())<22:style='full_page';reason='Short narrative beat: recommend an illustration with positioned text.'
        else:style='classic';reason='Balanced story beat: illustration above its saved text.'
    # A spread links existing facing pages, never combines/deletes their text.
    partner=None;spread_id=None;side=None
    logical=(index+1) if index is not None else 1
    left=logical if logical%2==0 else logical-1
    if style=='spread':
        if index is not None and left>=2 and left<len(allpages):
            partner=allpages[left if logical==left else left-1]
            other=(raw.get('positions') or {}).get(anchor(partner['kind'],partner['number'])) or {}
            if other.get('layout_override') not in (None,'inherit','adaptive','spread'):
                style='full_page';reason='The facing page has a different author override; its layout is preserved.'
            else:
                spread_id='spread-'+str(left)+'-'+str(left+1);side='left' if logical==left else 'right'
        else:style='full_page';reason='Unpaired cover or last page: retain a single-page illustration without adding pages.'
    elif stored.get('layout_override') in (None,'adaptive') and index is not None and left>=2 and left<len(allpages):
        otherpage=allpages[left if logical==left else left-1]
        other=(raw.get('positions') or {}).get(anchor(otherpage['kind'],otherpage['number'])) or {}
        other_requested=other.get('layout_override',raw.get('overall_layout',DEFAULT))
        other_index=left if logical==left else left-1
        adaptive_reveal=other_requested=='adaptive' and _spread_recommendation(snapshot,otherpage,other_index,otherpage['text'],len(allpages))
        if other_requested=='spread' or adaptive_reveal:
            style='spread';spread_id='spread-'+str(left)+'-'+str(left+1);side='left' if logical==left else 'right';reason='Linked to the author-selected illustration on its facing page.'
    s=spec(snapshot);w=s['width'];h=s['height'];m=s['margin'];cw=w-2*m;ch=h-2*m
    # Normalized boxes are the single browser/Word placement specification.
    if style=='classic':
        import math
        full_width_chars=max(12,cw*72/(s['font_size']*.52))
        text_height=sum(max(1,math.ceil(len(line)/full_width_chars)) for line in text.split('\n'))*s['font_size']*1.2/72
        image_height=min(ch*.48,max(ch*.12,ch-text_height-.25))
        ib=[m,m,cw,image_height];tb=[m,m+image_height+.2,cw,ch-image_height-.2]
    elif style=='split':ib=[m,m,cw*.46,ch*.86];tb=[m+cw*.51,m,cw*.49,ch]
    else:ib=[0,0,w,h];tb=[m,h*.64,cw,h*.30]
    show_art=bool(actual_text.strip() or raw.get('overall_layout',DEFAULT)!='adaptive' or stored.get('layout_override') not in (None,'inherit','adaptive') or any(stored.get(k) for k in ('asset_id','description','caption')))
    title_box=None
    if kind=='picture-page' and logical==1:
        # Reserve a real cover title band; artwork must not start behind it.
        title_box=[m,m,cw,min(1.1,ch*.18)]
        image_top=title_box[1]+title_box[3]+.35
        image_bottom=max(image_top+.3,min(ib[1]+ib[3],tb[1]-.2))
        ib=[ib[0],image_top,ib[2],max(.3,image_bottom-image_top)]
        if tb[1]<image_top+.5:
            tb=[m,max(image_top+.6,h*.64),cw,max(.5,h-m-max(image_top+.6,h*.64))]
    if kind in {'picture-page','education-unit'}:
        from core.inline_images import data as inserted_data
        has_inline=any(item.get('unit')==str(number) for item in inserted_data(snapshot).get('insertions',{}).values())
        if has_inline:
            # A flowing uploaded image needs the page's reading width, not a
            # narrow future-art column. Retain all slot metadata and real art.
            top=title_box[1]+title_box[3]+.35 if title_box else m
            tb=[m,top,cw,h-m-top]
            show_art=bool(stored.get('asset_id'))
    chars_per_line=max(12,tb[2]*72/(s['font_size']*.52))
    import math
    estimated=sum(max(1,math.ceil(len(line)/chars_per_line)) for line in actual_text.split('\n'))*s['font_size']*1.2/72
    overflow=estimated>tb[3]
    return dict(requested=requested,style=style,reason=reason,anchor=ident,logical_page=logical,overflow_warning=overflow,
        show_art=show_art,canvas=[w,h],image_box=ib,text_box=tb,title_box=title_box,spread_id=spread_id,spread_side=side,
        crop=[0,0,.5,1] if side=='left' else [.5,0,1,1] if side=='right' else [0,0,1,1],
        master_image_width=2*w if spread_id else w,master_image_height=h)


def thumbnail(style,w,h):
    """Local SVG sample artwork: sky, hills, sun, tree and fox; no provider call."""
    width=220;height=width*h/w/(2 if style=='spread' else 1)
    def artwork(x,y,bw,bh):
        return f'<svg x="{x}" y="{y}" width="{bw}" height="{bh}" viewBox="0 0 220 160" preserveAspectRatio="xMidYMid slice"><rect width="220" height="160" fill="#d9eff4"/><circle cx="171" cy="32" r="18" fill="#f5ce67"/><path d="M0 119 Q70 63 137 113 T240 100V160H0" fill="#94bda1"/><path d="M0 141 Q115 95 220 141V160H0" fill="#467d65"/><rect x="35" y="63" width="9" height="65" fill="#79614c"/><circle cx="39" cy="58" r="28" fill="#39775b"/><path d="M98 117l-13-25 22 10 25-10-4 31z" fill="#d88545"/><ellipse cx="113" cy="131" rx="26" ry="15" fill="#d88545"/><path d="M95 117l15 14 17-14z" fill="#fff3db"/><circle cx="101" cy="113" r="2"/><circle cx="120" cy="113" r="2"/></svg>'
    def words(x,y,bw,bh):
        return f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="3" fill="white" opacity=".94"/><text x="{x+7}" y="{y+16}" font-size="10" fill="#20382d">One little seed.</text><path d="M{x+7} {y+25}h{bw*.77}m{-bw*.77} 8h{bw*.6}" stroke="#67796d" stroke-width="2"/>'
    if style=='classic':body=artwork(8,8,width-16,height*.6)+words(8,height*.65,width-16,height*.29)
    elif style=='full_page':body=artwork(0,0,width,height)+words(12,height*.68,width-24,height*.25)
    elif style=='split':body=artwork(8,8,width*.46,height-16)+words(width*.52,8,width*.44,height-16)
    elif style=='spread':body=artwork(0,0,width,height)+words(8,height*.68,width*.46,height*.24)+f'<path d="M110 0V{height}" stroke="#78978a" stroke-width="2"/>'
    else:
        body=artwork(6,6,100,height*.46)+words(6,height*.34,100,height*.15)+artwork(114,6,100,height*.3)+words(114,height*.32,100,height*.16)+artwork(6,height*.54,100,height*.40)+words(114,height*.54,100,height*.40)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{STYLES[style]} sample illustration and text placement"><rect width="{width}" height="{height}" fill="#fafbf8"/>{body}<rect x="1" y="1" width="{width-2}" height="{height-2}" fill="none" stroke="#8a9b91"/></svg>'


def controls(context,stage):
    st=context['st'];state=st.session_state
    from core.children_publication import spec
    from core.structure_ui import widget_key
    raw=data(state);current=raw.get('overall_layout',DEFAULT)
    if stage=='concept':
        st.subheader('Illustrated Layout')
        s=spec(state)
        for column,style in zip(st.columns(5),STYLES):
            with column:
                st.image(thumbnail(style,s['width'],s['height']),width='stretch')
                st.caption(STYLES[style]+(' — Recommended' if style==DEFAULT else ''))
    labels=lambda x:STYLES[x]+(' — Recommended' if x==DEFAULT else '')
    choice=st.selectbox('Overall illustrated layout',list(STYLES),index=list(STYLES).index(current),format_func=labels,key=widget_key(state,'overall_illustrated_'+stage+'_'+current))
    if choice!=current:set_overall(state,choice);st.rerun()
    if stage=='concept' and 'overall_layout' not in raw:set_overall(state,current)
    st.caption('Story-Adaptive uses saved storyline, page-turn boundaries and learning activities to recommend placement. It never rewrites story text. Individual page choices take priority.')
    with st.expander('Individual page layout overrides',expanded=False):
        records=pages(state)
        if not records:return
        byid={anchor(p['kind'],p['number']):p for p in records}
        ident=st.selectbox('Page to customize',list(byid),format_func=lambda x:byid[x]['label'],key=widget_key(state,'layout_page_'+stage))
        p=byid[ident];slot=(data(state).get('positions') or {}).get(ident) or {};override=slot.get('layout_override','inherit')
        options=['inherit']+list(STYLES)
        selected=st.selectbox('Layout for this page',options,index=options.index(override),format_func=lambda x:'Use overall layout' if x=='inherit' else labels(x),key=widget_key(state,'layout_override_'+stage+'_'+ident+'_'+override))
        if selected!=override:set_override(state,p['kind'],p['number'],selected);st.rerun()
        plan=resolve(state,p['kind'],p['number'],p['text']);st.caption('Placement: '+STYLES[plan['style']]+' — '+plan['reason'])
        if st.button('Save Illustrated Layout to Current Revision',key=widget_key(state,'save_arrangement_'+stage)):
            from core.children_publication import save
            try:save(context)
            except (ValueError,RuntimeError) as exc:st.error(str(exc))
            else:st.success('Layout saved; manuscript and V-number unchanged.');st.rerun()

def word_frame(paragraph,box):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    ppr=paragraph._p.get_or_add_pPr()
    for old in ppr.findall(qn('w:framePr')):ppr.remove(old)
    frame=OxmlElement('w:framePr')
    for name,value in dict(x=round(box[0]*1440),y=round(box[1]*1440),w=round(box[2]*1440),h=round(box[3]*1440),hRule='atLeast',hAnchor='page',vAnchor='page',wrap='none').items():frame.set(qn('w:'+name),str(value))
    ppr.append(frame)
    paragraph.paragraph_format.space_before=Pt(0);paragraph.paragraph_format.space_after=Pt(4)
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'FFFFFF');ppr.append(shade)


def word_art(doc,snapshot,kind,number,text='',resolve_asset=None):
    """Native positioned Word illustration and a shared, inspectable plan."""
    from lxml import etree
    from docx.oxml.ns import qn
    from core.children_publication import position
    from io import BytesIO
    plan=resolve(snapshot,kind,number,text);slot=position(snapshot,kind,number)
    if not plan['show_art']:return plan
    x,y,w,h=plan['image_box'];v='urn:schemas-microsoft-com:vml'
    p=doc.add_paragraph();p.paragraph_format.space_after=0
    pict=etree.SubElement(p.add_run()._r,qn('w:pict'))
    rect=etree.SubElement(pict,'{'+v+'}rect',nsmap={'v':v})
    rect.set('id','wbs_'+re.sub(r'[^a-zA-Z0-9_]','_',plan['anchor']))
    rect.set('title',STYLES[plan['style']]+'; '+(plan['spread_id'] or plan['anchor']))
    rect.set('style',f'position:absolute;margin-left:{x*72:g}pt;margin-top:{y*72:g}pt;width:{w*72:g}pt;height:{h*72:g}pt;z-index:-251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page')
    rect.set('fillcolor','#e6efeb');rect.set('strokecolor','#a7b9af')
    asset_id=slot.get('asset_id')
    if not asset_id and plan['spread_id']:
        records=pages(snapshot);peer=records[plan['logical_page'] if plan['spread_side']=='left' else plan['logical_page']-2]
        asset_id=((data(snapshot).get('positions') or {}).get(anchor(peer['kind'],peer['number'])) or {}).get('asset_id')
    if resolve_asset and asset_id:
        supplied=resolve_asset(asset_id);asset_bytes=supplied if isinstance(supplied,bytes) else supplied.read()
        if plan['spread_id']:
            from PIL import Image
            image=Image.open(BytesIO(asset_bytes));box=plan['crop'];image=image.crop(tuple(round(n*d) for n,d in zip(box,[image.width,image.height,image.width,image.height])))
            buffer=BytesIO();image.save(buffer,format='PNG');asset_bytes=buffer.getvalue()
        rid,_=doc.part.get_or_add_image(BytesIO(asset_bytes));image=etree.SubElement(rect,'{'+v+'}imagedata');image.set(qn('r:id'),rid)
    else:
        tb=etree.SubElement(rect,'{'+v+'}textbox');tb.set('inset','8pt,8pt,8pt,8pt')
        body=etree.SubElement(tb,qn('w:txbxContent'));para=etree.SubElement(body,qn('w:p'));run=etree.SubElement(para,qn('w:r'));node=etree.SubElement(run,qn('w:t'))
        node.text='Illustration — '+plan['anchor']+(' · '+plan['spread_id']+' '+plan['spread_side'] if plan['spread_id'] else '')+'\n'+(slot.get('description') or 'Reserved illustration area')+('\n'+str(slot['caption']) if slot.get('caption') else '')
    return plan


def educational_docx(doc,snapshot,resolve_asset=None):
    """Apply the plan to complete existing pages, retaining every teaching field."""
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    records=pages(snapshot);groups=[[]]
    for node in list(doc.element.body):
        if node.tag==qn('w:sectPr'):continue
        if node.tag==qn('w:p') and node.xpath('.//w:br[@w:type="page"]'):
            groups.append([])
            if not ''.join(node.xpath('.//w:t/text()')):continue
        groups[-1].append(node)
    for node in list(doc.element.body):
        if node.tag!=qn('w:sectPr'):doc.element.body.remove(node)
    for index,nodes in enumerate(groups):
        if index:doc.add_page_break()
        record=records[index] if index<len(records) else dict(kind='education-continuation',number=index+1,text='')
        text='\n'.join(''.join(n.xpath('.//w:t/text()')) for n in nodes)
        if record['kind']=='education-guide':
            # Adult instructions are flowing reference matter, not a fixed canvas.
            # Word may create as many continuation pages as the saved text needs.
            for node in nodes:
                doc.element.body.insert(len(doc.element.body)-1,node)
                if node.tag==qn('w:p'):
                    ppr=node.find(qn('w:pPr'))
                    if ppr is not None:
                        for frame in list(ppr.findall(qn('w:framePr'))):ppr.remove(frame)
            continue
        plan=word_art(doc,snapshot,record['kind'],record['number'],text,resolve_asset)
        for node in nodes:
            doc.element.body.insert(len(doc.element.body)-1,node)
            if node.tag==qn('w:p'):word_frame(Paragraph(node,doc),plan['text_box'])
    return doc
