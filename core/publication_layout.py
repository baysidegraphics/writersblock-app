"""Publication rendering from saved writing. Format rules live with each format."""
from copy import deepcopy
from importlib import import_module
from io import BytesIO
import html,re
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def specification(snapshot):
    from core.registry import get_format
    fmt=snapshot['active_format_id'];get_format(fmt)
    result=deepcopy(import_module('formats.'+fmt+'.publication').SPEC)
    if fmt in {'childrens_picture_book','childrens_interactive_educational'}:
        from core.children_publication import spec
        p=spec(snapshot);result.update(page_width=p['width'],page_height=p['height'],size=p['font_size'])
    return result


def decorate_document(doc,snapshot):
    s=specification(snapshot);children=snapshot['active_format_id'].startswith('childrens_')
    if not children:
        for section in doc.sections:
            section.page_width=Inches(s['page_width']);section.page_height=Inches(s['page_height'])
            section.left_margin,section.right_margin,section.top_margin,section.bottom_margin=[Inches(v) for v in s['margins']]
    for name in ('Normal','Title','Heading 1','Heading 2','Heading 3','Caption'):
        style=doc.styles[name];style.font.name=s['font'];style.font.color.rgb=RGBColor(0,0,0)
        style.font.size=Pt(s['size'] if name in ('Normal','Title','Caption') or s['font']=='Courier New' else s['size']+2)
    normal=doc.styles['Normal'].paragraph_format;normal.line_spacing=s['spacing'];normal.space_after=Pt(0 if s['spacing']==2 else 4)
    normal.widow_control=True
    for section in doc.sections:
        is_footer=s.get('footer')=='center' or children
        target=section.footer if is_footer else section.header
        if not any(p._p.xpath('.//w:fldChar') for p in target.paragraphs):
            p=target.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER if is_footer else WD_ALIGN_PARAGRAPH.RIGHT
            run=p.add_run();run.font.name=s['font'];run.font.size=Pt(s['size'] if snapshot['active_format_id']=='audiobook' else 10)
            for tag,kind in [('begin','fldChar'),('PAGE','instrText'),('end','fldChar')]:
                el=OxmlElement('w:'+kind)
                if kind=='fldChar':el.set(qn('w:fldCharType'),tag)
                else:el.text=' PAGE '
                run._r.append(el)
    return doc


def _style(doc,name,**kwargs):
    from docx.enum.style import WD_STYLE_TYPE
    style=doc.styles[name] if name in doc.styles else doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
    style.base_style=doc.styles['Normal'];p=style.paragraph_format
    for k,v in kwargs.items():setattr(p,k,v)
    return style


def install_styles(doc,snapshot):
    decorate_document(doc,snapshot)
    _style(doc,'WBS Prose',first_line_indent=Inches(.5),space_after=Pt(0))
    _style(doc,'WBS Action',space_before=Pt(6),space_after=Pt(0))
    _style(doc,'WBS Scene Heading',keep_with_next=True,space_before=Pt(12),space_after=Pt(6)).font.bold=True
    _style(doc,'WBS Speaker',keep_with_next=True,space_before=Pt(6),space_after=Pt(0)).font.bold=True
    _style(doc,'WBS Dialogue',space_after=Pt(0))
    _style(doc,'WBS Parenthetical',keep_with_next=True,space_after=Pt(0))
    _style(doc,'WBS Direction',space_before=Pt(4),space_after=Pt(4)).font.italic=True
    _style(doc,'WBS Cue',space_after=Pt(4))
    _style(doc,'WBS Spoken',space_after=Pt(4)).font.bold=True;doc.styles['WBS Spoken'].font.italic=True
    _style(doc,'WBS Narration',space_after=Pt(4))
    _style(doc,'WBS Host Dialogue',left_indent=Inches(.2),space_after=Pt(4))
    _style(doc,'WBS Guest Dialogue',left_indent=Inches(.45),space_after=Pt(4))
    _style(doc,'WBS Transition',alignment=WD_ALIGN_PARAGRAPH.RIGHT)
    _style(doc,'WBS Visual Direction',space_after=Pt(4)).font.italic=True
    _style(doc,'WBS Timing',keep_with_next=True,space_before=Pt(8)).font.bold=True
    fmt=snapshot['active_format_id']
    if fmt=='screenplay':
        doc.styles['WBS Speaker'].paragraph_format.left_indent=Inches(2.2)
        doc.styles['WBS Speaker'].font.bold=False
        doc.styles['WBS Dialogue'].paragraph_format.left_indent=Inches(1)
        doc.styles['WBS Dialogue'].paragraph_format.right_indent=Inches(1.5)
        doc.styles['WBS Parenthetical'].paragraph_format.left_indent=Inches(1.6)
        doc.styles['WBS Parenthetical'].paragraph_format.right_indent=Inches(1.4)
    elif fmt=='stage_play':
        doc.styles['Heading 1'].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        doc.styles['Heading 2'].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        doc.styles['WBS Scene Heading'].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        doc.styles['WBS Speaker'].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        doc.styles['WBS Direction'].paragraph_format.left_indent=Inches(2)
    return doc


def role_lines(text,fmt):
    """Classify, never rewrite, source lines. Preserve whitespace and case."""
    previous='';speaker=''
    prose=fmt in {'short_story','novel_prose_novella','standard_manuscript','biography_memoir'}
    if prose:
        return [(x,'WBS Prose') for x in str(text).split('\n\n')]
    out=[]
    for raw in str(text).split('\n'):
        stripped=raw.strip();style='WBS Action'
        if not stripped:style='Normal';previous=''
        elif re.match(r'^(INT\.|EXT\.|INT\./EXT\.|ACT\b|SCENE\b|CHAPTER\b|PART\b)',stripped,re.I):style='WBS Scene Heading';previous='';speaker=''
        elif fmt in {'screenplay','stage_play'} and (stripped.startswith('[') and stripped.endswith(']')):
            style='WBS Direction';previous='';speaker=''
        elif fmt in {'screenplay','stage_play'} and re.match(r'^(ACTION|STAGE DIRECTIONS?)\s*:',stripped,re.I):
            style='WBS Action' if fmt=='screenplay' else 'WBS Direction';previous='';speaker=''
        elif fmt=='audiobook' and stripped.startswith('[') and stripped.endswith(']'):style='WBS Cue'
        elif fmt=='podcast_script' and re.match(r'^\[?\d{1,2}:\d{2}(?::\d{2})?\]?(?:\s*[-–].*)?$',stripped):style='WBS Timing'
        elif fmt=='podcast_script' and re.match(r'^(HOST|GUEST|NARRATOR|NARRATION)\s*:',stripped,re.I):
            speaker=stripped.split(':',1)[0].upper();previous='speaker'
            style='WBS Speaker' if not stripped.split(':',1)[1].strip() else 'WBS Host Dialogue' if speaker=='HOST' else 'WBS Guest Dialogue' if speaker=='GUEST' else 'WBS Narration'
        elif re.match(r'^\[(SFX|MUSIC|BED|PAUSE|AMBIENCE|PRONUNCIATION|PERFORMANCE|NOTE)\b',stripped,re.I):style='WBS Cue'
        elif re.match(r'^(SFX|MUSIC|SOUND|BED|PAUSE)\s*:',stripped,re.I):style='WBS Cue'
        elif re.match(r'^\d{1,2}:\d{2}(?:\s*[-–].*)?$',stripped):style='WBS Timing'
        elif re.match(r'^(ON SCREEN|VISUAL|CAPTION|B-ROLL)\s*:',stripped,re.I):style='WBS Visual Direction'
        elif stripped.startswith('(') and stripped.endswith(')'):style='WBS Parenthetical' if fmt=='screenplay' else 'WBS Direction'
        elif stripped.upper() in {'FADE IN:','FADE OUT.','CUT TO:','DISSOLVE TO:'}:style='WBS Transition';previous=''
        elif stripped.isupper() and len(stripped.split())<=7 and not stripped.endswith(('.', '!', '?')) and not stripped.startswith('['):
            style='WBS Speaker';speaker=stripped.rstrip(':');previous='speaker'
        elif fmt=='audiobook':style='WBS Narration' if speaker in ('','NARRATOR') else 'WBS Spoken'
        elif fmt=='podcast_script' and speaker:
            style='WBS Host Dialogue' if speaker=='HOST' else 'WBS Guest Dialogue' if speaker=='GUEST' else 'WBS Narration'
        elif previous in ('speaker','dialogue') and fmt in {'screenplay','stage_play'}:style='WBS Dialogue';previous='dialogue'
        if style=='WBS Parenthetical':previous='dialogue'
        out.append((raw,style))
    return out


def anchors(snapshot):
    from core.manuscript_structure import profile,unit_plan,values
    fmt=snapshot['active_format_id'];p=profile(fmt)
    if fmt=='youtube_shorts':return ['segment-'+str(r['unit_id']) for r in unit_plan(snapshot)]
    if fmt=='biography_memoir':return ['chapter-'+str(r['chapter_number']) for r in values(snapshot).get('chapters') or []]
    if p['group']:return [p['group'].lower().replace(' ','-')+'-'+str(n) for n in sorted({r['group_number'] for r in unit_plan(snapshot)})]
    return ['section-'+str(r['unit_id']) for r in unit_plan(snapshot)]


def structured_docx(snapshot,base_bytes=None,resolve_asset=None):
    from core.manuscript_structure import profile,unit_plan,unit_heading,blocks
    from core.print_export import bytes_for
    from core.image_placement import add_docx
    fmt=snapshot['active_format_id'];p=profile(fmt);writing=blocks(snapshot)
    doc=Document(BytesIO(base_bytes)) if base_bytes else Document()
    for node in list(doc.element.body):
        if node.tag!=qn('w:sectPr'):doc.element.body.remove(node)
    install_styles(doc,snapshot)
    title=doc.add_heading(str(snapshot.get('project_title') or 'Untitled Project'),0);title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    if fmt=='audiobook':
        subtitle=doc.add_paragraph('AUDIOBOOK THEATRE PRODUCTION SCRIPT','WBS Speaker');subtitle.alignment=WD_ALIGN_PARAGRAPH.CENTER
    if fmt in {'screenplay','stage_play'}:
        title.paragraph_format.space_before=Inches(3)
        from docx.enum.section import WD_SECTION
        body=doc.add_section(WD_SECTION.NEW_PAGE);body.header.is_linked_to_previous=False;body.footer.is_linked_to_previous=False
        body.different_first_page_header_footer=fmt=='screenplay'
        num=OxmlElement('w:pgNumType');num.set(qn('w:start'),'1');body._sectPr.append(num)
        for part in (doc.sections[0].header,doc.sections[0].footer):
            for para in part.paragraphs:
                for child in list(para._p):para._p.remove(child)
        decorate_document(doc,snapshot)
        # Keep the title page free of running page numbers.
        doc.sections[0].different_first_page_header_footer=True
    group=None;first=True;podcast_seconds=0
    planned=unit_plan(snapshot)
    for row_index,row in enumerate(planned):
        if p['group'] and row['group_number']!=group:
            group=row['group_number'];podcast_seconds=0
            if not first and p['group'] in {'Chapter','Act','Part','Episode','Episode / Short'}:doc.add_page_break()
            doc.add_heading(p['group']+' '+str(group)+(' — '+row['group_title'] if row['group_title'] else ''),1)
            if fmt=='novel_prose_novella':
                from core.image_placement import slot
                if slot(snapshot,'chapter-'+str(group))['placement']=='chapter_start':add_docx(doc,snapshot,'chapter-'+str(group),resolve_asset)
            elif fmt!='youtube_shorts':add_docx(doc,snapshot,p['group'].lower().replace(' ','-')+'-'+str(group),resolve_asset)
        if fmt=='short_story':
            if not first:
                separator=doc.add_paragraph('* * *');separator.alignment=WD_ALIGN_PARAGRAPH.CENTER
        else:
            source=writing.get(row['unit_id'],'')
            first_line=source.split('\n',1)[0].strip()
            default=row['title'].strip()==p['unit']+' '+str(row['unit_number'])
            self_headed=fmt in {'stage_play','full_novel_blueprint'} and re.match(r'^(SCENE|CHAPTER)\s+'+str(row['unit_number'])+r'\b',first_line,re.I)
            if not (default and self_headed):doc.add_heading(unit_heading(p,row),2 if p['group'] else 1)
        if fmt=='podcast_script' and not re.search(r'(?m)^\s*\[?\d{1,2}:\d{2}(?::\d{2})?',writing.get(row['unit_id'],'')):
            # An explicitly labeled rehearsal estimate, never an invented recording time.
            spoken=' '.join(t for t,role in role_lines(writing.get(row['unit_id'],''),fmt) if role in {'WBS Host Dialogue','WBS Guest Dialogue','WBS Narration'})
            duration=max(1,round(len(spoken.split())*60/140))
            stamp=lambda n:f'{n//60:02d}:{n%60:02d}'
            doc.add_paragraph(stamp(podcast_seconds)+' - '+stamp(podcast_seconds+duration)+' | Estimated speech timing (140 words/min; excludes music, SFX and pauses)', 'WBS Timing')
            podcast_seconds+=duration
        if fmt=='youtube_shorts':add_docx(doc,snapshot,'segment-'+str(row['unit_id']),resolve_asset)
        for text,style in role_lines(writing.get(row['unit_id'],''),fmt):
            if fmt in {'podcast_script','youtube_shorts','full_novel_blueprint'} and re.match(r'^(HOST|GUEST|VOICEOVER|NARRATOR|SFX|MUSIC|ON SCREEN|CAPTION|Objective|Consequence)\s*:',text,re.I):
                label,rest=text.split(':',1);paragraph=doc.add_paragraph(style=style);paragraph.add_run(label+':').bold=True;paragraph.add_run(rest)
            else:doc.add_paragraph(text,style)
        if fmt=='full_novel_blueprint' and row['detail']:
            doc.add_heading('Scene and Beat Plan',3);doc.add_paragraph(row['detail'])
        if fmt=='novel_prose_novella' and (row_index==len(planned)-1 or planned[row_index+1]['group_number']!=group):
            if slot(snapshot,'chapter-'+str(group))['placement']=='chapter_end':add_docx(doc,snapshot,'chapter-'+str(group),resolve_asset)
        first=False
    from core.inline_images import apply_to_doc
    apply_to_doc(doc,snapshot)
    return bytes_for(doc)


def build_docx(snapshot,resolve_asset=None):
    fmt=snapshot['active_format_id']
    if fmt=='childrens_picture_book':
        from formats.childrens_picture_book.page_turns import export_docx
        return export_docx(snapshot,resolve_asset=resolve_asset)
    if fmt in {'biography_memoir','childrens_interactive_educational'}:
        return import_module('formats.'+fmt+'.exports').build_docx(snapshot,resolve_asset=resolve_asset)
    return structured_docx(snapshot,resolve_asset=resolve_asset)


def render_preview(st,snapshot):
    """Use actual DOCX paragraph styles and sections, not a separate text template."""
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    doc=Document(BytesIO(build_docx(snapshot)));s=specification(snapshot)
    # Web pagination honors explicit boundaries and estimates overflow using
    # the same physical widths/fonts. Word remains the final overflow renderer.
    pages=[];parts=[];used=0;page=1;scale=64
    section=doc.sections[-1];w=section.page_width.inches;h=section.page_height.inches
    left=section.left_margin.inches;right=section.right_margin.inches
    top=section.top_margin.inches;bottom=section.bottom_margin.inches
    capacity=(h-top-bottom)*72
    def flush():
        nonlocal parts,used,page
        if parts:pages.append((page,''.join(parts)));page+=1
        parts=[];used=0
    for node in doc.element.body:
        if node.tag==qn('w:p'):
            p=Paragraph(node,doc);text=p.text
            if node.xpath('.//w:br[@w:type="page"]') or node.xpath('./w:pPr/w:sectPr'):flush()
            if not text and not node.xpath('.//w:drawing'):continue
            style=p.style;fmt=p.paragraph_format;inherited=style.paragraph_format
            font=style.font.name or s['font'];size=(style.font.size.pt if style.font.size else s['size'])
            li=(fmt.left_indent or inherited.left_indent);ri=(fmt.right_indent or inherited.right_indent)
            li=li.inches if li else 0;ri=ri.inches if ri else 0
            indent=fmt.first_line_indent if fmt.first_line_indent is not None else inherited.first_line_indent
            indent=indent.inches if indent else 0
            available=max(.5,w-left-right-li-ri)*72
            charwidth=size*(.6 if font=='Courier New' else .48)
            lines=sum(max(1,__import__('math').ceil(len(line)*charwidth/available)) for line in text.split('\n'))
            spacing=fmt.line_spacing or inherited.line_spacing or s['spacing'];spacing=float(spacing) if isinstance(spacing,(int,float)) and spacing<10 else s['spacing']
            before=fmt.space_before or inherited.space_before;after=fmt.space_after or inherited.space_after
            height=lines*size*spacing+(before.pt if before else 0)+(after.pt if after else 0)
            if parts and used+height>capacity:flush()
            alignment=fmt.alignment if fmt.alignment is not None else inherited.alignment
            align={WD_ALIGN_PARAGRAPH.CENTER:'center',WD_ALIGN_PARAGRAPH.RIGHT:'right'}.get(alignment,'left')
            bold=style.font.bold;italic=style.font.italic
            from core.image_editor import paragraph_html
            content=paragraph_html(p,scale)
            image_heights=node.xpath('.//wp:extent/@cy')
            if image_heights:height=max(height,max(int(v)/914400*72 for v in image_heights))
            parts.append('<div data-docx-style="'+html.escape(style.name)+'" style="display:flow-root;white-space:pre-wrap;overflow-wrap:anywhere;font-family:'+html.escape(font)+';font-size:'+str(size*scale/72)+'px;line-height:'+str(spacing)+';text-indent:'+str(indent*scale)+'px;margin-left:'+str(li*scale)+'px;margin-right:'+str(ri*scale)+'px;margin-top:'+str((before.pt if before else 0)*scale/72)+'px;margin-bottom:'+str((after.pt if after else 0)*scale/72)+'px;text-align:'+align+';font-weight:'+('700' if bold else '400')+';font-style:'+('italic' if italic else 'normal')+'">'+content+'</div>');used+=height
        elif node.tag==qn('w:tbl'):
            table=Table(node,doc);height=table.rows[0].height.inches if table.rows and table.rows[0].height else 1
            if parts and used+height*72>capacity:flush()
            content='\n'.join(c.text for row in table.rows for c in row.cells)
            image_width=table.columns[0].width.inches if table.columns and table.columns[0].width else w-left-right
            image_alignment=int(table.alignment) if table.alignment is not None else 0
            image_margins=('margin-left:0;margin-right:auto;' if image_alignment==0 else 'margin-left:auto;margin-right:0;' if image_alignment==2 else 'margin-left:auto;margin-right:auto;')
            parts.append('<div class="wbs-publication-image" style="width:'+str(image_width*scale)+'px;max-width:100%;'+image_margins+'font-family:'+html.escape(s['font'])+';font-size:'+str(s['size']*scale/72)+'px;border:1px dashed #999;min-height:'+str(height*scale)+'px;white-space:pre-wrap;text-align:center;display:flex;align-items:center;justify-content:center">'+html.escape(content)+'</div>');used+=height*72
    flush()
    st.caption(s['label']+' · Preview uses export typography, dimensions and explicit page breaks. Word determines final overflow pagination.')
    for number,body in pages:
        scripted=snapshot['active_format_id'] in {'screenplay','stage_play'}
        displayed=number-1 if scripted else number
        page_label='Title page' if scripted and number==1 else 'Page '+str(displayed)
        footer=s.get('footer')=='center' or snapshot['active_format_id'].startswith('childrens_')
        hidden=scripted and (number==1 or (snapshot['active_format_id']=='screenplay' and number==2))
        running='' if hidden else '<div class="wbs-running-page-number" data-position="'+('bottom-center' if footer else 'top-right')+'" style="position:absolute;'+('bottom' if footer else 'top')+':32px;left:0;right:'+('0' if footer else str(right*scale)+'px')+';text-align:'+('center' if footer else 'right')+';font-family:'+html.escape(s['font'])+';font-size:'+str((12 if snapshot['active_format_id']=='audiobook' else 10)*scale/72)+'px">'+str(displayed)+'</div>'
        def responsive(markup):
            def convert(match):
                value=re.sub(r'(-?\d+(?:\.\d+)?)px',lambda px:str(float(px[1])/(w*scale)*100)+'cqw',match[1])
                return 'style="'+value+'"'
            return re.sub(r'style="([^"]*)"',convert,markup)
        body=responsive(body);running=responsive(running)
        st.markdown('<div class="wbs-layout-page-label" style="font-size:.8rem">'+page_label+'</div><div style="width:'+str(w*scale)+'px;max-width:100%;container-type:inline-size"><article class="wbs-format-publication-page" data-format="'+snapshot['active_format_id']+'" data-page-number="'+str(displayed)+'" style="position:relative;box-sizing:border-box;background:white;color:black;width:100%;aspect-ratio:'+str(w)+' / '+str(h)+';padding:'+str(top/w*100)+'cqw '+str(right/w*100)+'cqw '+str(bottom/w*100)+'cqw '+str(left/w*100)+'cqw;margin:1rem 0;border:1px solid #999;break-before:page">'+running+body+'</article></div>',unsafe_allow_html=True)



def render_final(context):
    st=context['st'];state=st.session_state;fmt=state['active_format_id']
    if fmt=='childrens_picture_book':
        from formats.childrens_picture_book.page_turn_ui import final
        result=final(context)
        from core.format_services import coach
        coach(context)
        return result
    if fmt in {'biography_memoir','childrens_interactive_educational'}:
        return import_module('formats.'+fmt+'.final_manuscript').render(context)
    st.header('6. '+specification(state)['label']+' — Final Manuscript')
    from core.saved_scene_state import saved_snapshot_for_session
    from core.image_placement import allowed,controls,settings
    if allowed(state):controls(context,anchors(state))
    render_preview(st,state)
    if not context['wbs_editorial_ready_for_assessment']():
        st.warning('Approve the exact saved manuscript and Integrity Report in Stage 4 before downloading.');return
    if state.get('demo_mode'):st.info('Downloads require the full Writer Edition.');return
    saved=saved_snapshot_for_session(state)
    if allowed(state) and settings(state)!=settings(saved):
        st.warning('Save the adjusted image layout before downloading.');return
    from core.text import safe_download_stem
    stem=safe_download_stem(state.get('project_title') or 'manuscript')
    if fmt=='short_story' or fmt in __import__('core.inline_images',fromlist=['SUPPORTED']).SUPPORTED:
        from core.image_pdf import download
        download(st,build_docx(saved),stem,'publication_image',preserve_paragraph_layout=fmt=='short_story')
    st.download_button('Download Formatted Manuscript (.docx)',data=build_docx(saved),file_name=stem+'.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key='publication_docx')
    text=state.get('current_draft_output') or ''
    from core.manuscript_structure import configured
    if fmt!='short_story' and configured(saved):
        from core.manuscript_structure import export_text
        text=export_text(saved)
    st.download_button('Download Manuscript Text (.txt)',data=text,file_name=stem+'.txt',mime='text/plain',key='publication_txt')
    from core.format_services import coach
    coach(context)
