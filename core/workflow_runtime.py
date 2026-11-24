"""Format-owned stage routing. No shared room execution or sibling format imports."""
from functools import partial
from importlib import import_module
import inspect

STAGES = frozenset({"concept_development", "plot_architecture", "scene_scripting",
                    "editorial_review", "publisher_assessment", "final_manuscript",
                    "drafting", "script_polish", "script_rewrite"})


def active_scene_functions(snapshot):
    from core.project_state import active_format_id
    return import_module(f"formats.{active_format_id(snapshot)}.scenes")


def get_workflow(format_id, name):
    from core.registry import get_format
    get_format(format_id)  # Validate against the existing registry before import.
    if name not in STAGES:
        raise ValueError("Unknown workflow")
    return import_module(f"formats.{format_id}.{name}").render


def format_context(format_id, namespace):
    state = namespace["st"].session_state
    if state.get("active_format_id") != format_id:
        raise ValueError("Cross-format workflow dispatch refused")
    project_id = str(state.get("current_project_id") or "")
    if (project_id and str(state.get("_wbs_locked_project_id") or "") == project_id
            and state.get("wbs_locked_format_id") not in (None, "", format_id)):
        raise ValueError("The saved project's writing format is locked")
    context = dict(namespace)
    # Remove transient sibling callbacks left by an earlier workspace.
    for name in tuple(context):
        value = context[name]
        stale_format = getattr(value, "_wbs_format_id", None) if isinstance(value, partial) else None
        if name.startswith(("wbs_ss_", "wbs_novel_", "wbs_stage4_")) or (stale_format and stale_format != format_id):
            context.pop(name)
    scenes = active_scene_functions(state)
    context.update(scene_blocks=scenes.completed_blocks,
                   scene_manuscript=scenes.manuscript,
                   scene_outline_parts=scenes.outline_parts)
    if format_id == "short_story":
        context.update(wbs_ss_blocks=scenes.wbs_ss_blocks,
                       wbs_ss_storyline=scenes.wbs_ss_storyline,
                       wbs_ss_outline_parts=scenes.wbs_ss_outline_parts)
    if format_id == "novel_prose_novella":
        context.update(wbs_novel_blocks=scenes.wbs_novel_blocks,
                       wbs_novel_manuscript=scenes.wbs_novel_manuscript)
    helpers = import_module(f"formats.{format_id}.helpers")
    for name, function in inspect.getmembers(helpers, inspect.isfunction):
        if function.__module__ == helpers.__name__:
            callback = partial(_call_owned_helper, format_id, function, context)
            callback._wbs_format_id = format_id
            context[name] = callback
    return context



def _call_owned_helper(format_id, function, context, *args, **kwargs):
    if context["st"].session_state.get("active_format_id") != format_id:
        raise ValueError("A callback from another writing format was refused")
    result=function(context, *args, **kwargs)
    if result and context.get('_wbs_rendered_workflow')=='editorial_review' and function.__name__=='wbs_stage4_save_final_acceptance':
        from core.stage_navigation import after_approval
        after_approval(context,4)
    return result


def execute_format_workflow(format_id, name, namespace):
    context = format_context(format_id, namespace)
    context['_wbs_rendered_workflow']=name
    from core.structure_ui import project_header,preferences
    final_view=name=='final_manuscript' or (name=='editorial_review' and context['st'].session_state.get('export_view'))
    project_header(context)
    from quill.modular_context import prepare
    prepare(context["st"].session_state,context.get("_wbs_display_revision"))
    if format_id=='novel_prose_novella' and name in {'plot_architecture','scene_scripting','editorial_review','publisher_assessment'}:
        from formats.novel_prose_novella.work_type import guidance
        context['st'].caption(guidance(context['st'].session_state))
    if final_view or name=='concept_development':
        from core.publication_choices import controls as layout_choices
        layout_choices(context)
    if final_view:
        from core.publication_layout import render_final
        return render_final(context)
    if name=='concept_development':preferences(context)
    if name=='editorial_review' and not context['st'].session_state.get('export_view'):
        from core.stage_navigation import review_destination
        review_destination(context)
    if name == "scene_scripting":
        from sidebar.summary import render_saved_scene_total
        render_saved_scene_total(context["st"], namespace)
    try:
        from core.manuscript_structure import profile,configured,approved
        spec=profile(format_id)
        if spec['structured_editor']:
            from core.structure_ui import editor,review
            if name=='scene_scripting' and editor(context):return
            if name=='editorial_review' and not context['st'].session_state.get('export_view') and review(context):return
            if name=='final_manuscript' and spec.get('explicit_page_turns'):
                from formats.childrens_picture_book.page_turn_ui import final as page_final
                page_final(context)
                from core.format_services import coach
                coach(context)
                return
            if name=='final_manuscript' and configured(context['st'].session_state):
                state=context['st'].session_state;st=context['st']
                if not approved(state):
                    st.warning('Approve the exact saved organization and manuscript in Editorial Review before export.');return
                exports=import_module('formats.'+format_id+'.exports')
                original=context['build_final_output_docx_bytes']
                context['build_final_output_docx_bytes']=lambda title,text,target:exports.build_docx(state,original(title,text,target))
                picture=context.get('build_picture_book_layout_docx_bytes')
                if picture:context['build_picture_book_layout_docx_bytes']=lambda *a,**kw:exports.build_docx(state,picture(*a,**kw))
                st.download_button('Download Structured Text (.txt)',data=exports.build_text(state),
                    file_name='structured_manuscript.txt',mime='text/plain',key='structured_text_export')
                from core.manuscript_structure import export_plan
                st.download_button('Download Organization Plan (.txt)',data=export_plan(state),
                    file_name=format_id+'_organization_plan.txt',mime='text/plain',key='structured_plan_export')
        if name=='publisher_assessment' and format_id not in {'biography_memoir','childrens_interactive_educational'}:
            # Render before stage validation may stop the page, so Quill can
            # explain missing prerequisites without altering approval behavior.
            from core.format_services import coach
            coach(context)
        return get_workflow(format_id, name)(context)
    finally:
        if namespace.get("_wbs_scene_total_views"):
            from sidebar.summary import refresh_scene_total_views
            refresh_scene_total_views(namespace)


def call_format_helper(name, namespace, *args, **kwargs):
    from core.project_state import active_format_id
    fmt = active_format_id(namespace["st"].session_state)
    context = format_context(fmt, namespace)
    helpers = import_module(f"formats.{fmt}.helpers")
    function = getattr(helpers, name, None)
    if not inspect.isfunction(function) or function.__module__ != helpers.__name__:
        raise ValueError(f"Helper {name} does not belong to active format {fmt}")
    return function(context, *args, **kwargs)


def run_workflow(name, namespace):
    from core.project_state import active_format_id
    from core.registry import get_format
    fmt = active_format_id(namespace["st"].session_state)
    return get_format(fmt).run_workflow(name, namespace)
