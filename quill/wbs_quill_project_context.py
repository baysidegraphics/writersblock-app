"""
WritersBlock Studios
Quill Project Awareness / Safe Routing Layer
Version: 1.0
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, MutableMapping, Optional

try:
    from wbs_decision_engine import WBSDecisionEngine, WBSProjectSnapshot
except Exception:
    WBSDecisionEngine = None
    WBSProjectSnapshot = None

QUILL_PROJECT_CONTEXT_VERSION = "1.0"

CONTEXT_ISSUES_KEY = "_wbs_quill_context_issues_v1"
PENDING_WORKAROUND_KEY = "_wbs_quill_pending_workaround_v1"

STEP_NAMES = {
    1: "Concept Development",
    2: "Story Path Selection",
    3: "Plot Development",
    4: "Creative Draft",
    5: "Script Lock",
    6: "Script Polish",
    7: "Script Rewrite",
    8: "Final Output",
}

ACTION_STEP = {
    "generate_sandbox": 1,
    "select_sandbox_path": 2,
    "generate_plot": 3,
    "draft_next_beat": 4,
    "review_script_lock": 5,
    "run_polish": 6,
    "run_rewrite": 7,
    "generate_final_output": 8,
    "build_picture_book_layout": 8,
}

STATE_CHANGING_ACTIONS = {
    "generate_sandbox", "select_sandbox_path", "generate_plot", "draft_next_beat",
    "review_script_lock", "save_draft", "run_polish", "run_rewrite",
    "skip_rewrite", "generate_final_output", "build_picture_book_layout",
    "save_final", "save_project", "manage_version", "rename_project",
}

def clean(value: Any) -> str:
    return str(value or "").strip()

def get_value(state: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return state.get(key, default)
    except Exception:
        try:
            return state[key]
        except Exception:
            return default

def count_words(text: Any) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", clean(text), flags=re.UNICODE))

def project_title(state: Mapping[str, Any]) -> str:
    return clean(
        get_value(state, "project_title", "")
        or get_value(state, "current_project_title", "")
        or get_value(state, "project_name", "")
    )

def current_manuscript(state: Mapping[str, Any]) -> str:
    for key in (
        "rewritten_manuscript",
        "current_draft_output",
        "manuscript_text",
        "imported_source_text",
        "final_output_text",
    ):
        value = get_value(state, key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""

def current_step(state: Mapping[str, Any]) -> tuple[int, str]:
    if WBSProjectSnapshot is not None:
        try:
            snap = WBSProjectSnapshot.from_mapping(state)
            return int(snap.step), str(snap.stage_name)
        except Exception:
            pass

    stage = clean(get_value(state, "project_stage", ""))
    export_view = bool(get_value(state, "export_view", False))

    if stage == "Intake":
        return 1, STEP_NAMES[1]
    if stage in {"Sandbox", "Sandbox Engine", "Sandbox Selection"}:
        return 2, STEP_NAMES[2]
    if stage in {"Plotting", "Plot Engine", "Plot Development"}:
        return 3, STEP_NAMES[3]
    if stage == "Drafting Engine":
        return 4, STEP_NAMES[4]
    if stage == "Isolation Guardrail":
        return (8, STEP_NAMES[8]) if export_view else (5, STEP_NAMES[5])
    if stage == "Revision Engine":
        return 6, STEP_NAMES[6]
    if stage == "Rewrite Engine":
        return 7, STEP_NAMES[7]
    return 0, stage or "Current Project"

def has_loaded_project(state: Mapping[str, Any]) -> bool:
    if clean(get_value(state, "current_project_id", "")):
        return True
    if project_title(state) and current_manuscript(state):
        return True
    try:
        if int(get_value(state, "manuscript_version", 0) or 0) > 0:
            return True
    except Exception:
        pass
    return False

def build_context(state: Mapping[str, Any]) -> dict[str, Any]:
    try:
        ctx = dict(state)
    except Exception:
        ctx = {}

    step, stage_name = current_step(state)
    manuscript = current_manuscript(state)
    title = project_title(state)

    ctx["project_title"] = title
    ctx["wbs_current_step"] = step
    ctx["wbs_current_stage_name"] = stage_name
    ctx["current_manuscript"] = manuscript
    ctx["current_manuscript_word_count"] = count_words(manuscript)
    ctx["selected_final_output_format"] = clean(
        get_value(state, "final_output_format", "")
    )

    ctx["quill_project_reference"] = {
        "title": title,
        "step": step,
        "stage": stage_name,
        "format_type": clean(get_value(state, "format_type", "")),
        "final_output_format": ctx["selected_final_output_format"],
        "dialogue_style": clean(get_value(state, "dialogue_style", "")),
        "story_seed": clean(get_value(state, "story_seed", "")),
        "chosen_option": get_value(state, "chosen_option", ""),
        "chosen_option_text": get_value(state, "chosen_option_text", ""),
        "plot_outline": get_value(state, "plot_outline", ""),
        "rolling_lore_book": get_value(state, "rolling_lore_book", ""),
        "revision_report": get_value(state, "revision_report", ""),
        "manuscript_word_count": ctx["current_manuscript_word_count"],
        "current_project_id": clean(get_value(state, "current_project_id", "")),
        "manuscript_version": get_value(state, "manuscript_version", 0),
    }
    return ctx

def context_signature(state: Mapping[str, Any]) -> str:
    ref = build_context(state)["quill_project_reference"]
    raw = repr((
        ref.get("current_project_id"), ref.get("title"), ref.get("step"),
        ref.get("stage"), ref.get("manuscript_version"),
        ref.get("manuscript_word_count"), ref.get("final_output_format"),
    ))
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]

def record_issue(
    state: MutableMapping[str, Any],
    *,
    code: str,
    message: str,
    user_text: str = "",
    suggested_workaround: str = "",
) -> dict[str, Any]:
    issues = list(state.get(CONTEXT_ISSUES_KEY, []) or [])
    item = {
        "code": clean(code) or "QUILL_CONTEXT",
        "message": clean(message),
        "question": clean(user_text)[:500],
        "project_id": clean(get_value(state, "current_project_id", "")),
        "project_title": project_title(state),
        "context_signature": context_signature(state),
        "suggested_workaround": clean(suggested_workaround),
    }
    if not issues or issues[-1] != item:
        issues.append(item)
    state[CONTEXT_ISSUES_KEY] = issues[-20:]
    if suggested_workaround:
        state[PENDING_WORKAROUND_KEY] = clean(suggested_workaround)
    return item

def recovery_text(
    state: MutableMapping[str, Any],
    *,
    message: str,
    user_text: str = "",
    workaround: str = "",
) -> tuple[str, dict[str, Any]]:
    issue = record_issue(
        state,
        code="QUILL_CONTEXT_RECOVERY",
        message=message,
        user_text=user_text,
        suggested_workaround=workaround,
    )
    parts = [
        "I found an inconsistency in the current WritersBlock context. "
        "I have flagged it for correction and your project has not been changed."
    ]
    if workaround:
        parts.append(
            f"A possible workaround is: {workaround} "
            "I will not apply or guide a state-changing workaround unless you approve it."
        )
    parts.append(
        "You can continue working and asking me questions that do not require that blocked change. "
        "If the problem continues, Customer Support can use the context details recorded for this session."
    )
    return " ".join(parts), issue

def approved_workaround_reply(
    state: MutableMapping[str, Any],
    user_text: str,
) -> Optional[str]:
    pending = clean(state.get(PENDING_WORKAROUND_KEY, ""))
    if not pending:
        return None
    lower = clean(user_text).lower()
    approvals = {
        "yes", "yes please", "ok", "okay", "go ahead",
        "show me", "show me the workaround", "try the workaround",
        "yes show me", "yes, show me the workaround",
    }
    if lower not in approvals:
        return None

    state[PENDING_WORKAROUND_KEY] = ""
    return (
        f"Approved. The suggested workaround is: {pending} "
        "Use the normal WritersBlock controls for the change. I will continue to guide you, "
        "but I will not silently alter the project or switch stages/projects for you."
    )

def direct_fact(state: Mapping[str, Any], user_text: str) -> Optional[dict[str, str]]:
    """Answer simple facts about the CURRENT loaded WritersBlock project."""
    text = clean(user_text)
    if not text:
        return None

    normalized = re.sub(r"[^a-z0-9\s]", "", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    ctx = build_context(state)
    step = int(ctx.get("wbs_current_step") or 0)
    stage = clean(ctx.get("wbs_current_stage_name", "")) or "Current Project"
    title = clean(ctx.get("project_title", ""))
    manuscript = clean(ctx.get("current_manuscript", ""))
    output_format = clean(ctx.get("selected_final_output_format", ""))
    base_format = clean(ctx.get("format_type", ""))

    if (
        "word count" in normalized
        or "how many words" in normalized
        or "number of words" in normalized
    ):
        if manuscript:
            count = int(ctx.get("current_manuscript_word_count") or 0)
            suffix = f' for "{title}"' if title else ""
            answer = f"The current working manuscript{suffix} is {count:,} words."
        else:
            answer = "There is no working manuscript loaded in the current project to count yet."
        return {"text": answer, "stage": stage, "source": "project_context"}

    stage_phrases = (
        "where am i",
        "where are we",
        "what stage am i in",
        "what stage are we in",
        "what step am i on",
        "what step are we on",
        "current stage",
        "current step",
    )
    if any(phrase in normalized for phrase in stage_phrases):
        suffix = f' in "{title}"' if title else ""
        answer = (
            f"You are at Step {step}: {stage}{suffix}."
            if step
            else f"You are in {stage}{suffix}."
        )
        return {"text": answer, "stage": stage, "source": "project_context"}

    project_phrases = (
        "what project is this",
        "what project are we in",
        "what story is this",
        "what story are we working on",
        "what is the project title",
        "project title",
    )
    if any(phrase in normalized for phrase in project_phrases):
        answer = (
            f'You are working in "{title}".'
            if title
            else "The current project does not have a saved title."
        )
        return {"text": answer, "stage": stage, "source": "project_context"}

    if (
        "output format" in normalized
        or normalized in {"what format is this", "what format am i using"}
    ):
        if output_format:
            answer = f"The selected Final Output format is {output_format}."
        elif base_format:
            answer = f"The current writing format is {base_format}."
        else:
            answer = "No writing or output format is currently available in the active project context."
        return {"text": answer, "stage": stage, "source": "project_context"}

    return None

def _explicit_other_project_request(user_text: str) -> bool:
    lower = clean(user_text).lower()
    return any(phrase in lower for phrase in (
        "another project", "different project", "other project",
        "saved project", "previous project", "my other book", "my other story",
    ))

def route_action(state: Mapping[str, Any], user_text: str) -> Optional[dict[str, str]]:
    if WBSDecisionEngine is None:
        return None
    try:
        decision = WBSDecisionEngine().analyze(user_text, build_context(state))
    except Exception:
        return None

    action = getattr(decision, "action", None)
    action_value = clean(getattr(action, "value", action))
    if not action_value or action_value in {"general", "status", "research", "business", "technical"}:
        return None

    step, stage_name = current_step(state)

    if action_value in STATE_CHANGING_ACTIONS and _explicit_other_project_request(user_text):
        return {
            "text": (
                "That request appears to change a project other than the one currently loaded. "
                "Open Saved Projects and load the project you want to change first. "
                "I can discuss another project from here when enough information is available, "
                "but I will not modify an unloaded project."
            ),
            "stage": stage_name,
            "source": "project_boundary",
        }

    target_step = ACTION_STEP.get(action_value)
    if target_step and step and target_step != step:
        target_name = STEP_NAMES[target_step]
        return {
            "text": (
                f"That change belongs in Step {target_step}: {target_name}. "
                f"You are currently in Step {step}: {stage_name}. "
                f"Open {target_name} from the WritersBlock workflow, then ask me again and "
                "I can help you make the change there. I have not altered the current project."
            ),
            "stage": stage_name,
            "source": "stage_boundary",
        }

    return None

def _clip(value: Any, limit: int) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return text[:head] + "\n...[middle omitted for context size]...\n" + text[-tail:]

def build_ai_prompt(state: Mapping[str, Any], user_text: str) -> str:
    ctx = build_context(state)
    ref = ctx["quill_project_reference"]
    manuscript_context = _clip(ctx.get("current_manuscript", ""), 50000)

    return f"""
You are Quill, the WritersBlock Studios writing partner.

CORE RULES:
- The writer may ask about ANY part of the CURRENT loaded WritersBlock project,
  regardless of the workflow screen currently open.
- The current screen tells you where the writer is working; it does not limit what you may discuss.
- Answer general writing, publishing, terminology, research, and outside-world questions normally.
- Do not claim you changed WritersBlock state, switched projects, navigated screens,
  rewrote text, or applied a workaround unless the application explicitly did so.
- State-changing cross-stage/project requests are handled separately by WritersBlock.
- Be concise and practical.

CURRENT PROJECT
Title: {ref.get("title") or "(untitled)"}
Current Step: {ref.get("step")} - {ref.get("stage")}
Writing Format: {ref.get("format_type")}
Selected Final Output Format: {ref.get("final_output_format")}
Dialogue Style: {ref.get("dialogue_style")}
Current Manuscript Word Count: {ref.get("manuscript_word_count")}

PROJECT DEVELOPMENT CONTEXT
Concept / Story Seed:
{_clip(ref.get("story_seed"), 7000)}

Chosen Story Path:
{_clip(ref.get("chosen_option_text") or ref.get("chosen_option"), 7000)}

Plot Outline:
{_clip(ref.get("plot_outline"), 12000)}

Rolling Lore / Continuity:
{_clip(ref.get("rolling_lore_book"), 12000)}

Revision Report:
{_clip(ref.get("revision_report"), 8000)}

CURRENT WORKING MANUSCRIPT CONTEXT:
{manuscript_context}

WRITER QUESTION:
{clean(user_text)}

Answer directly. If the supplied project material is insufficient, say what is missing rather than inventing project facts.
""".strip()

def contextual_ai_answer(state: Mapping[str, Any], user_text: str) -> Optional[str]:
    backend = get_value(state, "backend")
    client = getattr(backend, "client", None) if backend is not None else None
    model_name = clean(getattr(backend, "model_name", "")) if backend is not None else ""
    if client is None or not model_name:
        return None

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=build_ai_prompt(state, user_text),
        )
        text = clean(getattr(response, "text", ""))
        return text or None
    except Exception:
        return None
