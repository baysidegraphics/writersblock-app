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
from supabase import create_client
from quill import render_quill_for_current_stage
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
PURCHASE_URL = "https://buy.stripe.com/bJeeVeckVeui86Vdwn5Vu0a"  # Paste the direct Stripe Payment Link here when created.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# AFFITOR AFFILIATE LEAD ATTRIBUTION
# ==========================================
# The public WritersBlock website passes the first-party Affitor click ID into
# the Streamlit app as ?affitor_click_id=... . Keep it in session state across
# Streamlit reruns, then bind it to the stable WritersBlock user ID after signup.
AFFITOR_LEAD_ENDPOINT = "https://api.affitor.com/api/v1/track/lead"


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
    licensed_user_row = st.session_state.get("licensed_user_row") or {}
    demo_user_row = st.session_state.get("demo_user_row") or {}

    if isinstance(licensed_user_row, dict) and licensed_user_row.get("id"):
        return licensed_user_row.get("id")

    if isinstance(demo_user_row, dict) and demo_user_row.get("id"):
        return demo_user_row.get("id")

    return None


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
    "picture_book_word_target", "picture_book_page_size", "story_seed", "wbs_project_original_concept",
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
    """First save creates the master; all subsequent changed saves make versions.

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
    st.session_state.pop("_wbs_stage1_continue_approval", None)
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
        verified = prepare_saved_snapshot(normalized_raw, load_project_id, restored_format_id)
    except SavedFormatError as exc:
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
load_dotenv()

if "backend" not in st.session_state:
    st.session_state.backend = GeminiWriterBackend()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
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
    if not values:
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
    for key, value in values.items():
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
    template = st.session_state.get("active_format_template") or {}
    fields = [f for f in (template.get("concept_fields") or []) if isinstance(f, dict)]
    if not fields:
        return

    # These are already supplied by common WritersBlock controls elsewhere on Step 1.
    shared_keys = {
        "project_title", "dialogue_style",
        "story_premise", "premise", "logline", "story_idea", "objective",
        "core_premise",
    }
    values = get_active_format_template_values()
    render_fields = [
        f for f in fields
        if str(f.get("key")) not in shared_keys and format_field_should_render(f, values)
    ]
    if not render_fields:
        return

    setup_name = str(template.get("display_name") or st.session_state.get("quill_format_name") or "Format").strip()
    st.markdown(f"### {setup_name} Development Setup")
    st.caption(str(template.get("description") or ""))

    # Keep the form compact: two controlled columns inside the middle panel.
    for i in range(0, len(render_fields), 2):
        row = render_fields[i:i + 2]
        cols = st.columns(2, gap="medium")
        for col, field in zip(cols, row):
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            label = str(field.get("label") or key)
            help_text = str(field.get("help") or "") or None
            widget_key = get_active_format_widget_key(key)
            existing = values.get(key, "")

            with col:
                if field.get("type") == "select":
                    options = list(field.get("options") or [])
                    if (("genre" in key.lower() or "genre" in label.lower())
                            and "Spiritual" not in options):
                        options.append("Spiritual")
                    if key == "production_influence":
                        custom_option = "Custom Influence / Other"
                        if custom_option not in options:
                            options.append(custom_option)
                    # Picture-book ages: flexible, inclusive age-range selection.
                    age_field = (
                        str(st.session_state.get("active_format_id")) == "childrens_picture_book"
                        and ("age" in key.lower() or "age" in label.lower())
                    )
                    if age_field:
                        options = list(dict.fromkeys(options + [
                            "0-2", "2-5", "3-8", "5-9", "6-10", "8-12",
                            "Custom age range",
                        ]))
                    if not options:
                        continue
                    # Re-open custom ranges as a custom selection, not the first preset.
                    chosen_age = existing
                    if age_field and existing not in options and str(existing).strip():
                        chosen_age = "Custom age range"
                    index = options.index(chosen_age) if chosen_age in options else 0
                    value = st.selectbox(
                        label, options, index=index, key=widget_key, help=help_text
                    )
                    if age_field and value == "Custom age range":
                        from_age, to_age = st.columns(2)
                        found = re.search(r"(\d+)\s*[-–]\s*(\d+)", str(existing or ""))
                        start_age = int(found.group(1)) if found else 3
                        end_age = int(found.group(2)) if found else 8
                        with from_age:
                            lower_age = st.number_input("From age", 0, 18, start_age,
                                key=f"{widget_key}_from")
                        with to_age:
                            upper_age = st.number_input("To age", 0, 18, end_age,
                                key=f"{widget_key}_to")
                        if lower_age > upper_age:
                            st.warning("The ending age must be at least the starting age.")
                            value = str(existing or "")
                        else:
                            value = f"{lower_age}-{upper_age}"
                elif field.get("type") == "date":
                    try:
                        existing_date = datetime.strptime(str(existing), "%Y-%m-%d").date() if existing else datetime.now().date()
                    except Exception:
                        existing_date = datetime.now().date()
                    selected_date = st.date_input(
                        label, value=existing_date, key=widget_key, help=help_text
                    )
                    value = selected_date.isoformat() if selected_date else ""
                elif field.get("type") == "textarea":
                    value = st.text_area(
                        label, value=str(existing or ""), height=95, key=widget_key, help=help_text
                    )
                else:
                    value = st.text_input(
                        label, value=str(existing or ""), key=widget_key, help=help_text
                    )
                set_active_format_template_value(key, value)

                # Production Influence is mutually exclusive: either choose a preset
                # OR choose Custom Influence / Other and enter a custom reference.
                if key == "production_influence":
                    custom_key = "production_influence_custom"
                    custom_option = "Custom Influence / Other"
                    if value == custom_option:
                        custom_widget_key = get_active_format_widget_key(custom_key)
                        custom_existing = values.get(custom_key, "")
                        custom_value = st.text_input(
                            "Custom Influence",
                            value=str(custom_existing or ""),
                            key=custom_widget_key,
                            help=(
                                "Enter an author, director, playwright, filmmaker, or creative style "
                                "not listed above."
                            ),
                            placeholder="Enter the influence you want WritersBlock to use",
                        )
                        set_active_format_template_value(custom_key, custom_value)
                        st.session_state.author_style = str(custom_value or "").strip()
                    else:
                        # A preset choice always wins and removes any stale custom value.
                        set_active_format_template_value(custom_key, "")
                        st.session_state.author_style = str(value or "").strip()
                elif key == "visual_style":
                    st.session_state.author_style = str(value or "")
                elif key == "narration_type":
                    st.session_state.author_style = f"Narration Type: {value}" if value else ""

    refresh_quill_template_context()
    if is_picture_book_project():
        render_picture_book_budget("development", editable=True)



def wbs_concept_contains_editorial_commentary(text):
    """Reject planning notes mistakenly presented as a writer-facing concept."""
    text = str(text or "")
    editorial_patterns = (
        r"\b(?:this|the) (?:story|flash story|narrative|premise|concept|episode|screenplay|script|plot)\s+(?:explores|examines|focuses on|centers on|revolves around|will|should|aims to|is about|follows|depicts|portrays)\b",
        r"\b(?:the )?(?:central|core|main) (?:idea|theme|premise|tension|conflict) (?:is|explores|examines|centers|focuses)\b",
        r"\b(?:the )?(?:narrative|story|plot|episode|script) should\b",
        r"\b(?:from a|in a) (?:first|third)[ -]person perspective\b",
        r"\b(?:the writer|the author|the reader|the audience) (?:should|will|can|must)\b",
        r"\b(?:the ending|the climax|the resolution) (?:should|will|can)\b",
        r"\b(?:this concept|this premise|this suggestion)\b",
        r"\b(?:target audience|genre|dialogue style|production influence):\s",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in editorial_patterns)


def render_format_template_save_reminder():
    """One master Save Project, then non-destructive new versions (all formats)."""
    st.markdown("---")
    with st.container(border=True):
        if st.session_state.get("demo_mode"):
            st.caption("Project saving is available in the full Writer Edition.")
            if st.button("💾 Save Project 🔒", key="template_save_project_trial", use_container_width=True):
                full_version_only_notice("Saved Projects")
            return
        has_master = wbs_has_saved_master()
        if has_master is None:
            st.warning("Cannot verify this project's save history. Saving is disabled until the connection is restored.")
        elif has_master:
            render_save_as_named_version_control(
                f"concept_{st.session_state.get('active_format_id', 'format')}"
            )
        elif st.button(
            "💾 Save Project — Create Master",
            key=f"template_save_project_{st.session_state.get('active_format_id', 'format')}",
            use_container_width=True, type="secondary",
        ):
            if not get_project_title():
                st.warning("Name the new project before saving.")
                return
            result = save_current_project_session_to_supabase()
            if result and not getattr(result, "unchanged", False):
                st.success("Master project saved. Future changes are new versions.")
                st.rerun()


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

def count_words(text):
    return len(re.findall(r"\b\w+\b", str(text or "")))


def get_text_signature(text):
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def safe_download_stem(value, fallback="writersblock_output"):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return stem.lower() or fallback


PICTURE_BOOK_FORMAT = "Children's Picture Book (32-Page Layout)"
PICTURE_BOOK_LAYOUT_TEMPLATES = [
    "Full Illustration — Text Top",
    "Full Illustration — Text Bottom",
    "Text Left — Illustration Right",
    "Illustration Left — Text Right",
    "Two-Page Illustration — Text Overlay",
    "Spot Illustration — Open Text Area",
]

PICTURE_BOOK_PAGE_SIZES = {
    "8.5 x 8.5 Square": {
        "page_width": 8.5,
        "page_height": 8.5,
        "spread_aspect": "2 / 1",
        "trim_reference": "8.5 x 8.5 square planning layout",
    },
    "10 x 8 Landscape": {
        "page_width": 10.0,
        "page_height": 8.0,
        "spread_aspect": "5 / 2",
        "trim_reference": "10 x 8 landscape planning layout",
    },
}

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

def render_picture_book_budget(location="", editable=False):
    if not is_picture_book_project():
        return
    st.markdown("#### 📚 Picture Book — Manuscript Word Budget")
    default, maximum, age_label = picture_book_age_budget_rules()
    target = picture_book_target()
    st.caption(f"Target age {age_label} · suggested {default:,} words · age-group maximum {maximum:,} words")
    if editable:
        # The widget uses an age-specific key so switching ages never changes
        # an already instantiated Streamlit widget's session-state entry.
        age_signature = str(age_label)
        widget_key = "_wbs_pb_target_input_" + re.sub(r"[^0-9A-Za-z]+", "_", age_signature)
        age_changed = st.session_state.get("_wbs_picture_book_budget_age") != age_signature
        if age_changed:
            st.session_state["_wbs_picture_book_budget_age"] = age_signature
            st.session_state["picture_book_word_target"] = default
            # Reset this age's input BEFORE instantiating it, if previously visited.
            st.session_state[widget_key] = default
        elif widget_key not in st.session_state:
            st.session_state[widget_key] = target
        target = st.number_input(
            "Total manuscript word target", min_value=100, max_value=maximum,
            step=25, key=widget_key,
            help="Age-group maximum is enforced. Only finished story text counts; planning text is excluded.",
        )
        # The canonical, non-widget value can safely be used by later stages.
        st.session_state["picture_book_word_target"] = int(target)
    blocks = st.session_state.get("scene_blocks") or {}
    if blocks:
        counts = [count_words(blocks.get(i, blocks.get(str(i), ""))) for i in range(1, 5)]
        used = sum(counts)
    else:
        used = count_words(st.session_state.get("current_draft_output") or "")
        counts = [0, 0, 0, 0]
    remaining = target - used
    st.write(f"**Total manuscript:** {used:,} / {target:,} words · " +
             (f"{remaining:,} remaining" if remaining >= 0 else f"{abs(remaining):,} OVER target"))
    st.progress(min(1., used/max(target, 1)))
    allocations = picture_book_allocations()
    if blocks:
        for i, (allocated, actual) in enumerate(zip(allocations, counts), 1):
            st.caption(f"Beat {i}: {actual} / {allocated} allocated · {allocated-actual:+} remaining")
    else:
        st.caption("Four-beat plan: " + " | ".join(f"Beat {i}: {n} words" for i, n in enumerate(allocations, 1)))
    # The selected target is a planning guide; only the age-group maximum
    # warrants an overlength warning. Do not block an approved manuscript.
    if used > maximum:
        st.warning(f"Manuscript is {used - maximum:,} words above the selected age-group maximum of {maximum:,} words.")

def render_picture_book_template_preview(template_name, page_size_name=None):
    """Show a proportional two-page spread preview for the selected trim size."""
    page_size_name = str(
        page_size_name
        or st.session_state.get("picture_book_page_size")
        or DEFAULT_PICTURE_BOOK_PAGE_SIZE
    )
    size_spec = get_picture_book_page_size_spec(page_size_name)

    container_style = (
        "width:100%;max-width:760px;"
        f"aspect-ratio:{size_spec['spread_aspect']};"
        "margin:0.35rem 0 1rem 0;"
        "border:2px solid #666;border-radius:8px;overflow:hidden;position:relative;"
        "background:#f5f5f5;box-sizing:border-box;color:#111;"
        "font-family:Arial,sans-serif;font-weight:700;letter-spacing:0.02em;"
    )
    illustration_style = (
        "display:flex;align-items:center;justify-content:center;"
        "background:#e5e5e5;color:#333;box-sizing:border-box;"
    )
    story_style = (
        "display:flex;align-items:center;justify-content:center;"
        "background:#ffffff;color:#111;box-sizing:border-box;"
        "padding:12px;text-align:center;"
    )
    gutter_html = (
        "<div style='position:absolute;left:50%;top:0;bottom:0;width:2px;"
        "background:#888;z-index:6;'></div>"
    )

    # Light outlines make the two individual pages obvious.
    page_outline_html = (
        "<div style='position:absolute;left:0;top:0;width:50%;height:100%;"
        "border-right:1px solid #aaa;box-sizing:border-box;z-index:7;pointer-events:none;'></div>"
        "<div style='position:absolute;right:0;top:0;width:50%;height:100%;"
        "border-left:1px solid #aaa;box-sizing:border-box;z-index:7;pointer-events:none;'></div>"
    )

    if template_name == "Full Illustration — Text Top":
        body_html = (
            f"<div style='{illustration_style}position:absolute;inset:0;'>ILLUSTRATION</div>"
            f"<div style='{story_style}position:absolute;left:4%;right:4%;top:7%;height:25%;"
            "border:1px solid #777;z-index:5;'>STORY TEXT</div>"
        )
    elif template_name == "Full Illustration — Text Bottom":
        body_html = (
            f"<div style='{illustration_style}position:absolute;inset:0;'>ILLUSTRATION</div>"
            f"<div style='{story_style}position:absolute;left:4%;right:4%;bottom:7%;height:25%;"
            "border:1px solid #777;z-index:5;'>STORY TEXT</div>"
        )
    elif template_name == "Text Left — Illustration Right":
        body_html = (
            f"<div style='{story_style}position:absolute;left:0;top:0;bottom:0;width:50%;'>STORY TEXT</div>"
            f"<div style='{illustration_style}position:absolute;right:0;top:0;bottom:0;width:50%;'>ILLUSTRATION</div>"
        )
    elif template_name == "Illustration Left — Text Right":
        body_html = (
            f"<div style='{illustration_style}position:absolute;left:0;top:0;bottom:0;width:50%;'>ILLUSTRATION</div>"
            f"<div style='{story_style}position:absolute;right:0;top:0;bottom:0;width:50%;'>STORY TEXT</div>"
        )
    elif template_name == "Two-Page Illustration — Text Overlay":
        body_html = (
            f"<div style='{illustration_style}position:absolute;inset:0;'>ILLUSTRATION ACROSS BOTH PAGES</div>"
            f"<div style='{story_style}position:absolute;left:10%;bottom:9%;width:38%;height:28%;"
            "border:1px solid #777;z-index:5;'>STORY TEXT</div>"
        )
    else:
        body_html = (
            f"<div style='{story_style}position:absolute;left:0;top:0;bottom:0;width:64%;padding:22px;'>"
            "STORY TEXT</div>"
            f"<div style='{illustration_style}position:absolute;right:8%;top:24%;width:24%;height:52%;"
            "border:1px solid #777;border-radius:50%;'>SPOT<br>ILLUSTRATION</div>"
        )

    preview_html = (
        f"<div style='{container_style}'>{body_html}{page_outline_html}{gutter_html}</div>"
        "<div style='font-size:0.78rem;opacity:0.72;margin-top:-0.65rem;margin-bottom:0.25rem;'>"
        f"Preview: two {size_spec['page_width']:g}&quot; × {size_spec['page_height']:g}&quot; pages "
        f"({page_size_name})."
        "</div>"
        "<div style='font-size:0.78rem;opacity:0.70;margin-bottom:0.8rem;'>"
        "Layout preview only — edit the story text and illustration direction below."
        "</div>"
    )

    st.markdown(preview_html, unsafe_allow_html=True)


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
    return selected in PROJECT_INTEGRITY_REVIEW_FORMATS


def render_project_integrity_report_html(report_text):
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
        elif stripped.startswith("- "):
            chunks.append(f"<div class='wbs-ir-bullet'>• {html.escape(stripped[2:].strip())}</div>")
        elif re.match(r"^\d+\.\s", stripped):
            chunks.append(f"<div class='wbs-ir-number'>{safe}</div>")
        else:
            chunks.append(f"<div class='wbs-ir-p'>{safe}</div>")
    chunks.append("</div>")
    return "\n".join(chunks)


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
5. Repetition: duplicated passages, repeated scenes, repeated explanations, or accidental restatement.
6. POV and tense drift, including unexplained changes between sections or chapters.
7. Unresolved placeholders, TODO/TBD notes, bracketed drafting notes, incomplete sentences, or obvious generation artifacts.
8. Missing, duplicated, misordered, or obviously incomplete chapters/scenes/sections when the format uses them.
9. Chapter/section numbering and heading consistency when headings are present.
10. Unresolved story threads, setups, promises, character actions, mysteries, or references that appear accidentally abandoned.
11. Internal contradictions between early and late portions of the manuscript.
12. Output-format compliance for the selected writing format at the manuscript-content level. Do not judge typography that is applied later by Final Output.
13. Any issue likely to embarrass the writer or damage continuity in a final manuscript.

IMPORTANT REVIEW RULES:
- Distinguish an actual contradiction from an intentional mystery, reveal, unreliable narrator, flashback, or deliberate stylistic choice.
- Do not invent problems merely to fill the report.
- Cite the chapter/scene/section or a short identifying phrase whenever possible.
- Do not quote long passages.
- If an item is uncertain, label it "VERIFY" rather than presenting it as a definite error.
- Recommendations must describe what the writer should inspect or consider. Do not rewrite the text.
- First-person dialogue inside quotation marks is normal in third-person narration and is NOT, by itself, a POV violation.
- When evaluating POV compliance, judge the narrative prose outside character dialogue and direct quotations.
- If the project requirements call for first-person POV but the manuscript uses third-person narration with normal first-person dialogue, report it as a narrative POV mismatch rather than a dialogue problem.

RETURN EXACTLY THIS REPORT STRUCTURE:
OVERALL STATUS: PASS
or
OVERALL STATUS: WARNINGS

PROJECT INTEGRITY SUMMARY
[2-6 concise sentences]

CRITICAL WARNINGS
- [items, or "None found."]

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

--- BEGIN MANUSCRIPT ---
{manuscript_text}
--- END MANUSCRIPT ---
""".strip()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    report = str(getattr(response, "text", "") or "").strip()
    if not report:
        raise RuntimeError("The Project Integrity review returned no report.")
    return report


FINAL_OUTPUT_FORMAT_OPTIONS = [
    "Novel / Prose",
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


def render_project_title_banner(stage_key):
    """
    Prominent Current Project banner plus database-safe rename control.
    Render this once near the top of each workflow stage.
    """
    current_title = get_project_title_for_display()
    project_id = str(get_active_project_id() or "new")
    safe_stage = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stage_key or "stage"))

    with st.container(border=True):
        st.markdown("### 📘 CURRENT PROJECT")
        st.markdown(f"## {current_title}")

        if (
            st.session_state.get("project_stage") != "Intake"
            and (st.session_state.get("licensed_mode") or st.session_state.get("demo_mode"))
        ):
            render_quill_for_current_stage(st_module=st, show_prelude=True)

        if st.session_state.get("demo_mode"):
            st.caption(
                "Project rename/save is a full Writer Edition feature. "
                "The current title remains visible during the trial."
            )
            return

        render_confirmed_project_rename(stage_key)
        render_save_open_project_to_series()


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

    try:
        manuscripts = (supabase.table("writersblock_manuscript_versions")
                       .select("id").eq("project_id", project_id)
                       .eq("user_id", user_id).limit(1).execute())
        if getattr(manuscripts, "data", None):
            return False, "This project has saved manuscript versions; existing work was protected."
        draft_rows = (supabase.table("writersblock_project_drafts")
                      .select("id,draft_type,draft_content").eq("project_id", project_id)
                      .eq("user_id", user_id).limit(101).execute())
        rows = getattr(draft_rows, "data", None)
        if not isinstance(rows, list) or not rows or len(rows) >= 101:
            return False, "Saved project history is incomplete or too large to verify safely."
        found_active = False
        for row in rows:
            kind = str(row.get("draft_type") or "")
            if kind == "series_metadata":
                continue
            if kind != "project_session":
                return False, "This project has other saved writing stages; no paths were generated."
            if str(row.get("id") or "") == str(st.session_state.get("_wbs_active_saved_session_row_id")):
                found_active = True
            snap = json.loads(row.get("draft_content") or "{}")
            if not isinstance(snap, dict):
                return False, "The project history contains an invalid saved record."
            if (str(snap.get("current_project_id") or project_id) != project_id
                    or str(snap.get("active_format_id") or "") != format_id
                    or str(snap.get("project_stage") or "Intake") != "Intake"
                    or has_downstream_content(snap)):
                return False, "An earlier saved version contains different or downstream work."
        if not found_active:
            return False, "The selected saved version is missing from this project's history."
    except (ValueError, TypeError, AttributeError, KeyError):
        return False, "Saved project history could not be checked safely. No work was changed."
    except Exception:
        return False, "Database history could not be verified. No paths were generated."
    return True, ""


def get_user_by_email(email: str):
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return None

    result = (
        supabase.table("writersblock_users")
        .select("*")
        .eq("email", clean_email)
        .limit(1)
        .execute()
    )
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def start_or_resume_trial(email: str):
    clean_email = (email or "").strip().lower()
    if not clean_email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
        return None, "Enter a valid email address."

    existing = get_user_by_email(clean_email)
    if is_evaluation_account(existing):
        return None, "This email is reserved for a private evaluation; use Licensed User Email when activated."
    now = datetime.now(timezone.utc)

    if existing:
        expires_at = existing.get("demo_expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except Exception:
                expires_dt = None

            if expires_dt and now > expires_dt:
                return None, "This email has already used its 7-Day Limited Free Trial."

            if expires_dt:
                if not existing.get("demo_active", True):
                    supabase.table("writersblock_users").update({
                        "demo_active": True
                    }).eq("id", existing.get("id")).execute()
                    existing["demo_active"] = True
                return existing, ""

        expires_dt = now + timedelta(days=TRIAL_DAYS)
        update_result = (
            supabase.table("writersblock_users")
            .update({
                "demo_active": True,
                "demo_expires_at": expires_dt.isoformat(),
            })
            .eq("id", existing.get("id"))
            .execute()
        )
        row = update_result.data[0] if update_result.data else existing
        row["demo_active"] = True
        row["demo_expires_at"] = expires_dt.isoformat()
        return row, ""

    expires_dt = now + timedelta(days=TRIAL_DAYS)
    try:
        insert_result = (
            supabase.table("writersblock_users")
            .insert({
                "email": clean_email,
                "email_verified": False,
                "is_active": False,
                "demo_active": True,
                "demo_expires_at": expires_dt.isoformat(),
            })
            .execute()
        )
    except Exception as exc:
        return None, f"Trial registration could not be created: {exc}"

    if insert_result.data:
        return insert_result.data[0], ""

    return None, "Trial registration could not be created."


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
        access_mode = st.radio(
            "Access Type",
            ["7-Day Limited Free Trial", "Licensed User Email"],
            key="access_mode",
        )

        if access_mode == "7-Day Limited Free Trial":
            trial_email_input = st.text_input(
                "Email for 7-Day Limited Free Trial",
                key="trial_email_input",
                placeholder="you@example.com",
            )
            st.caption(
                "Trial includes the complete writing path from Concept Development through "
                "Manuscript Review. Manuscript Printout, Saved Projects, and Saved Versions are full-version features."
            )

            if st.button("Start / Resume 7-Day Trial", key="activate_demo_access", use_container_width=True):
                email = trial_email_input.strip().lower()
                user_row, msg = start_or_resume_trial(email)

                if user_row:
                    track_affitor_lead(user_row, email)
                    st.session_state.demo_access_code = ""
                    st.session_state.demo_email = email
                    st.session_state.demo_user_row = user_row
                    st.session_state.demo_mode = True
                    st.session_state.licensed_mode = False
                    st.session_state.licensed_user_row = None
                    st.session_state.licensed_email = ""
                    st.session_state.access_success_message = "7-Day Limited Free Trial activated."
                    st.rerun()
                else:
                    st.error(msg)

        else:
            licensed_email_input = st.text_input(
                "Email Used for Writer Edition Purchase",
                key="licensed_email_input",
            )

            if st.button("Activate License", key="activate_license_access", use_container_width=True):
                email = licensed_email_input.strip().lower()
                user_row = get_licensed_user_by_email(email)
                ok, msg = is_license_access_valid(user_row)

                if ok:
                    track_affitor_lead(user_row, email)
                    st.session_state.licensed_user_row = user_row
                    st.session_state.licensed_mode = True
                    st.session_state.demo_mode = False
                    st.session_state.demo_access_code = ""
                    st.session_state.demo_email = ""
                    st.session_state.demo_user_row = None
                    st.session_state.licensed_email = email
                    st.session_state.access_success_message = "Writer Edition license activated."
                    st.rerun()
                else:
                    st.error(msg)

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

    st.write(f"Current Project: {get_project_title_for_display()}")

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
    _working_text = ""
    _stage_name = str(st.session_state.get("project_stage") or "").lower()
    if _stage_name in ("plot architect", "plot architecture"):
        _working_text = str(st.session_state.get("_wbs_stage3_clean_editor") or "").strip()
        if not _working_text:
            _raw_outline = str(st.session_state.get("plot_outline") or "")
            _working_text = " ".join(re.findall(
                r"(?ims)^\s*\[SCENE DETAILS[^\]]*\]\s*:\s*(.*?)(?=^\s*\[[A-Z][^\n]*\]|^\s*===|\Z)",
                _raw_outline))
    if not _working_text and st.session_state.get("current_draft_output"):
        _working_text = str(st.session_state.get("current_draft_output") or "")
    if not _working_text and st.session_state.get("chosen_option_text"):
        _working_text = str(st.session_state.get("chosen_option_text") or "")
    if not _working_text:
        _working_text = str(st.session_state.get("wbs_project_original_concept") or st.session_state.get("story_seed") or "")
    st.write(f"Current Version: V-{_active_version_number}" if _active_version_number else "Current Version: Unsaved")
    st.write(f"Current Working Words: {count_words(_working_text):,}")

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
_WBS_STAGE_TITLES = {
    "Intake": "1. Concept Development", "Sandbox": "2. Scripting",
    "Plot Architect": "3. Plot Architecture", "Drafting Engine": "4. Creative Draft",
    "Revision Engine": "6. Script Polish", "Rewrite Engine": "7. Script Rewrite",
}

def wbs_stage_title(stage, export_view=False):
    if stage == "Isolation Guardrail":
        return "8. Final Output" if export_view else "5. Script Lock"
    return _WBS_STAGE_TITLES.get(stage, str(stage))

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


def wbs_request_stage_change(destination, export_view=None):
    """Go directly to the requested writing stage; never display a second save gate.

    Project saving is a master-first action; later edits create new versions.
    """
    current = st.session_state.get("project_stage", "Intake")
    current_export = bool(st.session_state.get("export_view", False))
    target_export = current_export if export_view is None else bool(export_view)
    if current == destination and (destination != "Isolation Guardrail" or current_export == target_export):
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
    if target == "Isolation Guardrail":
        st.session_state.export_view = bool(pending["export_view"])
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
    if str(state.get("current_manuscript_save_status") or "").upper() == "FINAL":
        level = max(level, 5)
    elif str(state.get("saved_version_source_text") or "").strip():
        level = max(level, 4)
    return min(level, 5)

_wbs_unlocked = wbs_reached_review_level(st.session_state)
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
    st.sidebar.button("🔵 1. Concept Development (Active)", key="nav_intake_active", use_container_width=True)
else:
    if st.sidebar.button("⚪ 1. Concept Development", key="nav_intake", use_container_width=True):
        wbs_request_stage_change("Intake")

if st.session_state.project_stage == "Sandbox":
    st.sidebar.button("🔵 2. Scripting (Active)", key="nav_sandbox_active", use_container_width=True)
elif can_navigate_to_sandbox:
    if st.sidebar.button("⚪ 2. Scripting", key="nav_sandbox", use_container_width=True):
        wbs_request_stage_change("Sandbox")
else:
    st.sidebar.button("🔒 2. Scripting (Locked)", key="nav_sandbox_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Plot Architect":
    st.sidebar.button("🔵 3. Plot Architecture (Active)", key="nav_plot_active", use_container_width=True)
elif can_navigate_to_plot:
    if st.sidebar.button("⚪ 3. Plot Architecture", key="nav_plot", use_container_width=True):
        wbs_request_stage_change("Plot Architect")
else:
    st.sidebar.button("🔒 3. Plot Architecture (Locked)", key="nav_plot_locked", disabled=True, use_container_width=True)

# Five-stage navigation: drafting runs internally; editing tools share Stage 4.
# Legacy internal stages remain loadable for earlier saved projects.
if st.session_state.project_stage == "Drafting Engine":
    st.sidebar.info("🔵 4. Editorial & Publisher Review — Generating the approved manuscript…")

_is_draft_review = (st.session_state.project_stage in {"Isolation Guardrail", "Revision Engine", "Rewrite Engine"}
                    and not (st.session_state.project_stage == "Isolation Guardrail" and st.session_state.get("export_view", False)))
if _is_draft_review:
    st.sidebar.button("🔵 4. Editorial & Publisher Review (Active)", key="nav_guard_active", use_container_width=True)
elif can_navigate_to_guardrail:
    if st.sidebar.button("⚪ 4. Editorial & Publisher Review", key="nav_guard", use_container_width=True):
        wbs_request_stage_change("Isolation Guardrail", export_view=False)
else:
    st.sidebar.button("🔒 4. Editorial & Publisher Review (Locked)", key="nav_guard_locked", disabled=True, use_container_width=True)

stage_8_label = "Manuscript Review" if st.session_state.get("demo_mode") else "Final Manuscript"
if st.session_state.project_stage == "Isolation Guardrail" and st.session_state.get("export_view", False):
    st.sidebar.button(f"🔵 5. {stage_8_label} (Active)", key="nav_export_active", use_container_width=True)
elif _wbs_unlocked >= 5:
    if st.sidebar.button(f"⚪ 5. {stage_8_label}", key="nav_export", use_container_width=True):
        wbs_request_stage_change("Isolation Guardrail", export_view=True)
else:
    st.sidebar.button(f"🔒 5. {stage_8_label} (Locked)", key="nav_export_locked", disabled=True, use_container_width=True)

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


if st.session_state.project_stage == "Intake":
    st.markdown(
        """
        <style>
        /* Keep Quill inside its actual right column so every middle-panel field
           is physically constrained and can never run underneath it. */
        div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),
        div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {
            position: sticky !important;
            top: 0.75rem !important;
            align-self: flex-start !important;
            max-height: calc(100vh - 1.5rem) !important;
            overflow-y: auto !important;
            z-index: 20 !important;
            background: var(--background-color, transparent);
        }

        /* Primary Writer navigation and format-selector hierarchy. */
        [data-testid="stMain"] div[data-testid="stHorizontalBlock"]:first-of-type button p {
            font-weight: 700 !important;
            font-size: 1.02rem !important;
        }
        .wbs-format-selector-title {
            font-size: 1.08rem !important;
            font-weight: 700 !important;
            line-height: 1.2 !important;
            margin: 0 0 0.35rem 0 !important;
        }

        /* Raise the complete Writer workspace to recover vertical real estate. */
        [data-testid="stMainBlockContainer"] {
            padding-top: 1.0rem !important;
        }

        @media (max-width: 1100px) {
            div[data-testid="stColumn"]:has(.wbs-writer-quill-sticky-anchor),
            div[data-testid="column"]:has(.wbs-writer-quill-sticky-anchor) {
                position: static !important;
                max-height: none !important;
                overflow: visible !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    writer_main_col, writer_quill_col = st.columns([2.65, 1.15], gap="large")

    with writer_main_col:
        st.header("🗺️ Step 1: Concept Development")

        current_format_id = str(
            st.session_state.get("active_format_id") or "novel_prose_novella"
        )
        if current_format_id not in WBS_FORMAT_IDS:
            current_format_id = "novel_prose_novella"

        st.markdown(f"### Writing Format — {get_wbs_format_display_name(current_format_id)}")

        # Initialize the dropdown only when the widget has no saved value.
        # Streamlit updates its keyed value BEFORE rerunning the script when a writer
        # selects another format. Resetting it on every rerun silently undoes the click.
        # Saved-project loading explicitly restores this key from its validated format.
        if "wbs_format_template_selector" not in st.session_state:
            st.session_state["wbs_format_template_selector"] = current_format_id

        _format_control_col, _format_spacer_col = st.columns([1.6, 1.25], gap="small")
        with _format_control_col:
            if get_active_project_id():
                st.markdown(f"**{get_wbs_format_display_name(current_format_id)}**")
                selected_format_id = current_format_id
            else:
                selected_format_id = st.selectbox(
                    "Choose Writing Format",
                    options=WBS_FORMAT_IDS,
                    index=WBS_FORMAT_IDS.index(current_format_id),
                    format_func=get_wbs_format_display_name,
                    key="wbs_format_template_selector",
                    label_visibility="collapsed",
                )

        if selected_format_id != st.session_state.get("active_format_id") and get_active_project_id():
            st.session_state["wbs_format_template_selector"] = st.session_state.active_format_id
            st.warning("Saved project formats are protected. Start a new project to use a different writing format.")
            st.rerun()
        if selected_format_id != st.session_state.get("active_format_id"):
            st.session_state.active_format_id = selected_format_id
            st.session_state.active_format_template = get_wbs_format_template(selected_format_id)
            st.session_state.quill_format_instructions = get_wbs_quill_instructions(selected_format_id)
            st.session_state.quill_format_name = get_wbs_format_display_name(selected_format_id)
            st.session_state.format_type = WBS_LEGACY_FORMAT_BY_TEMPLATE_ID.get(
                selected_format_id,
                "Novel / Prose",
            )
            st.rerun()

        concept_ui = get_active_concept_ui()
        st.markdown(f"##### {concept_ui.get('step_subtitle') or 'Build the foundation for your project.'}")

        # Every format names this field PROJECT TITLE, never a saved version.
        # Format-specific title wording stays in the registry for other consumers.
        _format_title_prefix = next(
            (name for format_id, name in WBS_FORMAT_OPTIONS
             if format_id == st.session_state.get("active_format_id")),
            "Project",
        )
        _project_title_label = f"{_format_title_prefix} / Project Title/Revision"

        if get_active_project_id():
            st.caption("Loaded saved project — saved Concept Development choices are restored where recorded.")
            if st.session_state.get("_wbs_saved_concept_missing_fields"):
                # Older saved projects may not contain every newer template
                # field. Preserve that audit fact without displaying the same
                # alarming yellow warning on every Streamlit rerun.
                with st.expander("Historical Development Setup details", expanded=False):
                    st.caption(
                        "Some settings were not included in this saved project's "
                        "historical records. Those fields show current template "
                        "defaults, not verified original choices. Loading is read-only."
                    )
            if st.session_state.get("_wbs_series_conflict_for_review"):
                st.caption("Historical series positions differed. Current Book order is managed separately "
                           "in Series Library; saved stories were not changed.")
            elif st.session_state.get("_wbs_series_recovered_for_review"):
                st.info("Series relationship recovered from this project's saved records; "
                        "no changes were written to the database.")

            # This is a saved project's MASTER title, never an editable concept
            # field. The writer can change it only with the separate Rename
            # Project action. Do not feed a stale widget value back into state:
            # doing so changed "Return To Sender" to the previous project title
            # while leaving its manuscript/project ID untouched.
            _active_title_project_id = str(get_active_project_id() or "")
            _title_anchor = (
                str(st.session_state.get("_wbs_loaded_project_title") or "").strip()
                if str(st.session_state.get("_wbs_loaded_project_id") or "")
                == _active_title_project_id else ""
            )
            if _title_anchor and st.session_state.get("project_title") != _title_anchor:
                st.session_state.project_title = _title_anchor
            _display_master_title = _title_anchor or get_project_title()
            # Show the exact active saved revision alongside the master title.
            # Never change the master project title stored in Supabase.
            if True:  # Shared project/revision display across all formats.
                _active_saved_row_id = str(st.session_state.get("_wbs_loaded_saved_session_id") or "")
                _active_manuscript_row_id = str(st.session_state.get("_wbs_loaded_manuscript_version_id") or "")
                _active_project_key = str(get_active_project_id() or "")
                for _saved_entry in get_saved_projects_versions_dropdown_items():
                    _saved_row = _saved_entry.get("row") or {}
                    if str(_saved_row.get("project_id") or "") != _active_project_key:
                        continue
                    _is_active = (
                        (_saved_entry.get("type") == "project_session"
                         and _active_saved_row_id and str(_saved_row.get("id") or "") == _active_saved_row_id)
                        or (_saved_entry.get("type") == "manuscript_version"
                            and _active_manuscript_row_id and str(_saved_row.get("id") or "") == _active_manuscript_row_id)
                    )
                    if _is_active:
                        _version_match = re.search(r" — (V-\d+[A-Z]*) — ", str(_saved_entry.get("label") or ""))
                        if _version_match:
                            _display_master_title += " — " + _version_match.group(1)
                        break
            st.markdown(f"**{_project_title_label}**")
            st.markdown(
                '<div style="background:#262730;color:#ffffff;padding:0.65rem 0.8rem;'
                'border:1px solid #41444f;border-radius:0.45rem;min-height:2.4rem;">'
                + html.escape(_display_master_title) + '</div>',
                unsafe_allow_html=True,
            )
            # Rename is available only in the Start New Project workflow.
            render_save_open_project_to_series()
        else:
            st.session_state.project_title = st.text_input(
                _project_title_label,
                value=st.session_state.get("project_title", ""),
                placeholder="Example: It's Not Safe",
                key="project_title_input",
            ).strip()

        st.markdown("### " + str(concept_ui.get('project_connection_heading') or 'Project Relationship'))

        # Simple series membership. No bulk assignment, book-order UI, or manuscript writes.
        # The Project Type selection is a proposal for saved projects; it takes
        # effect ONLY after explicit confirmation (metadata-only). For a new
        # project the original master-save flow still creates the series link.
        project_scope_options = ["Standalone Book", "Book in a Series"]
        current_project_id = str(get_active_project_id() or "")
        membership = get_series_metadata_by_project() if get_current_user_id() else {}
        current_member = membership.get(current_project_id) or {}
        registered_series = str(current_member.get("series_name") or "").strip()
        saved_scope = "Book in a Series" if registered_series else "Standalone Book"
        selected_scope_default = (saved_scope if current_project_id else
                                  str(st.session_state.get("project_scope") or "Standalone Book"))
        context = f"{current_project_id or 'new'}:{registered_series}"
        # A project load resets the controls once. A normal Streamlit rerun must
        # not erase the writer's proposed selection or checkbox state.
        if st.session_state.get("_wbs_simple_series_context") != context:
            st.session_state["_wbs_simple_series_context"] = context
            st.session_state["project_scope_selector"] = selected_scope_default
            st.session_state["wbs_confirm_series_link"] = False
            st.session_state["wbs_confirm_series_removal"] = False
            st.session_state.pop("wbs_simple_series_choice", None)
            st.session_state.pop("wbs_simple_series_new_name", None)

        project_scope_labels = concept_ui.get("scope_labels") or {}
        chosen_scope = st.radio(
                "Project Type:", project_scope_options, horizontal=True,
                key="project_scope_selector",
                format_func=lambda v: project_scope_labels.get(v, v),
            )
        # For existing projects the recorded membership is authoritative even
        # when the user previews the other radio button. This protects version
        # saves, navigation, and Quill continuity from unsaved changes.
        if current_project_id:
            st.session_state.project_scope = saved_scope
            st.session_state.series_name = registered_series
            st.session_state.series_key = make_series_key(registered_series)
            if registered_series:
                st.session_state.series_book_number = int(current_member.get("series_book_number") or 1)
        else:
            st.session_state.project_scope = chosen_scope

        if chosen_scope == "Book in a Series":
            known_series = get_existing_series_names()
            choice_options = list(known_series) + ["Create New Series"]
            existing_name = (registered_series if current_project_id else
                             str(st.session_state.get("series_name") or "").strip())
            if "wbs_simple_series_choice" not in st.session_state:
                st.session_state["wbs_simple_series_choice"] = (
                    existing_name if existing_name in known_series else "Create New Series")
            with st.columns([1, 1], gap="small")[0]:
                selected_choice = st.selectbox(
                    "Select Series:", choice_options, key="wbs_simple_series_choice")
                if selected_choice == "Create New Series":
                    selected_series = st.text_input(
                        "New Series Name:", key="wbs_simple_series_new_name",
                        max_chars=80).strip()
                else:
                    selected_series = selected_choice
            if not current_project_id:
                # Initial master project save has always included its series
                # metadata; retain that behavior, without making a new version.
                st.session_state.series_name = selected_series
                st.session_state.series_key = make_series_key(selected_series)
                st.session_state.series_continuity_mode = "Strict"
                if selected_series:
                    st.session_state.series_book_number = get_next_series_book_number(selected_series)
                    st.caption("This new project will join the selected series when you save its master project.")
                else:
                    st.caption("Enter a series name before saving the project.")
            else:
                # Saved projects are changed ONLY with the version-aware action
                # directly below Rename Project, never from an unconfirmed radio.
                pass
        elif not current_project_id:
            st.session_state.series_name = ""
            st.session_state.series_key = ""
        else:
            st.session_state.series_name = ""
            st.session_state.series_key = ""

        # Automatic series continuity still uses confirmed earlier projects.
        if st.session_state.project_scope == "Book in a Series" and st.session_state.get("series_name"):
            st.session_state.series_continuity_mode = "Strict"
            candidates = get_series_reference_candidates()
            project_ids = get_unambiguous_series_project_ids(
                st.session_state.series_key,
                before_number=st.session_state.get("series_book_number") or 1)
            st.session_state.series_reference_ids = [
                c["id"] for c in candidates if str(c.get("project_id")) in project_ids]
            st.session_state.series_selection_signature = (
                f"{st.session_state.series_key}:{st.session_state.get('series_book_number') or 1}")
        else:
            st.session_state.series_reference_ids = []

        # Render the selected format's independent development fields.
        # Common WritersBlock controls (title, source/premise, dialogue style) remain shared.
        render_active_format_development_fields()

        # The project format is selected once from the Format Template dropdown
        # beneath the WritersBlock header. Do not ask for the same format twice.

        if st.session_state.format_type == "Audio Book":
            previous_length = st.session_state.get("audiobook_length", "30 Minutes")
            audiobook_lengths = list(AUDIOBOOK_LENGTH_OPTIONS.keys())

            _audio_length_col, _audio_length_spacer = st.columns([3.0, 1.2])
            with _audio_length_col:
                selected_audiobook_length = st.selectbox(
                    "Approximate Finished Audio Book Length:",
                    audiobook_lengths,
                    index=(
                        audiobook_lengths.index(previous_length)
                        if previous_length in audiobook_lengths
                        else audiobook_lengths.index("30 Minutes")
                    ),
                    key="audiobook_length_selector",
                )

            st.session_state.audiobook_length = selected_audiobook_length
            audiobook_spec = AUDIOBOOK_LENGTH_OPTIONS[selected_audiobook_length]

            existing_target = int(
                st.session_state.get(
                    "audiobook_target_word_count",
                    audiobook_spec["default_words"],
                )
            )

            if (
                selected_audiobook_length != previous_length
                or existing_target < audiobook_spec["min_words"]
                or existing_target > audiobook_spec["max_words"]
            ):
                existing_target = audiobook_spec["default_words"]

            audiobook_target_words = st.number_input(
                "Target Total Manuscript Word Count:",
                min_value=audiobook_spec["min_words"],
                max_value=audiobook_spec["max_words"],
                value=existing_target,
                step=50,
                key=f"audiobook_target_words_{selected_audiobook_length}",
            )

            st.session_state.audiobook_target_word_count = int(audiobook_target_words)

            st.info(
                f"Recommended range for {selected_audiobook_length.lower()}: "
                f"{audiobook_spec['min_words']:,}–{audiobook_spec['max_words']:,} words. "
                f"WritersBlock will use the selected {int(audiobook_target_words):,}-word target "
                f"when building the outline and distributing scene lengths."
            )

        dialogue_style_options = DIALOGUE_STYLE_OPTIONS
        current_dialogue_style = get_dialogue_style()
        _podcast_episode_format = str(
            get_active_format_template_values().get("episode_format") or ""
        )
        _show_dialogue_control = not (
            st.session_state.get("active_format_id") == "podcast_script"
            and _podcast_episode_format not in {"Scripted / Narrated", "Hybrid"}
        )

        if _show_dialogue_control:
            _dialogue_col, _dialogue_spacer = st.columns([3.0, 1.2])
            with _dialogue_col:
                st.session_state.dialogue_style = st.selectbox(
                    concept_ui.get("dialogue_label") or "Dialogue Style:",
                    dialogue_style_options,
                    index=dialogue_style_options.index(current_dialogue_style),
                    key="dialogue_style_selector",
                    format_func=get_dialogue_style_display,
                    help=(
                        "Percentages are approximate targets for the share of finished words that are spoken dialogue. "
                        "Story-Driven / Automatic has no fixed percentage. The selected project type still controls "
                        "how dialogue is formatted."
                    ),
                )
        elif st.session_state.get("active_format_id") == "podcast_script":
            # Live/conversational/interview formats are guided by talking points and segment structure,
            # not an artificial dialogue percentage.
            st.session_state.dialogue_style = "Story-Driven / Automatic"


        # Format-specific tone, source intake, and style controls are supplied by
        # the active template so the lower half of Concept Development is no
        # longer a generic story form.
        tone_options = list(concept_ui.get("tone_options") or [
            "Professional", "Warm", "Serious", "Humorous", "Suspenseful", "Cinematic"
        ])
        tone_label = str(concept_ui.get("tone_label") or "Tone / Aesthetic:")
        current_tone = str(st.session_state.get("tone_style") or "")
        default_tone_index = tone_options.index(current_tone) if current_tone in tone_options else 0

        _tone_col, _tone_spacer = st.columns([3.0, 1.2])
        with _tone_col:
            st.session_state.tone_style = st.selectbox(
                tone_label,
                tone_options,
                index=default_tone_index,
                key=f"tone_style_{st.session_state.active_format_id}",
            )

        st.markdown("---")
        st.markdown(f"### {concept_ui.get('source_heading') or 'Choose a Starting Point'}")

        current_saved_option = "-- Use Current Saved Manuscript / Storyline --"
        custom_plot_option = str(
            concept_ui.get("custom_option") or "-- Enter Your Own Story / Premise --"
        )
        quill_start_option = "-- Quill-Assisted Starting Point --"
        replacement_draft_option = "-- Upload / Replace with Different Draft / Manuscript --"

        # All four choices remain available. The selected source becomes the
        # authoritative input for the new named version.
        seed_options = [
            current_saved_option,
            custom_plot_option,
            quill_start_option,
            replacement_draft_option,
        ]

        current_seed = str(st.session_state.get("story_seed") or "")
        current_source_mode = str(
            st.session_state.get("version_source_mode")
            or st.session_state.get("starting_source_mode")
            or "Custom Plot Line"
        )

        if current_source_mode == "Saved Manuscript":
            default_seed_index = seed_options.index(current_saved_option)
        elif current_source_mode in {"Replacement Draft / Manuscript", "Existing Draft / Manuscript"}:
            default_seed_index = seed_options.index(replacement_draft_option)
        elif current_source_mode == "Quill Assisted":
            default_seed_index = seed_options.index(quill_start_option)
        else:
            default_seed_index = seed_options.index(custom_plot_option)

        saved_version_source_text = str(
            st.session_state.get("saved_version_source_text") or ""
        ).strip()
        if saved_version_source_text:
            saved_source_name = str(
                st.session_state.get("saved_version_source_name")
                or get_current_project_version_name()
                or "Saved Version"
            ).strip()
            st.info(
                f"Saved Version Source: {saved_source_name} — "
                f"{count_words(saved_version_source_text):,} words. "
                "This manuscript is retained and can be selected as the transformation source."
            )

        selected_seed = st.radio(
            str(concept_ui.get("source_label") or "Starting Source:"),
            seed_options,
            index=default_seed_index,
            key=f"starting_source_{st.session_state.active_format_id}",
        )

        if selected_seed == current_saved_option:
            st.session_state.version_source_mode = "Saved Manuscript"
            st.session_state.starting_source_mode = "Saved Manuscript"

            saved_source = str(
                st.session_state.get("saved_version_source_text") or ""
            ).strip()
            if saved_source:
                st.success(
                    f"Using Current Saved Manuscript / Storyline — "
                    f"{count_words(saved_source):,} words"
                )
                st.caption(
                    "The loaded manuscript remains the story source. Any Concept Development "
                    "changes above will be used to transform it into the new version."
                )
                # WBS_20261023_EDITABLE_SAVED_SOURCE — writer-approved changes only.
                # Keep the loaded original intact until a new version is explicitly saved.
                _src_id = get_text_signature(saved_source)[:12]
                _edit_key = f"wbs_saved_source_edit_{st.session_state.active_format_id}_{_src_id}"
                st.markdown("**Editable Saved Manuscript — paste Quill's revised text here:**")
                _revised_source = st.text_area(
                    "Editable Saved Manuscript:",
                    value=saved_source,
                    height=330,
                    key=_edit_key,
                    label_visibility="collapsed",
                )
                st.caption("Edit or paste a revision. The original remains unchanged until you save a NEW version.")
                if st.button("💾 Save Edited Manuscript As New Version", key=f"wbs_save_edited_source_{_src_id}",
                             type="primary", use_container_width=True,
                             disabled=bool(st.session_state.get("demo_mode"))):
                    if not _revised_source.strip():
                        st.error("The manuscript cannot be empty.")
                    elif _revised_source == saved_source:
                        st.info("No text changes to save.")
                    else:
                        _prev_source = saved_source
                        _prev_draft = st.session_state.get("current_draft_output", "")
                        _prev_name = st.session_state.get("project_version_name", "Original")
                        _new_name = f"Edited {datetime.now():%m-%d %H%M}"
                        st.session_state.saved_version_source_text = _revised_source
                        st.session_state.saved_version_source_word_count = count_words(_revised_source)
                        st.session_state.saved_version_source_name = _new_name
                        st.session_state.current_draft_output = _revised_source
                        st.session_state.project_version_name = _new_name
                        try:
                            _save_result = save_current_project_session_to_supabase(
                                version_name=_new_name, save_as_new_version=True)
                            if not _save_result:
                                raise RuntimeError("Database did not confirm the save")
                        except Exception as _exc:
                            st.session_state.saved_version_source_text = _prev_source
                            st.session_state.saved_version_source_word_count = count_words(_prev_source)
                            st.session_state.current_draft_output = _prev_draft
                            st.session_state.project_version_name = _prev_name
                            st.error(f"Save failed; original restored: {_exc}")
                        else:
                            st.success("New editable manuscript version saved. The original is preserved.")
                            st.rerun()
            else:
                st.warning(
                    "No saved manuscript is loaded. Choose another starting source or load a saved version first."
                )

        elif selected_seed == custom_plot_option:
            st.session_state.version_source_mode = "Custom Plot Line"
            st.session_state.starting_source_mode = "Custom Plot Line"
            custom_value = str(
                st.session_state.get("story_seed")
                or st.session_state.get("wbs_project_original_concept")
                or ""
            )
            st.session_state.story_seed = st.text_area(
                str(concept_ui.get("custom_label") or "Enter Your Project Premise:"),
                value=custom_value,
                height=170,
                key=f"custom_plot_line_input_{st.session_state.active_format_id}",
                placeholder=(
                    "Describe what you want to create in your own words. Quill will use this concept/brief, together with the selected template, to guide development."
                ),
            )
            custom_word_count = count_words(st.session_state.story_seed)
            st.caption(f"{custom_word_count:,} / 1,000 words")
            if custom_word_count > 1000:
                st.warning("This entry exceeds the 1,000-word Concept Development limit.")

        elif selected_seed == quill_start_option:
            st.session_state.version_source_mode = "Quill Assisted"
            st.session_state.starting_source_mode = "Quill Assisted"
            format_name = str(
                (st.session_state.get("active_format_template") or {}).get("display_name")
                or st.session_state.get("quill_format_name")
                or "Writing Project"
            )
            st.caption(
                f"Quill uses your {format_name} Development Setup above to propose a starting concept. "
                "You can edit it or request another suggestion before continuing."
            )
            # The development setup supplies the writer's theme and takeaway.
            # Only one editable concept box is shown below.
            st.session_state.quill_starting_direction = ""
            quill_key = f"wbs_quill_starting_concept_{st.session_state.active_format_id}"
            # Apply any revision generated by Quill chat before this widget exists.
            pending_key = f"_wbs_quill_pending_concept_{st.session_state.active_format_id}"
            pending_concept = st.session_state.pop(pending_key, None)
            if pending_concept is not None:
                st.session_state[quill_key] = str(pending_concept)
                st.session_state.story_seed = str(pending_concept)
            if quill_key not in st.session_state:
                # New Quill starting points must be blank until a generation button is used.
                # Saved Quill versions are explicitly seeded by the restore routine above.
                st.session_state[quill_key] = ""
            guided_col, original_col = st.columns(2, gap="small")
            with guided_col:
                guided_generation = st.button(
                    "Create Story From My Development Setup",
                    key=f"wbs_quill_generate_guided_{st.session_state.active_format_id}",
                    use_container_width=True,
                )
            with original_col:
                original_generation = st.button(
                    "Let Quill Suggest a Story",
                    key=f"wbs_quill_generate_original_{st.session_state.active_format_id}",
                    use_container_width=True,
                )
            if guided_generation or original_generation:
                require_product_access("sandbox")
                backend = st.session_state.get("backend")
                client = getattr(backend, "client", None)
                model_name = getattr(backend, "model_name", None)
                if client is None or not model_name:
                    st.error("Quill's writing service is unavailable. Please try again later.")
                else:
                    development_context = get_active_format_development_context()
                    creative_direction = (
                        "Build the story around the writer's specified theme, takeaway, and "
                        "creative instructions in Development Setup. Honor those choices closely."
                        if guided_generation else
                        "Invent a fresh, original storyline. Honor the format, age range, genre, "
                        "and required production constraints, but freely invent characters, conflict, "
                        "and events rather than relying on a writer-specified theme or takeaway."
                    )
                    prompt = (
                        "You are Quill, writing an original STORY CONCEPT that a writer can edit. "
                        f"Write 100–180 words for {format_name}. "
                        "Deliver a vivid, self-contained account of WHAT HAPPENS: name the protagonist, "
                        "establish the situation, show the inciting event, describe concrete choices and "
                        "consequences, and end with a plausible change or unresolved question. "
                        "Write paragraphs of story-facing prose, not a lesson, evaluation, outline, "
                        "creative brief, or discussion of theme. Keep it at concept/synopsis length, "
                        "not a finished manuscript. Respect relevant development requirements "
                        "without calling attention to these requirements. "
                        "NEVER use meta-commentary such as 'this story explores', 'the central idea', "
                        "'the narrative should', 'the story will', 'from a first-person perspective', "
                        "'the writer', or 'the reader'. Do not add a heading. "
                        "Begin immediately with the character or unfolding event.\n\n"
                        f"GENERATION DIRECTION: {creative_direction}\n\n"
                        f"DEVELOPMENT SETUP:\n{development_context}\n"
                        f"Tone: {st.session_state.get('tone_style', '')}\n"
                        f"Dialogue: {get_dialogue_style_display()}\n"
                        f"Format guidance: {st.session_state.get('quill_format_instructions', '')}"
                    )
                    try:
                        with st.spinner("Quill is preparing a starting concept..."):
                            suggestion = client.models.generate_content(model=model_name, contents=prompt)
                            concept = str(getattr(suggestion, "text", "") or "").strip()
                            # Never publish editorial planning text in the suggested-concept field.
                            # Ask the same model for a prose-only rewrite, preserving plot details.
                            if concept and wbs_concept_contains_editorial_commentary(concept):
                                rewrite_prompt = (
                                    "Rewrite the following draft as a STORY SYNOPSIS, not commentary "
                                    "about a story. Keep its protagonist, events, conflict, and outcome "
                                    "intact, but express them only as things that happen in the "
                                    "fictional world. Use 100–180 words of fluent prose. "
                                    "Remove references to themes, writing, narrative structure, "
                                    "the reader, genre, viewpoint, and any phrases beginning "
                                    "'this story', 'the central idea', or 'the narrative'. "
                                    "Return the revised synopsis only, without a heading.\n\n"
                                    f"DRAFT:\n{concept}"
                                )
                                rewritten = client.models.generate_content(
                                    model=model_name, contents=rewrite_prompt
                                )
                                concept = str(getattr(rewritten, "text", "") or "").strip()
                        if not concept or not ai_output_is_usable(concept) or wbs_concept_contains_editorial_commentary(concept):
                            st.error("Quill could not produce a clean story concept. Please try again.")
                        else:
                            st.session_state[quill_key] = concept
                            st.session_state.story_seed = concept
                            st.session_state.version_source_mode = "Quill Assisted"
                            st.session_state.starting_source_mode = "Quill Assisted"
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Quill could not generate a starting concept: {exc}")
            st.session_state.story_seed = st.text_area(
                "Saved / Suggested Story Concept — Edit Before Continuing:",
                key=quill_key,
                height=180,
                placeholder="Choose one of the two buttons above, then edit Quill's suggestion here.",
            )
            st.caption(f"{count_words(st.session_state.story_seed):,} / 1,000 words")
            if count_words(st.session_state.story_seed) > 1000:
                st.warning("Reduce the starting concept to 1,000 words or fewer.")

        elif selected_seed == replacement_draft_option:
            st.session_state.version_source_mode = "Replacement Draft / Manuscript"
            st.session_state.starting_source_mode = "Replacement Draft / Manuscript"
            st.warning("Large documents may result in higher API usage during processing.")

            st.markdown(
                """
                <style>
                [data-testid="stFileUploaderDropzoneInstructions"] {
                    display: none !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            uploaded_existing_draft = st.file_uploader(
                "Upload / Replace with Different Draft / Manuscript:",
                type=["docx", "txt"],
                key=f"concept_existing_draft_upload_{st.session_state.active_format_id}",
                help="Use a DOCX or TXT as the authoritative replacement source for this new version.",
            )
            st.caption("Maximum 120,000 words • DOCX, TXT")

            if uploaded_existing_draft is not None:
                try:
                    extracted_existing_draft = extract_uploaded_manuscript_text(uploaded_existing_draft)
                except Exception as source_error:
                    st.error(f"The document could not be read: {source_error}")
                    extracted_existing_draft = ""

                if extracted_existing_draft.strip():
                    extracted_word_count = count_words(extracted_existing_draft)
                    if extracted_word_count > 120000:
                        st.session_state.imported_source_text = ""
                        st.session_state.imported_source_name = ""
                        st.session_state.imported_source_word_count = 0
                        st.error(
                            f"Document contains {extracted_word_count:,} words. "
                            "WritersBlock accepts existing drafts up to 120,000 words."
                        )
                    else:
                        st.session_state.imported_source_text = extracted_existing_draft.strip()
                        st.session_state.imported_source_name = str(
                            getattr(uploaded_existing_draft, "name", "Existing Draft") or "Existing Draft"
                        )
                        st.session_state.imported_source_word_count = extracted_word_count
                        st.session_state.story_seed = st.session_state.imported_source_text

            imported_source_text = str(st.session_state.get("imported_source_text") or "").strip()
            imported_source_name = str(st.session_state.get("imported_source_name") or "").strip()
            if imported_source_text:
                st.success(
                    f"Replacement Source Loaded: {imported_source_name or 'Uploaded Document'} — "
                    f"{count_words(imported_source_text):,} words"
                )
                st.caption(
                    "This source is read-only in Concept Development. WritersBlock will use it as protected "
                    "starting material while the selected format and its development rules control the project."
                )
                st.text_area(
                    "Replacement Source — Read Only:",
                    value=imported_source_text,
                    height=320,
                    disabled=True,
                    key=f"concept_existing_draft_read_only_preview_{st.session_state.active_format_id}",
                )
            else:
                st.info("Upload a DOCX or TXT source to use it as the replacement starting material.")

        # Production influence is now selected at the top of each relevant
        # Development Setup instead of appearing as a late style-reference field.
        if st.session_state.get("active_format_id") == "podcast_script":
            st.session_state.author_style = ""

        # Shared Stage 1 checkpoint across all writing formats.
        _wbs_short_story_stage1 = True
        if not _wbs_short_story_stage1:
            render_format_template_save_reminder()
        else:
            st.markdown("---")
            _ss_save_col, _ss_continue_col = st.columns(2)
            with _ss_save_col:
                if st.button("SAVE CURRENT STAGE", key="short_story_save_stage_1", use_container_width=True, type="primary"):
                    _ss_result = save_current_project_session_to_supabase()
                    if _ss_result:
                        # Arm the development action only after this explicit save.
                        st.session_state["_wbs_stage1_continue_approval"] = (
                            str(get_active_project_id() or ""),
                            str(st.session_state.get("active_format_id") or ""),
                            str(st.session_state.get("_wbs_last_saved_work_signature") or ""),
                        )
                        st.success("Current stage saved; no duplicate version created when unchanged.")
                        st.rerun()
            with _ss_continue_col:
                _ss_master = wbs_has_saved_master()
                _ss_changed = wbs_work_has_changed() if _ss_master is True else True
                _ss_approval = st.session_state.get("_wbs_stage1_continue_approval")
                _ss_expected = (
                    str(get_active_project_id() or ""),
                    str(st.session_state.get("active_format_id") or ""),
                    str(st.session_state.get("_wbs_last_saved_work_signature") or ""),
                )
                _ss_can_continue = (
                    _ss_master is True and _ss_changed is False
                    and _ss_approval == _ss_expected
                )
                st.caption("CONTINUE TO NEXT STAGE: use the enabled development button below.")
            if not _ss_can_continue:
                st.caption("Save the current stage before proceeding.")

        # A loaded saved project may already contain its Scripting options.
        # Continue READ-ONLY: never regenerate its paths, reset its manuscript,
        # or create another writersblock_projects row under a new identity.
        _wbs_is_loaded_project = bool(get_active_project_id())
        _wbs_has_saved_paths = (
            _wbs_is_loaded_project
            and isinstance(st.session_state.get("sandbox_slates"), dict)
            and sandbox_output_is_usable(st.session_state.get("sandbox_slates"))
        )
        _wbs_paths_button_label = (
            "Continue to Scripting — Existing Paths"
            if _wbs_has_saved_paths
            else str(concept_ui.get("button_label") or "Develop Project Paths 🚀")
        )
        if st.button(
            _wbs_paths_button_label,
            key="generate_sandbox_paths",
            type="primary",
            use_container_width=True,
            disabled=(_wbs_short_story_stage1 and not _ss_can_continue),
        ):
            if _wbs_has_saved_paths:
                # Reuse only paths that match the currently saved snapshot.
                # In particular, after a failed write, keep the generated paths
                # in memory so the user can save them without another API call.
                if (wbs_has_saved_master() is not True
                        or wbs_work_has_changed() is not False):
                    st.error(
                        "These scripting paths or concept changes are not yet saved. "
                        "Use 'Save Project Changes As A New Version' above, then "
                        "continue to Scripting. No AI regeneration is required."
                    )
                    st.stop()
                wbs_request_stage_change("Sandbox")
                st.stop()
            _wbs_create_saved_first_paths = False
            if _wbs_is_loaded_project:
                # Saved V-1 concept-only projects must not be trapped before
                # Scripting. Protect *all* existing versions and other stages.
                _wbs_create_saved_first_paths, _wbs_first_paths_error = (
                    wbs_can_generate_first_paths_for_saved_concept()
                )
                if not _wbs_create_saved_first_paths:
                    st.error(_wbs_first_paths_error)
                    st.stop()
                _audit = wbs_get_saved_concept_setup_audit()
                if not _audit.get("ok"):
                    st.error((_audit.get("message") or "Cannot verify saved setup.") +
                             " No AI generation was started.")
                    st.stop()
                if _audit.get("missing"):
                    st.error("This saved revision is missing Development Setup selections: "
                             + ", ".join(label for _, label in _audit["missing"][:12])
                             + ". The displayed template defaults are NOT proven "
                               "to be your original instructions. No AI generation "
                               "was started. Review the saved Setup audit.")
                    st.stop()
            require_product_access("sandbox")
            require_demo_action_available("sandbox")

            # Resolve and protect the writer-selected source before any downstream
            # draft/plot state is cleared.
            selected_source_mode = str(
                st.session_state.get("version_source_mode")
                or st.session_state.get("starting_source_mode")
                or "Custom Plot Line"
            )

            if selected_source_mode == "Saved Manuscript":
                selected_source_text = str(
                    st.session_state.get("saved_version_source_text") or ""
                ).strip()
                if not selected_source_text:
                    st.error(
                        "No current saved manuscript is available. Load a saved version "
                        "or choose another starting source."
                    )
                    st.stop()
                st.session_state.story_seed = selected_source_text

            elif selected_source_mode in {"Replacement Draft / Manuscript", "Existing Draft / Manuscript"}:
                selected_source_text = str(
                    st.session_state.get("imported_source_text") or ""
                ).strip()
                if not selected_source_text:
                    st.error(
                        "Please upload a DOCX or TXT replacement draft before developing this version."
                    )
                    st.stop()
                st.session_state.story_seed = selected_source_text

            elif selected_source_mode in {"Custom Plot Line", "Quill Assisted"}:
                selected_source_text = str(st.session_state.get("story_seed") or "").strip()
                if not selected_source_text:
                    st.error("Please enter or generate a starting point before continuing.")
                    st.stop()

            st.session_state.plot_outline = None
            st.session_state.current_draft_output = ""
            st.session_state.rewritten_manuscript = ""
            st.session_state.manuscript_text = ""
            st.session_state.current_processing_beat = 0
            st.session_state.total_beats = 0
            st.session_state.manuscript_version = 0
            st.session_state.picture_book_layout_spreads = []
            st.session_state.picture_book_layout_source_signature = ""
            st.session_state.picture_book_layout_preview_id = 0
            st.session_state.picture_book_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE

            if not get_project_title():
                st.error("Please name this project before continuing.")
                st.stop()


            if not st.session_state.get("wbs_project_original_concept"):
                st.session_state.wbs_project_original_concept = str(st.session_state.story_seed or "").strip()

            if not st.session_state.story_seed.strip():
                source_noun = str(concept_ui.get("source_noun") or "project premise")
                st.error(f"Please enter a {source_noun} or upload an existing source before continuing.")
                st.stop()

            if (
                st.session_state.get("version_source_mode") in {"Custom Plot Line", "Quill Assisted"}
                and count_words(st.session_state.story_seed) > 1000
            ):
                st.error("Please reduce the Concept Development entry to 1,000 words or fewer before continuing.")
                st.stop()

            with st.spinner(str(concept_ui.get("spinner") or "Developing project paths...")):
                time.sleep(1)

                if create_bridge_adapter is None:
                    st.error(
                        "WritersBlock Model is unavailable. "
                        f"{WBS_MODEL_IMPORT_ERROR}"
                    )
                    st.stop()

                _wbs_bridge_adapter = create_bridge_adapter(
                    backend=st.session_state.backend
                )
                _wbs_bridge_result = _wbs_bridge_adapter.execute(
                    "Generate sandbox paths",
                    st.session_state,
                    prepared_context={
                        "series_aware_story_seed": get_series_aware_story_seed(),
                        "scripting_format_context": get_scripting_format_context(),
                        "format_development_context": get_full_project_continuity_context(),
                        "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                        "quill_template_context": refresh_quill_template_context(),
                    },
                    action_payload={
                        "tone_style": st.session_state.tone_style,
                        "author_style": st.session_state.author_style,
                    },
                )

                if not _wbs_bridge_result.success:
                    st.error(
                        "WritersBlock Model Bridge could not generate the sandbox paths. "
                        + (_wbs_bridge_result.error or "Unknown bridge error.")
                    )
                    st.stop()

                st.session_state.sandbox_slates = _wbs_bridge_result.output
                st.session_state["_wbs_agent_bridge_last_operation"] = (
                    _wbs_bridge_result.backend_operation or ""
                )
                st.session_state["_wbs_agent_bridge_last_success"] = True

                if not sandbox_output_is_usable(st.session_state.sandbox_slates):
                    st.error("Quill did not return three usable paths. Nothing was saved.")
                    st.stop()
                mark_demo_action_used("sandbox")

                if _wbs_create_saved_first_paths:
                    # INSERT ONLY: V-1 remains intact, first generated paths
                    # are committed as the next saved project version (V-2).
                    first_paths_save = save_current_project_session_to_supabase(
                        version_name="First Scripting Paths", save_as_new_version=True,
                    )
                    if not first_paths_save or getattr(first_paths_save, "unchanged", False):
                        st.error(
                            "Generated paths remain in this session but were NOT saved. "
                            "Use 'Save Project Changes As A New Version' above to "
                            "retry the save without another AI generation."
                        )
                        st.stop()
                    st.session_state.project_saved_notice = True
                    wbs_request_stage_change("Sandbox")
                    st.stop()

                # A genuinely new project creates its parent only once.
                # NEVER replace current_project_id while editing saved work.
                if get_active_project_id():
                    st.error("Existing project detected. No new project was created or saved.")
                    st.stop()
                new_project_result = save_project_to_supabase(
                    project_title=get_project_title_for_display()[:80],
                    project_type=st.session_state.format_type,
                )
                if not new_project_result or not get_active_project_id():
                    st.error("New project creation could not be confirmed. Scripting was not opened.")
                    st.stop()

                if st.session_state.get("project_scope") == "Book in a Series":
                    save_series_metadata_for_project(
                        st.session_state.get("current_project_id")
                    )


                st.session_state.project_saved_notice = True
                wbs_request_stage_change("Sandbox")



    # ======================================
    # PHASE 2: SCRIPTING
    # ======================================

    with writer_quill_col:
        if st.session_state.get("licensed_mode") or st.session_state.get("demo_mode"):
            st.markdown(
                '<div class="wbs-writer-quill-sticky-anchor"></div>',
                unsafe_allow_html=True,
            )
            render_quill_for_current_stage(st_module=st, show_prelude=True)

elif st.session_state.project_stage == "Sandbox":
    st.header("🗺️ Step 2: Scripting")
    render_project_title_banner("step_2_scripting")
    st.markdown("##### Shape the first working script paths from your concept.")
    st.caption(
        f"Dialogue Style: {get_dialogue_style_display()} — inherited from Concept Development. "
        "Project type controls dialogue formatting."
    )
    st.markdown("---")

    if st.session_state.get("project_saved_notice"):
        st.session_state.project_saved_notice = False

    sandbox_slates = st.session_state.get("sandbox_slates", {})

    if not sandbox_slates:
        st.warning("No story paths are available yet. Return to Concept Development and generate story paths first.")
    else:
        if sandbox_slates.get("is_fallback", False):
            st.warning("AI connection issue detected. Temporary local story paths are being shown.")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Option A: Classic Structure")
            st.markdown("*A clear, traditional story path.*")
            st.info(sandbox_slates.get("Option A", ""))

            if st.button("Select Path A 🎯", key="btn_a", type="primary", use_container_width=True):
                require_product_access("plot")

                _wbs_same_saved_path = (
                    st.session_state.get("chosen_option") == "Option A: Classic Structure"
                    and st.session_state.get("chosen_option_text") == sandbox_slates.get("Option A", "")
                    and st.session_state.get("plot_outline") is not None
                )
                st.session_state.chosen_option = "Option A: Classic Structure"
                st.session_state.chosen_option_text = sandbox_slates.get("Option A", "")

                active_project_id = get_active_project_id()

                if active_project_id:
                    supabase.table("writersblock_project_drafts").insert({
                        "project_id": active_project_id,
                        "user_id": get_current_user_id(),
                        "draft_title": "Option A: Classic Structure",
                        "draft_type": "sandbox_option",
                        "draft_content": st.session_state.chosen_option_text,
                        "version_number": 1,
                    }).execute()

                if not _wbs_same_saved_path:
                    st.session_state.plot_outline = None
                wbs_request_stage_change("Plot Architect")

        with col2:
            st.subheader("Option B: Twisted Perspective")
            st.markdown("*A stranger version with a hidden truth or reversal.*")
            st.info(sandbox_slates.get("Option B", ""))

            if st.button("Select Path B 🎯", key="btn_b", type="primary", use_container_width=True):
                require_product_access("plot")

                _wbs_same_saved_path = (
                    st.session_state.get("chosen_option") == "Option B: Twisted Perspective"
                    and st.session_state.get("chosen_option_text") == sandbox_slates.get("Option B", "")
                    and st.session_state.get("plot_outline") is not None
                )
                st.session_state.chosen_option = "Option B: Twisted Perspective"
                st.session_state.chosen_option_text = sandbox_slates.get("Option B", "")

                active_project_id = get_active_project_id()

                if active_project_id:
                    supabase.table("writersblock_project_drafts").insert({
                        "project_id": active_project_id,
                        "user_id": get_current_user_id(),
                        "draft_title": "Option B: Twisted Perspective",
                        "draft_type": "sandbox_option",
                        "draft_content": st.session_state.chosen_option_text,
                        "version_number": 1,
                    }).execute()

                if not _wbs_same_saved_path:
                    st.session_state.plot_outline = None
                wbs_request_stage_change("Plot Architect")

        with col3:
            st.subheader("Option C: High-Impact Version")
            st.markdown("*A faster, more intense story path.*")
            st.info(sandbox_slates.get("Option C", ""))

            if st.button("Select Path C 🎯", key="btn_c", type="primary", use_container_width=True):
                require_product_access("plot")

                _wbs_same_saved_path = (
                    st.session_state.get("chosen_option") == "Option C: High-Impact Version"
                    and st.session_state.get("chosen_option_text") == sandbox_slates.get("Option C", "")
                    and st.session_state.get("plot_outline") is not None
                )
                st.session_state.chosen_option = "Option C: High-Impact Version"
                st.session_state.chosen_option_text = sandbox_slates.get("Option C", "")

                active_project_id = get_active_project_id()

                if active_project_id:
                    supabase.table("writersblock_project_drafts").insert({
                        "project_id": active_project_id,
                        "user_id": get_current_user_id(),
                        "draft_title": "Option C: High-Impact Version",
                        "draft_type": "sandbox_option",
                        "draft_content": st.session_state.chosen_option_text,
                        "version_number": 1,
                    }).execute()

                if not _wbs_same_saved_path:
                    st.session_state.plot_outline = None
                wbs_request_stage_change("Plot Architect")

# ==========================================
# PHASE 3: PLOT ARCHITECT ENGINE
# ==========================================
if st.session_state.project_stage == "Plot Architect":
    st.header("🏗️ Step 3: Plot Architecture")
    render_project_title_banner("step_3_plot_architecture")
    st.caption(
        f"Dialogue Style: {get_dialogue_style_display()} — carried forward from Concept Development. "
        "The selected project type controls dialogue formatting."
    )
    st.markdown(f"**Selected Direction:** `{st.session_state.chosen_option}`")
    st.markdown("---")

    # A selected Sandbox path starts plot generation immediately, without an extra click.
    # A loaded outline is displayed unchanged; never regenerate it automatically.
    if st.session_state.plot_outline is None:
        require_product_access("plot")
        require_demo_action_available("plot")

        with st.spinner("Locking down scene beats and style directives..."):
            time.sleep(1)

            if create_bridge_adapter is None:
                st.error(
                    "WritersBlock Model is unavailable. "
                    f"{WBS_MODEL_IMPORT_ERROR}"
                )
                st.stop()

            _wbs_plot_bridge = create_bridge_adapter(
                backend=st.session_state.backend
            )
            _wbs_plot_result = _wbs_plot_bridge.execute(
                "Generate plot outline",
                st.session_state,
                prepared_context={
                    "series_aware_story_seed": get_series_aware_story_seed(),
                    "effective_format_type": get_effective_format_type(),
                    "format_development_context": get_full_project_continuity_context(),
                    "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                    "quill_template_context": refresh_quill_template_context(),
                },
                action_payload={
                    "chosen_option": st.session_state.chosen_option,
                    "chosen_option_text": get_plot_dialogue_context(),
                    "tone_style": st.session_state.tone_style,
                    "author_style": st.session_state.author_style,
                },
            )

            if not _wbs_plot_result.success:
                st.error(
                    "WritersBlock Model Bridge could not generate Plot Architecture. "
                    + (_wbs_plot_result.error or "Unknown bridge error.")
                )
                st.stop()

            st.session_state.plot_outline = _wbs_plot_result.output
            # Newly generated outlines require their first save.
            st.session_state["_wbs_stage3_saved_outline_baseline"] = ""
            st.session_state["_wbs_stage3_unsaved_changes"] = True
            st.session_state["_wbs_agent_bridge_last_operation"] = (
                _wbs_plot_result.backend_operation or ""
            )
            st.session_state["_wbs_agent_bridge_last_success"] = True

            # WritersBlock Model state pin:
            # Plot generation belongs to Step 3. Preserve the current selection
            # and explicitly keep the app on Plot Architect before Streamlit reruns.
            st.session_state.project_stage = "Plot Architect"
            st.session_state.chosen_option = st.session_state.get("chosen_option")
            st.session_state.chosen_option_text = st.session_state.get("chosen_option_text")
            st.session_state["_wbs_agent_bridge_plot_stage_pinned"] = True

        if ai_output_is_usable(st.session_state.plot_outline):
            mark_demo_action_used("plot")
        if not ai_output_is_usable(st.session_state.get("plot_outline")):
            st.error("Plot generation did not produce a usable result. Return to Scripting and select a path again.")
            st.stop()

    # Stage 3 display guard: planning language can be embedded inside a SCENE
    # field (without a tag). Never display it as part of the reader's story.
    def _wbs_reader_scene_text(raw):
        raw = str(raw or "").strip()
        # Strip editorial/generation commentary only when a clause explicitly
        # discusses the scene, narration, directive or writer, not the action.
        raw = re.sub(
            r"(?is)(?:^|(?<=[.!?])\s+)(?:The scene (?:emphasizes|focuses on|is carried|will be|relies on|should|uses|highlights|establishes)|"
            r"Narration (?:carries|highlights|focuses|will|should|describes)|"
            r"The narration (?:carries|highlights|focuses|will|should|describes)|"
            r"This (?:beat|scene) (?:emphasizes|focuses|should|uses|is designed)|"
            r"(?:Use|Maintain|Employ|Apply|Analyze and apply) (?:active syntax|descriptive|style syntax|narration|dialogue)).*?(?:[.!?](?=\s|$)|$)",
            " ", raw,
        )
        return re.sub(r"[ \t]{2,}", " ", raw).strip()

    def _wbs_reader_outline_preview(raw):
        # Preserve source tags internally, but present only scene titles and
        # prose during review; all format controls still use the raw outline.
        beats = re.split(r"(?im)^\s*\[BEAT\s+\d+\]\s*", str(raw or ""))
        displayed = []
        for section in beats:
            title = re.search(r"(?is)\[SCENE TITLE\]\s*:\s*(.*?)(?=\[[A-Z][A-Z\s&0-9]*\]\s*:|$)", section)
            scene = re.search(r"(?is)\[(?:SCENE DETAILS(?:\s*&\s*CONFLICT)?|SCENE\s*\d*)\]\s*:\s*(.*?)(?=\[[A-Z][A-Z\s&0-9]*\]\s*:|$)", section)
            if scene:
                prose = _wbs_reader_scene_text(scene.group(1))
                if prose:
                    displayed.append(((title.group(1).strip() + "\n\n") if title else "") + prose)
        return "\n\n".join(displayed)

    # Single Stage 3 workspace: source on the left, editing / rewrite on the right.
    # The tagged outline remains authoritative for every writing format.
    _outline_now = str(st.session_state.get("plot_outline") or "").strip()
    _beat_pattern = r"(?im)^\s*\[BEAT\s+(\d+)\]"
    _beat_matches = list(re.finditer(_beat_pattern, _outline_now))
    _beat_sections = {}
    for _idx, _hit in enumerate(_beat_matches):
        _section_end = _beat_matches[_idx + 1].start() if _idx + 1 < len(_beat_matches) else len(_outline_now)
        _beat_sections[_hit.group(1)] = _outline_now[_hit.start():_section_end].strip()
    _beat_numbers = list(_beat_sections)
    _locations = [f"Scene Beat {_num}" for _num in _beat_numbers] + ["Full Storyline"]
    _source_col, _edit_col = st.columns([1.15, 1], gap="large")

    # Selection lives with the edit controls; only that beat is shown on the left.
    with _edit_col:
        st.subheader("Edit / Rewrite Storyline")
        _location = st.selectbox("Choose scene / beat to edit", _locations,
            key="_wbs_stage3_rewrite_location")
    _selected_number = re.search(r"\d+", _location).group() if _location != "Full Storyline" else ""
    _selected_outline = _beat_sections.get(_selected_number, "") if _selected_number else _outline_now
    _edit_signature = get_text_signature(_selected_outline) + "|" + _location
    if st.session_state.get("_wbs_stage3_edit_signature") != _edit_signature:
        st.session_state["_wbs_stage3_edit_source"] = _selected_outline
        st.session_state["_wbs_stage3_edit_signature"] = _edit_signature

    # The left workspace must show the active manuscript text when the
    # selected beat already has a drafted scene. Do not show an obsolete
    # plot-outline scene after the writer accepts a manuscript rewrite.
    _visible_blocks = st.session_state.get("scene_blocks") or {}
    _visible_beat = int(_selected_number) if _selected_number else None
    _visible_draft = (
        str(_visible_blocks.get(_visible_beat, _visible_blocks.get(str(_visible_beat), "")) or "").strip()
        if _visible_beat is not None and isinstance(_visible_blocks, dict)
        else ""
    )
    _visible_draft = _visible_draft if str(st.session_state.get("current_draft_output") or "").strip() else ""

    with _source_col:
        st.subheader(f"Beat {_selected_number} — Scene {_selected_number}" if _selected_number else "Full Storyline")
        if not _selected_outline:
            st.info("No scene content is available yet.")
        else:
            # Approved manuscript rewrites immediately appear in this left panel.
            if _visible_draft:
                st.caption("Current working manuscript scene")
                for _paragraph in re.split(r"\n\s*\n", _wbs_reader_scene_text(_visible_draft)):
                    if _paragraph.strip():
                        st.write(_paragraph.strip())
            # Otherwise display the outline's story text, never its directives.
            elif _selected_number:
                _title_match = re.search(r"\[SCENE TITLE\]\s*:\s*", _selected_outline, flags=re.I)
                _scene_match = re.search(
                    r"\[(?:SCENE DETAILS(?:\s*&\s*CONFLICT)?|SCENE\s*\d*)\]\s*:\s*",
                    _selected_outline, flags=re.I)
                _next_header = re.compile(r"\[(?:BEAT\s*\d+|SCENE TITLE|CORE OBJECTIVE|SCENE DETAILS(?:\s*&\s*CONFLICT)?|SCENE\s*\d*|THE\s+CONFLICT|STYLE\s*&\s*SYNTAX DIRECTIVE)\]", re.I)
                if _title_match:
                    _tail = _selected_outline[_title_match.end():]
                    _next = _next_header.search(_tail)
                    _title = _tail[:_next.start() if _next else len(_tail)].strip().strip("=").strip()
                    if _title:
                        st.markdown(f"**{_title}**")
                if _scene_match:
                    _tail = _selected_outline[_scene_match.end():]
                    _next = _next_header.search(_tail)
                    _scene_text = _wbs_reader_scene_text(_tail[:_next.start() if _next else len(_tail)].strip().strip("=").strip())
                    if _scene_text:
                        st.markdown("**Scene**")
                        for _paragraph in re.split(r"\n\s*\n", _scene_text):
                            if _paragraph.strip():
                                st.write(_paragraph.strip())
                elif not _title_match:
                    st.info("Scene text is unavailable for this beat.")
            else:
                st.caption("Select an individual beat to read its scene.")

    with _edit_col:
        st.markdown("#### Script Rewrite Controls")
        # Creative modes stay in the rewrite dropdown. Exact/direct changes
        # have their own explicit control immediately above the text box.
        _mode = st.selectbox("Rewrite Mode", [
            "Creative Script Rewrite / Improve Scene",
            "Polish Only / Do Not Change Story",
        ], key="_wbs_stage3_rewrite_mode")
        _length = st.selectbox("Target Length", [
            "Keep Current Length", "Condense for Tighter Pacing",
            "Expand to 400 Words", "Custom Word Count",
        ], key="_wbs_stage3_rewrite_length")
        _custom_words = None
        if _length == "Custom Word Count":
            _custom_words = st.number_input("Target words", 50, 2500, 400, 25,
                key="_wbs_stage3_rewrite_custom_words")
        _dialogue = st.selectbox("Dialogue Style for Rewrite", [
            "Use Current Project Dialogue Style", *DIALOGUE_STYLE_OPTIONS,
        ], key="_wbs_stage3_rewrite_dialogue")
        _exact_script_change = st.checkbox(
            "Direct Script Change / Obey My Instructions Exactly",
            key="_wbs_stage3_direct_script_change",
            help="Use the text below as an exact replacement rather than a creative rewrite.")
        if _exact_script_change:
            _mode = "Direct Script Change / Obey My Instructions Exactly"
        rewrite_direction = st.text_area(
            "Replacement Text" if _exact_script_change else "Specific Rewrite Direction (optional)",
            key="_wbs_stage3_rewrite_direction", height=130,
            placeholder=("Paste replacement text for the selected scene."
                         if _exact_script_change else
                         "Describe changes to the selected beat or entire storyline."))
        # If the scene is already drafted, this editor must rewrite the ACTUAL
        # manuscript scene, rather than silently changing only its old outline.
        _draft_blocks = st.session_state.get("scene_blocks") or {}
        _draft_beat_num = int(_selected_number) if _selected_number else None
        _draft_scene = (str(_draft_blocks.get(_draft_beat_num, _draft_blocks.get(str(_draft_beat_num), "")) or "").strip()
                        if _draft_beat_num is not None and isinstance(_draft_blocks, dict) else "")
        _rewrite_existing_draft = bool(_draft_scene and str(st.session_state.get("current_draft_output") or "").strip())
        if _rewrite_existing_draft:
            st.caption("Editing the existing manuscript scene. Accept Rewrite will replace this scene in the working draft.")
        if st.button("Preview Rewritten Storyline", key="_wbs_stage3_rewrite_preview_button",
                     use_container_width=True):
            backend = st.session_state.get("backend")
            client = getattr(backend, "client", None)
            model = getattr(backend, "model_name", None)
            if client is None or not model or not _selected_outline:
                st.error("The source storyline or writing service is unavailable. No changes were made.")
            else:
                _target = f"Aim for about {_custom_words} words." if _custom_words else _length
                _dialogue_rule = (get_dialogue_style_instruction() if
                    _dialogue == "Use Current Project Dialogue Style" else
                    DIALOGUE_STYLE_INSTRUCTIONS.get(_dialogue, _dialogue))
                _instruction = (
                    "Revise the supplied STORY OUTLINE only, not finished manuscript prose. "
                    "Return only the complete revised selected outline. "
                    "Keep every original [BEAT N] heading, [SCENE TITLE], [CORE OBJECTIVE], "
                    "[SCENE DETAILS & CONFLICT] and [STYLE & SYNTAX DIRECTIVE] so later generation works. "
                    "Preserve the writer's format, characters, continuity, voice, and development tense. "
                    "In SCENE DETAILS & CONFLICT write story events only. NEVER add commentary about "
                    "the scene, narration, objectives, pacing, syntax or writing technique to story text. "
                    "Put all such instructions solely in CORE OBJECTIVE or STYLE & SYNTAX DIRECTIVE. "
                    f"Mode: {_mode}. Target length: {_target}. Dialogue: {_dialogue_rule}. "
                    f"Development: {get_active_format_development_context()}. "
                    f"Writer's direction: {rewrite_direction or 'Improve selected outline.'}\n\n"
                    f"SOURCE OUTLINE:\n{_selected_outline}")
                if _rewrite_existing_draft:
                    _instruction = (
                        "Rewrite the following FINISHED MANUSCRIPT SCENE according to the writer's instructions. "
                        "Return only replacement story prose, no headers, beat markers, meta commentary, "
                        "writing instructions or explanation. Preserve story continuity, characters, "
                        "format, voice and existing scene length unless requested otherwise. "
                        f"Mode: {_mode}. Target length: {_target}. Dialogue: {_dialogue_rule}. "
                        f"Writer's direction: {rewrite_direction or 'Improve this scene.'}\n\n"
                        f"EXISTING MANUSCRIPT SCENE:\n{_draft_scene}"
                    )
                try:
                    _response = client.models.generate_content(model=model, contents=_instruction)
                    _preview = str(getattr(_response, "text", "") or "").strip()
                    if _rewrite_existing_draft:
                        _valid = bool(_preview) and not re.search(
                            r"(?im)^\s*\[(?:BEAT|CORE OBJECTIVE|STYLE\s*&\s*SYNTAX DIRECTIVE)", _preview)
                    else:
                        _old_ids = re.findall(_beat_pattern, _selected_outline)
                        _new_ids = re.findall(_beat_pattern, _preview)
                        _tags = ("[SCENE TITLE]", "[CORE OBJECTIVE]", "[SCENE DETAILS & CONFLICT]", "[STYLE & SYNTAX DIRECTIVE]")
                        _valid = bool(_preview) and _old_ids == _new_ids and not any(
                            _preview.upper().count(tag) != len(_old_ids) for tag in _tags)
                    if not _valid:
                        st.error("The rewrite did not preserve the required scene format. Original retained.")
                    else:
                        st.session_state["_wbs_stage3_rewrite_preview"] = _preview
                        st.session_state["_wbs_stage3_rewrite_origin"] = get_text_signature(_outline_now)
                        st.session_state["_wbs_stage3_rewrite_target"] = _location
                        st.session_state["_wbs_stage3_rewrite_draft_beat"] = _draft_beat_num if _rewrite_existing_draft else None
                        st.session_state["_wbs_stage3_rewrite_draft_signature"] = get_text_signature(_draft_scene) if _rewrite_existing_draft else ""
                except Exception as exc:
                    st.error(f"Rewrite could not be completed: {exc}")
        _preview = str(st.session_state.get("_wbs_stage3_rewrite_preview") or "").strip()
        if _preview:
            st.text_area("Review proposed rewrite before approval",
                         value=(_preview if st.session_state.get("_wbs_stage3_rewrite_draft_beat") is not None
                                else _wbs_reader_outline_preview(_preview)),
                         height=240, disabled=True, key="_wbs_stage3_rewrite_display")
            _accept, _discard = st.columns(2)
            with _accept:
                if st.button("Accept Rewrite", key="_wbs_stage3_accept_rewritten_outline", use_container_width=True):
                    _original = str(st.session_state.get("plot_outline") or "")
                    if st.session_state.get("_wbs_stage3_rewrite_origin") != get_text_signature(_original):
                        st.error("Source changed. Generate another preview first.")
                    elif st.session_state.get("_wbs_stage3_rewrite_draft_beat") is not None:
                        _n = int(st.session_state["_wbs_stage3_rewrite_draft_beat"])
                        _blocks = st.session_state.get("scene_blocks") or {}
                        _old_scene = str(_blocks.get(_n, _blocks.get(str(_n), "")) or "").strip()
                        if get_text_signature(_old_scene) != st.session_state.get("_wbs_stage3_rewrite_draft_signature"):
                            st.error("The manuscript scene changed. Generate another preview before accepting.")
                        elif _preview != _old_scene:
                            _blocks[_n] = _preview
                            _blocks.pop(str(_n), None)
                            st.session_state.scene_blocks = _blocks
                            st.session_state.current_draft_output = "\n\n".join(
                                str(_blocks[k]).strip() for k in sorted(_blocks, key=lambda v: int(v))
                                if str(_blocks[k] or "").strip())
                            st.session_state["_wbs_stage3_manuscript_rewrite_notice"] = f"Scene {_n} rewrite applied to working manuscript. Save when ready."
                            for _key in ("_wbs_stage3_rewrite_preview", "_wbs_stage3_rewrite_origin", "_wbs_stage3_rewrite_target", "_wbs_stage3_rewrite_draft_beat", "_wbs_stage3_rewrite_draft_signature"):
                                st.session_state.pop(_key, None)
                            st.rerun()
                    else:
                        _target = st.session_state.get("_wbs_stage3_rewrite_target") or ""
                        if _target == "Full Storyline":
                            _new_outline = _preview
                        else:
                            _num = re.search(r"\d+", _target).group()
                            _match = re.search(rf"(?ims)^\s*\[BEAT\s+{_num}\].*?(?=^\s*\[BEAT\s+\d+\]|\Z)", _original)
                            _new_outline = (_original[:_match.start()] + _preview + "\n" + _original[_match.end():]) if _match else ""
                        if _new_outline:
                            st.session_state.plot_outline = _new_outline
                            st.session_state["_wbs_stage3_unsaved_changes"] = True
                            for _key in ("_wbs_stage3_rewrite_preview", "_wbs_stage3_rewrite_origin", "_wbs_stage3_rewrite_target", "_wbs_stage3_rewrite_draft_beat", "_wbs_stage3_rewrite_draft_signature"):
                                st.session_state.pop(_key, None)
                            st.rerun()
            with _discard:
                if st.button("Discard", key="_wbs_stage3_discard_rewrite", use_container_width=True):
                    for _key in ("_wbs_stage3_rewrite_preview", "_wbs_stage3_rewrite_origin", "_wbs_stage3_rewrite_target", "_wbs_stage3_rewrite_draft_beat", "_wbs_stage3_rewrite_draft_signature"):
                        st.session_state.pop(_key, None)
                    st.rerun()

    if st.session_state.get("_wbs_stage3_manuscript_rewrite_notice"):
        st.success(st.session_state.pop("_wbs_stage3_manuscript_rewrite_notice"))
    # Review all approved manuscript scenes before leaving Plot Architecture.
    # This is an inspection and in-place checkpoint, never a new version.
    _preview_scene_blocks = st.session_state.get("scene_blocks") or {}
    _preview_scenes = []
    if isinstance(_preview_scene_blocks, dict):
        for _scene_key, _scene_value in sorted(_preview_scene_blocks.items(), key=lambda kv: int(kv[0])):
            _scene_text = str(_scene_value or "").strip()
            if _scene_text:
                _preview_scenes.append((int(_scene_key), _scene_text))
    if _preview_scenes:
        st.markdown("---")
        st.subheader("Final Working Manuscript Preview")
        st.caption("Review all scenes together before saving Plot Architecture. This preview uses the accepted working manuscript; no AI generation.")
        _preview_complete_text = "\n\n".join(_text for _, _text in _preview_scenes)
        for _scene_id, _scene_text in _preview_scenes:
            st.markdown(f"**Scene {_scene_id}**")
            for _paragraph in re.split(r"\n\s*\n", _scene_text):
                if _paragraph.strip():
                    st.write(_paragraph.strip())
        _original_full_draft = str(st.session_state.get("current_draft_output") or "").strip()
        if _original_full_draft != _preview_complete_text:
            st.warning("The working manuscript and scene list do not match. Saving is blocked to avoid losing accepted edits.")
        elif st.button("💾 Save Working Manuscript to Current Revision", key="_wbs_stage3_save_existing_revision", use_container_width=True, disabled=bool(st.session_state.get("demo_mode"))):
            _row_id = str(st.session_state.get("_wbs_active_saved_session_row_id") or "").strip()
            _project_id = get_active_project_id()
            _user_id = get_current_user_id()
            if not _row_id or not _project_id or not _user_id:
                st.error("Cannot identify the exact current saved revision. No record changed.")
            else:
                try:
                    _query = (supabase.table("writersblock_project_drafts")
                        .select("id, draft_content")
                        .eq("id", _row_id)
                        .eq("project_id", _project_id)
                        .eq("user_id", _user_id)
                        .eq("draft_type", "project_session")
                        .limit(1).execute())
                    _rows = getattr(_query, "data", None) or []
                    if not _rows:
                        st.error("The selected saved revision was not found. No record changed.")
                    else:
                        _snapshot = json.loads(_rows[0].get("draft_content") or "{}")
                        if not isinstance(_snapshot, dict):
                            raise ValueError("The existing revision data is invalid")
                        _previous_text = str(_snapshot.get("current_draft_output") or "").strip()
                        _previous_blocks = _snapshot.get("scene_blocks") or {}
                        _new_blocks = {str(_n): _text for _n, _text in _preview_scenes}
                        if _previous_text == _preview_complete_text and _previous_blocks == _new_blocks:
                            st.info("Current revision already contains these scenes. No changes or new version created.")
                        else:
                            _snapshot["current_draft_output"] = _preview_complete_text
                            _snapshot["scene_blocks"] = _new_blocks
                            # Any previous integrity report applied to different prose is no longer current.
                            _snapshot.pop("project_integrity_report", None)
                            _snapshot.pop("project_integrity_source_signature", None)
                            _snapshot.pop("project_integrity_status", None)
                            _updated = (supabase.table("writersblock_project_drafts")
                                .update({"draft_content": json.dumps(_snapshot)})
                                .eq("id", _row_id)
                                .eq("project_id", _project_id)
                                .eq("user_id", _user_id)
                                .eq("draft_type", "project_session")
                                .execute())
                            if not getattr(_updated, "data", None):
                                raise RuntimeError("The database did not confirm the update")
                            st.session_state.current_draft_output = _preview_complete_text
                            st.session_state.pop("project_integrity_report", None)
                            st.session_state.pop("project_integrity_source_signature", None)
                            st.session_state.pop("project_integrity_status", None)
                            st.success("Working manuscript saved to the existing revision. No new version created.")
                except Exception as _save_exc:
                    st.error(f"Manuscript was not saved: {_save_exc}")

    st.markdown("---")
    st.caption("Save and continue. Unchanged storylines retain their existing version number.")
    if st.button("💾 Save Plot Architecture & Continue", key="_wbs_stage3_save_plot_architecture",
                 type="primary", use_container_width=True):
        if st.session_state.get("demo_mode"):
            full_version_only_notice("Save Plot Architecture")
        else:
            # Compare with the outline loaded by this writer (or last saved
            # in this session). Never compare against the latest project row:
            # other saved versions/branches can have different outlines.
            _current_outline = str(st.session_state.get("plot_outline") or "").strip()
            _baseline = st.session_state.get("_wbs_stage3_saved_outline_baseline")
            _explicit_edits = bool(st.session_state.get("_wbs_stage3_unsaved_changes", False))
            _project_id = get_active_project_id()
            # A project that has never been saved needs an initial checkpoint.
            _requires_first_save = not _project_id
            if _baseline is None and _project_id:
                # Existing project loaded through a legacy flow: determine its
                # exact selected saved snapshot, not the newest sibling version.
                _baseline = _current_outline if not _explicit_edits else ""
            _changed = (_baseline is not None and _current_outline != _baseline)
            if _requires_first_save or _changed or _explicit_edits:
                if not save_current_project_session_to_supabase():
                    st.stop()
                st.session_state["_wbs_stage3_saved_outline_baseline"] = _current_outline
            # With no edits, advance without ANY Supabase insert/version bump.
            st.session_state["_wbs_stage3_unsaved_changes"] = False
            # A saved complete manuscript must not be regenerated simply because
            # the writer returns to Plot Architecture and advances again.
            if str(st.session_state.get("current_draft_output") or "").strip():
                wbs_request_stage_change("Isolation Guardrail", export_view=False)
            else:
                wbs_request_stage_change("Drafting Engine")
    if st.session_state.get("_wbs_stage3_unsaved_changes"):
        st.caption("There are unsaved changes to the storyline.")

# ======================================
# PHASE 4: RECURSIVE DRAFTING ENGINE
# ======================================
elif st.session_state.project_stage in ["Drafting", "Drafting Engine"]:
    require_product_access("drafting")

    st.header("📄 Generating Your Creative Draft")
    st.caption("WBS is writing the approved story sections in sequence and preserving continuity. Each section is generated only once.")
    render_project_title_banner("step_4_creative_draft")
    st.caption(
        f"Dialogue Style: {get_dialogue_style_display()} — applied to every scene block. "
        "Project type controls how dialogue is written and formatted."
    )
  

    if "current_draft_output" not in st.session_state:
        st.session_state.current_draft_output = ""

    if "rolling_lore_book" not in st.session_state:
        st.session_state.rolling_lore_book = ""

    if "current_processing_beat" not in st.session_state:
        st.session_state.current_processing_beat = 1

    plot_outline_text = st.session_state.get("plot_outline", "")

    def split_plot_outline_into_beats(outline_text):
        text = str(outline_text or "").strip()
        if not text:
            return []

        # Current Plot Architecture format: [BEAT 1], [BEAT 2], etc.
        beat_pattern = re.compile(
            r"(?im)^\s*\[BEAT\s+(\d+)\]\s*$"
        )
        matches = list(beat_pattern.finditer(text))

        if matches:
            beats = []
            for idx, match in enumerate(matches):
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                beat_block = text[match.start():end].strip()
                if beat_block:
                    beats.append(beat_block)
            return beats

        # Compatibility with older outlines that used === separators.
        legacy_beats = [
            beat.strip()
            for beat in text.split("===")
            if beat.strip()
        ]
        if len(legacy_beats) > 1:
            return legacy_beats

        # Final compatibility fallback for plain BEAT 1 / BEAT 2 headings.
        plain_pattern = re.compile(
            r"(?im)^\s*BEAT\s+(\d+)\s*:?\s*$"
        )
        plain_matches = list(plain_pattern.finditer(text))
        if plain_matches:
            beats = []
            for idx, match in enumerate(plain_matches):
                end = plain_matches[idx + 1].start() if idx + 1 < len(plain_matches) else len(text)
                beat_block = text[match.start():end].strip()
                if beat_block:
                    beats.append(beat_block)
            return beats

        return [text]

    filtered_beats = split_plot_outline_into_beats(plot_outline_text)
    total_beats = len(filtered_beats)
    st.session_state.total_beats = total_beats

    if total_beats == 0:
        st.warning("No plot outline beats found. Return to Plot Architect and create an outline first.")

    else:
        if "scene_blocks" not in st.session_state:
            st.session_state.scene_blocks = {}

        saved_scene_numbers = [
            int(scene_number)
            for scene_number, scene_text in st.session_state.scene_blocks.items()
            if str(scene_text or "").strip()
        ]

        next_missing_scene = None
        for scene_number in range(1, total_beats + 1):
            if scene_number not in saved_scene_numbers:
                next_missing_scene = scene_number
                break

        if next_missing_scene is not None:
            st.session_state.current_processing_beat = next_missing_scene
        else:
            st.session_state.current_processing_beat = total_beats + 1

        recommended_scene_word_count = 1200
        audiobook_scene_instruction = ""

        if is_picture_book_project():
            render_picture_book_budget("drafting")
            alloc = picture_book_allocations()
            beat_index = max(0, min(3, int(st.session_state.current_processing_beat or 1)-1))
            recommended_scene_word_count = alloc[beat_index]
            if total_beats != 4:
                st.warning("Picture books require exactly four beats. Return to Plot Architecture and set four beats.")
                st.stop()
            remaining = picture_book_target() - count_words(st.session_state.current_draft_output)
            st.info(f"Beat {beat_index+1} suggested allocation: {recommended_scene_word_count} words. "
                    f"Overall target remaining: {max(0,remaining)} words. "
                    "Scene allocations are guidelines; review overall length before final output.")

        if st.session_state.get("format_type") == "Audio Book":
            audiobook_spec = get_audiobook_length_spec()
            audiobook_target_total = int(
                st.session_state.get(
                    "audiobook_target_word_count",
                    audiobook_spec["default_words"],
                )
            )
            drafted_word_count = count_words(st.session_state.current_draft_output)
            remaining_scene_count = max(1, total_beats - len(saved_scene_numbers))
            remaining_word_target = max(50, audiobook_target_total - drafted_word_count)
            recommended_scene_word_count = int(
                round((remaining_word_target / remaining_scene_count) / 25) * 25
            )
            recommended_scene_word_count = max(50, min(2500, recommended_scene_word_count))

            st.info(
                f"Audio Book target: {st.session_state.get('audiobook_length', '30 Minutes')} | "
                f"{audiobook_target_total:,} total words | "
                f"{drafted_word_count:,} written | "
                f"approximately {remaining_word_target:,} remaining across "
                f"{remaining_scene_count} unwritten scene block(s)."
            )

            audiobook_scene_instruction = f"""
AUDIO BOOK LENGTH CONTROL:
Selected finished length: {st.session_state.get('audiobook_length', '30 Minutes')}
Acceptable total manuscript range: {audiobook_spec['min_words']:,}–{audiobook_spec['max_words']:,} words
Selected total manuscript target: {audiobook_target_total:,} words
Words already drafted before this scene: {drafted_word_count:,}
Approximate words remaining before this scene: {remaining_word_target:,}
Keep this scene close to its assigned target so the completed manuscript remains within the selected Audio Book length.
"""

        if st.session_state.get("_wbs_last_draft_budget_notice"):
            st.info(st.session_state.pop("_wbs_last_draft_budget_notice"))

        # WBS_20261023_SCENE_BEAT_EDITOR
        with st.expander("✏️ Edit Saved Scene Beat / Manuscript", expanded=False):
            _existing_blocks = st.session_state.get("scene_blocks") or {}
            _scene_numbers = sorted(int(k) for k,v in _existing_blocks.items() if str(k).isdigit() and str(v or "").strip())
            _labels = [f"Scene Beat {k}" for k in _scene_numbers]
            if str(st.session_state.get("current_draft_output") or "").strip():
                _labels.append("Full Manuscript")
            if not _labels:
                st.info("Load an existing manuscript or generate a scene first.")
            else:
                _chosen = st.selectbox("Select section to revise", _labels, key="wbs_scene_edit_choice")
                _beat_no = None if _chosen == "Full Manuscript" else int(_chosen.rsplit(" ",1)[-1])
                _old_text = str(st.session_state.get("current_draft_output") or "") if _beat_no is None else str(_existing_blocks.get(_beat_no, _existing_blocks.get(str(_beat_no), "")))
                _sig = get_text_signature(_old_text)[:12]
                _edited = st.text_area("Editable scene text — paste Quill's revision here", value=_old_text,
                                        height=320, key=f"wbs_scene_edit_{_beat_no}_{_sig}")
                if st.button("💾 Save This Version", key="wbs_scene_save_revision", type="primary",
                             disabled=bool(st.session_state.get("demo_mode"))):
                    if not _edited.strip():
                        st.error("Empty text cannot be saved.")
                    elif _edited == _old_text:
                        st.info("No changes to save.")
                    else:
                        _old_draft = st.session_state.get("current_draft_output", "")
                        _old_blocks = dict(_existing_blocks)
                        _old_branch = st.session_state.get("project_version_name", "Original")
                        if _beat_no is None:
                            st.session_state.current_draft_output = _edited
                            st.session_state.scene_blocks = {}
                        else:
                            st.session_state.scene_blocks[_beat_no] = _edited
                            st.session_state.current_draft_output = "\n\n".join(
                                str(v).strip() for k,v in sorted(st.session_state.scene_blocks.items(),key=lambda kv:int(kv[0])) if str(v or "").strip())
                        _new_branch = f"Edited {datetime.now():%m-%d %H%M}"
                        try:
                            _result = save_current_project_session_to_supabase(version_name=_new_branch, save_as_new_version=True)
                            if not _result:
                                raise RuntimeError("Database save was not confirmed")
                        except Exception as _exc:
                            st.session_state.current_draft_output = _old_draft
                            st.session_state.scene_blocks = _old_blocks
                            st.session_state.project_version_name = _old_branch
                            st.error(f"Unable to save; previous content restored: {_exc}")
                        else:
                            st.success("Edited manuscript saved as a new version; previous version preserved.")
                            st.rerun()

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📄 Draft Output Canvas")

            latest_scene_number = max(1, int(st.session_state.get("current_processing_beat", 1) or 1) - 1)
            latest_scene_text = ""
            if isinstance(st.session_state.get("scene_blocks"), dict):
                latest_scene_text = st.session_state.scene_blocks.get(latest_scene_number, "")

            st.text_area(
                "Latest Scene Output:",
                value=latest_scene_text or st.session_state.current_draft_output,
                height=500,
                label_visibility="collapsed",
                disabled=True,
            )

            st.subheader("⚙️ Chapter / Scene Settings")

            chapter_title = st.text_input(
                "Chapter / Scene Title:",
                value=f"Scene Block {st.session_state.current_processing_beat}",
                key=f"chapter_title_{st.session_state.current_processing_beat}"
            )

            target_word_count = st.number_input(
                "Target Word Count Per Scene Block:",
                min_value=50,
                max_value=2500,
                value=recommended_scene_word_count,
                step=25,
                key=f"target_word_count_{st.session_state.current_processing_beat}"
            )

            pov_choice = st.selectbox(
                "Point of View:",
                ["Third Person Limited", "Third Person Omniscient", "First Person"],
                key=f"pov_choice_{st.session_state.current_processing_beat}"
            )

            # Read-only preview of the CURRENT planned scene, before instructions.
            # Uses the existing Stage 3 outline; does not generate or modify story content.
            _preview_index = int(st.session_state.current_processing_beat) - 1
            if 0 <= _preview_index < len(filtered_beats):
                _preview_beat = str(filtered_beats[_preview_index] or "")

                def _preview_field(label):
                    _match = re.search(
                        rf"(?ims)^\s*\[{label}\]\s*:\s*(.*?)(?=^\s*\[[A-Z][^\n]*\]\s*:|^\s*\[BEAT\s+\d+\]|^\s*===|\Z)",
                        _preview_beat,
                    )
                    return _match.group(1).strip() if _match else ""

                _preview_title = _preview_field(r"SCENE TITLE")
                _preview_goal = _preview_field(r"CORE OBJECTIVE")
                _preview_detail = (_preview_field(r"SCENE DETAILS\s*&\s*CONFLICT")
                                   or _preview_field(r"SCENE DETAILS"))
                st.markdown(f"**Upcoming Scene {(_preview_index + 1)} of {total_beats} — Story Plan**")
                if _preview_title:
                    st.markdown(f"**{_preview_title}**")
                if _preview_goal:
                    st.markdown(_preview_goal)
                if _preview_detail:
                    st.markdown(_preview_detail)
                if not (_preview_title or _preview_goal or _preview_detail):
                    st.caption("This scene's detailed plan is not available in the loaded outline.")
                st.caption("Read-only scene plan from Stage 3. The scene will be drafted from this outline; review wording after the draft is assembled.")

            st.markdown("---")

        # WBS_FAST_PICTURE_BOOK_20261025
        # A picture book is short enough to draft in one model call. Split the
        # returned story into individually resumable blocks, without creating
        # a numbered project version. Fall back to the existing per-beat
        # drafting engine if the four labeled blocks cannot be verified.
        _wbs_pb_fast_ready = (
            is_picture_book_project()
            and total_beats == 4
            and not any(str(v or "").strip() for v in st.session_state.scene_blocks.values())
            and not st.session_state.get("_wbs_pb_fast_attempted")
            and not st.session_state.get("_wbs_overbudget_scene")
        )
        if _wbs_pb_fast_ready:
            st.session_state["_wbs_pb_fast_attempted"] = True
            st.subheader("Preparing complete picture-book draft")
            _wbs_pb_progress = st.progress(0, text="Drafting four beats together — one model request")
            _wbs_pb_outline = "\n\n".join(filtered_beats)
            _wbs_pb_alloc = picture_book_allocations()
            _wbs_pb_instruction = f"""
WRITE THE COMPLETE CHILDREN'S PICTURE BOOK IN ONE RESPONSE.
Use exactly FOUR scenes, following each outline beat IN ORDER.
Begin each scene on a new line with EXACTLY this marker:
[SCENE BLOCK 1]
[SCENE BLOCK 2]
[SCENE BLOCK 3]
[SCENE BLOCK 4]
After each marker write only the finished narrative for that scene.
Do not use additional [SCENE BLOCK] labels. Do not insert commentary,
markdown code fences, planning notes, or a summary. Do not include
=== LORE UPDATE ===; this is the entire short book in one request.
Maintain plot continuity between all four scenes and honor the project
format, age group, POV, writing tense, style, and narration rules.
Total manuscript maximum: {picture_book_target()} words; suggested
beat allocations: {', '.join(str(n) for n in _wbs_pb_alloc)} words.
These are guidelines for the scenes; respect the total manuscript maximum.
DIALOGUE AND NARRATION:
{get_dialogue_development_packet()}
PROJECT CREATIVE CONTEXT:
{get_full_project_continuity_context()}
WRITING TENSE:
{get_development_writing_tense()}
STORY OUTLINE:
{_wbs_pb_outline}
"""
            try:
                if create_bridge_adapter is None:
                    raise RuntimeError("WritersBlock Model bridge unavailable")
                _wbs_pb_bridge = create_bridge_adapter(backend=st.session_state.backend)
                _wbs_pb_result = _wbs_pb_bridge.execute(
                    "Continue drafting",
                    st.session_state,
                    prepared_context={
                        "effective_format_type": get_effective_format_type(),
                        "dialogue_development_packet": get_dialogue_development_packet(),
                        "format_development_context": get_full_project_continuity_context(),
                        "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                        "quill_template_context": refresh_quill_template_context(),
                    },
                    action_payload={
                        "current_beat_text": _wbs_pb_instruction,
                        "rolling_lore": st.session_state.rolling_lore_book,
                        "format_type": get_effective_format_type(),
                        "tone_style": st.session_state.tone_style,
                        "author_style": st.session_state.author_style,
                    },
                )
                if not _wbs_pb_result.success or not ai_output_is_usable(_wbs_pb_result.output):
                    raise RuntimeError(_wbs_pb_result.error or "Empty or unusable story response")
                _wbs_pb_text = str(_wbs_pb_result.output).strip()
                _wbs_pb_matches = list(re.finditer(r"(?im)^\s*\[SCENE\s+BLOCK\s+([1-4])\]\s*$", _wbs_pb_text))
                _wbs_pb_numbers = [int(m.group(1)) for m in _wbs_pb_matches]
                if _wbs_pb_numbers != [1, 2, 3, 4]:
                    raise ValueError("Model did not return four separately labeled scenes")
                _wbs_pb_scenes = {}
                for _i, _m in enumerate(_wbs_pb_matches):
                    _end = _wbs_pb_matches[_i + 1].start() if _i < 3 else len(_wbs_pb_text)
                    _scene_text = _wbs_pb_text[_m.end():_end].strip()
                    if not _scene_text or not ai_output_is_usable(_scene_text):
                        raise ValueError(f"Scene {_i + 1} was empty")
                    _wbs_pb_scenes[_i + 1] = _scene_text
                # Commit only AFTER all four scenes have passed validation.
                st.session_state.scene_blocks.update(_wbs_pb_scenes)
                st.session_state.current_draft_output = "\n\n".join(
                    st.session_state.scene_blocks[i] for i in range(1, 5))
                st.session_state.current_processing_beat = 5
                _project_id = get_active_project_id()
                if _project_id:
                    for _scene_no, _scene_text in _wbs_pb_scenes.items():
                        try:
                            supabase.table("writersblock_project_drafts").insert({
                                "project_id": _project_id,
                                "user_id": get_current_user_id(),
                                "draft_title": f"Scene Block {_scene_no}",
                                "draft_type": "scene_draft",
                                "draft_content": _scene_text,
                                "version_number": _scene_no,
                            }).execute()
                        except Exception as _save_error:
                            st.warning(f"Scene {_scene_no} completed in this session but its background checkpoint failed: {_save_error}")
                _wbs_pb_progress.progress(100, text="All four picture-book scenes completed")
                wbs_request_stage_change("Isolation Guardrail", export_view=False)
                st.stop()
            except Exception as _wbs_pb_error:
                _wbs_pb_progress.empty()
                st.info("Fast picture-book draft was unavailable. Switching to reliable scene-by-scene drafting; no completed scenes were duplicated.")
                # One attempt only per session. This prevents repeated paid
                # fast-path API calls on each Streamlit rerun.

        if st.session_state.current_processing_beat <= total_beats:
            current_scene_number = st.session_state.current_processing_beat

            if current_scene_number in st.session_state.scene_blocks and str(st.session_state.scene_blocks.get(current_scene_number, "")).strip():
                st.info(f"Scene Block {current_scene_number} is already written.")
                st.stop()

            # WBS: A generated picture-book scene that exceeds its budget remains editable.
            # Nothing is appended until the writer accepts a version within the limits.
            _pending = st.session_state.get("_wbs_overbudget_scene")
            if isinstance(_pending, dict) and _pending.get("beat") == current_scene_number and is_picture_book_project():
                _beat_limit = picture_book_allocations()[current_scene_number - 1]
                _book_remaining = max(0, picture_book_target() - count_words(st.session_state.current_draft_output))
                _effective_limit = min(_beat_limit, _book_remaining)
                st.warning(f"Scene {current_scene_number} needs shortening to {_effective_limit} words or fewer before it can be added.")
                _review = st.text_area(
                    "Edit generated scene to fit the word budget",
                    value=str(_pending.get("text") or ""),
                    height=300,
                    key=f"wbs_overbudget_review_{current_scene_number}_{_pending['token']}",
                )
                _review_count = count_words(_review)
                st.caption(f"Scene words: {_review_count} / {_effective_limit} allowed · "
                           f"{max(0, _review_count - _effective_limit)} words to remove")
                _accept, _discard = st.columns(2)
                with _accept:
                    if st.button("✅ Accept Edited Scene", key=f"wbs_accept_overbudget_{current_scene_number}",
                                 disabled=not (0 < _review_count <= _effective_limit), use_container_width=True):
                        if current_scene_number in st.session_state.scene_blocks:
                            st.warning("This scene was already added. The edit was not duplicated.")
                            st.stop()
                        _project_id = get_active_project_id()
                        if _project_id:
                            try:
                                supabase.table("writersblock_project_drafts").insert({
                                    "project_id": _project_id,
                                    "user_id": get_current_user_id(),
                                    "draft_title": f"Scene Block {current_scene_number}",
                                    "draft_type": "scene_draft",
                                    "draft_content": _review,
                                    "version_number": current_scene_number,
                                }).execute()
                            except Exception as _exc:
                                st.error(f"Scene could not be saved: {_exc}")
                                st.stop()
                        st.session_state.scene_blocks[current_scene_number] = _review
                        st.session_state.current_draft_output = "\n\n".join(
                            str(v).strip() for _, v in sorted(
                                st.session_state.scene_blocks.items(), key=lambda kv: int(kv[0]))
                            if str(v or "").strip()
                        )
                        if _pending.get("lore"):
                            st.session_state.rolling_lore_book = _pending["lore"]
                        mark_demo_action_used("draft_scene")
                        st.session_state.pop("_wbs_overbudget_scene", None)
                        _next = next((i for i in range(1, total_beats + 1)
                                      if not str(st.session_state.scene_blocks.get(i, "")).strip()), None)
                        if _next is None:
                            st.session_state.current_processing_beat = total_beats + 1
                            wbs_request_stage_change("Isolation Guardrail", export_view=False)
                        else:
                            st.session_state.current_processing_beat = _next
                        st.rerun()
                with _discard:
                    if st.button("Discard and Regenerate", key=f"wbs_discard_overbudget_{current_scene_number}",
                                 use_container_width=True):
                        st.session_state.pop("_wbs_overbudget_scene", None)
                        st.rerun()
                st.info("Your generated scene has not been added. Edit and accept it, or discard and regenerate.")

            btn_label = f"Execute Scene Block {current_scene_number} of {total_beats} ⚡"

            # Automatic internal drafting — no redundant scene execution screen.
            # The original generation/save pathway below remains unchanged.
            if True:
                require_product_access("drafting")
                require_demo_action_available("draft_scene", current_scene_number)
                current_beat_data = filtered_beats[current_scene_number - 1]

                series_drafting_context = build_series_context_text(
                    max_total_chars=18000,
                    per_source_chars=8000,
                )

                drafting_instruction_packet = f"""
{audiobook_scene_instruction}
CHAPTER / SCENE SETTINGS:
Chapter / Scene Title: {chapter_title}
Target Word Count: Approximately {recommended_scene_word_count if is_picture_book_project() else target_word_count} words
Picture Book Word Budget (if applicable): {f'Overall target {picture_book_target()} words; beat {current_scene_number} suggested allocation {picture_book_allocations()[current_scene_number-1]} words. Try to stay near these targets; do not truncate or omit story content to enforce a single scene limit.' if is_picture_book_project() else 'Not applicable'}
Point of View: {pov_choice}
Tense (set in Development Setup; maintain consistently): {get_development_writing_tense()}

DIALOGUE / NARRATION REQUIREMENT:
{get_dialogue_development_packet()}
Apply this requirement to the current scene. Preserve the selected project type and its dialogue conventions.

SERIES CONTINUITY REFERENCE:
{series_drafting_context or "This is a standalone book with no series reference package."}

PROJECT-WIDE CREATIVE CONTINUITY:
{get_full_project_continuity_context()}

CURRENT OUTLINE BEAT:
{current_beat_data}

IMPORTANT OUTPUT RULE:
Write ONLY this single scene block. Do not repeat earlier scenes. Do not summarize the full manuscript. Do not include manuscript output, prior scene text, headings, or any material outside this current scene block. End with a LORE UPDATE only if needed.
"""

                with st.spinner(f"Drafting scene block {current_scene_number}..."):
                        try:

                            if create_bridge_adapter is None:
                                st.error(
                                    "WritersBlock Model is unavailable. "
                                    f"{WBS_MODEL_IMPORT_ERROR}"
                                )
                                st.stop()

                            _wbs_draft_bridge = create_bridge_adapter(
                                backend=st.session_state.backend
                            )
                            _wbs_draft_result = _wbs_draft_bridge.execute(
                                "Continue drafting",
                                st.session_state,
                                prepared_context={
                                    "effective_format_type": get_effective_format_type(),
                                    "dialogue_development_packet": get_dialogue_development_packet(),
                                    "format_development_context": get_full_project_continuity_context(),
                                    "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                                    "quill_template_context": refresh_quill_template_context(),
                                },
                                action_payload={
                                    "current_beat_text": drafting_instruction_packet,
                                    "rolling_lore": st.session_state.rolling_lore_book,
                                    "format_type": get_effective_format_type(),
                                    "tone_style": st.session_state.tone_style,
                                    "author_style": st.session_state.author_style,
                                },
                            )

                            if not _wbs_draft_result.success:
                                raise RuntimeError(
                                    _wbs_draft_result.error
                                    or "WritersBlock Model Bridge returned no draft."
                                )

                            raw_response = _wbs_draft_result.output
                            st.session_state["_wbs_agent_bridge_last_operation"] = (
                                _wbs_draft_result.backend_operation or ""
                            )
                            st.session_state["_wbs_agent_bridge_last_success"] = True

                        except Exception as e:
                            st.error(f"Drafting failed. No scene text was saved. Backend error: {e}")
                            st.stop()

                        if not ai_output_is_usable(raw_response):
                            st.error("Drafting failed. Gemini did not return usable scene text. No scene text was saved.")
                            st.stop()


                        lore_marker_match = re.search(
                            r"===?\s*LORE\s+UPDATE\s*===?",
                            str(raw_response),
                            re.IGNORECASE,
                        )

                        if lore_marker_match:
                            start_idx, end_idx = lore_marker_match.span()
                            narrative_text = str(raw_response)[:start_idx].strip()
                            new_lore = str(raw_response)[end_idx:].strip()
                        else:
                            narrative_text = str(raw_response).strip()
                            new_lore = (
                                st.session_state.rolling_lore_book
                                if st.session_state.rolling_lore_book
                                else "- Active context state synchronized."
                            )

                        if narrative_text and is_picture_book_project():
                            _suggested = picture_book_allocations()[current_scene_number - 1]
                            _scene_words = count_words(narrative_text)
                            if _scene_words > _suggested:
                                st.session_state["_wbs_last_draft_budget_notice"] = (
                                    f"Scene {current_scene_number}: {_scene_words} words, above its "
                                    f"suggested {_suggested}-word allocation. The scene was kept intact. "
                                    "Review total length in Stage 5 or rewrite in Stage 7."
                                )
                        if narrative_text:
                            if "scene_blocks" not in st.session_state:
                                st.session_state.scene_blocks = {}

                            if current_scene_number in st.session_state.scene_blocks:
                                st.warning(f"Scene Block {current_scene_number} was already written. It was not added twice.")
                                st.stop()

                            st.session_state.scene_blocks[current_scene_number] = narrative_text

                            ordered_scene_texts = []
                            for scene_idx in sorted(st.session_state.scene_blocks.keys()):
                                scene_text = str(st.session_state.scene_blocks.get(scene_idx) or "").strip()
                                if scene_text:
                                    ordered_scene_texts.append(scene_text)

                            st.session_state.current_draft_output = "\n\n".join(ordered_scene_texts)

                        if new_lore:
                            st.session_state.rolling_lore_book = new_lore

                        if narrative_text:
                            mark_demo_action_used("draft_scene")

                        # Save generated scene block to the selected project only.
                        active_project_id = get_active_project_id()

                        if active_project_id and narrative_text:
                            supabase.table("writersblock_project_drafts").insert({
                                "project_id": active_project_id,
                                "user_id": get_current_user_id(),
                                "draft_title": f"Scene Block {current_scene_number}",
                                "draft_type": "scene_draft",
                                "draft_content": narrative_text,
                                "version_number": current_scene_number
                            }).execute()

                        saved_scene_numbers = [
                            int(scene_number)
                            for scene_number, scene_text in st.session_state.scene_blocks.items()
                            if str(scene_text or "").strip()
                        ]

                        next_missing_scene = None
                        for scene_number in range(1, total_beats + 1):
                            if scene_number not in saved_scene_numbers:
                                next_missing_scene = scene_number
                                break

                        if next_missing_scene is None:
                            st.session_state.current_processing_beat = total_beats + 1
                            wbs_request_stage_change("Isolation Guardrail", export_view=False)
                        else:
                            st.session_state.current_processing_beat = next_missing_scene

                        st.rerun()

        with col_right:
            st.subheader("🧠 Rolling Lore Memory")

            st.text_area(
                "Rolling Lore Memory:",
                value=st.session_state.rolling_lore_book,
                height=250,
                label_visibility="collapsed",
                disabled=True,
            )

            st.markdown("---")

            saved_scene_count = len([
                scene_text
                for scene_text in st.session_state.scene_blocks.values()
                if str(scene_text or "").strip()
            ])

            st.metric(
                "Current Scene Beat",
                f"{saved_scene_count} / {total_beats}"
            )

            st.markdown("---")

            for idx in range(1, total_beats + 1):
                scene_is_saved = (
                    idx in st.session_state.scene_blocks
                    and str(st.session_state.scene_blocks.get(idx, "")).strip()
                )

                if scene_is_saved:
                    st.markdown(f"✅ Scene Block {idx}: Written")
                elif idx == st.session_state.current_processing_beat:
                    st.markdown(f"🔷 Scene Block {idx}: Ready")
                else:
                    st.markdown(f"⚪ Scene Block {idx}: Pending")
# ======================================================================================
# PHASE 5: SCRIPT LOCK / MANUSCRIPT OUTPUT
# ======================================================================================
elif st.session_state.project_stage == "Isolation Guardrail":
    require_product_access("safety")


    # Step 8 is the only place where the neutral working manuscript is converted to an industry format.
    if st.session_state.get("export_view", False):
        st.header("📤 Stage 5: Manuscript Review" if st.session_state.get("demo_mode") else "✅ Stage 5: Final Manuscript")
        render_project_title_banner("step_8_final_output_conversion")
        st.markdown("---")

        # Step 8 terminates this rerun with st.stop(), so render Shadow here.

        current_source = str(st.session_state.get("current_draft_output") or "").strip()
        if not current_source:
            st.warning("No working manuscript is available for Final Output.")
            st.stop()

        # The manuscript was written for the format selected at project setup.
        # Final output must not request another format selection, model call, or rewrite.
        selected_final_format = str(st.session_state.get("format_type") or "Novel / Prose").strip()
        if selected_final_format not in FINAL_OUTPUT_FORMAT_OPTIONS:
            selected_final_format = get_final_output_format()
        st.session_state.final_output_format = selected_final_format

        source_signature = get_text_signature(current_source)
        if st.session_state.get("final_output_source_signature") != source_signature or str(st.session_state.get("final_output_text") or "").strip() != current_source:
            st.session_state.final_output_text = current_source
            st.session_state.final_output_source_signature = source_signature
            st.session_state.final_output_saved_signature = ""

        st.subheader(f"📋 FINAL MANUSCRIPT — {get_automatic_output_label(selected_final_format)}")
        st.caption(f"{count_words(current_source):,} words · Prepared directly from the approved manuscript · No AI regeneration")
        st.text_area("Final Manuscript", value=current_source, height=520, disabled=True, key=f"wbs_final_manuscript_readonly_{source_signature}")

        if st.session_state.get("demo_mode"):
            if st.button("Download Final Manuscript (.docx) 🔒", key="trial_download_final_converted_output", use_container_width=True):
                full_version_only_notice("Manuscript Printout")
        else:
            if selected_final_format == PICTURE_BOOK_FORMAT:
                spreads = build_picture_book_spreads_locally(current_source)
                docx_bytes = build_picture_book_layout_docx_bytes(
                    get_project_title_for_display(), spreads,
                    st.session_state.get("picture_book_page_size", DEFAULT_PICTURE_BOOK_PAGE_SIZE),
                )
            else:
                docx_bytes = build_final_output_docx_bytes(
                    get_project_title_for_display(), current_source, selected_final_format
                )
            project_stem = safe_download_stem(get_project_title_for_display(), "writersblock_project")
            format_stem = safe_download_stem(get_automatic_output_label(selected_final_format), "final_output")
            st.download_button(
                label="Download Final Manuscript (.docx)",
                data=docx_bytes,
                file_name=f"{project_stem}_{format_stem}_final.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary", use_container_width=True,
            )

        st.stop()

    if st.session_state.get("export_view", False):
        if st.session_state.get("demo_mode"):
            st.header("📤 Stage 5: Manuscript Review")
            st.markdown("##### Review the completed manuscript. Final manuscript saving and printout are available in the full Writer Edition.")
        else:
            st.header("📤 Stage 5: FINAL OUTPUT")
            st.markdown("##### This is the final manuscript output stage. Save the final manuscript before downloading or starting a new project.")
        render_project_title_banner("step_8_manuscript_output")
    else:
        st.header("🛡️ Stage 4: Editorial & Publisher Review")
        st.markdown("##### Examine the draft, run optional editorial and submission checks, then approve it for Final Manuscript. Polish and Rewrite remain available on request.")
        if access_allows("rewrite") and str(st.session_state.get("current_draft_output") or "").strip():
            if st.button("Open Script Rewrite", key="wbs_stage4_open_rewrite", use_container_width=True):
                wbs_request_stage_change("Rewrite Engine")
        render_project_title_banner("step_5_script_lock")
        st.markdown("---")
        st.subheader("Editorial & Publisher Review")
        st.caption("Review your complete working manuscript before final approval. Checks are read-only and never rewrite your work.")
        current_source = str(st.session_state.get("current_draft_output") or "").strip()
        source_signature = get_text_signature(current_source)
        # ------------------------------------------------------------------
        # PROJECT INTEGRITY / FINAL REVIEW — read-only whole-manuscript QC.
        # This never changes current_draft_output and never applies fixes automatically.
        # ------------------------------------------------------------------
        if project_integrity_review_applies():
            st.subheader("🛡️ Project Integrity / Final Review")
            st.caption(
                "Whole-manuscript quality control before Final Output. It checks continuity, names, timeline, "
                "repetition, POV/tense drift, unresolved placeholders, missing/duplicate sections, structure, "
                "and other inconsistencies. This review does not rewrite or alter your manuscript."
            )

            integrity_is_current = bool(
                str(st.session_state.get("project_integrity_report") or "").strip()
                and st.session_state.get("project_integrity_source_signature") == source_signature
            )

            if not integrity_is_current and st.session_state.get("project_integrity_report"):
                st.info("The manuscript has changed since the last Project Integrity review. Run the review again for the current manuscript.")

            review_label = "REFRESH PROJECT INTEGRITY REVIEW" if integrity_is_current else "RUN PROJECT INTEGRITY FINAL REVIEW"
            if st.button(
                review_label,
                key="run_project_integrity_final_review",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Running whole-manuscript Project Integrity review..."):
                    try:
                        integrity_report = run_project_integrity_final_review(current_source)
                    except Exception as exc:
                        st.error(f"Project Integrity review failed: {exc}")
                    else:
                        st.session_state.project_integrity_report = integrity_report
                        st.session_state.project_integrity_source_signature = source_signature
                        first_line = integrity_report.splitlines()[0].strip().upper() if integrity_report else ""
                        integrity_status = "PASS" if "OVERALL STATUS: PASS" in first_line else "WARNINGS"
                        st.session_state.project_integrity_status = integrity_status
                        try:
                            persist_project_integrity_in_current_version(
                                integrity_report, source_signature, integrity_status
                            )
                        except Exception as save_exc:
                            st.error(f"Review completed but could not auto-save: {save_exc}")
                        else:
                            st.success("Project Integrity saved in the current version — no new version created.")
                        st.rerun()

            if integrity_is_current:
                if st.session_state.get("project_integrity_status") == "PASS":
                    st.success("Project Integrity Review: PASS")
                else:
                    st.warning("Project Integrity Review: WARNINGS — review the report before Final Output.")

                st.markdown("**Project Integrity Report:**")
                st.markdown(
                    render_project_integrity_report_html(
                        st.session_state.get("project_integrity_report", "")
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.info("Project Integrity review has not been run on the current manuscript. Final Output remains writer-controlled and is not blocked.")

            st.markdown("---")

        # OPTIONAL PUBLISHER READINESS — format-specific, read-only guidance.
        # No automatic rewriting, manuscript mutation, or extra AI generation.
        st.subheader("📋 Optional Publisher Readiness Review")
        st.caption(
            "Recommended for submission-oriented projects. This review is optional, "
            "does not alter your manuscript, and is not a substitute for an editor or a publisher's guidelines."
        )
        publisher_format = str(get_effective_format_type() or st.session_state.get("format_type") or "").lower()
        publisher_checklists = {
            "picture_book": (
                "Children's Picture Book",
                ["Age-appropriate vocabulary and read-aloud rhythm", "Word count and page/spread pacing", "Illustration placement and page breaks", "Publisher’s special requirements (if any)"],
            ),
            "screenplay": (
                "Screenplay / Film",
                ["Scene headings, action, and dialogue conventions", "Consistent character cues and scene transitions", "Script length and requested screenplay layout", "Logline, synopsis, and submission specifications"],
            ),
            "stage_play": (
                "Stage Play",
                ["Acts/scenes and speaking-character conventions", "Stage directions and production practicality", "Cast list and approximate running time", "Requested dramatic-script submission format"],
            ),
            "audiobook": (
                "Audiobook",
                ["Narration-friendly wording and pronunciation notes", "Chapter/segment breaks and read-aloud pacing", "Rights, credits, and narrator requirements", "Audio production/submission specifications"],
            ),
            "podcast": (
                "Podcast",
                ["Episode and segment structure", "Host/guest cues, transitions, and timing", "Source/rights and production notes", "Platform or producer delivery requirements"],
            ),
            "youtube": (
                "YouTube Short",
                ["Opening hook and concise pacing", "Narration, visual cues, and on-screen wording", "Rights and platform-specific requirements", "Runtime and delivery specifications"],
            ),
            "commercial": (
                "Commercial",
                ["Clear message and call to action", "Claims, permissions, and required disclosures", "Scene/voiceover timing", "Client/platform delivery requirements"],
            ),
            "novel": (
                "Novel / Long-form Fiction",
                ["Opening pages, chapter sequence, and narrative consistency", "Target genre and manuscript length", "Synopsis, query materials, and submission sample", "Requested manuscript layout and house guidelines"],
            ),
            "short_story": (
                "Short Story",
                ["Complete narrative arc and consistent POV/tense", "Market word-count limit", "Requested manuscript and cover-letter format", "Publication rights and submission guidelines"],
            ),
            "standard": (
                "Standard Manuscript",
                ["Consistent headings, sections, and pagination", "Citations, references, and permissions where applicable", "Intended audience and editorial consistency", "Publisher's required file and house style"],
            ),
        }
        if "picture" in publisher_format and "book" in publisher_format:
            checklist_key = "picture_book"
        elif "screenplay" in publisher_format or "film" in publisher_format:
            checklist_key = "screenplay"
        elif "stage" in publisher_format or "dramatic" in publisher_format or "play" in publisher_format:
            checklist_key = "stage_play"
        elif "audio" in publisher_format:
            checklist_key = "audiobook"
        elif "podcast" in publisher_format:
            checklist_key = "podcast"
        elif "youtube" in publisher_format or "shorts" in publisher_format:
            checklist_key = "youtube"
        elif "commercial" in publisher_format:
            checklist_key = "commercial"
        elif "short story" in publisher_format:
            checklist_key = "short_story"
        elif "novel" in publisher_format or "novella" in publisher_format:
            checklist_key = "novel"
        else:
            checklist_key = "standard"
        publisher_label, publisher_points = publisher_checklists[checklist_key]
        with st.expander(f"Publisher Readiness — {publisher_label} (Optional)", expanded=False):
            st.write("**Submission checklist (writer-controlled):**")
            publisher_identity = str(get_active_project_id() or "current")
            checklist_state_key = "_wbs_publisher_review_" + publisher_identity + "_" + checklist_key
            for index, check_text in enumerate(publisher_points):
                st.checkbox(check_text, key=f"{checklist_state_key}_{index}")
            publisher_specific = st.text_area(
                "Publisher’s special requirements (if any)",
                key=f"{checklist_state_key}_requirements",
                help="Record submission standards supplied by the intended publisher. This does not change the manuscript.",
            )
            completed = sum(bool(st.session_state.get(f"{checklist_state_key}_{index}")) for index in range(len(publisher_points)))
            st.caption(f"Checklist: {completed} of {len(publisher_points)} marked reviewed. "
                       "For manuscript continuity and editorial flags, use Project Integrity / Final Review above.")
            if publisher_specific.strip():
                st.info("Publisher-specific requirements recorded for this review. Confirm these manually against the finished submission.")
            st.caption("You may continue to Final Output without completing this optional checklist.")
            
        if checklist_key == "picture_book" and str(st.session_state.get("current_draft_output") or "").strip():
            with st.expander("Picture Book — Illustration & Page Turn Suggestions", expanded=False):
                st.caption("Planning suggestions only. The manuscript and version number are not changed. "
                           "Adjust the exact page breaks and artwork during layout.")
                st.text_area("Suggested picture-book script", value=build_picture_book_cue_script(
                    st.session_state.current_draft_output), height=300,
                    key="wbs_picture_book_cue_preview", disabled=True)

        st.markdown("---")
        if st.button("Proceed to Stage 5 — Final Manuscript", key="wbs_editorial_to_final", type="primary", use_container_width=True):
            wbs_request_stage_change("Isolation Guardrail", export_view=True)
        # Stage 4 ends here. Draft history, download, and final approval belong to Stage 5.
        st.stop()
    st.markdown("---")

    if st.session_state.get("export_view", False):
        st.info("✅ FINAL OUTPUT is ready. Save the final manuscript before downloading or starting a new project.")
    else:
        st.info("This is a working draft. Editorial review does not automatically change or save it; Stage 5 handles final approval and export.")

    if not st.session_state.get("export_view", False):
        st.markdown("## 📝 DRAFT OUTPUT")
        st.caption("This manuscript is still a working draft. Save it to history before downloading or proceeding if you want this draft preserved.")

        draft_save_notice = st.session_state.pop("draft_save_notice_step5", None)
        if isinstance(draft_save_notice, dict):
            notice_type = draft_save_notice.get("type")
            notice_text = draft_save_notice.get("text") or ""
            if notice_type == "success":
                st.success(notice_text)
            elif notice_type == "info":
                st.info(notice_text)
            elif notice_type == "error":
                st.error(notice_text)

        # For specialized formats that do not use the standard manuscript download block below,
        # keep the draft-save control visible here. Standard prose/script formats render it
        # immediately above their download button.
        if is_picture_book_project() or st.session_state.get("format_type") == "Audio Book":
            if st.session_state.get("demo_mode"):
                if st.button("💾 SAVE CURRENT DRAFT 🔒", key="save_current_draft_step5_trial_special", use_container_width=True):
                    full_version_only_notice("Saved Versions")
            else:
                if st.button(
                    "💾 SAVE CURRENT DRAFT",
                    key="save_current_draft_step5_special",
                    type="primary",
                    use_container_width=True,
                ):
                    draft_result = save_manuscript_checkpoint(
                        status="DRAFT",
                        stage_label="Script Lock",
                        source_stage="script_lock_draft",
                    )
                    save_current_project_session_to_supabase()
                    if draft_result.get("status") == "saved":
                        st.session_state.draft_save_notice_step5 = {
                            "type": "success",
                            "text": f"DRAFT — Script Lock — V{draft_result.get('version_number')} saved to version history.",
                        }
                    elif draft_result.get("status") == "unchanged":
                        st.session_state.draft_save_notice_step5 = {
                            "type": "info",
                            "text": f"This DRAFT — Script Lock — V{draft_result.get('version_number')} is already saved.",
                        }
                    else:
                        st.session_state.draft_save_notice_step5 = {
                            "type": "error",
                            "text": "Current draft could not be saved to version history.",
                        }
                    st.rerun()

    if st.session_state.get("export_view", False) and not st.session_state.get("demo_mode"):
        st.markdown("## ✅ FINAL OUTPUT")
        if st.button(
            "💾 SAVE FINAL OUTPUT MANUSCRIPT",
            key="save_final_output_manuscript_step8",
            type="primary",
            use_container_width=True,
        ):
            final_result = save_manuscript_checkpoint(
                status="FINAL",
                stage_label="Manuscript Output",
                source_stage="final_output",
            )
            save_result = save_current_project_session_to_supabase()
            if final_result.get("status") == "saved" and save_result:
                st.success(f"FINAL — Manuscript Output — V{final_result.get('version_number')} saved.")
            elif final_result.get("status") == "unchanged" and save_result:
                st.info(f"FINAL — Manuscript Output — V{final_result.get('version_number')} is already saved.")
            else:
                st.error("Final manuscript could not be saved completely. No manuscript text was changed.")

    if st.session_state.get("format_type") == "Audio Book":
        audiobook_spec = get_audiobook_length_spec()
        audiobook_target_total = int(
            st.session_state.get(
                "audiobook_target_word_count",
                audiobook_spec["default_words"],
            )
        )
        current_audiobook_words = count_words(st.session_state.current_draft_output)

        st.write(
            f"**Audio Book Length:** {st.session_state.get('audiobook_length', '30 Minutes')}  "
            f"| **Target:** {audiobook_target_total:,} words  "
            f"| **Current:** {current_audiobook_words:,} words"
        )

        if current_audiobook_words < audiobook_spec["min_words"]:
            st.warning(
                f"The manuscript is below the recommended minimum of "
                f"{audiobook_spec['min_words']:,} words for the selected length."
            )
        elif current_audiobook_words > audiobook_spec["max_words"]:
            st.warning(
                f"The manuscript is above the recommended maximum of "
                f"{audiobook_spec['max_words']:,} words for the selected length."
            )
        else:
            st.success("The manuscript is within the selected Audio Book word-count range.")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        automatic_output_label = get_automatic_output_label()
        if st.session_state.get("demo_mode"):
            st.subheader(f"📋 {automatic_output_label} Review")
        elif st.session_state.get("export_view", False):
            st.subheader(f"📋 FINAL OUTPUT — {automatic_output_label}")
        else:
            st.subheader(f"📋 DRAFT OUTPUT — {automatic_output_label}")

        # Keep edits in the current working manuscript before a save or stage change.
        draft_editor_key = "final_manuscript_export_view"
        draft_identity = (str(get_active_project_id()),
                          str(st.session_state.get('project_stage') or ''),
                          bool(st.session_state.get('export_view', False)))
        if st.session_state.get('_wbs_stage5_editor_identity') != draft_identity:
            st.session_state[draft_editor_key] = str(st.session_state.current_draft_output or '')
            st.session_state['_wbs_stage5_editor_identity'] = draft_identity

        def _wbs_sync_stage5_manuscript():
            st.session_state.current_draft_output = str(st.session_state.get(draft_editor_key) or '')

        st.text_area(
            "Review Manuscript:",
            height=500,
            key=draft_editor_key,
            on_change=_wbs_sync_stage5_manuscript,
        )
        if not st.session_state.get('export_view', False):
            if st.session_state.get('demo_mode'):
                if st.button('💾 Save This Version 🔒', key='wbs_stage5_revision_trial', use_container_width=True):
                    full_version_only_notice('Saved Versions')
            elif st.button('💾 Save This Version', key='wbs_stage5_revision_save', use_container_width=True):
                _wbs_sync_stage5_manuscript()
                revision = save_stage5_lettered_revision(st.session_state.current_draft_output)
                if revision and revision.get('status') == 'saved':
                    st.success(f"{revision['label']} saved as a separate manuscript revision.")
                elif revision and revision.get('status') == 'unchanged':
                    st.info('This manuscript is already saved as a revision.')
                else:
                    st.error('Revision could not be saved; your text remains in the editor.')

        try:
            if not is_picture_book_project() and st.session_state.get("format_type") != "Audio Book":
                # Stage 5 downloads the current working draft only. Saved versions are managed
                # from the sidebar; there is no version-selection dropdown in the normal workflow.
                current_download_text = str(st.session_state.current_draft_output or "")

                doc = Document()
                doc.add_heading(f"WritersBlock Studios — {automatic_output_label}", level=1)
                doc.add_paragraph(
                    f"Output Status: {'FINAL' if st.session_state.get('export_view', False) else 'DRAFT'}"
                )
                normal_style = doc.styles["Normal"]
                normal_style.font.name = (
                    "Courier New"
                    if st.session_state.get("format_type") in {"Screenplay Outline", "Stage Play / Dramatic Script"}
                    else "Times New Roman"
                )
                normal_style.font.size = Pt(12)
                section = doc.sections[0]
                section.top_margin = Inches(1)
                section.bottom_margin = Inches(1)
                section.left_margin = Inches(1)
                section.right_margin = Inches(1)

                for paragraph in current_download_text.split("\n\n"):
                    clean_paragraph = paragraph.strip()
                    if clean_paragraph:
                        p = doc.add_paragraph(clean_paragraph)
                        p.paragraph_format.space_after = Pt(8)
                        if st.session_state.get("format_type") in {"Novel / Prose", "Short Story", "Novella"}:
                            p.paragraph_format.line_spacing = 2.0
                        elif st.session_state.get("format_type") in {"Screenplay Outline", "Stage Play / Dramatic Script"}:
                            p.paragraph_format.line_spacing = 1.0
                        else:
                            p.paragraph_format.line_spacing = 1.15

                docx_buffer = BytesIO()
                doc.save(docx_buffer)
                docx_bytes = docx_buffer.getvalue()

                project_stem = safe_download_stem(get_project_title_for_display(), "writersblock_project")
                format_stem = safe_download_stem(automatic_output_label, "project_output")
                output_status_stem = "final" if st.session_state.get("export_view", False) else "draft"
                safe_filename = f"{project_stem}_{format_stem}_{output_status_stem}"

                if not st.session_state.get("export_view", False):
                    if st.session_state.get("demo_mode"):
                        if st.button(
                            "💾 SAVE CURRENT DRAFT 🔒",
                            key="save_current_draft_step5_trial",
                            use_container_width=True,
                        ):
                            full_version_only_notice("Saved Versions")
                    else:
                        if st.button(
                            "💾 SAVE CURRENT DRAFT",
                            key="save_current_draft_step5",
                            type="primary",
                            use_container_width=True,
                        ):
                            draft_result = save_manuscript_checkpoint(
                                status="DRAFT",
                                stage_label="Script Lock",
                                source_stage="script_lock_draft",
                            )
                            save_current_project_session_to_supabase()
                            if draft_result.get("status") == "saved":
                                st.session_state.draft_save_notice_step5 = {
                                    "type": "success",
                                    "text": f"DRAFT — Script Lock — V{draft_result.get('version_number')} saved to version history.",
                                }
                            elif draft_result.get("status") == "unchanged":
                                st.session_state.draft_save_notice_step5 = {
                                    "type": "info",
                                    "text": f"This DRAFT — Script Lock — V{draft_result.get('version_number')} is already saved.",
                                }
                            else:
                                st.session_state.draft_save_notice_step5 = {
                                    "type": "error",
                                    "text": "Current draft could not be saved to version history.",
                                }
                            st.rerun()

                if st.session_state.get("demo_mode"):
                    if st.button(
                        f"Download {automatic_output_label} (.docx) 🔒",
                        key="trial_manuscript_printout_notice",
                        type="primary",
                        use_container_width=True,
                    ):
                        full_version_only_notice("Manuscript Printout")
                else:
                    output_download_prefix = "Final" if st.session_state.get("export_view", False) else "Draft"
                    st.download_button(
                        label=f"Download {output_download_prefix} {automatic_output_label} (.docx)",
                        data=docx_bytes,
                        file_name=f"{safe_filename}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True,
                    )

            if st.session_state.get("export_view", False) and is_picture_book_project():
                st.markdown("---")
                st.subheader("🖼️ Children's Picture Book Layout Draft")
                st.markdown("**Illustration & Page Turn Markers**")
                include_picture_book_cues = st.checkbox(
                    "Include [ILLUSTRATION] and [PAGE TURN] planning markers",
                    value=True, key="wbs_picture_book_export_cues",
                )
                prepared_picture_book_script = build_picture_book_cue_script(
                    st.session_state.current_draft_output, include_picture_book_cues)
                st.caption("Markers are planning suggestions, not a finished page design. "
                           "Turn them off for a clean text-only manuscript. Neither choice changes saved versions.")
                if not st.session_state.get("demo_mode"):
                    st.download_button(
                        "Download Picture Book Manuscript (.docx)",
                        data=picture_book_cues_docx_bytes(get_project_title_for_display(), prepared_picture_book_script),
                        file_name=f"{safe_download_stem(get_project_title_for_display(), 'picture_book')}_manuscript.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="wbs_picture_book_cues_download", use_container_width=True,
                    )
                st.caption(
                    "The project type selected in Concept Development automatically controls this output. "
                    "Create the 32-page / 16-spread layout draft, edit story text, and add illustration direction. "
                    "Layout creation is local and does not call Gemini."
                )
                page_size_options = list(PICTURE_BOOK_PAGE_SIZES.keys())
                saved_page_size = str(
                    st.session_state.get("picture_book_page_size")
                    or DEFAULT_PICTURE_BOOK_PAGE_SIZE
                )
                if saved_page_size not in page_size_options:
                    saved_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE

                selected_picture_book_page_size = st.selectbox(
                    "Picture Book Page Size:",
                    page_size_options,
                    index=page_size_options.index(saved_page_size),
                    key="picture_book_page_size",
                    help=(
                        "8.5 x 8.5 uses square pages. 10 x 8 uses wider landscape pages. "
                        "The selected size controls the on-screen spread proportions and layout-draft export."
                    ),
                )

                selected_size_spec = get_picture_book_page_size_spec(
                    selected_picture_book_page_size
                )
                st.caption(
                    f"Each page: {selected_size_spec['page_width']:g}\" × "
                    f"{selected_size_spec['page_height']:g}\". "
                    f"Two-page spread: {selected_size_spec['page_width'] * 2:g}\" × "
                    f"{selected_size_spec['page_height']:g}\"."
                )

                current_picture_book_signature = get_text_signature(
                    st.session_state.current_draft_output
                )
                saved_picture_book_signature = st.session_state.get(
                    "picture_book_layout_source_signature",
                    "",
                )
                layout_is_current = bool(
                    st.session_state.get("picture_book_layout_spreads")
                    and saved_picture_book_signature
                    and saved_picture_book_signature == current_picture_book_signature
                )

                if (
                    st.session_state.get("picture_book_layout_spreads")
                    and not layout_is_current
                ):
                    st.warning(
                        "The manuscript has changed since this layout draft was built. "
                        "Build the layout again before finalizing it."
                    )

                generate_layout_label = (
                    "Rebuild 32-Page Layout — No AI Charge"
                    if st.session_state.get("picture_book_layout_spreads")
                    else "Build 32-Page Layout — No AI Charge"
                )

                if st.button(
                    generate_layout_label,
                    key="generate_picture_book_layout_local",
                    type="primary",
                    use_container_width=True,
                ):
                    require_product_access("safety")

                    if not st.session_state.current_draft_output.strip():
                        st.error("No completed manuscript is available for layout conversion.")
                        st.stop()

                    normalized_layout = build_picture_book_spreads_locally(
                        st.session_state.current_draft_output
                    )
                    st.session_state.picture_book_layout_spreads = normalized_layout
                    st.session_state.picture_book_layout_source_signature = current_picture_book_signature
                    st.session_state.picture_book_layout_preview_id += 1
                    if not st.session_state.get("demo_mode"):
                        save_picture_book_layout_to_supabase(normalized_layout, selected_picture_book_page_size)
                        save_current_project_session_to_supabase()
                    st.rerun()

                if layout_is_current:
                    st.info(
                        "32-page planning structure: 16 editable spreads. "
                        "Each spread can use a different standard layout template."
                    )

                    edited_spreads = []
                    for spread in normalize_picture_book_spreads(
                        st.session_state.picture_book_layout_spreads
                    ):
                        spread_number = spread["spread_number"]
                        with st.expander(
                            f"Spread {spread_number} — Pages {spread['pages']}",
                            expanded=(spread_number == 1),
                        ):
                            template = st.selectbox(
                                "Text / Image Position Template:",
                                PICTURE_BOOK_LAYOUT_TEMPLATES,
                                index=PICTURE_BOOK_LAYOUT_TEMPLATES.index(spread["template"])
                                if spread["template"] in PICTURE_BOOK_LAYOUT_TEMPLATES
                                else 0,
                                key=f"picture_book_template_{st.session_state.picture_book_layout_preview_id}_{spread_number}",
                            )
                            render_picture_book_template_preview(template, selected_picture_book_page_size)

                            story_text = st.text_area(
                                "Story Text for This Spread:",
                                value=spread.get("story_text", ""),
                                height=130,
                                key=f"picture_book_text_{st.session_state.picture_book_layout_preview_id}_{spread_number}",
                            )

                            illustration_direction = st.text_area(
                                "Illustration Direction:",
                                value=spread.get("illustration_direction", ""),
                                height=110,
                                key=f"picture_book_illustration_{st.session_state.picture_book_layout_preview_id}_{spread_number}",
                            )


                            edited_spreads.append({
                                "spread_number": spread_number,
                                "pages": spread["pages"],
                                "template": template,
                                "story_text": story_text.strip(),
                                "illustration_direction": illustration_direction.strip(),
                            })

                    st.session_state.picture_book_layout_spreads = edited_spreads

                    if st.button(
                        "Save Picture Book Layout Draft 💾",
                        key="save_picture_book_layout_edits",
                        use_container_width=True,
                    ):
                        if st.session_state.get("demo_mode"):
                            full_version_only_notice("Saved Projects")
                        else:
                            result = save_picture_book_layout_to_supabase(edited_spreads, selected_picture_book_page_size)
                            if result:
                                st.session_state.picture_book_layout_preview_id += 1
                                save_current_project_session_to_supabase()
                                st.success("Children's Picture Book layout draft saved.")
                                st.rerun()

                    picture_book_docx_bytes = build_picture_book_layout_docx_bytes(
                        get_project_title_for_display(),
                        edited_spreads,
                        selected_picture_book_page_size,
                    )
                    picture_book_stem = safe_download_stem(
                        get_project_title_for_display(),
                        "children_picture_book",
                    )

                    if st.session_state.get("demo_mode"):
                        if st.button(
                            "Download Picture Book Layout Draft (.docx) 🔒",
                            key="trial_picture_book_layout_download_notice",
                            type="primary",
                            use_container_width=True,
                        ):
                            full_version_only_notice("Manuscript Printout")
                    else:
                        st.download_button(
                            label="Download Picture Book Layout Draft (.docx)",
                            data=picture_book_docx_bytes,
                            file_name=f"{picture_book_stem}_layout_draft.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            type="primary",
                            use_container_width=True,
                        )

            if (
                st.session_state.get("export_view", False)
                and st.session_state.get("format_type") == "Audio Book"
            ):
                st.markdown("---")
                st.subheader("🎙️ Audiobook Theatre Production Layout")
                st.caption(
                    "The Audio Book project type automatically outputs an Audiobook Theatre Production Script. "
                    "There is no alternate output-format selector."
                )

                selected_cue_level = st.selectbox(
                    "Production Cue Level:",
                    [
                        "Clean Voices Only",
                        "Voices + Minimal SFX",
                        "Full Audiobook Theatre Cues",
                    ],
                    index=[
                        "Clean Voices Only",
                        "Voices + Minimal SFX",
                        "Full Audiobook Theatre Cues",
                    ].index(
                        st.session_state.get(
                            "audiobook_production_cue_level",
                            "Voices + Minimal SFX",
                        )
                        if st.session_state.get(
                            "audiobook_production_cue_level",
                            "Voices + Minimal SFX",
                        ) in [
                            "Clean Voices Only",
                            "Voices + Minimal SFX",
                            "Full Audiobook Theatre Cues",
                        ]
                        else "Voices + Minimal SFX"
                    ),
                    key="audiobook_production_cue_level_select",
                )

                current_production_source_signature = get_text_signature(
                    st.session_state.current_draft_output
                )
                saved_production_signature = st.session_state.get(
                    "audiobook_production_source_signature",
                    "",
                )
                production_script_is_current = bool(
                    st.session_state.get("audiobook_production_script", "").strip()
                    and saved_production_signature
                    and saved_production_signature == current_production_source_signature
                )

                if (
                    st.session_state.get("audiobook_production_script", "").strip()
                    and not production_script_is_current
                ):
                    st.warning(
                        "The manuscript has changed since this production script was generated. "
                        "Generate it again before downloading or recording."
                    )

                production_button_label = (
                    "Refresh Production Script 🎙️"
                    if st.session_state.get("audiobook_production_script", "").strip()
                    else "Generate Production Script 🎙️"
                )

                if st.button(
                    production_button_label,
                    key="generate_audiobook_production_script",
                    type="primary",
                    use_container_width=True,
                ):
                    require_product_access("safety")

                    if not st.session_state.current_draft_output.strip():
                        st.error("No current manuscript is available for production conversion.")
                        st.stop()

                    with st.spinner("Converting the manuscript into an Audiobook Theatre production layout..."):
                        try:
                            production_output = st.session_state.backend.run_rewrite_engine(
                                source_text=st.session_state.current_draft_output,
                                rewrite_mode="Direct Script Change / Obey My Instructions Exactly",
                                scene_choice="Full Manuscript",
                                custom_instruction=get_audiobook_production_instruction(
                                    selected_cue_level
                                ),
                                target_length="Keep Current Length",
                                custom_target_word_count=None,
                                tone_style=st.session_state.tone_style,
                                author_style=st.session_state.author_style,
                            )
                        except Exception as e:
                            st.error(f"Production layout conversion failed: {e}")
                            st.stop()

                    if not ai_output_is_usable(production_output):
                        st.error(
                            "The production layout conversion did not return usable text. "
                            "The manuscript was not changed and no production script was saved."
                        )
                        st.stop()

                    st.session_state.audiobook_production_script = str(production_output).strip()
                    st.session_state.audiobook_production_source_signature = (
                        current_production_source_signature
                    )
                    st.session_state.audiobook_production_cue_level = selected_cue_level
                    st.session_state.audiobook_production_preview_id += 1

                    project_id = get_active_project_id()
                    if project_id:
                        save_project_draft_to_supabase(
                            project_id=project_id,
                            draft_title="Audiobook Theatre Production Script",
                            draft_type="audiobook_production_script",
                            draft_content=st.session_state.audiobook_production_script,
                        )

                    save_current_project_session_to_supabase()
                    st.rerun()

                if production_script_is_current:
                    edited_production_script = st.text_area(
                        "Review / Edit Production Script:",
                        value=st.session_state.audiobook_production_script,
                        height=500,
                        key=(
                            "audiobook_production_script_editor_"
                            f"{st.session_state.audiobook_production_preview_id}"
                        ),
                    )
                    st.session_state.audiobook_production_script = edited_production_script
                    st.caption(
                        f"Production Script Words: "
                        f"{count_words(st.session_state.audiobook_production_script):,}"
                    )

                    if st.button(
                        "Save Production Script Edits 💾",
                        key="save_audiobook_production_edits",
                        use_container_width=True,
                    ):
                        project_id = get_active_project_id()
                        if project_id:
                            save_project_draft_to_supabase(
                                project_id=project_id,
                                draft_title="Audiobook Theatre Production Script - Edited",
                                draft_type="audiobook_production_script",
                                draft_content=st.session_state.audiobook_production_script,
                            )
                        save_current_project_session_to_supabase()
                        st.success("Production script edits saved.")

                    project_stem = safe_download_stem(
                        get_project_title_for_display(),
                        "audiobook",
                    )
                    production_docx_bytes = build_audiobook_production_docx_bytes(
                        get_project_title_for_display(),
                        st.session_state.audiobook_production_script,
                    )

                    if st.session_state.get("demo_mode"):
                        if st.button(
                            "Download Audiobook Theatre Production Script (.docx) 🔒",
                            key="trial_audiobook_printout_notice",
                            type="primary",
                            use_container_width=True,
                        ):
                            full_version_only_notice("Manuscript Printout")
                    else:
                        st.download_button(
                            label="Download Final Audiobook Theatre Production Script (.docx)",
                            data=production_docx_bytes,
                            file_name=(
                                f"{project_stem}_audiobook_theatre_production_script.docx"
                            ),
                            mime=(
                                "application/vnd.openxmlformats-officedocument."
                                "wordprocessingml.document"
                            ),
                            type="primary",
                            use_container_width=True,
                        )

            if can_use_rewrite:
                if st.button(
                    "Proceed to Script Rewrite 🛠️",
                    key="proceed_to_rewrite_from_export",
                    type="primary",
                    use_container_width=True,
                ):
                    wbs_request_stage_change("Rewrite Engine")
            else:
                st.button(
                    "🔒 Script Rewrite Locked",
                    key="rewrite_locked_from_export",
                    disabled=True,
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f"Failed to generate Word document: {e}")

    with col_right:
        st.subheader("📊 Output Summary")

        compiled_scene_count = len([
            scene_text
            for scene_text in st.session_state.get("scene_blocks", {}).values()
            if str(scene_text or "").strip()
        ])

        if compiled_scene_count == 0 and str(st.session_state.get("current_draft_output", "")).strip():
            compiled_scene_count = max(int(st.session_state.get("current_processing_beat", 1) or 1) - 1, 1)

        st.metric(
            label="Script Blocks Compiled",
            value=f"{compiled_scene_count}",
        )

        st.markdown("**Project Memory Cache:**")

        st.text_area(
            "Saved Project Memory:",
            value=st.session_state.rolling_lore_book,
            height=200,
            key="final_lore_view",
            disabled=True,
        )

        st.write("---")
        st.subheader("🗂️ Saved Versions")

        if st.session_state.get("demo_mode"):
            st.caption("Saved Versions are available in the full Writer Edition.")
            if st.button("Open Saved Versions 🔒", key="trial_output_saved_versions_notice", use_container_width=True):
                full_version_only_notice("Saved Versions")
        else:
            saved_version_count = len(get_manuscript_versions_for_current_project())
            st.caption(f"Saved manuscript versions: {saved_version_count}")
            st.caption("Use Saved Version Manager in the sidebar when you want to review, restore, download, or delete a saved version.")

        st.write("---")

        if st.button("🔄 Start New Project", use_container_width=True):
            wbs_clear_new_project_ui_state()
            st.session_state.project_title = ""
            st.session_state.current_project_id = None
            for _key in ("_wbs_loaded_project_id", "_wbs_loaded_project_title", "_wbs_loaded_saved_session_id",
                         "_wbs_loaded_manuscript_version_id", "wbs_locked_format_id", "_wbs_locked_project_id"):
                st.session_state.pop(_key, None)
            st.session_state.project_version_name = "Original"
            st.session_state.project_stage = "Intake"
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
            st.session_state.sandbox_slates = None
            st.session_state.chosen_option = None
            st.session_state.chosen_option_text = None
            st.session_state.plot_outline = None
            st.session_state.current_draft_output = ""
            st.session_state.rolling_lore_book = ""
            st.session_state.completed_beats = []
            st.session_state.scene_blocks = {}
            st.session_state.current_processing_beat = 1
            st.session_state.rewritten_manuscript = ""
            st.session_state.rewrite_applied_message = ""
            st.session_state.audiobook_production_script = ""
            st.session_state.audiobook_production_source_signature = ""
            st.session_state.audiobook_production_preview_id = 0
            st.session_state.picture_book_layout_spreads = []
            st.session_state.picture_book_layout_source_signature = ""
            st.session_state.picture_book_layout_preview_id = 0
            st.session_state.picture_book_page_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
            st.session_state.manuscript_version = 0
            st.session_state.current_manuscript_save_status = ""
            st.session_state.current_manuscript_save_stage = ""
            st.session_state.current_manuscript_save_version = 0
            st.session_state.export_view = False
            st.session_state.show_saved_version_manager = False
            st.rerun()

    if st.session_state.get("export_view", False) and st.session_state.get("show_saved_version_manager", False):
        if st.session_state.get("demo_mode"):
            st.markdown("---")
            st.subheader("🗂️ Saved Version Manager")
            st.caption("Saved Versions remain visible during the trial and unlock with the full Writer Edition.")
            if st.button("Open Saved Version Manager 🔒", key="trial_saved_version_manager_page_notice", use_container_width=True):
                full_version_only_notice("Saved Versions")
        else:
            st.markdown("---")
            st.subheader("🗂️ Saved Version Manager")
            st.caption(
                "Review saved manuscript versions here. Nothing changes unless you choose Restore or Delete. "
                "Delete removes only the selected saved version after confirmation."
            )

            manager_versions = get_manuscript_versions_for_current_project()

            if not manager_versions:
                st.info("No saved manuscript versions found yet.")
            else:
                manager_items = []

                for version in manager_versions:
                    project_join = version.get("writersblock_projects") or {}
                    if isinstance(project_join, dict):
                        project_title_for_version = project_join.get("project_title")
                    else:
                        project_title_for_version = None

                    title = str(
                        project_title_for_version
                        or version.get("project_title")
                        or get_project_title_for_display()
                    ).strip()

                    version_number = int(version.get("version_number") or 1)
                    created_at = version.get("created_at")
                    word_count = count_words(version.get("manuscript_content", ""))
                    status, stage_label = get_manuscript_version_status_stage(version)
                    label_text = str(version.get("version_label") or "Saved Version").strip()
                    display_label = f"{title} — {status} V{version_number} — {word_count} words"

                    manager_items.append({
                        "label": display_label,
                        "version": version,
                        "title": title,
                        "version_number": version_number,
                        "word_count": word_count,
                        "label_text": label_text,
                    })

                manager_labels = [item["label"] for item in manager_items]
                manager_lookup = {item["label"]: item for item in manager_items}

                selected_manager_label = st.selectbox(
                    "Saved versions:",
                    manager_labels,
                    key=f"saved_version_manager_selector_{st.session_state.get('current_project_id')}",
                )

                selected_manager_item = manager_lookup.get(selected_manager_label)
                selected_manager_version = selected_manager_item["version"] if selected_manager_item else None
                selected_manager_text = str(selected_manager_version.get("manuscript_content") or "") if selected_manager_version else ""

                st.text_area(
                    "Selected Version Review:",
                    value=selected_manager_text,
                    height=520,
                    key=f"saved_version_manager_review_box_{st.session_state.get('current_project_id')}",
                    disabled=True,
                )

                col_download, col_restore, col_delete = st.columns(3)

                with col_download:
                    try:
                        version_doc = Document()
                        version_doc.add_heading(f"WritersBlock Studios Manuscript - {selected_manager_item['label']}", level=1)

                        for paragraph in selected_manager_text.split("\n\n"):
                            clean_paragraph = paragraph.strip()
                            if clean_paragraph:
                                p = version_doc.add_paragraph(clean_paragraph)
                                p.paragraph_format.space_after = Pt(8)
                                p.paragraph_format.line_spacing = 1.15

                        version_buffer = BytesIO()
                        version_doc.save(version_buffer)

                        st.download_button(
                            label="Download Selected Version",
                            data=version_buffer.getvalue(),
                            file_name=f"saved_version_v{selected_manager_item['version_number']}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Selected version download unavailable: {e}")

                with col_restore:
                    restore_confirmed = st.checkbox(
                        "Confirm restore",
                        key=f"confirm_restore_selected_version_{st.session_state.get('current_project_id')}",
                    )

                    if st.button(
                        "Restore Selected Version",
                        key=f"restore_selected_saved_version_{st.session_state.get('current_project_id')}",
                        disabled=not restore_confirmed,
                        use_container_width=True,
                    ):
                        st.session_state.current_draft_output = selected_manager_text
                        st.session_state.current_project_id = selected_manager_version.get("project_id")
                        st.session_state.project_title = selected_manager_item.get("title") or get_project_title_for_display()
                        st.session_state.manuscript_version = int(selected_manager_version.get("version_number") or st.session_state.get("manuscript_version", 0) or 0)
                        st.session_state.rewritten_manuscript = ""
                        st.session_state.rewrite_applied_message = "Selected saved version restored as the current manuscript."
                        save_current_project_session_to_supabase()
                        st.success("Selected saved version restored as the current manuscript.")
                        st.rerun()

                with col_delete:
                    delete_confirmed = st.checkbox(
                        "I understand this will permanently delete the selected saved version.",
                        key=f"confirm_delete_selected_version_{st.session_state.get('current_project_id')}",
                    )

                    if st.button(
                        "Delete Selected Version",
                        key=f"delete_selected_saved_version_{st.session_state.get('current_project_id')}",
                        disabled=not delete_confirmed,
                        use_container_width=True,
                    ):
                        delete_manuscript_version_ids([selected_manager_version.get("id")])
                        st.success("Selected saved version deleted.")
                        st.rerun()
# ======================================================================================
# PHASE 6: SCRIPT POLISH
# ======================================================================================
if st.session_state.project_stage == "Revision Engine":
    require_product_access("revision")

    st.header("🧠 Stage 4: Optional Script Polish")
    render_project_title_banner("step_6_script_polish")
    st.markdown("##### Review the manuscript for continuity, pacing, tone, and polish opportunities.")
    st.markdown("---")

    if not st.session_state.current_draft_output.strip():
        st.warning("No manuscript draft found. Return to Creative Draft and complete drafting first.")
    else:
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📄 Script Under Review")

            st.text_area(
                "Current Manuscript:",
                value=st.session_state.current_draft_output,
                height=500,
                label_visibility="collapsed",
                disabled=True,
            )

        with col_right:
            st.subheader("🔍 Polish Tools")

            revision_mode = st.selectbox(
                "Choose Polish Pass:",
                [
                    "Continuity Check",
                    "Pacing Check",
                    "Tone & Style Check",
                    "Character Consistency Check",
                    "Scene Expansion Suggestions",
                    "Final Polish Pass",
                ],
            )

            if st.button("Run Script Polish 🧠", key="run_revision_pass", type="primary", use_container_width=True):
                require_product_access("revision")
                with st.spinner("Running polish analysis..."):
                    if create_bridge_adapter is None:
                        st.error(
                            "WritersBlock Model is unavailable. "
                            f"{WBS_MODEL_IMPORT_ERROR}"
                        )
                        st.stop()

                    _wbs_polish_bridge = create_bridge_adapter(
                        backend=st.session_state.backend
                    )
                    _wbs_polish_result = _wbs_polish_bridge.execute(
                        "Run Script Polish",
                        st.session_state,
                        prepared_context={
                            "effective_format_type": get_effective_format_type(),
                            "format_development_context": get_full_project_continuity_context(),
                            "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                            "quill_template_context": refresh_quill_template_context(),
                        },
                        action_payload={
                            "revision_mode": revision_mode,
                            "tone_style": st.session_state.tone_style,
                            "author_style": st.session_state.author_style,
                        },
                    )

                    if not _wbs_polish_result.success:
                        st.error(
                            "WritersBlock Model Bridge could not run Script Polish. "
                            + (_wbs_polish_result.error or "Unknown bridge error.")
                        )
                        st.stop()

                    revision_report = _wbs_polish_result.output
                    st.session_state.revision_report = revision_report
                    st.session_state["_wbs_agent_bridge_last_operation"] = (
                        _wbs_polish_result.backend_operation or ""
                    )
                    st.session_state["_wbs_agent_bridge_last_success"] = True
                    st.rerun()

            st.markdown("---")

            if "revision_report" not in st.session_state:
                st.session_state.revision_report = ""

            st.text_area(
                "Polish Report:",
                value=st.session_state.revision_report,
                height=300,
                label_visibility="collapsed",
                disabled=True,
            )

            if can_use_rewrite:
                if st.button("Proceed to Script Rewrite 🛠️", key="proceed_to_rewrite_from_revision", type="primary", use_container_width=True):
                    wbs_request_stage_change("Rewrite Engine")
            else:
                st.button("🔒 Script Rewrite Locked", key="rewrite_locked_from_revision", disabled=True, use_container_width=True)
# ============================================================
# PHASE 7: SCRIPT REWRITE
# ============================================================
elif st.session_state.project_stage == "Rewrite Engine":
    require_product_access("rewrite")

    st.header("🛠️ Stage 4: Optional Script Rewrite")
    render_project_title_banner("step_7_script_rewrite")
    st.markdown("##### Script Rewrite uses the current live manuscript only. Saved versions are available for download, but are not used as the script rewrite source.")
    st.markdown("---")

    if "rewritten_manuscript" not in st.session_state:
        st.session_state.rewritten_manuscript = ""

    if "rewrite_preview_id" not in st.session_state:
        st.session_state.rewrite_preview_id = 0

    if "rewrite_target_length" not in st.session_state:
        st.session_state.rewrite_target_length = "Keep Current Length"

    manuscript_text = st.session_state.get("current_draft_output", "")

    def split_text_into_scene_chunks(full_text, total_scenes=4):
        full_text = str(full_text or "").strip()
        if not full_text:
            return []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]
        if not paragraphs:
            return [full_text]

        total_scenes = max(1, int(total_scenes or 1))
        chunk_size = max(1, (len(paragraphs) + total_scenes - 1) // total_scenes)

        chunks = []
        for i in range(total_scenes):
            start_idx = i * chunk_size
            end_idx = min(len(paragraphs), (i + 1) * chunk_size)
            if start_idx < len(paragraphs):
                chunks.append("\n\n".join(paragraphs[start_idx:end_idx]).strip())

        return chunks

    def get_scene_beat_text(full_text, beat_number):
        scene_blocks = st.session_state.get("scene_blocks", {})
        stored_scene = scene_blocks.get(int(beat_number)) if isinstance(scene_blocks, dict) else None
        if stored_scene and str(stored_scene).strip():
            return str(stored_scene).strip()

        chunks = split_text_into_scene_chunks(full_text, 4)
        idx = int(beat_number) - 1
        if 0 <= idx < len(chunks):
            return chunks[idx]
        return ""

    def replace_scene_beat_text(full_text, beat_number, replacement_text):
        full_text = str(full_text or "")
        replacement_text = str(replacement_text or "").strip()

        scene_blocks = st.session_state.get("scene_blocks", {})
        stored_scene = None

        if isinstance(scene_blocks, dict):
            stored_scene = scene_blocks.get(int(beat_number))

        if stored_scene and str(stored_scene).strip() and str(stored_scene).strip() in full_text:
            st.session_state.scene_blocks[int(beat_number)] = replacement_text
            return full_text.replace(str(stored_scene).strip(), replacement_text, 1)

        current_scene_text = get_scene_beat_text(full_text, beat_number)
        if current_scene_text and current_scene_text in full_text:
            if isinstance(scene_blocks, dict):
                st.session_state.scene_blocks[int(beat_number)] = replacement_text
            return full_text.replace(current_scene_text, replacement_text, 1)

        return full_text

    def strip_internal_notices(text):
        text = str(text or "")
        text = re.sub(r"\n?\[LOCAL NODE 8 FALLBACK NOTE:.*?\]", "", text, flags=re.DOTALL)
        text = re.sub(r"\n?\[LOCAL .*?FALLBACK NOTE:.*?\]", "", text, flags=re.DOTALL)
        text = re.sub(r"\n?NODE 8 TEST OUTPUT.*", "", text, flags=re.DOTALL)
        return text.strip()

    if not manuscript_text.strip():
        st.warning("No manuscript draft found. Return to Creative Draft and complete drafting first.")
    else:
        col_left, col_right = st.columns([2, 1])

        with col_right:
            st.subheader("🛠️ Script Rewrite Controls")

            rewrite_mode = st.selectbox(
                "1) Script Rewrite Mode:",
                [
                    "Creative Script Rewrite / Improve Scene",
                    "Direct Script Change / Obey My Instructions Exactly",
                    "Polish Only / Do Not Change Story",
                ],
                key="rewrite_mode_select",
            )

            scene_choice = st.selectbox(
                "2) Script Rewrite Location:",
                [
                    "Full Manuscript",
                    "Scene Beat 1",
                    "Scene Beat 2",
                    "Scene Beat 3",
                    "Scene Beat 4",
                ],
                key="rewrite_scene_choice",
            )

            rewrite_target_length = st.selectbox(
                "3) Target Length:",
                [
                    "Keep Current Length",
                    "Condense for Tighter Pacing",
                    "Expand to 400 Words",
                    "Custom Word Count",
                ],
                key="rewrite_target_length",
            )

            custom_target_word_count = None

            if rewrite_target_length == "Custom Word Count":
                custom_target_word_count = st.number_input(
                    "Custom Target Word Count:",
                    min_value=50,
                    max_value=2500,
                    value=min(1200, max(50, count_words(st.session_state.current_draft_output))),
                    step=25,
                    key="custom_target_word_count",
                )

            current_project_dialogue_style = get_dialogue_style()
            rewrite_dialogue_options = [
                f"Use Current Project Dialogue Style — {get_dialogue_style_display(current_project_dialogue_style)}",
                *DIALOGUE_STYLE_OPTIONS,
            ]

            rewrite_dialogue_choice = st.selectbox(
                "4) Dialogue Style for Rewrite:",
                rewrite_dialogue_options,
                index=0,
                key="rewrite_dialogue_style_choice",
                format_func=(
                    lambda option: get_dialogue_style_display(option)
                    if option in DIALOGUE_STYLE_OPTIONS
                    else option
                ),
                help=(
                    "Percentages are approximate spoken-dialogue targets. Default preserves the project's "
                    "current Dialogue Style. Choose another option only when you intentionally want this rewrite "
                    "to use a different dialogue/narration balance."
                ),
            )

            st.caption(
                f"Current Project Dialogue Style: {get_dialogue_style_display(current_project_dialogue_style)}. "
                "The selected project type remains locked and controls dialogue formatting."
            )

            custom_rewrite_instruction = st.text_area(
                "5) Specific Script Rewrite Direction - Optional:",
                value="",
                height=160,
                placeholder=(
                    "Example: Keep the same ending, but expand the story with stronger atmosphere, "
                    "more antique shop detail, more dread, and more of Elias's physical decline."
                ),
                key="custom_rewrite_instruction",
            )

            st.markdown("---")
            st.info(
                "Script Rewrite uses only the current live manuscript shown on this page. "
                "Saved versions are not used as the script rewrite source. "
                "Dialogue Style defaults to the current project setting unless you deliberately choose a rewrite override above."
            )

        if scene_choice == "Full Manuscript":
            selected_source_text = manuscript_text
        else:
            beat_number = int(scene_choice.replace("Scene Beat ", ""))
            selected_source_text = get_scene_beat_text(manuscript_text, beat_number)

        with col_left:
            st.subheader("📄 Editable Source Text")

            edited_source_text = st.text_area(
                "Edit selected source text before script rewrite:",
                value=selected_source_text,
                height=500,
                key=f"editable_rewrite_source_{scene_choice.replace(' ', '_')}_{st.session_state.manuscript_version}",
            )

            st.caption(f"Selected Source Words: {count_words(edited_source_text)}")
            st.caption("Save a manual change as a new draft version, or run an optional AI rewrite below.")
            if st.session_state.get("demo_mode"):
                st.button("💾 Save This Version 🔒", key="rewrite_manual_save_locked", disabled=True, use_container_width=True)
            elif st.button("💾 Save This Version", key="rewrite_manual_save", use_container_width=True):
                if not str(edited_source_text or "").strip():
                    st.error("There is no revised text to save.")
                else:
                    if scene_choice == "Full Manuscript":
                        updated_manuscript = str(edited_source_text).strip()
                    else:
                        updated_manuscript = replace_scene_beat_text(
                            st.session_state.current_draft_output,
                            int(scene_choice.replace("Scene Beat ", "")),
                            str(edited_source_text).strip(),
                        )
                    if updated_manuscript == st.session_state.current_draft_output:
                        st.info("No changes to save. Your current manuscript is preserved.")
                    else:
                        previous_manuscript = st.session_state.current_draft_output
                        st.session_state.current_draft_output = updated_manuscript
                        try:
                            saved = save_manuscript_checkpoint(
                                status="DRAFT", stage_label="Script Rewrite Manual Edit",
                                source_stage="script_rewrite_manual_edit",
                            )
                        except Exception as exc:
                            st.session_state.current_draft_output = previous_manuscript
                            st.error(f"Version save failed: {exc}")
                        else:
                            if saved.get("status") == "saved":
                                st.success("Edited manuscript saved as a new version. Earlier manuscript versions remain available.")
                                save_current_project_session_to_supabase()
                            else:
                                st.session_state.current_draft_output = previous_manuscript
                                st.error("The edited manuscript was not saved; the previously active text has been restored.")
            st.markdown("---")

            if st.button(
                "Run Script Rewrite 🛠️",
                key="run_rewrite_engine",
                type="primary",
                use_container_width=True,
            ):
                require_product_access("rewrite")

                if not edited_source_text.strip():
                    st.error("No source text selected for script rewrite.")
                else:
                    with st.spinner("Running script rewrite..."):
                        try:

                            effective_custom_rewrite_instruction = custom_rewrite_instruction.strip()

                            # STEP 7 ONLY — natural-language Quill handoff.
                            # Example: "Use the modified Quill intro in the rewrite."
                            # Quill may discuss/recommend changes anywhere, but manuscript
                            # changes remain controlled here in Script Rewrite.
                            if "quill" in effective_custom_rewrite_instruction.lower():
                                quill_creative_suggestion = str(
                                    st.session_state.get(
                                        "_wbs_quill_last_creative_suggestion", ""
                                    )
                                    or ""
                                ).strip()

                                if not quill_creative_suggestion:
                                    st.warning(
                                        "No recent Quill creative revision is available in this session. "
                                        "Ask Quill for the revision first, then return to Step 7 and run the rewrite."
                                    )
                                    st.stop()

                                effective_custom_rewrite_instruction = (
                                    effective_custom_rewrite_instruction
                                    + "\n\nQUILL CREATIVE SUGGESTION REFERENCED BY THE WRITER:\n"
                                    + quill_creative_suggestion
                                    + "\n\nApply that Quill material only within the selected Script Rewrite Location. "
                                    "Preserve all other scenes/beats and the balance of the existing manuscript."
                                )

                            rewrite_instruction_packet = (
                                get_rewrite_dialogue_instruction(rewrite_dialogue_choice)
                                + "\n\nADDITIONAL CREATOR REWRITE DIRECTION:\n"
                                + (
                                    effective_custom_rewrite_instruction
                                    if effective_custom_rewrite_instruction
                                    else "No additional rewrite direction provided."
                                )
                            )

                            if create_bridge_adapter is None:
                                raise RuntimeError(
                                    "WritersBlock Model is unavailable. "
                                    + WBS_MODEL_IMPORT_ERROR
                                )

                            _wbs_rewrite_bridge = create_bridge_adapter(
                                backend=st.session_state.backend
                            )
                            _wbs_rewrite_result = _wbs_rewrite_bridge.execute(
                                "Rewrite this manuscript",
                                st.session_state,
                                prepared_context={
                                    "effective_format_type": get_effective_format_type(),
                                    "format_development_context": get_full_project_continuity_context(),
                                    "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                                    "quill_template_context": refresh_quill_template_context(),
                                },
                                action_payload={
                                    "source_text": edited_source_text,
                                    "backend_rewrite_mode": rewrite_mode,
                                    "scene_choice": scene_choice,
                                    "custom_instruction": rewrite_instruction_packet,
                                    "target_length": rewrite_target_length,
                                    "custom_target_word_count": custom_target_word_count,
                                    "tone_style": st.session_state.tone_style,
                                    "author_style": st.session_state.author_style,
                                },
                            )

                            if not _wbs_rewrite_result.success:
                                raise RuntimeError(
                                    _wbs_rewrite_result.error
                                    or "WritersBlock Model Bridge returned no rewrite."
                                )

                            st.session_state.rewritten_manuscript = _wbs_rewrite_result.output
                            st.session_state["_wbs_agent_bridge_last_operation"] = (
                                _wbs_rewrite_result.backend_operation or ""
                            )
                            st.session_state["_wbs_agent_bridge_last_success"] = True
                            st.session_state.rewrite_preview_id += 1



                        except Exception as e:
                            st.session_state.rewritten_manuscript = (
                                "Script rewrite fallback output.\n\n"
                                f"Backend error: {e}\n\n"
                                "The script rewrite request was received, but the AI backend did not return usable text."
                            )
                            st.session_state.rewrite_preview_id += 1

                        st.rerun()

            # WBS_SKIP_REWRITE_TO_FINAL_2026_09_07
            st.caption(
                "If you are satisfied with the current manuscript, skip rewriting and proceed unchanged. "
                "No AI rewrite is run and no rewrite credits are used."
            )
            if st.button(
                "SKIP REWRITE — PROCEED TO FINAL OUTPUT ➡️",
                key="skip_rewrite_to_final_output",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.rewritten_manuscript = ""
                st.session_state.rewrite_applied_message = (
                    "Rewrite skipped. Current manuscript preserved unchanged."
                )
                wbs_request_stage_change("Isolation Guardrail", export_view=True)


        st.markdown("---")
        st.subheader("✍️ Script Rewrite Output")

        st.text_area(
            "Script Rewrite Output:",
            value=st.session_state.rewritten_manuscript,
            height=450,
            label_visibility="collapsed",
            key=f"rewrite_output_preview_{st.session_state.rewrite_preview_id}",
        )

        preview_words = count_words(st.session_state.rewritten_manuscript)
        if st.session_state.rewritten_manuscript.strip():
            st.caption(f"Script Rewrite Preview Words: {preview_words}")

        if st.session_state.rewrite_applied_message:
            st.success(st.session_state.rewrite_applied_message)

        preview_is_safe_to_apply = (
            st.session_state.rewritten_manuscript.strip()
            and "Script rewrite fallback output" not in st.session_state.rewritten_manuscript
            and "Backend error:" not in st.session_state.rewritten_manuscript
        )

        if st.session_state.rewritten_manuscript.strip() and not preview_is_safe_to_apply:
            st.error("This script rewrite preview could not be used. Please run the script rewrite again.")

        if preview_is_safe_to_apply:
            if st.button(
                "Apply Script Rewrite to Full Manuscript ✅",
                key="apply_rewrite_to_manuscript",
                type="primary",
                use_container_width=True,
            ):
                cleaned_rewrite_for_manuscript = strip_internal_notices(st.session_state.rewritten_manuscript)

                if scene_choice == "Full Manuscript":
                    st.session_state.current_draft_output = cleaned_rewrite_for_manuscript
                    st.session_state.rewrite_applied_message = "Full manuscript replaced with script rewrite version."
                else:
                    beat_number = int(scene_choice.replace("Scene Beat ", ""))
                    st.session_state.current_draft_output = replace_scene_beat_text(
                        st.session_state.current_draft_output,
                        beat_number,
                        cleaned_rewrite_for_manuscript,
                    )
                    st.session_state.rewrite_applied_message = f"{scene_choice} script rewrite applied to the full manuscript."

                st.session_state.rewritten_manuscript = ""
                rewrite_checkpoint = save_manuscript_checkpoint(
                    status="DRAFT",
                    stage_label="Script Rewrite",
                    source_stage="script_rewrite_draft",
                )
                st.session_state.rewrite_preview_id += 1

                save_result = save_current_project_session_to_supabase()
                if save_result:
                    st.session_state.rewrite_applied_message = (
                        st.session_state.rewrite_applied_message
                        + " Project saved to the current accepted state."
                    )
                else:
                    st.session_state.rewrite_applied_message = (
                        st.session_state.rewrite_applied_message
                        + " Project session was not saved automatically. Use Save Project Changes As A New Version before leaving."
                    )

                wbs_request_stage_change("Isolation Guardrail", export_view=True)

        st.markdown("---")

        st.markdown("## 📝 DRAFT OUTPUT")
        st.caption("The current manuscript remains a draft until it is saved at Step 8 as the FINAL OUTPUT MANUSCRIPT.")
        if st.session_state.get("demo_mode"):
            if st.button("💾 SAVE CURRENT DRAFT 🔒", key="save_current_draft_rewrite_trial", use_container_width=True):
                full_version_only_notice("Saved Versions")
        else:
            if st.button(
                "💾 SAVE CURRENT DRAFT",
                key="save_current_draft_rewrite",
                type="primary",
                use_container_width=True,
            ):
                rewrite_draft_result = save_manuscript_checkpoint(
                    status="DRAFT",
                    stage_label="Script Rewrite",
                    source_stage="script_rewrite_draft",
                )
                save_current_project_session_to_supabase()
                if rewrite_draft_result.get("status") == "saved":
                    st.success(f"DRAFT — Script Rewrite — V{rewrite_draft_result.get('version_number')} saved to version history.")
                elif rewrite_draft_result.get("status") == "unchanged":
                    st.info(f"This DRAFT — Script Rewrite — V{rewrite_draft_result.get('version_number')} is already saved.")
                else:
                    st.error("Current rewrite-stage draft could not be saved to version history.")

        try:
            final_doc = Document()
            final_style = final_doc.styles["Normal"]
            final_font = final_style.font
            final_font.name = "Times New Roman"
            final_font.size = Pt(12)

            final_export_text = strip_internal_notices(st.session_state.current_draft_output)

            for line in final_export_text.split("\n"):
                clean_line = line.strip()
                if clean_line:
                    if "CHAPTER SCENE BEAT" in clean_line:
                        p = final_doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(18)
                        p.paragraph_format.space_after = Pt(6)
                        run = p.add_run(clean_line)
                        run.bold = True
                    elif not clean_line.startswith("="):
                        p = final_doc.add_paragraph(clean_line)
                        p.paragraph_format.space_after = Pt(12)
                        p.paragraph_format.line_spacing = 1.15

            final_buffer = BytesIO()
            final_doc.save(final_buffer)
            final_docx_bytes = final_buffer.getvalue()

            if st.session_state.get("demo_mode"):
                if st.button(
                    "Download Current Draft (.docx) 📥 🔒",
                    key="trial_rewrite_manuscript_printout_notice",
                    type="primary",
                    use_container_width=True,
                ):
                    full_version_only_notice("Manuscript Printout")
            else:
                st.download_button(
                    label="Download Current Draft (.docx) 📥",
                    data=final_docx_bytes,
                    file_name="manuscript_current_draft.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f"Failed to generate revised Word document: {e}")

# ==========================================
# WBS AI AGENT — LATE SHADOW STATE READ
# ==========================================
