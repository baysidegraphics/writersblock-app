"""Local DOCX-to-PDF book flow renderer. No network or customer services."""
from io import BytesIO
import os,sys,importlib.util,subprocess


def _font_family_paths(family):
    """Prefer existing approved Windows fonts; support Linux Liberation families."""
    windows={'WbsTimes':['times.ttf','timesbd.ttf','timesi.ttf','timesbi.ttf'],
             'WbsArial':['arial.ttf','arialbd.ttf','ariali.ttf','arialbi.ttf']}
    liberation={'WbsTimes':['LiberationSerif-Regular.ttf','LiberationSerif-Bold.ttf','LiberationSerif-Italic.ttf','LiberationSerif-BoldItalic.ttf'],
                'WbsArial':['LiberationSans-Regular.ttf','LiberationSans-Bold.ttf','LiberationSans-Italic.ttf','LiberationSans-BoldItalic.ttf']}
    candidates=[]
    configured=os.environ.get('WBS_PDF_FONT_DIR')
    if configured:candidates.extend([(configured,windows[family]),(configured,liberation[family])])
    candidates.append((os.path.join(os.environ.get('WINDIR','C:/Windows'),'Fonts'),windows[family]))
    candidates.extend((folder,liberation[family]) for folder in ('/usr/share/fonts/truetype/liberation2','/usr/share/fonts/truetype/liberation'))
    for folder,names in candidates:
        paths=[os.path.join(folder,name) for name in names]
        if all(os.path.isfile(path) for path in paths):return paths
    return []

def available():
    return importlib.util.find_spec('reportlab') is not None or bool(os.environ.get('WBS_TEST_PDF_WORKER'))

def export_pdf(docx_bytes):
    if importlib.util.find_spec('reportlab') is None:
        worker=os.environ.get('WBS_TEST_PDF_WORKER')
        if not worker:raise RuntimeError('PDF export requires the reportlab dependency listed in requirements.txt.')
        result=subprocess.run([worker,'-X','utf8',__file__],input=docx_bytes,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,check=False)
        if result.returncode or not result.stdout.startswith(b'%PDF'):raise RuntimeError('Local PDF rendering failed; DOCX remains available.')
        return result.stdout
    return render(docx_bytes)


def render(payload):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph as WordParagraph
    from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Image,ParagraphAndImage,PageBreak,FrameBreak,NextPageTemplate,Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Flowable
    import math
    class FloatingImages(Flowable):
        def __init__(self,paragraph,records,planned=False):
            Flowable.__init__(self);self.P=paragraph;self.records=records;self.planned=planned
        def wrap(self,availWidth,availHeight):
            self.width=availWidth;self.P.width=availWidth;leading=self.P.style.leading;full=availWidth-self.P.style.leftIndent-self.P.style.rightIndent
            positioned=[]
            for image,side,prefix in self.records:
                if image.drawWidth+16>=full:raise ValueError('Image leaves no room for wrapped text in this layout.')
                if self.planned:line=prefix
                else:
                    before=Paragraph(escape(prefix) or '&#160;',self.P.style);before.wrap(availWidth,100000)
                    line=max(0,math.ceil(before.height/leading)-1)
                lines=max(1,math.ceil((image.drawHeight+4)/leading))
                while True:
                    overlaps=[r for r in positioned if line<r[2]+r[3] and r[2]<line+lines]
                    blocked=[r for r in overlaps if r[1]==side or r[0].drawWidth+image.drawWidth+32>=full]
                    if not blocked:break
                    line=max(r[2]+r[3] for r in blocked)
                positioned.append((image,side,line,lines))
            self.positioned=positioned;last=max((r[2]+r[3] for r in positioned),default=0)
            widths=[];self.offsets=[]
            for line in range(last+1):
                active=[r for r in positioned if r[2]<=line<r[2]+r[3]]
                left=sum(r[0].drawWidth+8 for r in active if r[1]=='left');right=sum(r[0].drawWidth+8 for r in active if r[1]=='right')
                widths.append(full-left-right-(self.P.style.firstLineIndent if line==0 else 0));self.offsets.append(left)
            widths.append(full);self.offsets.append(0)
            self.P.blPara=self.P.breakLines(widths);self.P.height=len(self.P.blPara.lines)*leading
            self.height=max(self.P.height,last*leading);return self.width,self.height
        def draw(self):
            for image,side,line,lines in self.positioned:
                x=0 if side=='left' else self.width-image.drawWidth
                image.drawOn(self.canv,x,self.height-line*self.P.style.leading-image.drawHeight)
            self.P._offsets=self.offsets
            try:self.P.drawOn(self.canv,0,self.height-self.P.height)
            finally:del self.P._offsets
        def split(self,availWidth,availHeight):
            leading=self.P.style.leading;cut=int(availHeight/leading)
            crossing=[r[2] for r in self.positioned if r[2]<cut<r[2]+r[3]]
            if crossing:cut=min(crossing)
            if cut<1:return []
            pieces=self.P.split(availWidth,cut*leading)
            if not pieces:return []
            if len(pieces)>1:cut=len(pieces[0].blPara.lines)
            if any(r[2]<cut<r[2]+r[3] for r in self.positioned):return []
            first=[(i,s,line) for i,s,line,n in self.positioned if line+n<=cut]
            rest=[(i,s,max(0,line-cut)) for i,s,line,n in self.positioned if line>=cut]
            result=[FloatingImages(pieces[0],first,True)]
            if len(pieces)>1:result.append(FloatingImages(pieces[1],rest,True) if rest else pieces[1]);result.extend(pieces[2:])
            elif rest:result.append(FloatingImages(Paragraph('&#160;',self.P.style),rest,True))
            return result
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from xml.sax.saxutils import escape
    doc=Document(BytesIO(payload));section=doc.sections[-1]
    width,height=section.page_width.pt,section.page_height.pt
    left,right,top,bottom=[x.pt for x in (section.left_margin,section.right_margin,section.top_margin,section.bottom_margin)]
    for family in ('WbsTimes','WbsArial'):
        names=[family,family+'-Bold',family+'-Italic',family+'-BoldItalic']
        for name,path in zip(names,_font_family_paths(family)):
            if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,path))
        if all(n in pdfmetrics.getRegisteredFontNames() for n in names):pdfmetrics.registerFontFamily(family,normal=names[0],bold=names[1],italic=names[2],boldItalic=names[3])
    out=BytesIO();pdf=BaseDocTemplate(out,pagesize=(width,height),leftMargin=left,rightMargin=right,topMargin=top,bottomMargin=bottom,title=doc.core_properties.title or 'WBS manuscript')
    groups=[[]]
    for node in doc.element.body:
        if node.tag==qn('w:p'):
            if node.xpath('.//w:br[@w:type="page"]'):groups.append([])
            p=WordParagraph(node,doc)
            if not p.text and not node.xpath('.//w:drawing'):continue
            if node.xpath('.//w:pict'):continue
            groups[-1].append(p)
    def draw_page(canvas,document):
        canvas.saveState();canvas.setFont('Times-Roman',10)
        footer=any(p._p.xpath('.//w:fldChar') for p in section.footer.paragraphs)
        if footer:canvas.drawCentredString(width/2,bottom/2,str(document.page))
        else:canvas.drawRightString(width-right,height-top/2,str(document.page))
        canvas.restoreState()
    story=[]
    for index,paragraphs in enumerate(groups):
        frames=[];runs=[];last_key=None
        for p in paragraphs:
            f=p._p.find('./'+qn('w:pPr')+'/'+qn('w:framePr'))
            key=tuple(f.get(qn('w:'+k)) for k in ('x','y','w','h')) if f is not None else None
            if not runs or key!=last_key:
                runs.append((key,[]));last_key=key
            runs[-1][1].append(p)
        if not runs:runs=[(None,[])]
        for n,(key,_) in enumerate(runs):
            if key:
                x,y,w,h=[int(v or 0)/20 for v in key];h=min(height-y-bottom,max(h,24))
                frames.append(Frame(x,height-y-h,w,h,id=f'f{index}_{n}',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0))
            else:frames.append(Frame(left,bottom,width-left-right,height-top-bottom,id=f'f{index}_{n}',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0))
        pdf.addPageTemplates(PageTemplate(id='p'+str(index),frames=frames,onPage=draw_page))
        if index:story.extend([NextPageTemplate('p'+str(index)),PageBreak()])
        for n,(key,ps) in enumerate(runs):
            if n:story.append(FrameBreak())
            for p in ps:
                font=p.style.font;normal=doc.styles['Normal'].font
                name=font.name or normal.name or 'Times New Roman';family='WbsTimes' if name=='Times New Roman' else 'WbsArial'
                if family not in pdfmetrics.getRegisteredFontNames():family='Times-Roman' if name=='Times New Roman' else 'Helvetica'
                bold=bool(font.bold);italic=bool(font.italic)
                chosen=family+('-BoldItalic' if bold and italic else '-Bold' if bold else '-Italic' if italic else '')
                if chosen not in pdfmetrics.getRegisteredFontNames() and chosen not in pdfmetrics.standardFonts:chosen=family
                size=font.size.pt if font.size else (normal.size.pt if normal.size else 12)
                pf=p.paragraph_format;sf=p.style.paragraph_format
                align=pf.alignment if pf.alignment is not None else sf.alignment
                style=ParagraphStyle('body',fontName=chosen,fontSize=size,leading=size*1.25,alignment={1:1,2:2}.get(int(align or 0),0),spaceAfter=4,leftIndent=(pf.left_indent or sf.left_indent).pt if (pf.left_indent or sf.left_indent) else 0,rightIndent=(pf.right_indent or sf.right_indent).pt if (pf.right_indent or sf.right_indent) else 0,firstLineIndent=(pf.first_line_indent or sf.first_line_indent).pt if (pf.first_line_indent or sf.first_line_indent) else 0)
                text=''.join(('<b>' if r.bold else '')+('<i>' if r.italic else '')+escape(r.text).replace('\n','<br/>')+('</i>' if r.italic else '')+('</b>' if r.bold else '') for r in p.runs)
                paragraph=Paragraph(text or '&#160;',style)
                images=[]
                for drawing in p._p.xpath('.//w:drawing'):
                    ids=drawing.xpath('.//a:blip/@r:embed');ext=drawing.xpath('.//wp:extent')
                    if not ids or not ext:continue
                    image=Image(BytesIO(doc.part.related_parts[ids[0]].blob),width=int(ext[0].get('cx'))/12700,height=int(ext[0].get('cy'))/12700)
                    side=drawing.xpath('.//wp:positionH/wp:align/text()')
                    prefix=''
                    for run in p.runs:
                        if run._r is drawing.getparent():break
                        prefix+=run.text
                    images.append((image,side[0] if side else 'center',prefix))
                if images:
                    floating=[r for r in images if r[1] in ('left','right')]
                    centered=[r for r in images if r[1]=='center']
                    if floating:story.append(FloatingImages(paragraph,floating))
                    else:
                        for image,side,prefix in centered:image.hAlign='CENTER';story.append(image)
                        if p.text:story.append(paragraph)
                else:story.append(paragraph)
    if not story:story=[Spacer(1,1)]
    pdf.build(story)
    return out.getvalue()


def download(st,docx_bytes,stem,key):
    if available():
        try:payload=export_pdf(docx_bytes)
        except Exception:st.warning('PDF rendering failed. Your writing and images are preserved; use DOCX while this layout is checked.')
        else:st.download_button('Download Illustrated PDF',data=payload,file_name=stem+'.pdf',mime='application/pdf',key=key+'_pdf')
    else:st.caption('PDF export requires the reportlab dependency. DOCX contains the embedded images and wrapping rules.')

if __name__=='__main__':sys.stdout.buffer.write(render(sys.stdin.buffer.read()))
