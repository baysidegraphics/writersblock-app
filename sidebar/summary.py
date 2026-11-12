"""Format-independent readout of a format-owned completed manuscript total.

The UI should display an existing format-produced summary. Do not count concept,
plot choices or other temporary widget content here.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectSummary:
    format_id: str
    completed_words: int
    scene_count: int

def from_format_report(format_id, completed_words, scene_count):
    from template_registry import FORMAT_REGISTRY
    if format_id not in FORMAT_REGISTRY:
        raise ValueError("Refuse summary for unregistered format")
    words, scenes = int(completed_words), int(scene_count)
    if words < 0 or scenes < 0:
        raise ValueError("Totals cannot be negative")
    return ProjectSummary(format_id, words, scenes)


def from_snapshot(snapshot):
    from core.project_state import active_format_id, completed_report
    words, scenes = completed_report(snapshot)
    if active_format_id(snapshot)=='childrens_picture_book':
        from formats.childrens_picture_book.page_turns import pages,author_source
        scenes=len(pages(author_source(snapshot)))
    return from_format_report(active_format_id(snapshot), words, scenes)


def from_session(state):
    from core.saved_scene_state import saved_snapshot_for_session
    return from_snapshot(saved_snapshot_for_session(state))


def refresh_scene_total_views(namespace):
    state = namespace["st"].session_state
    report = from_session(state)
    from core.manuscript_structure import profile,unit_plan,blocks
    spec=profile(report.format_id)
    label='Completed '+spec['plural']+': '+str(report.scene_count)
    if report.format_id=='short_story':label='Completed Scenes: '+str(report.scene_count)
    elif spec['structured_editor'] and spec['group']:
        from core.saved_scene_state import saved_snapshot_for_session
        saved=saved_snapshot_for_session(state)
        try:groups=len({r['group_number'] for r in unit_plan(saved) if r['unit_id'] in blocks(saved)})
        except (ValueError,KeyError):groups=0
        label+=' · '+spec['group']+'s: '+str(groups)
    for view in namespace.get("_wbs_scene_total_views", []):
        view.markdown(f"**Saved Scene Scripting Words: {report.completed_words:,}**  \n{label}")
    return report


def render_saved_scene_total(st, namespace):
    view = st.empty()
    namespace.setdefault("_wbs_scene_total_views", []).append(view)
    return refresh_scene_total_views(namespace)
