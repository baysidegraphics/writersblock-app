"""Persist authorized navigation as metadata on the existing owned revision.

No new database interface, record, V-number or approval is created. The caller
must have passed the existing stage gate. Existing atomic checkpoint saves
protect the complete unchanged writing payload against concurrent writers.
"""
import json
from core.save_conflicts import expected_checkpoint,verify_checkpoint

KEY='wbs_navigation_checkpoint'
LEVELS={'Intake':1,'Sandbox':2,'Plot Architect':3,'Drafting':4,
        'Drafting Engine':4,'Isolation Guardrail':4,'Revision Engine':4,
        'Rewrite Engine':4,'Publisher Assessment':4}

def saved_level(snapshot,project_id,revision_id,format_id):
    record=snapshot.get(KEY)
    if not isinstance(record,dict):return 1
    if (record.get('project_id'),record.get('revision_id'),record.get('format_id'))!=(str(project_id),str(revision_id),str(format_id)):
        return 1
    value=record.get('level')
    return value if type(value) is int and 1<=value<=5 else 1

def persist(state,client,owner_id,project_id,revision_id,destination,export_view=False):
    if destination not in LEVELS:raise ValueError('Unknown workflow destination')
    # Only Concept -> Plot Architecture lacked durable evidence. All later
    # stages retain their established saved-content and explicit-approval gates.
    if destination!='Sandbox':return False
    if not all((owner_id,project_id,revision_id)):raise ValueError('Load a saved revision before advancing.')
    fmt=str(state.get('active_format_id') or '')
    expected=expected_checkpoint(state,project_id,revision_id)
    rows=(client.table('writersblock_project_drafts').select('*')
          .eq('id',str(revision_id)).eq('project_id',str(project_id))
          .eq('user_id',str(owner_id)).eq('draft_type','project_session').limit(1).execute()).data or []
    if len(rows)!=1:raise ValueError('The exact owned workflow revision is unavailable.')
    row=rows[0];verify_checkpoint(expected,row['draft_content'])
    snapshot=json.loads(row['draft_content'])
    if (snapshot.get('active_format_id')!=fmt
            or str(snapshot.get('current_project_id') or project_id)!=str(project_id)):
        raise ValueError('Saved workflow identity differs from the open project.')
    current=saved_level(snapshot,project_id,revision_id,fmt)
    if current==1 and (LEVELS.get(str(snapshot.get('project_stage')),1)>1
            or str(snapshot.get('current_draft_output') or '').strip()
            or str(snapshot.get('plot_outline') or '').strip()):
        return False  # Existing legacy evidence already unlocks this earlier room.
    level=max(current,5 if destination=='Isolation Guardrail' and export_view else LEVELS[destination])
    # Reviewing earlier stages neither downgrades the saved checkpoint nor writes.
    if level==current:
        if current>1:state[KEY]=snapshot[KEY]
        return False
    snapshot[KEY]=dict(project_id=str(project_id),revision_id=str(revision_id),format_id=fmt,level=level)
    client.save_project_checkpoint(project_id,revision_id,row['draft_content'],json.dumps(snapshot,ensure_ascii=False))
    state[KEY]=snapshot[KEY]
    state['_wbs_unlocked_saved_stage']=max(int(state.get('_wbs_unlocked_saved_stage') or 1),level)
    return True
