"""Focused regressions for two new formats, using only synthetic local writing."""
import copy
import hashlib
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from core.registry import get_format, registered_format_ids
from core.format_services import approve, save_checkpoint, save_scene, put_data
from core.saved_scene_state import remember_saved_snapshot, saved_snapshot_for_session
from core.workflow_runtime import run_workflow
from sidebar.summary import from_session
from offline_app import environment, ROOT, Halt
from template_registry import FORMAT_REGISTRY, FORMAT_OPTIONS
BIO = 'biography_memoir'
EDU = 'childrens_interactive_educational'

def valid_environment(fmt, age='5–6', subject='Life Skills & Social Interaction'):
    saved, st, db, context = environment(fmt, scenes=2)
    values = copy.deepcopy(saved['format_template_values'][fmt])
    if fmt == BIO:
        values.update(subject_name='Synthetic Test Narrator', life_writing_type='Memoir', sources=[dict(source_id='S1', title='Supplied Test Journal', creator='Test Narrator', publication_date='2000', locator='Supplied journal, page 3', kind='Primary', reliability_notes='A synthetic test source.')], timeline=[dict(event_id='E1', date='2000-02-29', event='A supplied life event.', historical_context='Context supplied by the author.', source_ids='S1', fact_status='verified', notes='Recorded in the provided journal.'), dict(event_id='E2', date='unknown', event='A remembered later event.', historical_context='', source_ids='', fact_status='recollection', notes='The exact date is not known.')], interviews=[dict(interview_id='I1', interviewee='Test Narrator', interview_date='2001', questions='What do you remember?', notes='Author-provided notes.', quoted_excerpt='These are the exact supplied words.', consent='Granted', source_id='S1')], chapters=[dict(chapter_number='1', title='Early Years', life_period='2000', event_ids='E1', focus='First event'), dict(chapter_number='2', title='Later Recollections', life_period='Unknown', event_ids='E2', focus='Second event')], fact_checks=[dict(claim_id='F1', claim='The supplied event is recorded in the journal.', source_ids='S1', status='verified', notes='Checked by the test author.')])
    else:
        values.update(age_band=age, subject_area=subject, learning_goals='Practice a respectful choice and explain an observation.', adult_role='Read aloud, invite spoken or drawn responses, and check all materials.', output_mode='Printable Activity Book', units=[dict(unit_number='1', title='First Learning Unit', learning_goal='Notice and explain.', key_words='notice', adult_guidance='Read aloud and ask an open question.'), dict(unit_number='2', title='Second Learning Unit', learning_goal='Try a kind choice.', key_words='share', adult_guidance='Accept more than one thoughtful answer.')], vocabulary=[dict(word='notice', meaning='Look and pay attention.', unit_number='1'), dict(word='share', meaning='Let another person have a turn too.', unit_number='2')], choices=[dict(choice_id='C1', unit_number='1', prompt='What would you try?', option_a='Ask a friend.', target_a='2', option_b='Ask an adult.', target_b='2'), dict(choice_id='C2', unit_number='2', prompt='How will you finish?', option_a='Tell what you noticed.', target_a='END', option_b='Draw your idea.', target_b='END')], questions=[dict(question_id='Q1', unit_number='1', prompt='What did you notice?', answer_or_guidance='Accept an observation connected to the story.'), dict(question_id='Q2', unit_number='2', prompt='What could happen next?', answer_or_guidance='Invite a reason for the answer.')], activities=[dict(activity_id='A1', unit_number='1', title='Draw and Notice', instructions='Draw one thing you noticed in the story.', materials='Paper and a large crayon.', adult_steps='Read the prompt; offer adult scribing if requested.', answer_or_observation='Accept a drawing and an oral explanation.', safety_notes='Adult checks materials and supervises use.', exercise_type='Draw'), dict(activity_id='A2', unit_number='2', title='Mark a Kind Choice', instructions='Tell an adult about one respectful choice.', materials='This printed worksheet.', adult_steps='Offer two concrete story examples and invite a response.', answer_or_observation='Accept a thoughtful safe choice.', safety_notes='No extra equipment is needed; adult reviews the context.', exercise_type='Discuss')], fact_sources=[dict(source_id='S1', title='Supplied Science Teaching Notes', locator='Provided notes, section 1', claims_supported='Author-supplied explanations.')] if subject == 'Science & Discovery' else [], adult_review_complete=True, science_accuracy_review=subject == 'Science & Discovery')
    saved['format_template_values'] = {fmt: values}
    saved['scene_blocks'] = {'1': 'Author chapter one.\n\nEvery supplied word stays intact.', '2': 'Author chapter two — exact punctuation, spacing and wording.'}
    saved['current_draft_output'] = '\n\n'.join(saved['scene_blocks'].values())
    saved['project_title'] = 'Synthetic New Format Test'
    st.session_state.update(copy.deepcopy(saved))
    db.rows['writersblock_projects'][0]['project_title'] = saved['project_title']
    db.rows['writersblock_project_drafts'][0]['draft_content'] = json.dumps(saved, ensure_ascii=False)
    db.rows['writersblock_manuscript_versions'][0]['manuscript_content'] = saved['current_draft_output']
    remember_saved_snapshot(st.session_state, saved, 'own', 'revision-7', 'alice')
    return (saved, st, db, context)
