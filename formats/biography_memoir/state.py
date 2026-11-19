"""State belongs only to biography_memoir; nested domain data stays in the saved format values."""
from copy import deepcopy
FORMAT_ID = 'biography_memoir'

def get_data(snapshot):
    if snapshot.get('active_format_id') != FORMAT_ID:
        raise ValueError('Cross-format state access refused')
    values = snapshot.get('format_template_values') or {}
    if not isinstance(values,dict) or not isinstance(values.get(FORMAT_ID,{}) or {},dict):
        raise ValueError('Format state must be a record')
    return deepcopy(values.get(FORMAT_ID) or {})

def set_data(snapshot, values):
    get_data(snapshot)
    result = deepcopy(snapshot)
    result['format_template_values'] = {**(result.get('format_template_values') or {}), FORMAT_ID: deepcopy(values)}
    return result

def is_approved(state):
    from core.format_services import approved_saved
    return approved_saved(state, FORMAT_ID)
