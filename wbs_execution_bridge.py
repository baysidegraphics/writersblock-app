"""
WritersBlock Studios Agent
Execution Bridge
Version: 1.1
Aligned to current app.py + gemini_backend.py snapshot: 2026-09-12.

Purpose
-------
Execute an approved WritersBlock decision against the CURRENT
GeminiWriterBackend method surface without importing Streamlit or Supabase.

The bridge:
- accepts a WBSDecision plus the current app/project state,
- calls only the backend operation selected by the decision engine,
- translates the live app state into the exact GeminiWriterBackend signatures,
- keeps application/database actions separate from AI generation actions,
- never executes a blocked decision,
- never silently substitutes a saved manuscript for the current live manuscript,
- preserves Step 8 final-output source separation.

This module is intentionally provider/backend-facing. Persistence, Streamlit
session-state mutation, Supabase writes, navigation and download widgets remain
owned by app.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional
import re

from wbs_decision_engine import (
    ACTION_BACKEND_OPERATIONS,
    DecisionAction,
    WBSDecision,
    WBSDecisionEngine,
    WBSProjectSnapshot,
)
from wbs_program_intelligence import (
    DEFAULT_AUDIOBOOK_CUE_LEVEL,
    PICTURE_BOOK_PROJECT_TYPE,
    normalize_project_type,
)


WBS_EXECUTION_BRIDGE_VERSION = "1.1"

SAME_FORMAT_PROSE_OUTPUTS = {
    "Novel / Prose",
    "Short Story",
    "Novella",
}


@dataclass(frozen=True)
class WBSExecutionResult:
    decision: WBSDecision
    executed: bool
    success: bool
    execution_target: str
    backend_operation: Optional[str] = None
    output: Any = None
    app_action: Optional[str] = None
    error: str = ""
    used_arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.to_dict()
        return payload


APP_OWNED_ACTIONS = {
    DecisionAction.SELECT_SANDBOX_PATH: "select_sandbox_path",
    DecisionAction.REVIEW_SCRIPT_LOCK: "review_script_lock",
    DecisionAction.SAVE_DRAFT: "save_manuscript_checkpoint",
    DecisionAction.SKIP_REWRITE: "navigate_to_final_output",
    DecisionAction.SAVE_FINAL: "save_manuscript_checkpoint",
    DecisionAction.SAVE_PROJECT: "save_current_project_session_to_supabase",
    DecisionAction.MANAGE_VERSION: "saved_version_manager",
    DecisionAction.RENAME_PROJECT: "rename_current_project_everywhere",
    DecisionAction.STATUS: "display_project_status",
}

NON_BACKEND_SPECIALIST_ACTIONS = {
    DecisionAction.MARKETING,
    DecisionAction.SALES,
    DecisionAction.RESEARCH,
    DecisionAction.BUSINESS,
    DecisionAction.TECHNICAL,
    DecisionAction.GENERAL,
}


def _get(mapping: Mapping[str, Any], key: str, default: Any = "") -> Any:
    value = mapping.get(key, default)
    return default if value is None else value


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _extract_beat_text(plot_outline: str, beat_number: int) -> str:
    """Extract one [BEAT N] block from the current Plot Architecture text."""
    text = str(plot_outline or "")
    pattern = re.compile(
        rf"(\[BEAT\s+{int(beat_number)}\].*?)(?=\n\s*\[BEAT\s+\d+\]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _source_story_text(state: Mapping[str, Any]) -> str:
    """Use current Concept source, preferring the imported locked source when active."""
    source_mode = _clean(_get(state, "starting_source_mode", "Story Idea"))
    if source_mode == "Existing Draft / Manuscript":
        imported = _clean(_get(state, "imported_source_text", ""))
        if imported:
            return imported
    return _clean(_get(state, "story_seed", ""))


def _series_aware_source(state: Mapping[str, Any]) -> str:
    """Prefer app-prepared series-aware source if the caller supplies it.

    app.py already owns the detailed series-context assembly. Reusing its prepared
    value avoids maintaining a second canon-compression implementation here.
    """
    prepared = _clean(_get(state, "series_aware_story_seed", ""))
    return prepared or _source_story_text(state)


def _development_format_context(state: Mapping[str, Any]) -> str:
    """Prefer app-prepared scripting/effective format context when available."""
    prepared = _clean(_get(state, "scripting_format_context", ""))
    if prepared:
        return prepared
    effective = _clean(_get(state, "effective_format_type", ""))
    if effective:
        return effective
    return _clean(_get(state, "format_type", "Novel / Prose"))


def _dialogue_packet(state: Mapping[str, Any]) -> str:
    prepared = _clean(_get(state, "dialogue_development_packet", ""))
    return prepared


def _append_packet(base: str, packet: str) -> str:
    if not packet:
        return base
    return f"{base}\n\n{packet}".strip()


def _safe_argument_summary(kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    """Return useful execution diagnostics without duplicating full manuscripts."""
    summary: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            summary[key] = {
                "type": "text",
                "characters": len(value),
                "words": len(re.findall(r"\b\w+\b", value)),
            }
        else:
            summary[key] = value
    return summary


def _backend_failure_reason(output: Any) -> str:
    """Recognize GeminiWriterBackend fallback strings as execution failures."""
    if output is None:
        return "Backend returned no output."

    text = str(output).strip()
    if not text:
        return "Backend returned empty output."

    lowered = text.lower()
    failure_markers = (
        "fallback output",
        "backend error:",
        "backend issue:",
        "did not return usable text",
        "gemini returned an empty",
        "permission_denied",
        "403 permission",
        "project has been denied access",
    )
    if not any(marker in lowered for marker in failure_markers):
        return ""

    match = re.search(r"Backend error:\s*(.+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return text[:500]


class WBSExecutionBridge:
    """Translate WBS decisions into current GeminiWriterBackend calls."""

    def __init__(
        self,
        backend: Any,
        *,
        decision_engine: Optional[WBSDecisionEngine] = None,
    ) -> None:
        self.backend = backend
        self.decision_engine = decision_engine or WBSDecisionEngine()

    def decide(
        self,
        request_text: str,
        project_state: WBSProjectSnapshot | Mapping[str, Any],
    ) -> WBSDecision:
        return self.decision_engine.analyze(request_text, project_state)

    def execute_request(
        self,
        request_text: str,
        project_state: WBSProjectSnapshot | Mapping[str, Any],
        *,
        action_payload: Optional[Mapping[str, Any]] = None,
    ) -> WBSExecutionResult:
        raw_state = (
            dict(project_state.to_context())
            if isinstance(project_state, WBSProjectSnapshot)
            else dict(project_state or {})
        )
        decision = self.decide(request_text, project_state)
        return self.execute_decision(
            decision,
            raw_state,
            action_payload=action_payload,
        )

    def execute_decision(
        self,
        decision: WBSDecision,
        project_state: Mapping[str, Any],
        *,
        action_payload: Optional[Mapping[str, Any]] = None,
    ) -> WBSExecutionResult:
        state = dict(project_state or {})
        payload = dict(action_payload or {})

        if not decision.executable:
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="blocked",
                backend_operation=decision.backend_operation,
                error="; ".join(decision.blockers),
            )

        if decision.action in APP_OWNED_ACTIONS:
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=True,
                execution_target="application",
                app_action=APP_OWNED_ACTIONS[decision.action],
            )

        if decision.action in NON_BACKEND_SPECIALIST_ACTIONS:
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=True,
                execution_target="universal_specialist",
                error=(
                    "This request belongs to a WritersBlock specialist rather than "
                    "GeminiWriterBackend direct execution."
                ),
            )

        operation = decision.backend_operation
        if not operation:
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="bridge",
                error="Decision has no executable GeminiWriterBackend operation.",
            )

        method = getattr(self.backend, operation, None)
        if not callable(method):
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="backend",
                backend_operation=operation,
                error=f"Backend does not provide required operation: {operation}",
            )

        try:
            kwargs = self._build_backend_arguments(
                decision,
                state,
                payload,
            )
        except Exception as exc:
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="backend",
                backend_operation=operation,
                error=str(exc),
            )

        try:
            output = method(**kwargs)
        except Exception as exc:
            return WBSExecutionResult(
                decision=decision,
                executed=True,
                success=False,
                execution_target="backend",
                backend_operation=operation,
                error=str(exc),
                used_arguments=_safe_argument_summary(kwargs),
            )

        backend_failure = _backend_failure_reason(output)
        if backend_failure:
            return WBSExecutionResult(
                decision=decision,
                executed=True,
                success=False,
                execution_target="backend",
                backend_operation=operation,
                output=output,
                error=backend_failure,
                used_arguments=_safe_argument_summary(kwargs),
            )

        return WBSExecutionResult(
            decision=decision,
            executed=True,
            success=True,
            execution_target="backend",
            backend_operation=operation,
            output=output,
            used_arguments=_safe_argument_summary(kwargs),
        )

    def _build_backend_arguments(
        self,
        decision: WBSDecision,
        state: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        action = decision.action

        if action == DecisionAction.GENERATE_SANDBOX:
            story_seed = _clean(
                payload.get("story_seed")
                or state.get("series_aware_story_seed")
                or _series_aware_source(state)
            )
            if not story_seed:
                raise ValueError("No current story source is available for Scripting.")

            format_context = _clean(
                payload.get("format_type")
                or state.get("scripting_format_context")
                or _development_format_context(state)
            )
            dialogue_packet = _clean(
                payload.get("dialogue_development_packet")
                or _dialogue_packet(state)
            )

            return {
                "story_seed": story_seed,
                "format_type": _append_packet(format_context, dialogue_packet),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.GENERATE_PLOT:
            chosen_option = _clean(
                payload.get("chosen_option")
                or state.get("chosen_option")
            )
            option_text = _clean(
                payload.get("option_text")
                or payload.get("chosen_option_text")
                or state.get("chosen_option_text")
            )
            if not chosen_option or not option_text:
                raise ValueError(
                    "Current selected Scripting option and option text are required."
                )

            story_seed = _clean(
                payload.get("story_seed")
                or state.get("series_aware_story_seed")
                or _series_aware_source(state)
            )
            plot_dialogue_context = _clean(
                payload.get("plot_dialogue_context")
                or state.get("plot_dialogue_context")
                or ""
            )
            if plot_dialogue_context:
                option_text = _append_packet(option_text, plot_dialogue_context)

            return {
                "chosen_option": chosen_option,
                "option_text": option_text,
                "story_seed": story_seed,
                "format_type": _clean(
                    payload.get("format_type")
                    or state.get("effective_format_type")
                    or _development_format_context(state)
                ),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.DRAFT_NEXT_BEAT:
            beat_number = int(
                payload.get("beat_number")
                or decision.backend_arguments_hint.get("beat_number")
                or state.get("current_processing_beat")
                or 1
            )
            beat_text = _clean(
                payload.get("current_beat_text")
                or payload.get("beat_text")
            )
            if not beat_text:
                beat_text = _extract_beat_text(
                    _clean(state.get("plot_outline")),
                    beat_number,
                )
            if not beat_text:
                raise ValueError(
                    f"Could not resolve Plot Architecture text for Beat {beat_number}."
                )

            dialogue_packet = _clean(
                payload.get("dialogue_development_packet")
                or _dialogue_packet(state)
            )
            beat_text = _append_packet(beat_text, dialogue_packet)

            return {
                "current_beat_text": beat_text,
                "rolling_lore": _clean(
                    payload.get("rolling_lore")
                    or state.get("rolling_lore_book")
                    or ""
                ),
                "format_type": _clean(
                    payload.get("format_type")
                    or state.get("effective_format_type")
                    or _development_format_context(state)
                ),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.RUN_POLISH:
            source = _clean(
                payload.get("manuscript_text")
                or state.get("current_draft_output")
            )
            if not source:
                raise ValueError("Current live manuscript is required for Script Polish.")

            return {
                "manuscript_text": source,
                "revision_mode": _clean(
                    payload.get("revision_mode")
                    or "Final Polish Pass"
                ),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.RUN_REWRITE:
            source = _clean(
                payload.get("source_text")
                or state.get("current_draft_output")
            )
            if not source:
                raise ValueError("Current live manuscript is required for Script Rewrite.")

            hint = dict(decision.backend_arguments_hint)
            custom_instruction = _clean(
                payload.get("custom_instruction")
                or payload.get("rewrite_instruction")
                or ""
            )

            return {
                "source_text": source,
                "rewrite_mode": _clean(
                    payload.get("backend_rewrite_mode")
                    or hint.get("backend_rewrite_mode")
                    or "Creative Script Rewrite / Improve Scene"
                ),
                "scene_choice": _clean(
                    payload.get("scene_choice")
                    or "Full Manuscript"
                ),
                "custom_instruction": custom_instruction,
                "target_length": _clean(
                    payload.get("target_length")
                    or hint.get("target_length")
                    or "Keep Current Length"
                ),
                "custom_target_word_count": (
                    payload.get("custom_target_word_count")
                    if payload.get("custom_target_word_count") is not None
                    else hint.get("custom_target_word_count")
                ),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.GENERATE_FINAL_OUTPUT:
            source = _clean(
                payload.get("source_text")
                or state.get("current_draft_output")
            )
            if not source:
                raise ValueError("Current live manuscript is required for Final Output.")

            final_format = _clean(
                payload.get("final_output_format")
                or state.get("final_output_format")
                or state.get("format_type")
            )
            final_format = normalize_project_type(final_format)

            conversion_instruction = _clean(
                payload.get("final_output_instruction")
                or state.get("final_output_instruction")
            )
            if not conversion_instruction:
                raise ValueError(
                    "Final Output requires the current app.py conversion instruction. "
                    "Pass get_final_output_conversion_instruction(selected_format) as "
                    "'final_output_instruction' so the bridge uses the application's "
                    "authoritative conversion rules."
                )

            hint = dict(decision.backend_arguments_hint)
            target_length = _clean(
                payload.get("target_length")
                or hint.get("target_length")
                or "Keep Current Length"
            )
            custom_target = (
                payload.get("custom_target_word_count")
                if payload.get("custom_target_word_count") is not None
                else hint.get("custom_target_word_count")
            )

            # Current app behavior: picture-book adaptation is generated before
            # the separate 16-spread layout operation.
            if final_format == PICTURE_BOOK_PROJECT_TYPE and custom_target is None:
                target_length = "Custom Word Count"
                custom_target = 700

            development_format = _clean(state.get("format_type"))
            try:
                development_format = normalize_project_type(development_format)
            except ValueError:
                pass

            explicit_mode = _clean(payload.get("backend_rewrite_mode"))
            if explicit_mode:
                backend_mode = explicit_mode
            elif (
                final_format == development_format
                and final_format in SAME_FORMAT_PROSE_OUTPUTS
            ):
                # Same-format prose conversion is normalization, not a story change.
                # Polish mode permits Gemini to return text unchanged when it is
                # already correctly formatted, avoiding the backend's intentional
                # "unchanged text" rejection used for creative/direct rewrites.
                backend_mode = "Polish Only / Do Not Change Story"
            else:
                backend_mode = _clean(
                    hint.get("backend_rewrite_mode")
                    or "Direct Story Change / Obey My Instructions Exactly"
                )

            return {
                "source_text": source,
                "rewrite_mode": backend_mode,
                "scene_choice": "Full Manuscript",
                "custom_instruction": conversion_instruction,
                "target_length": target_length,
                "custom_target_word_count": custom_target,
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or "Gritty Noir Mystery"
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        if action == DecisionAction.BUILD_PICTURE_BOOK_LAYOUT:
            source = _clean(
                payload.get("manuscript_text")
                or state.get("final_output_text")
            )
            if not source:
                raise ValueError(
                    "Current adapted Children's Picture Book Final Output is required."
                )

            return {
                "manuscript_text": source,
                "project_title": _clean(
                    payload.get("project_title")
                    or state.get("project_title")
                    or "Untitled Children's Picture Book"
                ),
                "tone_style": _clean(
                    payload.get("tone_style")
                    or state.get("tone_style")
                    or ""
                ),
                "author_style": _clean(
                    payload.get("author_style")
                    or state.get("author_style")
                    or ""
                ),
            }

        raise ValueError(
            f"Action '{action.value}' is not a direct GeminiWriterBackend operation."
        )


__all__ = [
    "APP_OWNED_ACTIONS",
    "NON_BACKEND_SPECIALIST_ACTIONS",
    "WBS_EXECUTION_BRIDGE_VERSION",
    "WBSExecutionBridge",
    "WBSExecutionResult",
]
