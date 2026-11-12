# WBS_INDUSTRY_STANDARD_FINAL_DOCX_2026_09_09
# WBS_FINAL_OUTPUT_CONVERSION_ENGINE_2026_09_09
# WBS_NEUTRAL_DEVELOPMENT_DOCUMENT_2026_09_09
# WBS_PICTURE_BOOK_FINAL_WARNING_500_800_2026_09_09
# WBS_DIALOGUE_PERCENT_TARGETS_2026_09_09
# WBS_COMPACT_VERSION_LABELS_2026_09_08
# WBS_PROJECT_NAME_FIRST_VERSION_INCREMENT_2026_09_08
# WBS_HIDE_STREAMLIT_200MB_2026_09_08
# WBS_EXISTING_DRAFT_120K_LIMIT_2026_09_08
# WBS_EXISTING_DRAFT_INTAKE_API_WARNING_2026_09_08
# WBS_LICENSED_IMPORT_HIDE_2026_09_08
# WBS_INLINE_VERSION_MANAGER_REMOVED_2026_09_08
# WBS_DRAFT_FINAL_OUTPUT_LABELS_2026_09_08
# WBS_STAGE5_DRAFT_SAVE_DOWNLOAD_FLOW_2026_09_08
# WRITERSBLOCK_STUDIOS_WRITER_EDITION_COMMERCIAL_ONE_TIME_LICENSE_0827
# WBS_PROJECT_RENAME_VERIFIED_2026_09_06
# WBS_DIALOGUE_STYLE_SCRIPTING_2026_09_07
# WBS_DIALOGUE_PLOT_DRAFT_2026_09_07
# WBS_DIALOGUE_REWRITE_2026_09_07
# Writing-only build: story, script, and manuscript development.
import streamlit as st
import re
import time
import os
import sys
import json
import html
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
import hashlib
import zipfile
import uuid
from wbs_format_guard import (
    SavedFormatError, FORMAT_LEGACY, prepare_saved_snapshot,
    validate_format_for_save, project_format_widget_key,
)
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from gemini_backend import GeminiWriterBackend
from core.authentication import session_controller, AuthenticationError
from core.auth_ui import sync_access_state, render_auth_access
from quill import render_quill_for_current_stage
from core.workflow_runtime import active_scene_functions

def wbs_ss_blocks(source):
    return active_scene_functions(st.session_state).completed_blocks(source)

def wbs_novel_blocks(source):
    return active_scene_functions(st.session_state).completed_blocks(source)

def wbs_ss_storyline(source):
    return active_scene_functions(st.session_state).manuscript(source)

def wbs_novel_manuscript(source):
    return active_scene_functions(st.session_state).manuscript(source)

def wbs_ss_outline_parts(source):
    return active_scene_functions(st.session_state).outline_parts(source)

from template_registry import (
    FORMAT_OPTIONS as WBS_FORMAT_OPTIONS,
    get_template as get_wbs_format_template,
    get_quill_instructions as get_wbs_quill_instructions,
    get_format_display_name as get_wbs_format_display_name,
)

# ==========================================
# WRITERSBLOCK MODEL INTEGRATION
# ==========================================
# Production/deployment layout: the four WBS Model runtime modules live beside app.py.
# Development fallback: if they are not local, also check the separate Agent folder.
APP_FOLDER = Path(__file__).resolve().parent
WBS_AGENT_FOLDER = APP_FOLDER.parent / "WritersBlock Studio-Agent"

for _wbs_model_path in (APP_FOLDER, WBS_AGENT_FOLDER):
    if str(_wbs_model_path) not in sys.path:
        sys.path.insert(0, str(_wbs_model_path))

try:
    from wbs_streamlit_adapter import create_bridge_adapter
    WBS_MODEL_IMPORT_ERROR = ""
except Exception as exc:
    create_bridge_adapter = None
    WBS_MODEL_IMPORT_ERROR = str(exc)


WRITER_EDITION_RETAIL_USD = 132
WRITER_EDITION_REGULAR_USD = 99
WRITER_EDITION_FOUNDING_50_USD = 69
WRITER_EDITION_RETAIL_LABEL = "$132 retail"
WRITER_EDITION_REGULAR_LABEL = "$99 one-time"
WRITER_EDITION_FOUNDING_50_LABEL = "$69 one-time"
WRITER_EDITION_PRICE_LABEL = WRITER_EDITION_REGULAR_LABEL
TRIAL_DAYS = 7
FOUNDING_50_ACTIVE = True
PURCHASE_URL = ""  # Private staging: real checkout disabled.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

from core.persistence import OwnedClient
from core.saved_scene_state import observe_saved_rows
from sidebar.summary import refresh_scene_total_views
_wbs_scene_total_views = []

def _observe_saved_project_rows(table, operation, rows, owner):
    if observe_saved_rows(st.session_state, table, operation, rows, owner):
        refresh_scene_total_views(globals())

try:
    _wbs_auth = session_controller(st.session_state, SUPABASE_URL, SUPABASE_KEY)
except AuthenticationError as _wbs_auth_configuration_error:
    st.error(str(_wbs_auth_configuration_error))
    st.stop()
supabase = _wbs_auth.owned_client(_observe_saved_project_rows, checkpoint_state=st.session_state)

# ==========================================
# AFFITOR AFFILIATE LEAD ATTRIBUTION
# ==========================================
# The public WritersBlock website passes the first-party Affitor click ID into
# the Streamlit app as ?affitor_click_id=... . Keep it in session state across
# Streamlit reruns, then bind it to the stable WritersBlock user ID after signup.
AFFITOR_LEAD_ENDPOINT = "https://example.invalid/staging-affiliate-disabled"


def _clean_affitor_click_id(value):
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    clean = str(value or "").strip()
    if not clean or len(clean) > 200:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", clean):
        return ""
    return clean


def capture_affitor_click_id():
    """Capture the referral ID handed off from writersblockstudios.com."""
    try:
        incoming = st.query_params.get("affitor_click_id", "")
    except Exception:
        incoming = ""

    click_id = _clean_affitor_click_id(incoming)
    if click_id:
        st.session_state["affitor_click_id"] = click_id

    return _clean_affitor_click_id(st.session_state.get("affitor_click_id", ""))


def build_affitor_purchase_url(base_url):
    """Attach the Affitor click ID to Stripe Payment Links for webhook attribution."""
    click_id = capture_affitor_click_id()
    if not click_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", click_id):
        return base_url

    try:
        parts = urllib.parse.urlsplit(base_url)
        query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        query["client_reference_id"] = click_id
        return urllib.parse.urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            urllib.parse.urlencode(query),
            parts.fragment,
        ))
    except Exception:
        return base_url


def _get_affitor_api_key():
    """Read the private Affitor token only from server-side secrets/environment."""
    try:
        secret_value = st.secrets.get("AFFITOR_API_KEY", "")
    except Exception:
        secret_value = ""
    return str(secret_value or os.getenv("AFFITOR_API_KEY", "") or "").strip()


def track_affitor_lead(user_row, email):
    """Best-effort server-side lead attribution; never blocks WBS access."""
    if not isinstance(user_row, dict):
        return False

    customer_key = str(user_row.get("id") or "").strip()
    click_id = capture_affitor_click_id()
    clean_email = str(email or user_row.get("email") or "").strip().lower()
    api_key = _get_affitor_api_key()

    if not customer_key or not click_id or not api_key:
        return False

    tracking_key = f"{click_id}:{customer_key}"
    if st.session_state.get("affitor_lead_tracked_key") == tracking_key:
        return True

    payload = {
        "click_id": click_id,
        "customer_key": customer_key,
        "email": clean_email,
    }

    request = urllib.request.Request(
        AFFITOR_LEAD_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw_body = response.read().decode("utf-8", errors="replace")

        response_data = json.loads(raw_body) if raw_body.strip() else {}
        if 200 <= status < 300 and response_data.get("success") is not False:
            st.session_state["affitor_lead_tracked_key"] = tracking_key
            return True

    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Affitor lead tracking skipped: {exc}")
    except Exception as exc:
        print(f"Affitor lead tracking skipped: {exc}")

    return False


# Capture once on entry; Streamlit session state preserves it during reruns.
capture_affitor_click_id()
def get_current_user_id():
    # Existing ownership ids remain stable, but originate only from the
    # authenticated, RLS-protected account mapping, never editable UI flags.
    return _wbs_auth.owner_id


def save_project_to_supabase(project_title, project_type="story"):
    user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    result = supabase.table("writersblock_projects").insert({
        "user_id": user_id,
        "project_title": project_title,
        "project_type": project_type,
        "project_status": "active"
    }).execute()

    if result.data and len(result.data) > 0:
        st.session_state.current_project_id = result.data[0].get("id")

    return result

    def save_draft_to_supabase(project_id, draft_title, draft_content, draft_type="sandbox"):
        user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    result = supabase.table("writersblock_project_drafts").insert({
        "project_id": project_id,
        "user_id": user_id,
        "draft_title": draft_title,
        "draft_type": draft_type,
        "draft_content": draft_content,
        "version_number": 1
    }).execute()

def save_project_draft_to_supabase(project_id, draft_title, draft_type, draft_content):
    user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    result = supabase.table("writersblock_project_drafts").insert({
        "project_id": project_id,
        "user_id": user_id,
        "draft_title": draft_title,
        "draft_type": draft_type,
        "draft_content": draft_content,
        "version_number": 1
    }).execute()

    return result


WBS_SHARED_DEVELOPMENT_KEYS = {
    "project_title", "dialogue_style", "story_premise", "premise",
    "logline", "story_idea", "objective", "core_premise",
}


def wbs_expected_saved_development_fields(fmt, choices):
    """Return required *visible* field keys from the chosen format's setup.

    A conditional, hidden field is not required. Optional text fields must
    still be present with an empty value to prove the form was captured.
    """
    template = get_wbs_format_template(fmt) or {}
    fields = template.get("concept_fields") or []
    choices = choices if isinstance(choices, dict) else {}
    expected = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "")
        if not key or key in WBS_SHARED_DEVELOPMENT_KEYS:
            continue
        if field.get("type") == "select" and not field.get("options"):
            continue
        if not format_field_should_render(field, choices):
            continue
        expected.append((key, str(field.get("label") or key)))
    if choices.get("production_influence") == "Custom Influence / Other":
        expected.append(("production_influence_custom", "Custom Influence"))
    return expected


def wbs_validate_setup_for_save(snapshot):
    """Fail closed for incomplete *new* saves, across all registered formats.

    No old revision is altered. A default displayed on screen does not count
    as an original choice when it is absent from a saved snapshot.
    """
    fmt = str(snapshot.get("active_format_id") or "")
    values = (snapshot.get("format_template_values") or {}).get(fmt)
    values = values if isinstance(values, dict) else {}
    expected = wbs_expected_saved_development_fields(fmt, values)
    missing = [label for key, label in expected if key not in values]
    if fmt in {"biography_memoir", "childrens_interactive_educational"}:
        from core.registry import get_format
        missing.extend(get_format(fmt).validate_snapshot(snapshot))
    return missing


def wbs_get_saved_concept_setup_audit():
    """Read the exact saved project-session row; never substitute current widget defaults.

    A missing field is NOT evidence of its previous value. This read-only audit
    never creates, edits or deletes Supabase records.
    """
    row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or
                 st.session_state.get("_wbs_loaded_saved_session_id") or "").strip()
    project_id = str(get_active_project_id() or "").strip()
    user_id = get_current_user_id()
    fmt = str(st.session_state.get("active_format_id") or "").strip()
    if not (row_id and project_id and user_id and fmt in WBS_FORMAT_IDS):
        return {"ok": False, "message": "An exact saved revision is not currently loaded."}
    try:
        result = (supabase.table("writersblock_project_drafts")
                  .select("id, project_id, user_id, draft_type, draft_content")
                  .eq("id", row_id).eq("project_id", project_id)
                  .eq("user_id", user_id).eq("draft_type", "project_session")
                  .limit(1).execute())
        rows = getattr(result, "data", None) or []
        if len(rows) != 1:
            return {"ok": False, "message": "The exact saved revision could not be verified."}
        snap = json.loads(rows[0].get("draft_content") or "{}")
        if not isinstance(snap, dict):
            raise ValueError("Saved snapshot is not an object")
        if (str(snap.get("current_project_id") or project_id) != project_id
                or str(snap.get("active_format_id") or "") != fmt):
            return {"ok": False, "message": "Saved project identity/format mismatch; no data was changed."}
        all_values = snap.get("format_template_values")
        raw = all_values.get(fmt) if isinstance(all_values, dict) else None
        raw = raw if isinstance(raw, dict) else {}
        expected = wbs_expected_saved_development_fields(fmt, raw)
        recorded = [(name, label, raw[name]) for name, label in expected if name in raw]
        missing = [(name, label) for name, label in expected if name not in raw]
        return {"ok": True, "recorded": recorded, "missing": missing,
                "saved_revision_id": row_id, "format": fmt,
                "saved_premise_present": bool(str(snap.get("story_seed") or "").strip())}
    except Exception as exc:
        return {"ok": False, "message": f"Cannot inspect original saved settings: {exc}"}


def wbs_merge_live_concept_widgets_into_snapshot(snapshot, fmt):
    """Capture pending keyed Streamlit edits even when Save is in the sidebar.

    The sidebar's Save button executes before Step 1 form fields re-render on a
    click. Use only the currently scoped project+format+revision widget keys.
    Do not backfill absent historical settings from current template defaults.
    """
    template = get_wbs_format_template(fmt) or {}
    values = dict((snapshot.get("format_template_values") or {}).get(fmt) or {})
    excluded = {"project_title", "dialogue_style", "story_premise", "premise",
                "logline", "story_idea", "objective", "core_premise"}
    for field in (template.get("concept_fields") or []):
        if not isinstance(field, dict):
            continue
        name = str(field.get("key") or "")
        if not name or name in excluded:
            continue
        widget_key = get_active_format_widget_key(name)
        if widget_key in st.session_state:
            value = st.session_state[widget_key]
            # Streamlit date widgets use date objects, but JSON snapshots use ISO.
            if hasattr(value, "isoformat") and not isinstance(value, str):
                value = value.isoformat()
            values[name] = value
    snapshot["format_template_values"] = {fmt: values}

    # Stage 1 sidebar saves run BEFORE the center-panel widgets are rendered.
    # Copy the live, project/format/revision-scoped values into the snapshot;
    # otherwise an old generic widget (or old session value) can be saved.
    if st.session_state.get("project_stage") == "Intake":
        tone_key = get_active_format_widget_key("concept_prose_tone")
        if tone_key in st.session_state:
            snapshot["tone_style"] = str(st.session_state[tone_key] or "")
        premise_key = get_active_format_widget_key("concept_story_premise")
        source_mode = str(snapshot.get("version_source_mode") or
                          snapshot.get("starting_source_mode") or "")
        if (source_mode in {"Custom Plot Line", "Story Idea"}
                and premise_key in st.session_state):
            snapshot["story_seed"] = str(st.session_state[premise_key] or "")
    return snapshot


def get_project_session_snapshot():
    snapshot_keys = [
        "project_stage",
        "story_seed",
        "wbs_project_original_concept",
        "starting_source_mode",
        "version_source_mode",
        "saved_version_source_text",
        "saved_version_source_name",
        "saved_version_source_word_count",
        "quill_starting_direction",
        "imported_source_text",
        "imported_source_name",
        "imported_source_word_count",
        "project_title",
        "project_version_name",
        "concept_change_areas",
        "project_scope",
        "series_key",
        "series_name",
        "series_book_number",
        "series_continuity_mode",
        "series_reference_ids",
        "series_canon_notes",
        "series_selection_signature",
        "active_format_id",
        "format_template_values",
        "format_type",
        "dialogue_style",
        "audiobook_length",
        "audiobook_target_word_count",
        "picture_book_word_target",
        "_wbs_picture_book_budget_age",
        "audiobook_production_script",
        "audiobook_production_source_signature",
        "audiobook_production_cue_level",
        "audiobook_production_preview_id",
        "tone_style",
        "author_style",
        "sandbox_slates",
        "chosen_option",
        "chosen_option_text",
        "plot_outline",
        "current_draft_output",
        "rolling_lore_book",
        "completed_beats",
        "scene_blocks",
        "current_processing_beat",
        "manuscript_version",
        "current_manuscript_save_status",
        "current_manuscript_save_stage",
        "current_manuscript_save_version",
        "rewritten_manuscript",
        "rewrite_applied_message",
        "rewrite_preview_id",
        "rewrite_target_length",
        "revision_report",
        "project_integrity_report",
        "project_integrity_source_signature",
        "project_integrity_status",
        "wbs_stage4_scene_approvals",
        "wbs_stage4_final_acceptance",
        "export_view",
        "final_output_format",
        "final_output_text",
        "final_output_source_signature",
        "final_output_preview_id",
        "final_output_saved_signature",
        "picture_book_layout_spreads",
        "picture_book_layout_source_signature",
        "picture_book_layout_preview_id",
        "picture_book_page_size",
        "children_publication_layout",
        "publication_layout",
        "current_project_id",
    ]

    snapshot = {}
    for key in snapshot_keys:
        value = st.session_state.get(key)
        if key == "scene_blocks" and isinstance(value, dict):
            snapshot[key] = {str(k): v for k, v in value.items()}
        else:
            snapshot[key] = value

    # WBS Fixes-3: prevent a saved branch from silently switching format.
    project_id = get_active_project_id()
    locked = (st.session_state.get("wbs_locked_format_id")
              if project_id and str(st.session_state.get("_wbs_locked_project_id") or "") == str(project_id)
              else None)
    fmt = validate_format_for_save(str(st.session_state.get("active_format_id") or ""), locked)
    snapshot["active_format_id"] = fmt
    snapshot["format_type"] = FORMAT_LEGACY[fmt]
    values = st.session_state.get("format_template_values") or {}
    snapshot["format_template_values"] = {
        fmt: dict(values.get(fmt) or {})
    } if isinstance(values, dict) else {fmt: {}}
    wbs_merge_live_concept_widgets_into_snapshot(snapshot, fmt)
    snapshot["saved_at"] = datetime.now(timezone.utc).isoformat()
    return snapshot



CONCEPT_VERSION_GROUPS = {
    "Format": (
        "active_format_id",
        "format_type",
    ),
    "Development": (
        "format_template_values",
        "dialogue_style",
        "tone_style",
        "author_style",
        "project_scope",
        "series_name",
        "series_book_number",
        "series_continuity_mode",
        "series_reference_ids",
        "series_canon_notes",
        "audiobook_length",
        "audiobook_target_word_count",
    ),
    "Starting Point": (
        "version_source_mode",
        "quill_starting_direction",
        "story_seed",
        "wbs_project_original_concept",
        "imported_source_name",
        "imported_source_text",
    ),
}


def _concept_compare_value(value):
    """Create a stable comparison value for concept settings."""
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), sort_keys=True, ensure_ascii=False, default=str)
    return "" if value is None else str(value)


def get_current_concept_version_state():
    state = {}
    for group_keys in CONCEPT_VERSION_GROUPS.values():
        for key in group_keys:
            state[key] = st.session_state.get(key)
    return state


def set_loaded_concept_version_baseline(source=None):
    """Remember the loaded branch's Step 1 settings for change detection."""
    source = source or st.session_state
    baseline = {}
    for group_keys in CONCEPT_VERSION_GROUPS.values():
        for key in group_keys:
            if isinstance(source, dict):
                baseline[key] = source.get(key)
            else:
                baseline[key] = st.session_state.get(key)
    st.session_state["_wbs_loaded_concept_version_baseline"] = baseline


def get_changed_concept_version_areas():
    baseline = st.session_state.get("_wbs_loaded_concept_version_baseline")
    if not isinstance(baseline, dict) or not baseline:
        return []

    current = get_current_concept_version_state()
    changed = []

    for area, keys in CONCEPT_VERSION_GROUPS.items():
        if any(
            _concept_compare_value(current.get(key))
            != _concept_compare_value(baseline.get(key))
            for key in keys
        ):
            changed.append(area)

    return changed


def get_suggested_project_version_name():
    changed = get_changed_concept_version_areas()
    if changed:
        return f"{'-'.join(changed)} Change"
    current_name = str(st.session_state.get("project_version_name") or "").strip()
    if current_name and current_name != "Original":
        return current_name
    return "Alternate Version"


def clean_project_version_name(value):
    clean = re.sub(r"\s+", " ", str(value or "")).strip(" -")
    return clean[:60]


def get_next_project_session_internal_version(project_id):
    if not project_id:
        return 1
    result = (
        supabase.table("writersblock_project_drafts")
        .select("version_number")
        .eq("project_id", project_id)
        .eq("draft_type", "project_session")
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return int(result.data[0].get("version_number") or 0) + 1
    return 1


# MASTER PROJECT / VERSION RULE — shared by all formats and workflow stages.
def wbs_has_saved_master():
    """Read-only check: a project ID alone does not mean a master was saved."""
    project_id = get_active_project_id()
    user_id = get_current_user_id()
    if not project_id:
        return False
    if not user_id:
        return None
    if (str(st.session_state.get("_wbs_last_saved_project_id") or "") == str(project_id)
            and st.session_state.get("_wbs_active_saved_session_row_id")):
        return True
    try:
        rows = (supabase.table("writersblock_project_drafts")
                .select("id")
                .eq("project_id", project_id)
                .eq("user_id", user_id)
                .eq("draft_type", "project_session")
                .limit(1).execute())
        return bool(getattr(rows, "data", None))
    except Exception:
        return None  # fail closed; never risk an initial-save rewrite


# Only writer-facing content counts as a change, not navigation, dates, editor
# previews, labels, or the version's descriptive name.
WBS_WRITER_CHANGE_KEYS = (
    "active_format_id", "format_type", "format_template_values", "dialogue_style",
    "tone_style", "author_style", "project_scope", "series_key", "series_name",
    "series_book_number", "series_continuity_mode", "series_reference_ids",
    "series_canon_notes", "audiobook_length", "audiobook_target_word_count",
    "picture_book_word_target", "picture_book_page_size", "children_publication_layout", "publication_layout", "story_seed", "wbs_project_original_concept",
    "starting_source_mode", "version_source_mode", "imported_source_name",
    "quill_starting_direction", "imported_source_text", "saved_version_source_text",
    "audiobook_production_script", "audiobook_production_cue_level",
    "final_output_format",
    "chosen_option", "chosen_option_text", "sandbox_slates", "plot_outline",
    "current_draft_output", "rewritten_manuscript", "scene_blocks", "completed_beats",
    "rolling_lore_book", "final_output_text", "picture_book_layout_spreads",
)


def wbs_save_state_signature(snapshot=None):
    """Hash meaningful writer work; titles are changed ONLY using Rename Project."""
    if snapshot is None:
        snapshot = get_project_session_snapshot()
    relevant = {key: snapshot.get(key) for key in WBS_WRITER_CHANGE_KEYS}
    if isinstance(relevant.get("scene_blocks"), dict):
        relevant["scene_blocks"] = {str(k): v for k, v in relevant["scene_blocks"].items()}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True, default=str,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def wbs_work_has_changed(snapshot=None):
    """No version from a change to the branch label or a stage navigation alone."""
    project_id = str(get_active_project_id() or "")
    baseline_project = str(st.session_state.get("_wbs_last_saved_project_id") or "")
    baseline = str(st.session_state.get("_wbs_last_saved_work_signature") or "")
    if not baseline or baseline_project != project_id:
        # Older sessions without a trustworthy baseline require a reload, not
        # speculative insert of a duplicate saved version.
        return None
    try:
        return wbs_save_state_signature(snapshot) != baseline
    except SavedFormatError:
        return None


def render_save_as_named_version_control(location_key):
    """Save a NEW session revision without modifying an older saved version."""
    if st.session_state.get("demo_mode") or not get_active_project_id():
        return
    if wbs_has_saved_master() is not True:
        return

    changed_areas = get_changed_concept_version_areas()
    suggested = get_suggested_project_version_name()
    signature = "|".join(changed_areas) or suggested
    signature_key = f"_wbs_version_name_suggestion_signature_{location_key}"
    input_key = f"save_as_version_name_{location_key}"
    if st.session_state.get(signature_key) != signature:
        st.session_state[signature_key] = signature
        st.session_state[input_key] = suggested

    with st.expander("Save Project Changes As A New Version", expanded=False):
        version_name = st.text_input(
            "Version Description:",
            key=input_key, max_chars=60,
            help="Briefly describe what changed.",
        )
        if changed_areas:
            st.caption("Changes in: " + ", ".join(changed_areas))
        changed = wbs_work_has_changed()
        if changed is False:
            st.info("No changes detected. The existing saved version is preserved.")
        elif changed is None:
            st.warning("Reload the saved version before creating a new version; no changes were written.")
        if st.button(
            "Save Project Changes As A New Version",
            key=f"save_as_new_named_version_{location_key}",
            use_container_width=True, type="secondary", disabled=(changed is not True),
        ):
            clean_name = clean_project_version_name(version_name)
            if not clean_name:
                st.warning("Enter a brief description of the version change.")
                return
            result = save_current_project_session_to_supabase(
                version_name=clean_name, save_as_new_version=True,
            )
            if result and not getattr(result, "unchanged", False):
                st.success(f"New version saved under {get_project_title_for_display()} — {clean_name}")
                st.rerun()


def save_current_project_session_to_supabase(version_name=None, save_as_new_version=False):
    """First save creates V-1; routine stage saves remain on the active V-n.

    Never edit an existing snapshot and never silently rename the parent project.
    Stage checkpoint callers use this same protection in ALL formats.
    """
    user_id = get_current_user_id()
    if not user_id:
        st.error("No user found.")
        return None

    # Capture and verify the entire Stage 1 development configuration before
    # any Supabase INSERT, including before creation of a master project row.
    try:
        snapshot = get_project_session_snapshot()
    except SavedFormatError as exc:
        st.error(f"Project save cancelled: {exc}")
        return None
    missing_setup = wbs_validate_setup_for_save(snapshot)
    if missing_setup:
        st.error("Development Setup was not fully captured, so nothing was saved. "
                 "Return to Concept Development and review these fields: "
                 + ", ".join(missing_setup[:12])
                 + (f" (and {len(missing_setup)-12} others)" if len(missing_setup)>12 else ""))
        return None

    project_id = get_active_project_id()
    if not project_id:
        title = get_project_title()
        if not title:
            st.error("Name the project before its first master save.")
            return None
        result = save_project_to_supabase(
            project_title=title[:80],
            project_type=st.session_state.get("format_type", "story"),
        )
        project_id = get_active_project_id()
        if not project_id:
            st.error("Could not create the initial project record; nothing was saved.")
            return None

    ensure_project_title_loaded()
    # The authoritative Project Title is read-only here. Only Confirm Only If
    # Renaming may update it; creating a version must NEVER rename a project.
    try:
        parent = (supabase.table("writersblock_projects")
                  .select("project_title")
                  .eq("id", project_id).eq("user_id", user_id)
                  .limit(1).execute())
        parent_rows = getattr(parent, "data", None) or []
    except Exception as exc:
        st.error(f"Cannot verify the project title. Save blocked: {exc}")
        return None
    if len(parent_rows) != 1:
        st.error("Project identity cannot be verified; nothing was saved.")
        return None
    actual_title = str(parent_rows[0].get("project_title") or "").strip()
    if not actual_title or actual_title != get_project_title():
        st.error("Project title differs from its saved master. Use Rename Project; no version was saved.")
        return None

    master_saved = wbs_has_saved_master()
    if master_saved is None:
        st.error("Cannot check existing versions. No data was written.")
        return None
    if save_as_new_version and master_saved is False:
        st.error("Save the new project's master record first.")
        return None

    if (st.session_state.get("version_source_mode") == "Quill Assisted"
            and not str(st.session_state.get("story_seed") or "").strip()):
        st.error("No Quill story concept is present to save. Generate or restore it first.")
        return None

    if snapshot.get("version_source_mode") == "Quill Assisted":
        snapshot["saved_quill_concept"] = str(st.session_state.get("story_seed") or "")
    snapshot["current_project_id"] = project_id
    snapshot["project_title"] = actual_title

    # Loaded versions have a known baseline. A no-op is an explicit successful
    # navigation checkpoint but NEVER performs a database INSERT.
    if master_saved:
        changed = wbs_work_has_changed(snapshot)
        if changed is False:
            st.info("No project changes detected; no new version was created.")
            return SimpleNamespace(unchanged=True, data=[])
        if changed is None:
            st.error("Saved-version baseline is unavailable. Reload this project before saving; nothing was written.")
            return None

    # SHARED BACKEND RULE: only explicit Save as New Version increments V-n.
    if master_saved and not save_as_new_version:
        row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "").strip()
        if not row_id:
            st.error("Exact active revision cannot be verified. Reload the saved project; nothing was changed.")
            return None
        try:
            from core.save_conflicts import expected_checkpoint, verify_checkpoint
            expected_content = expected_checkpoint(st.session_state, project_id, row_id)
            rows = (supabase.table("writersblock_project_drafts")
                    .select("id, project_id, user_id, version_number, draft_content")
                    .eq("id", row_id).eq("project_id", project_id)
                    .eq("user_id", user_id).eq("draft_type", "project_session")
                    .limit(1).execute()).data or []
            if len(rows) != 1:
                raise ValueError("The selected revision was not found")
            verify_checkpoint(expected_content, rows[0]['draft_content'])
            previous = json.loads(rows[0].get("draft_content") or "{}")
            if not isinstance(previous, dict):
                raise ValueError("Saved revision is invalid")
            previous_format = str(previous.get("active_format_id") or "")
            if previous_format != snapshot.get("active_format_id"):
                raise ValueError("Saved format does not match the active writing format")
            previous_id = str(previous.get("current_project_id") or project_id)
            if previous_id != str(project_id):
                raise ValueError("Saved project identity mismatch")
            # Keep the revision's existing identity, and retain separately
            # persisted review metadata if it isn't in the live snapshot.
            snapshot["project_version_name"] = previous.get("project_version_name") or "Original"
            snapshot["concept_change_areas"] = previous.get("concept_change_areas") or []
            _structure_now = ((snapshot.get("format_template_values") or {}).get(snapshot["active_format_id"]) or {}).get("manuscript_structure")
            _structure_before = ((previous.get("format_template_values") or {}).get(snapshot["active_format_id"]) or {}).get("manuscript_structure")
            _structure_invalidates_report = (snapshot["active_format_id"] != "short_story" and bool(_structure_now)
                and (_structure_now != _structure_before or snapshot.get("current_draft_output") != previous.get("current_draft_output")))
            for review_key in ("project_integrity_report", "project_integrity_source_signature",
                               "project_integrity_status"):
                if not _structure_invalidates_report and not snapshot.get(review_key) and previous.get(review_key):
                    snapshot[review_key] = previous[review_key]
            updated = supabase.save_project_checkpoint(
                project_id, row_id, rows[0]['draft_content'], json.dumps(snapshot))
            if not getattr(updated, "data", None):
                raise RuntimeError("Save not confirmed by database")
        except Exception as exc:
            st.error(f"Current revision was not saved: {exc}")
            return None
        st.session_state.last_saved_project_at = snapshot.get("saved_at")
        from core.save_conflicts import remember_checkpoint
        remember_checkpoint(st.session_state, project_id, updated.data[0])
        st.session_state["_wbs_last_saved_work_signature"] = wbs_save_state_signature(snapshot)
        st.session_state["_wbs_last_saved_project_id"] = str(project_id)
        st.session_state["_wbs_active_saved_session_row_id"] = row_id
        st.session_state["_wbs_loaded_saved_session_id"] = row_id
        set_loaded_concept_version_baseline(snapshot)
        return SimpleNamespace(unchanged=False, updated_current=True, data=updated.data)

    changed_areas = get_changed_concept_version_areas()
    requested_version_name = clean_project_version_name(
        version_name or (get_suggested_project_version_name() if master_saved else "Original")
    ) or ("New Revision" if master_saved else "Original")
    snapshot["project_version_name"] = requested_version_name
    snapshot["concept_change_areas"] = list(changed_areas)
    internal_version_number = get_next_project_session_internal_version(project_id)

    # INSERT ONLY: never update an existing saved revision while saving a new one.
    try:
        result = (supabase.table("writersblock_project_drafts").insert({
            "project_id": project_id,
            "user_id": user_id,
            "draft_title": f"Saved Project Session — {requested_version_name}",
            "draft_type": "project_session",
            "draft_content": json.dumps(snapshot),
            "version_number": internal_version_number,
        }).execute())
    except Exception as exc:
        st.error(f"Unable to save the new version: {exc}")
        return None
    if not result or not getattr(result, "data", None):
        st.error("The database did not confirm a saved version; nothing has been overwritten.")
        return None

    if st.session_state.get("project_scope") == "Book in a Series":
        # Existing series metadata code is preserved; this is the only existing
        # extra save path, and never edits manuscript/version text.
        save_series_metadata_for_project(project_id)

    st.session_state.project_version_name = requested_version_name
    from core.save_conflicts import remember_checkpoint
    remember_checkpoint(st.session_state, project_id, result.data[0])
    st.session_state.concept_change_areas = list(changed_areas)
    st.session_state.last_saved_project_at = snapshot.get("saved_at")
    set_loaded_concept_version_baseline(snapshot)
    st.session_state["_wbs_last_saved_work_signature"] = wbs_save_state_signature(snapshot)
    st.session_state["_wbs_last_saved_project_id"] = str(project_id)
    st.session_state["_wbs_saved_session_to_select"] = str(result.data[0].get("id") or "")
    st.session_state["_wbs_active_saved_session_row_id"] = str(result.data[0].get("id") or "")
    st.session_state["_wbs_loaded_saved_session_id"] = str(result.data[0].get("id") or "")
    st.session_state["wbs_locked_format_id"] = snapshot["active_format_id"]
    st.session_state["_wbs_locked_project_id"] = str(project_id)
    st.session_state["_wbs_loaded_project_id"] = str(project_id)
    st.session_state["_wbs_loaded_project_title"] = actual_title
    return result


def persist_project_integrity_in_current_version(report, source_signature, status):
    """Update the existing saved version in place: no insert and no version increment."""
    project_id = get_active_project_id()
    user_id = get_current_user_id()
    if not project_id or not user_id:
        raise RuntimeError("Save this project once before running a persistent integrity review.")

    row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "").strip()
    query = (supabase.table("writersblock_project_drafts")
             .select("id, project_id, user_id, draft_content")
             .eq("project_id", project_id)
             .eq("user_id", user_id)
             .eq("draft_type", "project_session"))
    if row_id:
        query = query.eq("id", row_id)
    else:
        # Older sessions might lack an active row ID; attach to the latest saved
        # version for this project rather than creating a phantom new version.
        query = query.order("created_at", desc=True).limit(1)
    result = query.execute()
    rows = result.data or []
    if not rows:
        raise RuntimeError("The current saved project version could not be found. No new version was created.")
    row = rows[0]
    snapshot = json.loads(row.get("draft_content") or "{}")
    if not isinstance(snapshot, dict):
        raise RuntimeError("The saved project data is invalid. No changes were written.")
    # Keep the latest reviewed manuscript with the report so the signature
    # matches when this exact version is reloaded. Preserve all other snapshot data.
    snapshot["current_draft_output"] = str(st.session_state.get("current_draft_output") or "")
    snapshot["scene_blocks"] = {str(k): v for k, v in (st.session_state.get("scene_blocks") or {}).items()}
    snapshot["completed_beats"] = st.session_state.get("completed_beats") or []
    snapshot["rolling_lore_book"] = st.session_state.get("rolling_lore_book") or ""
    snapshot["project_integrity_report"] = report
    snapshot["project_integrity_source_signature"] = source_signature
    snapshot["project_integrity_status"] = status
    saved = (supabase.table("writersblock_project_drafts")
             .update({"draft_content": json.dumps(snapshot)})
             .eq("id", row["id"])
             .eq("project_id", project_id)
             .eq("user_id", user_id)
             .eq("draft_type", "project_session")
             .execute())
    if not saved or not getattr(saved, "data", None):
        raise RuntimeError("Review could not be saved to the current version.")
    st.session_state["_wbs_active_saved_session_row_id"] = str(row["id"])
    return True


def get_latest_saved_project_session():
    user_id = get_current_user_id()

    if not user_id:
        return None

    query = (
        supabase.table("writersblock_project_drafts")
        .select("id, project_id, draft_content, created_at")
        .eq("draft_type", "project_session")
        .order("created_at", desc=True)
        .limit(1)
    )

    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()

    if result.data and len(result.data) > 0:
        return result.data[0]

    return None


def clear_concept_widget_state_for_loaded_project():
    """Force Step 1 widgets to rebuild from the loaded project's saved values.

    Only widget-state keys are cleared. Project data itself is not changed.
    """
    exact_keys = {
        "wbs_format_template_selector",
        "project_title_input",
        "saved_project_title_input",
        "project_scope_selector",
        "series_choice_selector",
        "series_name_input",
        "series_book_number_input",
        "series_existing_book_selector",
        "series_reference_selector",
        "dialogue_style_selector",
        "audiobook_length_selector",
    }
    prefix_keys = (
        "rename_project_title_",
        "format_field_",
        "tone_style_",
        "starting_source_",
        "custom_plot_line_input_",
        "wbs_quill_starting_direction_",
        "wbs_quill_starting_concept_",
        "wbs_quill_generate_concept_",
        "audiobook_target_words_",
    )

    for key in list(st.session_state.keys()):
        key_text = str(key)
        if key_text in exact_keys or any(key_text.startswith(prefix) for prefix in prefix_keys):
            st.session_state.pop(key, None)

    # A saved V-n may be reopened in the same browser after viewing/editing it.
    # Its widget keys otherwise retain the old on-screen value and override
    # that revision's freshly loaded, authoritative snapshot.
    for field_name in ("concept_prose_tone", "concept_story_premise"):
        st.session_state.pop(get_active_format_widget_key(field_name), None)


def get_best_saved_manuscript_source(source=None):
    """Return the best complete manuscript available in a saved project snapshot."""
    source = source or st.session_state
    getter = source.get if isinstance(source, dict) else st.session_state.get

    candidates = (
        getter("current_draft_output"),
        getter("rewritten_manuscript"),
        getter("final_output_text"),
        getter("manuscript_text"),
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def get_current_project_version_name():
    return clean_project_version_name(
        st.session_state.get("project_version_name") or "Original"
    ) or "Original"


def get_manuscript_branch_name(version):
    """Read the writer-facing branch name from a manuscript checkpoint label."""
    label = str((version or {}).get("version_label") or "").strip()
    title = str(
        (version or {}).get("project_title")
        or ((version or {}).get("writersblock_projects") or {}).get("project_title")
        or ""
    ).strip()

    remainder = label
    if title and remainder.startswith(title + " — "):
        remainder = remainder[len(title + " — "):]

    parts = [part.strip() for part in remainder.split(" — ") if part.strip()]
    if not parts:
        return "Original"

    generic_first_parts = {
        "DRAFT", "FINAL", "SAVED", "IMPORTED",
        "Accepted Rewrite", "Imported Completed Manuscript",
        "Creative Draft", "Script Lock", "Script Rewrite",
        "Working Draft", "Manuscript Output",
    }
    first = parts[0]
    if first in generic_first_parts or first.startswith("DRAFT ") or first.startswith("FINAL "):
        return "Original"

    return clean_project_version_name(first) or "Original"


def get_latest_saved_project_session_for_project(project_id, version_name=None,
                                                checkpoint_created_at=None):
    """Return the newest saved project-state snapshot for one project/branch."""
    user_id = get_current_user_id()
    if not user_id or not project_id:
        return None

    query = (
        supabase.table("writersblock_project_drafts")
        .select("id, project_id, draft_content, created_at, version_number")
        .eq("draft_type", "project_session")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(500)
    )
    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()
    rows = list(result.data or [])
    if checkpoint_created_at:
        # Choosing the newest session overall leaks subsequent concept edits into
        # an older manuscript V-n. Never travel forward in time during restore.
        rows = [row for row in rows if str(row.get("created_at") or "")
                <= str(checkpoint_created_at)]
    if not rows:
        return None

    requested_name = clean_project_version_name(version_name or "")
    if requested_name:
        for row in rows:
            try:
                snapshot = json.loads(row.get("draft_content") or "{}")
            except Exception:
                snapshot = {}
            row_name = clean_project_version_name(
                snapshot.get("project_version_name") or "Original"
            ) or "Original"
            if row_name.lower() == requested_name.lower():
                return row

    # A different branch is not a valid restoration source for this checkpoint.
    # Older saves with no explicit branch name are matched above as "Original".
    return rows[0] if not requested_name else None


def _wbs_restore_missing_concept_fields(saved_snapshot, project_id, as_of=None):
    """Read-only recovery from THIS project's historical records, never session defaults.

    A manuscript checkpoint does not persist its Concept form separately.  Old
    project sessions may predate today's template or series fields.  Consult
    same-user/same-project historical snapshots and series metadata; never
    invent choices when the information was not recorded.
    """
    recovered = dict(saved_snapshot)
    audit = {"recovered_setup": False, "recovered_series": False,
             "series_conflict": False, "history_unavailable": False}
    user_id = get_current_user_id()
    if not user_id or not project_id:
        return recovered, audit

    saved_fmt = str(recovered.get("active_format_id") or "").strip()
    if saved_fmt not in WBS_FORMAT_IDS:
        saved_fmt = WBS_TEMPLATE_ID_BY_LEGACY_FORMAT.get(str(recovered.get("format_type") or ""), "")
    def _fmt_match(candidate):
        value = str(candidate.get("active_format_id") or "")
        if not value:
            value = WBS_TEMPLATE_ID_BY_LEGACY_FORMAT.get(str(candidate.get("format_type") or ""), "")
        return value == saved_fmt

    # Do not use a future branch/session to reconstruct an earlier checkpoint.
    historical = []
    target_branch = clean_project_version_name(recovered.get("project_version_name") or "Original").casefold()
    try:
        history_query = (supabase.table("writersblock_project_drafts")
                         .select("id, project_id, user_id, draft_content, created_at")
                         .eq("project_id", project_id).eq("user_id", user_id)
                         .eq("draft_type", "project_session")
                         .order("created_at", desc=True).limit(500))
        for row in history_query.execute().data or []:
            when = str(row.get("created_at") or "")
            if as_of and when and when > str(as_of):
                continue
            try:
                old = json.loads(row.get("draft_content") or "{}")
            except (ValueError, TypeError):
                continue
            if not isinstance(old, dict):
                continue
            if old.get("current_project_id") and str(old["current_project_id"]) != str(project_id):
                continue
            if not _fmt_match(old):
                continue
            old_branch = clean_project_version_name(old.get("project_version_name") or "Original").casefold()
            if old_branch != target_branch:
                continue
            historical.append((when, old))
    except Exception:
        audit["history_unavailable"] = True
    historical.sort(key=lambda item: item[0], reverse=True)

    # Only retrieve saved choices, not the current template's default values.
    all_values = recovered.get("format_template_values")
    all_values = dict(all_values) if isinstance(all_values, dict) else {}
    present = all_values.get(saved_fmt)
    present = dict(present) if isinstance(present, dict) else {}
    for _, old in historical:
        old_all = old.get("format_template_values")
        old_setup = old_all.get(saved_fmt) if isinstance(old_all, dict) else None
        if not isinstance(old_setup, dict):
            continue
        for field, value in old_setup.items():
            if field not in present and value is not None and str(value).strip():
                present[field] = value
                audit["recovered_setup"] = True
    if saved_fmt:
        all_values[saved_fmt] = present
    recovered["format_template_values"] = all_values

    # These independent development controls were saved before format templates.
    for field in ("dialogue_style", "tone_style", "author_style", "audiobook_length",
                  "audiobook_target_word_count", "picture_book_word_target"):
        if recovered.get(field) not in (None, ""):
            continue
        for _, old in historical:
            value = old.get(field)
            if value not in (None, ""):
                recovered[field] = value
                audit["recovered_setup"] = True
                break

    # Prefer the selected saved snapshot's exact series identity. When it lacks
    # series fields, an explicit series_metadata row for the SAME project may
    # supply the relationship. No cross-project or auto-number lookups.
    series_name = str(recovered.get("series_name") or "").strip()
    series_scope = recovered.get("project_scope") == "Book in a Series"
    if not (series_name and series_scope):
        # An old snapshot can predate its series assignment. Prefer historical
        # series metadata, and require unambiguous evidence for its book number.
        series_evidence = []
        for _, old in historical:
            name = str(old.get("series_name") or "").strip()
            if old.get("project_scope") == "Book in a Series" and name:
                series_evidence.append(old)
        try:
            metadata_query = (supabase.table("writersblock_project_drafts")
                              .select("id, project_id, user_id, draft_content, created_at")
                              .eq("project_id", project_id).eq("user_id", user_id)
                              .eq("draft_type", "series_metadata")
                              .order("created_at", desc=False).limit(200))
            for row in metadata_query.execute().data or []:
                try:
                    item = json.loads(row.get("draft_content") or "{}")
                except (TypeError, ValueError):
                    continue
                if isinstance(item, dict) and str(item.get("series_name") or "").strip():
                    series_evidence.append(item)
        except Exception:
            audit["history_unavailable"] = True
        names = {str(x.get("series_name") or "").strip().casefold() for x in series_evidence}
        names.discard("")
        if len(names) == 1:
            # Favor the oldest evidence for this project; this prevents a later
            # auto-renumbered metadata record from overwriting an earlier volume.
            evidence = series_evidence[0]
            recovered["project_scope"] = "Book in a Series"
            recovered["series_name"] = str(evidence.get("series_name") or "")
            if not str(recovered.get("series_key") or ""):
                recovered["series_key"] = str(evidence.get("series_key") or "")
            numbers = set()
            for item in series_evidence:
                try:
                    number = int(item.get("series_book_number") or 0)
                except (ValueError, TypeError):
                    number = 0
                if number > 0:
                    numbers.add(number)
            if len(numbers) == 1:
                recovered["series_book_number"] = next(iter(numbers))
            elif len(numbers) > 1:
                # Conflicting historical numbers must be flagged, not guessed.
                audit["series_conflict"] = True
                # Preserve the saved relationship fields but block the series
                # control from proposing an arbitrary volume of 1.
                recovered["project_scope"] = "Standalone Book"
            audit["recovered_series"] = True
        elif len(names) > 1:
            audit["series_conflict"] = True

    return recovered, audit


def load_saved_project_session_to_state(saved_session_row):
    st.session_state.pop("_wbs_ss_integrity_return_context", None)
    st.session_state.pop("_wbs_stage1_continue_approval", None)
    st.session_state.pop("_wbs_stage2_choose_new", None)
    st.session_state.pop("_wbs_stage2_pending_path", None)
    st.session_state.pop("_wbs_stage2_regen_unsaved", None)
    st.session_state.pop("_wbs_stage2_regen_preview", None)
    if not saved_session_row:
        st.warning("No saved project session found.")
        return False

    try:
        snapshot = json.loads(saved_session_row.get("draft_content") or "{}")
        if not isinstance(snapshot, dict):
            raise SavedFormatError("Saved project snapshot is not a record.")
        load_project_id = saved_session_row.get("project_id") or snapshot.get("current_project_id")
        # Validate ID and recognized format BEFORE modifying the open project.
        prepare_saved_snapshot(snapshot, load_project_id)
    except (ValueError, TypeError, SavedFormatError) as exc:
        st.error(f"Saved project could not be loaded: {exc}")
        return False

    # Restore only evidence saved for this exact project; all queries read-only.
    snapshot, restore_audit = _wbs_restore_missing_concept_fields(
        snapshot, load_project_id, saved_session_row.get("created_at"),
    )

    # Restoring a saved project must use evidence belonging to THIS project,
    # never the previous project's widget or session state.
    legacy_aliases = {
        "Children's Storybook (32-Page Writing Layout)": "Children's Picture Book (32-Page Layout)",
        "Children's Storybook (32-Page Layout)": "Children's Picture Book (32-Page Layout)",
        "Children's Picture Book": "Children's Picture Book (32-Page Layout)",
        "Audio Short Story — 15–30 min": "Audio Book",
    }
    def _format_id_from_name(value):
        name = legacy_aliases.get(str(value or "").strip(), str(value or "").strip())
        if name in WBS_FORMAT_IDS:
            return name
        return WBS_TEMPLATE_ID_BY_LEGACY_FORMAT.get(name)

    snapshot_id = _format_id_from_name(snapshot.get("active_format_id"))
    snapshot_name_id = _format_id_from_name(snapshot.get("format_type"))
    parent_id = None
    # The project row may be more accurate than a stale copied format field in
    # an old project_session. Read it, but NEVER update it during project load.
    try:
        parent_row = (supabase.table("writersblock_projects")
                      .select("project_type")
                      .eq("id", load_project_id)
                      .limit(1).execute())
        if getattr(parent_row, "data", None):
            parent_id = _format_id_from_name(parent_row.data[0].get("project_type"))
    except Exception:
        pass

    recovered_setup = False
    per_format = snapshot.get("format_template_values")
    if not isinstance(per_format, dict):
        per_format = {}
    populated = [fmt for fmt, values in per_format.items()
                 if fmt in WBS_FORMAT_IDS and isinstance(values, dict)
                 and any(str(value or "").strip() for value in values.values())]
    # A saved snapshot can have a stale childrens_picture_book ID while all
    # actual development choices belong to the audiobook or short-story template.
    # Prefer existing project-specific form data over an incompatible stale ID.
    candidates = [parent_id, snapshot_name_id, snapshot_id]
    restored_format_id = next((fmt for fmt in candidates if fmt in populated), None)
    if not restored_format_id and len(populated) == 1:
        restored_format_id = populated[0]
    if not restored_format_id:
        restored_format_id = next((fmt for fmt in candidates if fmt in WBS_FORMAT_IDS), None)
    if not restored_format_id:
        # Do not silently give an unknown saved project the previous template.
        st.error("Saved writing format is missing or unknown. This project was not loaded.")
        return False

    # If an old save has lost its format's setup values, recover them READ-ONLY
    # from an earlier session of the same project and same format. Never use
    # any other project's settings, and never auto-save the recovered data.
    current_values = per_format.get(restored_format_id)
    if not isinstance(current_values, dict) or not any(str(v or "").strip() for v in current_values.values()):
        try:
            old_rows = (supabase.table("writersblock_project_drafts")
                        .select("id, draft_content, created_at")
                        .eq("project_id", load_project_id)
                        .eq("draft_type", "project_session")
                        .order("created_at", desc=True).limit(100).execute())
            loaded_time = str(saved_session_row.get("created_at") or "")
            for candidate in getattr(old_rows, "data", None) or []:
                if str(candidate.get("id")) == str(saved_session_row.get("id")):
                    continue
                if loaded_time and str(candidate.get("created_at") or "") > loaded_time:
                    continue
                try:
                    older = json.loads(candidate.get("draft_content") or "{}")
                except (ValueError, TypeError):
                    continue
                older_values = older.get("format_template_values")
                if not isinstance(older_values, dict):
                    continue
                recovered = older_values.get(restored_format_id)
                if not isinstance(recovered, dict) or not any(str(v or "").strip() for v in recovered.values()):
                    continue
                older_id = _format_id_from_name(older.get("active_format_id"))
                older_name = _format_id_from_name(older.get("format_type"))
                if restored_format_id not in (older_id, older_name):
                    continue
                per_format = dict(per_format)
                per_format[restored_format_id] = dict(recovered)
                recovered_setup = True
                break
        except Exception:
            pass
    # Commit only after resolving this project's format and checking all IDs.
    # Reset absent older keys to project-safe defaults; license and account state
    # are never touched. Preserve the saved version/Quill/Stage 3 fields.
    normalized_raw = dict(snapshot)
    # Project title is master metadata owned by this project ID, not by an
    # earlier snapshot's UI widget or another open project. Read only: the
    # actual parent record always wins after explicit project renames.
    parent_project_title = get_project_title_from_project_id(load_project_id)
    if parent_project_title:
        normalized_raw["project_title"] = parent_project_title
    normalized_raw["format_template_values"] = {restored_format_id: dict(per_format.get(restored_format_id) or {})}
    try:
        # Format guard accepts the saved snapshot and project ID only.
        # Verify the restored ID separately; never load a different format.
        normalized_raw["active_format_id"] = restored_format_id
        normalized_raw["format_type"] = WBS_LEGACY_FORMAT_BY_TEMPLATE_ID[restored_format_id]
        verified = prepare_saved_snapshot(normalized_raw, load_project_id)
        if not isinstance(verified, dict) or verified.get("active_format_id") != restored_format_id:
            raise SavedFormatError("Saved writing format could not be verified.")
    except (SavedFormatError, TypeError) as exc:
        st.error(f"Saved project could not be loaded: {exc}")
        return False
    for key, value in verified.items():
        if key == "scene_blocks" and isinstance(value, dict):
            converted = {}
            for scene_key, scene_text in value.items():
                try:
                    converted[int(scene_key)] = scene_text
                except (ValueError, TypeError):
                    converted[scene_key] = scene_text
            st.session_state.scene_blocks = converted
        else:
            st.session_state[key] = value
    st.session_state.last_saved_project_at = snapshot.get("saved_at")
    st.session_state["_wbs_active_saved_session_row_id"] = str(saved_session_row.get("id") or "")
    from core.save_conflicts import remember_checkpoint
    remember_checkpoint(st.session_state, load_project_id, saved_session_row)
    st.session_state["wbs_stage4_scene_approvals"] = snapshot.get("wbs_stage4_scene_approvals") or {}
    st.session_state.pop("_wbs_stage4_review_identity", None)
    st.session_state.pop("_wbs_stage4_approved_scenes", None)
    st.session_state["_wbs_stage3_saved_outline_baseline"] = str(snapshot.get("plot_outline") or "").strip()
    st.session_state["_wbs_stage3_unsaved_changes"] = False
    st.session_state["_wbs_last_saved_work_signature"] = wbs_save_state_signature(verified)
    st.session_state["_wbs_last_saved_project_id"] = str(load_project_id or "")
    st.session_state["_wbs_loaded_project_id"] = str(load_project_id or "")
    st.session_state["_wbs_loaded_project_title"] = str(verified.get("project_title") or "").strip()
    st.session_state["wbs_locked_format_id"] = restored_format_id
    st.session_state["_wbs_locked_project_id"] = str(load_project_id or "")
    st.session_state["_wbs_concept_recovered_for_review"] = (
        recovered_setup or restore_audit["recovered_setup"]
    )
    st.session_state["_wbs_series_recovered_for_review"] = restore_audit["recovered_series"]
    st.session_state["_wbs_series_conflict_for_review"] = restore_audit["series_conflict"]
    st.session_state["_wbs_historical_restore_unavailable"] = restore_audit["history_unavailable"]
    setup_values = normalized_raw.get("format_template_values") or {}
    saved_fields = setup_values.get(restored_format_id) or {}
    template_fields = (get_wbs_format_template(restored_format_id) or {}).get("concept_fields") or []
    # Defaults shown by Streamlit are not proof of the writer's original choices.
    missing_fields = [str(f.get("key")) for f in template_fields if isinstance(f, dict)
                      and f.get("key") and f["key"] not in saved_fields
                      and f["key"] not in {"project_title", "dialogue_style",
                                            "story_premise", "premise", "logline",
                                            "story_idea", "objective", "core_premise"}]
    st.session_state["_wbs_saved_concept_missing_fields"] = missing_fields
    # Old preview/editor widget state must never spill into another project.
    for cache_key in list(st.session_state.keys()):
        if str(cache_key).startswith(("_wbs_stage3_rewrite_", "_wbs_stage3_edit_", "_wbs_stage3_clean_")):
            st.session_state.pop(cache_key, None)
    st.session_state["_wbs_loaded_quill_concept"] = False
    # Never carry a stale Quill-generated premise from another project.
    if snapshot.get("saved_quill_concept") is not None:
        st.session_state["saved_quill_concept"] = snapshot["saved_quill_concept"]
    else:
        st.session_state.pop("saved_quill_concept", None)
    st.session_state['children_publication_layout']=snapshot.get('children_publication_layout')
    st.session_state['publication_layout']=snapshot.get('publication_layout')
    st.session_state.active_format_id = restored_format_id
    st.session_state.format_type = WBS_LEGACY_FORMAT_BY_TEMPLATE_ID[restored_format_id]
    st.session_state.active_format_template = get_wbs_format_template(restored_format_id)
    st.session_state.quill_format_instructions = get_wbs_quill_instructions(restored_format_id)
    st.session_state.quill_format_name = get_wbs_format_display_name(restored_format_id)

    # Restore the Writing Format widget from the saved authoritative template.
    # A keyed Streamlit selectbox ignores its index= argument when an old widget
    # value remains in session_state; without this, it overwrites the loaded format.
    st.session_state["wbs_format_template_selector"] = restored_format_id

    # Restore the actual saved Quill concept before Step 1 constructs its widgets.
    # Clearing widget keys without seeding them again made saved stories look lost.
    clear_concept_widget_state_for_loaded_project()
    st.session_state["wbs_format_template_selector"] = restored_format_id
    saved_concept = str(snapshot.get("saved_quill_concept") or snapshot.get("story_seed") or "")
    saved_mode = str(snapshot.get("version_source_mode") or snapshot.get("starting_source_mode") or "")
    if saved_mode == "Quill Assisted":
        concept_widget_key = f"wbs_quill_starting_concept_{restored_format_id}"
        st.session_state[concept_widget_key] = saved_concept
        st.session_state["_wbs_loaded_quill_concept"] = bool(saved_concept.strip())
        st.session_state.story_seed = saved_concept
        # Never switch a saved Quill-created concept to the saved-manuscript option.
        st.session_state.version_source_mode = "Quill Assisted"
        st.session_state.starting_source_mode = "Quill Assisted"

    st.session_state.project_version_name = clean_project_version_name(
        snapshot.get("project_version_name") or "Original"
    ) or "Original"
    st.session_state.concept_change_areas = list(
        snapshot.get("concept_change_areas") or []
    )

    saved_source_text = str(
        snapshot.get("saved_version_source_text")
        or get_best_saved_manuscript_source(snapshot)
        or ""
    ).strip()
    if saved_source_text:
        st.session_state.saved_version_source_text = saved_source_text
        st.session_state.saved_version_source_name = str(
            snapshot.get("saved_version_source_name")
            or st.session_state.project_version_name
            or "Saved Version"
        ).strip()
        st.session_state.saved_version_source_word_count = count_words(saved_source_text)
        st.session_state.version_source_mode = str(
            snapshot.get("version_source_mode") or "Saved Manuscript"
        )
    else:
        st.session_state.saved_version_source_text = ""
        st.session_state.saved_version_source_name = ""
        st.session_state.saved_version_source_word_count = 0
        st.session_state.version_source_mode = str(
            snapshot.get("version_source_mode")
            or snapshot.get("starting_source_mode")
            or "Custom Plot Line"
        )

    # Start at Concept, but keep the furthest saved workflow milestone unlocked.
    # A saved manuscript can reopen later stages without replaying API generation.
    saved_stage = str(snapshot.get("project_stage") or "Intake")
    saved_export = bool(snapshot.get("export_view"))
    milestones = {"Intake": 1, "Sandbox": 2, "Plot Architect": 3,
                  "Drafting": 4, "Drafting Engine": 4, "Isolation Guardrail": 4,
                  "Revision Engine": 4, "Rewrite Engine": 4}
    saved_max = milestones.get(saved_stage, 1)
    if str(snapshot.get("current_draft_output") or "").strip():
        saved_max = max(saved_max, 4)
    if saved_export or str(snapshot.get("final_output_text") or "").strip():
        saved_max = 5
    st.session_state["_wbs_unlocked_saved_stage"] = saved_max
    st.session_state.project_stage = "Intake"
    st.session_state.export_view = False

    # Establish the baseline after legacy projects have been normalized to the
    # new four-source branching model.
    baseline_snapshot = dict(snapshot)
    baseline_snapshot["version_source_mode"] = st.session_state.version_source_mode
    set_loaded_concept_version_baseline(baseline_snapshot)

    from core.saved_scene_state import remember_saved_snapshot
    remember_saved_snapshot(st.session_state, verified, load_project_id, saved_session_row.get("id"))
    return True


def save_manuscript_version_to_supabase(manuscript_content, version_label="Accepted Rewrite", source_stage="rewrite_engine"):
    user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    project_id = get_active_project_id()

    if not project_id:
        st.error("No active project ID found. Start a new project before saving manuscript versions.")
        return None

    existing_versions = (
        supabase.table("writersblock_manuscript_versions")
        .select("version_number")
        .eq("project_id", project_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if existing_versions.data:
        next_version = int(existing_versions.data[0]["version_number"]) + 1
    else:
        next_version = 1

    result = (
        supabase.table("writersblock_manuscript_versions")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "version_number": next_version,
            "version_label": (
                f"{get_project_title_for_display()} — "
                f"{get_current_project_version_name()} — {version_label}"
            ),
            "manuscript_content": manuscript_content,
            "source_stage": source_stage
        })
        .execute()
    )

    return result
    user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    latest_project = (
        supabase.table("writersblock_projects")
        .select("id")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not latest_project.data:
        st.error("No project found.")
        return None

    project_id = latest_project.data[0]["id"]

    existing_versions = (
        supabase.table("writersblock_manuscript_versions")
        .select("version_number")
        .eq("project_id", project_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if existing_versions.data:
        next_version = int(existing_versions.data[0]["version_number"]) + 1
    else:
        next_version = 1

    result = (
        supabase.table("writersblock_manuscript_versions")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "version_number": next_version,
            "version_label": version_label,
            "manuscript_content": manuscript_content,
            "source_stage": source_stage
        })
        .execute()
    )

    return result



def get_manuscript_version_status_stage(version):
    """Normalize saved-version status/stage for both new and legacy records."""
    label = str((version or {}).get("version_label") or "").strip()
    source_stage = str((version or {}).get("source_stage") or "").strip().lower()
    upper_label = label.upper()

    if "FINAL" in upper_label or source_stage in {"final_output", "manuscript_output_final"}:
        return "FINAL", "Manuscript Output"

    if "SCRIPT REWRITE" in upper_label or source_stage in {"rewrite_engine", "script_rewrite_draft"}:
        return "DRAFT", "Script Rewrite"

    if "CREATIVE DRAFT" in upper_label or source_stage == "creative_draft":
        return "DRAFT", "Creative Draft"

    if "SCRIPT LOCK" in upper_label or "REVIEW CHECKPOINT" in upper_label or source_stage in {"script_lock_review", "script_lock_draft"}:
        return "DRAFT", "Script Lock"

    if "DRAFT" in upper_label:
        return "DRAFT", "Working Draft"

    if source_stage == "existing_manuscript_import":
        return "IMPORTED", "Existing Manuscript"

    return "SAVED", "Manuscript Version"


def save_stage5_lettered_revision(manuscript_text):
    """Append a Stage 5 revision without overwriting an earlier manuscript."""
    project_id = get_active_project_id()
    user_id = get_current_user_id()
    text = str(manuscript_text or '').strip()
    if not project_id or not user_id or not text:
        return None

    title = get_project_title_for_display().strip().casefold()
    saved_items = get_saved_projects_versions_dropdown_items()
    same_title = [item for item in saved_items
                  if str(item.get('label') or '').split(' — V-', 1)[0].strip().casefold() == title]
    # Base version is the most recently selected or generated numbered story version.
    loaded_id = str(st.session_state.get('_wbs_loaded_saved_session_id') or '')
    base = 0
    for item in same_title:
        if loaded_id and str((item.get('row') or {}).get('id') or '') == loaded_id:
            match = re.search(r' — V-(\d+)', item.get('label') or '')
            if match:
                base = int(match.group(1))
            break
    if not base:
        base = max((int(m.group(1)) for item in same_title
                    if (m := re.search(r' — V-(\d+)', item.get('label') or ''))), default=1)

    previous = (supabase.table('writersblock_manuscript_versions')
                .select('version_number, version_label, manuscript_content, source_stage')
                .eq('project_id', project_id).order('version_number', desc=True).execute())
    rows = list(previous.data or [])
    for row in rows:
        if str(row.get('source_stage') or '') == 'script_lock_revision' and str(row.get('manuscript_content') or '').strip() == text:
            return {'status': 'unchanged', 'label': row.get('version_label')}
    existing_labels = [str(row.get('version_label') or '') for row in rows
                       if str(row.get('source_stage') or '') == 'script_lock_revision']
    used = set()
    for label in existing_labels:
        match = re.search(r' — V-' + str(base) + r'([A-Z]+)(?: —|$)', label)
        if match:
            n = 0
            for letter in match.group(1):
                n = n * 26 + ord(letter) - 64
            used.add(n)
    revision_number = max(used, default=0) + 1
    letters = ''
    n = revision_number
    while n:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    tag = f'V-{base}{letters}'
    next_numeric = max((int(row.get('version_number') or 0) for row in rows), default=0) + 1
    label = f'{get_project_title_for_display()} — {tag} — DRAFT — Script Lock'
    result = supabase.table('writersblock_manuscript_versions').insert({
        'project_id': project_id, 'user_id': user_id,
        'version_number': next_numeric, 'version_label': label,
        'manuscript_content': text, 'source_stage': 'script_lock_revision',
    }).execute()
    if not getattr(result, 'data', None):
        return None
    st.session_state.current_manuscript_save_version = next_numeric
    return {'status': 'saved', 'label': tag}


def save_manuscript_checkpoint(status, stage_label, source_stage):
    """Save an explicit DRAFT or FINAL checkpoint as the next numbered manuscript version."""
    manuscript_text = str(st.session_state.get("current_draft_output") or "").strip()

    if not manuscript_text:
        return {"status": "empty", "version_number": None}

    project_id = get_active_project_id()
    user_id = get_current_user_id()

    if not project_id or not user_id:
        return {"status": "missing_project", "version_number": None}

    clean_status = str(status or "DRAFT").strip().upper()
    clean_stage = str(stage_label or "Working Draft").strip()
    clean_source_stage = str(source_stage or "working_draft").strip()

    latest_result = (
        supabase.table("writersblock_manuscript_versions")
        .select("version_number")
        .eq("project_id", project_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if latest_result.data:
        next_version = int(latest_result.data[0].get("version_number") or 0) + 1
    else:
        next_version = 1

    version_label = (
        f"{get_project_title_for_display()} — "
        f"{get_current_project_version_name()} — "
        f"{clean_status} — {clean_stage}"
    )

    result = (
        supabase.table("writersblock_manuscript_versions")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "version_number": next_version,
            "version_label": version_label,
            "manuscript_content": manuscript_text,
            "source_stage": clean_source_stage,
        })
        .execute()
    )

    if result.data:
        st.session_state.manuscript_version = next_version
        st.session_state.current_manuscript_save_status = clean_status
        st.session_state.current_manuscript_save_stage = clean_stage
        st.session_state.current_manuscript_save_version = next_version
        return {"status": "saved", "version_number": next_version}

    return {"status": "failed", "version_number": None}


def save_review_checkpoint_if_needed():
    """Legacy compatibility: treat older review checkpoints as Script Lock drafts."""
    return save_manuscript_checkpoint(
        status="DRAFT",
        stage_label="Script Lock",
        source_stage="script_lock_draft",
    )

def get_active_project_id():
    project_id = st.session_state.get("current_project_id")
    if project_id:
        return project_id

    return None


def get_project_title_from_project_id(project_id):
    if not project_id:
        return ""

    try:
        result = (
            supabase.table("writersblock_projects")
            .select("project_title")
            .eq("id", project_id)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return str(result.data[0].get("project_title") or "").strip()
    except Exception:
        return ""

    return ""



def wbs_saved_project_identity_preflight(saved_row):
    """Read-only preflight before loading an older project-session row.

    A historical session can retain a title from project A while its project_id
    points at project B. Replacing its title with B's database title would show
    the wrong manuscript/project, so fail closed and preserve the active state.
    """
    if not isinstance(saved_row, dict):
        return False, "The selected saved entry is invalid. Nothing was loaded."
    project_id = str(saved_row.get("project_id") or "").strip()
    row_id = str(saved_row.get("id") or "").strip()
    user_id = get_current_user_id()
    if not project_id or not row_id or not user_id:
        return False, "The selected saved entry has no verifiable project identity. Nothing was loaded."
    try:
        snapshot = json.loads(saved_row.get("draft_content") or "{}")
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid snapshot")
        embedded_id = str(snapshot.get("current_project_id") or "").strip()
        if embedded_id and embedded_id != project_id:
            return False, (
                "Saved entry contains two different project IDs. Loading was blocked; "
                "the current project and every saved version remain unchanged."
            )
        saved_title = str(snapshot.get("project_title") or "").strip()
        project_result = (supabase.table("writersblock_projects")
                          .select("id,project_title")
                          .eq("id", project_id).eq("user_id", user_id)
                          .limit(1).execute())
        projects = getattr(project_result, "data", None) or []
        if len(projects) != 1:
            return False, (
                "This saved entry does not have a uniquely verified parent project "
                "for the current user. Loading was blocked; no data was changed."
            )
        parent_title = str(projects[0].get("project_title") or "").strip()
        if not parent_title:
            return False, "The saved entry's parent project has no title. Loading was blocked."
        if not saved_title:
            return False, (
                "The saved project session has no original title to verify. "
                "Loading was blocked; no records were changed."
            )
        if saved_title.casefold() != parent_title.casefold():
            return False, (
                f'Saved entry is titled "{saved_title}" but its database project ID '
                f'belongs to "{parent_title}". This may be a legacy wrong-project '
                "association or a historical rename; it cannot be resolved safely "
                "by changing the displayed title. Loading was blocked, and neither "
                "project was changed."
            )
        # Verify the selected session itself still exists and belongs to the
        # authenticated user and parent; avoid trusting stale selectbox values.
        session_result = (supabase.table("writersblock_project_drafts")
                          .select("id,project_id,draft_type")
                          .eq("id", row_id).eq("user_id", user_id)
                          .eq("project_id", project_id)
                          .eq("draft_type", "project_session")
                          .limit(1).execute())
        sessions = getattr(session_result, "data", None) or []
        if len(sessions) != 1:
            return False, "The saved entry could not be verified against its project. Loading was blocked."
        return True, ""
    except (ValueError, TypeError, KeyError):
        return False, "Saved entry metadata is invalid; load cancelled without changes."
    except Exception:
        return False, (
            "Could not verify this saved entry with the database. "
            "Loading was blocked to protect existing projects."
        )


def get_projects_for_import():
    user_id = get_current_user_id()

    if not user_id:
        return []

    query = (
        supabase.table("writersblock_projects")
        .select("id, user_id, project_title, project_type, created_at")
        .order("created_at", desc=True)
    )

    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()
    return result.data or []


def get_latest_series_metadata_for_project(project_id):
    if not project_id:
        return {}

    query = (
        supabase.table("writersblock_project_drafts")
        .select("draft_content, created_at")
        .eq("project_id", project_id)
        .eq("draft_type", "series_metadata")
        .order("created_at", desc=True)
        .limit(1)
    )

    result = query.execute()

    if not result.data:
        return {}

    try:
        metadata = json.loads(result.data[0].get("draft_content") or "{}")
    except Exception:
        return {}

    return metadata if isinstance(metadata, dict) else {}


def extract_uploaded_manuscript_text(uploaded_file):
    if uploaded_file is None:
        return ""

    filename = str(getattr(uploaded_file, "name", "") or "").lower()
    file_bytes = uploaded_file.getvalue()

    if filename.endswith(".docx"):
        document = Document(BytesIO(file_bytes))
        paragraphs = []

        for paragraph in document.paragraphs:
            paragraph_text = str(paragraph.text or "").strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)

        for table in document.tables:
            for row in table.rows:
                cell_values = []
                for cell in row.cells:
                    cell_text = str(cell.text or "").strip()
                    if cell_text:
                        cell_values.append(cell_text)
                if cell_values:
                    paragraphs.append(" | ".join(cell_values))

        return "\n\n".join(paragraphs).strip()

    if filename.endswith(".txt"):
        return file_bytes.decode("utf-8-sig", errors="replace").strip()

    raise ValueError("Only DOCX and TXT manuscript files are supported.")


def build_imported_project_snapshot(
    project_id,
    project_title,
    project_type,
    manuscript_text,
    version_number,
):
    series_metadata = get_latest_series_metadata_for_project(project_id)
    is_series_book = bool(
        str(series_metadata.get("series_name") or "").strip()
        and int(series_metadata.get("series_book_number") or 0) > 0
    )

    saved_at = datetime.now(timezone.utc).isoformat()

    return {
        "project_stage": "Isolation Guardrail",
        "story_seed": "",
        "project_title": str(project_title or "Untitled Project").strip(),
        "project_scope": "Book in a Series" if is_series_book else "Standalone Book",
        "series_key": str(series_metadata.get("series_key") or ""),
        "series_name": str(series_metadata.get("series_name") or ""),
        "series_book_number": int(series_metadata.get("series_book_number") or 1),
        "series_continuity_mode": str(
            series_metadata.get("series_continuity_mode") or "Strict"
        ),
        "series_reference_ids": list(
            series_metadata.get("series_reference_ids") or []
        ),
        "series_canon_notes": str(
            series_metadata.get("series_canon_notes") or ""
        ),
        "series_selection_signature": (
            f"{series_metadata.get('series_key', '')}:"
            f"{int(series_metadata.get('series_book_number') or 1)}"
            if is_series_book else ""
        ),
        "format_type": str(project_type or "Audio Book"),
        "dialogue_style": "Story-Driven / Automatic",
        "audiobook_length": "30 Minutes",
        "audiobook_target_word_count": max(4000, count_words(manuscript_text)),
        "audiobook_production_script": "",
        "audiobook_production_source_signature": "",
        "audiobook_production_cue_level": "Voices + Minimal SFX",
        "audiobook_production_preview_id": 0,
        "tone_style": "Gritty Noir Mystery",
        "author_style": "",
        "sandbox_slates": None,
        "chosen_option": None,
        "chosen_option_text": None,
        "plot_outline": None,
        "current_draft_output": manuscript_text,
        "rolling_lore_book": "",
        "completed_beats": [],
        "scene_blocks": {},
        "current_processing_beat": 1,
        "manuscript_version": int(version_number or 1),
        "rewritten_manuscript": "",
        "rewrite_applied_message": "Imported completed manuscript loaded.",
        "rewrite_preview_id": 0,
        "rewrite_target_length": "Keep Current Length",
        "revision_report": "",
        "export_view": True,
        "picture_book_page_size": "8.5 x 8.5 Square",
        "current_project_id": project_id,
        "saved_at": saved_at,
    }


def import_existing_manuscript_to_supabase(
    project_id,
    project_title,
    project_type,
    manuscript_text,
):
    user_id = get_current_user_id()

    if not user_id:
        raise ValueError("No WritersBlock user was found.")

    if not project_id:
        raise ValueError("Select the project that should receive the manuscript.")

    clean_title = str(project_title or "").strip()
    clean_manuscript = str(manuscript_text or "").strip()

    if not clean_title:
        raise ValueError("Enter the project title.")

    if not clean_manuscript:
        raise ValueError("The selected manuscript file contains no readable text.")

    supabase.table("writersblock_projects").update({
        "project_title": clean_title,
        "project_type": str(project_type or "Audio Book"),
        "project_status": "active",
    }).eq("id", project_id).execute()

    existing_versions = (
        supabase.table("writersblock_manuscript_versions")
        .select("version_number")
        .eq("project_id", project_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if existing_versions.data:
        next_version = int(existing_versions.data[0].get("version_number") or 0) + 1
    else:
        next_version = 1

    manuscript_result = (
        supabase.table("writersblock_manuscript_versions")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "version_number": next_version,
            "version_label": f"{clean_title} — Imported Completed Manuscript",
            "manuscript_content": clean_manuscript,
            "source_stage": "existing_manuscript_import",
        })
        .execute()
    )

    if not manuscript_result.data:
        raise RuntimeError("The manuscript version was not saved.")

    snapshot = build_imported_project_snapshot(
        project_id=project_id,
        project_title=clean_title,
        project_type=project_type,
        manuscript_text=clean_manuscript,
        version_number=next_version,
    )

    session_result = (
        supabase.table("writersblock_project_drafts")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "draft_title": "Saved Project Session",
            "draft_type": "project_session",
            "draft_content": json.dumps(snapshot),
            "version_number": next_version,
        })
        .execute()
    )

    if not session_result.data:
        raise RuntimeError("The project session was not saved.")

    return snapshot



def ensure_project_title_loaded():
    if get_project_title():
        return True

    project_id = st.session_state.get("current_project_id")
    title_from_project = get_project_title_from_project_id(project_id)

    if title_from_project:
        st.session_state.project_title = title_from_project
        return True

    return False


def get_all_manuscript_versions_for_user():
    user_id = get_current_user_id()

    if not user_id:
        return []

    query = (
        supabase.table("writersblock_manuscript_versions")
        .select("id, version_number, version_label, manuscript_content, source_stage, created_at, project_id, user_id, writersblock_projects(project_title)")
        .order("created_at", desc=False)
    )

    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()
    return result.data or []


def get_manuscript_versions_for_current_project():
    project_id = st.session_state.get("current_project_id")
    user_id = get_current_user_id()

    if not user_id:
        return []

    if not project_id:
        return []

    query = (
        supabase.table("writersblock_manuscript_versions")
        .select("id, version_number, version_label, manuscript_content, source_stage, created_at, project_id, user_id, writersblock_projects(project_title)")
        .eq("project_id", project_id)
        .order("created_at", desc=False)
    )

    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()
    return result.data or []


def delete_manuscript_version_ids(version_ids):
    deleted_count = 0

    for version_id in version_ids:
        if not version_id:
            continue

        supabase.table("writersblock_manuscript_versions").delete().eq("id", version_id).execute()
        deleted_count += 1

    return deleted_count


def remove_duplicate_manuscript_versions_for_current_project():
    versions = get_manuscript_versions_for_current_project()
    seen = {}
    delete_ids = []

    sorted_versions = sorted(
        versions,
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    for version in sorted_versions:
        content_key = re.sub(r"\s+", " ", str(version.get("manuscript_content") or "").strip())

        if not content_key:
            delete_ids.append(version.get("id"))
            continue

        if content_key in seen:
            delete_ids.append(version.get("id"))
        else:
            seen[content_key] = version.get("id")

    return delete_manuscript_version_ids(delete_ids)


def purge_old_manuscript_versions_for_current_project(keep_latest_count=3):
    versions = get_manuscript_versions_for_current_project()

    sorted_versions = sorted(
        versions,
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    keep_latest_count = max(1, int(keep_latest_count or 3))
    delete_ids = [version.get("id") for version in sorted_versions[keep_latest_count:]]

    return delete_manuscript_version_ids(delete_ids)

st.markdown(
    """
    <style>
[data-testid="stMainBlockContainer"] {
    max-width: 1500px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
    div[role="radiogroup"] label {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #dddddd !important;
        border-radius: 6px !important;
        padding: 8px 10px !important;
        margin-bottom: 8px !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
    }

    div[role="radiogroup"] label p {
        color: #000000 !important;
        margin: 0 !important;
    }

    div[role="radiogroup"] label span {
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# WBS_UNIVERSAL_SELECT_VISUAL_20261029 — presentation only; no selectbox logic changed.
st.markdown("""<style>
/* All Streamlit single-select dropdowns: arrow points up while closed, down while open. */
[data-testid="stSelectbox"] [role="combobox"] svg:last-child,
[data-testid="stSelectbox"] [data-baseweb="select"] svg:last-child {
    transition: transform 140ms ease !important;
}
[data-testid="stSelectbox"] [role="combobox"][aria-expanded="false"] svg:last-child {
    transform: rotate(180deg) !important;
}
[data-testid="stSelectbox"] [role="combobox"][aria-expanded="true"] svg:last-child {
    transform: rotate(0deg) !important;
}
/* The dropdown list is visibly separated from its field. */
[data-baseweb="popover"]:has([role="listbox"]) {
    margin-top: 8px !important;
    filter: drop-shadow(0 6px 12px rgba(0,0,0,.35));
}
[data-baseweb="popover"] [role="listbox"] {
    border: 1px solid rgba(180,194,215,.55) !important;
    border-radius: 7px !important;
}
</style>""", unsafe_allow_html=True)

# WBS_20261023_MANUSCRIPT_TEXT_CONTRAST
st.markdown("""<style>
[data-testid="stTextArea"] textarea { color:#f7f9ff !important; -webkit-text-fill-color:#f7f9ff !important; background-color:#222632 !important; opacity:1 !important; }
[data-testid="stTextArea"] textarea:disabled { color:#f7f9ff !important; -webkit-text-fill-color:#f7f9ff !important; opacity:1 !important; }
</style>""", unsafe_allow_html=True)

# WBS_SKIP_REWRITE_RED_POSITION_2026_09_08
st.markdown(
    """
    <style>
    .st-key-skip_rewrite_to_final_output button {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
    }
    .st-key-skip_rewrite_to_final_output button:hover {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# WBS_PROJECT_INTEGRITY_UI_STYLING_2026_10_04
st.markdown(
    """
    <style>
    .st-key-run_project_integrity_final_review button {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    .st-key-run_project_integrity_final_review button:hover {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
    }
    .wbs-integrity-report {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 16px 18px;
        margin-top: 8px;
        margin-bottom: 8px;
    }
    .wbs-integrity-report .wbs-ir-section {
        margin-top: 14px;
    }
    .wbs-integrity-report .wbs-ir-section:first-child {
        margin-top: 0;
    }
    .wbs-integrity-report .wbs-ir-heading {
        color: #ffffff;
        font-size: 0.98rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        margin-bottom: 8px;
    }
    .wbs-integrity-report .wbs-ir-status {
        color: #ffffff;
        font-size: 1rem;
        font-weight: 800;
        margin-bottom: 12px;
    }
    .wbs-integrity-report .wbs-ir-p,
    .wbs-integrity-report .wbs-ir-bullet,
    .wbs-integrity-report .wbs-ir-number {
        color: #f5f7fb;
        font-size: 0.96rem;
        line-height: 1.58;
        margin-bottom: 6px;
        white-space: pre-wrap;
    }
    .wbs-integrity-report .wbs-ir-bullet {
        padding-left: 14px;
        text-indent: -12px;
    }
    .wbs-integrity-report .wbs-ir-number {
        padding-left: 2px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# BACKEND INITIALIZATION
# ==========================================
# Load local environment variables BEFORE constructing GeminiWriterBackend so
# GEMINI_API_KEY from the Integration-Test .env is available at backend startup.
from core.runtime_startup import load_local_environment, customer_backend
load_local_environment()
try:
    customer_backend(st.session_state, st.secrets)
except ValueError:
    st.error("Writing service configuration is invalid. Contact the application owner.")
    st.stop()

# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
# ==========================================
# SYSTEM STATE INITIALIZATION
# ==========================================
if "project_stage" not in st.session_state:
    st.session_state.project_stage = "Intake"

if "story_seed" not in st.session_state or not str(st.session_state.story_seed).strip():
    st.session_state.story_seed = ""

if "starting_source_mode" not in st.session_state:
    st.session_state.starting_source_mode = "Story Idea"

if "version_source_mode" not in st.session_state:
    st.session_state.version_source_mode = "Custom Plot Line"

if "saved_version_source_text" not in st.session_state:
    st.session_state.saved_version_source_text = ""

if "saved_version_source_name" not in st.session_state:
    st.session_state.saved_version_source_name = ""

if "saved_version_source_word_count" not in st.session_state:
    st.session_state.saved_version_source_word_count = 0

if "imported_source_text" not in st.session_state:
    st.session_state.imported_source_text = ""

if "imported_source_name" not in st.session_state:
    st.session_state.imported_source_name = ""

if "imported_source_word_count" not in st.session_state:
    st.session_state.imported_source_word_count = 0

if "project_title" not in st.session_state:
    st.session_state.project_title = ""

if "project_scope" not in st.session_state:
    st.session_state.project_scope = "Standalone Book"

if "series_key" not in st.session_state:
    st.session_state.series_key = ""

if "series_name" not in st.session_state:
    st.session_state.series_name = ""

if "series_book_number" not in st.session_state:
    st.session_state.series_book_number = 1

if "series_continuity_mode" not in st.session_state:
    st.session_state.series_continuity_mode = "Strict"

if "series_reference_ids" not in st.session_state:
    st.session_state.series_reference_ids = []

if "series_canon_notes" not in st.session_state:
    st.session_state.series_canon_notes = ""

if "series_selection_signature" not in st.session_state:
    st.session_state.series_selection_signature = ""

if "format_type" not in st.session_state:
    st.session_state.format_type = "Novel / Prose"

# Migrate projects saved under earlier format labels.
if st.session_state.get("format_type") == "Audio Short Story — 15–30 min":
    st.session_state.format_type = "Audio Book"

if st.session_state.get("format_type") == "Children's Storybook (32-Page Writing Layout)":
    st.session_state.format_type = "Children's Picture Book (32-Page Layout)"

# ==========================================
# WRITERSBLOCK FORMAT TEMPLATE ROUTING
# ==========================================
# `active_format_id` is the authoritative template selection. `format_type` is
# retained as a compatibility value for the existing writing engine until each
# dedicated format page is connected in the next integration stage.
WBS_LEGACY_FORMAT_BY_TEMPLATE_ID = {
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

WBS_TEMPLATE_ID_BY_LEGACY_FORMAT = {
    "Short Story": "short_story",
    "Novel / Prose": "novel_prose_novella",
    "Novella": "novel_prose_novella",
    "Screenplay Outline": "screenplay",
    "Stage Play / Dramatic Script": "stage_play",
    "Audio Book": "audiobook",
    "Children's Picture Book (32-Page Layout)": "childrens_picture_book",
    "Full Novel Blueprint": "full_novel_blueprint",
    "YouTube Shorts": "youtube_shorts",
    "Podcast Script": "podcast_script",
    "Standard Manuscript": "standard_manuscript",
}

# Additive registration for the two independent workspaces.
for _new_format_id in ("biography_memoir", "childrens_interactive_educational"):
    WBS_LEGACY_FORMAT_BY_TEMPLATE_ID[_new_format_id] = FORMAT_LEGACY[_new_format_id]
    WBS_TEMPLATE_ID_BY_LEGACY_FORMAT[FORMAT_LEGACY[_new_format_id]] = _new_format_id

WBS_FORMAT_IDS = [format_id for format_id, _label in WBS_FORMAT_OPTIONS]

if "active_format_id" not in st.session_state:
    st.session_state.active_format_id = WBS_TEMPLATE_ID_BY_LEGACY_FORMAT.get(
        str(st.session_state.get("format_type") or "Novel / Prose"),
        "novel_prose_novella",
    )

if st.session_state.get("active_format_id") not in WBS_FORMAT_IDS:
    st.session_state.active_format_id = "novel_prose_novella"
    st.session_state.format_template_values = {}

# Make the active template and its Quill rules available to the shared Quill
# panel on every stage. These values are refreshed again by the top selector.
st.session_state.active_format_template = get_wbs_format_template(
    st.session_state.active_format_id
)
st.session_state.quill_format_instructions = get_wbs_quill_instructions(
    st.session_state.active_format_id
)
st.session_state.quill_format_name = get_wbs_format_display_name(
    st.session_state.active_format_id
)

if "format_template_values" not in st.session_state or not isinstance(
    st.session_state.get("format_template_values"), dict
):
    st.session_state.format_template_values = {}


def get_active_format_widget_key(field_key):
    """Bind each development widget to the exact saved revision being edited.

    Project+format isolation alone is insufficient: V-1 and V-2 share those
    identifiers, so Streamlit can reuse V-2's live widget value after loading
    V-1 even though the V-1 snapshot itself was restored. The immutable saved
    session row ID keeps their widget states separate without changing any
    stored project data or calling the save API.
    """
    if not st.session_state.get("_wbs_draft_scope_id"):
        st.session_state._wbs_draft_scope_id = uuid.uuid4().hex[:12]
    saved_revision_id = str(
        st.session_state.get("_wbs_active_saved_session_row_id")
        or st.session_state.get("_wbs_loaded_saved_session_id")
        or ""
    ).strip()
    # Unsaved work uses its own fresh draft scope; the saved revision ID only
    # appears in widget keys, never in format-template values or manuscript text.
    revision_scope = saved_revision_id or "draft_" + st.session_state._wbs_draft_scope_id
    return project_format_widget_key(
        st.session_state.get("current_project_id"),
        st.session_state._wbs_draft_scope_id,
        st.session_state.get("active_format_id"),
        f"{field_key}__revision_{revision_scope}",
    )


def get_active_format_template_values():
    format_id = str(st.session_state.get("active_format_id") or "novel_prose_novella")
    all_values = st.session_state.get("format_template_values") or {}
    values = all_values.get(format_id) or {}
    return values if isinstance(values, dict) else {}


def set_active_format_template_value(field_key, value):
    format_id = str(st.session_state.get("active_format_id") or "novel_prose_novella")
    all_values = dict(st.session_state.get("format_template_values") or {})
    values = dict(all_values.get(format_id) or {})
    values[str(field_key)] = value
    all_values[format_id] = values
    st.session_state.format_template_values = all_values


def get_development_writing_tense():
    """Read the Stage 1 tense consistently for every writing format."""
    values = get_active_format_template_values()
    template = st.session_state.get("active_format_template") or {}
    fields = template.get("concept_fields") or []
    tense_keys = {str(f.get("key") or "") for f in fields
                  if isinstance(f, dict) and "tense" in
                  (str(f.get("key") or "") + " " + str(f.get("label") or "")).lower()}
    for key, value in values.items():
        if st.session_state.get('active_format_id')=='childrens_picture_book' and key in {'page_turn_source','page_turn_legacy_structure'}:continue
        if "tense" in str(key).lower() or key in tense_keys:
            text = str(value or "").strip()
            if text and ("present" in text.lower() or "past" in text.lower()):
                return "Present Tense" if "present" in text.lower() else "Past Tense"
    for key in ("writing_tense", "narrative_tense", "story_tense", "tense"):
        text = str(st.session_state.get(key) or "").strip()
        if "present" in text.lower():
            return "Present Tense"
        if "past" in text.lower():
            return "Past Tense"
    # Retain the former Stage 4 default only for older saved projects with no tense selection.
    return "Past Tense"


def get_active_concept_ui():
    template = st.session_state.get("active_format_template") or {}
    ui = template.get("concept_ui") or {}
    return ui if isinstance(ui, dict) else {}


def format_field_should_render(field, values):
    """Return True when a format field's optional conditional rule is satisfied."""
    condition = field.get("show_if") if isinstance(field, dict) else None
    if not isinstance(condition, dict) or not condition:
        return True
    for condition_key, allowed_values in condition.items():
        current = values.get(condition_key)
        if not isinstance(allowed_values, (list, tuple, set)):
            allowed_values = [allowed_values]
        if current not in allowed_values:
            return False
    return True


def get_active_format_development_context():
    template = st.session_state.get("active_format_template") or {}
    values = get_active_format_template_values()
    if not values and st.session_state.get('active_format_id')!='novel_prose_novella':
        return ""

    labels = {
        str(field.get("key")): str(field.get("label") or field.get("key"))
        for field in (template.get("concept_fields") or [])
        if isinstance(field, dict)
    }
    lines = [
        "ACTIVE WRITING FORMAT DEVELOPMENT REQUIREMENTS",
        f"Writing Format: {template.get('display_name') or st.session_state.get('quill_format_name') or ''}",
    ]
    if st.session_state.get('active_format_id') != 'short_story':
        from core.manuscript_structure import profile
        lines.append('Format organization: '+profile(st.session_state['active_format_id'])['description'])
    if st.session_state.get('active_format_id')=='novel_prose_novella':
        from formats.novel_prose_novella.work_type import guidance
        lines.append(guidance(st.session_state))
    for key, value in values.items():
        if st.session_state.get('active_format_id')=='novel_prose_novella' and key=='book_scale':
            continue  # Retained legacy metadata; Work Type is authoritative.
        if value is None or str(value).strip() == "":
            continue
        lines.append(f"{labels.get(str(key), str(key))}: {value}")
    return "\n".join(lines).strip()


def get_full_project_continuity_context():
    """Bounded, shared creative reference for all WBS production stages.

    Read-only: user-approved state always takes priority over old drafts.
    """
    state = st.session_state
    title = str(state.get("project_title") or "").strip()
    original = str(state.get("wbs_project_original_concept") or "").strip()
    if not original:
        original = str(state.get("story_seed") or "").strip()
    sections = [
        "PROJECT CONTINUITY — apply at every creative stage",
        "Preserve the original creative premise and all established names, events, setting, tone, POV, and chronology unless the writer explicitly approves a change. The latest writer-approved direction takes precedence over older planning notes. Do not automatically rewrite existing approved manuscript text.",
        f"Project title: {title or 'Untitled'}",
        f"Current stage: {state.get('project_stage') or ''}",
        f"Format: {state.get('quill_format_name') or state.get('format_type') or ''}",
        "DEVELOPMENT SETUP:\n" + get_active_format_development_context()[:8500],
        "ORIGINAL CREATIVE PREMISE:\n" + original[:5500],
    ]
    latest = str(state.get("story_seed") or "").strip()
    if latest and latest != original:
        sections.append("LATEST APPROVED CONCEPT:\n" + latest[:5500])
    for key, label, limit in (
        ("chosen_option_text", "WRITER-SELECTED STORY PATH", 5500),
        ("plot_outline", "APPROVED PLOT ARCHITECTURE", 7500),
        ("rolling_lore_book", "ESTABLISHED CONTINUITY / LORE", 6500),
    ):
        value = state.get(key)
        if value:
            if not isinstance(value, str):
                try:
                    value = json.dumps(value, ensure_ascii=False)
                except (TypeError, ValueError):
                    value = str(value)
            sections.append(label + ":\n" + value[:limit])
    draft = str(state.get("current_draft_output") or "").strip()
    if draft:
        sections.append("CURRENT WRITER-APPROVED DRAFT (RECENT EXCERPT, reference only; do not overwrite):\n" + draft[-4500:])
    return "\n\n".join(sections)


def refresh_quill_template_context():
    """Publish every active center-panel direction to Quill and the model bridge."""
    template = st.session_state.get("active_format_template") or {}
    values = get_active_format_template_values()
    st.session_state.active_format_development_context = get_active_format_development_context()
    st.session_state.wbs_quill_continuity_context = get_full_project_continuity_context()
    st.session_state.quill_template_context = {
        "active_format_id": str(st.session_state.get("active_format_id") or ""),
        "writing_format": str(template.get("display_name") or st.session_state.get("quill_format_name") or ""),
        "format_instructions": str(st.session_state.get("quill_format_instructions") or ""),
        "development_fields": dict(values),
        "project_continuity": st.session_state.wbs_quill_continuity_context,
        "project_title": str(st.session_state.get("project_title") or ""),
        "project_scope": str(st.session_state.get("project_scope") or ""),
        "series_name": str(st.session_state.get("series_name") or ""),
        "series_number": st.session_state.get("series_book_number"),
        "dialogue_style": str(st.session_state.get("dialogue_style") or ""),
        "tone_style": str(st.session_state.get("tone_style") or ""),
        "production_influence": str(values.get("production_influence_custom") or values.get("production_influence") or ""),
        "visual_style": str(values.get("visual_style") or ""),
        "narration_type": str(values.get("narration_type") or ""),
        "episode_format": str(values.get("episode_format") or ""),
    }
    return st.session_state.quill_template_context


def render_active_format_development_fields():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('render_active_format_development_fields', globals())



from formats.common.concept import wbs_concept_contains_editorial_commentary


def render_format_template_save_reminder():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('render_format_template_save_reminder', globals())


if "project_version_name" not in st.session_state:
    st.session_state.project_version_name = "Original"

if "concept_change_areas" not in st.session_state:
    st.session_state.concept_change_areas = []

if "quill_starting_direction" not in st.session_state:
    st.session_state.quill_starting_direction = ""

if "dialogue_style" not in st.session_state:
    st.session_state.dialogue_style = "Story-Driven / Automatic"

if "audiobook_length" not in st.session_state:
    st.session_state.audiobook_length = "30 Minutes"

if "audiobook_target_word_count" not in st.session_state:
    st.session_state.audiobook_target_word_count = 4000

if "audiobook_production_script" not in st.session_state:
    st.session_state.audiobook_production_script = ""

if "audiobook_production_source_signature" not in st.session_state:
    st.session_state.audiobook_production_source_signature = ""

if "audiobook_production_cue_level" not in st.session_state:
    st.session_state.audiobook_production_cue_level = "Voices + Minimal SFX"

if "audiobook_production_preview_id" not in st.session_state:
    st.session_state.audiobook_production_preview_id = 0

if "tone_style" not in st.session_state:
    st.session_state.tone_style = "Gritty Noir Mystery"

if "author_style" not in st.session_state:
    st.session_state.author_style = ""

if "sandbox_slates" not in st.session_state:
    st.session_state.sandbox_slates = None

if "chosen_option" not in st.session_state:
    st.session_state.chosen_option = None

if "chosen_option_text" not in st.session_state:
    st.session_state.chosen_option_text = None

if "plot_outline" not in st.session_state:
    st.session_state.plot_outline = None

if "current_draft_output" not in st.session_state:
    st.session_state.current_draft_output = ""

if "rolling_lore_book" not in st.session_state:
    st.session_state.rolling_lore_book = ""

if "completed_beats" not in st.session_state:
    st.session_state.completed_beats = []

if "scene_blocks" not in st.session_state:
    st.session_state.scene_blocks = {}

if "current_processing_beat" not in st.session_state:
    st.session_state.current_processing_beat = 1

if "manuscript_version" not in st.session_state:
    st.session_state.manuscript_version = 0

if "current_manuscript_save_status" not in st.session_state:
    st.session_state.current_manuscript_save_status = ""

if "current_manuscript_save_stage" not in st.session_state:
    st.session_state.current_manuscript_save_stage = ""

if "current_manuscript_save_version" not in st.session_state:
    st.session_state.current_manuscript_save_version = 0

if "rewrite_applied_message" not in st.session_state:
    st.session_state.rewrite_applied_message = ""

if "rewritten_manuscript" not in st.session_state:
    st.session_state.rewritten_manuscript = ""

if "rewrite_preview_id" not in st.session_state:
    st.session_state.rewrite_preview_id = 0

if "rewrite_target_length" not in st.session_state:
    st.session_state.rewrite_target_length = "Keep Current Length"

if "licensed_mode" not in st.session_state:
    st.session_state.licensed_mode = False

if "licensed_email" not in st.session_state:
    st.session_state.licensed_email = ""

if "licensed_user_row" not in st.session_state:
    st.session_state.licensed_user_row = None

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = False

if "demo_access_code" not in st.session_state:
    st.session_state.demo_access_code = ""

if "demo_email" not in st.session_state:
    st.session_state.demo_email = ""

if "demo_user_row" not in st.session_state:
    st.session_state.demo_user_row = None

if "access_success_message" not in st.session_state:
    st.session_state.access_success_message = ""

if "export_view" not in st.session_state:
    st.session_state.export_view = False

if "final_output_format" not in st.session_state:
    st.session_state.final_output_format = ""

if "final_output_text" not in st.session_state:
    st.session_state.final_output_text = ""

if "final_output_source_signature" not in st.session_state:
    st.session_state.final_output_source_signature = ""

if "final_output_preview_id" not in st.session_state:
    st.session_state.final_output_preview_id = 0

if "final_output_saved_signature" not in st.session_state:
    st.session_state.final_output_saved_signature = ""

if "project_integrity_report" not in st.session_state:
    st.session_state.project_integrity_report = ""

if "project_integrity_source_signature" not in st.session_state:
    st.session_state.project_integrity_source_signature = ""

if "project_integrity_status" not in st.session_state:
    st.session_state.project_integrity_status = ""

if "show_saved_version_manager" not in st.session_state:
    st.session_state.show_saved_version_manager = False

if "project_saved_notice" not in st.session_state:
    st.session_state.project_saved_notice = False

if "picture_book_layout_spreads" not in st.session_state:
    st.session_state.picture_book_layout_spreads = []

if "picture_book_layout_source_signature" not in st.session_state:
    st.session_state.picture_book_layout_source_signature = ""

if "picture_book_layout_preview_id" not in st.session_state:
    st.session_state.picture_book_layout_preview_id = 0

if "picture_book_page_size" not in st.session_state:
    st.session_state.picture_book_page_size = "8.5 x 8.5 Square"

from core.text import count_words


from core.text import get_text_signature


from core.text import safe_download_stem


PICTURE_BOOK_FORMAT = "Children's Picture Book (32-Page Layout)"
PICTURE_BOOK_LAYOUT_TEMPLATES = [
    "Full Illustration — Text Top",
    "Full Illustration — Text Bottom",
    "Text Left — Illustration Right",
    "Illustration Left — Text Right",
    "Two-Page Illustration — Text Overlay",
    "Spot Illustration — Open Text Area",
]

PICTURE_BOOK_PAGE_SIZES = {'8.5 x 8.5 Square': {'page_width': 8.5, 'page_height': 8.5, 'spread_aspect': '17.0 / 8.5', 'trim_reference': '8.5 x 8.5 Square planning layout'}, '10 x 8 Landscape': {'page_width': 10, 'page_height': 8, 'spread_aspect': '20 / 8', 'trim_reference': '10 x 8 Landscape planning layout'}, '7 x 7 Square': {'page_width': 7, 'page_height': 7, 'spread_aspect': '14 / 7', 'trim_reference': '7 x 7 Square planning layout'}, '8 x 8 Square': {'page_width': 8, 'page_height': 8, 'spread_aspect': '16 / 8', 'trim_reference': '8 x 8 Square planning layout'}, '8.25 x 8.25 Square': {'page_width': 8.25, 'page_height': 8.25, 'spread_aspect': '16.5 / 8.25', 'trim_reference': '8.25 x 8.25 Square planning layout'}, '8 x 10 Portrait': {'page_width': 8, 'page_height': 10, 'spread_aspect': '16 / 10', 'trim_reference': '8 x 10 Portrait planning layout'}, '8.5 x 11 Letter': {'page_width': 8.5, 'page_height': 11, 'spread_aspect': '17.0 / 11', 'trim_reference': '8.5 x 11 Letter planning layout'}, '6 x 9 Portrait': {'page_width': 6, 'page_height': 9, 'spread_aspect': '12 / 9', 'trim_reference': '6 x 9 Portrait planning layout'}, '7 x 10 Portrait': {'page_width': 7, 'page_height': 10, 'spread_aspect': '14 / 10', 'trim_reference': '7 x 10 Portrait planning layout'}, '11 x 8.5 Landscape': {'page_width': 11, 'page_height': 8.5, 'spread_aspect': '22 / 8.5', 'trim_reference': '11 x 8.5 Landscape planning layout'}, 'A4 Portrait (210 x 297 mm)': {'page_width': 8.267716535433072, 'page_height': 11.692913385826772, 'spread_aspect': '16.535433070866144 / 11.692913385826772', 'trim_reference': 'A4 Portrait (210 x 297 mm) planning layout'}}

DEFAULT_PICTURE_BOOK_PAGE_SIZE = "8.5 x 8.5 Square"


def get_picture_book_page_size_spec(page_size_name=None):
    selected = str(
        page_size_name
        or st.session_state.get("picture_book_page_size")
        or DEFAULT_PICTURE_BOOK_PAGE_SIZE
    )
    return PICTURE_BOOK_PAGE_SIZES.get(
        selected,
        PICTURE_BOOK_PAGE_SIZES[DEFAULT_PICTURE_BOOK_PAGE_SIZE],
    )


def is_picture_book_project():
    return str(st.session_state.get("format_type") or "") == PICTURE_BOOK_FORMAT


# WBS_PICTURE_BOOK_FOUR_BEAT_WORD_BUDGET_2026_10_24
PICTURE_BOOK_BEAT_WEIGHTS = (0.20, 0.25, 0.30, 0.25)

def picture_book_age_budget_rules():
    """Age-led manuscript target and hard maximum; custom ranges use upper age."""
    values = get_active_format_template_values()
    age_text = " ".join(
        str(v) for k, v in values.items()
        if "age" in str(k).lower() and str(v or "").strip()
    )
    match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", age_text)
    if match:
        lower, upper = map(int, match.groups())
        if lower > upper:
            lower, upper = upper, lower
        if (lower, upper) == (2, 5):
            return 250, 400, f"{lower}–{upper}"
        if (lower, upper) == (3, 8):
            return 450, 600, f"{lower}–{upper}"
        if (lower, upper) == (5, 9):
            return 600, 800, f"{lower}–{upper}"
        if upper <= 5:
            return 250, 400, f"{lower}–{upper}"
        if upper <= 8:
            return 450, 600, f"{lower}–{upper}"
        return 600, 800, f"{lower}–{upper}"
    return 450, 600, "not selected (3–8 default)"


def picture_book_age_suggested_target():
    return picture_book_age_budget_rules()[0]


def picture_book_target():
    """Read the age-limited target without mutating an instantiated widget."""
    default, maximum, age_label = picture_book_age_budget_rules()
    signature = str(age_label)
    if st.session_state.get("_wbs_picture_book_budget_age") != signature:
        # Age selection changed: compute the new age-appropriate target.
        # Initialization occurs in render_picture_book_budget, before input creation.
        return default
    try:
        value = int(st.session_state.get("picture_book_word_target") or default)
    except (ValueError, TypeError):
        value = default
    return max(100, min(maximum, value))

def picture_book_allocations():
    total = picture_book_target()
    a = [int(total * w) for w in PICTURE_BOOK_BEAT_WEIGHTS[:3]]
    return a + [total - sum(a)]

def render_picture_book_budget(location='', editable=False):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('render_picture_book_budget', globals(), location, editable)

def render_picture_book_template_preview(template_name, page_size_name=None):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('render_picture_book_template_preview', globals(), template_name, page_size_name)


def normalize_picture_book_spreads(layout_data):
    """Return exactly 16 editable spread records covering a 32-page layout draft."""
    if isinstance(layout_data, dict):
        raw_spreads = layout_data.get("spreads") or []
    elif isinstance(layout_data, list):
        raw_spreads = layout_data
    else:
        raw_spreads = []

    normalized = []
    for idx in range(16):
        raw = raw_spreads[idx] if idx < len(raw_spreads) and isinstance(raw_spreads[idx], dict) else {}
        page_start = idx * 2 + 1
        page_end = page_start + 1
        template = str(raw.get("template") or PICTURE_BOOK_LAYOUT_TEMPLATES[0]).strip()
        if template not in PICTURE_BOOK_LAYOUT_TEMPLATES:
            template = PICTURE_BOOK_LAYOUT_TEMPLATES[0]

        normalized.append({
            "spread_number": idx + 1,
            "pages": f"{page_start}-{page_end}",
            "template": template,
            "story_text": str(raw.get("story_text") or "").strip(),
            "illustration_direction": str(raw.get("illustration_direction") or raw.get("illustration_prompt") or "").strip(),
        })

    return normalized


def build_picture_book_spreads_locally(manuscript_text):
    """Split the completed manuscript into 16 editable spreads without any AI/API call."""
    text = re.sub(r"\s+", " ", str(manuscript_text or "").strip())
    if not text:
        return normalize_picture_book_spreads([])

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]

    target_words = max(1, int(round(count_words(text) / 16)))
    chunks = []
    current = []
    current_words = 0

    for sentence in sentences:
        sentence_words = count_words(sentence)
        remaining_sentences = len(sentences) - sum(len(c) for c in [])
        if current and current_words + sentence_words > target_words and len(chunks) < 15:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = sentence_words
        else:
            current.append(sentence)
            current_words += sentence_words

    if current:
        chunks.append(" ".join(current).strip())

    # If sentence grouping produced fewer than 16 chunks, split the longest chunks until there are 16.
    while len(chunks) < 16:
        if not chunks:
            chunks.append("")
            continue
        longest_index = max(range(len(chunks)), key=lambda i: count_words(chunks[i]))
        words = chunks[longest_index].split()
        if len(words) < 2:
            chunks.append("")
            continue
        mid = max(1, len(words) // 2)
        left = " ".join(words[:mid]).strip()
        right = " ".join(words[mid:]).strip()
        chunks[longest_index:longest_index + 1] = [left, right]

    if len(chunks) > 16:
        chunks = chunks[:15] + [" ".join(chunks[15:]).strip()]

    template_cycle = [
        "Full Illustration — Text Bottom",
        "Text Left — Illustration Right",
        "Illustration Left — Text Right",
        "Two-Page Illustration — Text Overlay",
        "Spot Illustration — Open Text Area",
        "Full Illustration — Text Top",
    ]

    spreads = []
    for idx in range(16):
        page_start = idx * 2 + 1
        story_text = chunks[idx].strip() if idx < len(chunks) else ""
        spreads.append({
            "spread_number": idx + 1,
            "pages": f"{page_start}-{page_start + 1}",
            "template": template_cycle[idx % len(template_cycle)],
            "story_text": story_text,
            "illustration_direction": "",
        })

    return normalize_picture_book_spreads(spreads)


def build_picture_book_cue_script(manuscript_text, include_cues=True):
    """Create an optional illustration/page-turn planning copy; never mutate the manuscript."""
    original = str(manuscript_text or "").strip()
    if not original or not include_cues:
        return original
    # Reuse the application's existing 16-spread segmentation as a planning guide.
    # Spread positions can be moved later by the writer/illustrator.
    spreads = build_picture_book_spreads_locally(original)
    out = []
    for spread in spreads:
        words = str(spread.get("story_text") or "").strip()
        if not words:
            continue
        number = spread.get("spread_number", len(out) + 1)
        out.append(f"[ILLUSTRATION: Spread {number} — decide what this scene should show]\n\n{words}")
        if number < 16:
            out.append("[PAGE TURN]")
    return "\n\n".join(out)


def picture_book_cues_docx_bytes(title, text):
    """Export a planning or clean manuscript independently of saved versions."""
    doc = Document()
    doc.add_heading(str(title or "Children's Picture Book"), 0)
    for paragraph in str(text or "").split("\n\n"):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_picture_book_layout_docx_bytes(title, spreads, page_size_name=None):
    """Create a production/planning DOCX, not a print-ready printer file."""
    page_size_name = str(
        page_size_name
        or st.session_state.get("picture_book_page_size")
        or DEFAULT_PICTURE_BOOK_PAGE_SIZE
    )
    size_spec = get_picture_book_page_size_spec(page_size_name)

    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(size_spec["page_width"] * 2)
    section.page_height = Inches(size_spec["page_height"])
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)

    doc.add_heading(str(title or "Untitled Children's Picture Book"), level=1)
    doc.add_paragraph("Children's Picture Book — 32-Page Layout Draft")
    doc.add_paragraph(
        f"Selected Page Size: {page_size_name} — "
        f"{size_spec['page_width']:g} x {size_spec['page_height']:g} inches per page."
    )
    doc.add_paragraph(
        "Production planning document only. This file organizes story text, illustration direction, "
        "and page/spread layout choices. It is not a printer-ready file."
    )

    for spread in normalize_picture_book_spreads(spreads):
        doc.add_heading(
            f"Spread {spread['spread_number']} — Pages {spread['pages']}",
            level=2,
        )
        doc.add_paragraph(f"Layout Template: {spread['template']}")

        p = doc.add_paragraph()
        run = p.add_run("Story Text")
        run.bold = True
        doc.add_paragraph(spread.get("story_text") or "[No story text assigned]")

        p = doc.add_paragraph()
        run = p.add_run("Illustration Direction")
        run.bold = True
        doc.add_paragraph(spread.get("illustration_direction") or "[No illustration direction assigned]")

        doc.add_paragraph("—" * 30)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def save_picture_book_layout_to_supabase(spreads, page_size_name=None):
    project_id = get_active_project_id()
    user_id = get_current_user_id()
    if not project_id or not user_id:
        return None

    page_size_name = str(
        page_size_name
        or st.session_state.get("picture_book_page_size")
        or DEFAULT_PICTURE_BOOK_PAGE_SIZE
    )
    size_spec = get_picture_book_page_size_spec(page_size_name)

    payload = {
        "format": PICTURE_BOOK_FORMAT,
        "page_count": 32,
        "page_size": page_size_name,
        "page_width_inches": size_spec["page_width"],
        "page_height_inches": size_spec["page_height"],
        "trim_reference": size_spec["trim_reference"],
        "spreads": normalize_picture_book_spreads(spreads),
        "source_signature": get_text_signature(st.session_state.get("current_draft_output", "")),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    result = supabase.table("writersblock_project_drafts").insert({
        "project_id": project_id,
        "user_id": user_id,
        "draft_title": "Children's Picture Book Layout Draft",
        "draft_type": "picture_book_layout",
        "draft_content": json.dumps(payload),
        "version_number": max(1, int(st.session_state.get("picture_book_layout_preview_id", 0) or 0)),
    }).execute()
    return result


def build_standard_manuscript_docx_bytes(title, manuscript_text, version_label="Current Manuscript"):
    doc = Document()
    doc.add_heading(str(title or "Untitled Project"), level=1)
    doc.add_paragraph(str(version_label or "Current Manuscript"))

    for paragraph in re.split(r"\n\s*\n", str(manuscript_text or "")):
        clean_paragraph = paragraph.strip()
        if clean_paragraph:
            p = doc.add_paragraph(clean_paragraph)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.15

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_audiobook_production_docx_bytes(title, production_text):
    """WritersBlock Audiobook Theatre Production Script layout.

    Locked production styling:
    - Courier New 12 pt throughout
    - speaker labels bold
    - narration regular
    - character-spoken lines bold italic
    - square-bracket production tags regular
    - page numbers bottom center
    """
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.footer_distance = Inches(0.5)
    _set_style_font(doc.styles["Normal"], "Courier New", 12)
    _configure_bottom_center_page_numbers(section)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(str(title or "Untitled Project"))
    _set_run_font(r, "Courier New", 12, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    r = p.add_run("AUDIOBOOK THEATRE PRODUCTION SCRIPT")
    _set_run_font(r, "Courier New", 12, bold=True)

    speaker_pattern = re.compile(r"^[A-Z][A-Z0-9 .,'’()&/\-]{1,50}:$")
    cue_pattern = re.compile(r"^\[(SFX|MUSIC|BED|PAUSE|AMBIENCE|PRONUNCIATION|PERFORMANCE|NOTE)\b", re.IGNORECASE)
    heading_pattern = re.compile(r"^(CHAPTER|SCENE|PART)\b", re.IGNORECASE)
    current_speaker = ""

    for raw_line in str(production_text or "").splitlines():
        line = raw_line.strip()
        line = re.sub(r"^\*\*(.*?)\*\*$", r"\1", line)

        if not line:
            doc.add_paragraph("")
            continue

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.0

        if speaker_pattern.match(line):
            current_speaker = line[:-1].strip().upper()
            r = p.add_run(line)
            _set_run_font(r, "Courier New", 12, bold=True)

        elif cue_pattern.match(line):
            # Enhancement / production tags remain regular per WBS formatting rule.
            r = p.add_run(line)
            _set_run_font(r, "Courier New", 12)

        elif heading_pattern.match(line):
            current_speaker = ""
            r = p.add_run(line)
            _set_run_font(r, "Courier New", 12, bold=True)

        else:
            r = p.add_run(line)
            if current_speaker and current_speaker != "NARRATOR":
                _set_run_font(r, "Courier New", 12, bold=True, italic=True)
            else:
                _set_run_font(r, "Courier New", 12)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

def build_audiobook_package_zip_bytes(title, manuscript_text, production_text):
    standard_bytes = build_standard_manuscript_docx_bytes(
        title,
        manuscript_text,
        version_label="Standard Manuscript",
    )
    production_bytes = build_audiobook_production_docx_bytes(title, production_text)
    stem = safe_download_stem(title, "audiobook")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{stem}_standard_manuscript.docx", standard_bytes)
        archive.writestr(f"{stem}_audiobook_theatre_production_script.docx", production_bytes)

    return buffer.getvalue()


def get_audiobook_production_instruction(cue_level):
    cue_rule = {
        "Clean Voices Only": (
            "Use only NARRATOR and character speaker labels. Do not add SFX, music, "
            "ambience, performance, or pause cues."
        ),
        "Voices + Minimal SFX": (
            "Add only essential SFX, ambience, or pause cues when the sound is clearly "
            "supported by the manuscript and helps the listener understand the action. "
            "Keep cues sparse. Do not add music unless the manuscript explicitly requires it."
        ),
        "Full Audiobook Theatre Cues": (
            "Add restrained SFX, ambience, pause, background-bed, and occasional performance "
            "cues where they directly support the existing story. Never let cues overwhelm narration."
        ),
    }.get(cue_level, "Add only essential SFX cues and keep them sparse.")

    return f"""
FORMAT CONVERSION ONLY — DO NOT REWRITE THE STORY.

Convert the supplied approved manuscript into an AUDIOBOOK THEATRE PRODUCTION SCRIPT.
Preserve the complete plot, chronology, character identities, dialogue meaning, narrative details,
and ending. Do not add scenes, remove scenes, invent dialogue, summarize, modernize, censor,
expand, condense, or change the writing style.

LAYOUT RULES:
1. Separate all descriptive prose and non-spoken action under the speaker label NARRATOR:.
2. Place each spoken passage under the correct CHARACTER NAME: in uppercase.
3. Remove quotation marks from spoken dialogue after assigning it to the correct speaker.
4. Keep narration and dialogue in the same story order as the manuscript.
5. Use plain text speaker labels on their own lines. Do not use tables, screenplay camera directions,
   shot descriptions, visual prompts, markdown headings, bullets, or code fences.
6. Keep chapter or scene headings only when they already exist or when a simple scene break is
   necessary to preserve the manuscript's existing structure.
7. Put production cues in square brackets on their own lines, for example:
   [SFX: Floorboard creaks behind Eleanor.]
   [PAUSE: 1 second.]
8. Never label internal thoughts as spoken dialogue unless the manuscript clearly presents them as speech.
9. Do not place character names inside narration labels. Use one speaker label for each continuous block.
10. Return only the finished production script.

CUE LEVEL:
{cue_rule}
""".strip()


AUDIOBOOK_LENGTH_OPTIONS = {
    "15 Minutes": {"min_words": 1800, "max_words": 2250, "default_words": 2000},
    "30 Minutes": {"min_words": 3600, "max_words": 4500, "default_words": 4000},
    "45 Minutes": {"min_words": 5400, "max_words": 6750, "default_words": 6000},
    "60 Minutes": {"min_words": 7200, "max_words": 9000, "default_words": 8000},
}


def get_audiobook_length_spec():
    selected_length = st.session_state.get("audiobook_length", "30 Minutes")
    return AUDIOBOOK_LENGTH_OPTIONS.get(
        selected_length,
        AUDIOBOOK_LENGTH_OPTIONS["30 Minutes"],
    )


def get_effective_format_type():
    format_type = str(st.session_state.get("format_type", "Novel / Prose"))

    if format_type != "Audio Book":
        return format_type

    selected_length = st.session_state.get("audiobook_length", "30 Minutes")
    length_spec = get_audiobook_length_spec()
    target_words = int(
        st.session_state.get(
            "audiobook_target_word_count",
            length_spec["default_words"],
        )
    )

    return (
        f"Audio Book | Approximate finished narration length: {selected_length} | "
        f"Target total manuscript length: {target_words:,} words | "
        f"Acceptable total range: {length_spec['min_words']:,}–"
        f"{length_spec['max_words']:,} words. Structure the outline and scene "
        f"distribution so the completed manuscript remains within this total range."
    )



PROJECT_INTEGRITY_REVIEW_FORMATS = {
    "Novel / Prose",
    "Short Story",
    "Novella",
    "Standard Manuscript",
    "Screenplay Outline",
    "Stage Play / Dramatic Script",
    "Audio Book",
    "Full Novel Blueprint",
    PICTURE_BOOK_FORMAT if "PICTURE_BOOK_FORMAT" in globals() else "Children's Picture Book (32-Page Layout)",
    "Podcast Script", "YouTube Shorts", "Commercial",
}


def project_integrity_review_applies(format_type=None):
    selected = str(format_type or st.session_state.get("format_type") or "").strip()
    from wbs_format_guard import FORMAT_LEGACY
    return selected in PROJECT_INTEGRITY_REVIEW_FORMATS or selected in {FORMAT_LEGACY[f] for f in ('biography_memoir','childrens_interactive_educational')}


def render_project_integrity_report_html(report_text, located_issues=None):
    report_text = str(report_text or "").strip()
    if not report_text:
        return ""

    section_titles = {
        "PROJECT INTEGRITY SUMMARY",
        "CRITICAL WARNINGS",
        "CONTINUITY / CHARACTER / TIMELINE",
        "REPETITION / POV / TENSE",
        "CHAPTER / SECTION / STRUCTURE INTEGRITY",
        "PLACEHOLDERS / MISSING / DUPLICATE CONTENT",
        "UNRESOLVED STORY ELEMENTS",
        "FORMAT COMPLIANCE",
        "RECOMMENDED WRITER CHECKS",
    }

    # Locate warnings in the actual saved scene text, then label the warning
    # INLINE. The report and manuscript themselves remain entirely unchanged.
    # Only verified quotes or explicit scene references get location labels.
    locations_by_issue = {}
    for item in (located_issues or []):
        issue = str(item.get("issue") or "").strip()
        if not issue:
            continue
        locs = locations_by_issue.setdefault(issue, [])
        label = f"Scene {item['scene']} — {item['title']}"
        if label not in locs:
            locs.append(label)

    chunks = ["<div class='wbs-integrity-report'>"]
    for raw_line in report_text.splitlines():
        line = str(raw_line or "").rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        safe = html.escape(stripped)
        upper = stripped.upper()
        if upper.startswith("OVERALL STATUS:"):
            chunks.append(f"<div class='wbs-ir-status'>{safe}</div>")
        elif upper in section_titles:
            chunks.append(f"<div class='wbs-ir-section'><div class='wbs-ir-heading'>{safe}</div></div>")
        elif stripped.startswith("- ") or stripped.startswith("-"):
            warning = stripped[1:].strip()
            locations = locations_by_issue.get(warning, [])
            position = ("<strong>Location: " + html.escape("; ".join(locations))
                        + "</strong> — ") if locations else ""
            chunks.append(f"<div class='wbs-ir-bullet'>• {position}{html.escape(warning)}</div>")
        elif re.match(r"^\d+\.\s", stripped):
            warning = re.sub(r"^\d+\.\s", "", stripped).strip()
            locations = locations_by_issue.get(warning, [])
            position = ("<strong>Location: " + html.escape("; ".join(locations))
                        + "</strong> — ") if locations else ""
            chunks.append(f"<div class='wbs-ir-number'>{position}{safe}</div>")
        else:
            chunks.append(f"<div class='wbs-ir-p'>{safe}</div>")
    chunks.append("</div>")
    return "\n".join(chunks)


# Integrity findings are *advice*, not manuscript edits. Reject assertions that
# cannot name a real reason, location, verbatim excerpt AND a specific action.
# This runs locally without another AI request or any database/manuscript writes.
_WBS_IR_FINDING_SECTIONS = (
    "CRITICAL WARNINGS", "CONTINUITY / CHARACTER / TIMELINE",
    "REPETITION / POV / TENSE", "CHAPTER / SECTION / STRUCTURE INTEGRITY",
    "PLACEHOLDERS / MISSING / DUPLICATE CONTENT",
    "UNRESOLVED STORY ELEMENTS", "FORMAT COMPLIANCE",
)
_WBS_IR_ALL_SECTIONS = (
    "PROJECT INTEGRITY SUMMARY", *_WBS_IR_FINDING_SECTIONS,
    "RECOMMENDED WRITER CHECKS",
)


from core.integrity import wbs_ir_parse_actionable_finding


def wbs_ir_screen_generated_report(report_text, manuscript_text, scene_blocks=None):
    """Remove unsubstantiated AI *warnings*, never remove or change story text.

    No extra API call. The returned REPORT can be saved alongside the unchanged
    manuscript. Older saved reports are left intact and are not silently edited.
    """
    source = str(manuscript_text or "")
    scene_texts = wbs_ss_blocks(scene_blocks or {})
    source_normalized = " ".join(re.findall(r"\w+", source.casefold()))
    warnings = []
    omitted = 0
    current_section = ""
    summary = []
    lines = str(report_text or "").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.upper() in _WBS_IR_ALL_SECTIONS:
            current_section = stripped.upper()
            continue
        if current_section not in _WBS_IR_FINDING_SECTIONS:
            continue
        bullet = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", stripped)
        if not bullet or bullet.upper().startswith(("NONE FOUND", "NO MATERIAL ISSUES", "NO ISSUES")):
            continue
        item = wbs_ir_parse_actionable_finding(bullet)
        if item is None:
            omitted += 1
            continue
        quote_words = re.findall(r"\w+", item["QUOTE"].casefold())
        if len(quote_words) < 4 or len(quote_words) > 22:
            omitted += 1
            continue
        quote_normalized = " ".join(quote_words)
        if quote_normalized not in source_normalized:
            omitted += 1
            continue
        location = item["LOCATION"]
        # A continuity error can span two scenes. Require every named scene to
        # exist, but let the one exact evidence quotation come from EITHER
        # scene. Previously only the first scene was checked, silently dropping
        # genuine Scene 2 -> Scene 3 transition errors.
        claimed = [int(n) for n in re.findall(r"\bscene\s*(\d+)\b", location, re.I)]
        if claimed and scene_texts:
            if any(n not in scene_texts for n in claimed) or not any(
                quote_normalized in " ".join(re.findall(r"\w+", scene_texts[n].casefold()))
                for n in claimed
            ):
                omitted += 1
                continue
        warnings.append((current_section, bullet, item))

    grouped = {name: [] for name in _WBS_IR_FINDING_SECTIONS}
    for section, bullet, item in warnings:
        if bullet not in grouped[section]:
            grouped[section].append(bullet)
    accepted = sum(len(items) for items in grouped.values())
    # The quality gate does not claim that a model is infallible: it prevents
    # unsupported remarks from being presented as corrections to the author.
    # A quality gate that discarded all the model's proposed findings has NOT
    # established a clean manuscript. Keep that distinct from a genuine PASS.
    review_status = ("WARNINGS" if accepted else
                     "REVIEW INCONCLUSIVE" if omitted else "PASS")
    output = [f"OVERALL STATUS: {review_status}", "", "PROJECT INTEGRITY SUMMARY"]
    if accepted:
        output.append(f"The review identified {accepted} specific finding(s) with a stated reason, "
                      "manuscript evidence and a suggested writer-controlled correction. "
                      "No manuscript text has been changed.")
    elif omitted:
        output.append("The review offered suggestions, but none met the evidence and specificity "
                      "requirements. This review is inconclusive, not a confirmed clean bill "
                      "of health. The manuscript has not been changed.")
    else:
        output.append("No sufficiently supported, actionable integrity findings were returned "
                      "by this review. The manuscript has not been changed.")
    if omitted:
        output.append(f"{omitted} unsupported or unclear AI suggestion(s) were excluded "
                      "because they did not establish an actionable defect.")
    for section in _WBS_IR_FINDING_SECTIONS:
        output.extend(("", section))
        output.extend("- " + bullet for bullet in grouped[section])
        if not grouped[section]:
            output.append("- None found." if section == "CRITICAL WARNINGS" else "- No material issues found.")
    output.extend(("", "RECOMMENDED WRITER CHECKS"))
    if accepted:
        # Only summarize the supported warning's specific action, not arbitrary
        # stylistic improvement suggestions from the AI response.
        output.extend("- " + item["SUGGESTED FIX"] for _, _, item in warnings)
    elif omitted:
        output.append("- This check was inconclusive. Review the saved manuscript yourself "
                      "and consider running another check if further confidence is needed.")
    else:
        output.append("- No changes recommended before Final Output.")
    return "\n".join(output), {"accepted": accepted, "omitted": omitted}


def run_project_integrity_final_review(manuscript_text):
    """Read-only whole-project quality-control review. Never rewrites manuscript text."""
    manuscript_text = str(manuscript_text or "").strip()
    if not manuscript_text:
        raise ValueError("No manuscript is available for Project Integrity review.")

    backend = st.session_state.get("backend")
    client = getattr(backend, "client", None)
    model_name = getattr(backend, "model_name", None)
    if client is None or not model_name:
        raise RuntimeError("The WritersBlock AI review service is unavailable.")

    project_type = str(st.session_state.get("format_type") or "Novel / Prose")
    project_title = get_project_title_for_display()
    format_context = get_active_format_development_context()
    series_context = build_series_context_text(
        max_total_chars=30000,
        per_source_chars=10000,
    )

    # Match editorial word-count guidance to the selected picture-book age group.
    # A suggested target (e.g. 450) is not a minimum or a publication blocker.
    picture_book_length_guidance = ""
    if is_picture_book_project():
        suggested, age_maximum, age_label = picture_book_age_budget_rules()
        picture_book_length_guidance = (
            f"CHILDREN'S PICTURE BOOK WORD COUNT: Selected age range {age_label}; "
            f"suggested target {suggested} words; upper guidance {age_maximum} words. "
            f"The suggested target is NOT a minimum or strict requirement. "
            f"Do not flag the manuscript as too short merely for being below 500 words. "
            f"A complete 469-word picture book is acceptable for the 3–8 age range. "
            f"Judge completeness by narrative quality rather than an invented minimum."
        )

    # Scene markers are context for audit LOCATION only. Never put these markers
    # into the stored manuscript or change its text. Use actual four-scene blocks.
    _ir_blocks = wbs_ss_blocks(st.session_state.get("scene_blocks") or {})
    _ir_titles = wbs_ss_outline_parts(st.session_state.get("plot_outline") or "")
    _novel_ir_blocks = (wbs_novel_blocks(st.session_state.get("scene_blocks") or {})
                        if st.session_state.get("active_format_id") == "novel_prose_novella" else {})
    from core.manuscript_structure import profile,configured,integrity_context
    _structure_spec = profile(st.session_state['active_format_id'])
    if st.session_state['active_format_id']!='short_story':
        from core.integrity_review import numbered_context
        _ir_annotated=numbered_context(st.session_state)
        _ir_scene_guidance='Use the supplied format-specific boundaries and exact quotations. Never assume four scenes or novel chapters.'
    elif (_novel_ir_blocks and set(_novel_ir_blocks) == set(range(1, max(_novel_ir_blocks) + 1))
            and manuscript_text == wbs_novel_manuscript(_novel_ir_blocks).strip()):
        _ir_annotated = "\n\n".join(
            f"[CHAPTER {n}]\n" + _novel_ir_blocks[n] + f"\n[END CHAPTER {n}]"
            for n in sorted(_novel_ir_blocks))
        _ir_scene_guidance = (
            "The manuscript contains CHAPTER boundary labels used solely for the integrity audit. "
            "For every warning identify the actual chapter number and paragraph number, "
            "and quote a short exact passage. Cross-chapter contradictions must identify "
            "both affected chapters. Do not treat boundary labels as story prose.")
    elif (set(_ir_blocks) == {1, 2, 3, 4}
            and manuscript_text == wbs_ss_storyline(_ir_blocks).strip()):
        _ir_annotated = "\n\n".join(
            f"[SCENE {n} — {_ir_titles.get(n, (f'Scene {n}',))[0]}]\n"
            + _ir_blocks[n] + f"\n[END SCENE {n}]"
            for n in (1, 2, 3, 4)
        )
        _ir_scene_guidance = (
            "The manuscript below contains scene boundary labels added for "
            "location reporting only. They are NOT manuscript content. "
            "For EACH warning, specify the exact scene number and scene title, "
            "and one short verbatim quote (under 18 words) identifying the passage. "
            "If a problem crosses two scenes, identify both scenes. "
            "Give scene-local paragraph numbers only when certain."
        )
    else:
        _ir_annotated = manuscript_text
        _ir_scene_guidance = (
            "Identify the actual chapter/section/scene where each warning occurs "
            "when the manuscript supplies one; quote a short exact passage. "
            "Do not invent four scenes or any absent boundaries."
        )

    prompt = f"""
You are the WritersBlock Studios PROJECT INTEGRITY / FINAL REVIEW quality-control system.

This is a READ-ONLY audit. DO NOT rewrite, edit, polish, replace, summarize, or continue the manuscript.
Do not silently fix anything. The writer controls all changes.

PROJECT:
Title: {project_title}
Writing Format: {project_type}

FORMAT / DEVELOPMENT REQUIREMENTS:
{format_context or "No additional format-development requirements were supplied."}
{picture_book_length_guidance}

SERIES / CONTINUITY REFERENCE:
{series_context or "This project has no selected series-continuity reference package."}

AUDIT THE COMPLETE MANUSCRIPT FOR:
1. Project integrity and continuity across the entire work.
2. Character names, identities, relationships, ages, roles, and descriptive contradictions.
3. Timeline, dates, sequence of events, travel/time logic, and historical-period consistency.
4. Location, object, world-rule, terminology, and factual continuity inside the manuscript.
   IMPORTANT: Compare the END of each scene with the BEGINNING of the next scene.
   Trace where each character/object was and where it appears next; look for
   unmotivated jumps (e.g., under a counter -> under a chair) and unexplained
   changes in possession, appearance, or access. Cite BOTH scenes for genuine
   cross-scene contradictions, and quote a passage that actually exists.
5. Repetition: duplicated passages, repeated scenes, repeated explanations, or accidental restatement.
6. POV and tense drift, including unexplained changes between sections or chapters.
7. Unresolved placeholders, TODO/TBD notes, bracketed drafting notes, incomplete sentences,
   subject/verb disagreement, accidental tense slips, dangling introductory clauses,
   or obvious generation artifacts. Check sentence-level grammar in EACH scene.
8. Missing, duplicated, misordered, or obviously incomplete chapters/scenes/sections when the format uses them.
9. Chapter/section numbering and heading consistency when headings are present.
10. Unresolved story threads, setups, promises, character actions, mysteries, or references that appear accidentally abandoned.
11. Internal contradictions between early and late portions of the manuscript.
    Check physical/action plausibility as established BY THE STORY: can a character
    reach the described object from its stated position, does an action have the
    needed physical setup, and do cause and effect follow? Missing explanation
    alone is not an impossibility. Distinguish uncertain logistics (VERIFY) from
    clear contradiction. Do not impose real-world physics on intentional fantasy.
12. Output-format compliance for the selected writing format at the manuscript-content level. Do not judge typography that is applied later by Final Output.
13. Any issue likely to embarrass the writer or damage continuity in a final manuscript.

MANDATORY COVERAGE PASS (internal analysis before writing the report):
- Examine all four scenes individually, if four scenes are supplied; do not
  concentrate only on the last scene or on an obvious planted typo.
- Explicitly compare Scene 1 -> 2, Scene 2 -> 3, and Scene 3 -> 4 for
  location, time, actor/object continuity, and causal transitions.
- On every scene, check grammar (including fragments and verb tense),
  repeated wording, physical setup and perspective limits.
- After the first obvious error is found, CONTINUE checking the rest of the
  manuscript. A single finding does not conclude the review.
- Report only genuinely supported issues found in these passes. This coverage
  checklist is not a quota: clean scenes should produce no invented findings.

IMPORTANT REVIEW RULES:
- Determine the manuscript's actual narrative point of view before judging name usage, voice, knowledge, and plot requirements. Compare its narrative prose (not quoted dialogue) with the requested POV. A consistently first-person account must be assessed from the narrator's own limited experience.
- In first-person narration, the narrator naturally says "I" and "my" and need not state their own name. A character name in the outline, concept, cast list, title, or development fields does NOT require that name to appear literally in the prose. Do not flag a missing self-name as an integrity or format problem unless the author explicitly requires the name to be spoken or introduced in the story, or the character's identity truly contradicts the project.
- A first-person narrator can describe other characters' audible sounds, visible actions, and the narrator's interpretation of them without knowing those characters' internal thoughts or intentions. Do not insist that a first-person narrator explicitly describe another character hearing a specific noise when that character's reaction is observable or reasonably conveyed. Flag only a genuine causal/continuity gap supported by the manuscript, not an unspoken inference.
- Do not require the author to rename a project, add the narrator's name, or rewrite the plot merely to satisfy a formal name-match check. Project titles, character setup, and outlines provide context; judge whether the intended story is actually present. If a substantive discrepancy remains, explain WHY and identify the precise text/location; otherwise report no issue.
- Distinguish an actual contradiction from an intentional mystery, reveal, unreliable narrator, flashback, or deliberate stylistic choice.
- Do not invent problems merely to fill the report.
- Cite the chapter/scene/section or a short identifying phrase whenever possible.
- Each substantive warning MUST include the actual scene/section location and an exact identifying quote when available. Never guess an absent scene.
- Do not quote long passages.
- If an item is uncertain, label it "VERIFY" rather than presenting it as a definite error.
- Recommendations must describe what the writer should inspect or consider. Do not rewrite the text.
- First-person dialogue inside quotation marks is normal in third-person narration and is NOT, by itself, a POV violation.
- When evaluating POV compliance, judge the narrative prose outside character dialogue and direct quotations.
- If the project requirements call for first-person POV but the manuscript uses third-person narration with normal first-person dialogue, report it as a narrative POV mismatch rather than a dialogue problem.
- A colorful description, emotion, plausible inference, stylistic choice, normal sensory detail, or playful metaphor is NOT a formatting or continuity error by itself. For example, a kitten saying a cereal flake is a \"tiny explosion of flavor\" is not an integrity defect. Never invent a rule merely to criticize evocative writing.
- A quoted sentence is NOT proof of a defect. Identify the concrete conflict or objective manuscript requirement first, then quote the evidence that demonstrates it.
- Evaluate actual published-format requirements only when they are supplied and applicable to this writing format. Never invent manuscript-format requirements or request changes because a passage \"might fail\" an unnamed rule.
- Do not turn an unverified impression into an actionable warning. If no explicit contradiction, actual rule violation, accidental duplication, or genuinely unresolved element can be substantiated, say there are no material issues.
- When a continuity issue spans two scenes, name BOTH in LOCATION (example:
  "Scene 2 and Scene 3") and state the contradictory facts from each in WHY.
  EVIDENCE must be one exact quoted passage from one of those scenes. Never
  manufacture a connecting quotation from separate scenes.
- Prefer a specific minimal correction for grammar, continuity, or unintended
  repetition; do not replace a passage with an entire AI rewrite.
- For EVERY material warning use ONE bullet in this precise form (single line):
  - ISSUE: <specific problem> | WHY: <what contradicts what, or exact objective rule> | LOCATION: <actual scene number/title if present, otherwise known section or Manuscript> | EVIDENCE: \"<exact verbatim excerpt from the manuscript of 4-18 words>\" | SUGGESTED FIX: <a precise optional correction the author can make>
- No generic warnings, no quote-only warnings, no statements such as \"check the stated requirement\", and no unsupported claims of a format rule. If the required five fields cannot truthfully be filled, OMIT that finding. Do not propose a change that would damage an intentional first-person voice or the author's story.
- In RECOMMENDED WRITER CHECKS, repeat only specific fixes for genuinely supported warnings. When there are none, write \"No changes recommended before Final Output.\". Do not generate extra optional stylistic criticism in this integrity gate.

RETURN EXACTLY THIS REPORT STRUCTURE:
OVERALL STATUS: PASS
or
OVERALL STATUS: WARNINGS

PROJECT INTEGRITY SUMMARY
[2-6 concise sentences]

CRITICAL WARNINGS
- [supported actionable issue in the required ISSUE/WHY/LOCATION/EVIDENCE/SUGGESTED FIX format, or "None found."]

CONTINUITY / CHARACTER / TIMELINE
- [items, or "No material issues found."]

REPETITION / POV / TENSE
- [items, or "No material issues found."]

CHAPTER / SECTION / STRUCTURE INTEGRITY
- [items, or "No material issues found."]

PLACEHOLDERS / MISSING / DUPLICATE CONTENT
- [items, or "No material issues found."]

UNRESOLVED STORY ELEMENTS
- [items, or "No material issues found."]

FORMAT COMPLIANCE
- [items, or "No material issues found."]

RECOMMENDED WRITER CHECKS
- [prioritized recommendations, or "No changes recommended before Final Output."]

Use PASS only when no material warning is found. Use WARNINGS when one or more items should be reviewed by the writer.

LOCATION REFERENCE:
{_ir_scene_guidance}

--- BEGIN MANUSCRIPT ---
{_ir_annotated}
--- END MANUSCRIPT ---
""".strip()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    report = str(getattr(response, "text", "") or "").strip()
    if not report:
        raise RuntimeError("The Project Integrity review returned no report.")
    # QC of the QC: only supported, specific, directly locatable warnings
    # survive to the report. The author's manuscript is never modified.
    checked_report, _review_qc = wbs_ir_screen_generated_report(
        report, manuscript_text, _ir_blocks
    )
    return checked_report


def wbs_ir_located_issues(report_text, blocks, titles, manuscript_text=None):
    """Annotate AI warnings with verified scene locations, without editing story.

    Scene-level editorial navigation must not depend on the stricter four-scene
    final-approval comparison. A report can refer to one saved scene even if the
    working manuscript has gained a small accepted rewrite. Match identifying
    quoted phrases against BOTH the scene and the reviewed manuscript.
    """
    actual = wbs_ss_blocks(blocks)
    if not actual:
        return []

    def _tokens(value):
        return re.findall(r"\w+", str(value or "").casefold())

    source_words = _tokens(manuscript_text) if manuscript_text is not None else []

    def _best_contiguous(words, passage):
        """Number of consecutive literal words shared by two passages."""
        if not words or not passage:
            return 0
        # Five to eight consecutive original words are more reliable than an
        # AI-invented section/paragraph number, and tolerate short prefatory
        # words changed by the reviewer (e.g. 'The richer' vs 'A sudden, richer').
        longest = 0
        lookups = {}
        for i, word in enumerate(passage):
            lookups.setdefault(word, []).append(i)
        for i, word in enumerate(words):
            for j in lookups.get(word, []):
                k = 0
                while (i+k < len(words) and j+k < len(passage)
                       and words[i+k] == passage[j+k]):
                    k += 1
                longest = max(longest, k)
                if longest >= len(words):
                    return longest
        return longest

    output = []
    section = ""
    neutral = ("NONE FOUND", "NO MATERIAL ISSUES", "NO CHANGES RECOMMENDED",
               "NO CRITICAL", "NO ISSUES", "NOT APPLICABLE")
    heading_names = {"CRITICAL WARNINGS", "CONTINUITY / CHARACTER / TIMELINE",
                     "REPETITION / POV / TENSE", "CHAPTER / SECTION / STRUCTURE INTEGRITY",
                     "PLACEHOLDERS / MISSING / DUPLICATE CONTENT",
                     "UNRESOLVED STORY ELEMENTS", "FORMAT COMPLIANCE",
                     "RECOMMENDED WRITER CHECKS"}
    for line in str(report_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper() in heading_names:
            section = stripped.upper()
            continue
        if section not in heading_names:
            continue
        # AI review responses sometimes use Markdown asterisks rather than the
        # requested hyphen for a VERIFY finding. Treat both as report bullets.
        content = re.sub(r"^(?:[-•*]\s*|\d+\.\s*)", "", stripped).strip()
        if not content or content.upper().startswith(neutral):
            continue
        if not (re.match(r"^(?:[-•*]|\d+\.)\s*", stripped)
                or 'VERIFY' in content.upper() or 'WARNING' in content.upper()):
            continue
        quotes = re.findall(r'["“]([^"”]{12,240})["”]', content)
        located = {}
        for quote in quotes:
            words = _tokens(quote)
            if len(words) < 6:
                continue
            # The quoted phrase MUST have a substantial verbatim anchor in
            # the reviewed manuscript. Do not navigate based on a guess.
            required = min(8, max(6, int(len(words) * 0.65)))
            if manuscript_text is not None and _best_contiguous(words, source_words) < required:
                continue
            for number, story in actual.items():
                if _best_contiguous(words, _tokens(story)) >= required:
                    located[number] = quote
        # Explicit scene IDs in the AI report are considered only when the
        # associated scene has content in the reviewed manuscript.
        if not located:
            for match in re.findall(r"\bscene\s*(?:number\s*)?(\d+)\b", content, re.I):
                number = int(match)
                if number in actual and (manuscript_text is None or
                    _best_contiguous(_tokens(actual[number]), source_words) >= 8):
                    located[number] = ""
        for number in sorted(located):
            title_entry = titles.get(number, (f"Scene {number}",))
            title = title_entry[0] if isinstance(title_entry, (tuple, list)) else str(title_entry)
            output.append({"scene": number, "title": title,
                           "section": section, "issue": content,
                           "quote": located[number]})
    seen = set()
    unique = []
    for entry in output:
        signature = (entry["scene"], entry["quote"].casefold() or entry["issue"].casefold())
        if signature not in seen:
            unique.append(entry)
            seen.add(signature)
    return unique



def wbs_ir_review_action(issue, section):
    """Suggest a writer check, never an automatic change to the manuscript.

    The original AI finding is always shown verbatim. This supplemental
    instruction is deliberately conservative and does not invent a correction.
    """
    finding = str(issue or "").casefold()
    heading = str(section or "").casefold()
    if ("name" in finding or "named" in finding) and any(
        term in finding for term in ("not present", "not used", "not mentioned", "absent", "never appears")
    ):
        return ("Check whether the character's name needs to appear in the story. "
                "In first-person narration, not naming the narrator may be intentional. "
                "Add the name only if you decide the omission is a problem.")
    if any(term in finding for term in ("repetit", "similar", "duplicate", "redundant")):
        return ("Compare the passages identified by the report. If the repetition "
                "is unintentional, rephrase or remove the duplicate wording.")
    if "point of view" in finding or "pov" in finding or "tense" in finding:
        return ("Check the cited passage against the chosen point of view "
                "and tense; correct an unintended shift only.")
    if "continuity" in heading or "character" in heading or "timeline" in heading:
        return ("Compare the reported detail with the surrounding story and "
                "project requirements. Edit only if the inconsistency is real.")
    if "format compliance" in heading:
        return ("Check the stated manuscript-format requirement and update "
                "the relevant text only if it fails that requirement.")
    return ("Read the specific finding above and inspect the quoted passage "
            "in context. Change the story only if the warning is valid.")


def wbs_ss_set_integrity_return_context(scene_number):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_set_integrity_return_context', globals(), scene_number)


def wbs_ss_is_integrity_return_context():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_is_integrity_return_context', globals())


def wbs_ir_go_to_scene(number):
    """Open the exact existing scene; never save, generate or renumber work."""
    number = int(number)
    if number not in (1, 2, 3, 4):
        return
    wbs_ss_set_integrity_return_context(number)
    st.session_state["_wbs_ss_jump_to"] = number
    if st.session_state.get("active_format_id") != "short_story":
        st.session_state["_wbs_stage3_rewrite_location"] = f"Scene Beat {number}"
    wbs_request_stage_change("Plot Architect")


FINAL_OUTPUT_FORMAT_OPTIONS = [
    "Novel / Prose",
    "Standard Manuscript",
    "Short Story",
    "Novella",
    "Screenplay Outline",
    "Stage Play / Dramatic Script",
    "Audio Book",
    PICTURE_BOOK_FORMAT,
    "Full Novel Blueprint",
    "YouTube Shorts",
    "Podcast Script",
]

FINAL_OUTPUT_FORMAT_OPTIONS.extend([
    FORMAT_LEGACY["biography_memoir"], FORMAT_LEGACY["childrens_interactive_educational"],
])

FINAL_OUTPUT_DISPLAY_LABELS = {
    "Novel / Prose": "Novel / Prose",
    "Short Story": "Short Story",
    "Novella": "Novella",
    "Standard Manuscript": "Standard Manuscript",
    "Screenplay Outline": "Screenplay",
    "Stage Play / Dramatic Script": "Stage Play / Dramatic Script",
    "Audio Book": "Audiobook Theatre Production Script",
    PICTURE_BOOK_FORMAT: "Children's Picture Book",
    "Full Novel Blueprint": "Full Novel Blueprint",
    "YouTube Shorts": "YouTube Shorts Script",
    "Podcast Script": "Podcast Script",
}


def get_final_output_format():
    selected = str(st.session_state.get("final_output_format") or "").strip()
    if selected not in FINAL_OUTPUT_FORMAT_OPTIONS:
        selected = str(st.session_state.get("format_type") or "Novel / Prose").strip()
    if selected not in FINAL_OUTPUT_FORMAT_OPTIONS:
        selected = "Novel / Prose"
    return selected


def get_automatic_output_label(format_type=None):
    selected = str(format_type or get_final_output_format()).strip()
    return FINAL_OUTPUT_DISPLAY_LABELS.get(selected, selected)


def get_final_output_conversion_instruction(target_format):
    target_format = str(target_format or "Novel / Prose")
    common = (
        "FINAL OUTPUT FORMAT CONVERSION ONLY. Use the supplied working manuscript as the authoritative source. "
        "Preserve its characters, plot, chronology, setting, important details, dialogue meaning, and ending. "
        "Do not invent a different story. Do not add commentary, markdown fences, or explanations. "
        "Return only the converted final-output text."
    )

    if target_format in {"Novel / Prose", "Short Story", "Novella", "Standard Manuscript"}:
        form_name = FINAL_OUTPUT_DISPLAY_LABELS.get(target_format, target_format)
        return f"""{common}
Convert the source into a clean {form_name} manuscript presentation. Use ordinary prose paragraphs and quoted dialogue with natural attribution. Remove screenplay, stage-play, or audiobook speaker labels if any exist in an older source. Preserve all substantive story content and approximately the current story length. This is manuscript normalization and format conversion, not a creative rewrite or summary."""

    if target_format == "Screenplay Outline":
        return f"""{common}
Convert the complete source into a properly structured professional screenplay.
REQUIRED SCREENPLAY FORM:
- Use INT./EXT. scene headings with location and DAY/NIGHT on their own lines.
- Use concise present-tense action paragraphs.
- Put CHARACTER NAMES in uppercase on their own lines before spoken dialogue.
- Put parentheticals on their own lines only when genuinely needed.
- Put dialogue beneath the character cue without quotation marks.
- Use transitions such as CUT TO: or FADE OUT: only when genuinely useful and place them on their own lines.
- Do not add camera directions, shot lists, or editing instructions unless the source itself requires them.
- Preserve every important scene, event, character, revelation, dialogue meaning, and ending from the source. Do not summarize or condense away story information merely to make the screenplay shorter.
Do not output prose-story paragraphs with quoted dialogue."""

    if target_format == "Stage Play / Dramatic Script":
        return f"""{common}
Convert the complete source into a professional stage play / dramatic script.
REQUIRED STAGE FORM:
- Begin with a concise CAST OF CHARACTERS section when the source provides identifiable characters.
- Use ACT and SCENE headings where appropriate.
- Put CHARACTER NAMES in uppercase on their own lines before their dialogue.
- Put spoken dialogue on the following line or lines without quotation marks.
- Put stage directions in parentheses on their own lines and keep them concise and performable.
- Do not use screenplay camera directions, shot descriptions, or ordinary quoted-prose dialogue.
- Preserve the complete story, characters, conflict, major action, dialogue meaning, and ending. Do not summarize away important material."""

    if target_format == "Audio Book":
        return get_audiobook_production_instruction(
            st.session_state.get("audiobook_production_cue_level", "Voices + Minimal SFX")
        )

    if target_format == PICTURE_BOOK_FORMAT:
        return f"""{common}
SPECIAL CHILDREN'S PICTURE BOOK ADAPTATION:
Adapt the source into a complete children's picture-book story of approximately {picture_book_target()} words TOTAL; never exceed this selected manuscript budget.
- Preserve the core plot, central characters, theme, emotional arc, and ending.
- Simplify exposition and descriptions for clear read-aloud pacing.
- Retain only dialogue that helps character, emotion, humor, or plot; shorten dialogue into simple age-appropriate spoken lines.
- Remove repetitive or adult-length conversations while preserving their essential meaning.
- Use short paragraphs suitable for later division across a 32-page / 16-spread picture-book layout.
- Do not include page numbers, spread numbers, illustration prompts, or layout instructions yet.
Return only the complete picture-book story within {picture_book_target()} words."""

    if target_format == "Full Novel Blueprint":
        return f"""{common}
Convert the source into a professional Full Novel Blueprint rather than finished prose.
Use clear section headings for PREMISE, PRINCIPAL CHARACTERS, CENTRAL CONFLICT, STORY ARCHITECTURE, MAJOR TURNING POINTS, CHAPTER / SCENE PROGRESSION, CHARACTER ARCS, CONTINUITY FACTS, and ENDING RESOLUTION where applicable. Preserve the source story exactly; organize it as a development blueprint rather than rewriting the story into new prose."""

    if target_format == "YouTube Shorts":
        return f"""{common}
Convert the source into a finished YouTube Shorts script.
REQUIRED SHORT-FORM VIDEO FORM:
- Assume vertical 9:16 presentation unless the project explicitly says otherwise.
- Open with an immediate hook.
- Keep the script focused on one core idea.
- Use concise narration/dialogue sized to the selected duration.
- Organize the script into clear visual beats or shot moments.
- Keep exposition minimal and move quickly.
- Include a strong final beat or call to action when appropriate.
- Preserve the source concept and essential message; do not expand it into long-form prose or screenplay structure.
Return only the finished YouTube Shorts script."""

    if target_format == "Podcast Script":
        return f"""{common}
Convert the source into a finished Podcast Script.
REQUIRED PODCAST FORM:
- Preserve the project's selected episode style, audience, duration, host structure, and publication context.
- Use clear spoken-language pacing suitable for listening.
- Organize the script into a strong opening, logical segments, transitions, and a clear close.
- Distinguish HOST, CO-HOST, GUEST, NARRATOR, or other speaker roles only when the project requires them.
- Keep sentences natural to say aloud; avoid visual-only instructions unless converted into spoken context.
- Include intro/outro, sponsor/CTA, or segment cues only when supported by the project setup.
- Do not convert the episode into prose fiction, screenplay, or stage-play formatting.
Return only the finished Podcast Script."""

    return common


def _set_run_font(run, font_name="Times New Roman", size=12, bold=None, italic=None):
    run.font.name = font_name
    run.font.size = Pt(size)
    # Word can otherwise substitute a theme font for complex-script ranges.
    run._element.rPr.rFonts.set(qn("w:ascii"), font_name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), font_name)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    return run

def _set_style_font(style, font_name="Times New Roman", size=12):
    style.font.name = font_name
    style.font.size = Pt(size)
    style._element.rPr.rFonts.set(qn("w:ascii"), font_name)
    style._element.rPr.rFonts.set(qn("w:hAnsi"), font_name)

def _add_page_field(paragraph, suffix=""):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    if suffix:
        paragraph.add_run(suffix)

def _restart_section_page_numbering(section, start=1):
    sect_pr = section._sectPr
    pg_num_type = sect_pr.find(qn("w:pgNumType"))
    if pg_num_type is None:
        pg_num_type = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num_type)
    pg_num_type.set(qn("w:start"), str(int(start)))

def _configure_top_right_page_numbers(section, hide_first=True, suffix=""):
    section.different_first_page_header_footer = bool(hide_first)
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    p.clear()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(0)
    _add_page_field(p, suffix=suffix)
    for run in p.runs:
        _set_run_font(run, "Courier New", 12)

    if hide_first:
        first_header = section.first_page_header
        first_header.is_linked_to_previous = False
        fp = first_header.paragraphs[0] if first_header.paragraphs else first_header.add_paragraph()
        fp.clear()

def _configure_bottom_center_page_numbers(section):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.clear()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    _add_page_field(p)
    for run in p.runs:
        _set_run_font(run, "Courier New", 12)

def _add_simple_title_page(doc, title, subtitle, font_name="Courier New"):
    # Clean submission-style title page without inventing author/contact information.
    for _ in range(7):
        doc.add_paragraph("")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(str(title or "Untitled Project").upper())
    _set_run_font(r, font_name, 12, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(str(subtitle or ""))
    _set_run_font(r, font_name, 12)

def _new_body_section(doc, left=1.0, right=1.0, top=1.0, bottom=1.0, restart_page=1):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = Inches(left)
    section.right_margin = Inches(right)
    section.top_margin = Inches(top)
    section.bottom_margin = Inches(bottom)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)
    _restart_section_page_numbering(section, restart_page)
    return section

def _is_scene_break(text):
    clean = str(text or "").strip()
    return bool(re.fullmatch(r"(?:#|\*\s*\*\s*\*|#\s*#\s*#)", clean))

def build_final_output_docx_bytes(title, output_text, target_format):
    target_format = str(target_format or "Novel / Prose")

    if target_format == "Audio Book":
        return build_audiobook_production_docx_bytes(title, output_text)

    # ------------------------------------------------------------------
    # SCREENPLAY: Final Draft-style US Letter submission layout.
    # 12 pt Courier, 1.5" binding margin, screenplay element indents,
    # first script page unnumbered and later pages numbered top-right.
    # ------------------------------------------------------------------
    if target_format == "Screenplay Outline":
        doc = Document()
        title_section = doc.sections[0]
        title_section.page_width = Inches(8.5)
        title_section.page_height = Inches(11)
        title_section.left_margin = Inches(1.5)
        title_section.right_margin = Inches(1.0)
        title_section.top_margin = Inches(1.0)
        title_section.bottom_margin = Inches(1.0)
        _set_style_font(doc.styles["Normal"], "Courier New", 12)
        _add_simple_title_page(doc, title, "Screenplay", "Courier New")

        section = _new_body_section(doc, left=1.5, right=1.0, top=1.0, bottom=0.75, restart_page=1)
        _configure_top_right_page_numbers(section, hide_first=True, suffix=".")

        scene_pat = re.compile(r"^(INT\.|EXT\.|INT\./EXT\.|EXT\./INT\.|I/E\.)", re.I)
        transition_pat = re.compile(r"^(FADE IN:|FADE OUT\.?|CUT TO:|DISSOLVE TO:|SMASH CUT TO:|MATCH CUT TO:|WIPE TO:)$", re.I)
        parenthetical_pat = re.compile(r"^\(.*\)$")
        char_pat = re.compile(r"^[A-Z][A-Z0-9 .,'’()&/\-]{1,45}$")
        previous_element = ""

        for raw in str(output_text or "").splitlines():
            line = raw.strip()
            if not line:
                previous_element = "blank"
                continue

            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.keep_together = False

            if scene_pat.match(line):
                p.paragraph_format.space_before = Pt(12 if len(doc.paragraphs) > 1 else 0)
                p.paragraph_format.keep_with_next = True
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12, bold=True)
                previous_element = "scene"

            elif line.upper() == "FADE IN:":
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12)
                previous_element = "transition"

            elif transition_pat.match(line) or (line.endswith(" TO:") and line.upper() == line):
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12)
                previous_element = "transition"

            elif parenthetical_pat.match(line):
                # Approx. 3.1" from page edge; narrowed on the right.
                p.paragraph_format.left_indent = Inches(1.6)
                p.paragraph_format.right_indent = Inches(1.4)
                p.paragraph_format.keep_with_next = True
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12)
                previous_element = "parenthetical"

            elif char_pat.match(line) and len(line.split()) <= 7 and not line.endswith((".", "!", "?", ":")):
                # Character cue begins approx. 3.7" from page edge.
                p.paragraph_format.left_indent = Inches(2.2)
                p.paragraph_format.keep_with_next = True
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12)
                previous_element = "character"

            elif previous_element in {"character", "parenthetical", "dialogue"}:
                # Dialogue begins approx. 2.5" from page edge and ends approx. 2.5" from right edge.
                p.paragraph_format.left_indent = Inches(1.0)
                p.paragraph_format.right_indent = Inches(1.5)
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12)
                previous_element = "dialogue"

            else:
                # Action: left page edge 1.5", right edge 1.0".
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12)
                previous_element = "action"

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # STAGE PLAY: Dramatists Guild modern-play style guidance.
    # 12 pt Courier, 1.5" binding margin, page numbers, centered cues,
    # single-spaced dialogue, clearly separated stage directions.
    # ------------------------------------------------------------------
    if target_format == "Stage Play / Dramatic Script":
        doc = Document()
        title_section = doc.sections[0]
        title_section.page_width = Inches(8.5)
        title_section.page_height = Inches(11)
        title_section.left_margin = Inches(1.5)
        title_section.right_margin = Inches(1.0)
        title_section.top_margin = Inches(1.0)
        title_section.bottom_margin = Inches(1.0)
        _set_style_font(doc.styles["Normal"], "Courier New", 12)
        _add_simple_title_page(doc, title, "Stage Play / Dramatic Script", "Courier New")

        section = _new_body_section(doc, left=1.5, right=1.0, top=1.0, bottom=1.0, restart_page=1)
        _configure_top_right_page_numbers(section, hide_first=False, suffix=".")

        act_scene_pat = re.compile(r"^(ACT|SCENE)\b", re.I)
        char_pat = re.compile(r"^[A-Z][A-Z0-9 .,'’()&/\-]{1,45}$")
        stage_direction_pat = re.compile(r"^\(.*\)$")
        heading_pat = re.compile(r"^(CAST OF CHARACTERS|CHARACTERS|SETTING|TIME|PLACE)$", re.I)
        previous_element = ""

        for raw in str(output_text or "").splitlines():
            line = raw.strip()
            if not line:
                previous_element = "blank"
                continue

            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)

            if act_scene_pat.match(line):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(12)
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12, bold=True)
                previous_element = "heading"

            elif heading_pat.match(line):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(6)
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12, bold=True)
                previous_element = "heading"

            elif stage_direction_pat.match(line):
                # Modern-play stage action is visually separated from dialogue.
                p.paragraph_format.left_indent = Inches(2.0)
                p.paragraph_format.right_indent = Inches(0.25)
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12, italic=True)
                previous_element = "direction"

            elif char_pat.match(line) and len(line.split()) <= 7 and not line.endswith((".", "!", "?", ":")):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.keep_with_next = True
                r = p.add_run(line.upper())
                _set_run_font(r, "Courier New", 12, bold=True)
                previous_element = "character"

            elif previous_element in {"character", "dialogue"}:
                p.paragraph_format.left_indent = Inches(0.0)
                p.paragraph_format.right_indent = Inches(0.0)
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12)
                previous_element = "dialogue"

            else:
                r = p.add_run(line)
                _set_run_font(r, "Courier New", 12)
                previous_element = "body"

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # PROSE MANUSCRIPTS: accepted submission-manuscript conventions.
    # 12 pt Times New Roman, 1" margins, double spacing, 0.5" first-line
    # indent, no extra paragraph spacing, upper-right page numbering.
    # ------------------------------------------------------------------
    if target_format in {"Novel / Prose", "Short Story", "Novella", "Standard Manuscript"}:
        doc = Document()
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.header_distance = Inches(0.5)
        _set_style_font(doc.styles["Normal"], "Times New Roman", 12)
        _configure_top_right_page_numbers(section, hide_first=True, suffix="")

        # Clean manuscript title without inventing author/contact metadata.
        for _ in range(5 if target_format == "Short Story" else 2):
            doc.add_paragraph("")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(24)
        r = p.add_run(str(title or "Untitled Project"))
        _set_run_font(r, "Times New Roman", 12, bold=True)

        paragraphs = re.split(r"\n\s*\n", str(output_text or ""))
        for block in paragraphs:
            clean = block.strip()
            if not clean:
                continue

            # Chapter / section headings and scene breaks do not receive first-line indents.
            if re.match(r"^(CHAPTER|PART|PROLOGUE|EPILOGUE)\b", clean, re.I) and len(clean.splitlines()) == 1:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing = 2.0
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(12)
                r = p.add_run(clean)
                _set_run_font(r, "Times New Roman", 12, bold=True)
                continue

            if _is_scene_break(clean):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing = 2.0
                r = p.add_run("#")
                _set_run_font(r, "Times New Roman", 12)
                continue

            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Inches(0.5)
            p.paragraph_format.line_spacing = 2.0
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(clean)
            _set_run_font(r, "Times New Roman", 12)

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # FULL NOVEL BLUEPRINT: no single mandated industry template exists,
    # so use a professional development-document layout with consistent
    # headings, readable body text and page numbering.
    # ------------------------------------------------------------------
    if target_format == "Full Novel Blueprint":
        doc = Document()
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        _set_style_font(doc.styles["Normal"], "Times New Roman", 12)
        _configure_top_right_page_numbers(section, hide_first=False)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(str(title or "Untitled Project"))
        _set_run_font(r, "Times New Roman", 14, bold=True)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(18)
        r = p.add_run("FULL NOVEL BLUEPRINT")
        _set_run_font(r, "Times New Roman", 12, bold=True)

        for raw in str(output_text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(6)
            if re.match(r"^[A-Z][A-Z0-9 /&:\-]{3,}$", line) or line.endswith(":") and len(line.split()) <= 8:
                p.paragraph_format.space_before = Pt(12)
                r = p.add_run(line.rstrip(":"))
                _set_run_font(r, "Times New Roman", 12, bold=True)
            elif line.startswith(("- ", "• ")):
                p.style = doc.styles["List Bullet"]
                r = p.add_run(line[2:].strip())
                _set_run_font(r, "Times New Roman", 12)
            else:
                r = p.add_run(line)
                _set_run_font(r, "Times New Roman", 12)

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # YOUTUBE SHORTS: compact production-script layout.
    # ------------------------------------------------------------------
    if target_format == "YouTube Shorts":
        doc = Document()
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)
        _set_style_font(doc.styles["Normal"], "Arial", 11)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(str(title or "Untitled Project"))
        _set_run_font(r, "Arial", 14, bold=True)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("YOUTUBE SHORTS SCRIPT")
        _set_run_font(r, "Arial", 11, bold=True)

        for raw in str(output_text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.0
            if re.match(r"^(HOOK|BEAT|SHOT|SCENE|VISUAL|NARRATION|DIALOGUE|CTA|END)\b", line, re.I):
                r = p.add_run(line)
                _set_run_font(r, "Arial", 11, bold=True)
            else:
                r = p.add_run(line)
                _set_run_font(r, "Arial", 11)

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # PODCAST: spoken-script layout.
    # ------------------------------------------------------------------
    if target_format == "Podcast Script":
        doc = Document()
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        _set_style_font(doc.styles["Normal"], "Arial", 11)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(str(title or "Untitled Project"))
        _set_run_font(r, "Arial", 14, bold=True)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("PODCAST SCRIPT")
        _set_run_font(r, "Arial", 11, bold=True)

        speaker_pat = re.compile(r"^[A-Z][A-Z0-9 .,'’()&/\-]{1,45}:$")
        heading_pat = re.compile(r"^(INTRO|OPEN|SEGMENT|BREAK|OUTRO|CLOSE|CTA|SPONSOR|AD)\b", re.I)

        for raw in str(output_text or "").splitlines():
            line = raw.strip()
            if not line:
                doc.add_paragraph("")
                continue

            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.05

            if speaker_pat.match(line) or heading_pat.match(line):
                r = p.add_run(line)
                _set_run_font(r, "Arial", 11, bold=True)
            else:
                r = p.add_run(line)
                _set_run_font(r, "Arial", 11)

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # Fallback professional document.
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    _set_style_font(doc.styles["Normal"], "Times New Roman", 12)
    p = doc.add_paragraph(str(title or "Untitled Project"))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for paragraph in re.split(r"\n\s*\n", str(output_text or "")):
        clean = paragraph.strip()
        if clean:
            p = doc.add_paragraph(clean)
            p.paragraph_format.line_spacing = 1.15
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

def save_final_output_artifact_to_supabase(target_format, output_text):
    project_id = get_active_project_id()
    user_id = get_current_user_id()
    if not project_id or not user_id or not str(output_text or "").strip():
        return None
    payload = {
        "final_output_format": str(target_format),
        "final_output_label": get_automatic_output_label(target_format),
        "source_signature": get_text_signature(st.session_state.get("current_draft_output", "")),
        "output_text": str(output_text),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    return supabase.table("writersblock_project_drafts").insert({
        "project_id": project_id,
        "user_id": user_id,
        "draft_title": f"Final Output — {get_automatic_output_label(target_format)}",
        "draft_type": "final_output_conversion",
        "draft_content": json.dumps(payload),
        "version_number": max(1, int(st.session_state.get("manuscript_version", 0) or 0)),
    }).execute()

DIALOGUE_STYLE_OPTIONS = [
    "Story-Driven / Automatic",
    "Dialogue Light",
    "Balanced Dialogue",
    "Dialogue Forward",
    "Narration Only / No Dialogue",
]

# Visible labels show the approximate share of finished words that should be spoken dialogue.
# Canonical option names remain unchanged internally so older saved projects continue to load correctly.
DIALOGUE_STYLE_DISPLAY_LABELS = {
    "Story-Driven / Automatic": "Story-Driven / Automatic (Variable)",
    "Dialogue Light": "Dialogue Light (10-20%)",
    "Balanced Dialogue": "Balanced Dialogue (25-40%)",
    "Dialogue Forward": "Dialogue Forward (40-60%)",
    "Narration Only / No Dialogue": "Narration Only / No Dialogue (0%)",
}

DIALOGUE_STYLE_INSTRUCTIONS = {
    "Story-Driven / Automatic": (
        "Use no fixed dialogue percentage. Let the story determine the natural balance of narration, "
        "action, and spoken dialogue. Use dialogue when it improves character, conflict, pacing, or clarity; "
        "do not force dialogue simply to reach a quota."
    ),
    "Dialogue Light": (
        "Target approximately 10-20% of the finished words as spoken dialogue. Keep dialogue selective "
        "and relatively sparse, with narration, action, description, and internal perspective carrying most "
        "of the story movement. Treat the percentage as a practical target range, not a rigid quota."
    ),
    "Balanced Dialogue": (
        "Target approximately 25-40% of the finished words as spoken dialogue. Use a balanced mix of dialogue "
        "and narration/action so conversation carries meaningful character and plot work without overwhelming "
        "descriptive or narrative development. Treat the percentage as a practical target range, not a rigid quota."
    ),
    "Dialogue Forward": (
        "Target approximately 40-60% of the finished words as spoken dialogue. Make character interaction and "
        "spoken exchanges a major engine of scenes and story movement, while retaining enough narration/action "
        "for clarity, pacing, atmosphere, and transitions. Treat the percentage as a practical target range, not a rigid quota."
    ),
    "Narration Only / No Dialogue": (
        "Target 0% spoken character dialogue. Carry character interaction, information, conflict, and emotional "
        "movement through narration, action, description, thought, or indirect speech."
    ),
}


def get_dialogue_style():
    selected = str(
        st.session_state.get("dialogue_style", "Story-Driven / Automatic")
    ).strip()
    if selected not in DIALOGUE_STYLE_OPTIONS:
        return "Story-Driven / Automatic"
    return selected


def get_dialogue_style_display(style_name=None):
    selected = str(style_name or get_dialogue_style()).strip()
    return DIALOGUE_STYLE_DISPLAY_LABELS.get(selected, selected)


def get_dialogue_style_instruction():
    selected = get_dialogue_style()
    return (
        f"Dialogue Style: {get_dialogue_style_display(selected)}. "
        f"{DIALOGUE_STYLE_INSTRUCTIONS[selected]} "
        "The selected project type controls dialogue formatting and production conventions."
    )


DIALOGUE_FORMAT_INSTRUCTIONS = {
    "Novel / Prose": (
        "Use normal prose dialogue in quotation marks with natural attribution, action beats, "
        "and surrounding narration. Do not use screenplay or stage-play speaker labels."
    ),
    "Short Story": (
        "Use normal prose dialogue in quotation marks with natural attribution, action beats, "
        "and surrounding narration. Do not use screenplay or stage-play speaker labels."
    ),
    "Novella": (
        "Use normal prose dialogue in quotation marks with natural attribution, action beats, "
        "and surrounding narration. Do not use screenplay or stage-play speaker labels."
    ),
    "Screenplay Outline": (
        "Use screenplay conventions when finished scene text is drafted: sluglines, action, "
        "character names, and dialogue blocks. Do not convert screenplay dialogue into quoted prose."
    ),
    "Stage Play / Dramatic Script": (
        "Use stage-play conventions: character labels for spoken lines and appropriate theatrical "
        "action or stage directions. Do not convert the play into ordinary quoted prose."
    ),
    "Audio Book": (
        "During story drafting, write natural prose narration with ordinary quoted character dialogue. "
        "Do not add NARRATOR: or character speaker labels at this stage; the Theatre Production output "
        "later separates narrator and character voices."
    ),
    "Children's Picture Book (32-Page Layout)": (
        "Use short, age-appropriate spoken lines embedded naturally in the story text. Keep dialogue "
        "simple, clear, and suitable for read-aloud pacing; do not use screenplay speaker blocks."
    ),
    "Full Novel Blueprint": (
        "This is a planning blueprint, not finished manuscript prose. Describe where dialogue is needed, "
        "who speaks, its purpose, tone, and key information as planning notes rather than inventing finished dialogue."
    ),
}


def get_dialogue_format_instruction():
    project_type = str(st.session_state.get("format_type") or "Novel / Prose")
    return (
        f"Development project type: {project_type}. During WritersBlock development, keep the working material "
        "in a neutral, readable WritersBlock document form rather than final-output typography. Use ordinary prose "
        "paragraphs and quoted dialogue with natural attribution when spoken dialogue is needed. Do not use screenplay "
        "character blocks, stage-play layout, NARRATOR:/character production labels, or picture-book spread layout during "
        "Steps 1-7. The selected project type may guide story structure and content expectations, but Step 8 Final Output "
        "is responsible for converting the working manuscript into the chosen industry format."
    )


def get_rewrite_dialogue_instruction(rewrite_dialogue_choice):
    current_style = get_dialogue_style()
    selected_choice = str(rewrite_dialogue_choice or "").strip()

    if selected_choice.startswith("Use Current Project Dialogue Style"):
        effective_style = current_style
    elif selected_choice in DIALOGUE_STYLE_OPTIONS:
        effective_style = selected_choice
    else:
        effective_style = current_style

    style_instruction = DIALOGUE_STYLE_INSTRUCTIONS.get(
        effective_style,
        DIALOGUE_STYLE_INSTRUCTIONS["Story-Driven / Automatic"],
    )

    return (
        f"Dialogue Style for this rewrite: {get_dialogue_style_display(effective_style)}. "
        f"{style_instruction} "
        f"PROJECT-TYPE DIALOGUE FORMAT: {get_dialogue_format_instruction()} "
        "Do not change the selected project type or its formatting conventions."
    )


def get_dialogue_development_packet():
    return (
        f"{get_dialogue_style_instruction()} "
        f"PROJECT-TYPE DIALOGUE FORMAT: {get_dialogue_format_instruction()}"
    )


def get_plot_dialogue_context():
    return (
        f"{st.session_state.chosen_option_text}\n\n"
        "DIALOGUE / NARRATION DEVELOPMENT REQUIREMENT:\n"
        f"{get_dialogue_development_packet()}\n"
        "Plan each of the four beats so the selected dialogue/narration balance is visible in the scene design. "
        "Identify where conversation, narration/action, indirect speech, or silence should carry the beat. "
        "Do not write finished manuscript dialogue in the plot outline unless the selected project type itself is a planning blueprint."
    )


def get_scripting_format_context():
    return (
        f"{get_effective_format_type()} | "
        f"DIALOGUE / NARRATION DEVELOPMENT PREFERENCE: {get_dialogue_style_instruction()} "
        "Apply this preference while developing the proposed story paths. "
        "Do not change or reinterpret the selected project type."
    )


def short_date_label(dt_value=None):
    if not dt_value:
        dt = datetime.now()
    else:
        try:
            dt = datetime.fromisoformat(str(dt_value).replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now()
    return f"{dt.month}-{dt.day}-{str(dt.year)[-2:]}"


def get_project_title():
    return str(st.session_state.get("project_title", "") or "").strip()


def get_project_title_for_display():
    title = get_project_title()
    return title if title else "Untitled Project"


def get_series_item_label(format_id=None):
    """Return the series-unit noun that matches the active writing template."""
    selected = str(format_id or st.session_state.get("active_format_id") or "").strip()
    return {
        "novel_prose_novella": "Book",
        "short_story": "Story",
        "screenplay": "Script",
        "stage_play": "Play",
        "youtube_shorts": "Short",
        "audiobook": "Volume",
        "childrens_picture_book": "Book",
        "full_novel_blueprint": "Book",
        "podcast_script": "Episode",
    }.get(selected, "Series Item")


def get_series_item_display(format_id=None, number=None):
    label = get_series_item_label(format_id)
    resolved_number = int(number or st.session_state.get("series_book_number", 1) or 1)
    return f"{label} {resolved_number}"


def rename_current_project_everywhere(new_title):
    """
    Rename the active project without calling Gemini.
    Updates the project record, saved session metadata, series metadata,
    saved draft titles that contain the old title, manuscript-version labels,
    and immediately saves the current working state for licensed users.
    """
    clean_title = re.sub(r"\\s+", " ", str(new_title or "").strip())

    if not clean_title:
        return False, "Project title cannot be blank."

    if len(clean_title) > 120:
        return False, "Project title must be 120 characters or fewer."

    old_title = get_project_title()
    if clean_title == old_title:
        return True, "Project title is already current."

    project_id = get_active_project_id()
    user_id = get_current_user_id()

    # Before a database project exists, this is only the initial project naming stage.
    if not project_id:
        st.session_state.project_title = clean_title
        return True, "Project title updated for the current project setup."

    try:
        # 1) Update the authoritative project record.
        project_update = (
            supabase.table("writersblock_projects")
            .update({"project_title": clean_title})
            .eq("id", project_id)
        )
        if user_id:
            project_update = project_update.eq("user_id", user_id)
        project_update.execute()

        # 2) Update manuscript-version labels so an old/misspelled title
        #    does not remain embedded in Saved Versions.
        version_query = (
            supabase.table("writersblock_manuscript_versions")
            .select("id, version_label")
            .eq("project_id", project_id)
        )
        if user_id:
            version_query = version_query.eq("user_id", user_id)

        version_rows = version_query.execute().data or []
        for row in version_rows:
            version_id = row.get("id")
            old_label = str(row.get("version_label") or "")
            if not version_id or not old_label:
                continue

            new_label = old_label
            if old_title and old_title in old_label:
                new_label = old_label.replace(old_title, clean_title)

            if new_label != old_label:
                (
                    supabase.table("writersblock_manuscript_versions")
                    .update({"version_label": new_label})
                    .eq("id", version_id)
                    .execute()
                )

        # 3) Update project-session snapshots and relevant draft metadata.
        draft_query = (
            supabase.table("writersblock_project_drafts")
            .select("id, draft_title, draft_type, draft_content")
            .eq("project_id", project_id)
        )
        if user_id:
            draft_query = draft_query.eq("user_id", user_id)

        draft_rows = draft_query.execute().data or []
        for row in draft_rows:
            draft_id = row.get("id")
            if not draft_id:
                continue

            draft_title = str(row.get("draft_title") or "")
            draft_type = str(row.get("draft_type") or "")
            draft_content = str(row.get("draft_content") or "")
            updates = {}

            if old_title and old_title in draft_title:
                updates["draft_title"] = draft_title.replace(old_title, clean_title)

            if draft_type in {"project_session", "series_metadata"} and draft_content:
                try:
                    payload = json.loads(draft_content)
                except Exception:
                    payload = None

                if isinstance(payload, dict):
                    if draft_type == "project_session":
                        payload["project_title"] = clean_title
                    elif draft_type == "series_metadata":
                        payload["project_title"] = clean_title
                    updates["draft_content"] = json.dumps(payload)

            if updates:
                (
                    supabase.table("writersblock_project_drafts")
                    .update(updates)
                    .eq("id", draft_id)
                    .execute()
                )

        # 4) Update the current live project title and loaded-project identity.
        st.session_state.project_title = clean_title
        st.session_state["_wbs_loaded_project_id"] = str(project_id)
        st.session_state["_wbs_loaded_project_title"] = clean_title

        # Project identity changed; this operation does NOT create a new version.
        # Explicit edits must be saved separately using New Version.
        return True, f'Project renamed to "{clean_title}". Earlier versions remain available; edits require a new version.'

    except Exception as exc:
        return False, f"Project rename could not be completed: {exc}"


def render_confirmed_project_rename(stage_key):
    """Two-step confirmation required to change an existing project's master title.

    This control never saves a project version. A new project's initial title is
    edited normally before the master is saved.
    """
    project_id = str(get_active_project_id() or "")
    if not project_id or st.session_state.get("demo_mode"):
        return
    safe_stage = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stage_key or "stage"))
    prefix = f"wbs_rename_{safe_stage}_{project_id}"
    title = get_project_title_for_display()
    source_key = f"{prefix}_original"
    edit_key = f"{prefix}_new"
    pending_key = f"{prefix}_pending"

    # Reset the proposed title after switching projects or completing a rename.
    if st.session_state.get(source_key) != title:
        st.session_state[source_key] = title
        st.session_state[edit_key] = title
        st.session_state.pop(pending_key, None)

    pending = st.session_state.get(pending_key)
    with st.expander("Rename Project", expanded=bool(pending)):
        proposed = st.text_input("New Project Title:", key=edit_key, max_chars=120)
        clean = re.sub(r"\s+", " ", str(proposed or "").strip())
        # A confirmation expires immediately if the title, project, or proposal
        # differs from what the writer previously reviewed.
        matches = (
            isinstance(pending, dict)
            and pending.get("project_id") == project_id
            and pending.get("old_title") == title
            and pending.get("new_title") == clean
            and clean != title
        )
        if matches:
            st.warning(f'Change project title from "{title}" to "{clean}"? This will update the title on existing saved versions, but will not create a new version.')
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Confirm Title Change", key=f"{prefix}_confirm", type="primary", use_container_width=True):
                    # Independently recheck identity on the final click; never
                    # confirm a stale title preview from another project.
                    if str(get_active_project_id() or "") != project_id or get_project_title_for_display() != title:
                        st.session_state.pop(pending_key, None)
                        st.error("Project changed during confirmation. Title was not changed.")
                    else:
                        ok, message = rename_current_project_everywhere(clean)
                        if ok:
                            st.session_state.pop(pending_key, None)
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
            with cancel_col:
                if st.button("Cancel Rename", key=f"{prefix}_cancel", use_container_width=True):
                    st.session_state.pop(pending_key, None)
                    st.rerun()
        else:
            if pending is not None:
                st.session_state.pop(pending_key, None)
                st.caption("The proposed title changed. Review it again before confirming.")
            if st.button("Review Title Change", key=f"{prefix}_review", disabled=not clean or clean == title, use_container_width=True):
                st.session_state[pending_key] = {
                    "project_id": project_id,
                    "old_title": title,
                    "new_title": clean,
                }
                st.rerun()


def get_loaded_project_series_versions(project_id):
    """Saved versions ONLY for the loaded project, with exact source IDs/word totals."""
    active_id = str(get_active_project_id() or "")
    if not project_id or str(project_id) != active_id:
        return []
    result = []
    for item in get_saved_projects_versions_dropdown_items():
        row = item.get("row") or {}
        if str(row.get("project_id") or "") != active_id:
            continue
        kind = item.get("type")
        if kind == "manuscript_version":
            saved_text = str(row.get("manuscript_content") or "")
        elif kind == "project_session":
            try:
                snapshot = json.loads(row.get("draft_content") or "{}")
            except (ValueError, TypeError):
                snapshot = {}
            saved_text = get_best_saved_manuscript_source(snapshot) if isinstance(snapshot, dict) and snapshot else ""
            if not saved_text and isinstance(snapshot, dict):
                saved_text = str(snapshot.get("story_seed") or "")
        else:
            continue
        key = f"{kind}:{row.get('id')}"
        result.append({"key": key, "type": kind, "id": str(row.get("id") or ""),
                       "label": str(item.get("label") or ""),
                       "words": count_words(saved_text)})
    return result



def get_assigned_series_projects_for_display(series_name):
    """Read-only: one book per distinct author-recognized project, not all history.

    Legacy saved sessions can contain accidental series links and duplicate project
    IDs. Those records remain intact; they do not automatically become approved
    book references. An exact saved source is authoritative only after explicit
    Save Project to Series confirmation.
    """
    series_key = make_series_key(series_name)
    if not series_key or not get_current_user_id():
        return []
    membership = {str(pid): dict(meta) for pid, meta in get_series_metadata_by_project().items()
                  if str(meta.get("series_key") or "") == series_key}
    projects = {str(row.get("id")): row for row in get_projects_for_import() if row.get("id")}
    membership = {pid: meta for pid, meta in membership.items() if pid in projects}
    if not membership:
        return []

    # Oakhaven's five historical book titles were expressly confirmed by its
    # owner. This is presentation-only: DO NOT alter, delete, or attach records.
    # Other series work generically from their own saved memberships.
    recognized_titles = (
        "It's Not Safe", "Return To Sender", "The Dead Letters Covenant",
        "Chronos' Grasp", "Blood Of The Ancients",
    ) if str(series_name or "").strip().casefold() == "oakhaven" else ()

    saved_versions = {}
    for item in get_saved_projects_versions_dropdown_items():
        row = item.get("row") or {}
        pid = str(row.get("project_id") or "")
        if pid not in membership:
            continue
        kind = str(item.get("type") or "")
        rid = str(row.get("id") or "")
        if kind not in ("manuscript_version", "project_session") or not rid:
            continue
        saved_versions.setdefault(pid, []).append((kind, rid, row, item))

    grouped = {}
    for pid, meta in membership.items():
        title = str(projects[pid].get("project_title") or meta.get("project_title") or "Untitled Project").strip()
        group_key = title.casefold()
        if recognized_titles and group_key not in {t.casefold() for t in recognized_titles}:
            continue  # Legacy extras are not an approved Oakhaven book reference.
        options = saved_versions.get(pid) or []
        chosen = next((entry for entry in options
                       if entry[0] == str(meta.get("series_source_type") or "")
                       and entry[1] == str(meta.get("series_source_id") or "")), None)
        pinned = chosen is not None
        if chosen is None and options:
            chosen = max(options, key=lambda entry: (str(entry[2].get("created_at") or ""), entry[1]))
        candidate = {"project_id": pid, "title": title, "meta": meta,
                     "selected": chosen, "confirmed": pinned,
                     "creation": str(projects[pid].get("created_at") or "")}
        grouped.setdefault(group_key, []).append(candidate)

    preferred = []
    for title_key, candidates in grouped.items():
        # Duplicate project names are old ambiguous records; do not present them
        # as additional books. Prefer a manually selected saved revision.
        winner = sorted(candidates, key=lambda c: (
            0 if c["confirmed"] else 1,
            c["creation"], c["project_id"]))[0]
        preferred.append(winner)

    # Only an explicitly saved series order overrides the owner's initial five-
    # book Oakhaven sequence. Ordering never changes the manuscript version.
    current_order = get_series_order_overrides().get(series_key)
    if current_order:
        positions = {pid: index for index, pid in enumerate(current_order)}
        preferred.sort(key=lambda c: (positions.get(c["project_id"], 100000), c["creation"], c["project_id"]))
    elif recognized_titles:
        ranks = {name.casefold(): i for i, name in enumerate(recognized_titles)}
        preferred.sort(key=lambda c: (ranks.get(c["title"].casefold(), 10000), c["creation"]))
    else:
        preferred.sort(key=lambda c: (int(c["meta"].get("series_book_number") or 10000), c["creation"], c["project_id"]))

    displayed = []
    for book_number, entry in enumerate(preferred, 1):
        choice = entry["selected"]
        if choice:
            kind, rid, row, item = choice
            match = re.search(r" — (V-\d+[A-Z]*)(?: —|$)", str(item.get("label") or ""))
            revision = match.group(1) if match else (
                f"V-{row.get('version_number')}" if row.get("version_number") else "Version unknown")
            try:
                saved_date = datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00")).strftime("%m/%d/%Y")
            except (TypeError, ValueError):
                saved_date = "Date unavailable"
            if kind == "manuscript_version":
                words = count_words(row.get("manuscript_content") or "")
            else:
                try:
                    snapshot = json.loads(row.get("draft_content") or "{}")
                except (TypeError, ValueError):
                    snapshot = {}
                text = get_best_saved_manuscript_source(snapshot) if isinstance(snapshot, dict) else ""
                if not text and isinstance(snapshot, dict):
                    text = str(snapshot.get("story_seed") or "")
                words = count_words(text)
            source_type, source_id = kind, rid
        else:
            revision, saved_date, words, source_type, source_id = "Unselected", "Date unavailable", 0, "", ""
        label = f"Book {book_number} — {entry['title']} — {revision} — {saved_date} — {words:,} words"
        displayed.append({
            "project_id": entry["project_id"], "book_number": book_number,
            "title": entry["title"], "revision": revision, "date": saved_date,
            "words": words, "confirmed": entry["confirmed"], "label": label,
            "source_type": source_type, "source_id": source_id,
            "note": ("Confirmed series version" if entry["confirmed"]
                     else "Historical series link — displayed revision is ONLY a preview; confirm it from the loaded project to select it for the series"),
        })
    return displayed


def get_series_reference_preview_text(member):
    """Return an existing saved book for PREVIEW ONLY, never load its project."""
    if not member or not get_current_user_id():
        return ""
    pid, kind, rid = (str(member.get(key) or "")
                      for key in ("project_id", "source_type", "source_id"))
    if not pid or not rid or kind not in ("manuscript_version", "project_session"):
        return ""
    for item in get_saved_projects_versions_dropdown_items():
        row = item.get("row") or {}
        if (str(row.get("project_id") or "") != pid or
            str(row.get("id") or "") != rid or
            item.get("type") != kind):
            continue
        if kind == "manuscript_version":
            return str(row.get("manuscript_content") or "")
        try:
            data = json.loads(row.get("draft_content") or "{}")
        except (ValueError, TypeError):
            return ""
        if isinstance(data, dict):
            return get_best_saved_manuscript_source(data) or str(data.get("story_seed") or "")
    return ""


def change_series_reference_book_number(series_name, visible_members, selected_pid, requested_number):
    """Reorder ONLY books shown to the writer; preserve all other legacy links.

    A single append-only series_order record is the sole database mutation.
    Existing projects, versions and manuscripts are never updated or deleted.
    """
    visible_ids = [str(x.get("project_id")) for x in visible_members]
    if not selected_pid or selected_pid not in visible_ids:
        raise ValueError("Selected book is no longer in this series.")
    if len(visible_ids) != len(set(visible_ids)):
        raise ValueError("Duplicate book records; series order was not changed.")
    target = int(requested_number)
    if not 1 <= target <= len(visible_ids):
        raise ValueError("Choose a valid book number.")
    updated = [pid for pid in visible_ids if pid != selected_pid]
    updated.insert(target - 1, selected_pid)
    if updated == visible_ids:
        return False
    # The membership catalog may include unconfirmed duplicate/legacy entries.
    # Preserve their relative order after the visible approved books.
    full_ids = ordered_series_members(series_name)
    if not set(visible_ids).issubset(set(full_ids)):
        raise ValueError("Series membership has changed. Reload before changing book order.")
    proposed = updated + [pid for pid in full_ids if pid not in visible_ids]
    save_series_book_order(series_name, proposed)
    return True


def render_save_open_project_to_series():
    """Explicit series/reference selection, scoped to the loaded project ID."""
    project_id = str(get_active_project_id() or "")
    if not project_id or not get_current_user_id() or st.session_state.get("demo_mode"):
        return
    confirmed_title = get_project_title_from_project_id(project_id)
    if not confirmed_title or confirmed_title != get_project_title():
        st.caption("Load the saved project before changing its series.")
        return
    membership = get_series_metadata_by_project().get(project_id) or {}
    current_series = str(membership.get("series_name") or "")
    current_source = f"{membership.get('series_source_type') or ''}:{membership.get('series_source_id') or ''}"
    versions = get_loaded_project_series_versions(project_id)
    if not versions:
        st.caption("No saved versions of this project are available for a series reference.")
        return
    ui_prefix = f"wbs_series_save_{project_id}"
    with st.expander("Save Project to Series", expanded=False):
        st.caption("Only the open project's saved versions are eligible. Your manuscript and version history are not changed.")
        known_series = get_existing_series_names()
        series_options = list(known_series) + ["Create New Series", "Standalone (Remove series link)"]
        series_col, projects_col = st.columns([1, 3], gap="medium")
        with series_col:
            selection = st.selectbox(
                "Select Series:", series_options,
                index=(known_series.index(current_series) if current_series in known_series else 0),
                key=f"{ui_prefix}_series")
        if selection == "Create New Series":
            destination = st.text_input("New Series Name:", key=f"{ui_prefix}_new", max_chars=80).strip()
        elif selection == "Standalone (Remove series link)":
            destination = ""
        else:
            destination = selection
        members = get_assigned_series_projects_for_display(destination) if destination else []
        with projects_col:
            if members:
                # Use stable project identity in widget keys; reruns after selecting
                # another series cannot reuse a different series' previous row.
                member_ids = [entry["project_id"] for entry in members]
                selected_pid = st.selectbox(
                    "Series Projects:", member_ids,
                    format_func=lambda pid: next(m["label"] for m in members if m["project_id"] == pid),
                    key=f"{ui_prefix}_members_{make_series_key(destination)}")
            else:
                selected_pid = None
                st.selectbox("Series Projects:", ["No projects selected for this series"],
                             disabled=True, key=f"{ui_prefix}_members_empty")
        member = next((m for m in members if m["project_id"] == selected_pid), None)
        if member:
            st.caption(member["label"])  # Full text wraps, even if a selectbox truncates.
            if not member["confirmed"]:
                st.caption(member["note"])
            if st.checkbox("View Selected Saved Book (read-only)",
                           key=f"{ui_prefix}_preview_{make_series_key(destination)}_{selected_pid}"):
                preview = get_series_reference_preview_text(member)
                if preview:
                    st.text_area("Saved Book Preview — no changes permitted", value=preview,
                                 height=240, disabled=True,
                                 key=f"{ui_prefix}_preview_text_{selected_pid}_{member['source_id']}")
                else:
                    st.caption("No readable text is available from this saved revision. The saved project has not been changed.")

            # Assign a different BOOK number without changing the chosen saved
            # revision, its title or date. Explicit confirmation is required.
            new_book_number = st.selectbox(
                "Change Book Number:", list(range(1, len(members) + 1)),
                format_func=lambda num: f"Book {num}",
                index=member["book_number"] - 1,
                key=f"{ui_prefix}_book_num_{make_series_key(destination)}_{selected_pid}")
            if new_book_number != member["book_number"]:
                order_token = hashlib.sha256(
                    f"{destination}:{selected_pid}:{new_book_number}:{[m['project_id'] for m in members]}".encode("utf-8")
                ).hexdigest()[:12]
                order_confirm = st.checkbox(
                    f"Confirm move of {member['title']} to Book {new_book_number}",
                    key=f"{ui_prefix}_order_confirm_{order_token}", value=False)
                if st.button("Update Book Order", disabled=not order_confirm,
                             key=f"{ui_prefix}_order_save_{order_token}"):
                    try:
                        changed = change_series_reference_book_number(
                            destination, members, selected_pid, new_book_number)
                    except Exception as exc:
                        st.error(f"Book order was not changed: {exc}")
                    else:
                        if changed:
                            st.success("Book order updated. Saved project versions were not changed.")
                            st.rerun()
        st.divider()
        labels = [f"{v['label']} — {v['words']:,} words" for v in versions]
        loaded_id = str(st.session_state.get("_wbs_loaded_saved_session_id") or "")
        loaded_manuscript_id = str(st.session_state.get("_wbs_loaded_manuscript_version_id") or "")
        loaded_key = (f"manuscript_version:{loaded_manuscript_id}" if loaded_manuscript_id
                      else f"project_session:{loaded_id}")
        default_key = (loaded_key if loaded_key in [v["key"] for v in versions]
                       else current_source)
        default_index = next((idx for idx,v in enumerate(versions) if v["key"] == default_key), 0)
        selected_idx = st.selectbox(
            "Saved Version to Use in Series:", list(range(len(versions))),
            format_func=lambda idx: labels[idx], index=default_index,
            key=f"{ui_prefix}_revision_{loaded_manuscript_id or loaded_id or 'unspecified'}")
        picked = versions[selected_idx]
        st.caption(f"Selected saved version: {picked['words']:,} words. This does not load or rewrite that version.")
        # Confirmation is bound to this exact project, destination, and version.
        # Changing either dropdown requires a fresh checkmark.
        confirmation_token = hashlib.sha256(
            f"{project_id}:{destination}:{picked['key']}".encode("utf-8")
        ).hexdigest()[:12]
        confirm = st.checkbox(
            "Confirm series and saved version", key=f"{ui_prefix}_confirm_{confirmation_token}", value=False)
        if st.button("Save Project to Series", key=f"{ui_prefix}_submit",
                     use_container_width=True, disabled=not confirm or (not destination and selection != "Standalone (Remove series link)")):
            # Re-verify owner/project and selected revision. No foreign titles/IDs.
            if str(get_active_project_id() or "") != project_id or get_project_title_from_project_id(project_id) != confirmed_title:
                st.error("The open project changed; series assignment cancelled.")
            elif selection == "Standalone (Remove series link)" and not current_series:
                st.info("This project is already standalone.")
            else:
                try:
                    changed = assign_saved_project_to_series(project_id, destination, picked)
                except Exception as exc:
                    st.error(f"Series assignment was not saved: {exc}")
                else:
                    if not changed:
                        st.info("No change to the current series/version assignment.")
                    else:
                        st.session_state.project_scope = "Book in a Series" if destination else "Standalone Book"
                        st.session_state.series_name = destination
                        st.session_state.series_key = make_series_key(destination)
                        st.success("Series reference saved. Manuscripts and project versions were not modified.")
                        st.rerun()


def wbs_stage4_title_input_key():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_title_input_key', globals())


def wbs_stage4_save_renamed_title_as_new_v1(new_title):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_save_renamed_title_as_new_v1', globals(), new_title)


def wbs_stage4_final_status(record, title, manuscript, report, report_source_signature, scene_approval_complete, project_id=None, revision_id=None):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_final_status', globals(), record, title, manuscript, report, report_source_signature, scene_approval_complete, project_id, revision_id)


def wbs_stage4_save_final_acceptance(component):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_save_final_acceptance', globals(), component)



def wbs_stage4_confirm_and_save_from_checkbox(component, widget_key):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_confirm_and_save_from_checkbox', globals(), component, widget_key)


def render_project_title_banner(stage_key):
    """Universal format-aware title/revision; series assignment unchanged."""
    current_title = get_project_title_for_display()
    format_name = str(st.session_state.get("format_type") or st.session_state.get("active_format_id") or "Project")
    revision = str(globals().get("_active_version_number") or st.session_state.get("current_version_number") or "").strip()
    # Match the active saved revision displayed in Project Status.
    revision_display = revision if revision.upper().startswith("V-") else ("V-" + revision if revision.isdigit() else "")
    st.markdown("<style>[class*='st-key-wbs_stage_title_'] input:disabled {color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important;}</style>", unsafe_allow_html=True)
    if stage_key == "step_5_script_lock":
        # Rename always starts blank. The project name never embeds V numbers;
        # Saved Projects / Versions adds V-1 and the date when the copy is saved.
        _title_key = wbs_stage4_title_input_key()
        if _title_key not in st.session_state:
            st.session_state[_title_key] = ""
        _current_col, _rename_col, _save_col = st.columns([1.25, 1.25, .75], gap="small", vertical_alignment="bottom")
        # The read-only field is HTML to keep its value fully white. Match
        # Streamlit's text-input dimensions precisely so all three controls
        # line up along their bottom edges. Do not use a disabled input:
        # Streamlit dims the entire control even with CSS color overrides.
        st.markdown("""<style>
        div[data-testid="stMarkdown"]:has(.wbs-stage4-current-title) {
            margin: 0 !important;
            padding: 0 !important;
        }
        .wbs-stage4-current-title {
            box-sizing: border-box;
            height: 68px;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            margin: 0;
        }
        .wbs-stage4-current-title .wbs-title-caption {
            box-sizing: border-box;
            height: 20px;
            line-height: 20px;
            margin: 0 0 8px 0;
            color: #fff;
            font-size: 0.875rem;
            font-weight: 400;
        }
        .wbs-stage4-current-title .wbs-title-value {
            box-sizing: border-box;
            height: 40px;
            min-height: 40px;
            display: flex;
            align-items: center;
            padding: 0 12px;
            border: 1px solid #656d79;
            border-radius: 0.5rem;
            background: #262b36;
            color: #fff !important;
            opacity: 1 !important;
            font-size: 1rem;
            font-weight: 600;
            line-height: 1.5rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        </style>""", unsafe_allow_html=True)
        with _current_col:
            _current_label = current_title + (" — " + revision_display if revision_display else "")
            st.markdown(
                # Offset the markdown-only display by the 14px extra widget
                # spacing measured against Streamlit's adjacent native input.
                # Visual correction only: read-only title and saved data untouched.
                '<div class="wbs-stage4-current-title" style="position:relative;top:-14px">'
                '<div class="wbs-title-caption">Current Project Title/Version</div>'
                '<div class="wbs-title-value">' + html.escape(_current_label) + '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with _rename_col:
            st.text_input(
                "Rename Your Project and save",
                key=_title_key,
                max_chars=120,
                placeholder="Enter new project title",
                disabled=bool(st.session_state.get("demo_mode")),
            )
        with _save_col:
            if st.button(
                "Save Title Change", type="primary", key="wbs_stage4_save_title_inline",
                use_container_width=True,
                disabled=bool(st.session_state.get("demo_mode")),
                help="Save a separate project copy starting at V-1; preserve the existing project and revision.",
            ):
                _proposed_name = re.sub(r"\s+", " ", str(st.session_state.get(_title_key) or "")).strip()
                if not _proposed_name or len(_proposed_name) > 120:
                    st.error("Enter a new project title of 1–120 characters before saving.")
                elif re.search(r"(?:^|\s)[—–-]?\s*V-?\d+[A-Za-z]?\s*$", _proposed_name, re.I):
                    st.error("Enter only the new title. The V-number and date are added in Saved Projects automatically.")
                elif _proposed_name.casefold() == current_title.casefold():
                    st.info("Enter a different title to create a renamed V-1 copy. No data was changed.")
                else:
                    try:
                        _made_copy = wbs_stage4_save_renamed_title_as_new_v1(_proposed_name)
                        if not _made_copy:
                            raise ValueError("No renamed project was created.")
                    except Exception as exc:
                        st.error(f"Project rename was not saved: {exc}")
                    else:
                        # The new V-1 is independent of the original project.
                        # Confirm its saved title on the NEW revision so the
                        # existing Stage 4 approval path still works.
                        try:
                            wbs_stage4_save_final_acceptance("title")
                        except Exception as exc:
                            st.warning(f"The renamed V-1 project was saved, but title approval needs retrying: {exc}")
                        st.session_state.pop(_title_key, None)
                        st.success("Renamed project saved as V-1 with today's date in Saved Projects. The previous revision is preserved.")
                        st.rerun()
    else:
        st.markdown(f"**{format_name} / Project Title/Revision**")
        st.text_input("Project Title/Revision", value=(current_title + (" — " + revision_display if revision_display and revision_display not in current_title else "")), disabled=True, label_visibility="collapsed", key=f"wbs_stage_title_{stage_key}_{revision_display}_{str(get_active_project_id() or 'unsaved')}")
    if stage_key == "step_2_scripting":
        _saved_path = bool(str(st.session_state.get("chosen_option") or "").strip() and str(st.session_state.get("chosen_option_text") or "").strip())
        if _saved_path:
            st.caption("Revision Status: Plot Architecture COMPLETE — selected plot saved. Next: Scene Scripting." if st.session_state.get("_wbs_active_saved_session_row_id") else "Revision Status: Plot selection ready; save to preserve it.")
        else:
            st.caption("Revision Status: Plot Architecture INCOMPLETE — no plot selected. Last completed: Concept Development. Next: Select a plot and save.")
    if st.session_state.get("project_stage") != "Intake" and (st.session_state.get("licensed_mode") or st.session_state.get("demo_mode")):
        render_quill_for_current_stage(st_module=st, show_prelude=True)
    # Series assignment is handled in Stage 1 (Concept Development) only.
    # Do not present the Series control during review, scripting or final output.


def make_version_display_label(version):
    """Compact visible label; stage remains stored internally for resume routing."""
    version_number = int((version or {}).get("version_number") or 1)
    project_title = str(
        (version or {}).get("project_title")
        or (version or {}).get("title")
        or get_project_title_for_display()
    ).strip()
    word_count = count_words((version or {}).get("manuscript_content", ""))
    status, _stage_label = get_manuscript_version_status_stage(version or {})
    return f"{project_title} — {status} V{version_number} — {word_count} words"

def full_date_label(dt_value=None):
    if not dt_value:
        dt = datetime.now()
    else:
        try:
            dt = datetime.fromisoformat(str(dt_value).replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now()
    return f"{dt.month:02d}/{dt.day:02d}/{dt.year}"


def get_saved_project_sessions_for_dropdown():
    user_id = get_current_user_id()

    if not user_id:
        return []

    query = (
        supabase.table("writersblock_project_drafts")
        .select("id, project_id, draft_content, created_at, version_number")
        .eq("draft_type", "project_session")
        .order("created_at", desc=True)
    )

    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()
    return result.data or []


# WBS_SIDEBAR_DRAFT_FINAL_LABELS_2026_09_08
def get_saved_projects_versions_dropdown_items():
    """List all saved entries, grouped by project, most recently saved first.

    The numbering and ordering affect presentation ONLY; no database writes.
    """
    items = []

    for version in list(get_all_manuscript_versions_for_user() or []):
        project_join = version.get("writersblock_projects") or {}
        if isinstance(project_join, dict):
            version["project_title"] = project_join.get("project_title") or version.get("project_title")
        title = str(version.get("project_title") or version.get("title") or "Untitled Project").strip()
        status, _stage_label = get_manuscript_version_status_stage(version)
        branch_name = get_manuscript_branch_name(version)
        words = count_words(version.get("manuscript_content", ""))
        items.append({
            "type": "manuscript_version", "row": version,
            "version_name": branch_name, "_title": title,
            "_time": str(version.get("created_at") or ""),
            "_detail": f"{branch_name} — {status} — {words} words",
        })

    # Keep ALL session saves, including numbered successive saves of a branch.
    # Do not discard earlier entries: they may be the only recoverable copy.
    for saved_row in get_saved_project_sessions_for_dropdown():
        try:
            snapshot = json.loads(saved_row.get("draft_content") or "{}")
        except Exception:
            snapshot = {}
        title = str(snapshot.get("project_title") or "Untitled Project").strip()
        branch_name = clean_project_version_name(
            snapshot.get("project_version_name") or "Original"
        ) or "Original"
        saved_time = str(saved_row.get("created_at") or snapshot.get("saved_at") or "")
        items.append({
            "type": "project_session", "row": saved_row,
            "version_name": branch_name, "_title": title,
            "_time": saved_time, "_detail": branch_name,
        })

    # Assign numbers chronologically within each project. Display recent first.
    by_project = {}
    for item in items:
        project_key = item["_title"].strip().casefold()
        by_project.setdefault(project_key, []).append(item)

    groups = []
    for group in by_project.values():
        chronological = sorted(group, key=lambda item: (item["_time"], str(item["row"].get("id") or "")))
        base_number = 0
        for item in chronological:
            if (item.get('type') == 'manuscript_version'
                    and str(item.get('row', {}).get('source_stage') or '') == 'script_lock_revision'):
                tagged = re.search(r' — (V-\d+[A-Z]+)(?: —|$)',
                                   str(item.get('row', {}).get('version_label') or ''))
                display_tag = tagged.group(1) if tagged else f'V-{max(base_number, 1)}A'
                item['_ordinal'] = base_number
                item['label'] = f"{item['_title']} — {display_tag} — {full_date_label(item['_time'])}"
            else:
                base_number += 1
                item['_ordinal'] = base_number
                item['label'] = f"{item['_title']} — V-{base_number} — {full_date_label(item['_time'])}"
        groups.append(sorted(group, key=lambda item: (item["_time"], item["_ordinal"]), reverse=True))

    groups.sort(key=lambda group: group[0]["_time"] if group else "", reverse=True)
    result = []
    for group in groups:
        for item in group:
            # Remove presentation-only fields before returning.
            for key in ("_title", "_time", "_detail", "_ordinal"):
                item.pop(key, None)
            result.append(item)
    return result


# ==========================================
# SERIES CONTINUITY SUPPORT
# ==========================================
def make_series_key(series_name):
    clean_name = re.sub(r"[^a-z0-9]+", "-", str(series_name or "").strip().lower()).strip("-")
    if not clean_name:
        return ""
    user_id = str(get_current_user_id() or "local-user")
    return hashlib.sha256(f"{user_id}:{clean_name}".encode("utf-8")).hexdigest()[:24]


def get_series_metadata_rows():
    user_id = get_current_user_id()

    if not user_id:
        return []
    query = (
        supabase.table("writersblock_project_drafts")
        .select("id, project_id, user_id, draft_content, created_at")
        .eq("draft_type", "series_metadata")
        .order("created_at", desc=True)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    try:
        result = query.execute()
    except Exception:
        return []

    rows = []
    seen_project_ids = set()
    for row in result.data or []:
        project_id = row.get("project_id")
        if not project_id or project_id in seen_project_ids:
            continue
        try:
            metadata = json.loads(row.get("draft_content") or "{}")
        except Exception:
            metadata = {}
        if not isinstance(metadata, dict):
            continue
        metadata["_project_id"] = project_id
        metadata["_created_at"] = row.get("created_at")
        rows.append(metadata)
        seen_project_ids.add(project_id)
    return rows


def get_series_order_overrides():
    """Read the latest explicit order PER series. No project-session edits."""
    user_id = get_current_user_id()
    if not user_id:
        return {}
    try:
        rows = (supabase.table("writersblock_project_drafts")
                .select("project_id, draft_content, created_at")
                .eq("user_id", user_id).eq("draft_type", "series_order")
                .order("created_at", desc=True).execute()).data or []
    except Exception:
        # Failure must never silently destroy or invent a series ordering.
        return {}
    result = {}
    for row in rows:
        try:
            data = json.loads(row.get("draft_content") or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        key = str(data.get("series_key") or "")
        ids = data.get("ordered_project_ids")
        if key and key not in result and isinstance(ids, list):
            result[key] = list(dict.fromkeys(str(pid) for pid in ids if pid))
    return result


def ordered_series_members(series_name, membership=None):
    """Unique project IDs, ordered Book 1..N, never manuscript/version rows."""
    membership = membership if membership is not None else get_series_metadata_by_project()
    key = make_series_key(series_name)
    return [pid for pid, row in sorted(
        membership.items(), key=lambda pair: (int(pair[1].get("series_book_number") or 9999), pair[0]))
        if str(row.get("series_key") or "") == key]


def save_series_book_order(series_name, ordered_ids):
    """One append-only, project-owned order record: single DB write per move."""
    user_id = get_current_user_id()
    series_key = make_series_key(series_name)
    verified = ordered_series_members(series_name)
    proposed = [str(pid) for pid in ordered_ids]
    if not user_id or not series_key or not proposed or len(set(proposed)) != len(proposed):
        raise ValueError("Choose a series containing saved projects.")
    if set(proposed) != set(verified):
        raise ValueError("Series membership changed. Refresh before reordering.")
    if proposed == verified:
        return None
    # PostgREST insert into the existing drafts table; never mutate manuscripts,
    # projects, or project-session snapshots.
    body = {"series_name": series_name, "series_key": series_key,
            "ordered_project_ids": proposed, "saved_at": datetime.now(timezone.utc).isoformat()}
    result = (supabase.table("writersblock_project_drafts")
              .insert({"project_id": proposed[0], "user_id": user_id,
                       "draft_type": "series_order", "draft_title": "Series Book Order",
                       "draft_content": json.dumps(body), "version_number": 0})
              .execute())
    if not getattr(result, "data", None):
        raise RuntimeError("Series book order was not confirmed saved.")
    return result


def assign_saved_project_to_series(project_id, series_name, selected_version=None):
    """Save series membership and the writer's chosen version, without editing any text."""
    user_id = get_current_user_id()
    project_id = str(project_id or "")
    name = str(series_name or "").strip()
    if not user_id or not project_id:
        raise ValueError("Select a saved project.")
    projects = {str(row.get("id")): row for row in get_projects_for_import() if row.get("id")}
    if project_id not in projects:
        raise ValueError("The saved project was not found in your account.")
    prior = get_series_metadata_by_project().get(project_id) or {}
    old_name = str(prior.get("series_name") or "").strip()

    # Verify the exact selected revision belongs to the logged-in user's LOADED
    # project. Never accept only a title or an unverified browser widget value.
    selected_info = {}
    if name:
        if not isinstance(selected_version, dict):
            raise ValueError("Select and confirm a saved version of the open project.")
        selected_type = str(selected_version.get("type") or "")
        selected_id = str(selected_version.get("id") or "")
        if selected_type == "manuscript_version":
            rows = (supabase.table("writersblock_manuscript_versions")
                    .select("id, project_id, user_id, manuscript_content")
                    .eq("id", selected_id).eq("project_id", project_id)
                    .eq("user_id", user_id).limit(1).execute()).data or []
            source_text = str(rows[0].get("manuscript_content") or "") if rows else ""
        elif selected_type == "project_session":
            rows = (supabase.table("writersblock_project_drafts")
                    .select("id, project_id, user_id, draft_type, draft_content")
                    .eq("id", selected_id).eq("project_id", project_id)
                    .eq("user_id", user_id).eq("draft_type", "project_session")
                    .limit(1).execute()).data or []
            try:
                snapshot = json.loads(rows[0].get("draft_content") or "{}") if rows else {}
            except (TypeError, ValueError):
                snapshot = {}
            source_text = get_best_saved_manuscript_source(snapshot) if isinstance(snapshot, dict) and snapshot else ""
            if not source_text and isinstance(snapshot, dict):
                source_text = str(snapshot.get("story_seed") or "")
        else:
            raise ValueError("Unrecognized saved version type; nothing was assigned.")
        if not rows:
            raise ValueError("This version does not belong to the open project. No series link was changed.")
        selected_info = {
            "series_source_type": selected_type,
            "series_source_id": selected_id,
            "series_source_words": count_words(source_text),
            "series_source_label": str(selected_version.get("label") or "")[:180],
        }

    same_series = (make_series_key(name) == str(prior.get("series_key") or ""))
    same_source = bool(selected_info) and all(
        str(prior.get(key) or "") == str(value or "")
        for key, value in selected_info.items()
        if key in ("series_source_type", "series_source_id")
    )
    if name and same_series and same_source:
        return False
    if not name and not old_name:
        return False
    old_data = {"series_name": name, "series_key": make_series_key(name) if name else "",
                "series_book_number": 0 if not name else len(ordered_series_members(name)) + 1,
                "series_continuity_mode": "Strict", "series_reference_ids": [],
                "series_canon_notes": str(prior.get("series_canon_notes") or ""),
                "project_title": str(projects[project_id].get("project_title") or "Untitled Project"),
                "series_membership_removed": not bool(name),
                "previous_series_name": old_name,
                "confirmed_manual_series_assignment": True,
                "saved_at": datetime.now(timezone.utc).isoformat()}
    old_data.update(selected_info)
    # A version change must not shuffle a project to a different book number.
    if same_series and old_name:
        old_data["series_book_number"] = int(prior.get("series_book_number") or 1)
    result = (supabase.table("writersblock_project_drafts")
              .insert({"project_id": project_id, "user_id": user_id,
                       "draft_type": "series_metadata", "draft_title": "Series Membership",
                       "draft_content": json.dumps(old_data), "version_number": 0})
              .execute())
    if not getattr(result, "data", None):
        raise RuntimeError("Series membership was not confirmed saved.")
    return True






def get_series_metadata_by_project():
    """Read-only membership index, including legacy project-session assignments.

    Some older projects recorded the series only in their project_session JSON,
    before a separate series_metadata record existed. We may use an explicit
    saved relationship as evidence, but NEVER infer membership from a title,
    story text, or a different project's saved settings.
    """
    # The newest explicit series_metadata row is authoritative, INCLUDING an
    # intentionally cleared relationship. Do not reconstruct a removed link
    # from older project_session snapshots.
    latest_rows = get_series_metadata_rows()
    inspected = {str(row["_project_id"]) for row in latest_rows if row.get("_project_id")}
    membership = {
        str(row["_project_id"]): row
        for row in latest_rows
        if row.get("_project_id")
        and not row.get("series_membership_removed")
        and str(row.get("series_name") or "").strip()
    }
    # Older projects sometimes have their explicit series link only in a
    # prior project session; later saves may omit the relationship. Search
    # newest-first until a confirmed link is found. A manually removed link
    # always wins because its series_metadata tombstone is in inspected.
    try:
        sessions = get_saved_project_sessions_for_dropdown()
    except Exception:
        sessions = []
    for row in sessions:
        project_id = str(row.get("project_id") or "").strip()
        if not project_id or project_id in inspected:
            continue
        try:
            snapshot = json.loads(row.get("draft_content") or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(snapshot, dict):
            continue
        name = str(snapshot.get("series_name") or "").strip()
        scope = str(snapshot.get("project_scope") or "").strip()
        if scope != "Book in a Series" or not name:
            continue
        inspected.add(project_id)
        try:
            number = int(snapshot.get("series_book_number") or 0)
        except (TypeError, ValueError):
            number = 0
        membership[project_id] = {
            "_project_id": project_id,
            "_source": "saved_project_session",
            "series_name": name,
            "series_key": make_series_key(name),
            "series_book_number": number,
            "series_canon_notes": str(snapshot.get("series_canon_notes") or ""),
            "project_title": str(snapshot.get("project_title") or ""),
        }
    # Series order is separate from saved-project chronology and revisions.
    # Existing metadata may hold duplicate/incorrect historical numbers; the
    # user-controlled series order is authoritative for the visible Book 1..N.
    project_rows = get_projects_for_import()
    creation_date = {str(row.get("id")): str(row.get("created_at") or "")
                     for row in project_rows if row.get("id")}
    by_series = {}
    for project_id, item in membership.items():
        by_series.setdefault(str(item.get("series_key") or ""), []).append(project_id)
    orders = get_series_order_overrides()
    for series_key, ids in by_series.items():
        chosen = [pid for pid in orders.get(series_key, []) if pid in ids]
        remaining = sorted((pid for pid in ids if pid not in chosen),
                           key=lambda pid: (creation_date.get(pid, ""), pid))
        # Original Oakhaven book order, as confirmed by the author. Only apply
        # as a display hint when NO explicit reordered list has been saved.
        # Match project IDs using unique titles; never infer or write membership.
        if not chosen and series_key == make_series_key("Oakhaven"):
            titles = {
                str(row.get("id")): str(row.get("project_title") or "").strip().casefold()
                for row in project_rows if row.get("id")
            }
            requested_titles = (
                "It's Not Safe", "Return To Sender", "The Dead Letters Covenant",
                "Chronos' Grasp", "Blood Of The Ancient",
            )
            for title in requested_titles:
                matches = [pid for pid in remaining if titles.get(pid) == title.casefold()]
                if len(matches) == 1:  # Multiple project IDs with one title are ambiguous.
                    chosen.append(matches[0])
            remaining = [pid for pid in remaining if pid not in chosen]
        for number, pid in enumerate(chosen + remaining, 1):
            membership[pid] = dict(membership[pid])
            membership[pid]["series_book_number"] = number
    return membership


def get_series_membership_slots(series_key, exclude_project_id=None):
    """One row per project ID; flag duplicate volume numbers, never guess."""
    slots = {}
    for project_id, metadata in get_series_metadata_by_project().items():
        if str(metadata.get("series_key") or "") != str(series_key or ""):
            continue
        if exclude_project_id and str(project_id) == str(exclude_project_id):
            continue
        try:
            number = int(metadata.get("series_book_number") or 0)
        except (ValueError, TypeError):
            continue
        if 1 <= number <= 100:
            slots.setdefault(number, []).append((str(project_id), metadata))
    return slots


def get_unambiguous_series_project_ids(series_key, before_number=None):
    """Only unique saved volume numbers may enter automatic continuity."""
    slots = get_series_membership_slots(series_key)
    return {
        project_id
        for number, entries in slots.items()
        if len(entries) == 1 and (before_number is None or number < before_number)
        for project_id, _metadata in entries
    }


def get_existing_series_names():
    names = {}
    for metadata in get_series_metadata_by_project().values():
        series_name = str(metadata.get("series_name") or "").strip()
        if series_name:
            names.setdefault(series_name.casefold(), series_name)
    return sorted(names.values(), key=str.lower)


def get_next_series_book_number(series_name, exclude_project_id=None):
    series_key = make_series_key(series_name)
    if not series_key:
        return 1

    book_numbers = []
    for metadata in get_series_metadata_by_project().values():
        if str(metadata.get("series_key") or "") != series_key:
            continue

        project_id = metadata.get("_project_id")
        if exclude_project_id and project_id == exclude_project_id:
            continue

        try:
            book_number = int(metadata.get("series_book_number") or 0)
        except Exception:
            book_number = 0

        if book_number > 0:
            book_numbers.append(book_number)

    return max(book_numbers, default=0) + 1


def get_inherited_series_canon_notes(series_key, current_book_number):
    inherited = []
    seen = set()
    for metadata in get_series_metadata_by_project().values():
        if str(metadata.get("series_key") or "") != str(series_key or ""):
            continue
        book_number = int(metadata.get("series_book_number") or 0)
        if book_number and book_number >= int(current_book_number or 1):
            continue
        notes = str(metadata.get("series_canon_notes") or "").strip()
        if notes and notes not in seen:
            inherited.append(notes)
            seen.add(notes)
    return "\n\n".join(inherited).strip()


def save_series_metadata_for_project(project_id=None):
    if st.session_state.get("project_scope") != "Book in a Series":
        return None

    series_name = str(st.session_state.get("series_name") or "").strip()
    if not series_name:
        return None

    project_id = project_id or get_active_project_id()
    user_id = get_current_user_id()
    if not project_id or not user_id:
        return None

    series_key = make_series_key(series_name)
    st.session_state.series_key = series_key
    metadata = {
        "series_key": series_key,
        "series_name": series_name,
        "series_book_number": int(st.session_state.get("series_book_number", 1) or 1),
        "series_continuity_mode": str(st.session_state.get("series_continuity_mode", "Strict")),
        "series_reference_ids": list(st.session_state.get("series_reference_ids", []) or []),
        "series_canon_notes": str(st.session_state.get("series_canon_notes", "") or "").strip(),
        "project_title": get_project_title_for_display(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    previous = get_series_metadata_by_project().get(str(project_id)) or {}
    if make_series_key(previous.get("series_name")) == series_key:
        for source_field in ("series_source_type", "series_source_id",
                             "series_source_words", "series_source_label"):
            if source_field in previous:
                metadata[source_field] = previous[source_field]

    return (
        supabase.table("writersblock_project_drafts")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "draft_title": f"{series_name} — Book {metadata['series_book_number']} Series Metadata",
            "draft_type": "series_metadata",
            "draft_content": json.dumps(metadata),
            "version_number": metadata["series_book_number"],
        })
        .execute()
    )


def assign_existing_project_to_series(project_id, series_name, book_number, project_title=""):
    """Explicit membership assignment. Never edit manuscript/version records."""
    user_id = get_current_user_id()
    clean_series_name = str(series_name or "").strip()
    if not user_id or not project_id or not clean_series_name:
        raise ValueError("A signed-in account, saved project, and series are required.")
    if str(project_id) == str(get_active_project_id() or ""):
        raise ValueError("Use the Project Relationship controls for the active project.")
    try:
        number = int(book_number)
    except (ValueError, TypeError):
        raise ValueError("Choose a valid series number.") from None
    if not 1 <= number <= 100:
        raise ValueError("Series number must be between 1 and 100.")

    # Verify ownership against the parent table before any write.
    project = next(
        (row for row in get_projects_for_import() if str(row.get("id")) == str(project_id)),
        None,
    )
    if not project:
        raise ValueError("The selected project does not belong to your account.")

    series_key = make_series_key(clean_series_name)
    for other_project_id, metadata in get_series_metadata_by_project().items():
        if (str(other_project_id) != str(project_id)
                and str(metadata.get("series_key") or "") == series_key
                and int(metadata.get("series_book_number") or 0) == number):
            raise ValueError(
                f"Series #{number} is already assigned. Correct the conflicting link first; "
                "no project was modified."
            )

    old = get_series_metadata_by_project().get(str(project_id)) or {}
    if str(old.get("series_key") or "") == series_key and int(old.get("series_book_number") or 0) == number:
        raise ValueError("That project is already assigned to this series and number.")

    metadata = {
        "series_key": series_key,
        "series_name": clean_series_name,
        "series_book_number": number,
        "series_continuity_mode": "Strict",
        "series_reference_ids": [],
        "series_canon_notes": str(old.get("series_canon_notes") or ""),
        "project_title": str(project.get("project_title") or project_title or "Untitled Project"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "assigned_from_existing_project": True,
        "confirmed_manual_series_assignment": True,
    }
    result = (
        supabase.table("writersblock_project_drafts")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "draft_title": f"{clean_series_name} — Series #{number} Membership",
            "draft_type": "series_metadata",
            "draft_content": json.dumps(metadata),
            "version_number": number,
        }).execute()
    )
    if not getattr(result, "data", None):
        raise RuntimeError("Series membership was not confirmed saved; no manuscript was changed.")
    return result


def remove_project_from_series(project_id, current_series_name):
    """Clear membership with a new metadata row; preserve all saved writing."""
    user_id = get_current_user_id()
    if not user_id or not project_id or str(project_id) == str(get_active_project_id() or ""):
        raise ValueError("Select a different saved project from your account.")
    owned = next((row for row in get_projects_for_import()
                  if str(row.get("id")) == str(project_id)), None)
    if not owned:
        raise ValueError("The selected project does not belong to your account.")
    old = get_series_metadata_by_project().get(str(project_id))
    if not old or str(old.get("series_key") or "") != make_series_key(current_series_name):
        raise ValueError("That project is not currently assigned to this series.")
    # Explicit tombstone beats old project sessions and retains an audit trail.
    metadata = {
        "series_name": "", "series_key": "", "series_book_number": 0,
        "series_membership_removed": True,
        "previous_series_name": str(old.get("series_name") or ""),
        "previous_series_book_number": int(old.get("series_book_number") or 0),
        "project_title": str(owned.get("project_title") or "Untitled Project"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    result = (supabase.table("writersblock_project_drafts")
              .insert({"project_id": project_id, "user_id": user_id,
                       "draft_title": "Series membership corrected (writing preserved)",
                       "draft_type": "series_metadata",
                       "draft_content": json.dumps(metadata), "version_number": 0})
              .execute())
    if not getattr(result, "data", None):
        raise RuntimeError("Series link correction was not confirmed saved.")
    return result


def get_series_reference_candidates():
    metadata_by_project = get_series_metadata_by_project()
    current_project_id = st.session_state.get("current_project_id")
    latest_manuscript_by_project = {}

    try:
        manuscript_versions = get_all_manuscript_versions_for_user()
    except Exception:
        manuscript_versions = []

    for version in manuscript_versions:
        project_id = version.get("project_id")
        if not project_id or project_id == current_project_id:
            continue

        manuscript_text = str(version.get("manuscript_content") or "").strip()
        if not manuscript_text:
            continue

        project_join = version.get("writersblock_projects") or {}
        joined_title = project_join.get("project_title") if isinstance(project_join, dict) else ""
        title = str(
            joined_title
            or version.get("project_title")
            or get_project_title_from_project_id(project_id)
            or "Untitled Project"
        ).strip()

        metadata = metadata_by_project.get(project_id, {})
        book_number = int(metadata.get("series_book_number") or 0)
        series_name = str(metadata.get("series_name") or "").strip()
        prefix = f"{series_name} — Book {book_number} — " if series_name and book_number else ""
        version_number = int(version.get("version_number") or 1)
        created_at = str(version.get("created_at") or "")

        candidate = {
            "id": f"manuscript:{version.get('id')}",
            "label": f"{prefix}{title} — Manuscript V{version_number} — {count_words(manuscript_text):,} words",
            "project_id": project_id,
            "title": title,
            "book_number": book_number,
            "series_name": series_name,
            "series_key": str(metadata.get("series_key") or ""),
            "text": manuscript_text,
            "created_at": created_at,
            "version_number": version_number,
        }

        existing = latest_manuscript_by_project.get(project_id)
        existing_key = (
            int(existing.get("version_number") or 0),
            str(existing.get("created_at") or ""),
        ) if existing else (-1, "")
        candidate_key = (version_number, created_at)
        if candidate_key >= existing_key:
            latest_manuscript_by_project[project_id] = candidate

    candidates = list(latest_manuscript_by_project.values())
    manuscript_project_ids = set(latest_manuscript_by_project.keys())

    try:
        saved_sessions = get_saved_project_sessions_for_dropdown()
    except Exception:
        saved_sessions = []

    seen_session_projects = set()
    for saved_row in saved_sessions:
        project_id = saved_row.get("project_id")
        if (
            not project_id
            or project_id == current_project_id
            or project_id in manuscript_project_ids
            or project_id in seen_session_projects
        ):
            continue

        try:
            snapshot = json.loads(saved_row.get("draft_content") or "{}")
        except Exception:
            snapshot = {}

        manuscript_text = str(
            snapshot.get("current_draft_output")
            or snapshot.get("rewritten_manuscript")
            or snapshot.get("final_output_text")
            or snapshot.get("manuscript_text")
            or ""
        ).strip()
        # Saved Concept/Plot Architecture projects may not yet have a draft.
        # Include their approved concept as a REFERENCE only; never present it
        # as a completed manuscript or change its saved content.
        reference_kind = "Saved Project"
        if not manuscript_text:
            manuscript_text = str(
                snapshot.get("story_seed")
                or snapshot.get("chosen_option_text")
                or snapshot.get("plot_outline")
                or ""
            ).strip()
            reference_kind = "Saved Concept"
        if not manuscript_text:
            continue

        title = str(
            snapshot.get("project_title")
            or get_project_title_from_project_id(project_id)
            or "Untitled Project"
        ).strip()
        metadata = metadata_by_project.get(project_id, {})
        # Use the authoritative index only. The project may have been removed
        # from its old series by an explicit metadata correction (tombstone).
        book_number = int(metadata.get("series_book_number") or 0)
        series_name = str(metadata.get("series_name") or "").strip()
        series_key = str(metadata.get("series_key") or "")
        prefix = f"{series_name} — Book {book_number} — " if series_name and book_number else ""

        candidates.append({
            "id": f"session:{saved_row.get('id')}",
            "label": f"{prefix}{title} — {reference_kind} — {count_words(manuscript_text):,} words",
            "project_id": project_id,
            "title": title,
            "book_number": book_number,
            "series_name": series_name,
            "series_key": series_key,
            "text": manuscript_text,
            "created_at": str(saved_row.get("created_at") or snapshot.get("saved_at") or ""),
            "version_number": int(saved_row.get("version_number") or snapshot.get("manuscript_version") or 1),
        })
        seen_session_projects.add(project_id)

    # The author's chosen saved version is the ONLY continuity source for a
    # pinned book; never silently substitute the most recent (possibly shorter)
    # revision. Older series members without a selection retain legacy behavior.
    for _p_id, _meta in metadata_by_project.items():
        _kind = str(_meta.get("series_source_type") or "")
        _v_id = str(_meta.get("series_source_id") or "")
        if not _kind or not _v_id or str(_p_id) == str(current_project_id or ""):
            continue
        _matched = None
        if _kind == "manuscript_version":
            _matched = next((r for r in manuscript_versions
                             if str(r.get("id") or "") == _v_id and str(r.get("project_id") or "") == str(_p_id)), None)
            _content = str((_matched or {}).get("manuscript_content") or "")
        elif _kind == "project_session":
            _matched = next((r for r in saved_sessions
                             if str(r.get("id") or "") == _v_id and str(r.get("project_id") or "") == str(_p_id)), None)
            try:
                _snapshot = json.loads((_matched or {}).get("draft_content") or "{}")
            except (ValueError, TypeError):
                _snapshot = {}
            _content = get_best_saved_manuscript_source(_snapshot) if isinstance(_snapshot, dict) and _snapshot else ""
            if not _content and isinstance(_snapshot, dict):
                _content = str(_snapshot.get("story_seed") or "")
        else:
            continue
        # If selected ID is missing, omit the reference instead of selecting
        # an unrelated version with a similar title.
        candidates = [c for c in candidates if str(c.get("project_id") or "") != str(_p_id)]
        if _matched and _content.strip():
            _title = str(get_project_title_from_project_id(_p_id) or _meta.get("project_title") or "Untitled Project")
            candidates.append({
                "id": f"{_kind}:{_v_id}", "project_id": _p_id,
                "label": f"{_meta.get('series_name') or ''} — {_title} — confirmed saved version — {count_words(_content):,} words",
                "title": _title, "book_number": int(_meta.get("series_book_number") or 0),
                "series_name": str(_meta.get("series_name") or ""),
                "series_key": str(_meta.get("series_key") or ""),
                "text": _content, "created_at": str(_matched.get("created_at") or ""),
                "version_number": int(_matched.get("version_number") or 1),
            })

    candidates.sort(
        key=lambda item: (
            str(item.get("series_name") or "").lower(),
            int(item.get("book_number") or 9999),
            str(item.get("created_at") or ""),
            str(item.get("title") or "").lower(),
        )
    )

    used_labels = {}
    for candidate in candidates:
        base_label = candidate["label"]
        used_labels[base_label] = used_labels.get(base_label, 0) + 1
        if used_labels[base_label] > 1:
            candidate["label"] = f"{base_label} ({used_labels[base_label]})"
    return candidates


def get_selected_series_reference_records():
    selected_ids = set(st.session_state.get("series_reference_ids", []) or [])
    return [
        candidate
        for candidate in get_series_reference_candidates()
        if candidate.get("id") in selected_ids
    ]


def get_series_continuity_instruction():
    mode = str(st.session_state.get("series_continuity_mode", "Strict"))
    if mode == "Flexible":
        return (
            "Preserve major identities, timeline anchors, and established endings. "
            "Minor descriptive details may evolve, but do not silently contradict earlier books."
        )
    if mode == "Balanced":
        return (
            "Preserve established characters, relationships, chronology, locations, important "
            "objects, mythology, and unresolved story threads. Flag deliberate canon changes."
        )
    return (
        "Treat all established facts in selected books and canon notes as locked series canon. "
        "Do not contradict character histories, chronology, relationships, locations, object "
        "rules, mythology, previous endings, or protected mysteries."
    )


def build_series_context_text(max_total_chars=60000, per_source_chars=25000):
    if st.session_state.get("project_scope") != "Book in a Series":
        return ""

    series_name = str(st.session_state.get("series_name") or "").strip()
    if not series_name:
        return ""

    book_number = int(st.session_state.get("series_book_number", 1) or 1)
    inherited_canon = get_inherited_series_canon_notes(
        st.session_state.get("series_key", ""),
        book_number,
    )
    current_canon = str(st.session_state.get("series_canon_notes", "") or "").strip()
    canon_notes = "\n\n".join(
        part for part in [inherited_canon, current_canon] if part
    ).strip()
    records = get_selected_series_reference_records()

    parts = [
        "SERIES CONTINUITY PACKAGE",
        f"Series Name: {series_name}",
        f"Current Book: {book_number}",
        f"Continuity Mode: {st.session_state.get('series_continuity_mode', 'Strict')}",
        f"Continuity Rule: {get_series_continuity_instruction()}",
    ]

    if canon_notes:
        parts.extend(["", "AUTHOR-LOCKED SERIES CANON NOTES:", canon_notes])
    if records:
        parts.extend(["", "SELECTED PREVIOUS BOOK REFERENCES:"])

    used_chars = sum(len(part) for part in parts)

    for record in records:
        remaining = max_total_chars - used_chars
        if remaining <= 500:
            parts.append("\n[Additional selected references omitted because the context limit was reached.]")
            break

        source_text = str(record.get("text") or "").strip()
        allowed = min(per_source_chars, remaining)

        if len(source_text) <= allowed:
            clipped = source_text
        else:
            head_chars = max(1, allowed // 2)
            tail_chars = max(1, allowed - head_chars)
            clipped = (
                source_text[:head_chars]
                + "\n\n[Middle of previous manuscript omitted for continuity compression.]\n\n"
                + source_text[-tail_chars:]
            )
            clipped += "\n[Reference shortened for this request. The full manuscript remains stored.]"

        block = (
            f"\n--- PREVIOUS BOOK: {record.get('title', 'Untitled')} ---\n"
            f"{clipped}\n"
            "--- END PREVIOUS BOOK REFERENCE ---"
        )
        parts.append(block)
        used_chars += len(block)

    if not records and not canon_notes:
        parts.extend(["", "No previous book manuscript or canon notes have been selected yet."])

    return "\n".join(parts).strip()


def get_series_aware_story_seed():
    plot_line = str(st.session_state.get("story_seed") or "").strip()

    source_mode = str(
        st.session_state.get("version_source_mode")
        or st.session_state.get("starting_source_mode")
        or ""
    )

    if source_mode == "Saved Manuscript":
        saved_source = str(st.session_state.get("saved_version_source_text") or "").strip()
        if saved_source:
            plot_line = f"""
CURRENT SAVED MANUSCRIPT / STORYLINE — TRANSFORM THIS SOURCE:
The writer selected the currently loaded saved manuscript as the authoritative story source.
Preserve its established characters, events, chronology, setting, relationships, and recognizable storyline
except where the writer's NEW Concept Development selections deliberately require changes. The new format,
development settings, tone, audience, dialogue approach, production influence, ending direction, and other
selected concept parameters are authoritative for this new named version. Revise the story as necessary so the
result genuinely reflects those changed inputs rather than merely relabeling the old manuscript.

--- BEGIN SAVED MANUSCRIPT SOURCE ---
{saved_source}
--- END SAVED MANUSCRIPT SOURCE ---
""".strip()

    elif source_mode in {"Replacement Draft / Manuscript", "Existing Draft / Manuscript"}:
        imported_source = str(st.session_state.get("imported_source_text") or "").strip()
        if imported_source:
            plot_line = f"""
UPLOADED REPLACEMENT DRAFT / MANUSCRIPT — USE AS THE PRIMARY WORKING SOURCE:
The writer supplied the complete draft below as the authoritative starting material for this version.
Preserve its established characters, events, chronology, setting, and core story except where the writer's
Concept Development selections deliberately require changes. Apply the selected project type, Dialogue Style,
tone, audience, author/production influence, and all other development choices to this source.

--- BEGIN UPLOADED REPLACEMENT SOURCE ---
{imported_source}
--- END UPLOADED REPLACEMENT SOURCE ---
""".strip()

    format_context = get_active_format_development_context()
    if format_context:
        plot_line = f"{plot_line}\n\n{format_context}".strip()

    series_context = build_series_context_text(
        max_total_chars=14000,
        per_source_chars=4500,
    )

    if not series_context:
        return plot_line

    return f"""
PRIMARY STORY COMMAND — FOLLOW THIS LITERALLY:
{plot_line}

NON-NEGOTIABLE PLOT PRIORITY RULES:
1. The author's new-book plot line controls the book's time period, setting, protagonists,
   central discovery, conflict, and story direction.
2. Previous books are continuity references only. They must never replace, redirect, modernize,
   or continue beyond the author's stated plot.
3. When the author specifies a historical year or era, every sandbox option must remain in that
   historical period unless the author explicitly requests a modern framing scene.
4. Do not make present-day characters the protagonists unless the new-book plot specifically
   names them as protagonists.
5. Every sandbox option must be a genuinely different path through the SAME stated story premise.

CONTINUITY REFERENCE PACKAGE:
{series_context}

FINAL DEVELOPMENT COMMAND:
Build all three sandbox paths directly from the PRIMARY STORY COMMAND. Preserve compatible series
canon, names, family relationships, objects, and chronology, but do not continue the previous
book's present-day plot unless the author explicitly asks for that continuation.
""".strip()

def access_allows(required_stage: str):
    """Licensed users and active trial users can move through the full writing workflow."""
    if st.session_state.get("licensed_mode"):
        return True

    if st.session_state.get("demo_mode"):
        ok, _ = is_demo_access_valid(st.session_state.get("demo_user_row") or {})
        return ok

    return False


def require_product_access(required_stage=None):
    if st.session_state.get("licensed_mode"):
        return True

    if st.session_state.get("demo_mode"):
        ok, msg = is_demo_access_valid(st.session_state.get("demo_user_row") or {})
        if ok:
            return True

        st.session_state.demo_mode = False
        st.error(msg or "Your 7-Day Limited Free Trial has expired.")
        st.stop()

    st.error(
        "Writer Edition is not activated. Open License / Trial in the sidebar to start "
        "a 7-Day Limited Free Trial or enter the email used for your one-time purchase."
    )
    st.stop()


def require_demo_action_available(action_name, scene_number=None):
    # The 7-Day Limited Free Trial can use the full writing workflow.
    # Restrictions are applied only to final print/download, Saved Projects, and Saved Versions.
    return True


def mark_demo_action_used(action_name):
    return


def full_version_only_notice(feature_name):
    message = (
        f"{feature_name} is available in the full Writer Edition and is not included in the "
        "7-Day Limited Free Trial. Purchase Writer Edition to unlock this feature."
    )
    st.warning(message)
    try:
        st.toast("Full Writer Edition feature", icon="🔒")
    except Exception:
        pass
    return message


def get_trial_days_remaining(user_row=None):
    user_row = user_row or st.session_state.get("demo_user_row") or {}
    expires_at = user_row.get("demo_expires_at")
    if not expires_at:
        return TRIAL_DAYS
    try:
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except Exception:
        return 0
    seconds = (expires_dt - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return 0
    return max(1, int((seconds + 86399) // 86400))


def get_trial_expiration_label(user_row=None):
    user_row = user_row or st.session_state.get("demo_user_row") or {}
    expires_at = user_row.get("demo_expires_at")
    if not expires_at:
        return ""
    try:
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        return expires_dt.strftime("%m/%d/%Y")
    except Exception:
        return ""


def ai_output_is_usable(output):
    if output is None:
        return False

    text_output = str(output).strip()
    if not text_output:
        return False

    blocked_phrases = [
        "fallback output",
        "backend error:",
        "backend issue:",
        "returned an empty response",
        "did not return usable text",
        "local fallback",
        "fallback beat",
        "permission_denied",
        "403 permission",
        "403",
        "project has been denied access",
        "api issue detected",
    ]

    lowered = text_output.lower()
    return not any(phrase in lowered for phrase in blocked_phrases)


# WBS_STAGE2_PREMISE_COMPLETE_REGEN_20261101
# Plot regeneration is preview-only until the author manually saves. This
# NEVER inserts a new version unless Save Version As is explicitly clicked.
def wbs_stage2_complete_plot_source_packet():
    """Pass the actual complete author text to the model, not cached plots."""
    original = str(st.session_state.get("story_seed") or "").strip()
    if not original:
        return ""
    fields = get_active_format_template_values()
    conflict = str(fields.get("central_conflict") or "").strip()
    subplot = str(fields.get("subplot_direction") or "").strip()
    return "\n\n".join((
        "THIS IS A REQUEST FOR THREE FULL PLOT PLANS, NOT THREE NEW STORIES.",
        "ORIGINAL AUTHOR'S STORY PREMISE — COMPLETE, BINDING:\n" + original,
        "AUTHOR'S CENTRAL CONFLICT — BINDING:\n" + (conflict or "Not separately supplied"),
        "AUTHOR'S SUBPLOT — BINDING:\n" + (subplot or "Not separately supplied"),
        "OTHER FORMAT-SPECIFIC DEVELOPMENT SETTINGS:\n" + get_active_format_development_context(),
        "AUTHOR'S FINAL SOURCE PASSAGE — DO NOT OMIT OR REPLACE ITS EVENTS:\n" + original[-2400:],
        "RULES FOR EACH OF OPTION A, OPTION B AND OPTION C: All author-specified "
        "events, character identities, causes, consequences, subplot, climax, "
        "intervention or rescue, aftermath, restoration, memory changes, and "
        "final outcome MUST be represented explicitly. The original ending "
        "is binding, not a suggested alternative. Beginning and ending must "
        "both survive. Vary ONLY pacing, emphasis, and order of revelation. "
        "Never replace the story with an inspired-by version. Expand each "
        "option into concrete Opening/Origin, Central Conflict, Subplot, "
        "Escalation and Twists, Climax, and Aftermath and Ending. "
        "Before delivering each option, compare it to every sentence of the "
        "author's premise, including its final passage. Restore any omitted "
        "events. Output only the three detailed writer-facing plots."
    ))


def wbs_stage2_regenerated_plots_usable(slates):
    """Fail closed on empty, trivial, or incomplete three-path responses."""
    if not isinstance(slates, dict) or not sandbox_output_is_usable(slates):
        return False
    if slates.get("is_fallback"):
        return False
    for option in ("Option A", "Option B", "Option C"):
        text = str(slates.get(option) or "").strip()
        if len(re.findall(r"\b\w+\b", text)) < 125:
            return False
        text_lower = text.lower()
        if not any(word in text_lower for word in ("ending", "aftermath", "resolution", "finally")):
            return False
    return True


def wbs_stage2_verify_regen_source():
    """Require the exact saved project/revision and unmodified Concept fields."""
    project_id = str(get_active_project_id() or "")
    row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "")
    user_id = str(get_current_user_id() or "")
    fmt = str(st.session_state.get("active_format_id") or "")
    if not (project_id and row_id and user_id and fmt == "novel_prose_novella"):
        raise ValueError("Load the exact saved Novel/Novella revision first.")
    current_unsaved = st.session_state.get("_wbs_stage2_regen_unsaved")
    source_identity = (project_id, row_id, fmt,
                       get_text_signature(wbs_stage2_complete_plot_source_packet()))
    has_staged_plots = current_unsaved == source_identity
    if wbs_work_has_changed() is not False and not has_staged_plots:
        raise ValueError("Save or reload Concept Development changes before regenerating plots.")
    rows = (supabase.table("writersblock_project_drafts")
            .select("id,project_id,user_id,draft_type,draft_content")
            .eq("id", row_id).eq("project_id", project_id)
            .eq("user_id", user_id).eq("draft_type", "project_session")
            .limit(1).execute()).data or []
    if len(rows) != 1:
        raise ValueError("The exact saved revision could not be verified; nothing was changed.")
    try:
        saved = json.loads(rows[0].get("draft_content") or "{}")
    except (TypeError, ValueError):
        raise ValueError("The saved revision is invalid; nothing was changed.")
    if (not isinstance(saved, dict)
            or str(saved.get("active_format_id") or "") != fmt
            or str(saved.get("current_project_id") or project_id) != project_id
            or str(saved.get("story_seed") or "").strip()
                != str(st.session_state.get("story_seed") or "").strip()):
        raise ValueError("Saved project, format, or story premise differs from the open revision.")
    if not str(saved.get("story_seed") or "").strip():
        raise ValueError("The saved revision has no Story Premise.")
    if saved.get("sandbox_slates") != st.session_state.get("sandbox_slates") and not has_staged_plots:
        raise ValueError("Plot paths no longer match the saved revision. Reload it first.")
    return source_identity


def wbs_stage2_render_regenerate_novel_plots():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage2_render_regenerate_novel_plots', globals())



def sandbox_output_is_usable(sandbox_output):
    return bool(
        sandbox_output
        and sandbox_output.get("Option A")
        and sandbox_output.get("Option B")
        and sandbox_output.get("Option C")
        and not sandbox_output.get("error_message")
    )



def wbs_can_generate_first_paths_for_saved_concept():
    """Allow a saved *concept-only* master to develop its first paths.

    Fail closed on ambiguous history. Never overwrite a saved session or change
    the owning project ID. An eligible project's first paths become a new
    immutable project-session version via the normal version-save routine.
    """
    project_id = str(get_active_project_id() or "")
    user_id = get_current_user_id()
    if not project_id or not user_id or st.session_state.get("project_stage") != "Intake":
        return False, "First-time path generation requires a saved Concept Development project."
    if wbs_has_saved_master() is not True:
        return False, "Cannot verify the saved master. Reload this project before continuing."
    if (str(st.session_state.get("_wbs_loaded_project_id") or "") != project_id
            or str(st.session_state.get("_wbs_loaded_project_title") or "").strip() != get_project_title()):
        return False, "Saved project identity is not confirmed. Reload the exact saved project."
    if get_project_title_from_project_id(project_id) != get_project_title():
        return False, "Database project title does not match the open project. Nothing was changed."
    format_id = str(st.session_state.get("active_format_id") or "")
    if (not format_id or format_id != str(st.session_state.get("wbs_locked_format_id") or "")
            or str(st.session_state.get("_wbs_locked_project_id") or "") != project_id):
        return False, "Saved writing format cannot be verified; reload the saved project."
    if not st.session_state.get("_wbs_active_saved_session_row_id"):
        return False, "The active saved version cannot be verified. Reload V-1 before continuing."
    # This route is for writer-entered or Quill concepts, not imported/saved
    # manuscripts. No working manuscript or downstream scene may be reset.
    if str(st.session_state.get("version_source_mode") or "") not in {"Custom Plot Line", "Quill Assisted"}:
        return False, "Only saved concept-only starting points can generate first paths this way."
    if (st.session_state.get("imported_source_text") or st.session_state.get("saved_version_source_text")):
        return False, "A saved or imported manuscript is attached. Its existing content was protected."
    downstream_fields = (
        "sandbox_slates", "chosen_option", "chosen_option_text", "plot_outline",
        "current_draft_output", "rewritten_manuscript", "manuscript_text",
        "scene_blocks", "completed_beats", "rolling_lore_book", "final_output_text",
        "final_output_saved_signature", "picture_book_layout_spreads",
    )
    def has_downstream_content(record):
        return any(bool(record.get(key)) for key in downstream_fields)
    if has_downstream_content(st.session_state):
        return False, "This project already contains downstream writing. No paths were regenerated."

    # Check ONLY the explicitly loaded immutable project-session revision.
    # Other revisions may contain paths, drafts or manuscripts; their existence
    # must never block development of this selected concept-only revision.
    row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "")
    try:
        result = (supabase.table("writersblock_project_drafts")
                  .select("id,project_id,user_id,draft_type,draft_content")
                  .eq("id", row_id).eq("project_id", project_id)
                  .eq("user_id", user_id).eq("draft_type", "project_session")
                  .limit(1).execute())
        rows = getattr(result, "data", None) or []
        if len(rows) != 1:
            return False, "The exact selected saved revision could not be verified."
        snap = json.loads(rows[0].get("draft_content") or "{}")
        if not isinstance(snap, dict):
            return False, "The selected revision contains invalid saved data."
        if (str(snap.get("current_project_id") or project_id) != project_id
                or str(snap.get("active_format_id") or "") != format_id):
            return False, "The selected revision's project or format does not match."
        if str(snap.get("project_stage") or "Intake") != "Intake":
            return False, "The selected revision is not a Concept Development checkpoint."
        if has_downstream_content(snap):
            return False, "This selected revision already contains downstream writing; it was preserved."
        # Never generate against unsaved changes or a different revision.
        if wbs_work_has_changed() is not False:
            return False, "The selected concept has unsaved changes. Save them first."
    except (ValueError, TypeError, AttributeError, KeyError):
        return False, "The selected revision could not be checked safely."
    except Exception:
        return False, "The database could not verify the selected revision."
    return True, ""


def get_user_by_email(email: str):
    row = _wbs_auth.refresh_account()
    if str(email or "").strip().lower() != _wbs_auth.email:
        return None
    return row


def start_or_resume_trial(email: str):
    try:
        return _wbs_auth.start_trial(email), ""
    except AuthenticationError as error:
        return None, str(error)


def get_licensed_user_by_email(email: str):
    return get_user_by_email(email)


# Private evaluation: uses the existing licensed-email screen and Supabase user record.
# No separate login screen, payment, or ordinary free-trial activation.
EVALUATION_EMAIL = "michael@michaelbecker.org"


def is_evaluation_account(user_row):
    return bool(
        isinstance(user_row, dict)
        and str(user_row.get("email") or "").strip().lower() == EVALUATION_EMAIL
        and str(user_row.get("company") or "").strip().lower() == "evaluation"
    )


def is_evaluation_access_valid(user_row):
    if not is_evaluation_account(user_row):
        return False, "Evaluation account not found."
    if str(user_row.get("access_status") or "").strip().lower() != "active":
        return False, "Evaluation access has not been activated."
    if not user_row.get("is_active", False):
        return False, "Evaluation access is inactive."
    if not user_row.get("email_verified", False):
        return False, "Evaluation access is not authorized."
    expires_at = user_row.get("demo_expires_at")
    if not expires_at:
        return False, "Evaluation expiration has not been set."
    try:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            return False, "Evaluation expiration must include a timezone."
    except (TypeError, ValueError):
        return False, "Evaluation expiration is invalid."
    if datetime.now(timezone.utc) >= expiry:
        return False, "Evaluation access has expired."
    return True, ""


def enforce_evaluation_session():
    """Check Supabase each rerun so expiry/revocation also closes an open session."""
    row = st.session_state.get("licensed_user_row") or {}
    if not is_evaluation_account(row):
        return
    try:
        fresh = get_user_by_email(EVALUATION_EMAIL)
        ok, reason = is_evaluation_access_valid(fresh)
    except Exception:
        ok, reason, fresh = False, "Evaluation access could not be verified.", None
    if not ok:
        st.session_state.licensed_mode = False
        st.session_state.licensed_user_row = None
        st.session_state.licensed_email = ""
        st.session_state.access_success_message = ""
        st.error(reason)
        st.stop()
    st.session_state.licensed_user_row = fresh


def is_license_access_valid(user_row: dict):
    """Validate a one-time Writer Edition license without subscription or plan-tier fields."""
    if not user_row:
        return False, "Licensed email not found."
    if is_evaluation_account(user_row):
        return is_evaluation_access_valid(user_row)

    if "email_verified" in user_row and not user_row.get("email_verified", False):
        return False, "Licensed email is not verified."

    # Preferred commercial fields when they are added to Supabase.
    if "license_active" in user_row and not bool(user_row.get("license_active")):
        return False, "Writer Edition license is not active."

    if user_row.get("license_status") is not None:
        license_status = str(user_row.get("license_status") or "").strip().lower()
        if license_status not in {"active", "licensed", "paid", "permanent", "lifetime"}:
            return False, "Writer Edition license is not active."

    if user_row.get("purchase_status") is not None:
        purchase_status = str(user_row.get("purchase_status") or "").strip().lower()
        if purchase_status not in {"paid", "complete", "completed", "active"}:
            return False, "One-time purchase has not been confirmed."

    # Compatibility with the current users table until dedicated license fields are added.
    if "license_active" not in user_row and user_row.get("license_status") is None and user_row.get("purchase_status") is None:
        if not user_row.get("is_active", False):
            return False, "Writer Edition license is not active."

    return True, ""


def is_demo_access_valid(user_row: dict):
    if not user_row:
        return False, "Trial account not found."

    if not user_row.get("demo_active", True):
        return False, "The 7-Day Limited Free Trial is inactive."

    expires_at = user_row.get("demo_expires_at")
    if not expires_at:
        return False, "Start the 7-Day Limited Free Trial with your email address."

    try:
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except Exception:
        return False, "The trial expiration date is invalid. Start the trial again."

    if datetime.now(timezone.utc) > expires_dt:
        return False, "Your 7-Day Limited Free Trial has expired."

    return True, ""

# Revalidate evaluation access before the rest of the app processes this rerun.
sync_access_state(st.session_state, _wbs_auth, is_license_access_valid, is_demo_access_valid)
enforce_evaluation_session()

# ==========================================
# WBS PROGRAM / ADD-ON STATE
# ==========================================
if "wbs_active_program" not in st.session_state:
    st.session_state.wbs_active_program = "writer_studios"

# ==========================================
# WBS PROGRAM NAVIGATION — writing-only deployment
st.session_state.wbs_active_program = "writer_studios"

# ==========================================
# WRITER FORMAT TEMPLATE STATE
# ==========================================
# Keep the active template and Quill rules available to the whole application.
# The visible Writing Format selector is rendered inside the Step 1 middle panel.
current_format_id = str(
    st.session_state.get("active_format_id") or "novel_prose_novella"
)
if current_format_id not in WBS_FORMAT_IDS:
    current_format_id = "novel_prose_novella"

st.session_state.active_format_id = current_format_id
st.session_state.active_format_template = get_wbs_format_template(current_format_id)
st.session_state.quill_format_instructions = get_wbs_quill_instructions(current_format_id)
st.session_state.quill_format_name = get_wbs_format_display_name(current_format_id)
st.session_state.format_type = WBS_LEGACY_FORMAT_BY_TEMPLATE_ID.get(
    current_format_id,
    "Novel / Prose",
)
refresh_quill_template_context()

# WBS_STARTUP_SEQUENCE_NOTICE_20261020
_startup_access_active = bool(
    st.session_state.get("licensed_mode")
    or st.session_state.get("demo_mode")
)

if not _startup_access_active:
    st.markdown(
        """
        <div style="
            color:#ff4b4b;
            font-size:1.02rem;
            font-weight:700;
            line-height:1.45;
            margin:0.15rem 0 0.9rem 0;
        ">
        START HERE: Open <strong>License / Trial</strong> in the left sidebar and activate your account.
        Once login is complete, introduce yourself to your writing assistant, <strong>Quill</strong>,
        in the right-hand panel.
        </div>
        """,
        unsafe_allow_html=True,
    )


# WBS_API_REQUIREMENT_NOTICE_20261021
if not _startup_access_active:
    st.markdown(
        """
        <div style="
            margin-top:-8px;
            margin-bottom:12px;
            font-size:0.80rem;
            font-weight:600;
            color:#ff5a5a;
        ">
            GOOGLE GEMINI API KEY REQUIRED.
            <span style="color:#f2f2f2;font-weight:500;">
                Google Free tier may be suitable for light/small projects.
            </span>
            <a href="https://writersblockstudios.com/google-api-usage.html"
               target="_blank"
               style="color:#ff7777;font-weight:700;text-decoration:underline;">
               How Google API Usage Works
            </a>
            &nbsp;|&nbsp;
            <a href="https://writersblockstudios.com/google-api-key-setup.html"
               target="_blank"
               style="color:#ff7777;font-weight:700;text-decoration:underline;">
               API Key Setup
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =====================================
# SIDEBAR STATUS / NAVIGATION / ACCESS
# =====================================

with st.sidebar.expander(
    "License / Trial",
    expanded=not bool(
        st.session_state.get("licensed_mode")
        or st.session_state.get("demo_mode")
    ),
):
    active_access = st.session_state.get("licensed_mode") or st.session_state.get("demo_mode")

    if not st.session_state.get("licensed_mode"):
        if PURCHASE_URL and (
            PURCHASE_URL.startswith("https://buy.stripe.com/")
            or PURCHASE_URL.startswith("https://checkout.stripe.com/")
        ):
            purchase_url = build_affitor_purchase_url(PURCHASE_URL)
            st.markdown(
                f"""
                <a href="{purchase_url}" target="_blank" style="text-decoration:none;">
                    <div style="
                        border:1px solid rgba(255,255,255,0.28);
                        border-radius:9px;
                        padding:0.85rem 0.55rem 0.72rem 0.55rem;
                        margin:0.15rem 0 0.7rem 0;
                        text-align:center;
                        background:rgba(255,255,255,0.055);
                        cursor:pointer;
                    ">
                        <div style="font-size:1.05rem; font-weight:800; line-height:1.25;">
                            🔥 UPGRADE TO FULL VERSION
                        </div>
                        <div style="font-size:0.76rem; margin-top:0.35rem; opacity:0.82;">
                            One time purchase - No subscriptions
                        </div>
                    </div>
                </a>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="
                    border:1px solid rgba(255,255,255,0.22);
                    border-radius:9px;
                    padding:0.85rem 0.55rem 0.72rem 0.55rem;
                    margin:0.15rem 0 0.7rem 0;
                    text-align:center;
                    background:rgba(255,255,255,0.04);
                    opacity:0.72;
                ">
                    <div style="font-size:1.05rem; font-weight:800; line-height:1.25;">
                        🔥 UPGRADE TO FULL VERSION
                    </div>
                    <div style="font-size:0.76rem; margin-top:0.35rem; opacity:0.82;">
                        One time purchase - No subscriptions
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.session_state.get("access_success_message"):
        st.success(st.session_state.access_success_message)

    if active_access:
        if st.session_state.get("licensed_mode"):
            st.markdown("**Writer Edition License:** Active")
            if st.session_state.get("licensed_email"):
                st.markdown(f"**Licensed Email:** {st.session_state.licensed_email}")
        elif st.session_state.get("demo_mode"):
            ok, trial_msg = is_demo_access_valid(st.session_state.get("demo_user_row") or {})
            if ok:
                days_remaining = get_trial_days_remaining()
                st.markdown("**7-Day Limited Free Trial:** Active")
                st.markdown(f"**{days_remaining} day{'s' if days_remaining != 1 else ''} remaining**")
                expiry_label = get_trial_expiration_label()
                if expiry_label:
                    st.caption(f"Trial ends: {expiry_label}")
                if st.session_state.get("demo_email"):
                    st.markdown(
                        f"Trial Email: `{st.session_state.demo_email}`"
                    )
                st.caption(
                    "Concept → Scripting → Plot Architecture → Creative Draft → Script Lock → "
                    "Script Polish → Script Rewrite → Manuscript Review"
                )
                st.caption("Not included: Manuscript Printout • Saved Projects • Saved Versions")
            else:
                st.error(trial_msg)

        if st.button("Switch User / Logout", key="switch_user_logout", use_container_width=True):
            _wbs_auth.sign_out()
            st.session_state.clear()
            st.session_state.demo_mode = False
            st.session_state.licensed_mode = False
            st.session_state.demo_access_code = ""
            st.session_state.demo_email = ""
            st.session_state.demo_user_row = None
            st.session_state.licensed_user_row = None
            st.session_state.licensed_email = ""
            st.session_state.access_success_message = ""
            st.rerun()

    else:
        render_auth_access(st, _wbs_auth, globals())

st.sidebar.markdown("---")

# WBS 2026-10-24: Quill and new-story state must not leak into another project.
def wbs_clear_new_project_ui_state():
    """Clear old Quill dialogue and cached concept widgets; keep the login intact."""
    reset_prefixes = (
        "wbs_quill_", "quill_", "_wbs_quill_", "format_field_",
        "starting_source_", "wbs_quill_starting_", "save_as_version_name_",
    )
    reset_exact = {
        "quill_chat_history", "quill_last_response", "quill_conversation",
        "quill_last_spoken", "quill_message_input", "project_version_name",
    }
    for state_key in list(st.session_state.keys()):
        key_text = str(state_key).lower()
        if key_text in reset_exact or key_text.startswith(reset_prefixes):
            st.session_state.pop(state_key, None)
    st.session_state.format_template_values = {}
    st.session_state.quill_starting_direction = ""
    st.session_state.pop("wbs_pending_stage_change", None)
    st.session_state.pop("_wbs_last_saved_work_signature", None)
    st.session_state.pop("_wbs_last_saved_project_id", None)
    st.session_state.pop("_wbs_active_saved_session_row_id", None)
    st.session_state.pop("_wbs_loaded_saved_session_id", None)
    st.session_state.pop("_wbs_loaded_quill_concept", None)

if st.sidebar.button("⚠️ Start New Project", key="global_reset", use_container_width=True, type="secondary"):
    wbs_clear_new_project_ui_state()
    st.session_state.pop("_wbs_unlocked_saved_stage", None)
    st.session_state.project_stage = "Intake"
    st.session_state.project_title = ""
    st.session_state.project_version_name = "Original"
    st.session_state.concept_change_areas = []
    st.session_state.pop("_wbs_loaded_concept_version_baseline", None)
    st.session_state.project_scope = "Standalone Book"
    st.session_state.series_key = ""
    st.session_state.series_name = ""
    st.session_state.series_book_number = 1
    st.session_state.series_continuity_mode = "Strict"
    st.session_state.series_reference_ids = []
    st.session_state.series_canon_notes = ""
    st.session_state.series_selection_signature = ""
    st.session_state.pop("series_reference_selector", None)
    st.session_state.pop("series_choice_selector", None)
    st.session_state.pop("series_name_input", None)
    st.session_state.pop("_wbs_simple_series_context", None)
    st.session_state.pop("wbs_simple_series_choice", None)
    st.session_state.pop("wbs_simple_series_new_name", None)
    st.session_state.pop("wbs_confirm_series_link", None)
    st.session_state.pop("wbs_confirm_series_removal", None)
    st.session_state.pop("series_book_number_input", None)
    st.session_state.pop("series_book_number_auto_signature", None)
    st.session_state.pop("custom_plot_line_input", None)
    st.session_state.story_seed = (
        "An antique shop owner buys a heavy iron safe that cannot be opened, "
        "only to realize that every night, the ticking sounds coming from inside it get faster."
    )
    st.session_state.starting_source_mode = "Story Idea"
    st.session_state.version_source_mode = "Custom Plot Line"
    st.session_state.saved_version_source_text = ""
    st.session_state.saved_version_source_name = ""
    st.session_state.saved_version_source_word_count = 0
    st.session_state.imported_source_text = ""
    st.session_state.imported_source_name = ""
    st.session_state.imported_source_word_count = 0
    st.session_state.pop("concept_existing_draft_upload", None)
    st.session_state.pop("wbs_locked_format_id", None)
    st.session_state.pop("_wbs_locked_project_id", None)
    st.session_state.pop("_wbs_loaded_project_id", None)
    st.session_state.pop("_wbs_loaded_project_title", None)
    st.session_state.pop("_wbs_loaded_saved_session_id", None)
    st.session_state.pop("_wbs_loaded_manuscript_version_id", None)
    st.session_state.pop("_wbs_draft_scope_id", None)
    st.session_state.active_format_id = "novel_prose_novella"
    st.session_state.format_type = "Novel / Prose"
    st.session_state.active_format_template = get_wbs_format_template("novel_prose_novella")
    st.session_state.quill_format_instructions = get_wbs_quill_instructions("novel_prose_novella")
    st.session_state.quill_format_name = get_wbs_format_display_name("novel_prose_novella")
    st.session_state.pop("wbs_format_template_selector", None)
    st.session_state.dialogue_style = "Story-Driven / Automatic"
    st.session_state.audiobook_length = "30 Minutes"
    st.session_state.audiobook_target_word_count = 4000
    st.session_state.audiobook_production_script = ""
    st.session_state.audiobook_production_source_signature = ""
    st.session_state.audiobook_production_cue_level = "Voices + Minimal SFX"
    st.session_state.audiobook_production_preview_id = 0
    st.session_state.tone_style = "Gritty Noir Mystery"
    st.session_state.author_style = ""
    st.session_state.sandbox_slates = None
    st.session_state.chosen_option = None
    st.session_state.chosen_option_text = None
    st.session_state.plot_outline = None
    st.session_state.current_draft_output = ""
    st.session_state.rolling_lore_book = ""
    st.session_state.completed_beats = []
    st.session_state.scene_blocks = {}
    st.session_state.current_processing_beat = 1
    st.session_state.revision_report = ""
    st.session_state.rewritten_manuscript = ""
    st.session_state.manuscript_version = 0
    st.session_state.current_manuscript_save_status = ""
    st.session_state.current_manuscript_save_stage = ""
    st.session_state.current_manuscript_save_version = 0
    st.session_state.rewrite_applied_message = ""
    st.session_state.current_project_id = None
    st.session_state.revision_report = ""
    st.session_state.export_view = False
    st.session_state.final_output_format = ""
    st.session_state.final_output_text = ""
    st.session_state.final_output_source_signature = ""
    st.session_state.final_output_preview_id = 0
    st.session_state.final_output_saved_signature = ""
    st.session_state.project_integrity_report = ""
    st.session_state.project_integrity_source_signature = ""
    st.session_state.project_integrity_status = ""
    st.session_state.show_saved_version_manager = False
    st.session_state.project_saved_notice = False
    st.session_state.picture_book_layout_spreads = []
    st.session_state.picture_book_layout_source_signature = ""
    st.session_state.picture_book_layout_preview_id = 0
    st.session_state.picture_book_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
    st.session_state.pop('children_publication_layout',None)
    st.session_state.pop('publication_layout',None)
    st.session_state.rewrite_preview_id = 0
    st.session_state.rewrite_target_length = "Keep Current Length"
    st.rerun()

st.sidebar.markdown("---")

# Video Director is intentionally excluded from the public writing edition.
with st.sidebar.container(border=True):
    st.markdown("**📊 Project Status**")

    if st.session_state.get("licensed_mode"):
        st.write("License: Writer Edition — Active")
    elif st.session_state.get("demo_mode"):
        st.write("Access: 7-Day Limited Free Trial")
        st.write(f"Trial Remaining: {get_trial_days_remaining()} day(s)")
    else:
        st.write("License: Not Activated")

    # On an unsaved Concept project, the title widget may update after the sidebar
    # renders. Display its live value without changing the saved master title.
    _status_project_title = get_project_title_for_display()
    if not get_active_project_id() and st.session_state.get("project_stage") == "Intake":
        _pending_title = str(st.session_state.get("project_title_input") or "").strip()
        if _pending_title:
            _status_project_title = _pending_title
    st.write(f"Current Project: {_status_project_title}")

    if st.session_state.get("project_scope") == "Book in a Series":
        st.write(
            f"Series: {st.session_state.get('series_name') or 'Unnamed Series'} "
            f"— {get_series_item_display()}"
        )

    # Status follows the working story through all writing formats and stages.
    # This is separate from the Children's Picture Book manuscript budget.
    _active_title = get_project_title_for_display().strip().casefold()
    _saved_status_items = (get_saved_projects_versions_dropdown_items()
                           if st.session_state.get("licensed_mode") else [])
    _matching_saved_items = [item for item in _saved_status_items
                             if str(item.get("label") or "").split(" — V-", 1)[0].strip().casefold() == _active_title]
    _active_saved_id = str(st.session_state.get("_wbs_loaded_saved_session_id") or "")
    _active_version_number = 0
    if _active_saved_id:
        for _saved_item in _matching_saved_items:
            if str((_saved_item.get("row") or {}).get("id") or "") == _active_saved_id:
                _v_match = re.search(r" — V-(\d+) — ", _saved_item.get("label") or "")
                if _v_match:
                    _active_version_number = int(_v_match.group(1))
                break
    if not _active_version_number and _matching_saved_items:
        _v_match = re.search(r" — V-(\d+) — ", _matching_saved_items[0].get("label") or "")
        if _v_match:
            _active_version_number = int(_v_match.group(1))
    st.write(f"Current Version: V-{_active_version_number}" if _active_version_number else "Current Version: Unsaved")
    from sidebar.summary import render_saved_scene_total
    render_saved_scene_total(st, globals())


st.sidebar.markdown("---")

with st.sidebar.expander("Saved Projects / Versions", expanded=False):
    if st.session_state.get("demo_mode"):
        st.caption("These features remain visible during the 7-Day Limited Free Trial but unlock with the full Writer Edition.")

        if st.button("💾 Saved Projects 🔒", key="trial_saved_projects_notice", use_container_width=True):
            full_version_only_notice("Saved Projects")

        if st.button("🗂️ Saved Versions 🔒", key="trial_saved_versions_notice", use_container_width=True):
            full_version_only_notice("Saved Versions")
    else:
        saved_items = _saved_status_items

        if not saved_items:
            st.caption("No saved projects or versions found.")
        else:
            saved_lookup = {}
            saved_labels = []
            for item in saved_items:
                label = item["label"]
                unique_label = label
                suffix = 2
                while unique_label in saved_lookup:
                    unique_label = f"{label} ({suffix})"
                    suffix += 1
                saved_labels.append(unique_label)
                saved_lookup[unique_label] = item
            # Update widget selection only BEFORE the selectbox is constructed.
            recent_id = st.session_state.pop("_wbs_saved_session_to_select", "")
            if recent_id:
                for item in saved_items:
                    if (item.get("type") == "project_session"
                            and str(item.get("row", {}).get("id") or "") == recent_id):
                        st.session_state["sidebar_saved_projects_versions_selector"] = next(
                            label for label, mapped in saved_lookup.items() if mapped is item
                        )
                        break
            selected_key = "sidebar_saved_projects_versions_selector"
            if st.session_state.get(selected_key) not in saved_labels:
                st.session_state[selected_key] = saved_labels[0]

            selected_saved_label = st.selectbox(
                "Saved Projects / Versions:",
                saved_labels,
                key="sidebar_saved_projects_versions_selector",
            )

            selected_saved_item = saved_lookup.get(selected_saved_label)
            if selected_saved_item:
                chosen_project_id = str((selected_saved_item.get("row") or {}).get("project_id") or "")
                selected_title = str(selected_saved_label).split(" — V-", 1)[0].strip()
                live_project_id = str(get_active_project_id() or "")
                live_title = get_project_title()
                if (chosen_project_id != live_project_id or (selected_title and selected_title != live_title)):
                    st.caption("Selected saved item is not the active story. Click **Load Selected Saved Item** to open it.")

            # Detect a legacy cross-linked project BEFORE the writer tries to
            # load it. This check is read-only and never changes series,
            # manuscript, title, or version records.
            if selected_saved_item and selected_saved_item.get("type") == "project_session":
                _row = selected_saved_item.get("row") or {}
                try:
                    _snapshot = json.loads(_row.get("draft_content") or "{}")
                except (ValueError, TypeError):
                    _snapshot = {}
                _entry_title = str((_snapshot if isinstance(_snapshot, dict) else {}).get("project_title") or "").strip()
                _parent_title = get_project_title_from_project_id(_row.get("project_id"))
                if _entry_title and _parent_title and _entry_title.casefold() != _parent_title.casefold():
                    st.error(
                        f'Saved entry "{_entry_title}" is linked to database project '
                        f'"{_parent_title}". Loading has been blocked to prevent '
                        'mixing projects. No data was saved or changed.'
                    )

            if st.button("Load Selected Saved Item", key="sidebar_load_saved_item", use_container_width=True):
                if selected_saved_item and selected_saved_item["type"] == "project_session":
                    _identity_ok, _identity_message = wbs_saved_project_identity_preflight(
                        selected_saved_item["row"]
                    )
                    if not _identity_ok:
                        st.error(_identity_message)
                        st.stop()
                    if load_saved_project_session_to_state(selected_saved_item["row"]):
                        st.session_state.pop("_wbs_loaded_manuscript_version_id", None)
                        st.session_state["_wbs_loaded_saved_session_id"] = str(selected_saved_item["row"].get("id") or "")
                        st.session_state["_wbs_loaded_project_id"] = str(selected_saved_item["row"].get("project_id") or "")
                        st.session_state["_wbs_loaded_project_title"] = get_project_title()
                        st.session_state.pop("_wbs_stage3_clean_editor", None)
                        st.session_state.pop("_wbs_stage3_clean_source", None)
                        st.success("Saved project loaded.")
                        st.rerun()

                elif selected_saved_item and selected_saved_item["type"] == "manuscript_version":
                    selected_version = selected_saved_item["row"]
                    selected_project_id = selected_version.get("project_id")

                    # A manuscript checkpoint stores manuscript text, while the
                    # project-session snapshot stores Concept Development settings.
                    # Restore both so Step 1 always reflects the saved project.
                    branch_name = get_manuscript_branch_name(selected_version)
                    saved_project_state = get_latest_saved_project_session_for_project(
                        selected_project_id,
                        version_name=branch_name,
                        checkpoint_created_at=selected_version.get("created_at"),
                    )
                    if not saved_project_state:
                        st.error(
                            "Cannot safely load this manuscript version: its matching "
                            "saved project session was not found. The current project "
                            "has NOT been replaced or mixed with another story."
                        )
                        st.stop()
                    # Validate the selected record and title BEFORE applying any
                    # saved state. A previous project must survive a failed load.
                    loaded_project_title = str(
                        get_project_title_from_project_id(selected_project_id)
                        or selected_version.get("project_title")
                        or ""
                    ).strip()
                    if not selected_project_id or not loaded_project_title:
                        st.error("The selected manuscript has no valid project identity. Load cancelled.")
                        st.stop()
                    if str(saved_project_state.get("project_id") or "") != str(selected_project_id):
                        st.error("The saved session belongs to a different project. Load cancelled.")
                        st.stop()
                    _identity_ok, _identity_message = wbs_saved_project_identity_preflight(
                        saved_project_state
                    )
                    if not _identity_ok:
                        st.error(_identity_message)
                        st.stop()
                    if not load_saved_project_session_to_state(saved_project_state):
                        st.error("The manuscript was not loaded because its project session failed validation.")
                        st.stop()
                    if str(st.session_state.get("current_project_id") or "") != str(selected_project_id):
                        st.error("Project ID mismatch. The manuscript was not applied.")
                        st.stop()

                    # A checkpoint title is bound to its parent project, never to
                    # the previously open project or a stale input widget.
                    st.session_state.current_project_id = selected_project_id
                    st.session_state.project_version_name = branch_name
                    st.session_state.project_title = loaded_project_title
                    st.session_state["_wbs_loaded_project_id"] = str(selected_project_id)
                    st.session_state["_wbs_loaded_project_title"] = loaded_project_title
                    st.session_state["_wbs_loaded_saved_session_id"] = str(saved_project_state.get("id") or "")
                    # This checkpoint ID gives stage navigation a read-only,
                    # user-scoped way to verify project provenance after a rerun.
                    st.session_state["_wbs_loaded_manuscript_version_id"] = str(selected_version.get("id") or "")
                    st.session_state.current_draft_output = str(selected_version.get("manuscript_content") or "")
                    st.session_state.manuscript_version = int(selected_version.get("version_number") or 0)

                    # The exact checkpoint selected by the writer becomes the
                    # protected source available in Step 1 for transformation.
                    st.session_state.saved_version_source_text = str(
                        selected_version.get("manuscript_content") or ""
                    ).strip()
                    st.session_state.saved_version_source_name = branch_name
                    st.session_state.saved_version_source_word_count = count_words(
                        st.session_state.saved_version_source_text
                    )
                    st.session_state.version_source_mode = "Saved Manuscript"
                    clear_concept_widget_state_for_loaded_project()
                    loaded_status, loaded_stage = get_manuscript_version_status_stage(selected_version)
                    st.session_state.current_manuscript_save_status = loaded_status
                    st.session_state.current_manuscript_save_stage = loaded_stage
                    st.session_state.current_manuscript_save_version = int(selected_version.get("version_number") or 0)
                    st.session_state.rewritten_manuscript = ""
                    st.session_state.rewrite_applied_message = ""
                    # Exact writer-selected checkpoint, no phantom version on reload.
                    st.session_state["_wbs_last_saved_work_signature"] = wbs_save_state_signature()
                    st.session_state["_wbs_last_saved_project_id"] = str(selected_project_id)
                    st.session_state.show_saved_version_manager = False

                    # Open at Concept but unlock review of all reached stages.
                    # This applies even when the earlier session is unavailable.
                    st.session_state["_wbs_unlocked_saved_stage"] = max(
                        int(st.session_state.get("_wbs_unlocked_saved_stage") or 1),
                        5 if loaded_status == "FINAL" else 4,
                    )
                    st.session_state.project_stage = "Intake"
                    st.session_state.export_view = False

                    st.success(f"Saved {loaded_status.lower()} loaded. Review Concept Development.")
                    st.rerun()

            if selected_saved_item and selected_saved_item["type"] == "manuscript_version":
                try:
                    selected_version = selected_saved_item["row"]
                    selected_saved_text = str(selected_version.get("manuscript_content") or "")

                    saved_doc = Document()
                    saved_doc.add_heading(f"WritersBlock Studios Saved Manuscript - {selected_saved_label}", level=1)

                    for paragraph in selected_saved_text.split("\n\n"):
                        clean_paragraph = paragraph.strip()
                        if clean_paragraph:
                            p = saved_doc.add_paragraph(clean_paragraph)
                            p.paragraph_format.space_after = Pt(8)
                            p.paragraph_format.line_spacing = 1.15

                    saved_docx_buffer = BytesIO()
                    saved_doc.save(saved_docx_buffer)

                    st.download_button(
                        label="Download Selected Version (.docx)",
                        data=saved_docx_buffer.getvalue(),
                        file_name="saved_manuscript_version.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.caption(f"Download unavailable: {e}")


st.sidebar.markdown(
    """
    <div style="
        border:1px solid rgba(255,255,255,0.18);
        border-radius:10px;
        padding:0.55rem 0.55rem 0.48rem 0.55rem;
        margin:0.35rem 0 0.55rem 0;
        text-align:center;
    ">
        <h2 style="margin:0; padding:0; font-size:1.05rem; line-height:1.0;">
            The Writer Studios
        </h2>
        <p style="font-size:0.85rem; line-height:1.0; margin:0.18rem 0 0 0; padding:0;">
            Navigate your project through each creative production room.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# WBS GLOBAL SAVE-BEFORE-STAGE-CHANGE 2026-10-24
from core.stages import _WBS_STAGE_TITLES

from core.stages import wbs_stage_title

def wbs_verify_navigation_project_identity():
    """Read-only reconciliation of a stale active ID for a loaded checkpoint.

    The loaded saved-version record, saved-session record, user, format and
    manuscript content must all agree before restoring an active project ID.
    Never auto-save, auto-rename, or substitute one project's content.
    """
    state = st.session_state
    expected_id = str(state.get("_wbs_loaded_project_id") or "")
    active_id = str(get_active_project_id() or "")
    if not expected_id or active_id == expected_id:
        return True

    # Absence of a checkpoint identity must NOT cause us to guess based on title.
    version_id = str(state.get("_wbs_loaded_manuscript_version_id") or "")
    saved_session_id = str(state.get("_wbs_loaded_saved_session_id") or "")
    user_id = str(get_current_user_id() or "")
    expected_title = str(state.get("_wbs_loaded_project_title") or "").strip()
    displayed_title = get_project_title()
    source_text = str(state.get("saved_version_source_text") or "")
    if not (version_id and saved_session_id and user_id and expected_title
            and displayed_title == expected_title and source_text):
        return False
    try:
        version_result = (
            supabase.table("writersblock_manuscript_versions")
            .select("id,project_id,manuscript_content")
            .eq("id", version_id).eq("user_id", user_id).limit(1).execute()
        )
        saved_result = (
            supabase.table("writersblock_project_drafts")
            .select("id,project_id,draft_type,draft_content")
            .eq("id", saved_session_id).eq("user_id", user_id).limit(1).execute()
        )
        versions = getattr(version_result, "data", None) or []
        sessions = getattr(saved_result, "data", None) or []
        if len(versions) != 1 or len(sessions) != 1:
            return False
        version, session = versions[0], sessions[0]
        if (str(version.get("project_id") or "") != expected_id
                or str(session.get("project_id") or "") != expected_id
                or session.get("draft_type") != "project_session"
                or str(version.get("manuscript_content") or "").strip() != source_text.strip()):
            return False
        snapshot = json.loads(session.get("draft_content") or "{}")
        if not isinstance(snapshot, dict):
            return False
        # Reject any persisted session which is itself tagged with another ID.
        if str(snapshot.get("current_project_id") or expected_id) != expected_id:
            return False
        saved_format = str(snapshot.get("active_format_id") or "")
        if saved_format and saved_format != str(state.get("active_format_id") or ""):
            return False
        # Parent title must agree with the loaded screen title.
        if get_project_title_from_project_id(expected_id).strip() != expected_title:
            return False
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
    except Exception:
        # Database/network failures cannot authorize identity repair.
        return False
    # All verification above was read-only. This repairs only an in-memory ID.
    state["current_project_id"] = expected_id
    return True


def wbs_stage4_final_access_ready():
    from core.integrity_review import ready
    if not ready(st.session_state,required=project_integrity_review_applies()):return False
    from core.manuscript_structure import profile,configured,approved,pending_edits
    if profile(st.session_state['active_format_id'])['structured_editor'] and pending_edits(st.session_state):return False
    if profile(st.session_state['active_format_id'])['structured_editor'] and configured(st.session_state):
        return approved(st.session_state)
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_final_access_ready', globals())


def wbs_editorial_ready_for_assessment():
    """Read-only Stage 4 approval gate, scoped to this saved project/revision/text.

    A four-scene manuscript needs all three explicit approvals. Non-scene
    formats retain the existing editorial Integrity requirements.
    """
    from core.integrity_review import ready
    if not ready(st.session_state,required=project_integrity_review_applies()):return False
    from core.manuscript_structure import profile,configured,approved,pending_edits
    if profile(st.session_state['active_format_id'])['structured_editor'] and pending_edits(st.session_state):return False
    if profile(st.session_state['active_format_id'])['structured_editor'] and configured(st.session_state):
        return approved(st.session_state)
    if st.session_state.get("active_format_id") in {"biography_memoir", "childrens_interactive_educational"}:
        from importlib import import_module
        return import_module("formats." + st.session_state["active_format_id"] + ".state").is_approved(st.session_state)
    manuscript = str(st.session_state.get("current_draft_output") or "")
    project = str(get_active_project_id() or "")
    row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "")
    if not manuscript.strip() or not project or not row_id:
        return False
    if not wbs_stage4_final_access_ready():
        return False
    signature = get_text_signature(manuscript)
    if project_integrity_review_applies():
        if (not str(st.session_state.get("project_integrity_report") or "").strip()
                or st.session_state.get("project_integrity_source_signature") != signature):
            return False
    blocks = st.session_state.get("scene_blocks") or {}
    exact_four = (isinstance(blocks, dict)
                  and {int(k) for k in blocks if str(k) in ("1", "2", "3", "4")} == {1, 2, 3, 4}
                  and manuscript == "\n\n".join(str(blocks.get(n, blocks.get(str(n), ""))) for n in range(1, 5)))
    if st.session_state.get("active_format_id") == "short_story" or exact_four:
        approvals = wbs_stage4_final_status(
            st.session_state.get("wbs_stage4_final_acceptance"),
            get_project_title(), manuscript,
            st.session_state.get("project_integrity_report") or "",
            st.session_state.get("project_integrity_source_signature"),
            True, project, row_id,
        )
        return all(approvals.values())
    return True


def wbs_request_stage_change(destination, export_view=None):
    """Go directly to the requested writing stage; never display a second save gate.

    Project saving is a master-first action; later edits create new versions.
    """
    current = st.session_state.get("project_stage", "Intake")
    current_export = bool(st.session_state.get("export_view", False))
    target_export = (current_export if export_view is None else bool(export_view)) if destination == "Isolation Guardrail" else False
    if current == destination and current_export == target_export:
        return
    # Stop cross-project leakage before stage 2/3/4 displays cached story text.
    anchor_id = str(st.session_state.get("_wbs_loaded_project_id") or "")
    anchor_title = str(st.session_state.get("_wbs_loaded_project_title") or "").strip()
    active_id = str(get_active_project_id() or "")
    active_title = get_project_title()
    if anchor_id and anchor_id != active_id:
        if not wbs_verify_navigation_project_identity():
            st.error(
                "Project identity needs verification. Navigation was blocked; "
                "no work was saved or overwritten. Reload the exact saved item."
            )
            return
        active_id = str(get_active_project_id() or "")
    # A display-only revision suffix is not a project rename. Compare the
    # canonical project title, not the editable/display label.
    if anchor_id and anchor_title and current == "Intake" and destination != "Intake":
        canonical_title = get_project_title_from_project_id(anchor_id)
        if canonical_title and canonical_title.strip() != anchor_title.strip():
            st.error("Saved project identity does not match. Reload the saved project.")
            return
    # Sidebar review is non-destructive: preserve all in-memory edits and
    # generated work. Saving is required by the development/advance controls,
    # not by read-only movement among already developed stages.
    review_levels = {"Intake": 1, "Sandbox": 2, "Plot Architect": 3,
                     "Drafting Engine": 4, "Isolation Guardrail": 4,
                     "Revision Engine": 4, "Rewrite Engine": 4}
    target_level = 5 if destination == "Isolation Guardrail" and target_export else review_levels.get(destination, 99)
    if destination == "Publisher Assessment":
        if not wbs_editorial_ready_for_assessment():
            st.warning("Approve and save the current editorial revision before Publisher Assessment.")
            return
        target_level = 4
    if (destination == "Isolation Guardrail" and target_export
            and not wbs_stage4_final_access_ready()):
        st.warning("Review and accept the complete story in Stage 4 before Final Manuscript.")
        return
    if destination == "Isolation Guardrail" and target_export and wbs_editorial_ready_for_assessment():
        target_level = 4  # Optional Stage 5 is not an additional approval gate.
    if target_level > wbs_reached_review_level(st.session_state):
        st.warning("This stage has not been developed yet.")
        return
    st.session_state["wbs_pending_stage_change"] = {
        "target": destination, "export_view": target_export,
        "source": current, "source_export_view": current_export,
    }
    wbs_complete_stage_change()

def wbs_complete_stage_change():
    pending = st.session_state.pop("wbs_pending_stage_change", None)
    if not pending:
        return
    target = pending["target"]
    previous = pending["source"]
    # Review navigation must not clear or regenerate any developed content.
    # Downstream invalidation belongs to an explicit edit/generation action.
    st.session_state.project_stage = target
    st.session_state.export_view = bool(pending["export_view"]) if target == "Isolation Guardrail" else False
    st.rerun()

def wbs_render_stage_save_gate():
    """Legacy compatibility: the redundant confirmation screen is retired."""
    return

def wbs_reached_review_level(state):
    """Furthest reached milestone; earlier rooms remain reviewable even if
    intermediate generated data was not retained in an older saved version.
    Does not unlock any undeveloped stage or change manuscript state.
    """
    level = int(state.get("_wbs_unlocked_saved_stage") or 1)
    if state.get("active_format_id") in {"biography_memoir", "childrens_interactive_educational"}:
        values = (state.get("format_template_values") or {}).get(state["active_format_id"]) or {}
        try:
            level = max(level, min(5, int(values.get("stage_unlocked") or 1)))
        except (TypeError, ValueError):
            pass  # Invalid imported milestones cannot unlock a stage.
    current = str(state.get("project_stage") or "Intake")
    level = max(level, {"Intake": 1, "Sandbox": 2, "Plot Architect": 3,
                        "Drafting Engine": 4, "Isolation Guardrail": 4,
                        "Revision Engine": 4, "Rewrite Engine": 4}.get(current, 1))
    if state.get("sandbox_slates") is not None:
        level = max(level, 2)
    if state.get("chosen_option") is not None or str(state.get("plot_outline") or "").strip():
        level = max(level, 3)
    if str(state.get("current_draft_output") or "").strip() or str(state.get("rewritten_manuscript") or "").strip():
        level = max(level, 4)
    if str(state.get("final_output_text") or "").strip() or bool(state.get("export_view")):
        level = max(level, 5)
    # Visiting optional Stage 5 unlocks final output without forcing an AI call.
    passport = (str(get_active_project_id() or ""),
                str(state.get("_wbs_active_saved_session_row_id") or ""),
                get_text_signature(state.get("current_draft_output") or ""))
    if state.get("_wbs_stage5_passport") == passport and passport[0] and passport[1]:
        level = max(level, 5)
    if str(state.get("current_manuscript_save_status") or "").upper() == "FINAL":
        level = max(level, 5)
    elif str(state.get("saved_version_source_text") or "").strip():
        level = max(level, 4)
    return min(level, 5)

_wbs_unlocked = wbs_reached_review_level(st.session_state)
from core.stage_navigation import ACTIVE_NAV_STYLE
st.sidebar.markdown(ACTIVE_NAV_STYLE, unsafe_allow_html=True)
can_navigate_to_sandbox = _wbs_unlocked >= 2
can_navigate_to_plot = _wbs_unlocked >= 3
can_navigate_to_drafting = _wbs_unlocked >= 4
can_navigate_to_guardrail = _wbs_unlocked >= 4
can_navigate_to_revision = _wbs_unlocked >= 4
can_navigate_to_rewrite = _wbs_unlocked >= 4

can_use_sandbox = access_allows("sandbox")
can_use_plot = access_allows("plot")
can_use_drafting = access_allows("drafting")
can_use_safety = access_allows("safety")
can_use_revision = access_allows("revision")
can_use_rewrite = access_allows("rewrite")

if st.session_state.project_stage == "Intake":
    st.sidebar.button("🔵 1. Concept Development (Active)", key="nav_intake_active", use_container_width=True, type="primary")
else:
    if st.sidebar.button("⚪ 1. Concept Development", key="nav_intake", use_container_width=True):
        wbs_request_stage_change("Intake")

if st.session_state.project_stage == "Sandbox":
    st.sidebar.button("🔵 2. Plot Architecture (Active)", key="nav_sandbox_active", use_container_width=True, type="primary")
elif can_navigate_to_sandbox:
    if st.sidebar.button("⚪ 2. Plot Architecture", key="nav_sandbox", use_container_width=True):
        wbs_request_stage_change("Sandbox")
else:
    st.sidebar.button("🔒 2. Plot Architecture (Locked)", key="nav_sandbox_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Plot Architect":
    st.sidebar.button("🔵 3. Scene Scripting (Active)", key="nav_plot_active", use_container_width=True, type="primary")
elif can_navigate_to_plot:
    if st.sidebar.button("⚪ 3. Scene Scripting", key="nav_plot", use_container_width=True):
        wbs_request_stage_change("Plot Architect")
else:
    st.sidebar.button("🔒 3. Scene Scripting (Locked)", key="nav_plot_locked", disabled=True, use_container_width=True)

# Five-stage navigation: drafting runs internally; editing tools share Stage 4.
# Legacy internal stages remain loadable for earlier saved projects.
if st.session_state.project_stage == "Drafting Engine":
    st.sidebar.info("🔵 Scene Development — Manual Review (Active)")

_is_draft_review = (st.session_state.project_stage in {"Isolation Guardrail", "Revision Engine", "Rewrite Engine"}
                    and not (st.session_state.project_stage == "Isolation Guardrail" and st.session_state.get("export_view", False)))
if _is_draft_review:
    st.sidebar.button("🔵 4. Editorial & Publisher Review (Active)", key="nav_guard_active", use_container_width=True, type="primary")
elif can_navigate_to_guardrail:
    if st.sidebar.button("⚪ 4. Editorial & Publisher Review", key="nav_guard", use_container_width=True):
        wbs_request_stage_change("Isolation Guardrail", export_view=False)
else:
    st.sidebar.button("🔒 4. Editorial & Publisher Review (Locked)", key="nav_guard_locked", disabled=True, use_container_width=True)

# The original saved internal stage IDs remain unchanged for project/session restoration.
# New sequence: Stage 4 editorial approval -> Stage 5 optional publisher assessment
# -> Stage 6 existing final save/print/export engine.
_wbs_stage5_ready = (
    not st.session_state.get("demo_mode")
    and bool(get_active_project_id())
    and wbs_editorial_ready_for_assessment()
)
_wbs_stage5_passport = (
    str(get_active_project_id() or ""),
    str(st.session_state.get("_wbs_active_saved_session_row_id") or ""),
    get_text_signature(st.session_state.get("current_draft_output") or ""),
)
_wbs_stage5_visited = st.session_state.get("_wbs_stage5_passport") == _wbs_stage5_passport
if st.session_state.project_stage == "Publisher Assessment":
    st.sidebar.button("🔵 5. Publisher & Market Readiness (Active)",
                      key="nav_publisher_assessment_active", use_container_width=True, type="primary")
elif _wbs_stage5_ready:
    if st.sidebar.button("⚪ 5. Publisher & Market Readiness (Optional)",
                         key="nav_publisher_assessment", use_container_width=True):
        st.session_state.project_stage = "Publisher Assessment"
        st.session_state.export_view = False
        st.rerun()
else:
    st.sidebar.button("🔒 5. Publisher & Market Readiness (Locked)",
                      key="nav_publisher_assessment_locked", disabled=True,
                      use_container_width=True)

stage_8_label = "Manuscript Review" if st.session_state.get("demo_mode") else "Final Manuscript"
_wbs_stage6_ready = (_wbs_stage5_ready and _wbs_stage5_visited)
# Previously saved FINAL checkpoints must remain accessible after upgrading,
# even if the older record predates the optional assessment stage.
_wbs_legacy_final_exists = (
    str(st.session_state.get("current_manuscript_save_status") or "").upper() == "FINAL"
    and bool(get_active_project_id())
    and wbs_stage4_final_access_ready()
)
if st.session_state.project_stage == "Isolation Guardrail" and st.session_state.get("export_view", False):
    st.sidebar.button(f"🔵 6. {stage_8_label} (Active)", key="nav_export_active", use_container_width=True, type="primary")
elif _wbs_stage6_ready or _wbs_legacy_final_exists:
    if st.sidebar.button(f"⚪ 6. {stage_8_label}", key="nav_export", use_container_width=True):
        wbs_request_stage_change("Isolation Guardrail", export_view=True)
else:
    st.sidebar.button(f"🔒 6. {stage_8_label} (Locked)", key="nav_export_locked", disabled=True, use_container_width=True)

st.sidebar.markdown("---")

with st.sidebar.container(border=True):
    st.markdown("**Current Project**")
    active_project_title = get_project_title()
    active_saved_at = st.session_state.get("last_saved_project_at")
    active_status = str(st.session_state.get("current_manuscript_save_status") or "").strip().upper()
    active_stage = str(st.session_state.get("current_manuscript_save_stage") or "").strip()
    active_project_version = int(
        st.session_state.get("current_manuscript_save_version")
        or st.session_state.get("manuscript_version", 0)
        or 0
    )

    if active_project_title:
        st.write(active_project_title)
        current_version_name = clean_project_version_name(
            st.session_state.get("project_version_name") or "Original"
        ) or "Original"
        st.caption(f"Version: {current_version_name}")
        _loaded_id = str(st.session_state.get("_wbs_loaded_saved_session_id") or "")
        _manuscript_id = str(st.session_state.get("_wbs_loaded_manuscript_version_id") or "")
        _loaded_words = None
        for _item in _saved_status_items:
            _row = _item.get("row") or {}
            if str(_row.get("project_id") or "") != str(get_active_project_id() or ""):
                continue
            if _item.get("type") == "manuscript_version" and _manuscript_id and str(_row.get("id") or "") == _manuscript_id:
                _loaded_words = count_words(_row.get("manuscript_content") or "")
                break
            if _item.get("type") == "project_session" and _loaded_id and str(_row.get("id") or "") == _loaded_id:
                try:
                    _snap = json.loads(_row.get("draft_content") or "{}")
                except (ValueError, TypeError):
                    _snap = {}
                _text = get_best_saved_manuscript_source(_snap) if isinstance(_snap, dict) and _snap else ""
                if not _text and isinstance(_snap, dict):
                    _text = str(_snap.get("story_seed") or "")
                _loaded_words = count_words(_text)
        if _loaded_words is not None:
            st.caption(f"Loaded Version Word Total: {_loaded_words:,}")
        if st.session_state.get("project_scope") == "Book in a Series":
            st.caption(
                f"{st.session_state.get('series_name') or 'Unnamed Series'} — "
                f"{get_series_item_display()}"
            )
        if active_status in {"DRAFT", "FINAL"} and active_project_version > 0:
            st.caption(f"{active_status} V{active_project_version}")
            if active_saved_at:
                st.caption(f"Saved {full_date_label(active_saved_at)}")
        elif active_saved_at:
            working_version = max(1, int(st.session_state.get("manuscript_version", 0) or 0) + 1)
            st.caption(f"PROJECT SAVE — {full_date_label(active_saved_at)} — Working V{working_version}")
        else:
            working_version = max(1, int(st.session_state.get("manuscript_version", 0) or 0) + 1)
            st.caption(f"Working Draft — V{working_version}")
    else:
        if st.session_state.get("demo_mode"):
            st.caption("Trial project — Save Project unlocks in the full Writer Edition")
        else:
            st.caption("First name the project, then select Save Project")

    # Saved project format is immutable here. A format conversion is not a
    # metadata-only operation: the Concept setup and downstream writing differ.
    # Removing the old metadata-change button prevents accidental loss of the
    # project's true template and the creation of spurious numbered revisions.
    if active_project_title and get_active_project_id():
        current_saved_format_id = str(st.session_state.get("active_format_id") or "")
        if current_saved_format_id in WBS_FORMAT_IDS:
            st.caption(f"Format: {get_wbs_format_display_name(current_saved_format_id)}")
        if st.session_state.pop("_wbs_concept_recovered_for_review", False):
            st.info("Concept setup was restored from an earlier save of this same project. Review it before saving.")

with st.sidebar:
    if st.session_state.get("demo_mode"):
        if st.button("💾 Save Project 🔒", key="save_current_project_session_trial", use_container_width=True, type="secondary"):
            full_version_only_notice("Saved Projects")
    else:
        _sidebar_has_master = wbs_has_saved_master()
        if _sidebar_has_master is None:
            st.warning("Cannot verify saved project history; saving is disabled.")
        elif _sidebar_has_master:
            render_save_as_named_version_control("sidebar")
        elif st.button("💾 Save Project — Create Master", key="save_current_project_session", use_container_width=True, type="secondary"):
            if not get_project_title():
                st.warning("Name the project in Concept Development first.")
            else:
                _master_result = save_current_project_session_to_supabase()
                if _master_result and not getattr(_master_result, "unchanged", False):
                    st.success("Master project saved. Future changes become versions.")
                    st.rerun()

if st.session_state.get("demo_mode"):
    if st.sidebar.button("📚 Saved Version Manager 🔒", key="sidebar_saved_version_manager_trial", use_container_width=True, type="secondary"):
        full_version_only_notice("Saved Versions")
elif can_navigate_to_guardrail and can_use_safety:
    if st.sidebar.button("📚 Saved Version Manager", key="sidebar_saved_version_manager_shortcut", use_container_width=True, type="secondary"):
        st.session_state.show_saved_version_manager = True
        wbs_request_stage_change("Isolation Guardrail", export_view=True)
else:
    st.sidebar.button("🔒 Saved Version Manager", key="sidebar_saved_version_manager_locked", disabled=True, use_container_width=True, type="secondary")

# ==========================================
# PHASE 1: CONCEPT DEVELOPMENT
# ==========================================
SPARK_BANK = {
    "Novel / Prose": [
        "A retired cartographer discovers that one forgotten road on every map he ever drew leads to the same abandoned house.",
        "A woman inherits a rural post office where letters continue arriving for residents who died decades ago.",
        "A historian finds a family diary that accurately describes events scheduled to happen the following week.",
    ],
    "Short Story": [
        "An antique shop owner buys a heavy iron safe that cannot be opened, only to realize that every night, the ticking sounds coming from inside it get faster.",
        "In a city where memories can be bought and sold like currency, a detective is hired to find a beautiful memory that someone was murdered to forget.",
        "A lighthouse keeper notices that the light is not reflecting off the ocean anymore — instead, something beneath the water is shining a different light back up at him.",
    ],
    "Novella": [
        "A small-town undertaker receives instructions for a funeral belonging to someone who is still alive and living across the street.",
        "During a week-long snowstorm, the guests of an isolated inn discover that each room contains an object from one guest's future.",
        "An aging stage magician is offered one final performance by a theatre that burned down forty years earlier.",
    ],
    "Audio Book": [
        "A lighthouse keeper records one final message before the fog rolls in and the lanterns begin answering back.",
        "An elderly train conductor tells a passenger the same bedtime story every night, only to discover the story is changing.",
        "A woman staying alone in a quiet seaside inn hears a piano playing downstairs after midnight, though the inn has no piano.",
    ],
    "Screenplay Outline": [
        "A disgraced detective is forced to pair up with an AI android to solve a string of cyber-crimes, only to realize the android's code matches the handwriting of his missing daughter.",
        "A group of astronauts on a deep-space research vessel wake up from hyper-sleep to find an extra stasis pod on board that was not there when they launched.",
        "A forensic accountant auditing a massive tech corporation discovers a secret payroll line for an employee who has been paid continuously since 1895.",
    ],
    "Stage Play / Dramatic Script": [
        "Three estranged siblings gather in their childhood home to read a will that requires them to remain together until sunrise.",
        "A retired judge and the prisoner he once sentenced meet unexpectedly in an empty railway waiting room.",
        "Two actors rehearsing a forgotten play realize the dialogue is revealing secrets neither has confessed.",
    ],
    "Full Novel Blueprint": [
        "In a dystopian future where the human brain is permanently connected to a cloud network, a glitch causes one man to hear the internal monologues of everyone within a 1-mile radius.",
        "A young archeologist unearths a pristine modern digital watch buried inside an untouched 3,000-year-old Egyptian pharaoh's tomb.",
        "An elite hacker discovers a hidden string of code embedded in the human genome that acts as an IP address — and someone just tried to ping it from deep space.",
    ],
    "Children's Picture Book (32-Page Layout)": [
        "A tiny, brave field mouse finds a shiny fallen star in a meadow and journeys across the forest to toss it back into the night sky.",
        "A little boy discovers that his shadow does not want to copy him anymore — it wants to dance, explore, and teach him bravery.",
        "Barnaby the Bear is terrified of the dark until a wise old owl shows him that night is a soft velvet blanket embroidered with stars.",
    ],
}


# Stage 5 is a separate, optional publisher assessment module. It reads
# the exact saved Stage 4 editorial revision; it cannot alter manuscript text.
if st.session_state.project_stage == "Publisher Assessment":
    from core.workflow_runtime import run_workflow
    run_workflow('publisher_assessment', globals())

if st.session_state.project_stage == "Intake":
    from core.workflow_runtime import run_workflow
    run_workflow('concept_development', globals())

elif st.session_state.project_stage == "Sandbox":
    from core.workflow_runtime import run_workflow
    run_workflow('plot_architecture', globals())

# WBS FIXES-4 — Novel/Novella helpers. Other writing formats are not modified.




def wbs_novel_save_chapters(changed, previous_source):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_novel_save_chapters', globals(), changed, previous_source)


# SHORT STORY SCENE SCRIPTING — independent of other format pipelines.
# Existing stage identifiers and Supabase revision IDs are not changed.






def wbs_ss_revision_identity():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_revision_identity', globals())


def wbs_ss_save_scene_to_current_revision(scene_number, scene_text):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_save_scene_to_current_revision', globals(), scene_number, scene_text)


def wbs_ss_safe_scene_draft(draft, recorded_scene):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_safe_scene_draft', globals(), draft, recorded_scene)


def wbs_ss_capture_draft_on_selection_change():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_capture_draft_on_selection_change', globals())


def wbs_ss_approved_for_final():
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_ss_approved_for_final', globals())

# STAGE 4 — Editorial approvals share one scene-based workflow across formats.
# The selected scene's content is NEVER changed by approving it. A review
# confirmation is stored on the existing project_session row, without V-number
# increments or a new version. Saved content hashes prevent stale approvals.
def wbs_stage4_approval_record(blocks, manuscript):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_approval_record', globals(), blocks, manuscript)


def wbs_stage4_valid_approvals(approvals, blocks, manuscript):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_valid_approvals', globals(), approvals, blocks, manuscript)


def wbs_stage4_accept_and_save(scene_number=None):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_accept_and_save', globals(), scene_number)


def wbs_stage4_save_manuscript_corrections(edited_blocks, expected_manuscript, expected_blocks):
    from core.workflow_runtime import call_format_helper
    return call_format_helper('wbs_stage4_save_manuscript_corrections', globals(), edited_blocks, expected_manuscript, expected_blocks)


# ==========================================
# PHASE 3: PLOT ARCHITECT ENGINE
# ==========================================
if st.session_state.project_stage == "Plot Architect":
    from core.workflow_runtime import run_workflow
    run_workflow('scene_scripting', globals())

# ======================================
# PHASE 4: RECURSIVE DRAFTING ENGINE
# ======================================
elif st.session_state.project_stage in ["Drafting", "Drafting Engine"]:
    from core.workflow_runtime import run_workflow
    run_workflow('drafting', globals())
# ======================================================================================
# PHASE 5: SCRIPT LOCK / MANUSCRIPT OUTPUT
# ======================================================================================
elif st.session_state.project_stage == "Isolation Guardrail":
    from core.workflow_runtime import run_workflow
    run_workflow('editorial_review', globals())
# ======================================================================================
# PHASE 6: SCRIPT POLISH
# ======================================================================================
if st.session_state.project_stage == "Revision Engine":
    from core.workflow_runtime import run_workflow
    run_workflow('script_polish', globals())
# ============================================================
# PHASE 7: SCRIPT REWRITE
# ============================================================
elif st.session_state.project_stage == "Rewrite Engine":
    from core.workflow_runtime import run_workflow
    run_workflow('script_rewrite', globals())

# ==========================================
# WBS AI AGENT — LATE SHADOW STATE READ
# ==========================================
