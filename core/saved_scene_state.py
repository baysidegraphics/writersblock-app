"""Read-only cache of the exact persisted project snapshot, never editor buffers.

One active saved revision is retained. No derived word count is persisted: the
format-owned scene parser and core text counter are the single calculation path.
"""
from copy import deepcopy
import json

CACHE_KEY = '_wbs_saved_project_snapshot'


def session_owner(state):
    for key in ('licensed_user_row', 'demo_user_row'):
        row = state.get(key) or {}
        if isinstance(row, dict) and row.get('id'):
            return str(row['id'])
    return ''


def remember_saved_snapshot(state, snapshot, project_id, revision_id, owner_id=None):
    from core.project_state import active_format_id
    if not isinstance(snapshot, dict) or not project_id or not revision_id:
        return False
    try:
        fmt = active_format_id(snapshot)
    except ValueError:
        return False
    if str(snapshot.get('current_project_id') or project_id) != str(project_id):
        return False
    if fmt != state.get('active_format_id'):
        return False
    state[CACHE_KEY] = dict(project_id=str(project_id), revision_id=str(revision_id),
                           owner_id=str(owner_id or session_owner(state)),
                           format_id=fmt, snapshot=deepcopy(snapshot))
    return True


def saved_snapshot_for_session(state):
    cached = state.get(CACHE_KEY) or {}
    project = str(state.get('current_project_id') or '')
    revision = str(state.get('_wbs_active_saved_session_row_id') or state.get('_wbs_loaded_saved_session_id') or '')
    if (not project or not revision or cached.get('project_id') != project
            or cached.get('revision_id') != revision
            or cached.get('format_id') != state.get('active_format_id')
            or cached.get('owner_id') != session_owner(state)):
        # An unsaved, switched, or unverified project has no saved scene total.
        return {'active_format_id': state.get('active_format_id'), 'scene_blocks': {}}
    return deepcopy(cached['snapshot'])


def observe_saved_rows(state, table, operation, rows, owner_id):
    if table != 'writersblock_project_drafts':
        return False
    if operation == 'delete':
        cached = state.get(CACHE_KEY) or {}
        if cached.get('owner_id') == str(owner_id) and any(str(row.get('id') or '') == cached.get('revision_id') for row in rows or []):
            state.pop(CACHE_KEY, None)
            return True
        return False
    active_project = str(state.get('current_project_id') or '')
    active_revision = str(state.get('_wbs_active_saved_session_row_id') or state.get('_wbs_loaded_saved_session_id') or '')
    changed = False
    for row in rows or []:
        if not isinstance(row, dict) or 'draft_content' not in row:
            continue
        if row.get('draft_type') not in (None, 'project_session'):
            continue
        if str(row.get('user_id') or owner_id) != str(owner_id):
            continue
        if str(row.get('project_id') or '') != active_project:
            continue
        if operation != 'insert' and str(row.get('id') or '') != active_revision:
            continue
        try:
            snapshot = json.loads(row['draft_content'])
        except (ValueError, TypeError):
            continue
        changed = remember_saved_snapshot(state, snapshot, active_project, row.get('id'), owner_id) or changed
    return changed
