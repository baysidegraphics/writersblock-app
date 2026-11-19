"""Format-owned gates for the existing navigation shell."""
from .state import is_approved

def wbs_stage4_final_access_ready(context):
    return is_approved(context['st'].session_state)

def wbs_stage4_final_status(context,*args,**kwargs):
    ready=is_approved(context['st'].session_state)
    return {'manuscript':ready,'integrity':ready,'title':ready}
