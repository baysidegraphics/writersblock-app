"""Biography-specific structural and evidence checks; never fabricates verification."""
from core.domain_validation import records,identifiers,check_refs,refs,number,check_date,require_text
from .state import get_data
from .scenes import completed_blocks,manuscript

STATUSES={'verified','recollection','disputed','needs verification'}


def validate(snapshot,for_export=False):
    errors=[]
    try:values=get_data(snapshot)
    except ValueError as exc:return [str(exc)]
    if 'stage_unlocked' in values and number(values['stage_unlocked']) not in range(1,6):errors.append('Saved workflow milestone must be between 1 and 5.')
    require_text(values.get('subject_name'),'Subject / Narrator',errors)
    if values.get('life_writing_type','Biography') not in {'Biography','Autobiography','Memoir'}:errors.append('Choose Biography, Autobiography or Memoir.')
    if values.get('narrative_perspective','First Person') not in {'First Person','Third Person'}:errors.append('Choose a first-person or third-person narrative perspective.')
    sources=records(values,'sources',errors);source_ids=identifiers(sources,'source_id',errors)
    for row in sources:
        require_text(row.get('title'),'Source title',errors)
        require_text(row.get('locator'),'Source locator (page, archive reference or URL)',errors)
    timeline=records(values,'timeline',errors);event_ids=identifiers(timeline,'event_id',errors)
    for row in timeline:
        require_text(row.get('event'),'Life event',errors);check_date(row.get('date'),'Life event date',errors)
        check_refs(row.get('source_ids'),source_ids,'Life event sources',errors)
        status=str(row.get('fact_status') or 'needs verification')
        if status not in STATUSES:errors.append('Life event fact status must be verified, recollection, disputed or needs verification.')
        if status=='verified' and not refs(row.get('source_ids')):errors.append('A verified life event needs a recorded source.')
        if for_export and status=='needs verification':errors.append('Resolve or explicitly label unverified life events before final export.')
        if status in {'recollection','disputed'} and not str(row.get('notes') or '').strip():errors.append('Recollections and disputed accounts need explanatory notes.')
        if status=='disputed' and not refs(row.get('source_ids')):errors.append('A disputed account needs sources for the differing accounts.')
    interviews=records(values,'interviews',errors);identifiers(interviews,'interview_id',errors)
    for row in interviews:
        require_text(row.get('interviewee'),'Interviewee',errors);check_date(row.get('interview_date'),'Interview date',errors)
        check_refs(row.get('source_id'),source_ids,'Interview source',errors)
        if str(row.get('quoted_excerpt') or '').strip() and for_export:
            if row.get('consent')!='Granted':errors.append('Quoted interviews need recorded granted permission for final export.')
            if not refs(row.get('source_id')):errors.append('Quoted interviews need a source or transcript reference.')
    claims=records(values,'fact_checks',errors);identifiers(claims,'claim_id',errors)
    for row in claims:
        require_text(row.get('claim'),'Fact-check claim',errors)
        check_refs(row.get('source_ids'),source_ids,'Fact-check sources',errors)
        status=str(row.get('status') or 'needs verification')
        if status not in STATUSES:errors.append('Choose a recognized fact-check status.')
        if status=='verified' and not refs(row.get('source_ids')):errors.append('Verified claims need source references.')
        if for_export and status=='needs verification':errors.append('Resolve outstanding fact-check claims before final export.')
        if status in {'recollection','disputed'} and not str(row.get('notes') or '').strip():errors.append('Label the limits of recollected or disputed claims in notes.')
        if status=='disputed' and not refs(row.get('source_ids')):errors.append('Disputed claims need source references.')
    chapters=records(values,'chapters',errors);seen=set()
    for row in chapters:
        n=number(row.get('chapter_number'))
        if n is None or n in seen:errors.append('Chapter numbers must be unique positive integers.')
        if n:seen.add(n)
        require_text(row.get('title'),'Chapter title',errors)
        check_refs(row.get('event_ids'),event_ids,'Chapter life events',errors)
    if for_export:
        if not timeline:errors.append('Add the factual life-event timeline before final export.')
        if not chapters:errors.append('Add the chapter organization before final export.')
        blocks=completed_blocks(snapshot.get('scene_blocks') or {})
        if set(blocks)!=seen:errors.append('Saved chapter text must match every planned chapter without omitting or inventing chapters.')
        if not blocks or snapshot.get('current_draft_output')!=manuscript(blocks):errors.append('The saved manuscript and chapter text must match exactly.')
    return errors
