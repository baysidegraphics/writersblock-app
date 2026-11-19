from core.format_services import edit_table,data,put_data,save_checkpoint,show_errors,approve,coach,key
from . import FORMAT_ID
from .validation import validate

def render(context):
    if context['st'].session_state.get('export_view',False):
        from .final_manuscript import render as render_final
        return render_final(context)
    st=context['st'];st.header('4. Life-Writing Editorial Review and Fact-Checking')
    from core.integrity_review import panel
    integrity_ready=panel(context)
    from core.publication_layout import render_preview
    try:render_preview(st,st.session_state)
    except ValueError as exc:st.warning(str(exc))
    edit_table(context,FORMAT_ID,'fact_checks','Claim-by-Claim Fact Checks',('claim_id','claim','source_ids','status','notes'))
    st.caption('Local checks validate references and recorded review status. They do not verify historical facts against outside sources. Review chronology, context, quotation permissions and the distinction between fact and recollection.')
    if st.button('Check Sources And Chapter Completeness',key='bio_validate'):show_errors(context,validate(dict(st.session_state),for_export=True))
    if st.button('Save Fact-Checking Work',key='bio_review_save'):save_checkpoint(context,FORMAT_ID)
    confirmed=st.checkbox('I reviewed the factual record, historical context, manuscript and source notes.',key=key(context,FORMAT_ID,'editorial_confirm'))
    if st.button('Accept And Save Life-Writing Editorial Review',key='bio_accept',disabled=not (confirmed and integrity_ready)):
        if approve(context,FORMAT_ID):
            from core.stage_navigation import after_approval
            after_approval(context,4)
    coach(context)
