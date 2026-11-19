"""Work-type planning within the existing Novel / Prose / Novella format."""
from copy import deepcopy
FORMAT='novel_prose_novella'
TYPES={
 'Novel':dict(words='70,000–100,000 words',chapters='20–40 chapters',chapter_length='2,000–5,000 words per chapter',plot='Allow sustained character arcs and layered conflict; develop supporting subplots only when they serve the central story.',pacing='Balance escalation, discoveries and reflective scenes across a longer arc.',organization='Chapters may contain multiple scenes and beats; vary chapter lengths to support turning points.',editorial='Assess long-form continuity, subplot payoff, character development and sustained pacing.'),
 'Novella':dict(words='20,000–40,000 words',chapters='8–16 chapters',chapter_length='1,500–3,000 words per chapter',plot='Favor a focused central conflict and a small number of supporting threads; preserve every author-approved subplot.',pacing='Prefer concentrated escalation and economical transitions while retaining necessary character development.',organization='Use compact chapters or longer continuous sections; scenes and beats should serve the main arc.',editorial='Assess concentration, economy, emotional completeness and resolution without demanding novel-scale complexity.'),
 'Other Prose Fiction':dict(words='Author-defined; no universal word-count range',chapters='Author-defined; chapters are optional where the work calls for continuous prose',chapter_length='Variable; match the chosen narrative form',plot='Follow the author-defined prose form; use only the complexity and subplots appropriate to its intent.',pacing='Evaluate rhythm against the stated form and purpose rather than novel or novella conventions.',organization='Use chapters, scenes and beats flexibly within the existing chapter editor; no sections are created or removed automatically.',editorial='Assess the stated form, voice, coherence and completeness without imposing novel or novella expectations.')}


def settings(state):
    raw=((state.get('format_template_values') or {}).get(FORMAT) or {})
    legacy='Novella' if str(raw.get('book_scale') or '').lower().startswith('novella') else 'Novel'
    kind=raw.get('work_type',legacy)
    if kind not in TYPES:kind='Novel'
    return kind,raw


def guidance(state):
    if state.get('active_format_id')!=FORMAT:return ''
    kind,raw=settings(state);p=TYPES[kind]
    lines=['Work Type: '+kind,'Recommendations only: '+p['words']+'; '+p['chapters']+'; '+p['chapter_length']+'.']
    for key,label in [('author_word_target','Author manuscript word target'),('author_chapter_target','Author planned chapters'),('author_chapter_words','Author preferred chapter length')]:
        if raw.get(key):lines.append(label+': '+str(raw[key]))
    lines += [p['plot'],p['pacing'],p['organization'],p['editorial'], 'Author targets override recommendations. Shorter or longer manuscripts are valid. Never fail integrity solely for length, chapter count or number of subplots. Preserve saved chapters, approved Plot A/B/C and writing; offer changes as proposals only.']
    return '\n'.join(lines)


def controls(context):
    st=context['st'];state=st.session_state;kind,old=settings(state)
    from core.structure_ui import widget_key
    raw=deepcopy(old)
    raw['work_type']=st.selectbox('Work Type',list(TYPES),index=list(TYPES).index(kind),key=widget_key(state,'work_type'))
    p=TYPES[raw['work_type']]
    st.caption('Suggested scale: '+p['words']+'; '+p['chapters']+'; '+p['chapter_length']+'. These are guidance, not limits.')
    with st.expander('Author length and chapter preferences — optional',expanded=False):
        for key,label in [('author_word_target','Preferred manuscript words'),('author_chapter_target','Preferred chapter count'),('author_chapter_words','Preferred words per chapter')]:
            raw[key]=st.number_input(label,min_value=0,value=int(raw.get(key) or 0),step=1,key=widget_key(state,key))
        st.caption('Zero means unspecified. Any shorter or longer target is allowed. These preferences never resize or regenerate saved chapters.')
    update(state,raw)
    st.caption(p['plot']+' '+p['pacing'])
    st.caption(p['organization'])
    st.caption('Editorial focus: '+p['editorial'])


def chapter_word_target(state):
    kind,raw=settings(state)
    return int(raw.get('author_chapter_words') or {'Novel':3000,'Novella':2000,'Other Prose Fiction':1500}[kind])


def update(state,raw):
    previous_kind,old=settings(state)
    changed=raw.get('work_type',previous_kind)!=previous_kind or any(int(raw.get(k) or 0)!=int(old.get(k) or 0) for k in ('author_word_target','author_chapter_target','author_chapter_words'))
    state['format_template_values']={**(state.get('format_template_values') or {}),FORMAT:deepcopy(raw)}
    if changed and state.get('project_integrity_report'):
        # Retain the old report, but do not approve a new work-type intent with it.
        state['project_integrity_source_signature']=''
        state['project_integrity_status']='STALE'
