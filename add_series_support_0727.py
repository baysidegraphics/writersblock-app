#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

OUTPUT_NAME = "app-Writer-Edition-Series-0727.py"

class PatchError(RuntimeError):
    pass

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise PatchError(f"{label}: expected 1 match, found {count}.")
    return source.replace(old, new, 1)

def regex_replace_once(source, pattern, replacement, label, flags=0):
    updated, count = re.subn(pattern, replacement, source, count=1, flags=flags)
    if count != 1:
        raise PatchError(f"{label}: expected 1 match, found {count}.")
    return updated

SERIES_HELPERS = '# ==========================================\n# SERIES CONTINUITY SUPPORT\n# ==========================================\ndef make_series_key(series_name):\n    clean_name = re.sub(r"[^a-z0-9]+", "-", str(series_name or "").strip().lower()).strip("-")\n    if not clean_name:\n        return ""\n    user_id = str(get_current_user_id() or "local-user")\n    return hashlib.sha256(f"{user_id}:{clean_name}".encode("utf-8")).hexdigest()[:24]\n\n\ndef get_series_metadata_rows():\n    user_id = get_current_user_id()\n    query = (\n        supabase.table("writersblock_project_drafts")\n        .select("id, project_id, user_id, draft_content, created_at")\n        .eq("draft_type", "series_metadata")\n        .order("created_at", desc=True)\n    )\n    if user_id:\n        query = query.eq("user_id", user_id)\n    try:\n        result = query.execute()\n    except Exception:\n        return []\n\n    rows = []\n    seen_project_ids = set()\n    for row in result.data or []:\n        project_id = row.get("project_id")\n        if not project_id or project_id in seen_project_ids:\n            continue\n        try:\n            metadata = json.loads(row.get("draft_content") or "{}")\n        except Exception:\n            metadata = {}\n        if not isinstance(metadata, dict):\n            continue\n        metadata["_project_id"] = project_id\n        metadata["_created_at"] = row.get("created_at")\n        rows.append(metadata)\n        seen_project_ids.add(project_id)\n    return rows\n\n\ndef get_series_metadata_by_project():\n    return {\n        row.get("_project_id"): row\n        for row in get_series_metadata_rows()\n        if row.get("_project_id")\n    }\n\n\ndef get_existing_series_names():\n    names = []\n    for metadata in get_series_metadata_rows():\n        series_name = str(metadata.get("series_name") or "").strip()\n        if series_name and series_name not in names:\n            names.append(series_name)\n    return sorted(names, key=str.lower)\n\n\ndef save_series_metadata_for_project(project_id=None):\n    if st.session_state.get("project_scope") != "Book in a Series":\n        return None\n\n    series_name = str(st.session_state.get("series_name") or "").strip()\n    if not series_name:\n        return None\n\n    project_id = project_id or get_active_project_id()\n    user_id = get_current_user_id()\n    if not project_id or not user_id:\n        return None\n\n    series_key = make_series_key(series_name)\n    st.session_state.series_key = series_key\n    metadata = {\n        "series_key": series_key,\n        "series_name": series_name,\n        "series_book_number": int(st.session_state.get("series_book_number", 1) or 1),\n        "series_continuity_mode": str(st.session_state.get("series_continuity_mode", "Strict")),\n        "series_reference_ids": list(st.session_state.get("series_reference_ids", []) or []),\n        "series_canon_notes": str(st.session_state.get("series_canon_notes", "") or "").strip(),\n        "project_title": get_project_title_for_display(),\n        "saved_at": datetime.now(timezone.utc).isoformat(),\n    }\n\n    return (\n        supabase.table("writersblock_project_drafts")\n        .insert({\n            "project_id": project_id,\n            "user_id": user_id,\n            "draft_title": f"{series_name} — Book {metadata[\'series_book_number\']} Series Metadata",\n            "draft_type": "series_metadata",\n            "draft_content": json.dumps(metadata),\n            "version_number": metadata["series_book_number"],\n        })\n        .execute()\n    )\n\n\ndef get_series_reference_candidates():\n    metadata_by_project = get_series_metadata_by_project()\n    current_project_id = st.session_state.get("current_project_id")\n    candidates = []\n    manuscript_project_ids = set()\n\n    try:\n        manuscript_versions = get_manuscript_versions_for_current_project()\n    except Exception:\n        manuscript_versions = []\n\n    for version in manuscript_versions:\n        project_id = version.get("project_id")\n        if not project_id or project_id == current_project_id:\n            continue\n\n        manuscript_text = str(version.get("manuscript_content") or "").strip()\n        if not manuscript_text:\n            continue\n\n        project_join = version.get("writersblock_projects") or {}\n        joined_title = project_join.get("project_title") if isinstance(project_join, dict) else ""\n        title = str(\n            joined_title\n            or version.get("project_title")\n            or get_project_title_from_project_id(project_id)\n            or "Untitled Project"\n        ).strip()\n\n        metadata = metadata_by_project.get(project_id, {})\n        book_number = int(metadata.get("series_book_number") or 0)\n        series_name = str(metadata.get("series_name") or "").strip()\n        prefix = f"{series_name} — Book {book_number} — " if series_name and book_number else ""\n        version_number = int(version.get("version_number") or 1)\n\n        candidates.append({\n            "id": f"manuscript:{version.get(\'id\')}",\n            "label": f"{prefix}{title} — Manuscript V{version_number} — {count_words(manuscript_text):,} words",\n            "project_id": project_id,\n            "title": title,\n            "book_number": book_number,\n            "series_name": series_name,\n            "series_key": str(metadata.get("series_key") or ""),\n            "text": manuscript_text,\n        })\n        manuscript_project_ids.add(project_id)\n\n    try:\n        saved_sessions = get_saved_project_sessions_for_dropdown()\n    except Exception:\n        saved_sessions = []\n\n    seen_session_projects = set()\n    for saved_row in saved_sessions:\n        project_id = saved_row.get("project_id")\n        if (\n            not project_id\n            or project_id == current_project_id\n            or project_id in manuscript_project_ids\n            or project_id in seen_session_projects\n        ):\n            continue\n\n        try:\n            snapshot = json.loads(saved_row.get("draft_content") or "{}")\n        except Exception:\n            snapshot = {}\n\n        manuscript_text = str(\n            snapshot.get("current_draft_output")\n            or snapshot.get("rewritten_manuscript")\n            or snapshot.get("manuscript_text")\n            or ""\n        ).strip()\n        if not manuscript_text:\n            continue\n\n        title = str(\n            snapshot.get("project_title")\n            or get_project_title_from_project_id(project_id)\n            or "Untitled Project"\n        ).strip()\n        metadata = metadata_by_project.get(project_id, {})\n        book_number = int(metadata.get("series_book_number") or snapshot.get("series_book_number") or 0)\n        series_name = str(metadata.get("series_name") or snapshot.get("series_name") or "").strip()\n        series_key = str(metadata.get("series_key") or snapshot.get("series_key") or "")\n        prefix = f"{series_name} — Book {book_number} — " if series_name and book_number else ""\n\n        candidates.append({\n            "id": f"session:{saved_row.get(\'id\')}",\n            "label": f"{prefix}{title} — Saved Project — {count_words(manuscript_text):,} words",\n            "project_id": project_id,\n            "title": title,\n            "book_number": book_number,\n            "series_name": series_name,\n            "series_key": series_key,\n            "text": manuscript_text,\n        })\n        seen_session_projects.add(project_id)\n\n    candidates.sort(\n        key=lambda item: (\n            str(item.get("series_name") or "").lower(),\n            int(item.get("book_number") or 9999),\n            str(item.get("title") or "").lower(),\n        )\n    )\n\n    used_labels = {}\n    for candidate in candidates:\n        base_label = candidate["label"]\n        used_labels[base_label] = used_labels.get(base_label, 0) + 1\n        if used_labels[base_label] > 1:\n            candidate["label"] = f"{base_label} ({used_labels[base_label]})"\n    return candidates\n\n\ndef get_selected_series_reference_records():\n    selected_ids = set(st.session_state.get("series_reference_ids", []) or [])\n    return [\n        candidate\n        for candidate in get_series_reference_candidates()\n        if candidate.get("id") in selected_ids\n    ]\n\n\ndef get_series_continuity_instruction():\n    mode = str(st.session_state.get("series_continuity_mode", "Strict"))\n    if mode == "Flexible":\n        return (\n            "Preserve major identities, timeline anchors, and established endings. "\n            "Minor descriptive details may evolve, but do not silently contradict earlier books."\n        )\n    if mode == "Balanced":\n        return (\n            "Preserve established characters, relationships, chronology, locations, important "\n            "objects, mythology, and unresolved story threads. Flag deliberate canon changes."\n        )\n    return (\n        "Treat all established facts in selected books and canon notes as locked series canon. "\n        "Do not contradict character histories, chronology, relationships, locations, object "\n        "rules, mythology, previous endings, or protected mysteries."\n    )\n\n\ndef build_series_context_text(max_total_chars=60000, per_source_chars=25000):\n    if st.session_state.get("project_scope") != "Book in a Series":\n        return ""\n\n    series_name = str(st.session_state.get("series_name") or "").strip()\n    if not series_name:\n        return ""\n\n    book_number = int(st.session_state.get("series_book_number", 1) or 1)\n    canon_notes = str(st.session_state.get("series_canon_notes", "") or "").strip()\n    records = get_selected_series_reference_records()\n\n    parts = [\n        "SERIES CONTINUITY PACKAGE",\n        f"Series Name: {series_name}",\n        f"Current Book Number: {book_number}",\n        f"Continuity Mode: {st.session_state.get(\'series_continuity_mode\', \'Strict\')}",\n        f"Continuity Rule: {get_series_continuity_instruction()}",\n    ]\n\n    if canon_notes:\n        parts.extend(["", "AUTHOR-LOCKED SERIES CANON NOTES:", canon_notes])\n    if records:\n        parts.extend(["", "SELECTED PREVIOUS BOOK REFERENCES:"])\n\n    used_chars = sum(len(part) for part in parts)\n\n    for record in records:\n        remaining = max_total_chars - used_chars\n        if remaining <= 500:\n            parts.append("\\n[Additional selected references omitted because the context limit was reached.]")\n            break\n\n        source_text = str(record.get("text") or "").strip()\n        allowed = min(per_source_chars, remaining)\n        clipped = source_text[:allowed]\n        if len(source_text) > allowed:\n            clipped += "\\n[Reference shortened for this request. The full manuscript remains stored.]"\n\n        block = (\n            f"\\n--- PREVIOUS BOOK: {record.get(\'title\', \'Untitled\')} ---\\n"\n            f"{clipped}\\n"\n            "--- END PREVIOUS BOOK REFERENCE ---"\n        )\n        parts.append(block)\n        used_chars += len(block)\n\n    if not records and not canon_notes:\n        parts.extend(["", "No previous book manuscript or canon notes have been selected yet."])\n\n    return "\\n".join(parts).strip()\n\n\ndef get_series_aware_story_seed():\n    plot_line = str(st.session_state.get("story_seed") or "").strip()\n    series_context = build_series_context_text()\n    if not series_context:\n        return plot_line\n\n    return f"""\nAUTHOR\'S NEW BOOK PLOT LINE:\n{plot_line}\n\n{series_context}\n\nDEVELOPMENT INSTRUCTION:\nDevelop the new book from the author\'s plot line while using the series continuity package\nas controlling reference material. Continue appropriate unresolved threads, preserve character\nidentity and chronology, and do not repeat the plots of earlier books.\n""".strip()\n'
SERIES_UI = '\nst.markdown("---")\nst.markdown("### Project Connection")\n\nproject_scope_options = ["Standalone Book", "Book in a Series"]\ncurrent_project_scope = str(st.session_state.get("project_scope", "Standalone Book"))\n\nst.session_state.project_scope = st.radio(\n    "Project Type:",\n    project_scope_options,\n    index=project_scope_options.index(current_project_scope)\n    if current_project_scope in project_scope_options else 0,\n    horizontal=True,\n    key="project_scope_selector",\n)\n\nif st.session_state.project_scope == "Book in a Series":\n    existing_series_names = get_existing_series_names()\n    series_choice_options = existing_series_names + ["Create New Series"]\n    current_series_name = str(st.session_state.get("series_name", "") or "").strip()\n    default_series_choice = current_series_name if current_series_name in existing_series_names else "Create New Series"\n\n    selected_series_choice = st.selectbox(\n        "Select Series:",\n        series_choice_options,\n        index=series_choice_options.index(default_series_choice),\n        key="series_choice_selector",\n    )\n\n    if selected_series_choice == "Create New Series":\n        st.session_state.series_name = st.text_input(\n            "Series Name:",\n            value=current_series_name,\n            placeholder="Example: Oakhaven",\n            key="series_name_input",\n        ).strip()\n    else:\n        st.session_state.series_name = selected_series_choice\n\n    series_col_1, series_col_2 = st.columns(2)\n    with series_col_1:\n        st.session_state.series_book_number = int(\n            st.number_input(\n                "Book Number:",\n                min_value=1,\n                max_value=100,\n                value=int(st.session_state.get("series_book_number", 1) or 1),\n                step=1,\n                key="series_book_number_input",\n            )\n        )\n\n    with series_col_2:\n        continuity_options = ["Strict", "Balanced", "Flexible"]\n        current_continuity = str(st.session_state.get("series_continuity_mode", "Strict"))\n        st.session_state.series_continuity_mode = st.selectbox(\n            "Continuity Mode:",\n            continuity_options,\n            index=continuity_options.index(current_continuity)\n            if current_continuity in continuity_options else 0,\n            key="series_continuity_mode_selector",\n        )\n\n    st.session_state.series_key = make_series_key(st.session_state.series_name)\n\n    candidates = get_series_reference_candidates()\n    label_to_id = {candidate["label"]: candidate["id"] for candidate in candidates}\n    id_to_label = {candidate["id"]: candidate["label"] for candidate in candidates}\n\n    valid_saved_ids = [\n        reference_id\n        for reference_id in (st.session_state.get("series_reference_ids", []) or [])\n        if reference_id in id_to_label\n    ]\n    auto_series_ids = [\n        candidate["id"]\n        for candidate in candidates\n        if (\n            st.session_state.series_key\n            and candidate.get("series_key") == st.session_state.series_key\n            and int(candidate.get("book_number") or 0) < st.session_state.series_book_number\n        )\n    ]\n\n    selection_signature = f"{st.session_state.series_key}:{st.session_state.series_book_number}"\n    if st.session_state.get("series_selection_signature") != selection_signature:\n        default_ids = valid_saved_ids or auto_series_ids\n        st.session_state.series_reference_selector = [\n            id_to_label[reference_id]\n            for reference_id in default_ids\n            if reference_id in id_to_label\n        ]\n        st.session_state.series_selection_signature = selection_signature\n\n    if candidates:\n        selected_labels = st.multiselect(\n            "Previous Books to Reference:",\n            options=list(label_to_id.keys()),\n            key="series_reference_selector",\n            help="Select completed saved books that WritersBlock must use for continuity.",\n        )\n        st.session_state.series_reference_ids = [\n            label_to_id[label] for label in selected_labels if label in label_to_id\n        ]\n    else:\n        st.session_state.series_reference_ids = []\n        st.info(\n            "No completed saved manuscripts are available yet. Save earlier books through "\n            "Manuscript Output, then return here to attach them to the series."\n        )\n\n    st.session_state.series_canon_notes = st.text_area(\n        "Series Bible / Locked Canon Notes:",\n        value=str(st.session_state.get("series_canon_notes", "") or ""),\n        height=160,\n        placeholder=(\n            "Enter facts that must remain consistent: character ages, relationships, timeline "\n            "dates, mythology, object rules, unresolved mysteries, and protected reveals."\n        ),\n        key="series_canon_notes_input",\n    )\n\n    reference_count = len(st.session_state.get("series_reference_ids", []) or [])\n    st.success(\n        f"Series Continuity Active: {st.session_state.series_name or \'Name Required\'} — "\n        f"Book {st.session_state.series_book_number} — {reference_count} previous "\n        f"book{\'\' if reference_count == 1 else \'s\'} selected."\n    )\nelse:\n    st.session_state.series_key = ""\n    st.session_state.series_reference_ids = []\n\n'

def apply_patches(source):
    source = replace_once(
        source,
        '# WRITERSBLOCK_STUDIOS_WRITER_EDITION_V1_AUDIOBOOK_PRODUCTION',
        '# WRITERSBLOCK_STUDIOS_WRITER_EDITION_V1_SERIES_SUPPORT_0727',
        'Build identifier',
    )

    source = replace_once(
        source,
        '        "project_title",\n        "format_type",',
        '        "project_title",\n        "project_scope",\n        "series_key",\n        "series_name",\n        "series_book_number",\n        "series_continuity_mode",\n        "series_reference_ids",\n        "series_canon_notes",\n        "series_selection_signature",\n        "format_type",',
        'Snapshot fields',
    )

    source = replace_once(
        source,
        'if "project_title" not in st.session_state:\n    st.session_state.project_title = ""\n\nif "format_type" not in st.session_state:',
        'if "project_title" not in st.session_state:\n    st.session_state.project_title = ""\n\nif "project_scope" not in st.session_state:\n    st.session_state.project_scope = "Standalone Book"\n\nif "series_key" not in st.session_state:\n    st.session_state.series_key = ""\n\nif "series_name" not in st.session_state:\n    st.session_state.series_name = ""\n\nif "series_book_number" not in st.session_state:\n    st.session_state.series_book_number = 1\n\nif "series_continuity_mode" not in st.session_state:\n    st.session_state.series_continuity_mode = "Strict"\n\nif "series_reference_ids" not in st.session_state:\n    st.session_state.series_reference_ids = []\n\nif "series_canon_notes" not in st.session_state:\n    st.session_state.series_canon_notes = ""\n\nif "series_selection_signature" not in st.session_state:\n    st.session_state.series_selection_signature = ""\n\nif "format_type" not in st.session_state:',
        'Series state initialization',
    )

    source = replace_once(source, '\ndef get_current_plan_tier():', '\n' + SERIES_HELPERS + '\ndef get_current_plan_tier():', 'Series helpers')

    old_ui = '    st.session_state.project_title = st.text_input(\n        "Project / Story Title:",\n        value=st.session_state.get("project_title", ""),\n        placeholder="Example: It\'s Not Safe",\n        key="project_title_input",\n    ).strip()\n\n    format_options = list(SPARK_BANK.keys())'
    new_ui = '    st.session_state.project_title = st.text_input(\n        "Project / Story Title:",\n        value=st.session_state.get("project_title", ""),\n        placeholder="Example: It\'s Not Safe",\n        key="project_title_input",\n    ).strip()\n\n' + SERIES_UI + '    format_options = list(SPARK_BANK.keys())'
    source = replace_once(source, old_ui, new_ui, 'Series UI')

    source = regex_replace_once(
        source,
        '(st\\.session_state\\.sandbox_slates\\s*=\\s*st\\.session_state\\.backend\\.generate_sandbox_slates\\(\\s*\\n\\s*)story_seed=st\\.session_state\\.story_seed,',
        '\\1story_seed=get_series_aware_story_seed(),',
        'Concept continuity',
        flags=re.MULTILINE,
    )

    source = replace_once(
        source,
        '            save_project_to_supabase(\n                project_title=get_project_title_for_display()[:80],\n                project_type=st.session_state.format_type,\n            )\n\n            if st.session_state.get("demo_mode"):',
        '            save_project_to_supabase(\n                project_title=get_project_title_for_display()[:80],\n                project_type=st.session_state.format_type,\n            )\n\n            if st.session_state.get("project_scope") == "Book in a Series":\n                save_series_metadata_for_project(\n                    st.session_state.get("current_project_id")\n                )\n\n            if st.session_state.get("demo_mode"):',
        'Save series metadata',
    )

    source = regex_replace_once(
        source,
        '(st\\.session_state\\.plot_outline\\s*=\\s*st\\.session_state\\.backend\\.generate_plot_outline\\([\\s\\S]*?\\n\\s*)story_seed=st\\.session_state\\.story_seed,',
        '\\1story_seed=get_series_aware_story_seed(),',
        'Plot continuity',
        flags=re.MULTILINE,
    )

    source = regex_replace_once(
        source,
        '(st\\.session_state\\.plot_outline\\s*=\\s*st\\.session_state\\.backend\\.generate_plot_outline\\([\\s\\S]*?\\n\\s*)format_type=st\\.session_state\\.format_type,',
        '\\1format_type=get_effective_format_type(),',
        'Plot format',
        flags=re.MULTILINE,
    )

    source = replace_once(
        source,
        '                current_beat_data = filtered_beats[current_scene_number - 1]\n                require_writer_credits("draft_scene")\n\n                drafting_instruction_packet = f"""',
        '                current_beat_data = filtered_beats[current_scene_number - 1]\n                require_writer_credits("draft_scene")\n\n                series_drafting_context = build_series_context_text(\n                    max_total_chars=18000,\n                    per_source_chars=8000,\n                )\n\n                drafting_instruction_packet = f"""',
        'Draft continuity setup',
    )

    source = replace_once(
        source,
        'Scene Purpose / Special Instructions: {scene_notes}\n\nCURRENT OUTLINE BEAT:',
        'Scene Purpose / Special Instructions: {scene_notes}\n\nSERIES CONTINUITY REFERENCE:\n{series_drafting_context or "This is a standalone book with no series reference package."}\n\nCURRENT OUTLINE BEAT:',
        'Draft continuity packet',
    )

    source = regex_replace_once(
        source,
        '(raw_response\\s*=\\s*st\\.session_state\\.backend\\.execute_recursive_draft_chunk\\([\\s\\S]*?\\n\\s*)format_type=st\\.session_state\\.format_type,',
        '\\1format_type=get_effective_format_type(),',
        'Draft format',
        flags=re.MULTILINE,
    )

    source = replace_once(
        source,
        '    result = supabase.table("writersblock_project_drafts").insert({\n        "project_id": project_id,\n        "user_id": user_id,\n        "draft_title": "Saved Project Session",\n        "draft_type": "project_session",\n        "draft_content": json.dumps(snapshot),\n        "version_number": int(st.session_state.get("current_processing_beat", 1) or 1),\n    }).execute()\n\n    return result\n\n\ndef get_latest_saved_project_session():',
        '    result = supabase.table("writersblock_project_drafts").insert({\n        "project_id": project_id,\n        "user_id": user_id,\n        "draft_title": "Saved Project Session",\n        "draft_type": "project_session",\n        "draft_content": json.dumps(snapshot),\n        "version_number": int(st.session_state.get("current_processing_beat", 1) or 1),\n    }).execute()\n\n    if result and st.session_state.get("project_scope") == "Book in a Series":\n        save_series_metadata_for_project(project_id)\n\n    return result\n\n\ndef get_latest_saved_project_session():',
        'Save metadata with project session',
    )

    source = replace_once(
        source,
        '    st.write(f"Current Project: {get_project_title_for_display()}")\n    st.write(f"Manuscript Version: {st.session_state.manuscript_version}")',
        '    st.write(f"Current Project: {get_project_title_for_display()}")\n\n    if st.session_state.get("project_scope") == "Book in a Series":\n        st.write(\n            f"Series: {st.session_state.get(\'series_name\') or \'Unnamed Series\'} "\n            f"— Book {int(st.session_state.get(\'series_book_number\', 1) or 1)}"\n        )\n\n    st.write(f"Manuscript Version: {st.session_state.manuscript_version}")',
        'Sidebar series status',
    )

    global_start = source.find('if st.sidebar.button("⚠️ Start New Project"')
    if global_start == -1:
        raise PatchError('Global reset block not found.')
    reset_old = '    st.session_state.project_title = ""\n'
    reset_new = '    st.session_state.project_title = ""\n    st.session_state.project_scope = "Standalone Book"\n    st.session_state.series_key = ""\n    st.session_state.series_name = ""\n    st.session_state.series_book_number = 1\n    st.session_state.series_continuity_mode = "Strict"\n    st.session_state.series_reference_ids = []\n    st.session_state.series_canon_notes = ""\n    st.session_state.series_selection_signature = ""\n    st.session_state.pop("series_reference_selector", None)\n    st.session_state.pop("series_choice_selector", None)\n    st.session_state.pop("series_name_input", None)\n'
    reset_index = source.find(reset_old, global_start)
    if reset_index == -1:
        raise PatchError('Global reset title marker not found.')
    source = source[:reset_index] + reset_new + source[reset_index + len(reset_old):]

    source = regex_replace_once(
        source,
        '(if st\\.button\\("🔄 Start New Project", use_container_width=True\\):\\n\\s+st\\.session_state\\.project_stage = "Intake"\\n)',
        '\\1            st.session_state.project_scope = "Standalone Book"\n            st.session_state.series_key = ""\n            st.session_state.series_name = ""\n            st.session_state.series_book_number = 1\n            st.session_state.series_continuity_mode = "Strict"\n            st.session_state.series_reference_ids = []\n            st.session_state.series_canon_notes = ""\n            st.session_state.series_selection_signature = ""\n            st.session_state.pop("series_reference_selector", None)\n            st.session_state.pop("series_choice_selector", None)\n            st.session_state.pop("series_name_input", None)\n',
        'Output reset',
        flags=re.MULTILINE,
    )

    return source

def main():
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('app-Writer-Edition-Audiobook-Production.py')
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    output_path = source_path.with_name(OUTPUT_NAME)
    source = source_path.read_text(encoding='utf-8')
    updated = apply_patches(source)
    compile(updated, str(output_path), 'exec')
    output_path.write_text(updated, encoding='utf-8')
    print(f"Source preserved: {source_path.name}")
    print(f"Created: {output_path.name}")
    print('Python syntax validation passed.')
    print(f"Test with: streamlit run {output_path.name}")

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
