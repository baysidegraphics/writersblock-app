"""
WritersBlock Studios Agent
Safe Streamlit Integration Adapter
Version: 1.0
Aligned to app.py + gemini_backend.py snapshot: 2026-09-11.

DESIGN RULE
-----------
This adapter is NON-DESTRUCTIVE by default.

It reads the current Streamlit session-state mapping, builds a WritersBlock
project snapshot, and runs the purpose-specific decision layer in SHADOW mode.
It does not import Streamlit, mutate existing WritersBlock project keys, call
Supabase, navigate the application, or replace the current Gemini backend calls.

BRIDGE mode exists for controlled later integration. Even in BRIDGE mode this
adapter returns execution results to app.py; it does not write generated output
back into existing WritersBlock session-state fields automatically.

Reserved adapter state uses only the prefix:
    _wbs_agent_

This keeps the existing working application authoritative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Mapping, MutableMapping, Optional
import time

from wbs_decision_engine import (
    WBSDecision,
    WBSDecisionEngine,
    WBSProjectSnapshot,
)
from wbs_execution_bridge import (
    WBSExecutionBridge,
    WBSExecutionResult,
)


WBS_STREAMLIT_ADAPTER_VERSION = "1.0"
RESERVED_PREFIX = "_wbs_agent_"


class IntegrationMode(str, Enum):
    SHADOW = "shadow"
    BRIDGE = "bridge"


# Current app.py fields required by the WritersBlock decision/execution layers.
# Unknown/additional session keys are deliberately ignored.
PROJECT_STATE_KEYS = (
    "project_title",
    "project_stage",
    "export_view",
    "format_type",
    "dialogue_style",
    "project_scope",
    "series_name",
    "series_book_number",
    "series_continuity_mode",
    "story_seed",
    "starting_source_mode",
    "imported_source_text",
    "imported_source_name",
    "imported_source_word_count",
    "sandbox_slates",
    "chosen_option",
    "chosen_option_text",
    "plot_outline",
    "current_draft_output",
    "rolling_lore_book",
    "completed_beats",
    "scene_blocks",
    "current_processing_beat",
    "revision_report",
    "rewritten_manuscript",
    "final_output_format",
    "final_output_text",
    "picture_book_layout_spreads",
    "picture_book_page_size",
    "tone_style",
    "author_style",
    "licensed_mode",
    "demo_mode",
    "current_project_id",
    "manuscript_version",
    "current_manuscript_save_status",
    "current_manuscript_save_stage",
    "audiobook_production_cue_level",
)

# These values are prepared by current app.py helper functions and may be supplied
# by the live hook when a backend operation needs them. Keeping them explicit
# avoids duplicating app.py's series/dialogue/final-output rule builders.
PREPARED_CONTEXT_KEYS = (
    "series_aware_story_seed",
    "scripting_format_context",
    "plot_dialogue_context",
    "dialogue_development_packet",
    "effective_format_type",
    "final_output_instruction",
)


REQUIRED_BACKEND_METHODS = (
    "generate_sandbox_slates",
    "generate_plot_outline",
    "execute_recursive_draft_chunk",
    "run_revision_pass",
    "run_rewrite_engine",
    "generate_picture_book_layout",
)


@dataclass(frozen=True)
class AdapterHealth:
    ok: bool
    mode: str
    decision_engine_ready: bool
    backend_bound: bool
    backend_methods_available: tuple[str, ...]
    backend_methods_missing: tuple[str, ...]
    destructive_writes_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _mapping_get(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return mapping.get(key, default)
    except AttributeError:
        try:
            return mapping[key]
        except Exception:
            return default


def capture_project_state(
    session_state: Mapping[str, Any],
    *,
    prepared_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Copy only known current WritersBlock state fields.

    The returned dict is detached from Streamlit session state. Mutating it cannot
    mutate the live application.
    """
    captured: Dict[str, Any] = {}
    for key in PROJECT_STATE_KEYS:
        captured[key] = _mapping_get(session_state, key)

    for key in PREPARED_CONTEXT_KEYS:
        if prepared_context and key in prepared_context:
            captured[key] = prepared_context[key]

    return captured


def build_project_snapshot(
    session_state: Mapping[str, Any],
    *,
    prepared_context: Optional[Mapping[str, Any]] = None,
) -> WBSProjectSnapshot:
    return WBSProjectSnapshot.from_mapping(
        capture_project_state(
            session_state,
            prepared_context=prepared_context,
        )
    )


def _decision_summary(decision: WBSDecision) -> Dict[str, Any]:
    return {
        "action": decision.action.value,
        "step": decision.step,
        "stage_name": decision.stage_name,
        "specialist": decision.specialist,
        "backend_operation": decision.backend_operation,
        "executable": decision.executable,
        "blockers": list(decision.blockers),
        "next_best_action": decision.next_best_action,
        "reason": decision.reason,
    }


def _execution_summary(result: WBSExecutionResult) -> Dict[str, Any]:
    # Deliberately do not copy generated manuscript/output text into adapter
    # session metadata. app.py remains the owner of generated content.
    return {
        "executed": result.executed,
        "success": result.success,
        "execution_target": result.execution_target,
        "backend_operation": result.backend_operation,
        "app_action": result.app_action,
        "error": result.error,
        "used_arguments": dict(result.used_arguments),
    }


class WBSStreamlitAdapter:
    """Safe integration surface for the current WritersBlock Streamlit app."""

    def __init__(
        self,
        *,
        mode: IntegrationMode | str = IntegrationMode.SHADOW,
        backend: Any = None,
        decision_engine: Optional[WBSDecisionEngine] = None,
    ) -> None:
        self.mode = IntegrationMode(mode)
        self.backend = backend
        self.decision_engine = decision_engine or WBSDecisionEngine()
        self.execution_bridge = (
            WBSExecutionBridge(
                backend,
                decision_engine=self.decision_engine,
            )
            if backend is not None
            else None
        )

    def health(self) -> AdapterHealth:
        available = []
        missing = []

        if self.backend is not None:
            for name in REQUIRED_BACKEND_METHODS:
                if callable(getattr(self.backend, name, None)):
                    available.append(name)
                else:
                    missing.append(name)

        ok = (
            self.decision_engine is not None
            and (
                self.mode == IntegrationMode.SHADOW
                or (
                    self.backend is not None
                    and not missing
                )
            )
        )

        return AdapterHealth(
            ok=ok,
            mode=self.mode.value,
            decision_engine_ready=self.decision_engine is not None,
            backend_bound=self.backend is not None,
            backend_methods_available=tuple(available),
            backend_methods_missing=tuple(missing),
            destructive_writes_enabled=False,
        )

    def analyze(
        self,
        request_text: str,
        session_state: Mapping[str, Any],
        *,
        prepared_context: Optional[Mapping[str, Any]] = None,
    ) -> WBSDecision:
        state = capture_project_state(
            session_state,
            prepared_context=prepared_context,
        )
        return self.decision_engine.analyze(request_text, state)

    def shadow(
        self,
        request_text: str,
        session_state: MutableMapping[str, Any],
        *,
        prepared_context: Optional[Mapping[str, Any]] = None,
    ) -> WBSDecision:
        """Analyze and record adapter-only metadata; never call backend."""
        decision = self.analyze(
            request_text,
            session_state,
            prepared_context=prepared_context,
        )
        self._record_decision(session_state, decision)
        session_state[f"{RESERVED_PREFIX}mode"] = IntegrationMode.SHADOW.value
        return decision

    def execute(
        self,
        request_text: str,
        session_state: MutableMapping[str, Any],
        *,
        prepared_context: Optional[Mapping[str, Any]] = None,
        action_payload: Optional[Mapping[str, Any]] = None,
    ) -> WBSExecutionResult:
        """Controlled direct execution.

        SHADOW mode refuses backend execution. BRIDGE mode may call the current
        GeminiWriterBackend through WBSExecutionBridge.

        This method never applies returned creative output to existing app.py
        session keys. app.py must explicitly accept/apply the result.
        """
        if self.mode != IntegrationMode.BRIDGE:
            decision = self.shadow(
                request_text,
                session_state,
                prepared_context=prepared_context,
            )
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="shadow",
                backend_operation=decision.backend_operation,
                error="Adapter is in SHADOW mode; backend execution is disabled.",
            )

        if self.execution_bridge is None:
            decision = self.analyze(
                request_text,
                session_state,
                prepared_context=prepared_context,
            )
            self._record_decision(session_state, decision)
            return WBSExecutionResult(
                decision=decision,
                executed=False,
                success=False,
                execution_target="bridge",
                backend_operation=decision.backend_operation,
                error="No GeminiWriterBackend instance is bound to the adapter.",
            )

        state = capture_project_state(
            session_state,
            prepared_context=prepared_context,
        )
        result = self.execution_bridge.execute_request(
            request_text,
            state,
            action_payload=action_payload,
        )

        self._record_decision(session_state, result.decision)
        session_state[f"{RESERVED_PREFIX}mode"] = IntegrationMode.BRIDGE.value
        session_state[f"{RESERVED_PREFIX}last_execution"] = _execution_summary(result)
        session_state[f"{RESERVED_PREFIX}last_execution_at"] = time.time()

        return result

    def next_best_action(
        self,
        session_state: Mapping[str, Any],
        *,
        prepared_context: Optional[Mapping[str, Any]] = None,
    ) -> str:
        snapshot = build_project_snapshot(
            session_state,
            prepared_context=prepared_context,
        )
        return self.decision_engine.next_best_action(snapshot)

    def clear_adapter_metadata(
        self,
        session_state: MutableMapping[str, Any],
    ) -> None:
        """Remove only adapter-owned metadata. Never touch WritersBlock state."""
        keys = [
            key
            for key in list(session_state.keys())
            if str(key).startswith(RESERVED_PREFIX)
        ]
        for key in keys:
            try:
                del session_state[key]
            except Exception:
                pass

    def _record_decision(
        self,
        session_state: MutableMapping[str, Any],
        decision: WBSDecision,
    ) -> None:
        session_state[f"{RESERVED_PREFIX}last_decision"] = _decision_summary(decision)
        session_state[f"{RESERVED_PREFIX}next_best_action"] = decision.next_best_action
        session_state[f"{RESERVED_PREFIX}last_decision_at"] = time.time()


def create_shadow_adapter(*, backend: Any = None) -> WBSStreamlitAdapter:
    """Recommended first live integration mode."""
    return WBSStreamlitAdapter(
        mode=IntegrationMode.SHADOW,
        backend=backend,
    )


def create_bridge_adapter(*, backend: Any) -> WBSStreamlitAdapter:
    """Controlled execution mode for later activation after shadow validation."""
    return WBSStreamlitAdapter(
        mode=IntegrationMode.BRIDGE,
        backend=backend,
    )


__all__ = [
    "AdapterHealth",
    "IntegrationMode",
    "PREPARED_CONTEXT_KEYS",
    "PROJECT_STATE_KEYS",
    "REQUIRED_BACKEND_METHODS",
    "RESERVED_PREFIX",
    "WBS_STREAMLIT_ADAPTER_VERSION",
    "WBSStreamlitAdapter",
    "build_project_snapshot",
    "capture_project_state",
    "create_bridge_adapter",
    "create_shadow_adapter",
]
