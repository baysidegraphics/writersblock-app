"""Format-scoped in-memory view. No mutation of the saved WBS snapshot."""
from copy import deepcopy

FORMAT_ID = "podcast_script"
def get_data(snapshot):
    if snapshot.get("active_format_id") != FORMAT_ID:
        raise ValueError("Format mismatch: refusing cross-format access")
    values = snapshot.get("format_template_values") or {}
    return deepcopy(values.get(FORMAT_ID) or {})
