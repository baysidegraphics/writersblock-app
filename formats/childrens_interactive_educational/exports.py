"""Print-first educational story, worksheets and separate parent/teacher answer guide."""
from core.print_export import document,bytes_for,row_text
from core.domain_validation import number
from .state import get_data
from .scenes import completed_blocks
from .validation import validate,AGE_GUIDANCE


def _validated(snapshot):
    errors=validate(snapshot,for_export=True)
    if errors:raise ValueError('; '.join(errors))
    return get_data(snapshot)


def _target(value):
    return 'Finish this learning path.' if str(value).upper()=='END' else 'Go to Unit '+str(value)+'.'


def build_docx(snapshot,resolve_asset=None):
    values=_validated(snapshot);age=values['age_band'];guidance=AGE_GUIDANCE[age]
    doc=document(snapshot.get('project_title'),guidance['font_size'])
    from core.children_publication import apply_docx,add_placeholder
    apply_docx(doc,snapshot)
    doc.add_paragraph('Printable Activity Book — Ages '+age)
    doc.add_paragraph(values['subject_area']);doc.add_heading('Learning Goals',1);doc.add_paragraph(values['learning_goals'])
    doc.add_paragraph(guidance['guidance'])
    doc.add_paragraph('Printed choices are read and followed on paper. This book contains no clickable controls or digital learner tracking.')
    blocks=completed_blocks(snapshot.get('scene_blocks') or {})
    for unit in sorted(values['units'],key=lambda row:int(row['unit_number'])):
        n=int(unit['unit_number']);doc.add_page_break();doc.add_heading(f"Unit {n}: {unit['title']}",1)
        # Placement is applied to the complete teaching page below.
        doc.add_paragraph('We are learning: '+str(unit.get('learning_goal') or ''))
        doc.add_paragraph(blocks[n])
        words=[row for row in values.get('vocabulary') or [] if not row.get('unit_number') or number(row.get('unit_number'))==n]
        if words:
            doc.add_heading('Words to Explore',2)
            for row in words:doc.add_paragraph(str(row['word'])+': '+str(row['meaning']))
        for choice in values.get('choices') or []:
            if number(choice.get('unit_number'))!=n:continue
            doc.add_heading('Your Story Choice',2);doc.add_paragraph(choice['prompt'])
            doc.add_paragraph('[ ] '+choice['option_a']+' — '+_target(choice['target_a']))
            doc.add_paragraph('[ ] '+choice['option_b']+' — '+_target(choice['target_b']))
        for question in values.get('questions') or []:
            if number(question.get('unit_number'))==n:
                doc.add_heading('Think, Talk or Draw',2);doc.add_paragraph(question['prompt'])
                doc.add_paragraph('________________________________________________\n\n________________________________________________')
        for activity in values.get('activities') or []:
            if number(activity.get('unit_number'))!=n:continue
            doc.add_page_break();doc.add_heading('Printable Exercise: '+activity['title'],1)
            doc.add_paragraph('Name: ____________________    Date: ____________________')
            doc.add_paragraph('Materials: '+str(activity.get('materials') or 'None specified'))
            doc.add_paragraph(activity['instructions'])
            doc.add_paragraph('Draw, mark, trace, write or tell an adult your response as appropriate.\n\n________________________________________________\n\n________________________________________________\n\n________________________________________________\n\n________________________________________________')
    doc.add_page_break();doc.add_heading('Parent / Teacher Instructions and Answer Guide',1)
    doc.add_paragraph(values['adult_role']);doc.add_paragraph(guidance['guidance'])
    doc.add_paragraph('Access adaptations: '+str(values.get('accessibility_notes') or 'Offer spoken, drawn or adult-scribed responses as needed.'))
    for unit in values['units']:
        doc.add_heading('Unit '+str(unit['unit_number'])+' — Adult Guidance',2);doc.add_paragraph(str(unit.get('adult_guidance') or ''))
    for question in values.get('questions') or []:
        doc.add_paragraph('Question '+str(question['question_id'])+': '+str(question.get('answer_or_guidance') or ''))
    for activity in values.get('activities') or []:
        doc.add_heading(activity['title'],2)
        doc.add_paragraph(row_text(activity,(('adult_steps','Adult instructions'),('answer_or_observation','Answer / observations'),('safety_notes','Material and safety review'))))
    doc.add_heading('Factual Sources',2)
    for source in values.get('fact_sources') or []:doc.add_paragraph(row_text(source,(('source_id','Source'),('title','Title'),('locator','Locator'),('claims_supported','Supported content'))))
    from core.children_arrangements import educational_docx
    educational_docx(doc,snapshot,resolve_asset)
    from core.publication_layout import decorate_document
    decorate_document(doc,snapshot)
    from core.inline_images import apply_to_doc
    apply_to_doc(doc,snapshot)
    return bytes_for(doc)


def build_text(snapshot):
    values=_validated(snapshot);blocks=completed_blocks(snapshot.get('scene_blocks') or {})
    parts=[str(snapshot.get('project_title') or ''),'Printable Activity Book — Ages '+values['age_band'],values['subject_area'],values['learning_goals'],AGE_GUIDANCE[values['age_band']]['guidance']]
    for unit in sorted(values['units'],key=lambda row:int(row['unit_number'])):
        n=int(unit['unit_number']);parts.extend([f"Unit {n}: {unit['title']}",blocks[n]])
        for choice in values.get('choices') or []:
            if number(choice.get('unit_number'))==n:parts.extend([choice['prompt'],choice['option_a']+' — '+_target(choice['target_a']),choice['option_b']+' — '+_target(choice['target_b'])])
        for question in values.get('questions') or []:
            if number(question.get('unit_number'))==n:parts.extend(['Question: '+question['prompt'],'Response: ______________________________'])
        for activity in values.get('activities') or []:
            if number(activity.get('unit_number'))==n:parts.extend(['Printable Exercise: '+activity['title'],activity['instructions'],'Response: ______________________________'])
    parts.extend(['Vocabulary']+[str(row['word'])+': '+str(row['meaning']) for row in values.get('vocabulary') or []])
    parts.extend(['Parent / Teacher Instructions and Answer Guide',values['adult_role'],'Access adaptations: '+str(values.get('accessibility_notes') or '')])
    for question in values.get('questions') or []:parts.append('Question '+str(question['question_id'])+': '+str(question.get('answer_or_guidance') or ''))
    for activity in values.get('activities') or []:parts.append(row_text(activity,(('title','Activity'),('materials','Materials'),('adult_steps','Adult instructions'),('answer_or_observation','Answer / observations'),('safety_notes','Material and safety review'))))
    for source in values.get('fact_sources') or []:parts.append(row_text(source,(('source_id','Source'),('title','Title'),('locator','Locator'))))
    return '\n\n'.join(parts)
