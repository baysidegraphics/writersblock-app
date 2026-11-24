"""Embedded author images; no storage service, network, filesystem assets or prose tokens."""
import base64,hashlib,html,re,warnings
from copy import deepcopy
from io import BytesIO
SUPPORTED={'novel_prose_novella','standard_manuscript','biography_memoir','childrens_picture_book','childrens_interactive_educational','youtube_shorts'}
SIZES={'Small':.25,'Medium':.40,'Large':.60}


def data(state):
    from core.image_placement import settings
    if state.get('active_format_id') not in SUPPORTED:raise ValueError('Inline illustrations are not supported by this writing format.')
    return settings(state)


def upload(state,content,name):
    from PIL import Image,ImageOps
    if len(content)>8*1024*1024:raise ValueError('Choose an image smaller than 8 MB.')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        try:
            image=Image.open(BytesIO(content))
            if image.format not in {'JPEG','PNG','WEBP'}:raise ValueError('Only JPG, PNG and WEBP images are supported.')
            if image.width*image.height>20_000_000:raise ValueError('Choose an image smaller than 20 megapixels.')
            image.load();image=ImageOps.exif_transpose(image).convert('RGBA')
            out=BytesIO();image.save(out,format='PNG');payload=out.getvalue()
        except (OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:raise ValueError('This image could not be safely decoded.') from exc
    if len(payload)>10*1024*1024:raise ValueError('Decoded image is too large; reduce its dimensions.')
    raw=data(state);assets=raw.setdefault('assets',{});ident=hashlib.sha256(payload).hexdigest()
    if sum(len(a['png']) for a in assets.values())+len(payload)*4/3>32*1024*1024 and ident not in assets:raise ValueError('Project image storage limit reached (32 MB).')
    assets[ident]={'png':base64.b64encode(payload).decode('ascii'),'width':image.width,'height':image.height,'name':str(name).replace('\\','/').rsplit('/',1)[-1][:120]}
    from core.image_placement import KEY
    state[KEY]=raw
    return ident


def place(state,unit,source,offset,asset,size='Medium',align='Center',ident=None):
    if size not in SIZES or align not in {'Left','Center','Right'}:raise ValueError('Invalid image size or alignment.')
    if not 0<=offset<=len(source):raise ValueError('Choose an insertion point inside the text.')
    raw=data(state)
    if asset not in raw.get('assets',{}):raise ValueError('Upload this project image first.')
    if ident is None:
        from uuid import uuid4
        ident=uuid4().hex
    raw.setdefault('insertions',{})[ident]={'unit':str(unit),'asset':asset,'size':size,'align':align,'offset':offset,'source_hash':hashlib.sha256(source.encode()).hexdigest(),'left':source[max(0,offset-80):offset],'right':source[offset:offset+80]}
    from core.image_placement import KEY
    state[KEY]=raw
    return ident


def locate(item,source):
    if hashlib.sha256(source.encode()).hexdigest()==item['source_hash']:return item['offset']
    left,right=item['left'],item['right'];candidates=[]
    for offset in range(len(source)+1):
        if (not left or source[:offset].endswith(left)) and (not right or source[offset:].startswith(right)):candidates.append(offset)
    if len(candidates)!=1:raise ValueError('An image insertion point changed. Reposition that image in the editor before exporting; its data is retained.')
    return candidates[0]


def center_boundary(source,offset):
    if offset==0 or offset==len(source) or source[max(0,offset-2):offset]=='\n\n':return offset
    boundary=source.find('\n\n',offset)
    return len(source) if boundary<0 else boundary


def word_boundary(source,offset):
    if 0<offset<len(source) and not source[offset-1].isspace() and not source[offset].isspace():
        while offset<len(source) and not source[offset].isspace():offset+=1
    return offset


def entries(state,unit,source):
    raw=data(state)
    return sorted([(center_boundary(source,locate(item,source)) if item['align']=='Center' else word_boundary(source,locate(item,source)),ident,item) for ident,item in raw.get('insertions',{}).items() if item['unit']==str(unit)],key=lambda r:(r[0],r[1]))


def dimensions(state,item):
    from core.publication_layout import specification
    spec=specification(state);asset=data(state)['assets'][item['asset']]
    usable_width=spec['page_width']-spec['margins'][0]-spec['margins'][1]
    width=usable_width*SIZES[item['size']]
    height=width*asset['height']/asset['width'];maximum=spec['page_height']-spec['margins'][2]-spec['margins'][3]-.3
    if state['active_format_id'] in {'childrens_picture_book','childrens_interactive_educational'}:
        from core.children_arrangements import resolve
        kind='picture-page' if state['active_format_id']=='childrens_picture_book' else 'education-unit'
        maximum=min(maximum,resolve(state,kind,int(item['unit']))['text_box'][3]-.3)
    if height>maximum:raise ValueError('This image is too tall at the selected preset. Choose a smaller preset or a shorter image; proportions and saved image data are preserved.')
    return width,height


def image_html(state,item,unit_width=None):
    from core.publication_layout import specification
    width,height=dimensions(state,item);asset=data(state)['assets'][item['asset']]
    page=specification(state)['page_width'];width_css=str(width/page*100)+'cqw' if unit_width is None else str(width/unit_width*100)+'%'
    align=item['align'].lower();style='float:'+align+';margin:.12in;' if align!='center' else 'display:block;clear:both;margin:.12in auto;'
    return '<img class="wbs-inserted-image" alt="'+html.escape(asset['name'],quote=True)+'" src="data:image/png;base64,'+asset['png']+'" style="'+style+'width:'+width_css+';max-width:100%;height:auto;break-inside:avoid">'


def flow_html(state,unit,source,unit_width=None):
    parts=[];last=0
    for offset,ident,item in entries(state,unit,source):
        parts.extend([html.escape(source[last:offset]),image_html(state,item,unit_width).replace('<img ','<img data-image-id="'+ident+'" contenteditable="false" draggable="false" ',1)]);last=offset
    return ''.join(parts)+html.escape(source[last:])


def _drawing(doc,item,state):
    from docx.shared import Inches
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    width,height=dimensions(state,item);asset=data(state)['assets'][item['asset']]
    p=doc.add_paragraph();p.add_run().add_picture(BytesIO(base64.b64decode(asset['png'])),width=Inches(width),height=Inches(height))
    p.paragraph_format.first_line_indent=Inches(0)
    p.paragraph_format.keep_together=True
    inline=p._p.xpath('.//wp:inline')[0];inline.docPr.set('descr','WBS embedded image')
    if item['align']=='Center':
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    else:
        anchor=OxmlElement('wp:anchor')
        for k,v in {'distT':'0','distB':'0','distL':'91440','distR':'91440','simplePos':'0','relativeHeight':'0','behindDoc':'0','locked':'1','layoutInCell':'1','allowOverlap':'0'}.items():anchor.set(k,v)
        simple=OxmlElement('wp:simplePos');simple.set('x','0');simple.set('y','0');anchor.append(simple)
        for axis,rel in [('H','column'),('V','paragraph')]:
            pos=OxmlElement('wp:position'+axis);pos.set('relativeFrom',rel)
            value=OxmlElement('wp:align' if axis=='H' else 'wp:posOffset');value.text=item['align'].lower() if axis=='H' else '0';pos.append(value);anchor.append(pos)
        for name in ('extent','effectExtent'):
            node=inline.find(qn('wp:'+name))
            if node is not None:anchor.append(deepcopy(node))
        wrap=OxmlElement('wp:wrapSquare');wrap.set('wrapText','right' if item['align']=='Left' else 'left');anchor.append(wrap)
        for name in ('docPr','cNvGraphicFramePr'):
            node=inline.find(qn('wp:'+name))
            if node is not None:anchor.append(deepcopy(node))
        anchor.append(deepcopy(inline.find(qn('a:graphic'))));inline.getparent().replace(inline,anchor)
    doc.element.body.remove(p._p)
    return p


def apply_to_doc(doc,state):
    if state.get('active_format_id') not in SUPPORTED:return
    raw=data(state)
    if not raw.get('insertions'):return
    from core.manuscript_structure import blocks
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn
    writing=blocks(state);paragraphs=list(doc.paragraphs);cursor=0;found=set()
    from core.manuscript_structure import unit_plan,profile
    order=[r['unit_id'] for r in unit_plan(state)] if profile(state['active_format_id'])['structured_editor'] else sorted(writing)
    order=list(dict.fromkeys(order+list(writing)))
    for unit in order:
        source=writing.get(unit,'')
        items=entries(state,unit,source);source_cursor=0
        if not items:
            # Still walk the prose so identical text in another unit stays distinct.
            pass
        for index in range(cursor,len(paragraphs)):
            p=paragraphs[index];text=p.text
            if not text or p.style.name.startswith(('Heading','Title')) or p._p.xpath('.//w:pict'):continue
            start=source.find(text,source_cursor)
            if start<0:continue
            end=start+len(text);matches=[r for r in items if start<=r[0]<=end and r[1] not in found]
            source_cursor=end;cursor=index+1
            if matches:
                from docx.text.run import Run
                replacement=[]
                def prose(begin,finish,floats):
                    node=deepcopy(p._p)
                    for child in list(node):
                        if child.tag!=qn('w:pPr'):node.remove(child)
                    para=Paragraph(node,p._parent);position=0
                    pending=list(floats)
                    for original in p.runs:
                        run_text=original.text;run_start=position;position+=len(run_text)
                        lo=max(begin,run_start);hi=min(finish,position)
                        if lo>hi:continue
                        cut=lo
                        for where,ident,item in list(pending):
                            if lo<=where<=hi:
                                if where>cut:
                                    r=deepcopy(original._r);Run(r,p._parent).text=text[cut:where];node.append(r)
                                drawing=_drawing(doc,item,state)
                                anchor=drawing._p.xpath('.//wp:positionV')[0];anchor.set('relativeFrom','line')
                                node.append(deepcopy(drawing._p.xpath('./w:r')[0]));found.add(ident)
                                pending.remove((where,ident,item));cut=where
                        if hi>cut:
                            r=deepcopy(original._r);Run(r,p._parent).text=text[cut:hi];node.append(r)
                    if pending:raise ValueError('An image could not be anchored inside its paragraph.')
                    return para
                centers=[r for r in matches if r[2]['align']=='Center']
                floats=[(offset-start,ident,item) for offset,ident,item in matches if item['align']!='Center']
                begin=0
                for offset,ident,item in centers:
                    boundary=offset-start
                    chosen=[r for r in floats if begin<=r[0]<=boundary]
                    if boundary>begin or chosen:replacement.append(prose(begin,boundary,chosen))
                    floats=[r for r in floats if r not in chosen]
                    drawing=_drawing(doc,item,state)
                    frame=p._p.find('./'+qn('w:pPr')+'/'+qn('w:framePr'))
                    if frame is not None:drawing._p.get_or_add_pPr().append(deepcopy(frame))
                    replacement.append(drawing);found.add(ident);begin=boundary
                if begin<len(text) or floats:replacement.append(prose(begin,len(text),floats))
                for new in replacement:p._p.addprevious(new._p)
                p._p.getparent().remove(p._p)
            if source_cursor>=len(source):break
    expected=set(raw['insertions'])
    if found!=expected:raise ValueError('An image anchor could not be matched to saved manuscript text. Reposition the image before export; no image data was removed.')
