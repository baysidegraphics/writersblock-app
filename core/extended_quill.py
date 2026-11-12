"""Six-stage coaching adapter for extension formats; original Quill code is untouched."""
from copy import deepcopy
from types import SimpleNamespace
from quill.wbs_quill_runtime_bridge import QuillRuntimeBridge
from quill.wbs_quill_studio_coach import QuillStudioCoach,QuillCoachMessage,QuillSeverity

FORMAT_IDS={'biography_memoir','childrens_interactive_educational'}
STAGE_TITLES=('Concept Development','Plot Architecture','Scene Scripting','Editorial Review','Publisher Assessment','Final Manuscript')


def stage_number(state):
    stage=state.get('project_stage','Intake')
    if stage=='Isolation Guardrail':return 6 if state.get('export_view') else 4
    return {'Intake':1,'Sandbox':2,'Plot Architect':3,'Drafting':3,'Drafting Engine':3,
            'Revision Engine':4,'Rewrite Engine':3,'Publisher Assessment':5}.get(stage,1)


class ExtensionCoach(QuillStudioCoach):
    def coach(self,request_text,snapshot,*,decision=None,detail_mode=None):
        step=snapshot['step'];fmt=snapshot['active_format_id']
        subject='life events, historical context and traceable sources' if fmt=='biography_memoir' else 'age band, learning goals, vocabulary and adult guidance'
        plans='chapters linked to the supplied life events' if fmt=='biography_memoir' else 'learning units and printed story choices'
        actions=(f'Review {subject}, then save the setup and continue.',f'Organize and explicitly approve {plans}.',
                 'Review and save the selected chapter or unit without replacing sibling text.',
                 'Complete the evidence or educational checks and accept this exact saved revision.',
                 'Review the optional publisher assessment, or continue without generating a report.',
                 'Download the approved saved manuscript and print package; digital playback is not implemented.' if fmt=='childrens_interactive_educational' else 'Download the approved saved manuscript with its research appendices.')
        text=actions[step-1]
        if 'why' in request_text.lower() or str(detail_mode).lower().endswith('detail'):
            text+=' Saved writing remains authoritative. Quill suggestions are read-only proposals; source and review changes require author approval.'
        return QuillCoachMessage(text=text,stage=STAGE_TITLES[step-1],severity=QuillSeverity.INFO,next_action=actions[step-1])


class ExtensionQuillBridge(QuillRuntimeBridge):
    def __init__(self,agent=None,display_name=''):
        super().__init__(agent=agent,display_name=display_name)
        self.coach=ExtensionCoach(display_name=display_name)

    def snapshot(self,state):
        fmt=state.get('active_format_id')
        if fmt not in FORMAT_IDS:raise ValueError('The extension Quill adapter cannot run another writing format.')
        result={name:deepcopy(state.get(name)) for name in ('active_format_id','project_title','current_project_id','project_stage',
            'story_seed','quill_format_instructions','quill_template_context','tone_style','dialogue_style','format_template_values')}
        result['step']=stage_number(state);result['stage_name']=STAGE_TITLES[result['step']-1]
        return result

    def analyze(self,request_text,state):
        snapshot=self.snapshot(state)
        action=self.coach.coach(request_text,snapshot).next_action
        packet={'action':'author_review','next_best_action':action,'blockers':[],'format_id':snapshot['active_format_id']}
        return snapshot,SimpleNamespace(blockers=(),next_best_action=action,reason='Respect the active format and author-approved saved revision.',to_dict=lambda:packet)


class ReadOnlyBackendAgent:
    """Reuse the already initialized writer backend; never save, rewrite or navigate."""
    def __init__(self,backend):self.backend=backend
    def run(self,request,**kwargs):
        client=getattr(self.backend,'client',None);model=getattr(self.backend,'model_name',None)
        if client is None or not model:raise RuntimeError('Quill conversation service is unavailable.')
        import json
        metadata=kwargs.get('metadata') or {}
        prompt=('You are Quill. Answer the author about the active writing project. Follow the supplied format instructions. '
                'Offer proposals only; never claim to save, edit, verify external facts, navigate or implement clickable output. '
                'For biography do not invent facts, dates, citations or quotations.\\nPROJECT CONTEXT:\\n'+json.dumps(metadata,ensure_ascii=False,default=str)+'\\nAUTHOR QUESTION:\\n'+str(request))
        response=client.models.generate_content(model=model,contents=prompt)
        text=str(getattr(response,'text','') or '')
        if not text.strip():raise ValueError('Quill returned no response.')
        return {'text':text}
    def run_with_approval(self,request,**kwargs):return self.run(request,**kwargs)


def render(context):
    state=context['st'].session_state
    agent=context.get('extension_quill_agent') or ReadOnlyBackendAgent(state.get('backend'))
    bridge=ExtensionQuillBridge(agent=agent)
    renderer=context.get('extension_quill_renderer')
    if renderer is None:
        from quill.wbs_quill_streamlit_ui import render_quill_studio_coach
        renderer=render_quill_studio_coach
    return renderer(bridge=bridge,st_module=context['st'],show_prelude=True)
