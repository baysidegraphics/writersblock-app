"""Fail-closed integrity results; no writing generation or manuscript mutation."""
from core.text import get_text_signature


def status(report):
    if not isinstance(report,str) or not report.strip():raise ValueError('Integrity review did not return a report.')
    first=report.strip().splitlines()[0].strip().upper()
    if first=='OVERALL STATUS: PASS':return 'PASS'
    if first=='OVERALL STATUS: WARNINGS':return 'WARNINGS'
    raise ValueError('Integrity validation failed or was inconclusive. Run a successful review before approval.')


def ready(state,required=True):
    if state.get('project_integrity_status')=='FAILED':return False
    if not required:return True
    try:status(state.get('project_integrity_report'))
    except ValueError:return False
    return state.get('project_integrity_source_signature')==get_text_signature(state.get('current_draft_output') or '')


def run(context):
    state=context['st'].session_state
    from core.saved_scene_state import saved_snapshot_for_session
    try:
        saved=saved_snapshot_for_session(state)
        text=str(state.get('current_draft_output') or '')
        if not text.strip() or text!=saved.get('current_draft_output'):raise ValueError('Save the current manuscript before running Integrity Review.')
        report=context['run_project_integrity_final_review'](text)
        result=status(report);signature=get_text_signature(text)
        if context['persist_project_integrity_in_current_version'](report,signature,result) is not True:
            raise ValueError('Integrity report could not be saved to the current revision. Approval remains blocked.')
        state['project_integrity_report']=report;state['project_integrity_source_signature']=signature
        state['project_integrity_status']=result
        return report
    except Exception:
        state['project_integrity_status']='FAILED'
        state['project_integrity_source_signature']=''
        raise


def panel(context):
    st=context['st'];state=st.session_state
    if st.button('Run Project Integrity Report',key='run_project_integrity_final_review'):
        try:run(context)
        except Exception:st.error('Integrity review failed or could not be saved. Approval remains blocked; retry when the review service is available.')
        else:st.rerun()
    if ready(state):st.markdown(state['project_integrity_report'])
    else:st.warning('A successful, saved Integrity Report for this manuscript is required before approval.')
    return ready(state)


def numbered_context(state):
    from core.manuscript_structure import profile,integrity_context,blocks,values
    spec=profile(state['active_format_id'])
    if spec['structured_editor']:return integrity_context(state)[0]
    current=values(state);writing=blocks(state);result=[]
    for n,text in sorted(writing.items()):
        label=spec['unit']+' '+str(n)
        if state['active_format_id']=='biography_memoir':
            rows=current.get('chapters') or []
            row=next((r for r in rows if str(r.get('chapter_number'))==str(n)),{})
            if row.get('life_period'):label='Life period '+str(row['life_period'])+' / '+label
        elif state['active_format_id']=='childrens_interactive_educational':
            label='Subject area '+str(current.get('subject_area') or 'Unspecified')+' / '+label
        result.append('['+label+']\n'+text+'\n[END '+label+']')
    return '\n\n'.join(result)
