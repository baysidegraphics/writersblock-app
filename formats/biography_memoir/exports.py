"""Printable life-writing exports preserve supplied prose and provenance verbatim."""
from core.print_export import document,bytes_for,row_text
from .state import get_data
from .scenes import completed_blocks
from .validation import validate

FACTUAL_DISCLAIMER='Recorded verification statuses are author-supplied. This export does not independently certify facts or interview permissions.'

APPENDICES=(
 ('Factual Timeline and Historical Context','timeline',(('event_id','Event ID'),('date','Date'),('event','Life event'),('historical_context','Historical context'),('source_ids','Sources'),('fact_status','Recorded fact status'),('notes','Notes / uncertainty'))),
 ('Sources','sources',(('source_id','Source ID'),('title','Title'),('creator','Creator'),('publication_date','Publication date'),('locator','Locator'),('kind','Source type'),('reliability_notes','Reliability notes'))),
 ('Interview Records','interviews',(('interview_id','Interview ID'),('interviewee','Interviewee'),('interview_date','Date'),('questions','Questions'),('notes','Notes'),('quoted_excerpt','Exact supplied quotation'),('consent','Recorded permission'),('source_id','Source / transcript'))),
 ('Fact-Checking Record','fact_checks',(('claim_id','Claim ID'),('claim','Claim'),('source_ids','Sources'),('status','Recorded status'),('notes','Notes'))))


def _validated(snapshot):
    errors=validate(snapshot,for_export=True)
    if errors:raise ValueError('; '.join(errors))
    return get_data(snapshot)


def build_docx(snapshot,resolve_asset=None):
    values=_validated(snapshot);doc=document(snapshot.get('project_title'))
    doc.add_paragraph(str(values.get('life_writing_type') or 'Biography')+' — '+str(values.get('subject_name') or ''))
    doc.add_paragraph('Life scope: '+str(values.get('life_scope') or ''))
    doc.add_paragraph('Source and recollection policy: '+str(values.get('source_policy') or ''))
    blocks=completed_blocks(snapshot.get('scene_blocks') or {})
    for chapter in sorted(values['chapters'],key=lambda row:int(row['chapter_number'])):
        n=int(chapter['chapter_number'])
        if n!=min(int(c['chapter_number']) for c in values['chapters']):doc.add_page_break()
        doc.add_heading(f"Chapter {n}: {chapter['title']}",1)
        from core.image_placement import add_docx
        add_docx(doc,snapshot,'chapter-'+str(n),resolve_asset)
        doc.add_paragraph(blocks[n])
        if chapter.get('life_period'):doc.add_paragraph('Life period: '+str(chapter['life_period']))
        doc.add_paragraph('Life-event references: '+str(chapter.get('event_ids') or ''))
    for label,key,fields in APPENDICES:
        doc.add_page_break();doc.add_heading(label,1)
        for row in values.get(key) or []:doc.add_paragraph(row_text(row,fields))
        if not values.get(key):doc.add_paragraph('No records supplied.')
    doc.add_paragraph(FACTUAL_DISCLAIMER)
    from core.publication_layout import decorate_document
    decorate_document(doc,snapshot)
    from core.inline_images import apply_to_doc
    apply_to_doc(doc,snapshot)
    return bytes_for(doc)


def build_text(snapshot):
    values=_validated(snapshot);blocks=completed_blocks(snapshot.get('scene_blocks') or {})
    parts=[str(snapshot.get('project_title') or ''),str(values.get('subject_name') or ''),str(values.get('source_policy') or '')]
    for chapter in sorted(values['chapters'],key=lambda row:int(row['chapter_number'])):
        n=int(chapter['chapter_number']);parts.extend([f"Chapter {n}: {chapter['title']}",blocks[n],'Life period: '+str(chapter.get('life_period') or ''),'Life-event references: '+str(chapter.get('event_ids') or '')])
    for label,key,fields in APPENDICES:
        parts.append(label)
        parts.extend(row_text(row,fields) for row in values.get(key) or [])
    parts.append(FACTUAL_DISCLAIMER)
    return '\n\n'.join(parts)
