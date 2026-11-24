"""Educational book validation, independent of fiction and picture-book workflows."""
from core.domain_validation import records,identifiers,check_refs,number,require_text
from .state import get_data
from .scenes import completed_blocks,manuscript

AGE_GUIDANCE={
 '3–4':{'font_size':16,'guidance':'Adult read-aloud; familiar concrete words, short oral prompts, pointing, matching and one-step actions. Accept spoken or drawn answers.'},
 '5–6':{'font_size':14,'guidance':'Short concrete sentences; introduce a few explained words. Use one- or two-step tasks with adult support as needed.'},
 '7–9':{'font_size':12,'guidance':'Short paragraphs; explain new terms. Invite predictions, comparisons, reasons and short written or drawn responses.'}}
SUBJECT_AREAS=('Life Skills & Social Interaction','Science & Discovery')


def validate(snapshot,for_export=False):
    errors=[]
    try:values=get_data(snapshot)
    except ValueError as exc:return [str(exc)]
    if 'stage_unlocked' in values and number(values['stage_unlocked']) not in range(1,6):errors.append('Saved workflow milestone must be between 1 and 5.')
    if values.get('age_band') not in AGE_GUIDANCE:errors.append('Choose an age band within ages 3–9.')
    if values.get('subject_area') not in SUBJECT_AREAS:errors.append('Choose Life Skills & Social Interaction or Science & Discovery.')
    if values.get('output_mode','Printable Activity Book')!='Printable Activity Book':errors.append('Only printable activity book output is implemented.')
    require_text(values.get('learning_goals'),'Learning goals',errors)
    units=records(values,'units',errors);unit_numbers=set()
    for row in units:
        n=number(row.get('unit_number'))
        if n is None or n in unit_numbers:errors.append('Learning unit numbers must be unique positive integers.')
        if n:unit_numbers.add(n)
        require_text(row.get('title'),'Learning unit title',errors)
        if for_export:require_text(row.get('learning_goal'),'Unit learning goal',errors)
    def unit_ref(row,label):
        if number(row.get('unit_number')) not in unit_numbers:errors.append(label+' refers to an unknown learning unit.')
    vocabulary=records(values,'vocabulary',errors)
    for row in vocabulary:
        require_text(row.get('word'),'Vocabulary word',errors);require_text(row.get('meaning'),'Child-friendly meaning',errors)
        if row.get('unit_number') not in (None,''):unit_ref(row,'Vocabulary entry')
    choices=records(values,'choices',errors);identifiers(choices,'choice_id',errors)
    for row in choices:
        unit_ref(row,'Story choice')
        for name in ('prompt','option_a','option_b'):require_text(row.get(name),'Story choice '+name,errors)
        for name in ('target_a','target_b'):
            if str(row.get(name) or '').upper()!='END' and number(row.get(name)) not in unit_numbers:
                errors.append('Printed story-choice targets must be known unit numbers or END.')
    questions=records(values,'questions',errors);identifiers(questions,'question_id',errors)
    for row in questions:
        unit_ref(row,'Question');require_text(row.get('prompt'),'Question prompt',errors)
        if for_export:require_text(row.get('answer_or_guidance'),'Answer or discussion guidance',errors)
    activities=records(values,'activities',errors);identifiers(activities,'activity_id',errors)
    for row in activities:
        unit_ref(row,'Activity')
        for name in ('title','instructions'):require_text(row.get(name),'Activity '+name,errors)
        if for_export:
            for name in ('adult_steps','answer_or_observation','safety_notes'):require_text(row.get(name),'Activity '+name.replace('_',' '),errors)
    sources=records(values,'fact_sources',errors);identifiers(sources,'source_id',errors)
    for row in sources:
        require_text(row.get('title'),'Educational source title',errors);require_text(row.get('locator'),'Educational source locator',errors)
    if for_export:
        if not units:errors.append('Plan at least one learning unit.')
        for label,rows in [('Story choices',choices),('Questions',questions),('Printable activities',activities),('Age-specific vocabulary',vocabulary)]:
            if not rows:errors.append(label+' are required in the final educational book.')
        for n in unit_numbers:
            if not any(number(row.get('unit_number'))==n for row in activities):errors.append(f'Unit {n} needs a printable activity.')
            if not any(number(row.get('unit_number'))==n for row in questions):errors.append(f'Unit {n} needs a question.')
        require_text(values.get('adult_role'),'Parent / teacher instructions',errors)
        if values.get('adult_review_complete') is not True:errors.append('Complete the adult accessibility, vocabulary and material-safety review.')
        if values.get('subject_area')=='Science & Discovery':
            if not sources:errors.append('Science & Discovery requires recorded factual sources.')
            if values.get('science_accuracy_review') is not True:errors.append('Complete the source-based science accuracy review.')
        blocks=completed_blocks(snapshot.get('scene_blocks') or {})
        if set(blocks)!=unit_numbers:errors.append('Saved story text must match every planned learning unit.')
        if not blocks or snapshot.get('current_draft_output')!=manuscript(blocks):errors.append('The saved story manuscript and unit text must match exactly.')
    return errors
