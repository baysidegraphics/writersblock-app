"""
Central registry for all nine WritersBlock format templates.

The application should store the selected `format_id` in project/session state.
That same value controls both the center-page template and Quill's format rules.
"""

from templates.template_short_story import TEMPLATE as SHORT_STORY_TEMPLATE
from templates.template_novel_prose_novella import TEMPLATE as NOVEL_PROSE_NOVELLA_TEMPLATE
from templates.template_screenplay import TEMPLATE as SCREENPLAY_TEMPLATE
from templates.template_stage_play import TEMPLATE as STAGE_PLAY_TEMPLATE
from templates.template_youtube_shorts import TEMPLATE as YOUTUBE_SHORTS_TEMPLATE
from templates.template_audiobook import TEMPLATE as AUDIOBOOK_TEMPLATE
from templates.template_childrens_picture_book import TEMPLATE as CHILDRENS_PICTURE_BOOK_TEMPLATE
from templates.template_full_novel_blueprint import TEMPLATE as FULL_NOVEL_BLUEPRINT_TEMPLATE
from templates.template_podcast_script import TEMPLATE as PODCAST_SCRIPT_TEMPLATE

from format_quill.quill_short_story import QUILL_INSTRUCTIONS as SHORT_STORY_QUILL
from format_quill.quill_novel_prose_novella import QUILL_INSTRUCTIONS as NOVEL_PROSE_NOVELLA_QUILL
from format_quill.quill_screenplay import QUILL_INSTRUCTIONS as SCREENPLAY_QUILL
from format_quill.quill_stage_play import QUILL_INSTRUCTIONS as STAGE_PLAY_QUILL
from format_quill.quill_youtube_shorts import QUILL_INSTRUCTIONS as YOUTUBE_SHORTS_QUILL
from format_quill.quill_audiobook import QUILL_INSTRUCTIONS as AUDIOBOOK_QUILL
from format_quill.quill_childrens_picture_book import QUILL_INSTRUCTIONS as CHILDRENS_PICTURE_BOOK_QUILL
from format_quill.quill_full_novel_blueprint import QUILL_INSTRUCTIONS as FULL_NOVEL_BLUEPRINT_QUILL
from format_quill.quill_podcast_script import QUILL_INSTRUCTIONS as PODCAST_SCRIPT_QUILL

FORMAT_REGISTRY = {
    'short_story': (SHORT_STORY_TEMPLATE, SHORT_STORY_QUILL),
    'novel_prose_novella': (NOVEL_PROSE_NOVELLA_TEMPLATE, NOVEL_PROSE_NOVELLA_QUILL),
    'screenplay': (SCREENPLAY_TEMPLATE, SCREENPLAY_QUILL),
    'stage_play': (STAGE_PLAY_TEMPLATE, STAGE_PLAY_QUILL),
    'youtube_shorts': (YOUTUBE_SHORTS_TEMPLATE, YOUTUBE_SHORTS_QUILL),
    'audiobook': (AUDIOBOOK_TEMPLATE, AUDIOBOOK_QUILL),
    'childrens_picture_book': (CHILDRENS_PICTURE_BOOK_TEMPLATE, CHILDRENS_PICTURE_BOOK_QUILL),
    'full_novel_blueprint': (FULL_NOVEL_BLUEPRINT_TEMPLATE, FULL_NOVEL_BLUEPRINT_QUILL),
    'podcast_script': (PODCAST_SCRIPT_TEMPLATE, PODCAST_SCRIPT_QUILL),
}

FORMAT_OPTIONS = [
    ('short_story', 'Short Story'),
    ('novel_prose_novella', 'Novel / Prose / Novella'),
    ('screenplay', 'Screenplay'),
    ('stage_play', 'Stage Play / Dramatic Script'),
    ('youtube_shorts', 'YouTube Shorts'),
    ('audiobook', 'Audiobook'),
    ('childrens_picture_book', 'Children’s Picture Book'),
    ('full_novel_blueprint', 'Full Novel Blueprint'),
    ('podcast_script', 'Podcast Script'),
]

def get_template(format_id: str):
    return FORMAT_REGISTRY[format_id][0]

def get_quill_instructions(format_id: str):
    return FORMAT_REGISTRY[format_id][1]

def get_format_display_name(format_id: str):
    return FORMAT_REGISTRY[format_id][0]["display_name"]
