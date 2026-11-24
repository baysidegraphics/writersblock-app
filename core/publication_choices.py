"""Format-owned presentation choices. No source edits, generation or approval changes."""
from importlib import import_module
from html import escape


def choices(snapshot):
    return getattr(import_module('formats.'+snapshot['active_format_id']+'.publication'),'LAYOUT_CHOICES',[])


def selected(snapshot):
    from core.image_placement import settings
    options=choices(snapshot)
    if not options:return ''
    value=settings(snapshot).get('layout_style')
    # Missing selection preserves legacy image behavior, including saved slots.
    return value if value in dict(options) else ''


def default_image(snapshot):
    fmt=snapshot['active_format_id'];style=selected(snapshot)
    if fmt=='biography_memoir':return style in {'photo_rich','historical'}
    return fmt=='youtube_shorts' and style=='storyboard'


def image_label(snapshot):
    if snapshot['active_format_id']=='youtube_shorts':return 'Storyboard frame / visual direction'
    if snapshot['active_format_id']=='biography_memoir':
        return 'Historical document / archival image' if selected(snapshot)=='historical' else 'Photograph or historical document'
    return 'Optional illustration'


def thumbnail(style,label):
    # Code-native visual sample: photograph/document panels and actual text placement.
    illustrated=style not in ('traditional','recording')
    art=('''<rect x="24" y="48" width="152" height="80" fill="#cfe8e5"/><circle cx="145" cy="68" r="10" fill="#f4ce65"/><path d="M24 128 L70 80 L115 128 L142 100 L176 128" fill="#43877a"/>''' if illustrated else '')
    if style=='historical':art='<rect x="38" y="40" width="124" height="94" fill="#e9dfc8"/><path d="M54 60h90m-90 12h78m-78 12h90m-90 12h65m-65 12h82" stroke="#8d795b"/>'
    start=148 if illustrated else 55
    lines=''.join(f'<path d="M24 {y}h152" stroke="#77808e" stroke-width="2"/>' for y in range(start,230,13))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="260" viewBox="0 0 200 260"><rect x="1" y="1" width="198" height="258" fill="white" stroke="#999"/><text x="100" y="26" text-anchor="middle" font-size="10">{escape(label)}</text>{art}{lines}</svg>'


def controls(context):
    st=context['st'];state=st.session_state;options=choices(state)
    if not options:return
    from core.image_placement import settings,KEY
    from core.structure_ui import widget_key
    st.subheader('Publication layout')
    columns=st.columns(len(options))
    for column,(key,label) in zip(columns,options):
        with column:st.image(thumbnail(key,label),caption=label,width=160)
    options=[('','Keep existing saved layout')]+options
    current=selected(state)
    value=st.selectbox('Overall publication layout',[key for key,label in options],format_func=lambda key:dict(options)[key],index=[key for key,label in options].index(current),key=widget_key(state,'publication_style'))
    if value!=current:
        raw=settings(state);raw['layout_style']=value;state[KEY]=raw
        if state['active_format_id']=='novel_prose_novella':
            prefix=widget_key(state,'image_')
            for field in list(state):
                if str(field).startswith(prefix):del state[field]
    st.caption('Layout changes preserve text, source references and existing image metadata. Individual image positions can be adjusted in Final Manuscript. Save changes to retain them with this revision.')
    if st.button('Save Publication Layout to Current Revision',key=widget_key(state,'save_publication_style')):
        if state.get('demo_mode') or not state.get('_wbs_active_saved_session_row_id'):st.warning('Load a saved Writer Edition revision first.')
        elif context['save_current_project_session_to_supabase']():st.success('Publication layout saved.');st.rerun()
        else:st.error('Layout save failed. Working changes retained.')
