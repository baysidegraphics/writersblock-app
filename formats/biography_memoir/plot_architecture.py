from core.format_services import edit_table,data,save_checkpoint,advance,coach
from . import FORMAT_ID

def render(context):
    st=context['st'];st.header('2. Chapter Organization — Life Story Architecture')
    edit_table(context,FORMAT_ID,'chapters','Author Chapter Plan',('chapter_number','title','life_period','event_ids','focus'))
    st.caption('Organize the supplied life events chronologically or thematically. Approving this plan does not generate or replace manuscript text.')
    if st.button('Approve And Save Chapter Organization',key='bio_plan_save'):
        values=data(st.session_state,FORMAT_ID);chapters=values.get('chapters') or []
        if not chapters:st.warning('Add at least one chapter before approving the plan.')
        else:
            previous={name:st.session_state.get(name) for name in ('chosen_option','chosen_option_text','plot_outline')}
            plan='\n'.join(str(row.get('chapter_number'))+'. '+str(row.get('title'))+' — '+str(row.get('focus') or '') for row in chapters)
            st.session_state.update(chosen_option='Author-approved life-writing plan',chosen_option_text=plan,plot_outline=plan)
            if save_checkpoint(context,FORMAT_ID,3):advance(context,'Plot Architect')
            else:st.session_state.update(previous)
    coach(context)
