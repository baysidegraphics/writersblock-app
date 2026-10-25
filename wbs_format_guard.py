"""WritersBlock format identity and project-state isolation.

Pure helpers: no Streamlit, database, or AI dependencies. Every persisted
project has one canonical format ID. Unknown IDs must never be silently
converted to a default on saved-project load.
"""

from __future__ import annotations

from copy import deepcopy
import re

FORMAT_LEGACY = {
    "short_story": "Short Story",
    "novel_prose_novella": "Novel / Prose",
    "screenplay": "Screenplay Outline",
    "stage_play": "Stage Play / Dramatic Script",
    "youtube_shorts": "YouTube Shorts",
    "audiobook": "Audio Book",
    "childrens_picture_book": "Children's Picture Book (32-Page Layout)",
    "full_novel_blueprint": "Full Novel Blueprint",
    "podcast_script": "Podcast Script",
    "standard_manuscript": "Standard Manuscript",
}

LEGACY_FORMAT_IDS = {name: key for key, name in FORMAT_LEGACY.items()}
LEGACY_FORMAT_IDS.update({
    "Novella": "novel_prose_novella",
    "Screenplay": "screenplay",
    "Stage Play": "stage_play",
    "Audio Short Story — 15–30 min": "audiobook",
    "Children's Storybook (32-Page Writing Layout)": "childrens_picture_book",
    "Children's Storybook (32-Page Layout)": "childrens_picture_book",
    "Children's Picture Book": "childrens_picture_book",
})

# Reused for loads from older project-session snapshots that omitted newer keys.
# No keys connected to access, licensing, authentication, or secrets belong here.
PROJECT_RESTORE_DEFAULTS = {
    "_wbs_picture_book_budget_age": '',
    "picture_book_word_target": None,
    "concept_change_areas": [],
    "project_version_name": 'Original',
    "quill_starting_direction": '',
    "saved_version_source_word_count": 0,
    "saved_version_source_name": '',
    "saved_version_source_text": '',
    "version_source_mode": 'Custom Plot Line',
    "project_stage": "Intake",
    "story_seed": "",
    "wbs_project_original_concept": "",
    "starting_source_mode": "Story Idea",
    "imported_source_text": "",
    "imported_source_name": "",
    "imported_source_word_count": 0,
    "project_title": "",
    "project_scope": "Standalone Book",
    "series_key": "",
    "series_name": "",
    "series_book_number": 1,
    "series_continuity_mode": "Strict",
    "series_reference_ids": [],
    "series_canon_notes": "",
    "series_selection_signature": "",
    "active_format_id": "",
    "format_template_values": {},
    "format_type": "",
    "dialogue_style": "Story-Driven / Automatic",
    "audiobook_length": "30 Minutes",
    "audiobook_target_word_count": 4000,
    "audiobook_production_script": "",
    "audiobook_production_source_signature": "",
    "audiobook_production_cue_level": "Voices + Minimal SFX",
    "audiobook_production_preview_id": 0,
    "tone_style": "",
    "author_style": "",
    "sandbox_slates": None,
    "chosen_option": None,
    "chosen_option_text": None,
    "plot_outline": None,
    "current_draft_output": "",
    "rolling_lore_book": "",
    "completed_beats": [],
    "scene_blocks": {},
    "current_processing_beat": 1,
    "manuscript_version": 0,
    "current_manuscript_save_status": "",
    "current_manuscript_save_stage": "",
    "current_manuscript_save_version": 0,
    "rewritten_manuscript": "",
    "rewrite_applied_message": "",
    "rewrite_preview_id": 0,
    "rewrite_target_length": "Keep Current Length",
    "revision_report": "",
    "project_integrity_report": "",
    "project_integrity_source_signature": "",
    "project_integrity_status": "",
    "export_view": False,
    "final_output_format": "",
    "final_output_text": "",
    "final_output_source_signature": "",
    "final_output_preview_id": 0,
    "final_output_saved_signature": "",
    "picture_book_layout_spreads": [],
    "picture_book_layout_source_signature": "",
    "picture_book_layout_preview_id": 0,
    "picture_book_page_size": "",
    "current_project_id": None,
}


class SavedFormatError(ValueError):
    """Saved project's format identity is missing or invalid."""


def require_format_id(format_id: object) -> str:
    """Validate explicit canonical IDs without silently choosing a different one."""
    if not isinstance(format_id, str) or format_id not in FORMAT_LEGACY:
        raise SavedFormatError(f"Unrecognized writing format ID: {format_id!r}")
    return format_id


def resolve_saved_format(snapshot: dict) -> str:
    """Prefer persisted canonical ID. Migrate only a recognized legacy label.

    A present but invalid active_format_id is an error, NOT permission to fall
    back to a stale format_type or the current session's format.
    """
    if not isinstance(snapshot, dict):
        raise SavedFormatError("Saved project snapshot is invalid.")
    if "active_format_id" in snapshot and snapshot["active_format_id"] not in (None, ""):
        return require_format_id(snapshot["active_format_id"])
    legacy_label = snapshot.get("format_type")
    fmt = LEGACY_FORMAT_IDS.get(legacy_label) if isinstance(legacy_label, str) else None
    if fmt is None:
        raise SavedFormatError("Saved project has no recognized writing format; load cancelled.")
    return fmt


def prepare_saved_snapshot(snapshot: dict, row_project_id: object = None,
                           selected_format_id: str | None = None) -> dict:
    """Return validated, normalized, independent project state; never mutate inputs."""
    fmt = resolve_saved_format(snapshot)
    snapshot_pid = snapshot.get("current_project_id")
    if row_project_id and snapshot_pid and str(row_project_id) != str(snapshot_pid):
        raise SavedFormatError("Project-session record does not match its project ID.")
    if selected_format_id is not None:
        fmt = require_format_id(selected_format_id)
    normalized = {key: deepcopy(value) for key, value in PROJECT_RESTORE_DEFAULTS.items()}
    for key in PROJECT_RESTORE_DEFAULTS:
        if key in snapshot:
            normalized[key] = deepcopy(snapshot[key])
    normalized["active_format_id"] = fmt
    normalized["format_type"] = FORMAT_LEGACY[fmt]
    normalized["current_project_id"] = row_project_id or snapshot_pid
    all_values = normalized.get("format_template_values")
    if not isinstance(all_values, dict):
        all_values = {}
    normalized["format_template_values"] = {
        k: deepcopy(v) for k, v in all_values.items()
        if k == fmt and isinstance(v, dict)
    }
    return normalized


def validate_format_for_save(format_id: str, locked_id: str | None = None) -> str:
    fmt = require_format_id(format_id)
    if locked_id and fmt != require_format_id(locked_id):
        raise SavedFormatError(
            "This saved project has a different writing format. "
            "Start a new project to use another format."
        )
    return fmt


def project_format_widget_key(project_id: object, draft_scope: str, fmt: str, field: str) -> str:
    """Namespace widgets by project AND format so revisions cannot bleed across."""
    require_format_id(fmt)
    source = str(project_id) if project_id else "new_" + str(draft_scope)
    if not source or source == "new_":
        raise ValueError("An unsaved project requires a unique draft scope.")
    safe_source = re.sub(r"[^a-zA-Z0-9_-]", "_", source)
    return f"format_field_{safe_source}_{fmt}_{field}"
