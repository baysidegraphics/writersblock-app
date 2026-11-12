"""Universal Concept Development layout, used only by the two extension formats."""
from copy import deepcopy
import hashlib
import html
import json
from core.text import count_words
from core.saved_scene_state import saved_snapshot_for_session
from core.format_services import data,key,coach,select_format,save_checkpoint,advance,approval_signature

LAYOUT_STYLE = '\n        <style>\n        /* Keep Quill inside its actual right column so every middle-panel field\n           is physically constrained and can never run underneath it. */\n        div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),\n        div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {\n            position: sticky !important;\n            top: 0.75rem !important;\n            align-self: flex-start !important;\n            max-height: calc(100vh - 1.5rem) !important;\n            overflow-y: auto !important;\n            z-index: 20 !important;\n            background: var(--background-color, transparent);\n        }\n\n        /* Primary Writer navigation and format-selector hierarchy. */\n        [data-testid="stMain"] div[data-testid="stHorizontalBlock"]:first-of-type button p {\n            font-weight: 700 !important;\n            font-size: 1.02rem !important;\n        }\n        .wbs-format-selector-title {\n            font-size: 1.08rem !important;\n            font-weight: 700 !important;\n            line-height: 1.2 !important;\n            margin: 0 0 0.35rem 0 !important;\n        }\n\n        /* Raise the complete Writer workspace to recover vertical real estate. */\n        [data-testid="stMainBlockContainer"] {\n            padding-top: 1.0rem !important;\n        }\n\n        @media (max-width: 1100px) {\n            div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),\n            div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {\n                position: static !important;\n                max-height: none !important;\n                overflow: visible !important;\n            }\n        }\n        </style>\n        '

SOURCE_OPTIONS = (
    '-- Use Current Saved Manuscript / Storyline --',
    '-- Enter Your Own Story / Premise --',
    '-- Quill-Assisted Starting Point --',
    '-- Upload / Replace with Different Draft / Manuscript --',
)
SOURCE_MODES = ('Saved Manuscript','Custom Plot Line','Quill Assisted','Replacement Draft / Manuscript')


def _relationship(context,fmt):
    st=context['st'];state=st.session_state
    st.markdown('### Project Relationship')
    options=['Standalone Book','Book in a Series']
    project_id=str(state.get('current_project_id') or '')
    membership=context['get_series_metadata_by_project']() if context['get_current_user_id']() else {}
    member=membership.get(project_id) or {}
    registered=str(member.get('series_name') or '').strip()
    if project_id and not registered and state.get('project_scope')=='Book in a Series':
        registered=str(state.get('series_name') or '').strip()
    saved_scope='Book in a Series' if registered else 'Standalone Book'
    selected_default=saved_scope if project_id else str(state.get('project_scope') or options[0])
    scope_context=f"{project_id or 'new'}:{registered}"
    if state.get('_wbs_simple_series_context')!=scope_context:
        state['_wbs_simple_series_context']=scope_context
        state['project_scope_selector']=selected_default
        state['wbs_confirm_series_link']=False;state['wbs_confirm_series_removal']=False
        state.pop('wbs_simple_series_choice',None);state.pop('wbs_simple_series_new_name',None)
    chosen=st.radio('Project Type:',options,horizontal=True,key='project_scope_selector')
    if project_id:
        state['project_scope']=saved_scope;state['series_name']=registered
        state['series_key']=context['make_series_key'](registered)
        if registered and member.get('series_book_number'):state['series_book_number']=int(member['series_book_number'])
    else:state['project_scope']=chosen
    if chosen=='Book in a Series':
        known=list(context['get_existing_series_names']())
        names=known+['Create New Series']
        existing=registered if project_id else str(state.get('series_name') or '')
        if 'wbs_simple_series_choice' not in state:state['wbs_simple_series_choice']=existing if existing in known else 'Create New Series'
        with st.columns([1,1],gap='small')[0]:
            choice=st.selectbox('Select Series:',names,key='wbs_simple_series_choice')
            selected=st.text_input('New Series Name:',key='wbs_simple_series_new_name',max_chars=80).strip() if choice=='Create New Series' else choice
        if not project_id:
            state['series_name']=selected;state['series_key']=context['make_series_key'](selected)
            state['series_continuity_mode']='Strict'
            if selected:
                state['series_book_number']=context['get_next_series_book_number'](selected)
                st.caption('This new project will join the selected series when you save its master project.')
            else:st.caption('Enter a series name before saving the project.')
    elif not project_id:
        state['series_name']='';state['series_key']='';state['series_reference_ids']=[]
    # Existing membership changes require the established explicit series control
    # beside the saved project title; merely browsing the relationship radio
    # never changes a saved membership or writes a record.


def _proposal_key(context,fmt):return key(context,fmt,'quill_proposal')


def _apply_pending(context,fmt):
    state=context['st'].session_state
    pending=state.pop(key(context,fmt,'quill_pending'),None)
    if pending is not None:
        state['story_seed']=pending;state['saved_quill_concept']=pending
        state[key(context,fmt,'quill_concept')]=pending
        state[context['get_active_format_widget_key']('concept_story_premise')]=pending


def _shared_controls(context,fmt):
    st=context['st'];state=st.session_state
    tones=['Professional','Warm','Serious','Humorous','Suspenseful','Cinematic','Vivid & Descriptive']
    current=state.get('tone_style') or tones[0]
    if current not in tones:tones.append(current)
    tone_key=context['get_active_format_widget_key']('concept_prose_tone')
    with st.columns([3.0,1.2])[0]:
        state['tone_style']=st.selectbox('Tone / Aesthetic:',tones,index=tones.index(current),key=tone_key)
    mode=state.get('version_source_mode') or state.get('starting_source_mode') or 'Custom Plot Line'
    editable=mode in {'Custom Plot Line','Story Idea'}
    premise_key=context['get_active_format_widget_key']('concept_story_premise')
    if premise_key not in state or not editable:state[premise_key]=state.get('story_seed') or ''
    st.markdown('#### Story Premise')
    premise=st.text_area('Story Premise:',height=210,key=premise_key,disabled=not editable,
        help='Your factual life-story premise or educational story premise. Existing manuscript text is kept separately.')
    if editable:state['story_seed']=premise
    if mode in {'Custom Plot Line','Story Idea','Quill Assisted'}:
        words=count_words(premise);st.caption(f'{words:,} / 1,000 words')
        if words>1000:st.warning('This entry exceeds the 1,000-word Concept Development limit.')
    dialogue=list(context['DIALOGUE_STYLE_OPTIONS'])
    current=state.get('dialogue_style') or dialogue[0]
    if current not in dialogue:dialogue.append(current)
    with st.columns([3.0,1.2])[0]:
        state['dialogue_style']=st.selectbox('Dialogue Style:',dialogue,index=dialogue.index(current),key=key(context,fmt,'dialogue_style'),
            help='For life writing, only documented quotations or clearly labeled recollections may be used. Educational dialogue follows the selected age band.')


def _quill_proposal(context,fmt,template):
    st=context['st'];state=st.session_state
    concept_key=key(context,fmt,'quill_concept')
    existing=state.get('saved_quill_concept') or state.get('story_seed') or ''
    text=st.text_area('Quill-Assisted Starting Concept:',value=existing,height=260,key=concept_key)
    state['story_seed']=text;state['saved_quill_concept']=text
    st.caption('Suggestions remain proposals until you explicitly accept them. Saved chapters and approved plans are never regenerated here.')
    if st.button('Create Starting Point From My Development Setup',key=key(context,fmt,'quill_suggest'),disabled=bool(state.get('demo_mode'))):
        backend=state.get('backend');client=getattr(backend,'client',None);model=getattr(backend,'model_name',None)
        if client is None or not model:st.warning("Quill's writing service is unavailable.")
        else:
            packet={'format':template['display_name'],'development_fields':data(state,fmt),'existing_premise':text,
                    'tone':state.get('tone_style'),'dialogue':state.get('dialogue_style')}
            prompt=('Propose a 100–180 word starting concept for the author to review. Do not rewrite a saved manuscript or replace an approved plan. '
                    'For life writing use ONLY supplied events and sources; never invent facts, historical context, dates, interviews, motives or quotations. '
                    'Describe missing evidence as a research gap. For educational books honor the age band and subject, printed story choices, vocabulary and adult-supported activities. '
                    'Do not claim working clickable output. Return only the proposal.\nFORMAT RULES:\n'+template.get('description','')+'\n'+str(state.get('quill_format_instructions') or '')+
                    '\nAUTHOR MATERIAL:\n'+json.dumps(packet,ensure_ascii=False,default=str))
            try:
                response=client.models.generate_content(model=model,contents=prompt)
                suggestion=str(getattr(response,'text','') or '')
                if not suggestion.strip() or count_words(suggestion)>1000:raise ValueError('No usable concept within the 1,000-word limit was returned.')
                state[_proposal_key(context,fmt)]={'text':suggestion,'signature':approval_signature(dict(state),fmt)}
            except Exception as exc:st.warning('Quill could not prepare a proposal: '+str(exc))
    proposal=state.get(_proposal_key(context,fmt))
    if isinstance(proposal,dict):
        st.text_area('Proposed Starting Point — Review Before Accepting:',value=proposal['text'],disabled=True,height=200,key=key(context,fmt,'quill_proposal_view')+'_'+hashlib.sha256(proposal['text'].encode()).hexdigest()[:10])
        stale=proposal.get('signature')!=approval_signature(dict(state),fmt)
        if st.button('Use This Starting Point',key=key(context,fmt,'quill_accept'),disabled=stale):
            state[key(context,fmt,'quill_pending')]=proposal['text'];state.pop(_proposal_key(context,fmt),None)
            st.rerun()
        if stale:st.caption('The setup changed after this proposal. Request a new suggestion before accepting it.')


def _starting_source(context,fmt,template):
    st=context['st'];state=st.session_state
    st.markdown('---');st.markdown('### Choose a Starting Point')
    current=state.get('version_source_mode') or state.get('starting_source_mode') or 'Custom Plot Line'
    if current=='Existing Draft / Manuscript':current='Replacement Draft / Manuscript'
    index=SOURCE_MODES.index(current) if current in SOURCE_MODES else 1
    selected=st.radio('Starting Source:',SOURCE_OPTIONS,index=index,key=key(context,fmt,'starting_source'))
    mode=SOURCE_MODES[SOURCE_OPTIONS.index(selected)]
    state['version_source_mode']=mode;state['starting_source_mode']=mode
    if mode=='Saved Manuscript':
        source=state.get('saved_version_source_text') or state.get('current_draft_output') or ''
        if source:
            state['saved_version_source_text']=source;state['saved_version_source_word_count']=count_words(source)
            st.text_area('Current Saved Manuscript / Storyline:',value=source,height=320,disabled=True,key=key(context,fmt,'saved_source'))
        else:st.warning('Load a saved manuscript before selecting this source.')
    elif mode=='Custom Plot Line':st.caption('Edit the Story Premise field above. Starting-source changes do not replace saved chapter or unit text.')
    elif mode=='Quill Assisted':_quill_proposal(context,fmt,template)
    else:
        upload=st.file_uploader('Upload / Replace with Different Draft / Manuscript:',type=['docx','txt'],key=key(context,fmt,'upload'))
        if upload is not None:
            try:
                text=context['extract_uploaded_manuscript_text'](upload)
                if not str(text).strip():raise ValueError('The uploaded source is empty.')
                if count_words(text)>120000:raise ValueError('The replacement source exceeds 120,000 words.')
                state['imported_source_text']=text;state['imported_source_name']=str(getattr(upload,'name','Uploaded source'));state['imported_source_word_count']=count_words(text)
            except Exception as exc:st.warning('The replacement source was not loaded: '+str(exc))
        if state.get('imported_source_text'):
            st.text_area('Replacement Source — Read Only:',value=state['imported_source_text'],height=320,disabled=True,key=key(context,fmt,'imported_source'))
        st.caption('The replacement is retained as source material. Apply chapter or unit edits explicitly in Scene Scripting.')


def _can_save_source(state):
    mode=state.get('version_source_mode')
    if mode in {'Custom Plot Line','Quill Assisted'} and count_words(state.get('story_seed') or '')>1000:return False
    if mode=='Quill Assisted' and not str(state.get('story_seed') or '').strip():return False
    if mode=='Saved Manuscript' and not str(state.get('saved_version_source_text') or '').strip():return False
    if mode=='Replacement Draft / Manuscript' and not str(state.get('imported_source_text') or '').strip():return False
    return True


def _checkpoint_controls(context,fmt):
    st=context['st'];state=st.session_state
    context['render_save_as_named_version_control']('extended_'+fmt)
    save_col,continue_col=st.columns(2,gap='small')
    with save_col:
        clicked=st.button('Save And/Or Continue To Next Stage',key='wbs_stage1_save_or_continue',use_container_width=True,disabled=bool(state.get('demo_mode')))
    if clicked:
        if not _can_save_source(state):st.warning('Choose an available starting source within the Concept Development limits.');return
        if save_checkpoint(context,fmt,2):
            state[key(context,fmt,'concept_saved_approval')]=approval_signature(dict(state),fmt)
            advance(context,'Sandbox')
    saved=saved_snapshot_for_session(state)
    ready=bool(saved.get('current_project_id') and _can_save_source(state)
        and approval_signature(saved,fmt)==approval_signature(dict(state),fmt)
        and state.get(key(context,fmt,'concept_saved_approval'))==approval_signature(dict(state),fmt))
    with continue_col:
        if st.button('Continue to Plot Architecture',key='generate_sandbox_paths',use_container_width=True,disabled=not ready):advance(context,'Sandbox')


def render_concept(context,fmt,template,render_domain):
    st=context['st'];state=st.session_state
    data(state,fmt);_apply_pending(context,fmt)
    selection=state.get(key(context,fmt,'starting_source'))
    if selection in SOURCE_OPTIONS:
        state['version_source_mode']=SOURCE_MODES[SOURCE_OPTIONS.index(selection)]
        state['starting_source_mode']=state['version_source_mode']
    st.markdown(LAYOUT_STYLE,unsafe_allow_html=True)
    main,quill=st.columns([2.65,1.15],gap='large')
    with main:
        st.header('🗺️ Step 1: Concept Development')
        st.markdown('### Writing Format — '+template['display_name'])
        select_format(context,fmt)
        st.markdown('##### '+str(template.get('concept_ui',{}).get('step_subtitle') or 'Build the foundation for your project.'))
        label=template['display_name']+' / Project Title/Revision'
        if state.get('current_project_id'):
            display_title=str(state.get('project_title') or '')
            revision=str(context.get('_active_version_number') or '')
            if revision:display_title+=' — '+(revision if revision.startswith('V-') else 'V-'+revision)
            st.caption('Loaded saved project — saved Concept Development choices are restored where recorded.')
            st.markdown('**'+label+'**');st.markdown('<div style="background:#262730;color:#ffffff;padding:0.65rem 0.8rem;border:1px solid #41444f;border-radius:0.45rem;min-height:2.4rem;">'+html.escape(display_title)+'</div>',unsafe_allow_html=True)
            context['render_save_open_project_to_series']()
        else:state['project_title']=st.text_input(label,value=state.get('project_title') or '',key='project_title_input').strip()
        _relationship(context,fmt)
        st.markdown('### '+template['display_name']+' Development Setup')
        st.caption(template.get('description') or '')
        render_domain(context)
        _shared_controls(context,fmt)
        _starting_source(context,fmt,template)
        _checkpoint_controls(context,fmt)
    with quill:
        st.markdown('<div class="wbs-writer-quill-sticky-anchor"></div>',unsafe_allow_html=True)
        coach(context)
