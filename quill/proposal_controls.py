"""Author-controlled Quill draft proposals. Never write the saved manuscript."""
from copy import deepcopy

def valid(state,proposal):
    from .modular_context import scope,fingerprint
    return bool(proposal and tuple(proposal.get('scope') or ())==scope(state) and proposal.get('source_hash')==fingerprint(state))

def remember_response(state,text):
    from .modular_context import scope,fingerprint
    state['_wbs_quill_response_binding']={'scope':scope(state),'source_hash':fingerprint(state),'text':str(text)}

def copy_to_draft(state,text):
    binding=state.get('_wbs_quill_response_binding')
    if not valid(state,binding) or str(binding.get('text',''))!=str(text):raise ValueError('This response belongs to another or changed saved revision. Ask Quill again before copying it.')
    from uuid import uuid4
    proposal=deepcopy(binding);proposal['text']=str(text);proposal['editor_id']=uuid4().hex
    state['_wbs_quill_draft_proposal']=proposal
    return proposal

def render(st,state):
    text=str(state.get('_wbs_quill_last_response') or '')
    from .modular_context import scope
    import hashlib
    key=hashlib.sha256(repr(scope(state)).encode()).hexdigest()[:12]
    with st.expander('Full Quill Response',expanded=False):
        st.text_area('Complete Quill response',value=text,height=280,disabled=True,key='_wbs_quill_full_'+key+'_'+hashlib.sha256(text.encode()).hexdigest()[:12])
        st.caption('Your Frontline Editor-in-Chief. The complete returned response is shown here; saved manuscript content is unchanged.')
    binding=state.get('_wbs_quill_response_binding');can_copy=valid(state,binding) and str(binding.get('text',''))==text
    if st.button('Copy to Draft',key='_wbs_quill_copy_'+key,disabled=not can_copy):
        copy_to_draft(state,text);st.rerun()
    if not text:
        st.button('Revise',key='_wbs_quill_revise_'+key,disabled=True)
        st.caption('Ask Quill first; these controls will use the response for this project and revision.')
        return
    if not can_copy:st.caption('Ask a fresh question for this saved revision before copying or revising an old response.')
    proposal=state.get('_wbs_quill_draft_proposal')
    if proposal:
        if not valid(state,proposal):st.warning('This proposal is stale. Your saved manuscript is unchanged.');return
        draft=st.text_area('Quill Draft — author-editable proposal',value=proposal['text'],height=240,key='_wbs_quill_draft_'+key+'_'+proposal.get('editor_id','legacy'))
        proposal['text']=draft;state['_wbs_quill_draft_proposal']=proposal
        st.caption('Copy to Draft creates this working proposal only. To apply it, copy the text into the intended existing manuscript editor, review it and use that stage’s normal save/approval controls. Quill never overwrites a saved unit. This also preserves the protected Short Story editor.')
    instructions=st.text_area('Revision instructions',key='_wbs_quill_revision_instructions_'+key,height=100)
    if st.button('Revise',key='_wbs_quill_revise_'+key,disabled=not can_copy or not str(instructions).strip()):
        from .provider import request,ProviderFailure
        try:
            revised=request(state,'Revise ONLY this Quill proposal according to the author instructions. Return the full revised proposal, not a claim that it was applied.\nPROPOSAL:\n'+(proposal['text'] if proposal else text)+'\nAUTHOR INSTRUCTIONS:\n'+instructions)
        except ProviderFailure as exc:st.warning(str(exc))
        else:
            if not valid(state,binding):
                st.warning("The saved project changed; the returned proposal was discarded.");return
            remember_response(state,revised);copy_to_draft(state,revised)
            history=list(state.get('_wbs_quill_chat_history') or []);history.append({'role':'assistant','content':revised,'source':'revision_proposal'})
            state['_wbs_quill_chat_history']=history;state['_wbs_quill_last_response']=revised;st.rerun()
