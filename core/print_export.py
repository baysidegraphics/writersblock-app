"""Neutral in-memory printable DOCX construction; no app startup or external I/O."""
from io import BytesIO


def document(title,font_size=12):
    from docx import Document
    from docx.shared import Inches,Pt
    doc=Document()
    for section in doc.sections:
        section.page_width=Inches(8.5);section.page_height=Inches(11)
        section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Inches(0.8)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(font_size)
    normal.paragraph_format.space_after=Pt(8)
    doc.add_heading(str(title or 'Untitled Book'),0)
    return doc


def bytes_for(doc):
    stream=BytesIO();doc.save(stream);return stream.getvalue()


def row_text(row,fields):
    return '\n'.join(label+': '+str(row.get(name) or '') for name,label in fields)
