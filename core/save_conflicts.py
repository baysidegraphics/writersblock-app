"""Optimistic checkpoint concurrency without changing writing or version labels."""
import json


class SaveConflictError(RuntimeError):
    pass


def expected_checkpoint(state, project_id, row_id):
    anchor = state.get('_wbs_persisted_checkpoint') or {}
    if anchor.get('project_id') == str(project_id) and anchor.get('row_id') == str(row_id):
        return anchor['content']
    cached = state.get('_wbs_saved_project_snapshot') or {}
    if cached.get('project_id') == str(project_id) and cached.get('revision_id') == str(row_id):
        return json.dumps(cached['snapshot'], ensure_ascii=False)
    raise SaveConflictError('Reload the saved revision before saving; its baseline is unavailable.')


def verify_checkpoint(expected, actual):
    if json.loads(expected) != json.loads(actual):
        raise SaveConflictError('Another session changed this revision. Your unsaved work is preserved. Reload or save it as a new version.')


def remember_checkpoint(state, project_id, row):
    state['_wbs_persisted_checkpoint'] = dict(project_id=str(project_id), row_id=str(row['id']), content=row['draft_content'])
