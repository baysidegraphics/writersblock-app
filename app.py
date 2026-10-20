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
import hashlib
import zipfile
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


def get_project_session_snapshot():
    snapshot_keys = [
        "project_stage",
        "story_seed",
        "wbs_project_original_concept",
        "starting_source_mode",
        "imported_source_text",
        "imported_source_name",
        "imported_source_word_count",
        "project_title",
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

    snapshot["saved_at"] = datetime.now(timezone.utc).isoformat()
    return snapshot


def save_current_project_session_to_supabase():
    user_id = get_current_user_id()

    if not user_id:
        st.error("No user found.")
        return None

    project_id = get_active_project_id()
    if not project_id:
        result = save_project_to_supabase(
            project_title=get_project_title_for_display()[:80],
            project_type=st.session_state.get("format_type", "story"),
        )
        project_id = st.session_state.get("current_project_id")

    if not project_id:
        st.error("No active project available to save.")
        return None

    ensure_project_title_loaded()

    snapshot = get_project_session_snapshot()
    snapshot["current_project_id"] = project_id
    st.session_state.last_saved_project_at = snapshot.get("saved_at")

    result = supabase.table("writersblock_project_drafts").insert({
        "project_id": project_id,
        "user_id": user_id,
        "draft_title": "Saved Project Session",
        "draft_type": "project_session",
        "draft_content": json.dumps(snapshot),
        "version_number": int(st.session_state.get("current_processing_beat", 1) or 1),
    }).execute()

    if result and st.session_state.get("project_scope") == "Book in a Series":
        save_series_metadata_for_project(project_id)

    return result


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


def load_saved_project_session_to_state(saved_session_row):
    if not saved_session_row:
        st.warning("No saved project session found.")
        return False

    try:
        snapshot = json.loads(saved_session_row.get("draft_content") or "{}")
    except Exception as e:
        st.error(f"Saved project could not be loaded: {e}")
        return False

    for key, value in snapshot.items():
        if key == "saved_at":
            st.session_state.last_saved_project_at = value
            continue
        if key == "scene_blocks" and isinstance(value, dict):
            restored = {}
            for scene_key, scene_text in value.items():
                try:
                    restored[int(scene_key)] = scene_text
                except Exception:
                    restored[scene_key] = scene_text
            st.session_state.scene_blocks = restored
        else:
            st.session_state[key] = value

    st.session_state.current_project_id = saved_session_row.get("project_id") or snapshot.get("current_project_id")

    # Normalize older picture-book labels every time a saved project is restored.
    restored_format = str(st.session_state.get("format_type") or "").strip()
    if restored_format in {
        "Children's Storybook (32-Page Writing Layout)",
        "Children's Storybook (32-Page Layout)",
        "Children's Picture Book",
    }:
        st.session_state.format_type = "Children's Picture Book (32-Page Layout)"

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
            "version_label": f"{get_project_title_for_display()} — {version_label}",
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
        f"{get_project_title_for_display()} — {clean_status} — "
        f"{clean_stage} — V{next_version}"
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
    st.session_state.story_seed = (
        "An antique shop owner buys a heavy iron safe that cannot be opened, "
        "only to realize that every night, the ticking sounds coming from inside it get faster."
    )

if "starting_source_mode" not in st.session_state:
    st.session_state.starting_source_mode = "Story Idea"

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
            widget_key = f"format_field_{st.session_state.active_format_id}_{key}"
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
                    if not options:
                        continue
                    index = options.index(existing) if existing in options else 0
                    value = st.selectbox(
                        label, options, index=index, key=widget_key, help=help_text
                    )
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
                        custom_widget_key = f"format_field_{st.session_state.active_format_id}_{custom_key}"
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
    """Bottom-of-template reminder and save action for Concept Development."""
    st.markdown("---")
    with st.container(border=True):
        st.markdown("**💾 Remember to Save Project before leaving Concept Development.**")

        if st.session_state.get("demo_mode"):
            st.caption("Project saving is available in the full Writer Edition.")
            if st.button(
                "💾 Save Project 🔒",
                key=f"template_save_project_trial_{st.session_state.get('active_format_id', 'format')}",
                use_container_width=True,
                type="secondary",
            ):
                full_version_only_notice("Saved Projects")
            return

        if st.button(
            "💾 Save Project",
            key=f"template_save_project_{st.session_state.get('active_format_id', 'format')}",
            use_container_width=True,
            type="secondary",
        ):
            ensure_project_title_loaded()
            if not get_project_title():
                st.warning("Name this project before saving.")
                return
            save_result = save_current_project_session_to_supabase()
            if save_result:
                st.success("Project saved.")



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
    "Screenplay Outline",
    "Stage Play / Dramatic Script",
    "Audio Book",
    "Full Novel Blueprint",
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

    prompt = f"""
You are the WritersBlock Studios PROJECT INTEGRITY / FINAL REVIEW quality-control system.

This is a READ-ONLY audit. DO NOT rewrite, edit, polish, replace, summarize, or continue the manuscript.
Do not silently fix anything. The writer controls all changes.

PROJECT:
Title: {project_title}
Writing Format: {project_type}

FORMAT / DEVELOPMENT REQUIREMENTS:
{format_context or "No additional format-development requirements were supplied."}

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

    if target_format in {"Novel / Prose", "Short Story", "Novella"}:
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
Adapt the source into a complete children's picture-book story of approximately 500-800 words TOTAL and NEVER more than 800 words.
- Preserve the core plot, central characters, theme, emotional arc, and ending.
- Simplify exposition and descriptions for clear read-aloud pacing.
- Retain only dialogue that helps character, emotion, humor, or plot; shorten dialogue into simple age-appropriate spoken lines.
- Remove repetitive or adult-length conversations while preserving their essential meaning.
- Use short paragraphs suitable for later division across a 32-page / 16-spread picture-book layout.
- Do not include page numbers, spread numbers, illustration prompts, or layout instructions yet.
Return only the adapted 500-800 word picture-book story."""

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
    if target_format in {"Novel / Prose", "Short Story", "Novella"}:
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

        # 4) Update the current live project title.
        st.session_state.project_title = clean_title

        # 5) Save the complete current working state immediately for licensed users.
        #    This is a database save only; it makes no Gemini/API generation call.
        if st.session_state.get("licensed_mode"):
            save_result = save_current_project_session_to_supabase()
            if not save_result:
                return (
                    True,
                    "Project renamed, but the current project session could not be saved automatically. "
                    "Use Save Project before leaving.",
                )


        return True, f'Project renamed to "{clean_title}" and current work saved.'

    except Exception as exc:
        return False, f"Project rename could not be completed: {exc}"


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

        rename_key = f"rename_project_title_{safe_stage}_{project_id}"
        source_key = f"{rename_key}_source"

        # Keep the rename field synchronized after a successful rename or project load.
        if st.session_state.get(source_key) != current_title:
            st.session_state[rename_key] = "" if current_title == "Untitled Project" else current_title
            st.session_state[source_key] = current_title

        col_title, col_button = st.columns([4, 1.35])

        with col_title:
            proposed_title = st.text_input(
                "Rename Project:",
                key=rename_key,
                placeholder="Enter a new project title",
                label_visibility="visible",
            )

        with col_button:
            st.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
            confirm_clicked = st.button(
                "CONFIRM RENAME",
                key=f"confirm_rename_{safe_stage}_{project_id}",
                type="primary",
                use_container_width=True,
            )

        if confirm_clicked:
            ok, message = rename_current_project_everywhere(proposed_title)

            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)


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
    """Show project name first, then DRAFT / FINAL status, stage, and version."""
    items = []

    # Manuscript versions are the writer's explicit DRAFT / FINAL checkpoints.
    # Put manuscript checkpoints first and newest first so the latest saved version is immediately visible.
    manuscript_versions = list(get_all_manuscript_versions_for_user() or [])
    manuscript_versions.sort(
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    for version in manuscript_versions:
        project_join = version.get("writersblock_projects") or {}
        if isinstance(project_join, dict):
            version["project_title"] = project_join.get("project_title")

        title = str(
            version.get("project_title")
            or version.get("title")
            or get_project_title_for_display()
        ).strip()

        version_number = int(version.get("version_number") or 1)
        status, _stage_label = get_manuscript_version_status_stage(version)
        word_count = count_words(version.get("manuscript_content", ""))
        label = f"{title} — {status} V{version_number} — {word_count} words"

        items.append({
            "label": label,
            "type": "manuscript_version",
            "row": version,
        })

    # Project-session saves are working-state saves, not manuscript DRAFT / FINAL checkpoints.
    for saved_row in get_saved_project_sessions_for_dropdown():
        try:
            snapshot = json.loads(saved_row.get("draft_content") or "{}")
        except Exception:
            snapshot = {}

        title = str(snapshot.get("project_title") or "Untitled Project").strip()
        created_at = saved_row.get("created_at") or snapshot.get("saved_at")
        label = f"{title} — PROJECT SAVE — {full_date_label(created_at)}"
        items.append({
            "label": label,
            "type": "project_session",
            "row": saved_row,
        })

    return items


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


def get_series_metadata_by_project():
    return {
        row.get("_project_id"): row
        for row in get_series_metadata_rows()
        if row.get("_project_id")
    }


def get_existing_series_names():
    names = []
    for metadata in get_series_metadata_rows():
        series_name = str(metadata.get("series_name") or "").strip()
        if series_name and series_name not in names:
            names.append(series_name)
    return sorted(names, key=str.lower)


def get_next_series_book_number(series_name, exclude_project_id=None):
    series_key = make_series_key(series_name)
    if not series_key:
        return 1

    book_numbers = []
    for metadata in get_series_metadata_rows():
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
    for metadata in get_series_metadata_rows():
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
    user_id = get_current_user_id()
    clean_series_name = str(series_name or "").strip()
    if not user_id or not project_id or not clean_series_name:
        return None

    series_key = make_series_key(clean_series_name)
    metadata = {
        "series_key": series_key,
        "series_name": clean_series_name,
        "series_book_number": int(book_number or 1),
        "series_continuity_mode": "Strict",
        "series_reference_ids": [],
        "series_canon_notes": "",
        "project_title": str(project_title or get_project_title_from_project_id(project_id) or "Untitled Project").strip(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "assigned_from_existing_project": True,
    }

    return (
        supabase.table("writersblock_project_drafts")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "draft_title": (
                f"{clean_series_name} — Book {metadata['series_book_number']} Series Metadata"
            ),
            "draft_type": "series_metadata",
            "draft_content": json.dumps(metadata),
            "version_number": metadata["series_book_number"],
        })
        .execute()
    )


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
        prefix = f"{series_name} — Series #{book_number} — " if series_name and book_number else ""
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
            or snapshot.get("manuscript_text")
            or ""
        ).strip()
        if not manuscript_text:
            continue

        title = str(
            snapshot.get("project_title")
            or get_project_title_from_project_id(project_id)
            or "Untitled Project"
        ).strip()
        metadata = metadata_by_project.get(project_id, {})
        book_number = int(metadata.get("series_book_number") or snapshot.get("series_book_number") or 0)
        series_name = str(metadata.get("series_name") or snapshot.get("series_name") or "").strip()
        series_key = str(metadata.get("series_key") or snapshot.get("series_key") or "")
        prefix = f"{series_name} — Series #{book_number} — " if series_name and book_number else ""

        candidates.append({
            "id": f"session:{saved_row.get('id')}",
            "label": f"{prefix}{title} — Saved Project — {count_words(manuscript_text):,} words",
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
        f"Current Series Number: {book_number}",
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

    if st.session_state.get("starting_source_mode") == "Existing Draft / Manuscript":
        imported_source = str(st.session_state.get("imported_source_text") or "").strip()
        if imported_source:
            plot_line = f"""
EXISTING DRAFT / MANUSCRIPT SOURCE — USE AS THE PRIMARY WORKING SOURCE:
The author supplied the complete draft below as the starting material. Treat it as an existing working draft,
not as a one-paragraph plot prompt. Preserve its established characters, events, chronology, setting, and core
story unless a later WritersBlock choice deliberately changes them. Apply the selected project type, Dialogue
Style, tone, author-style preference, and later development choices to this source as the project moves forward.
Do not truncate the source merely because later stages contain target word-count controls.

--- BEGIN EXISTING DRAFT SOURCE ---
{imported_source}
--- END EXISTING DRAFT SOURCE ---
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

    st.write(f"Manuscript Version: {st.session_state.manuscript_version}")
    st.write(f"Current Manuscript Words: {count_words(st.session_state.current_draft_output)}")

st.sidebar.markdown("---")

with st.sidebar.expander("Saved Projects / Versions", expanded=False):
    if st.session_state.get("demo_mode"):
        st.caption("These features remain visible during the 7-Day Limited Free Trial but unlock with the full Writer Edition.")

        if st.button("💾 Saved Projects 🔒", key="trial_saved_projects_notice", use_container_width=True):
            full_version_only_notice("Saved Projects")

        if st.button("🗂️ Saved Versions 🔒", key="trial_saved_versions_notice", use_container_width=True):
            full_version_only_notice("Saved Versions")
    else:
        saved_items = get_saved_projects_versions_dropdown_items()

        if not saved_items:
            st.caption("No saved projects or versions found.")
        else:
            saved_labels = [item["label"] for item in saved_items]
            saved_lookup = {item["label"]: item for item in saved_items}

            selected_saved_label = st.selectbox(
                "Saved Projects / Versions:",
                saved_labels,
                key="sidebar_saved_projects_versions_selector",
            )

            selected_saved_item = saved_lookup.get(selected_saved_label)

            if st.button("Load Selected Saved Item", key="sidebar_load_saved_item", use_container_width=True):
                if selected_saved_item and selected_saved_item["type"] == "project_session":
                    if load_saved_project_session_to_state(selected_saved_item["row"]):
                        st.success("Saved project loaded.")
                        st.rerun()

                elif selected_saved_item and selected_saved_item["type"] == "manuscript_version":
                    selected_version = selected_saved_item["row"]
                    st.session_state.current_project_id = selected_version.get("project_id")

                    loaded_project_title = str(
                        selected_version.get("project_title")
                        or get_project_title_from_project_id(selected_version.get("project_id"))
                        or get_project_title()
                        or "Untitled Project"
                    ).strip()

                    st.session_state.project_title = loaded_project_title
                    st.session_state.current_draft_output = str(selected_version.get("manuscript_content") or "")
                    st.session_state.manuscript_version = int(selected_version.get("version_number") or 0)
                    loaded_status, loaded_stage = get_manuscript_version_status_stage(selected_version)
                    st.session_state.current_manuscript_save_status = loaded_status
                    st.session_state.current_manuscript_save_stage = loaded_stage
                    st.session_state.current_manuscript_save_version = int(selected_version.get("version_number") or 0)
                    st.session_state.rewritten_manuscript = ""
                    st.session_state.rewrite_applied_message = ""
                    st.session_state.show_saved_version_manager = False

                    # Resume a saved manuscript at the stage where that checkpoint was created.
                    # A Step 5 DRAFT must return to Script Lock, not Final Output.
                    if loaded_status == "FINAL":
                        st.session_state.project_stage = "Isolation Guardrail"
                        st.session_state.export_view = True
                    elif loaded_stage == "Script Rewrite":
                        st.session_state.project_stage = "Rewrite Engine"
                        st.session_state.export_view = False
                    elif loaded_stage == "Creative Draft":
                        st.session_state.project_stage = "Drafting Engine"
                        st.session_state.export_view = False
                    else:
                        st.session_state.project_stage = "Isolation Guardrail"
                        st.session_state.export_view = False

                    st.success(f"Saved {loaded_status.lower()} loaded at {loaded_stage}.")
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

can_navigate_to_sandbox = st.session_state.sandbox_slates is not None
can_navigate_to_plot = st.session_state.chosen_option is not None
can_navigate_to_drafting = st.session_state.plot_outline is not None
can_navigate_to_guardrail = bool(st.session_state.current_draft_output.strip())
can_navigate_to_revision = bool(st.session_state.current_draft_output.strip())
can_navigate_to_rewrite = bool(st.session_state.current_draft_output.strip())

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
        st.session_state.project_stage = "Intake"
        st.rerun()

if st.session_state.project_stage == "Sandbox":
    st.sidebar.button("🔵 2. Scripting (Active)", key="nav_sandbox_active", use_container_width=True)
elif can_navigate_to_sandbox and can_use_sandbox:
    if st.sidebar.button("⚪ 2. Scripting", key="nav_sandbox", use_container_width=True):
        st.session_state.project_stage = "Sandbox"
        st.rerun()
else:
    st.sidebar.button("🔒 2. Scripting (Locked)", key="nav_sandbox_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Plot Architect":
    st.sidebar.button("🔵 3. Plot Architecture (Active)", key="nav_plot_active", use_container_width=True)
elif can_navigate_to_plot and can_use_plot:
    if st.sidebar.button("⚪ 3. Plot Architecture", key="nav_plot", use_container_width=True):
        st.session_state.project_stage = "Plot Architect"
        st.rerun()
else:
    st.sidebar.button("🔒 3. Plot Architecture (Locked)", key="nav_plot_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Drafting Engine":
    st.sidebar.button("🔵 4. Creative Draft (Active)", key="nav_draft_active", use_container_width=True)
elif can_navigate_to_drafting and can_use_drafting:
    if st.sidebar.button("⚪ 4. Creative Draft", key="nav_draft", use_container_width=True):
        st.session_state.project_stage = "Drafting Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 4. Creative Draft (Locked)", key="nav_draft_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Isolation Guardrail" and not st.session_state.get("export_view", False):
    st.sidebar.button("🔵 5. Script Lock (Active)", key="nav_guard_active", use_container_width=True)
elif can_navigate_to_guardrail and can_use_safety:
    if st.sidebar.button("⚪ 5. Script Lock", key="nav_guard", use_container_width=True):
        st.session_state.project_stage = "Isolation Guardrail"
        st.session_state.export_view = False
        st.session_state.show_saved_version_manager = False
        st.rerun()
else:
    st.sidebar.button("🔒 5. Script Lock (Locked)", key="nav_guard_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Revision Engine":
    st.sidebar.button("🔵 6. Script Polish (Active)", key="nav_revision_active", use_container_width=True)
elif can_navigate_to_revision and can_use_revision:
    if st.sidebar.button("⚪ 6. Script Polish", key="nav_revision", use_container_width=True):
        st.session_state.project_stage = "Revision Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 6. Script Polish (Locked)", key="nav_revision_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Rewrite Engine":
    st.sidebar.button("🔵 7. Script Rewrite (Active)", key="nav_rewrite_active", use_container_width=True)
elif can_navigate_to_rewrite and can_use_rewrite:
    if st.sidebar.button("⚪ 7. Script Rewrite", key="nav_rewrite", use_container_width=True):
        st.session_state.project_stage = "Rewrite Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 7. Script Rewrite (Locked)", key="nav_rewrite_locked", disabled=True, use_container_width=True)

stage_8_label = "Manuscript Review" if st.session_state.get("demo_mode") else "Final Output"
if st.session_state.project_stage == "Isolation Guardrail" and st.session_state.get("export_view", False):
    st.sidebar.button(f"🔵 8. {stage_8_label} (Active)", key="nav_export_active", use_container_width=True)
elif can_navigate_to_guardrail and can_use_safety:
    if st.sidebar.button(f"⚪ 8. {stage_8_label}", key="nav_export", use_container_width=True):
        st.session_state.project_stage = "Isolation Guardrail"
        st.session_state.export_view = True
        st.session_state.show_saved_version_manager = False
        st.rerun()
else:
    st.sidebar.button(f"🔒 8. {stage_8_label} (Locked)", key="nav_export_locked", disabled=True, use_container_width=True)

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

if st.session_state.get("demo_mode"):
    if st.sidebar.button("💾 Save Project 🔒", key="save_current_project_session_trial", use_container_width=True, type="secondary"):
        full_version_only_notice("Saved Projects")
else:
    if st.sidebar.button("💾 Save Project", key="save_current_project_session", use_container_width=True, type="secondary"):
        ensure_project_title_loaded()

        if not get_project_title():
            st.sidebar.warning("Project title could not be found. Return to Concept Development and name the project before saving.")
        else:
            result = save_current_project_session_to_supabase()
            if result:
                st.sidebar.success("Project saved. Use SAVE CURRENT DRAFT at a draft output point to add a manuscript version to history.")
                st.rerun()

if st.session_state.get("demo_mode"):
    if st.sidebar.button("📚 Saved Version Manager 🔒", key="sidebar_saved_version_manager_trial", use_container_width=True, type="secondary"):
        full_version_only_notice("Saved Versions")
elif can_navigate_to_guardrail and can_use_safety:
    if st.sidebar.button("📚 Saved Version Manager", key="sidebar_saved_version_manager_shortcut", use_container_width=True, type="secondary"):
        st.session_state.project_stage = "Isolation Guardrail"
        st.session_state.export_view = True
        st.session_state.show_saved_version_manager = True
        st.rerun()
else:
    st.sidebar.button("🔒 Saved Version Manager", key="sidebar_saved_version_manager_locked", disabled=True, use_container_width=True, type="secondary")

if st.sidebar.button("⚠️ Start New Project", key="global_reset", use_container_width=True, type="secondary"):
    st.session_state.project_stage = "Intake"
    st.session_state.project_title = ""
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
    st.session_state.pop("series_book_number_input", None)
    st.session_state.pop("series_book_number_auto_signature", None)
    st.session_state.pop("custom_plot_line_input", None)
    st.session_state.story_seed = (
        "An antique shop owner buys a heavy iron safe that cannot be opened, "
        "only to realize that every night, the ticking sounds coming from inside it get faster."
    )
    st.session_state.starting_source_mode = "Story Idea"
    st.session_state.imported_source_text = ""
    st.session_state.imported_source_name = ""
    st.session_state.imported_source_word_count = 0
    st.session_state.pop("concept_existing_draft_upload", None)
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

        st.markdown("### Writing Format")
        current_format_id = str(
            st.session_state.get("active_format_id") or "novel_prose_novella"
        )
        if current_format_id not in WBS_FORMAT_IDS:
            current_format_id = "novel_prose_novella"

        _format_control_col, _format_spacer_col = st.columns([1.6, 1.25], gap="small")
        with _format_control_col:
            selected_format_id = st.selectbox(
                "Choose Writing Format",
                options=WBS_FORMAT_IDS,
                index=WBS_FORMAT_IDS.index(current_format_id),
                format_func=get_wbs_format_display_name,
                key="wbs_format_template_selector",
                label_visibility="collapsed",
            )

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

        if get_active_project_id():
            render_project_title_banner("step_1_concept_development")
        else:
            st.session_state.project_title = st.text_input(
                concept_ui.get("title_label") or "Project / Story Title:",
                value=st.session_state.get("project_title", ""),
                placeholder="Example: It's Not Safe",
                key="project_title_input",
            ).strip()

        st.markdown("### " + str(concept_ui.get('project_connection_heading') or 'Project Relationship'))

        project_scope_options = ["Standalone Book", "Book in a Series"]
        current_project_scope = str(st.session_state.get("project_scope", "Standalone Book"))

        scope_labels = concept_ui.get("scope_labels") or {}
        st.session_state.project_scope = st.radio(
            "Project Type:",
            project_scope_options,
            index=project_scope_options.index(current_project_scope)
            if current_project_scope in project_scope_options else 0,
            horizontal=True,
            key="project_scope_selector",
            format_func=lambda value: scope_labels.get(value, value),
        )

        if st.session_state.project_scope == "Book in a Series":
            existing_series_names = get_existing_series_names()
            series_choice_options = existing_series_names + ["Create New Series"]
            current_series_name = str(st.session_state.get("series_name", "") or "").strip()
            default_series_choice = current_series_name if current_series_name in existing_series_names else "Create New Series"

            _series_control_col, _series_spacer_col = st.columns([3.0, 1.2])
            with _series_control_col:
                selected_series_choice = st.selectbox(
                    "Select Series:",
                    series_choice_options,
                    index=series_choice_options.index(default_series_choice),
                    key="series_choice_selector",
                )

            if selected_series_choice == "Create New Series":
                st.session_state.series_name = st.text_input(
                    "Series Name:",
                    value=current_series_name,
                    placeholder="Example: Oakhaven",
                    key="series_name_input",
                ).strip()
            else:
                st.session_state.series_name = selected_series_choice

            resolved_series_name = str(st.session_state.get("series_name") or "").strip()
            resolved_series_key = make_series_key(resolved_series_name)
            auto_number_signature = (
                f"{resolved_series_key}:{st.session_state.get('current_project_id') or 'new-project'}"
            )

            if (
                resolved_series_key
                and st.session_state.get("series_book_number_auto_signature")
                != auto_number_signature
            ):
                next_book_number = get_next_series_book_number(
                    resolved_series_name,
                    exclude_project_id=st.session_state.get("current_project_id"),
                )
                st.session_state.series_book_number = next_book_number
                st.session_state.series_book_number_input = next_book_number
                st.session_state.series_book_number_auto_signature = auto_number_signature

            st.session_state.series_book_number = int(
                st.number_input(
                    "Series Number:",
                    min_value=1,
                    max_value=100,
                    value=int(st.session_state.get("series_book_number", 1) or 1),
                    step=1,
                    key="series_book_number_input",
                )
            )

            # Series continuity is automatic and always strict.
            st.session_state.series_continuity_mode = "Strict"
            st.caption("Continuity Protection: Strict — automatic")

            st.session_state.series_key = make_series_key(st.session_state.series_name)

            candidates = get_series_reference_candidates()
            id_to_candidate = {candidate["id"]: candidate for candidate in candidates}

            # One-time setup for books written before series support was added.
            unassigned_candidates = [
                candidate
                for candidate in candidates
                if not str(candidate.get("series_key") or "").strip()
            ]

            if unassigned_candidates and st.session_state.series_name:
                st.markdown("**Add Previously Created Projects to This Series (One-Time Setup):**")
                setup_label_to_candidate = {
                    candidate["label"]: candidate for candidate in unassigned_candidates
                }
                selected_existing_labels = st.multiselect(
                    "Existing Saved Projects:",
                    options=list(setup_label_to_candidate.keys()),
                    key="series_existing_book_selector",
                    help=(
                        "Select books already written before series support was added. "
                        "They will be numbered automatically by their original saved date."
                    ),
                )

                selected_existing_records = [
                    setup_label_to_candidate[label]
                    for label in selected_existing_labels
                    if label in setup_label_to_candidate
                ]
                selected_existing_records.sort(
                    key=lambda item: (
                        str(item.get("created_at") or ""),
                        str(item.get("title") or "").lower(),
                    )
                )

                if selected_existing_records:
                    st.caption("Automatic series order:")
                    for assigned_number, record in enumerate(selected_existing_records, start=1):
                        st.write(f"Series #{assigned_number}: {record.get('title', 'Untitled Project')}")

                    if st.button(
                        "Add Selected Projects to Series",
                        key="assign_existing_books_to_series",
                        use_container_width=True,
                    ):
                        for assigned_number, record in enumerate(selected_existing_records, start=1):
                            assign_existing_project_to_series(
                                project_id=record.get("project_id"),
                                series_name=st.session_state.series_name,
                                book_number=assigned_number,
                                project_title=record.get("title"),
                            )

                        st.session_state.series_book_number = max(
                            int(st.session_state.get("series_book_number", 1) or 1),
                            len(selected_existing_records) + 1,
                        )
                        st.session_state.series_existing_book_selector = []
                        st.success("Existing projects added to the series.")
                        st.rerun()

            valid_saved_ids = [
                reference_id
                for reference_id in (st.session_state.get("series_reference_ids", []) or [])
                if reference_id in id_to_candidate
            ]
            prior_series_ids = [
                candidate["id"]
                for candidate in candidates
                if (
                    st.session_state.series_key
                    and candidate.get("series_key") == st.session_state.series_key
                    and int(candidate.get("book_number") or 0) > 0
                    and int(candidate.get("book_number") or 0) < st.session_state.series_book_number
                )
            ]

            # Preserve any books already attached during first-time series setup, then automatically
            # include every earlier book already saved under the same series.
            automatic_ids = []
            for reference_id in valid_saved_ids + prior_series_ids:
                if reference_id not in automatic_ids:
                    automatic_ids.append(reference_id)
            st.session_state.series_reference_ids = automatic_ids
            st.session_state.series_selection_signature = (
                f"{st.session_state.series_key}:{st.session_state.series_book_number}"
            )
            st.session_state.pop("series_reference_selector", None)

            automatic_records = [
                id_to_candidate[reference_id]
                for reference_id in automatic_ids
                if reference_id in id_to_candidate
            ]

            
            _series_reference_heading = {
                "podcast_script": "**Previous Podcast Automatically Referenced:**",
                "youtube_shorts": "**Previous Series Projects Automatically Referenced:**",
            }.get(
                str(st.session_state.get("active_format_id") or ""),
                "**Previous Series Projects Automatically Referenced:**",
            )
            st.markdown(_series_reference_heading)
            if automatic_records:
                for record in automatic_records:
                    st.write(f"✓ {record.get('title', 'Untitled Project')}")
            elif st.session_state.series_book_number > 1:
                st.warning(
                    "No earlier projects are currently saved under this series. Existing projects only need "
                    "to be assigned to the series once; future projects will include them automatically."
                )
            else:
                st.caption("This is the first project in the series.")

            inherited_canon = get_inherited_series_canon_notes(
                st.session_state.series_key,
                st.session_state.series_book_number,
            )
            if inherited_canon:
                st.markdown("**Inherited Series Reference:** Automatically loaded from earlier series projects.")

            # Series continuity is derived automatically from earlier manuscripts and saved metadata.
            # No manual facts field is shown or required.
            st.session_state.series_canon_notes = ""
            st.session_state.pop("series_canon_notes_input", None)

            reference_count = len(st.session_state.get("series_reference_ids", []) or [])
            st.success(
                f"Series Continuity Active: {st.session_state.series_name or 'Name Required'} — "
                f"Series #{st.session_state.series_book_number} — {reference_count} earlier "
                f"project{'' if reference_count == 1 else 's'} automatically included."
            )
        else:
            st.session_state.series_key = ""
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

        existing_draft_option = str(
            concept_ui.get("existing_option") or "-- Use Existing Draft / Manuscript --"
        )
        custom_plot_option = str(
            concept_ui.get("custom_option") or "-- Enter Your Own Project Premise --"
        )
        # Use one universal concept/brief entry instead of preloaded sample concepts.
        # This keeps every format neutral and lets Quill respond to the user's actual intent.
        seed_bank = []
        quill_start_option = "-- Quill-Assisted Starting Point --"
        seed_options = [custom_plot_option, existing_draft_option, quill_start_option]

        current_seed = str(st.session_state.get("story_seed") or "")
        current_source_mode = str(st.session_state.get("starting_source_mode") or "Story Idea")

        if current_source_mode == "Existing Draft / Manuscript":
            default_seed_index = seed_options.index(existing_draft_option)
        elif current_source_mode == "Quill Assisted" and quill_start_option in seed_options:
            default_seed_index = seed_options.index(quill_start_option)
        elif current_source_mode == "Custom Plot Line":
            default_seed_index = seed_options.index(custom_plot_option)
        elif current_seed in seed_bank:
            default_seed_index = seed_bank.index(current_seed)
        else:
            default_seed_index = seed_options.index(custom_plot_option)

        selected_seed = st.radio(
            str(concept_ui.get("source_label") or "Starting Source:"),
            seed_options,
            index=default_seed_index,
            key=f"starting_source_{st.session_state.active_format_id}",
        )

        if selected_seed == custom_plot_option:
            st.session_state.starting_source_mode = "Custom Plot Line"
            custom_value = (
                st.session_state.story_seed
                if current_source_mode != "Existing Draft / Manuscript"
                else ""
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
            # Optional creative direction for Quill-Assisted Starting Point.
            # This is guidance for concept generation, not the generated concept itself.
            quill_direction = st.text_area(
                "Starting Idea / Direction (Optional):",
                key=f"wbs_quill_starting_direction_{st.session_state.active_format_id}",
                height=110,
                placeholder=(
                    "Share a basic idea, theme, character, situation, or intended outcome. "
                    "Quill will build a starting concept around your direction."
                ),
                help="Give Quill as much or as little direction as you wish. Leave blank for an original suggestion.",
            )
            st.caption("Optional: leave the direction blank for Quill to suggest a concept from your Development Setup above.")
            quill_key = f"wbs_quill_starting_concept_{st.session_state.active_format_id}"
            # Apply any revision generated by Quill chat before this widget exists.
            pending_key = f"_wbs_quill_pending_concept_{st.session_state.active_format_id}"
            pending_concept = st.session_state.pop(pending_key, None)
            if pending_concept is not None:
                st.session_state[quill_key] = str(pending_concept)
                st.session_state.story_seed = str(pending_concept)
            if quill_key not in st.session_state:
                st.session_state[quill_key] = ""
            if st.button(
                "Ask Quill to Suggest a Starting Point",
                key=f"wbs_quill_generate_concept_{st.session_state.active_format_id}",
            ):
                require_product_access("sandbox")
                backend = st.session_state.get("backend")
                client = getattr(backend, "client", None)
                model_name = getattr(backend, "model_name", None)
                if client is None or not model_name:
                    st.error("Quill's writing service is unavailable. Please try again later.")
                else:
                    development_context = get_active_format_development_context()
                    prompt = (
                        "You are Quill, writing an original STORY CONCEPT that a writer can edit. "
                        f"Write 100–180 words for {format_name}. "
                        "Deliver a vivid, self-contained account of WHAT HAPPENS: name the protagonist, "
                        "establish the situation, show the inciting event, describe concrete choices and "
                        "consequences, and end with a plausible change or unresolved question. "
                        "Write paragraphs of story-facing prose, not a lesson, evaluation, outline, "
                        "creative brief, or discussion of theme. Keep it at concept/synopsis length, "
                        "not a finished manuscript. Respect the selections and optional writer direction "
                        "without calling attention to these requirements. "
                        "NEVER use meta-commentary such as 'this story explores', 'the central idea', "
                        "'the narrative should', 'the story will', 'from a first-person perspective', "
                        "'the writer', or 'the reader'. Do not add a heading. "
                        "Begin immediately with the character or unfolding event.\n\n"
                        "Writer's direction (if any; preserve its substance):\n"
                        f"{quill_direction.strip() or '[No additional direction supplied]'}\n\n"
                        f"{development_context}\n"
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
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Quill could not generate a starting concept: {exc}")
            st.session_state.story_seed = st.text_area(
                "Quill's Suggested Starting Concept — Edit Before Continuing:",
                key=quill_key,
                height=180,
                placeholder="Ask Quill to suggest a starting concept based on your development selections.",
            )
            st.caption(f"{count_words(st.session_state.story_seed):,} / 1,000 words")
            if count_words(st.session_state.story_seed) > 1000:
                st.warning("Reduce the starting concept to 1,000 words or fewer.")

        elif selected_seed == existing_draft_option:
            st.session_state.starting_source_mode = "Existing Draft / Manuscript"
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
                str(concept_ui.get("existing_label") or "Upload Existing Draft / Manuscript:"),
                type=["docx", "txt"],
                key=f"concept_existing_draft_upload_{st.session_state.active_format_id}",
                help="Use a DOCX or TXT as the protected starting source for this WritersBlock project.",
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
                    f"Existing Source Loaded: {imported_source_name or 'Uploaded Document'} — "
                    f"{count_words(imported_source_text):,} words"
                )
                st.caption(
                    "This source is read-only in Concept Development. WritersBlock will use it as protected "
                    "starting material while the selected format and its development rules control the project."
                )
                st.text_area(
                    "Existing Source — Read Only:",
                    value=imported_source_text,
                    height=320,
                    disabled=True,
                    key=f"concept_existing_draft_read_only_preview_{st.session_state.active_format_id}",
                )
            else:
                st.info("Upload a DOCX or TXT source to use it as the protected starting material.")

        else:
            st.session_state.starting_source_mode = "Story Idea"
            st.session_state.story_seed = selected_seed

        # Production influence is now selected at the top of each relevant
        # Development Setup instead of appearing as a late style-reference field.
        if st.session_state.get("active_format_id") == "podcast_script":
            st.session_state.author_style = ""

        st.markdown("---")

        if st.button(
            str(concept_ui.get("button_label") or "Develop Project Paths 🚀"),
            key="generate_sandbox_paths",
            type="primary",
            use_container_width=True,
        ):
            require_product_access("sandbox")
            require_demo_action_available("sandbox")
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


            if st.session_state.get("starting_source_mode") == "Existing Draft / Manuscript":
                imported_source_text = str(st.session_state.get("imported_source_text") or "").strip()
                if not imported_source_text:
                    st.error("Please upload an existing DOCX or TXT draft before generating sandbox paths.")
                    st.stop()
                st.session_state.story_seed = imported_source_text

            if not st.session_state.get("wbs_project_original_concept"):
                st.session_state.wbs_project_original_concept = str(st.session_state.story_seed or "").strip()

            if not st.session_state.story_seed.strip():
                source_noun = str(concept_ui.get("source_noun") or "project premise")
                st.error(f"Please enter a {source_noun} or upload an existing source before continuing.")
                st.stop()

            if (
                st.session_state.get("starting_source_mode") in {"Custom Plot Line", "Quill Assisted"}
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

                if sandbox_output_is_usable(st.session_state.sandbox_slates):
                    mark_demo_action_used("sandbox")

                save_project_to_supabase(
                    project_title=get_project_title_for_display()[:80],
                    project_type=st.session_state.format_type,
                )

                if st.session_state.get("project_scope") == "Book in a Series":
                    save_series_metadata_for_project(
                        st.session_state.get("current_project_id")
                    )


                st.session_state.chosen_option = None
                st.session_state.chosen_option_text = None
                st.session_state.plot_outline = None
                st.session_state.current_draft_output = ""
                st.session_state.rolling_lore_book = ""
                st.session_state.completed_beats = []
                st.session_state.scene_blocks = {}
                st.session_state.current_processing_beat = 1
                st.session_state.project_saved_notice = True
                st.session_state.project_stage = "Sandbox"
                st.rerun()

        # Every writing-format template ends with the same explicit save reminder.
        render_format_template_save_reminder()


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
        st.success("Project saved.")
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

                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

        with col2:
            st.subheader("Option B: Twisted Perspective")
            st.markdown("*A stranger version with a hidden truth or reversal.*")
            st.info(sandbox_slates.get("Option B", ""))

            if st.button("Select Path B 🎯", key="btn_b", type="primary", use_container_width=True):
                require_product_access("plot")

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

                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

        with col3:
            st.subheader("Option C: High-Impact Version")
            st.markdown("*A faster, more intense story path.*")
            st.info(sandbox_slates.get("Option C", ""))

            if st.button("Select Path C 🎯", key="btn_c", type="primary", use_container_width=True):
                require_product_access("plot")

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

                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

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

    if st.session_state.plot_outline is None:
        if st.button(
            "Generate Plot Architecture 🧱",
            key="generate_plot_architecture",
            type="primary",
            use_container_width=True,
        ):
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
            st.rerun()
        else:
            st.stop()

    st.subheader("Review / Modify Architectural Output:")

    st.session_state.plot_outline = st.text_area(
        "Structured Scene Beats Layout Panel:",
        value=st.session_state.plot_outline,
        height=450,
        key="current_outline_view",
        label_visibility="collapsed",
    )

    st.markdown("---")

    if st.button("Lock Outline & Advance to Recursive Drafting 🚀", key="lock_outline_advance", type="primary", use_container_width=True):
        require_product_access("drafting")

        st.session_state.current_draft_output = ""
        st.session_state.rolling_lore_book = ""
        st.session_state.completed_beats = []
        st.session_state.scene_blocks = {}
        st.session_state.current_processing_beat = 1
        st.session_state.project_stage = "Drafting Engine"
        st.rerun()

# ======================================
# PHASE 4: RECURSIVE DRAFTING ENGINE
# ======================================
elif st.session_state.project_stage in ["Drafting", "Drafting Engine"]:
    require_product_access("drafting")

    st.header("📄 Step 4: Creative Draft")
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
            recommended_scene_word_count = 150
            st.info(
                "Children's Picture Book target: approximately 500–800 story words total. "
                "With four structural scene beats, WritersBlock recommends about 125–200 words per beat "
                "before the final manuscript is divided into the 32-page / 16-spread layout draft."
            )

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

            tense_choice = st.selectbox(
                "Tense:",
                ["Past Tense", "Present Tense"],
                key=f"tense_choice_{st.session_state.current_processing_beat}"
            )

            scene_notes = st.text_area(
                "Scene Purpose / Special Instructions:",
                placeholder="Example: Make this scene slower, more suspenseful, with stronger sensory detail.",
                height=100,
                key=f"scene_notes_{st.session_state.current_processing_beat}"
            )

            st.markdown("---")

        if st.session_state.current_processing_beat <= total_beats:
            current_scene_number = st.session_state.current_processing_beat

            if current_scene_number in st.session_state.scene_blocks and str(st.session_state.scene_blocks.get(current_scene_number, "")).strip():
                st.info(f"Scene Block {current_scene_number} is already written.")
                st.stop()

            btn_label = f"Execute Scene Block {current_scene_number} of {total_beats} ⚡"

            if st.button(
                btn_label,
                key=f"execute_scene_block_{current_scene_number}",
                type="primary",
                use_container_width=True,
            ):
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
Target Word Count: Approximately {target_word_count} words
Point of View: {pov_choice}
Tense: {tense_choice}
Scene Purpose / Special Instructions: {scene_notes}

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
                            st.session_state.project_stage = "Isolation Guardrail"
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
        st.header("📤 Step 8: Manuscript Review" if st.session_state.get("demo_mode") else "✅ FINAL OUTPUT")
        render_project_title_banner("step_8_final_output_conversion")
        st.markdown("---")

        # Step 8 terminates this rerun with st.stop(), so render Shadow here.

        current_source = str(st.session_state.get("current_draft_output") or "").strip()
        if not current_source:
            st.warning("No working manuscript is available for Final Output.")
            st.stop()

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
                        st.session_state.project_integrity_status = (
                            "PASS" if "OVERALL STATUS: PASS" in first_line else "WARNINGS"
                        )
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

        original_format = str(st.session_state.get("format_type") or "Novel / Prose")
        if not st.session_state.get("final_output_format"):
            st.session_state.final_output_format = original_format if original_format in FINAL_OUTPUT_FORMAT_OPTIONS else "Novel / Prose"

        display_options = [FINAL_OUTPUT_DISPLAY_LABELS[x] for x in FINAL_OUTPUT_FORMAT_OPTIONS]
        display_to_value = {FINAL_OUTPUT_DISPLAY_LABELS[x]: x for x in FINAL_OUTPUT_FORMAT_OPTIONS}
        current_final_format = get_final_output_format()
        current_display = FINAL_OUTPUT_DISPLAY_LABELS[current_final_format]

        selected_display = st.selectbox(
            "Final Output Format:", display_options,
            index=display_options.index(current_display),
            key="final_output_format_selector_display",
            help="Choose the finished industry format. This does not alter the saved working manuscript.",
        )
        selected_final_format = display_to_value[selected_display]

        if selected_final_format != st.session_state.get("final_output_format"):
            st.session_state.final_output_format = selected_final_format
            st.session_state.final_output_text = ""
            st.session_state.final_output_source_signature = ""
            st.session_state.final_output_saved_signature = ""
            st.session_state.picture_book_layout_spreads = []
            st.session_state.picture_book_layout_source_signature = ""

        conversion_is_current = bool(
            str(st.session_state.get("final_output_text") or "").strip()
            and st.session_state.get("final_output_source_signature") == source_signature
        )

        if selected_final_format == PICTURE_BOOK_FORMAT:
            st.warning(
                "Children's Picture Book requires adaptation, not simple formatting. WritersBlock will rewrite the current "
                "manuscript to approximately 500-800 words (never over 800), simplify dialogue and exposition, and then "
                "prepare it for the 32-page picture-book layout. For greater control over what is shortened or preserved, "
                "WritersBlock recommends using Script Rewrite first to reduce and refine the manuscript."
            )
            picture_book_confirmed = st.checkbox(
                "I understand the manuscript will be adapted to a 500-800 word Children's Picture Book.",
                key="confirm_picture_book_final_conversion",
            )
        else:
            picture_book_confirmed = True

        button_label = "REFRESH FINAL OUTPUT" if conversion_is_current else "GENERATE FINAL OUTPUT"
        if st.button(button_label, key="generate_final_output_conversion", type="primary", use_container_width=True, disabled=not picture_book_confirmed):
            with st.spinner(f"Converting working manuscript to {get_automatic_output_label(selected_final_format)}..."):
                try:
                    if create_bridge_adapter is None:
                        raise RuntimeError(
                            "WritersBlock Model is unavailable. "
                            + WBS_MODEL_IMPORT_ERROR
                        )

                    _wbs_final_bridge = create_bridge_adapter(
                        backend=st.session_state.backend
                    )
                    _wbs_final_result = _wbs_final_bridge.execute(
                        "Generate final output",
                        st.session_state,
                        prepared_context={
                            "final_output_instruction": get_final_output_conversion_instruction(
                                selected_final_format
                            ),
                            "effective_format_type": get_effective_format_type(),
                            "format_development_context": get_full_project_continuity_context(),
                            "quill_format_instructions": st.session_state.get("quill_format_instructions", ""),
                            "quill_template_context": refresh_quill_template_context(),
                        },
                        action_payload={
                            "source_text": current_source,
                            "final_output_format": selected_final_format,
                            "final_output_instruction": get_final_output_conversion_instruction(
                                selected_final_format
                            ),
                            # Explicit Step 8 backend mode:
                            # Same-format prose is normalization/polish, not a story rewrite.
                            # Other final-format conversions remain direct controlled conversion.
                            "backend_rewrite_mode": (
                                "Polish Only / Do Not Change Story"
                                if selected_final_format == st.session_state.get("format_type")
                                and selected_final_format in {
                                    "Novel / Prose",
                                    "Short Story",
                                    "Novella",
                                }
                                else "Direct Story Change / Obey My Instructions Exactly"
                            ),
                            "target_length": (
                                "Custom Word Count"
                                if selected_final_format == PICTURE_BOOK_FORMAT
                                else "Keep Current Length"
                            ),
                            "custom_target_word_count": (
                                700 if selected_final_format == PICTURE_BOOK_FORMAT else None
                            ),
                            "tone_style": st.session_state.tone_style,
                            "author_style": st.session_state.author_style,
                        },
                    )

                    if not _wbs_final_result.success:
                        st.session_state["_wbs_agent_final_bridge_error"] = (
                            _wbs_final_result.error
                            or "WritersBlock Model Bridge returned no Final Output."
                        )
                        raise RuntimeError(
                            st.session_state["_wbs_agent_final_bridge_error"]
                        )

                    converted = _wbs_final_result.output
                    st.session_state["_wbs_agent_bridge_last_operation"] = (
                        _wbs_final_result.backend_operation or ""
                    )
                    st.session_state["_wbs_agent_bridge_last_success"] = True
                except Exception as exc:
                    st.error(f"Final Output conversion failed: {exc}")
                    st.stop()

            if not ai_output_is_usable(converted):
                st.error("Final Output conversion did not return usable text. The working manuscript was not changed.")
                st.stop()

            st.session_state.final_output_text = str(converted).strip()
            st.session_state.final_output_source_signature = source_signature
            st.session_state.final_output_preview_id += 1
            st.session_state.final_output_saved_signature = ""
            if selected_final_format == PICTURE_BOOK_FORMAT and count_words(st.session_state.final_output_text) <= 800:
                st.session_state.picture_book_layout_spreads = build_picture_book_spreads_locally(st.session_state.final_output_text)
                st.session_state.picture_book_layout_source_signature = get_text_signature(st.session_state.final_output_text)
                st.session_state.picture_book_layout_preview_id += 1
            st.rerun()

        final_text = str(st.session_state.get("final_output_text") or "").strip()
        conversion_is_current = bool(final_text and st.session_state.get("final_output_source_signature") == source_signature)

        if not conversion_is_current:
            st.info(f"Working manuscript: {count_words(current_source):,} words. Choose the Final Output Format above and select GENERATE FINAL OUTPUT. The working manuscript remains unchanged.")
        else:
            st.subheader(f"📋 FINAL OUTPUT — {get_automatic_output_label(selected_final_format)}")
            edited_final_text = st.text_area("Review Final Output:", value=final_text, height=520, key=f"final_output_review_{st.session_state.final_output_preview_id}")
            st.session_state.final_output_text = edited_final_text
            final_text = edited_final_text.strip()

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Source Words", f"{count_words(current_source):,}")
            with c2: st.metric("Final Output Words", f"{count_words(final_text):,}")
            with c3: st.metric("Format", get_automatic_output_label(selected_final_format))

            if selected_final_format == PICTURE_BOOK_FORMAT:
                if count_words(final_text) > 800:
                    st.error("This Picture Book output is over 800 words. Refresh the conversion before creating the layout.")
                else:
                    st.markdown("---")
                    st.subheader("🖼️ 32-Page Picture Book Layout Draft")
                    page_size_options = list(PICTURE_BOOK_PAGE_SIZES.keys())
                    current_size = st.session_state.get("picture_book_page_size", DEFAULT_PICTURE_BOOK_PAGE_SIZE)
                    if current_size not in page_size_options:
                        current_size = DEFAULT_PICTURE_BOOK_PAGE_SIZE
                    selected_page_size = st.selectbox("Picture Book Page Size:", page_size_options, index=page_size_options.index(current_size), key="picture_book_page_size_final_output")
                    st.session_state.picture_book_page_size = selected_page_size
                    final_sig = get_text_signature(final_text)
                    if st.session_state.get("picture_book_layout_source_signature") != final_sig:
                        st.session_state.picture_book_layout_spreads = build_picture_book_spreads_locally(final_text)
                        st.session_state.picture_book_layout_source_signature = final_sig
                    edited_spreads = []
                    for spread in normalize_picture_book_spreads(st.session_state.picture_book_layout_spreads):
                        with st.expander(f"Spread {spread['spread_number']} — Pages {spread['pages']}", expanded=(spread['spread_number'] == 1)):
                            template = st.selectbox("Text / Image Position Template:", PICTURE_BOOK_LAYOUT_TEMPLATES, index=PICTURE_BOOK_LAYOUT_TEMPLATES.index(spread['template']) if spread['template'] in PICTURE_BOOK_LAYOUT_TEMPLATES else 0, key=f"final_pb_template_{st.session_state.picture_book_layout_preview_id}_{spread['spread_number']}")
                            render_picture_book_template_preview(template, selected_page_size)
                            story_text = st.text_area("Story Text for This Spread:", value=spread.get('story_text', ''), height=120, key=f"final_pb_text_{st.session_state.picture_book_layout_preview_id}_{spread['spread_number']}")
                            illustration = st.text_area("Illustration Direction:", value=spread.get('illustration_direction', ''), height=100, key=f"final_pb_ill_{st.session_state.picture_book_layout_preview_id}_{spread['spread_number']}")
                            edited_spreads.append({'spread_number': spread['spread_number'], 'pages': spread['pages'], 'template': template, 'story_text': story_text.strip(), 'illustration_direction': illustration.strip()})
                    st.session_state.picture_book_layout_spreads = edited_spreads

            st.markdown("---")
            if st.session_state.get("demo_mode"):
                if st.button("💾 SAVE FINAL OUTPUT 🔒", key="trial_save_final_converted_output", use_container_width=True):
                    full_version_only_notice("Saved Versions")
            else:
                if st.button("💾 SAVE FINAL OUTPUT", key="save_final_converted_output", type="primary", use_container_width=True):
                    checkpoint = save_manuscript_checkpoint(status="FINAL", stage_label="Manuscript Output", source_stage="final_output")
                    artifact = save_final_output_artifact_to_supabase(selected_final_format, final_text)
                    save_current_project_session_to_supabase()
                    if selected_final_format == PICTURE_BOOK_FORMAT and st.session_state.get("picture_book_layout_spreads"):
                        save_picture_book_layout_to_supabase(st.session_state.picture_book_layout_spreads, st.session_state.get("picture_book_page_size", DEFAULT_PICTURE_BOOK_PAGE_SIZE))
                    if checkpoint.get("status") == "saved" and artifact:
                        st.session_state.final_output_saved_signature = get_text_signature(final_text)
                        st.success(f"FINAL source checkpoint saved and {get_automatic_output_label(selected_final_format)} output stored separately.")
                    else:
                        st.warning("The Final Output was generated, but one or more save records could not be confirmed.")

            if st.session_state.get("demo_mode"):
                if st.button(f"Download Final {get_automatic_output_label(selected_final_format)} (.docx) 🔒", key="trial_download_final_converted_output", type="primary", use_container_width=True):
                    full_version_only_notice("Manuscript Printout")
            else:
                if selected_final_format == PICTURE_BOOK_FORMAT:
                    docx_bytes = build_picture_book_layout_docx_bytes(get_project_title_for_display(), st.session_state.get("picture_book_layout_spreads") or build_picture_book_spreads_locally(final_text), st.session_state.get("picture_book_page_size", DEFAULT_PICTURE_BOOK_PAGE_SIZE))
                else:
                    docx_bytes = build_final_output_docx_bytes(get_project_title_for_display(), final_text, selected_final_format)
                project_stem = safe_download_stem(get_project_title_for_display(), "writersblock_project")
                format_stem = safe_download_stem(get_automatic_output_label(selected_final_format), "final_output")
                st.download_button(label=f"Download Final {get_automatic_output_label(selected_final_format)} (.docx)", data=docx_bytes, file_name=f"{project_stem}_{format_stem}_final.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary", use_container_width=True)

        st.markdown("---")
        if st.button("Return to Script Rewrite 🛠️", key="return_to_script_rewrite_from_final", use_container_width=True):
            st.session_state.project_stage = "Rewrite Engine"
            st.session_state.export_view = False
            st.rerun()
        st.stop()

    if st.session_state.get("export_view", False):
        if st.session_state.get("demo_mode"):
            st.header("📤 Step 8: Manuscript Review")
            st.markdown("##### Review the completed manuscript. Final manuscript saving and printout are available in the full Writer Edition.")
        else:
            st.header("📤 Step 8: FINAL OUTPUT")
            st.markdown("##### This is the final manuscript output stage. Save the final manuscript before downloading or starting a new project.")
        render_project_title_banner("step_8_manuscript_output")
    else:
        st.header("🛡️ Step 5: Script Lock")
        st.markdown("##### Verify the current manuscript before downloading the draft or proceeding to Script Rewrite.")
        render_project_title_banner("step_5_script_lock")
    st.markdown("---")

    if st.session_state.get("export_view", False):
        st.info("✅ FINAL OUTPUT is ready. Save the final manuscript before downloading or starting a new project.")
    else:
        st.info("✅ Script Lock check complete. This is still a draft until it is saved as FINAL OUTPUT in Step 8.")

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

        st.text_area(
            "Review Manuscript:",
            value=st.session_state.current_draft_output,
            height=500,
            key="final_manuscript_export_view",
        )

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
                    st.session_state.project_stage = "Rewrite Engine"
                    st.rerun()
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

    st.header("🧠 Step 6: Script Polish")
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
                    st.session_state.project_stage = "Rewrite Engine"
                    st.rerun()
            else:
                st.button("🔒 Script Rewrite Locked", key="rewrite_locked_from_revision", disabled=True, use_container_width=True)
# ============================================================
# PHASE 7: SCRIPT REWRITE
# ============================================================
elif st.session_state.project_stage == "Rewrite Engine":
    require_product_access("rewrite")

    st.header("🛠️ Step 7: Script Rewrite")
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

                            rewrite_instruction_packet = (
                                get_rewrite_dialogue_instruction(rewrite_dialogue_choice)
                                + "\n\nADDITIONAL CREATOR REWRITE DIRECTION:\n"
                                + (custom_rewrite_instruction.strip() if custom_rewrite_instruction.strip() else "No additional rewrite direction provided.")
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
                st.session_state.project_stage = "Isolation Guardrail"
                st.session_state.export_view = True

                try:
                    save_current_project_session_to_supabase()
                except Exception:
                    pass

                st.rerun()


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
                        + " Project session was not saved automatically. Use Save Project before leaving."
                    )

                st.session_state.project_stage = "Isolation Guardrail"
                st.session_state.export_view = True
                st.rerun()

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
