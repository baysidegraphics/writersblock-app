"""
WritersBlock Studios Agent
Current Program Intelligence Map
Version: 1.0
Source alignment: app.py + gemini_backend.py uploaded 2026-09-11

This module is the purpose-specific bridge between the WritersBlock Studios
Agent and the CURRENT working WritersBlock application. It records the exact
user-facing labels, internal stage values, development/output behavior, and
backend operation roles found in the supplied application files.

It does not import Streamlit, Supabase, or Gemini and does not modify app.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


PROGRAM_INTELLIGENCE_VERSION = "1.0"
SOURCE_SNAPSHOT_DATE = "2026-09-11"

TRIAL_NAME = "7-Day Limited Free Trial"
TRIAL_EXCLUDED_FEATURES: Tuple[str, ...] = (
    "Manuscript Printout",
    "Saved Projects",
    "Saved Versions",
)

MAX_IMPORT_WORDS = 120_000
ALLOWED_IMPORT_EXTENSIONS: Tuple[str, ...] = (".docx", ".txt")


@dataclass(frozen=True)
class StageSpec:
    step: int
    display_name: str
    internal_stage: str
    export_view: Optional[bool] = None
    trial_display_name: Optional[str] = None


STAGES: Tuple[StageSpec, ...] = (
    StageSpec(1, "Concept Development", "Intake"),
    StageSpec(2, "Scripting", "Sandbox"),
    StageSpec(3, "Plot Architecture", "Plot Architect"),
    StageSpec(4, "Creative Draft", "Drafting Engine"),
    StageSpec(5, "Script Lock", "Isolation Guardrail", export_view=False),
    StageSpec(6, "Script Polish", "Revision Engine"),
    StageSpec(7, "Script Rewrite", "Rewrite Engine"),
    StageSpec(
        8,
        "Final Output",
        "Isolation Guardrail",
        export_view=True,
        trial_display_name="Manuscript Review",
    ),
)

WORKFLOW_STAGE_NAMES: Tuple[str, ...] = tuple(stage.display_name for stage in STAGES)
INTERNAL_STAGE_NAMES: Tuple[str, ...] = tuple(dict.fromkeys(stage.internal_stage for stage in STAGES))


PROJECT_TYPES: Tuple[str, ...] = (
    "Novel / Prose",
    "Short Story",
    "Novella",
    "Audio Book",
    "Screenplay Outline",
    "Stage Play / Dramatic Script",
    "Full Novel Blueprint",
    "Children's Picture Book (32-Page Layout)",
    "YouTube Shorts",
    "Podcast Script",
)

FINAL_OUTPUT_FORMATS: Tuple[str, ...] = (
    "Novel / Prose",
    "Short Story",
    "Novella",
    "Screenplay Outline",
    "Stage Play / Dramatic Script",
    "Audio Book",
    "Children's Picture Book (32-Page Layout)",
    "Full Novel Blueprint",
    "YouTube Shorts",
    "Podcast Script",
)

FINAL_OUTPUT_DISPLAY_LABELS: Dict[str, str] = {
    "Novel / Prose": "Novel / Prose",
    "Short Story": "Short Story",
    "Novella": "Novella",
    "Screenplay Outline": "Screenplay",
    "Stage Play / Dramatic Script": "Stage Play / Dramatic Script",
    "Audio Book": "Audiobook Theatre Production Script",
    "Children's Picture Book (32-Page Layout)": "Children's Picture Book",
    "Full Novel Blueprint": "Full Novel Blueprint",
    "YouTube Shorts": "YouTube Shorts Script",
    "Podcast Script": "Podcast Script",
}

# Current application behavior: Steps 1-7 use a neutral readable development
# document. Step 8 converts a working manuscript into a chosen industry format.
DEVELOPMENT_DOCUMENT_MODE = "Neutral WritersBlock development document"
FINAL_OUTPUT_FORMAT_IS_SELECTABLE = True
FINAL_OUTPUT_PRESERVES_WORKING_MANUSCRIPT = True


DIALOGUE_STYLES: Tuple[str, ...] = (
    "Story-Driven / Automatic",
    "Dialogue Light",
    "Balanced Dialogue",
    "Dialogue Forward",
    "Narration Only / No Dialogue",
)

DIALOGUE_DISPLAY_LABELS: Dict[str, str] = {
    "Story-Driven / Automatic": "Story-Driven / Automatic (Variable)",
    "Dialogue Light": "Dialogue Light (10-20%)",
    "Balanced Dialogue": "Balanced Dialogue (25-40%)",
    "Dialogue Forward": "Dialogue Forward (40-60%)",
    "Narration Only / No Dialogue": "Narration Only / No Dialogue (0%)",
}

DIALOGUE_PERCENT_TARGETS: Dict[str, Optional[Tuple[int, int]]] = {
    "Story-Driven / Automatic": None,
    "Dialogue Light": (10, 20),
    "Balanced Dialogue": (25, 40),
    "Dialogue Forward": (40, 60),
    "Narration Only / No Dialogue": (0, 0),
}


TONE_OPTIONS: Tuple[str, ...] = (
    "Mind-Bending Sci-Fi",
    "Gritty Noir Mystery",
    "Children's: Scripture & Life Lessons",
    "Children's: Whimsical Animal Adventure",
    "Whimsical & Magical Fantasy",
    "Satirical & Sarcastic Comedy",
    "Suspenseful & Tense Thriller",
    "Melancholic & Nostalgic Prose",
    "Epic & Grandiose Lore",
)


AUDIOBOOK_LENGTHS = {
    "15 Minutes": {"min_words": 1800, "max_words": 2250, "default_words": 2000},
    "30 Minutes": {"min_words": 3600, "max_words": 4500, "default_words": 4000},
    "45 Minutes": {"min_words": 5400, "max_words": 6750, "default_words": 6000},
    "60 Minutes": {"min_words": 7200, "max_words": 9000, "default_words": 8000},
}

AUDIOBOOK_CUE_LEVELS: Tuple[str, ...] = (
    "Clean Voices Only",
    "Voices + Minimal SFX",
    "Full Audiobook Theatre Cues",
)

DEFAULT_AUDIOBOOK_LENGTH = "30 Minutes"
DEFAULT_AUDIOBOOK_TARGET_WORDS = 4000
DEFAULT_AUDIOBOOK_CUE_LEVEL = "Voices + Minimal SFX"


PICTURE_BOOK_PROJECT_TYPE = "Children's Picture Book (32-Page Layout)"
PICTURE_BOOK_FINAL_WORD_MIN = 500
PICTURE_BOOK_FINAL_WORD_MAX = 800
PICTURE_BOOK_PLANNING_PAGES = 32
PICTURE_BOOK_SPREADS = 16

PICTURE_BOOK_PAGE_SIZES = {
    "8.5 x 8.5 Square": {
        "page_width": 8.5,
        "page_height": 8.5,
        "spread_aspect": "2 / 1",
    },
    "10 x 8 Landscape": {
        "page_width": 10.0,
        "page_height": 8.0,
        "spread_aspect": "5 / 2",
    },
}
DEFAULT_PICTURE_BOOK_PAGE_SIZE = "8.5 x 8.5 Square"

PICTURE_BOOK_LAYOUT_TEMPLATES: Tuple[str, ...] = (
    "Full Illustration — Text Top",
    "Full Illustration — Text Bottom",
    "Text Left — Illustration Right",
    "Illustration Left — Text Right",
    "Two-Page Illustration — Text Overlay",
    "Spot Illustration — Open Text Area",
)


POLISH_PASSES: Tuple[str, ...] = (
    "Continuity Check",
    "Pacing Check",
    "Tone & Style Check",
    "Character Consistency Check",
    "Scene Expansion Suggestions",
    "Final Polish Pass",
)

REWRITE_MODES: Tuple[str, ...] = (
    "Creative Script Rewrite / Improve Scene",
    "Direct Script Change / Obey My Instructions Exactly",
    "Polish Only / Do Not Change Story",
)

REWRITE_LOCATIONS: Tuple[str, ...] = (
    "Full Manuscript",
    "Scene Beat 1",
    "Scene Beat 2",
    "Scene Beat 3",
    "Scene Beat 4",
)

REWRITE_TARGET_LENGTHS: Tuple[str, ...] = (
    "Keep Current Length",
    "Condense for Tighter Pacing",
    "Expand to 400 Words",
    "Custom Word Count",
)

# Current source-level compatibility notes.
# The decision engine translates these safely when it prepares backend hints;
# app.py and gemini_backend.py themselves remain untouched.
BACKEND_COMPATIBILITY_NOTES: Tuple[str, ...] = (
    "app.py presents 'Direct Script Change / Obey My Instructions Exactly' while "
    "gemini_backend.py tests for 'Direct Story Change / Obey My Instructions Exactly'.",
    "app.py presents 'Condense for Tighter Pacing' and 'Expand to 400 Words', while "
    "gemini_backend.py has no exact branches for those two labels.",
)


# Backend methods actually present in GeminiWriterBackend and their application role.
BACKEND_OPERATIONS = {
    "generate_sandbox_slates": {
        "stage": "Scripting",
        "purpose": "Generate exactly three strategic story paths: A, B, and C.",
    },
    "generate_plot_outline": {
        "stage": "Plot Architecture",
        "purpose": "Generate exactly four linear structural scene beats.",
    },
    "execute_recursive_draft_chunk": {
        "stage": "Creative Draft",
        "purpose": "Draft one beat at a time and return a LORE UPDATE for rolling continuity.",
    },
    "run_revision_pass": {
        "stage": "Script Polish",
        "purpose": "Produce an editorial revision/polish report without replacing the manuscript.",
    },
    "run_rewrite_engine": {
        "stage": "Script Rewrite / Final Output",
        "purpose": "Rewrite selected live manuscript text; also powers Step 8 final-format conversion.",
    },
    "generate_picture_book_layout": {
        "stage": "Final Output",
        "purpose": "Create a 16-spread / 32-page editable picture-book planning layout.",
    },
}


SERIES_CONTINUITY_MODE = "Strict"
SERIES_CONTINUITY_AUTOMATIC = True
SERIES_EARLIER_BOOKS_AUTOMATICALLY_REFERENCED = True


VERSION_STATUS_BY_SOURCE_STAGE = {
    "final_output": ("FINAL", "Manuscript Output"),
    "manuscript_output_final": ("FINAL", "Manuscript Output"),
    "rewrite_engine": ("DRAFT", "Script Rewrite"),
    "script_rewrite_draft": ("DRAFT", "Script Rewrite"),
    "creative_draft": ("DRAFT", "Creative Draft"),
    "script_lock_review": ("DRAFT", "Script Lock"),
    "script_lock_draft": ("DRAFT", "Script Lock"),
    "existing_manuscript_import": ("IMPORTED", "Existing Manuscript"),
}


LEGACY_PROJECT_TYPE_ALIASES = {
    "Novel": "Novel / Prose",
    "Screenplay": "Screenplay Outline",
    "Stage Play": "Stage Play / Dramatic Script",
    "Audiobook": "Audio Book",
    "Audio Short Story — 15–30 min": "Audio Book",
    "Children's Storybook (32-Page Writing Layout)": PICTURE_BOOK_PROJECT_TYPE,
    "Children's Storybook (32-Page Layout)": PICTURE_BOOK_PROJECT_TYPE,
    "Children's Picture Book": PICTURE_BOOK_PROJECT_TYPE,
    "Blueprint": "Full Novel Blueprint",
    "YouTube Short": "YouTube Shorts",
    "Podcast": "Podcast Script",
}

LEGACY_DIALOGUE_STYLE_ALIASES = {
    "Story-Driven/Automatic": "Story-Driven / Automatic",
    "Narration Only/No Dialogue": "Narration Only / No Dialogue",
}


def normalize_project_type(value: str) -> str:
    clean = str(value or "").strip()
    if clean in PROJECT_TYPES:
        return clean
    if clean in LEGACY_PROJECT_TYPE_ALIASES:
        return LEGACY_PROJECT_TYPE_ALIASES[clean]
    raise ValueError(f"Unsupported current WritersBlock project type: {value}")


def normalize_dialogue_style(value: str) -> str:
    clean = str(value or "").strip()
    if clean in DIALOGUE_STYLES:
        return clean
    if clean in LEGACY_DIALOGUE_STYLE_ALIASES:
        return LEGACY_DIALOGUE_STYLE_ALIASES[clean]
    raise ValueError(f"Unsupported current WritersBlock Dialogue Style: {value}")


def stage_spec(step: int) -> StageSpec:
    for spec in STAGES:
        if spec.step == int(step):
            return spec
    raise ValueError(f"Unsupported WritersBlock step: {step}")


def resolve_step(internal_stage: str, *, export_view: Optional[bool] = None) -> StageSpec:
    internal = str(internal_stage or "").strip()
    candidates = [spec for spec in STAGES if spec.internal_stage == internal]
    if not candidates:
        raise ValueError(f"Unsupported WritersBlock internal stage: {internal_stage}")

    if len(candidates) == 1:
        return candidates[0]

    # Script Lock and Final Output intentionally share Isolation Guardrail.
    for spec in candidates:
        if spec.export_view is export_view:
            return spec

    raise ValueError(
        f"Internal stage {internal!r} requires export_view to distinguish Step 5 from Step 8."
    )


def stage_display_name(step: int, *, trial: bool = False) -> str:
    spec = stage_spec(step)
    if trial and spec.trial_display_name:
        return spec.trial_display_name
    return spec.display_name


def final_output_display_name(format_type: str) -> str:
    normalized = normalize_project_type(format_type)
    return FINAL_OUTPUT_DISPLAY_LABELS[normalized]


__all__ = [
    "ALLOWED_IMPORT_EXTENSIONS",
    "AUDIOBOOK_CUE_LEVELS",
    "AUDIOBOOK_LENGTHS",
    "BACKEND_COMPATIBILITY_NOTES",
    "BACKEND_OPERATIONS",
    "DEFAULT_AUDIOBOOK_CUE_LEVEL",
    "DEFAULT_AUDIOBOOK_LENGTH",
    "DEFAULT_AUDIOBOOK_TARGET_WORDS",
    "DEFAULT_PICTURE_BOOK_PAGE_SIZE",
    "DEVELOPMENT_DOCUMENT_MODE",
    "DIALOGUE_DISPLAY_LABELS",
    "DIALOGUE_PERCENT_TARGETS",
    "DIALOGUE_STYLES",
    "FINAL_OUTPUT_DISPLAY_LABELS",
    "FINAL_OUTPUT_FORMATS",
    "FINAL_OUTPUT_FORMAT_IS_SELECTABLE",
    "FINAL_OUTPUT_PRESERVES_WORKING_MANUSCRIPT",
    "INTERNAL_STAGE_NAMES",
    "LEGACY_DIALOGUE_STYLE_ALIASES",
    "LEGACY_PROJECT_TYPE_ALIASES",
    "MAX_IMPORT_WORDS",
    "PICTURE_BOOK_FINAL_WORD_MAX",
    "PICTURE_BOOK_FINAL_WORD_MIN",
    "PICTURE_BOOK_LAYOUT_TEMPLATES",
    "PICTURE_BOOK_PAGE_SIZES",
    "PICTURE_BOOK_PLANNING_PAGES",
    "PICTURE_BOOK_PROJECT_TYPE",
    "PICTURE_BOOK_SPREADS",
    "POLISH_PASSES",
    "PROGRAM_INTELLIGENCE_VERSION",
    "PROJECT_TYPES",
    "REWRITE_LOCATIONS",
    "REWRITE_MODES",
    "REWRITE_TARGET_LENGTHS",
    "SERIES_CONTINUITY_AUTOMATIC",
    "SERIES_CONTINUITY_MODE",
    "SERIES_EARLIER_BOOKS_AUTOMATICALLY_REFERENCED",
    "SOURCE_SNAPSHOT_DATE",
    "STAGES",
    "StageSpec",
    "TONE_OPTIONS",
    "TRIAL_EXCLUDED_FEATURES",
    "TRIAL_NAME",
    "VERSION_STATUS_BY_SOURCE_STAGE",
    "WORKFLOW_STAGE_NAMES",
    "final_output_display_name",
    "normalize_dialogue_style",
    "normalize_project_type",
    "resolve_step",
    "stage_display_name",
    "stage_spec",
]