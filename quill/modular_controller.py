"""Modular Quill question routing: read-only facts/operations or one provider request."""
import re
from .modular_context import prepare,identity,build,scope,fingerprint
from .proposal_controls import remember_response

def answer(state,question):
    prepare(state);started=(scope(state),fingerprint(state));i=identity(state);q=question.lower();packet=build(state)
    if state.pop('_wbs_quill_force_test_ai',False):
        from .provider import request,ProviderFailure
        try:text=request(state,question)
        except ProviderFailure as exc:return {'text':str(exc),'stage':i['stage'],'source':'provider_error','severity':'warning'}
        remember_response(state,text)
        return {'text':text,'stage':i['stage'],'source':'editorial_proposal','severity':'info'}
    if any(t in q for t in ('who are you','what is quill','what can quill do')):
        text='I’m Quill — Your Frontline Editor-in-Chief. I provide creative/editorial help and exact guidance for operating WritersBlock Studios. I use your current saved project and revision; suggestions never overwrite your manuscript.';source='identity'
    elif any(t in q for t in ('what project','project title','what story is this')):text='You are working in "'+i['title']+'" — '+i['revision']+'.';source='project_context'
    elif any(t in q for t in ('what stage','what step','where am i','current stage','current step')):text='You are at Stage '+str(i['stage_number'])+': '+i['stage']+' — '+i['format']+', '+i['revision']+'.';source='project_context'
    elif re.search(r'what (?:format|work type)|which (?:format|work type)',q):text='Writing format: '+i['format']+'. Work Type: '+str(packet['development'].get('work_type') or 'format default')+'.';source='project_context'
    elif re.search(r'what (?:revision|version)|which (?:revision|version)',q):text='Current saved revision: '+i['revision']+' (revision ID '+(i['revision_id'] or 'unsaved')+').';source='project_context'
    elif re.search(r'(how many|word count|count).{0,20}words|word count',q):
        from sidebar.summary import from_session
        summary=from_session(state);text='The saved Scene Scripting manuscript contains '+str(summary.completed_words)+' words and '+str(summary.scene_count)+' '+packet['unit_label'].lower()+' units. Unsaved edits are not counted.';source='project_context'
    elif re.search(r'what next|what should i do|next step',q):
        from .operations import guides
        key=['concept','plot','edit','integrity','publisher','export'][i['stage_number']-1];text=guides(state)[key];source='operations'
    else:
        from .operations import answer as operation
        text=operation(state,question);source='operations'
        if text is None:
            from .provider import request,ProviderFailure
            try:text=request(state,question);source='editorial_proposal'
            except ProviderFailure as exc:
                state.pop('_wbs_quill_response_binding',None)
                return {'text':str(exc),'stage':i['stage'],'source':'provider_error','severity':'warning'}
    if (scope(state),fingerprint(state))!=started:
        return {"text":"The active saved project changed. Ask Quill again for this revision; your saved writing is unchanged.","stage":i["stage"],"source":"provider_error","severity":"warning"}
    remember_response(state,text)
    return {'text':text,'stage':i['stage'],'source':source,'severity':'info'}
