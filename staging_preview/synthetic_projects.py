"""Deterministic, disposable writing fixtures; no app startup or credential reads."""
import ast
import copy
from io import BytesIO
import json
from importlib import import_module
from offline_app import APP_TREE, environment
from test_new_formats import valid_environment, BIO, EDU
from core.saved_scene_state import remember_saved_snapshot
from core.text import get_text_signature
TITLES = {'short_story': 'The Lantern Keeper', 'novel_prose_novella': 'The River Observatory', 'screenplay': 'Last Train to Harbor', 'stage_play': 'The Empty Chair', 'youtube_shorts': 'One Seed in Sixty Seconds', 'audiobook': 'Letters from the Lighthouse', 'childrens_picture_book': 'Mila Shares the Moon', 'full_novel_blueprint': 'The Cartographers Promise', 'podcast_script': 'Neighborhood Science Hour', 'standard_manuscript': 'The Orchard Ledger', BIO: 'A Garden of Remembered Days', EDU: 'Nia Notices and Shares'}

def project(fmt):
    saved, st, db, context = valid_environment(fmt) if fmt in (BIO, EDU) else environment(fmt, scenes=6 if fmt == 'novel_prose_novella' else 4)
    blocks = {}
    actions = ['finds a weathered notebook', 'asks a neighbor for help', 'discovers why the garden gate was locked', 'opens the garden for everyone', 'compares the records with a map', 'plants a tree beside the restored path']
    for n in range(1, len(saved['scene_blocks']) + 1):
        prose = f'Mila {actions[n - 1]}. She listens carefully before deciding what to do. '
        prose += f'The notebook records her observation number {n}; every detail matters.'
        if fmt == 'screenplay':
            prose = f'INT. GARDEN HOUSE - DAY\n{prose}\nMILA\nWe can solve this together.'
        elif fmt == 'stage_play':
            prose = f'SCENE {n}\n(Mila sets down the notebook.)\nMILA\n{prose}'
        elif fmt == 'audiobook':
            prose = f'NARRATOR:\n{prose}\n[PAUSE: two seconds]\nMILA:\nLet us look again.'
        elif fmt == 'podcast_script':
            prose = f'HOST:\n{prose}\n[SFX: garden birds]\nWhat would you notice first?'
        elif fmt == 'youtube_shorts':
            prose = f'{(n - 1) * 15:02d}:00\nVOICEOVER: {prose}\nON SCREEN: Look closely.'
        elif fmt == 'full_novel_blueprint':
            prose = f'CHAPTER {n}\nObjective: {prose}\nConsequence: Mila must choose who to trust.'
        elif fmt in ('childrens_picture_book', EDU):
            prose = f'Nia sees a little seed. She gives her friend a turn. They look, wait, and draw what they see. This is learning moment {n}.'
        elif fmt == BIO:
            prose = f'In my supplied journal I described the garden on day {n}. I remember asking my neighbor for help. The exact weather is uncertain; this is my recollection.'
        blocks[str(n)] = prose
    title = 'SYNTHETIC - ' + TITLES[fmt]
    seed = f'{TITLES[fmt]} follows a careful observer learning how evidence and cooperation can restore a community garden.'
    plot = f'{TITLES[fmt]}: Mila discovers a notebook, tests its clues with a neighbor, and opens the garden after resolving the missing key.'
    saved.update(project_title=title, dialogue_style='Story-Driven / Automatic', story_seed=seed, saved_quill_concept=seed, chosen_option_text=plot, sandbox_slates={'Option A': 'A lost map leads home.', 'Option B': 'A neighbor shares a secret.', 'Option C': plot, 'is_fallback': False}, scene_blocks=blocks, current_draft_output='\n\n'.join(blocks.values()))
    saved['plot_outline'] = '\n'.join((f'[BEAT {n}]\n[SCENE TITLE]: Garden {n}\n[SCENE DETAILS]: {text}\n[CORE OBJECTIVE]: Follow the evidence.' for n, text in blocks.items()))
    saved['project_integrity_source_signature'] = get_text_signature(saved['current_draft_output'])
    st.session_state.update(copy.deepcopy(saved))
    st.session_state['_wbs_loaded_project_title'] = title
    st.session_state['_wbs_stage3_saved_outline_baseline'] = saved['plot_outline']
    db.rows['writersblock_projects'][0]['project_title'] = title
    db.rows['writersblock_project_drafts'][0]['draft_content'] = json.dumps(saved, ensure_ascii=False)
    db.rows['writersblock_manuscript_versions'][0]['manuscript_content'] = saved['current_draft_output']
    remember_saved_snapshot(st.session_state, saved, 'own', 'revision-7', 'alice')
    return (saved, st, db, context)

def install_app_definitions(context, names):
    nodes = [n for n in APP_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    missing = set(names) - {n.name for n in nodes}
    if missing:
        raise AssertionError(f'Missing real app definitions: {missing}')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'offline-real-app-services', 'exec'), context)

def install_exports(context):
    """Execute original export functions with real python-docx, never app startup."""
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_SECTION
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    context.update(Document=Document, Inches=Inches, Pt=Pt, WD_ALIGN_PARAGRAPH=WD_ALIGN_PARAGRAPH, WD_SECTION=WD_SECTION, OxmlElement=OxmlElement, qn=qn, BytesIO=BytesIO)
    constants = {'FINAL_OUTPUT_FORMAT_OPTIONS', 'FINAL_OUTPUT_DISPLAY_LABELS', 'PICTURE_BOOK_PAGE_SIZES', 'PICTURE_BOOK_LAYOUT_TEMPLATES', 'DEFAULT_PICTURE_BOOK_PAGE_SIZE'}
    for node in APP_TREE.body:
        if isinstance(node, ast.Assign) and any((isinstance(t, ast.Name) and t.id in constants for t in node.targets)):
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'offline-export-constants', 'exec'), context)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id == 'FINAL_OUTPUT_FORMAT_OPTIONS') and (f.attr == 'extend'):
                exec(compile(ast.Module(body=[node], type_ignores=[]), 'offline-export-extensions', 'exec'), context)
    install_app_definitions(context, {'get_final_output_format', 'get_automatic_output_label', 'build_final_output_docx_bytes', 'build_standard_manuscript_docx_bytes', 'build_audiobook_production_docx_bytes', 'build_picture_book_layout_docx_bytes', 'build_picture_book_spreads_locally', 'normalize_picture_book_spreads', 'get_picture_book_page_size_spec', '_set_run_font', '_set_style_font', '_add_page_field', '_restart_section_page_numbering', '_configure_top_right_page_numbers', '_configure_bottom_center_page_numbers', '_add_simple_title_page', '_new_body_section', '_is_scene_break'})

def export_project(snapshot, context):
    fmt = snapshot['active_format_id']
    if fmt in (BIO, EDU):
        exports = import_module('formats.' + fmt + '.exports')
        return (exports.build_docx(snapshot), exports.build_text(snapshot))
    text = snapshot['current_draft_output']
    if fmt == 'childrens_picture_book':
        spreads = context['build_picture_book_spreads_locally'](text)
        docx = context['build_picture_book_layout_docx_bytes'](snapshot['project_title'], spreads)
    else:
        docx = context['build_final_output_docx_bytes'](snapshot['project_title'], text, context['get_final_output_format']())
    return (docx, text)
