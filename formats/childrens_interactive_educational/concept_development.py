from core.format_services import edit_fields,edit_table,save_checkpoint,advance,coach,select_format
from . import FORMAT_ID,TEMPLATE
from .state import get_data
from .validation import AGE_GUIDANCE

from core.extended_concept import render_concept

def render_domain(context):
    st=context['st']
    from core.children_publication import controls
    controls(context,'concept')
    edit_fields(context,FORMAT_ID,[field for field in TEMPLATE['concept_fields'] if field['key']!='project_title'],columns=2)
    values=get_data(st.session_state);guidance=AGE_GUIDANCE.get(values.get('age_band'),{})
    st.info(guidance.get('guidance','Choose an age band.'))
    with st.expander('Vocabulary and Teaching References',expanded=False):
        edit_table(context,FORMAT_ID,'vocabulary','Age-Specific Vocabulary',('word','meaning','unit_number'))
        edit_table(context,FORMAT_ID,'fact_sources','Factual Sources and Teaching References',('source_id','title','locator','claims_supported'))
        st.caption('Printable activities are implemented. Digital interactive output is a separate design-only interface, with no working clickable controls.')


def render(context):
    render_concept(context,FORMAT_ID,TEMPLATE,render_domain)
