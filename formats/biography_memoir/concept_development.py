from core.format_services import edit_fields,edit_table,save_checkpoint,advance,coach,select_format
from . import FORMAT_ID,TEMPLATE

from core.extended_concept import render_concept

def render_domain(context):
    st=context['st']
    edit_fields(context,FORMAT_ID,[field for field in TEMPLATE['concept_fields'] if field['key']!='project_title'],columns=2)
    with st.expander('Sources, Timeline and Interviews',expanded=False):
        edit_table(context,FORMAT_ID,'sources','Source Register',('source_id','title','creator','publication_date','locator','kind','reliability_notes'))
        edit_table(context,FORMAT_ID,'timeline','Factual Timeline and Historical Context',('event_id','date','event','historical_context','source_ids','fact_status','notes'))
        edit_table(context,FORMAT_ID,'interviews','Interviews and Recorded Permissions',('interview_id','interviewee','interview_date','questions','notes','quoted_excerpt','consent','source_id'))
        st.caption('Use source IDs separated by commas. Mark facts verified, recollection, disputed or needs verification. Dates may be YYYY, YYYY-MM-DD, unknown or approximate.')


def render(context):
    render_concept(context,FORMAT_ID,TEMPLATE,render_domain)
