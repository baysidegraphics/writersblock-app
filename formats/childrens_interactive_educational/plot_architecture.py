from core.format_services import edit_table,data,save_checkpoint,advance,coach
from . import FORMAT_ID

def render(context):
    st=context['st'];st.header('2. Learning Units and Printed Story Choices')
    edit_table(context,FORMAT_ID,'units','Learning Unit Organization',('unit_number','title','learning_goal','key_words','adult_guidance'))
    edit_table(context,FORMAT_ID,'choices','Printed Choose-Your-Path Prompts',('choice_id','unit_number','prompt','option_a','target_a','option_b','target_b'))
    st.caption('Choice targets are unit numbers or END. Readers follow printed directions; these are not clickable links.')
    if st.button('Approve And Save Learning Unit Plan',key='edu_plan_save'):
        units=data(st.session_state,FORMAT_ID).get('units') or []
        if not units:st.warning('Add at least one learning unit.')
        else:
            previous={name:st.session_state.get(name) for name in ('chosen_option','chosen_option_text','plot_outline')}
            plan='\n'.join(str(row.get('unit_number'))+'. '+str(row.get('title'))+' — '+str(row.get('learning_goal') or '') for row in units)
            st.session_state.update(chosen_option='Author-approved educational unit plan',chosen_option_text=plan,plot_outline=plan)
            if save_checkpoint(context,FORMAT_ID,3):advance(context,'Plot Architect')
            else:st.session_state.update(previous)
    coach(context)
