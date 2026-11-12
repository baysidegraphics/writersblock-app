"""Author-controlled page breaks. No separate page-turn column or checkbox."""
from core.structure_ui import widget_key
from .page_turns import author_source,working_key,pages,save,render_pages,TOKEN,rewrite_page

HELP='''### Using Page Turns

To start a new page, type **[Page Turn]** directly into your story wherever you want the page to end and the next page to begin.

**Example:**

Mittens heard scratching behind the door. What could it be?

**[Page Turn]**

A tiny puppy jumped out!

WBS automatically begins a new page after the marker. You may insert, move or remove page turns whenever you edit your story.
'''


def editor(context):
    st=context['st'];state=st.session_state
    st.header("3. Children's Picture Book — Story Editor")
    st.markdown(HELP)
    baseline=author_source(state);key=working_key(state)
    if key not in state:state[key]=baseline
    from components.page_turn_editor import render
    from core.text import get_text_signature
    source=render(st,baseline,widget_key(state,'inline_editor_'+get_text_signature(baseline)[:16]+'_'+str(state.get(widget_key(state,'editor_replacement'),0))),key)
    state[key]=source
    with st.expander('[Insert Image] — edit an illustrated story page',expanded=False):
        selected=st.selectbox('Image editing page',list(range(1,len(pages(source))+1)),key=widget_key(state,'image_page'))
        from core.image_editor import edit as image_edit
        from .page_turns import TOKEN
        import re
        pieces=re.split('('+TOKEN.pattern+')',source)
        edited=image_edit(context,selected,pieces[(selected-1)*2],widget_key(state,'page_image_text_'+str(selected)),'Page story text',300)
        if edited!=pieces[(selected-1)*2]:
            pieces[(selected-1)*2]=edited;source=''.join(pieces);state[key]=source
    st.caption(str(len(pages(source)))+' pages · Page numbering updates as you edit. Saved writing changes only when you save.')
    if st.button('Save Story And Continue',key=widget_key(state,'save_page_story'),type='primary'):
        try:save(context,source)
        except (ValueError,RuntimeError) as exc:st.error(str(exc))
        else:context['wbs_request_stage_change']('Isolation Guardrail',export_view=False)
    name=st.text_input('New version name (optional)',key=widget_key(state,'page_version_name'))
    if st.button('Save Story As New Version',key=widget_key(state,'save_page_version')):
        try:save(context,source,True,name or 'Author page-turn edit')
        except (ValueError,RuntimeError) as exc:st.error(str(exc))
        else:st.rerun()
    with st.expander('Rewrite a page — author approval required',expanded=False):
        number=st.selectbox('Page to rewrite',list(range(1,len(pages(source))+1)),key=widget_key(state,'rewrite_page'))
        instructions=st.text_area('Your rewrite instructions',key=widget_key(state,'rewrite_instructions'))
        backend=state.get('backend');method=getattr(backend,'run_rewrite_engine',None)
        allowed=context.get('can_use_rewrite',False)
        if callable(allowed):allowed=allowed()
        if state.get('demo_mode') or not allowed:method=None
        if not callable(method):st.caption('Rewriting is unavailable in this session. Manual editing remains available.')
        if st.button('Preview Rewrite of Selected Page',disabled=not callable(method),key=widget_key(state,'preview_page_rewrite')):
            try:
                if context.get('require_product_access'):context['require_product_access']('revision')
                def rewrite(text):
                    result=method(text,'Custom Rewrite','Entire Manuscript',instructions,
                        tone_style=state.get('tone_style') or '',author_style=state.get('author_style') or '')
                    if not isinstance(result,str) or not result.strip() or 'LOCAL FALLBACK' in result.upper():raise ValueError('No successful rewrite was returned.')
                    return result
                state[widget_key(state,'page_rewrite_proposal')]={'source':source,'result':rewrite_page(source,number,rewrite)}
            except Exception:st.error('The rewrite could not be completed. Your saved and working story are unchanged.')
        proposal=state.get(widget_key(state,'page_rewrite_proposal'))
        if proposal and proposal['source']==source:
            fmt=state['active_format_id'];preview={'active_format_id':fmt,'current_project_id':state.get('current_project_id'),'picture_book_page_size':state.get('picture_book_page_size'),'children_publication_layout':state.get('children_publication_layout')}
            preview['format_template_values']={fmt:{'page_turn_source':proposal['result']}}
            render_pages(st,preview,show_controls=False)
            if st.button('Accept Rewrite Into Working Story',key=widget_key(state,'accept_page_rewrite')):
                state[key]=proposal['result'];state.pop(widget_key(state,'page_rewrite_proposal'),None)
                # Remount only for this explicit author-accepted replacement.
                state[widget_key(state,'editor_replacement')]=state.get(widget_key(state,'editor_replacement'),0)+1
                st.rerun()


def final(context):
    st=context['st'];state=st.session_state
    st.header('6. Picture Book — Final Manuscript')
    from core.children_publication import controls,illustration_controls,settings
    controls(context,'final')
    illustration_controls(context,'picture-page',range(1,len(pages(author_source(state)))+1))
    render_pages(st,state)
    if not context['wbs_editorial_ready_for_assessment']():
        st.warning('Approve the exact saved story and pagination in Editorial Review before downloading.');return
    if state.get('demo_mode'):
        st.info('Downloads require the full Writer Edition.');return
    from core.saved_scene_state import saved_snapshot_for_session
    saved=saved_snapshot_for_session(state)
    if settings(state)!=settings(saved) or __import__('core.inline_images',fromlist=['data']).data(state)!=__import__('core.inline_images',fromlist=['data']).data(saved):
        st.warning('Save the adjusted layout before downloading.');return
    from .page_turns import export_docx,export_text
    from core.text import safe_download_stem
    title=state.get('project_title') or ''
    base=context['build_picture_book_layout_docx_bytes'](title,context['build_picture_book_spreads_locally'](state.get('current_draft_output') or ''),state.get('picture_book_page_size',context['DEFAULT_PICTURE_BOOK_PAGE_SIZE']))
    stem=safe_download_stem(title)
    from core.image_pdf import download
    download(st,export_docx(saved,base),stem,'picture_image')
    st.download_button('Download Picture Book (.docx)',data=export_docx(state,base),file_name=stem+'.docx',
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key='page_turn_docx')
    st.download_button('Download Picture Book (.txt)',data=export_text(state),file_name=stem+'.txt',mime='text/plain',key='page_turn_txt')
