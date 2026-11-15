"""Installed WBS control knowledge. Read-only directions, never application actions."""
from pathlib import Path
from functools import lru_cache
import ast,re
ROOT=Path(__file__).resolve().parents[1]

@lru_cache(maxsize=64)
def labels(path,stamp):
    try:tree=ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,SyntaxError):return []
    result=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'button','download_button','selectbox','checkbox','text_input','text_area','file_uploader','number_input','radio','expander','form_submit_button'} and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
            result.append(node.args[0].value)
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value=='label' and isinstance(value,ast.Constant) and isinstance(value.value,str):result.append(value.value)
    return sorted(set(result))

def catalog(state):
    fmt=state['active_format_id'];result={}
    from core.inline_images import SUPPORTED
    common=['structure_ui.py','publisher_assessment.py','publication_layout.py']
    if fmt in SUPPORTED:common+=['image_editor.py','image_placement.py']
    if fmt in {'childrens_picture_book','childrens_interactive_educational'}:common+=['children_publication.py','children_arrangements.py']
    if fmt in {'biography_memoir','childrens_interactive_educational'}:common+=['extended_concept.py']
    paths=list((ROOT/'formats'/fmt).glob('*.py'))+[ROOT/'core'/n for n in common]+[ROOT/'quill/proposal_controls.py']
    for p in paths:
        if p.is_file():result[str(p.relative_to(ROOT))]=labels(str(p),p.stat().st_mtime_ns)
    return result

def guides(state):
    from .modular_context import identity,build
    from core.manuscript_structure import profile
    from core.inline_images import SUPPORTED
    from core.image_pdf import available
    i=identity(state);p=profile(i['format_id']);unit=p['unit'];plural=p['plural']
    image=('1. Open Stage 3 — Scene Scripting. Choose the '+unit.lower()+'. 2. Enable Edit with images. Put the caret at the insertion point and click [Insert Image], or open [Insert Image] — upload and placement. 3. Upload JPG, PNG or WEBP, select Small (25%), Medium (40%) or Large (60%) of usable page width, and Left/Center/Right. 4. Click Place Uploaded Image. Save the current text unit to the current revision. Left/right text wraps on the opposite side; centered images go between paragraphs. Use Update / Reanchor Image or Remove Image to adjust a placement. These do not create a new version by themselves.' if i['format_id'] in SUPPORTED else 'Image insertion is not enabled for this format. Its production/manuscript requirements and protected writing workflow are preserved; do not look for an Insert Image control here.')
    if i['format_id']=='childrens_picture_book':image='Open Stage 3, expand [Insert Image] — edit an illustrated story page, and choose Image editing page. '+image
    export='1. Save the manuscript and complete Stage 4 Editorial Review and its current Integrity Report. 2. Stage 5 is optional: use Skip Optional Assessment — Final Manuscript. 3. In Stage 6 download the approved DOCX or text. Adjust layout using the format’s available layout controls and save it before downloading.'
    if i['format_id'] in SUPPORTED:export+=(' Download Illustrated PDF is also available in this installed environment.' if available() else ' PDF export requires the installed reportlab dependency; DOCX remains available. Never attach billing or install services through Quill.')
    else:export+=' There is no Illustrated PDF control for this format.'
    result={
      'stage':'Use the numbered stage buttons in the sidebar. Stage 1 Concept Development; Stage 2 Plot Architecture; Stage 3 Scene Scripting; Stage 4 Editorial Review; optional Stage 5 Publisher Assessment; Stage 6 Final Manuscript. Required save/approval checks cannot be bypassed. Saving/approving a stage advances automatically; active navigation buttons are red.',
      'plot':'Open Stage 2 — Plot Architecture using the sidebar. Review the existing Plot A/B/C choices and the selected approved plot. Use the available author plot/outline editor, save and explicitly approve your intended selection. Quill can suggest changes but cannot replace the approved plot. Do not regenerate approved writing unless that is explicitly your request.',
      'image':image,
      'save':'Use the current stage’s Save to Current Revision control (the exact label depends on the format). It updates the selected V-number. Save And/Or Continue To Next Stage saves Concept Development and advances. A routine save is not Save As New Version.',
      'version':'To create a separate manuscript revision, use the existing Save As New Version / Save Project Changes As A New Version controls. In the picture-book story editor use Save Story As New Version and its optional version name. In Concept Development expand Save Project Changes As A New Version where present. Keep the original saved version; choose that revision in Saved Projects to reopen it. Quill never creates a version from a chat message.',
      'edit':'Open Stage 3 — Scene Scripting. Select the '+(p['group'].lower()+' then ' if p['group'] else '')+unit.lower()+'. Edit its text and use the current-revision save button. Organization controls plan '+plural.lower()+'; they do not regenerate source text. Existing stable text IDs preserve content when organization changes. Quill Copy to Draft creates an editable proposal, not a saved manuscript replacement.',
      'integrity':'Open Stage 4 and click Run Project Integrity Report. Save all text first. Approval remains blocked if the report is missing, failed, stale, inconclusive or cannot be saved. Accept the title, complete saved manuscript and current Integrity Report using the visible confirmations, then approve/save. Current report status: '+str(state.get('project_integrity_status') or 'not reviewed')+'. If your question concerns an error, provide the visible error text; Quill cannot bypass the check.',
      'export':export,
      'quill':'Quill is Your Frontline Editor-in-Chief. Type in Message Quill and press ENTER or click SEND. Operational questions use installed program knowledge without a model call. Editorial/creative requests require the configured writing service. Expand Full Quill Response to read all returned text. Copy to Draft opens an editable Quill proposal. Revise uses your instructions to generate a new proposal; it never changes approved writing. Use the existing manuscript editor and save controls to apply author-approved text.',
      'voice':'Use the speaker toggle to enable/disable Quill read-aloud and the Male/Female Quill Voice options. Voice uses local Kokoro when its resources are available. If unavailable, text responses remain accessible. The > button collapses Quill; it does not navigate projects.',
      'layout':'Choose the available Publication layout in Stage 1 or Stage 6. Novel/Novella has Traditional, Illustrated Fiction and Story-Adaptive options; Work Type is separate. Children’s formats have Page Size and illustrated layout choices with page-specific overrides. Save layout changes to the current revision. Layout controls do not rewrite the manuscript.',
      'page_turn':'Only formats supporting explicit page turns expose that editor. For Children’s Picture Book type [Page Turn] directly into story text; it is highlighted red. It creates the next page boundary and survives saves/revisions. Downstream output uses real page breaks rather than the marker. Do not add page-turn handling to unrelated formats.',
      'concept':'In Stage 1 set the Project Title / Revision, Project Relationship and the format-specific development fields. Save And/Or Continue To Next Stage preserves the setup and moves to Plot Architecture. Novel/Novella Work Type controls advisory scale and editorial guidance; author targets can be shorter or longer. Biography requires source/timeline context; Educational requires age, subject and learning activities. Uploaded source import keeps its existing file/resource checks.',
      'publisher':'Stage 5 Publisher Assessment is optional. Generate And Save Publisher Assessment creates an assessment for the current saved/approved revision. Skip Optional Assessment — Final Manuscript goes to Stage 6. This does not authorize rewriting text.',
      'troubleshoot':'First check the project title and revision, save pending edits, and read the visible error or missing prerequisite. For integrity failures rerun the report only after saving. For image anchor errors use Update / Reanchor Image at the intended point; uploaded data is retained. For provider errors Quill shows a safe error category and does not retry automatically. Reopen the saved revision only when you want to discard or separately preserve pending working edits.'}
    fmt=i['format_id']
    if fmt=='novel_prose_novella':result['layout']='In Stage 1 choose Publication layout: Traditional Novel, Illustrated Fiction or Story-Adaptive Illustrations. Use the independent Work Type selection for Novel, Novella or Other Prose Fiction. Author targets are advisory; no writing is resized. In Stage 4/6 use Image positions and captions for chapter-specific image spaces; save them before export.'
    elif fmt.startswith('childrens_'):result['layout']='Use Page Size in Stage 1 or Final Manuscript, and the five illustrated layout choices including Story-Adaptive. Per-page layout overrides preserve saved story/page-turns and image metadata. Save the layout to the current revision before downloading.'
    elif fmt=='biography_memoir':result['layout']='Stage 1 Publication layout offers Traditional Biography, Photo-rich Memoir or Historical-documentary. Stage 6 Image positions and captions sets chapter image reservations. Keep source references, captions and factual disclaimer; save layout changes before export.'
    elif fmt=='youtube_shorts':result['layout']='Use the Stage 1 Production Script or Production Script with Storyboards layout. Stage 6 image positions are per segment. Timed segments remain intact; this is a production script, not a children’s page layout.'
    else:result['layout']='This format uses its registered professional manuscript/production layout. Children’s page-size and illustrated arrangement controls are not provided for this format. Use Stage 6 to preview/download the approved output; applicable image reservations appear only where supported.'
    if state.get('_staging_context'):
        result['save']='This is isolated synthetic staging. Save synthetic checkpoint updates the selected V-number. Stage-specific text saves also preserve the current revision. No production records are involved.'
        result['version']='In this isolated preview, click Create synthetic V8 branch to create an explicit new synthetic revision; use Synthetic saved revision and Reload synthetic saved revision to reopen it. Save synthetic checkpoint performs a routine save without creating a new version.'
    return result

def knowledge(state):
    return '\n'.join(k.upper()+': '+v for k,v in guides(state).items())+'\nInstalled control labels for this format (some are conditional on stage, approval and options; do not claim they are currently visible):\n'+str(catalog(state))

def answer(state,question):
    q=question.lower();g=guides(state)
    patterns=[('version',r'version|revision|v-number'),('image',r'(insert|add|place|attach|put).{0,18}(image|picture|photo)|upload.{0,18}(image|picture)|image size|image position|text wrap'),('page_turn',r'page.?turn'),('integrity',r'integrity|approval.{0,12}block|blocked.{0,12}approval'),('publisher',r'publisher|market readiness'),('export',r'export|download|print|docx|pdf'),('voice',r'voice|speaker|read.aloud|mute'),('quill',r'copy to draft|\brev[ie]se\b|quill.{0,18}(button|response|expand)|send button'),('plot',r'(change|select|approve|edit|choose).{0,25}plot|plot.{0,20}(choice|selection|change)'),('save',r'\bsav(e|ing)\b'),('edit',r'edit.{0,20}(manuscript|scene|chapter|page|unit)|chapter organization'),('layout',r'layout|page size|illustrat|work type'),('stage',r'\bstage\b|navigat|where.{0,12}(click|go)|workflow'),('concept',r'concept|project title|relationship|starting point'),('troubleshoot',r'error|not working|missing|troubleshoot|unexpected')]
    operational=bool(re.search(r'\b(how|where|why|what|explain|help|button|control|setting|can i|can you|tell me|show me)\b',q))
    if not operational:return None
    topics=[topic for topic,pattern in patterns if re.search(pattern,q)]
    if topics:return '\n\n'.join(g[topic] for topic in dict.fromkeys(topics))
    # Exact installed labels can be explained without inventing operations.
    matches=[label for values in catalog(state).values() for label in values if len(label)>3 and label.lower() in q]
    if matches and re.search(r'\b(button|control|dropdown|drop-down|setting|option|field|menu|click)\b',q):return 'Installed control: '+matches[0]+'. '+g['troubleshoot']+'\nAsk about saving, editing, plot selection, image insertion, integrity or export for its exact workflow.'
    return None
