"""
WritersBlock Studios
Quill Studio Coach
Version: 1.0

Purpose
-------
Quill is the visible creative partner/coordinator for WritersBlock Studios.
This layer converts project state + decision-engine output into brief, pointed,
stage-aware coaching.

Core rule: BRIEF FIRST. DETAIL ON REQUEST.

Quill does not replace the decision engine, backend, Streamlit navigation,
persistence, or specialist modules. It explains the next useful move in a
human, concise way and only expands when the user asks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Any, Dict, Mapping, Optional


QUILL_STUDIO_COACH_VERSION = "1.0"
DEFAULT_MAX_BRIEF_WORDS = 42


class QuillDetailMode(str, Enum):
    BRIEF = "brief"
    DETAIL = "detail"


class QuillSeverity(str, Enum):
    INFO = "info"
    CAUTION = "caution"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class QuillCoachMessage:
    text: str
    stage: str
    severity: QuillSeverity = QuillSeverity.INFO
    next_action: str = ""
    expandable: bool = True
    trigger: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        return payload


STAGE_COACHING: Dict[int, Dict[str, str]] = {
    1: {
        "name": "Concept Development",
        "focus": "Define the project, source material, tone, dialogue style, and scope.",
        "ready": "The project has enough direction to enter Scripting.",
    },
    2: {
        "name": "Scripting",
        "focus": "Compare the three story directions and choose the strongest path.",
        "ready": "One story direction is selected.",
    },
    3: {
        "name": "Plot Architecture",
        "focus": "Turn the chosen direction into the four-beat production structure.",
        "ready": "The four-beat plot is complete.",
    },
    4: {
        "name": "Creative Draft",
        "focus": "Draft the story one beat at a time while preserving continuity.",
        "ready": "All four beats are drafted.",
    },
    5: {
        "name": "Script Lock",
        "focus": "Review the completed draft before polishing or rewriting it.",
        "ready": "The draft is accepted as the working manuscript.",
    },
    6: {
        "name": "Script Polish",
        "focus": "Identify continuity, pacing, tone, character, and polish issues.",
        "ready": "The revision report is complete.",
    },
    7: {
        "name": "Script Rewrite",
        "focus": "Apply selected changes, or skip rewrite when the manuscript is ready.",
        "ready": "The working manuscript is accepted for final production.",
    },
    8: {
        "name": "Final Output",
        "focus": "Convert the accepted manuscript into its industry-ready output format.",
        "ready": "The final output is generated and ready to save/download.",
    },
}


DETAIL_REQUEST_PATTERNS = (
    r"\bwhy\b",
    r"\bexplain\b",
    r"\bmore detail\b",
    r"\bdetails\b",
    r"\bexpand\b",
    r"\btell me more\b",
    r"\bwalk me through\b",
)

NEXT_REQUEST_PATTERNS = (
    r"\bwhat next\b",
    r"\bnext step\b",
    r"\bwhat should i do\b",
    r"\bwhere do i go\b",
    r"\bcontinue\b",
)


QUILL_PRELUDE = (
    "I’m Quill, your WritersBlock Studio Coach. I keep guidance brief and pointed, "
    "tell you what matters now, and recommend the next move. If you want the reasoning "
    "or a deeper discussion, just ask me to explain."
)


def quill_prelude(display_name: str = "") -> str:
    name = str(display_name or "").strip()
    if not name:
        return QUILL_PRELUDE
    return (
        f"I’m Quill, your WritersBlock Studio Coach, {name}. I keep guidance brief and "
        "pointed, tell you what matters now, and recommend the next move. If you want "
        "the reasoning or a deeper discussion, just ask me to explain."
    )


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _word_limit(text: str, limit: int = DEFAULT_MAX_BRIEF_WORDS) -> str:
    words = _clean(text).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(" ,;:") + "…"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _bool(obj: Any, key: str) -> bool:
    return bool(_get(obj, key, False))


def _detail_requested(request_text: str) -> bool:
    text = _clean(request_text).lower()
    return any(re.search(pattern, text) for pattern in DETAIL_REQUEST_PATTERNS)


def _next_requested(request_text: str) -> bool:
    text = _clean(request_text).lower()
    return any(re.search(pattern, text) for pattern in NEXT_REQUEST_PATTERNS)


def _stage_number(snapshot: Any) -> int:
    step = _get(snapshot, "step")
    if step:
        try:
            return int(step)
        except (TypeError, ValueError):
            pass

    stage_name = _clean(_get(snapshot, "stage_name")).lower()
    for number, spec in STAGE_COACHING.items():
        if spec["name"].lower() == stage_name:
            return number

    internal = _clean(_get(snapshot, "project_stage", "Intake"))
    export_view = bool(_get(snapshot, "export_view", False))
    internal_map = {
        "Intake": 1,
        "Sandbox": 2,
        "Plot Architect": 3,
        "Drafting Engine": 4,
        "Revision Engine": 6,
        "Rewrite Engine": 7,
    }
    if internal == "Isolation Guardrail":
        return 8 if export_view else 5
    return internal_map.get(internal, 1)


def _stage_name(snapshot: Any) -> str:
    supplied = _clean(_get(snapshot, "stage_name"))
    if supplied:
        return supplied
    return STAGE_COACHING[_stage_number(snapshot)]["name"]


def _snapshot_has_story_source(snapshot: Any) -> bool:
    explicit = _get(snapshot, "has_story_source")
    if explicit is not None:
        return bool(explicit)

    mode = _clean(_get(snapshot, "starting_source_mode", "Story Idea"))
    if mode == "Existing Draft / Manuscript":
        return bool(
            _clean(_get(snapshot, "imported_source_name"))
            and int(_get(snapshot, "imported_source_word_count", 0) or 0) > 0
        )
    return bool(_clean(_get(snapshot, "story_seed")))


def _completed_beats(snapshot: Any) -> int:
    beats = _get(snapshot, "completed_beats", ()) or ()
    try:
        return len(set(int(x) for x in beats))
    except Exception:
        return 0


def _state_next_action(snapshot: Any) -> str:
    step = _stage_number(snapshot)

    if step == 1:
        if not _snapshot_has_story_source(snapshot):
            return "Give me the story idea, or import the existing DOCX/TXT manuscript."
        return "Your concept is ready. Move to Scripting and generate the three story paths."

    if step == 2:
        if not _bool(snapshot, "has_sandbox_slates"):
            return "Generate the three story paths."
        if not _bool(snapshot, "has_chosen_option"):
            return "Choose the strongest path: A, B, or C."
        return "Your direction is chosen. Move to Plot Architecture."

    if step == 3:
        if not _bool(snapshot, "has_plot_outline"):
            return "Generate the four-beat plot structure."
        return "The plot is built. Move to Creative Draft."

    if step == 4:
        count = _completed_beats(snapshot)
        if count < 4:
            return f"Draft Beat {count + 1}."
        return "All four beats are drafted. Move to Script Lock."

    if step == 5:
        if not _bool(snapshot, "has_current_draft"):
            return "A completed draft is required before Script Lock."
        return "Review the draft, lock it, then move to Script Polish."

    if step == 6:
        if not _bool(snapshot, "has_revision_report"):
            return "Run the polish/revision pass."
        return "Review the polish findings, then move to Script Rewrite."

    if step == 7:
        if _bool(snapshot, "has_rewritten_manuscript"):
            return "Accept the rewrite if it is better, then move to Final Output."
        return "Rewrite what needs fixing—or skip rewrite and proceed to Final Output."

    if step == 8:
        if not _bool(snapshot, "has_final_output"):
            return "Generate the final industry-formatted output."
        return "Final output is ready. Save or download the finished manuscript."

    return "Continue with the current WritersBlock stage."


def _decision_blocker(decision: Any) -> str:
    blockers = _get(decision, "blockers", ()) or ()
    if isinstance(blockers, str):
        blockers = (blockers,)
    for blocker in blockers:
        clean = _clean(blocker)
        if clean:
            return clean
    return ""


def _decision_next(decision: Any) -> str:
    return _clean(_get(decision, "next_best_action", ""))


def _decision_reason(decision: Any) -> str:
    return _clean(_get(decision, "reason", ""))


class QuillStudioCoach:
    """Concise human-facing coaching layer for WritersBlock Studios."""

    def __init__(self, *, display_name: str = "", max_brief_words: int = DEFAULT_MAX_BRIEF_WORDS):
        self.display_name = _clean(display_name)
        self.max_brief_words = max(20, int(max_brief_words))

    def prelude(self) -> str:
        return quill_prelude(self.display_name)

    def coach(
        self,
        request_text: str,
        snapshot: Any,
        *,
        decision: Optional[Any] = None,
        detail_mode: Optional[QuillDetailMode | str] = None,
    ) -> QuillCoachMessage:
        mode = (
            QuillDetailMode(detail_mode)
            if detail_mode is not None
            else (QuillDetailMode.DETAIL if _detail_requested(request_text) else QuillDetailMode.BRIEF)
        )

        stage = _stage_name(snapshot)
        blocker = _decision_blocker(decision) if decision is not None else ""
        next_action = _decision_next(decision) if decision is not None else ""
        if not next_action:
            next_action = _state_next_action(snapshot)

        if blocker:
            base = f"We can’t move forward yet: {blocker}"
            if next_action:
                base += f" Next: {next_action}"
            return QuillCoachMessage(
                text=self._render(base, snapshot, decision, mode),
                stage=stage,
                severity=QuillSeverity.BLOCKED,
                next_action=next_action,
                trigger="blocker",
            )

        if _next_requested(request_text) or not _clean(request_text):
            return QuillCoachMessage(
                text=self._render(next_action, snapshot, decision, mode),
                stage=stage,
                severity=QuillSeverity.INFO,
                next_action=next_action,
                trigger="next_action",
            )

        if mode == QuillDetailMode.DETAIL:
            # Internal decision reasons are routing diagnostics, not customer prose.
            spec = STAGE_COACHING[_stage_number(snapshot)]
            parts = [spec["focus"]]
            parts.append(f"Next: {next_action}")
            text = " ".join(part for part in parts if part)
            return QuillCoachMessage(
                text=text,
                stage=stage,
                severity=QuillSeverity.INFO,
                next_action=next_action,
                trigger="detail_requested",
            )

        # Normal conversational request: answer with the most relevant current guidance,
        # not a generic chatbot monologue.
        return QuillCoachMessage(
            text=self._render(next_action, snapshot, decision, mode),
            stage=stage,
            severity=QuillSeverity.INFO,
            next_action=next_action,
            trigger="stage_guidance",
        )

    def stage_status(self, snapshot: Any) -> QuillCoachMessage:
        stage = _stage_name(snapshot)
        action = _state_next_action(snapshot)
        text = f"You’re in {stage}. {action}"
        return QuillCoachMessage(
            text=_word_limit(text, self.max_brief_words),
            stage=stage,
            next_action=action,
            trigger="status",
        )

    def _render(
        self,
        base: str,
        snapshot: Any,
        decision: Optional[Any],
        mode: QuillDetailMode,
    ) -> str:
        if mode == QuillDetailMode.BRIEF:
            return _word_limit(base, self.max_brief_words)

        # Never append private routing explanations to customer-facing responses.
        return base


__all__ = [
    "DEFAULT_MAX_BRIEF_WORDS",
    "QUILL_PRELUDE",
    "QUILL_STUDIO_COACH_VERSION",
    "QuillCoachMessage",
    "QuillDetailMode",
    "QuillSeverity",
    "QuillStudioCoach",
    "STAGE_COACHING",
    "quill_prelude",
]
