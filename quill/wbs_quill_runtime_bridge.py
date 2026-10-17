"""
WritersBlock Studios
Quill Runtime Bridge
Version: 1.0

Connects Quill Studio Coach to the existing WritersBlock Studio Agent runtime
without modifying the frozen Universal Agent core.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Optional

QUILL_RUNTIME_BRIDGE_VERSION = "1.0"

QUILL_DIR = Path(__file__).resolve().parent
WBS_AGENT_DIR = QUILL_DIR.parent
if str(WBS_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(WBS_AGENT_DIR))

try:  # package import when used as quill.wbs_quill_runtime_bridge
    from .wbs_quill_studio_coach import (  # noqa: E402
        QuillCoachMessage,
        QuillDetailMode,
        QuillStudioCoach,
    )
except ImportError:  # direct-file test/import
    from wbs_quill_studio_coach import (  # noqa: E402
        QuillCoachMessage,
        QuillDetailMode,
        QuillStudioCoach,
    )

try:  # production import when this file is inside WritersBlock Studio Agent/quill/
    from wbs_decision_engine import WBSDecisionEngine, WBSProjectSnapshot  # type: ignore
except Exception:  # allows isolated tests before installation
    WBSDecisionEngine = None  # type: ignore
    WBSProjectSnapshot = None  # type: ignore


@dataclass(frozen=True)
class QuillRuntimeResult:
    coach: QuillCoachMessage
    decision: Any
    runtime_result: Any = None
    runtime_called: bool = False
    metadata: Optional[Dict[str, Any]] = None


def _mapping(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_context") and callable(value.to_context):
        return dict(value.to_context())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return dict(value.to_dict())
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _decision_mapping(decision: Any) -> Dict[str, Any]:
    if decision is None:
        return {}
    if hasattr(decision, "to_dict") and callable(decision.to_dict):
        return dict(decision.to_dict())
    return _mapping(decision)


class QuillRuntimeBridge:
    """Front-door adapter between project state, Quill, and the WBS runtime."""

    def __init__(
        self,
        agent: Any = None,
        *,
        display_name: str = "",
        decision_engine: Any = None,
    ) -> None:
        self.agent = agent
        self.coach = QuillStudioCoach(display_name=display_name)

        if decision_engine is not None:
            self.decision_engine = decision_engine
        else:
            if WBSDecisionEngine is None:
                raise RuntimeError(
                    "wbs_decision_engine.py was not found. Place this file in "
                    "WritersBlock Studio Agent/quill/."
                )
            self.decision_engine = WBSDecisionEngine()

    def prelude(self) -> str:
        return self.coach.prelude()

    def snapshot(self, project_state: Any) -> Any:
        if WBSProjectSnapshot is not None and isinstance(project_state, Mapping):
            return WBSProjectSnapshot.from_mapping(project_state)
        return project_state

    def analyze(self, request_text: str, project_state: Any) -> tuple[Any, Any]:
        snapshot = self.snapshot(project_state)
        decision = self.decision_engine.analyze(request_text, snapshot)
        return snapshot, decision

    def guidance(
        self,
        request_text: str,
        project_state: Any,
        *,
        detail_mode: Optional[QuillDetailMode | str] = None,
    ) -> QuillRuntimeResult:
        snapshot, decision = self.analyze(request_text, project_state)
        message = self.coach.coach(
            request_text,
            snapshot,
            decision=decision,
            detail_mode=detail_mode,
        )
        metadata = self.build_metadata(snapshot, decision, message)
        return QuillRuntimeResult(
            coach=message,
            decision=decision,
            runtime_called=False,
            metadata=metadata,
        )

    def ask(
        self,
        request_text: str,
        project_state: Any,
        *,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        approved: bool = False,
        detail_mode: Optional[QuillDetailMode | str] = None,
    ) -> QuillRuntimeResult:
        if self.agent is None:
            raise RuntimeError("QuillRuntimeBridge requires a WritersBlock agent for ask().")

        snapshot, decision = self.analyze(request_text, project_state)
        message = self.coach.coach(
            request_text,
            snapshot,
            decision=decision,
            detail_mode=detail_mode,
        )

        merged = dict(metadata or {})
        merged.update(self.build_metadata(snapshot, decision, message))

        runner = (
            self.agent.run_with_approval
            if approved
            else self.agent.run
        )
        runtime_result = runner(
            request_text,
            project_id=project_id,
            project_name=project_name,
            metadata=merged,
        )

        return QuillRuntimeResult(
            coach=message,
            decision=decision,
            runtime_result=runtime_result,
            runtime_called=True,
            metadata=merged,
        )

    def build_metadata(
        self,
        snapshot: Any,
        decision: Any,
        message: QuillCoachMessage,
    ) -> Dict[str, Any]:
        return {
            "quill_enabled": True,
            "quill_role": "studio_coach",
            "quill_response_style": "brief_first_detail_on_request",
            "quill_stage": message.stage,
            "quill_next_action": message.next_action,
            "quill_severity": message.severity.value,
            "wbs_project_snapshot": _mapping(snapshot),
            "wbs_decision": _decision_mapping(decision),
        }


__all__ = [
    "QUILL_RUNTIME_BRIDGE_VERSION",
    "QuillRuntimeBridge",
    "QuillRuntimeResult",
]
