"""
WritersBlock Studios Agent
Project Decision / Intelligence Layer
Version: 1.0
Aligned to app.py + gemini_backend.py snapshot: 2026-09-11.

Purpose
-------
Deterministically understand the current WritersBlock project state before the
shared model is asked to do creative work.

The decision layer:
- identifies the active WritersBlock step from app.py state,
- recognizes the user's requested WritersBlock action,
- checks stage prerequisites,
- selects the appropriate WritersBlock specialist,
- identifies the matching current backend operation,
- supplies routing hints to the frozen Universal Agent,
- preserves project type, Dialogue Style, series continuity and working source,
- returns one next-best action when the request is simply "what next?".

It does not import Streamlit, Supabase or Gemini and does not modify app.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from wbs_program_intelligence import (
    BACKEND_OPERATIONS,
    DEFAULT_AUDIOBOOK_CUE_LEVEL,
    DIALOGUE_STYLES,
    FINAL_OUTPUT_FORMATS,
    PICTURE_BOOK_PROJECT_TYPE,
    PROJECT_TYPES,
    SERIES_CONTINUITY_MODE,
    normalize_dialogue_style,
    normalize_project_type,
    resolve_step,
)


WBS_DECISION_ENGINE_VERSION = "1.1-FREE-CHAT"


class DecisionAction(str, Enum):
    STATUS = "status"
    GENERATE_SANDBOX = "generate_sandbox"
    SELECT_SANDBOX_PATH = "select_sandbox_path"
    GENERATE_PLOT = "generate_plot"
    DRAFT_NEXT_BEAT = "draft_next_beat"
    REVIEW_SCRIPT_LOCK = "review_script_lock"
    SAVE_DRAFT = "save_draft"
    RUN_POLISH = "run_polish"
    RUN_REWRITE = "run_rewrite"
    SKIP_REWRITE = "skip_rewrite"
    GENERATE_FINAL_OUTPUT = "generate_final_output"
    BUILD_PICTURE_BOOK_LAYOUT = "build_picture_book_layout"
    SAVE_FINAL = "save_final"
    SAVE_PROJECT = "save_project"
    MANAGE_VERSION = "manage_version"
    RENAME_PROJECT = "rename_project"
    MARKETING = "marketing"
    SALES = "sales"
    RESEARCH = "research"
    BUSINESS = "business"
    TECHNICAL = "technical"
    GENERAL = "general"


@dataclass(frozen=True)
class WBSProjectSnapshot:
    project_title: str = ""
    project_stage: str = "Intake"
    export_view: bool = False
    format_type: str = "Novel / Prose"
    dialogue_style: str = "Story-Driven / Automatic"
    project_scope: str = "Standalone Book"
    series_name: str = ""
    series_book_number: int = 1
    series_continuity_mode: str = SERIES_CONTINUITY_MODE
    story_seed: str = ""
    starting_source_mode: str = "Story Idea"
    imported_source_name: str = ""
    imported_source_word_count: int = 0
    has_sandbox_slates: bool = False
    has_chosen_option: bool = False
    has_plot_outline: bool = False
    has_current_draft: bool = False
    completed_beats: Tuple[int, ...] = ()
    current_processing_beat: int = 1
    has_revision_report: bool = False
    has_rewritten_manuscript: bool = False
    final_output_format: str = ""
    has_final_output: bool = False
    has_picture_book_layout: bool = False
    picture_book_page_size: str = "8.5 x 8.5 Square"
    licensed_mode: bool = False
    demo_mode: bool = False
    current_project_id: Optional[str] = None
    manuscript_version: int = 0
    current_manuscript_save_status: str = ""
    current_manuscript_save_stage: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WBSProjectSnapshot":
        raw = dict(data or {})

        format_type = normalize_project_type(
            str(raw.get("format_type") or "Novel / Prose")
        )
        dialogue_style = normalize_dialogue_style(
            str(raw.get("dialogue_style") or "Story-Driven / Automatic")
        )

        completed_raw = raw.get("completed_beats") or ()
        completed: list[int] = []
        if isinstance(completed_raw, (str, bytes)):
            completed_raw = [completed_raw]
        try:
            for value in completed_raw:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    match = re.search(r"\d+", str(value))
                    if not match:
                        continue
                    number = int(match.group())
                if number not in completed:
                    completed.append(number)
        except TypeError:
            pass

        # Current app.py can have a written scene block visible before
        # completed_beats is fully synchronized. Infer completed beats from
        # non-empty scene_blocks so the Agent's "Next" instruction reflects
        # what the user actually sees in Creative Draft.
        if not completed:
            scene_blocks = raw.get("scene_blocks") or {}
            if isinstance(scene_blocks, Mapping):
                for key, value in scene_blocks.items():
                    if not str(value or "").strip():
                        continue
                    match = re.search(r"\d+", str(key))
                    if not match:
                        continue
                    number = int(match.group())
                    if number not in completed:
                        completed.append(number)

        def present(key: str, fallback_key: Optional[str] = None) -> bool:
            value = raw.get(key)
            if value is None and fallback_key:
                value = raw.get(fallback_key)
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, Mapping):
                return bool(value)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return bool(value)
            return bool(value)

        return cls(
            project_title=str(raw.get("project_title") or "").strip(),
            project_stage=str(raw.get("project_stage") or "Intake").strip(),
            export_view=bool(raw.get("export_view", False)),
            format_type=format_type,
            dialogue_style=dialogue_style,
            project_scope=str(raw.get("project_scope") or "Standalone Book").strip(),
            series_name=str(raw.get("series_name") or "").strip(),
            series_book_number=max(1, int(raw.get("series_book_number") or 1)),
            series_continuity_mode=str(
                raw.get("series_continuity_mode") or SERIES_CONTINUITY_MODE
            ).strip(),
            story_seed=str(raw.get("story_seed") or "").strip(),
            starting_source_mode=str(
                raw.get("starting_source_mode") or "Story Idea"
            ).strip(),
            imported_source_name=str(raw.get("imported_source_name") or "").strip(),
            imported_source_word_count=max(
                0, int(raw.get("imported_source_word_count") or 0)
            ),
            has_sandbox_slates=present("sandbox_slates"),
            has_chosen_option=present("chosen_option"),
            has_plot_outline=present("plot_outline"),
            has_current_draft=present("current_draft_output"),
            completed_beats=tuple(sorted(completed)),
            current_processing_beat=max(
                1, int(raw.get("current_processing_beat") or 1)
            ),
            has_revision_report=present("revision_report"),
            has_rewritten_manuscript=present("rewritten_manuscript"),
            final_output_format=str(raw.get("final_output_format") or "").strip(),
            has_final_output=present("final_output_text"),
            has_picture_book_layout=present("picture_book_layout_spreads"),
            picture_book_page_size=str(
                raw.get("picture_book_page_size") or "8.5 x 8.5 Square"
            ).strip(),
            licensed_mode=bool(raw.get("licensed_mode", False)),
            demo_mode=bool(raw.get("demo_mode", False)),
            current_project_id=(
                str(raw.get("current_project_id"))
                if raw.get("current_project_id") is not None
                else None
            ),
            manuscript_version=max(0, int(raw.get("manuscript_version") or 0)),
            current_manuscript_save_status=str(
                raw.get("current_manuscript_save_status") or ""
            ).strip(),
            current_manuscript_save_stage=str(
                raw.get("current_manuscript_save_stage") or ""
            ).strip(),
        )

    @property
    def stage_spec(self):
        return resolve_step(self.project_stage, export_view=self.export_view)

    @property
    def step(self) -> int:
        return self.stage_spec.step

    @property
    def stage_name(self) -> str:
        return self.stage_spec.display_name

    @property
    def is_series(self) -> bool:
        return self.project_scope == "Book in a Series"

    @property
    def has_story_source(self) -> bool:
        if self.starting_source_mode == "Existing Draft / Manuscript":
            return bool(self.imported_source_name and self.imported_source_word_count > 0)
        return bool(self.story_seed.strip())

    def to_context(self) -> Dict[str, Any]:
        result = asdict(self)
        result["step"] = self.step
        result["stage_name"] = self.stage_name
        result["is_series"] = self.is_series
        result["has_story_source"] = self.has_story_source
        return result


@dataclass(frozen=True)
class WBSDecision:
    action: DecisionAction
    step: int
    stage_name: str
    specialist: str
    backend_operation: Optional[str]
    executable: bool
    blockers: Tuple[str, ...] = ()
    next_best_action: str = ""
    reason: str = ""
    preserves: Tuple[str, ...] = ()
    backend_arguments_hint: Dict[str, Any] = field(default_factory=dict)
    routing_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


WORKFLOW_ACTION_DEFAULTS = {
    1: DecisionAction.GENERATE_SANDBOX,
    2: DecisionAction.SELECT_SANDBOX_PATH,
    3: DecisionAction.GENERATE_PLOT,
    4: DecisionAction.DRAFT_NEXT_BEAT,
    5: DecisionAction.REVIEW_SCRIPT_LOCK,
    6: DecisionAction.RUN_POLISH,
    7: DecisionAction.RUN_REWRITE,
    8: DecisionAction.GENERATE_FINAL_OUTPUT,
}

ACTION_SPECIALISTS = {
    DecisionAction.STATUS: "technical",
    DecisionAction.GENERATE_SANDBOX: "creative_development",
    DecisionAction.SELECT_SANDBOX_PATH: "creative_development",
    DecisionAction.GENERATE_PLOT: "creative_development",
    DecisionAction.DRAFT_NEXT_BEAT: "writing",
    DecisionAction.REVIEW_SCRIPT_LOCK: "writing",
    DecisionAction.SAVE_DRAFT: "technical",
    DecisionAction.RUN_POLISH: "writing",
    DecisionAction.RUN_REWRITE: "writing",
    DecisionAction.SKIP_REWRITE: "technical",
    DecisionAction.GENERATE_FINAL_OUTPUT: "production",
    DecisionAction.BUILD_PICTURE_BOOK_LAYOUT: "production",
    DecisionAction.SAVE_FINAL: "technical",
    DecisionAction.SAVE_PROJECT: "technical",
    DecisionAction.MANAGE_VERSION: "technical",
    DecisionAction.RENAME_PROJECT: "technical",
    DecisionAction.MARKETING: "marketing",
    DecisionAction.SALES: "sales",
    DecisionAction.RESEARCH: "research",
    DecisionAction.BUSINESS: "business",
    DecisionAction.TECHNICAL: "technical",
    DecisionAction.GENERAL: "writing",
}

ACTION_BACKEND_OPERATIONS = {
    DecisionAction.GENERATE_SANDBOX: "generate_sandbox_slates",
    DecisionAction.GENERATE_PLOT: "generate_plot_outline",
    DecisionAction.DRAFT_NEXT_BEAT: "execute_recursive_draft_chunk",
    DecisionAction.RUN_POLISH: "run_revision_pass",
    DecisionAction.RUN_REWRITE: "run_rewrite_engine",
    DecisionAction.GENERATE_FINAL_OUTPUT: "run_rewrite_engine",
    DecisionAction.BUILD_PICTURE_BOOK_LAYOUT: "generate_picture_book_layout",
}

PRESERVATION_RULES: Tuple[str, ...] = (
    "Preserve the current project title unless the user explicitly renames it.",
    "Preserve the current development project type unless the user explicitly changes it.",
    "Preserve the current Dialogue Style unless the user explicitly chooses a rewrite override.",
    "Preserve Strict series continuity and previously established canon for series projects.",
    "Use the current live manuscript as the Script Rewrite source; do not substitute a saved version.",
    "Final Output conversion must not replace or silently alter the saved working manuscript.",
    "An imported DOCX/TXT source remains read-only at Concept Development intake.",
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().casefold())


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    for phrase in phrases:
        p = phrase.casefold()
        if " " in p:
            if p in text:
                return True
        elif re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text):
            return True
    return False


def _explicit_action(text: str) -> Optional[DecisionAction]:
    # Non-workflow domain requests first.
    if _contains_any(text, ("marketing", "campaign", "advertising", "ad copy", "promotion")):
        return DecisionAction.MARKETING
    if _contains_any(text, ("sales", "pricing", "checkout", "conversion", "offer", "license price")):
        return DecisionAction.SALES
    if _contains_any(text, ("research", "compare", "competitor", "find out", "investigate", "latest")):
        return DecisionAction.RESEARCH
    if _contains_any(text, ("profit", "margin", "budget", "revenue", "roi", "business model")):
        return DecisionAction.BUSINESS
    if _contains_any(text, ("debug", "code", "python", "streamlit", "supabase", "app.py", "gemini_backend.py", "database")):
        return DecisionAction.TECHNICAL

    if _contains_any(text, ("what next", "next step", "where am i", "project status", "current stage", "status")):
        return DecisionAction.STATUS
    if _contains_any(text, ("rename project", "change project title", "rename title")):
        return DecisionAction.RENAME_PROJECT
    if _contains_any(text, ("delete version", "restore version", "saved version", "version manager")):
        return DecisionAction.MANAGE_VERSION
    if _contains_any(text, ("save project", "project save")):
        return DecisionAction.SAVE_PROJECT
    if _contains_any(text, ("save final", "save final output", "save final manuscript")):
        return DecisionAction.SAVE_FINAL
    if _contains_any(text, ("save current draft", "save draft", "draft checkpoint")):
        return DecisionAction.SAVE_DRAFT
    if _contains_any(text, ("skip rewrite", "proceed to final output")):
        return DecisionAction.SKIP_REWRITE
    if _contains_any(text, ("picture book layout", "build layout", "16 spreads", "32-page layout", "32 page layout")):
        return DecisionAction.BUILD_PICTURE_BOOK_LAYOUT
    if _contains_any(text, ("final output", "generate final", "convert manuscript", "industry format", "format final")):
        return DecisionAction.GENERATE_FINAL_OUTPUT
    if _contains_any(text, ("rewrite", "rewrite scene", "rewrite manuscript", "change story", "polish only")):
        return DecisionAction.RUN_REWRITE
    if _contains_any(text, ("script polish", "polish pass", "continuity check", "pacing check", "tone & style check", "character consistency")):
        return DecisionAction.RUN_POLISH
    if _contains_any(text, ("script lock", "lock script", "review draft", "review manuscript")):
        return DecisionAction.REVIEW_SCRIPT_LOCK
    if _contains_any(text, ("draft next", "draft beat", "write beat", "creative draft", "continue drafting")):
        return DecisionAction.DRAFT_NEXT_BEAT
    if _contains_any(text, ("plot architecture", "plot outline", "generate plot", "four beats", "4 beats")):
        return DecisionAction.GENERATE_PLOT
    if _contains_any(text, ("select path", "choose option", "option a", "option b", "option c")):
        return DecisionAction.SELECT_SANDBOX_PATH
    if _contains_any(text, ("sandbox", "generate paths", "story paths", "scripting options", "generate options")):
        return DecisionAction.GENERATE_SANDBOX

    return None


def _action_blockers(
    action: DecisionAction,
    snapshot: WBSProjectSnapshot,
) -> list[str]:
    blockers: list[str] = []

    if action == DecisionAction.GENERATE_SANDBOX:
        if not snapshot.project_title:
            blockers.append("Project title is required before generating sandbox paths.")
        if not snapshot.has_story_source:
            blockers.append("A story idea, custom plot line, or imported DOCX/TXT source is required.")

    elif action == DecisionAction.SELECT_SANDBOX_PATH:
        if not snapshot.has_sandbox_slates:
            blockers.append("Generate the three Scripting paths before selecting Option A, B, or C.")

    elif action == DecisionAction.GENERATE_PLOT:
        if not snapshot.has_chosen_option:
            blockers.append("Select a Scripting path before generating Plot Architecture.")

    elif action == DecisionAction.DRAFT_NEXT_BEAT:
        if not snapshot.has_plot_outline:
            blockers.append("Generate the four-beat Plot Architecture before Creative Draft.")

    elif action in {
        DecisionAction.REVIEW_SCRIPT_LOCK,
        DecisionAction.SAVE_DRAFT,
        DecisionAction.RUN_POLISH,
        DecisionAction.RUN_REWRITE,
        DecisionAction.SKIP_REWRITE,
        DecisionAction.GENERATE_FINAL_OUTPUT,
        DecisionAction.BUILD_PICTURE_BOOK_LAYOUT,
        DecisionAction.SAVE_FINAL,
    }:
        if not snapshot.has_current_draft:
            blockers.append("A current working manuscript is required.")

    if action == DecisionAction.RUN_POLISH and snapshot.step < 5:
        blockers.append("Script Polish belongs after the manuscript reaches Script Lock.")

    if action == DecisionAction.RUN_REWRITE and snapshot.step < 5:
        blockers.append("Script Rewrite belongs after the manuscript reaches Script Lock.")

    if action == DecisionAction.SKIP_REWRITE and snapshot.step < 5:
        blockers.append("Skip Rewrite is available only after Script Lock.")

    if action in {
        DecisionAction.GENERATE_FINAL_OUTPUT,
        DecisionAction.BUILD_PICTURE_BOOK_LAYOUT,
        DecisionAction.SAVE_FINAL,
    } and snapshot.step != 8:
        blockers.append("Final Output actions require Step 8 / export_view=True.")

    if action == DecisionAction.BUILD_PICTURE_BOOK_LAYOUT:
        selected = snapshot.final_output_format or snapshot.format_type
        try:
            selected = normalize_project_type(selected)
        except ValueError:
            pass
        if selected != PICTURE_BOOK_PROJECT_TYPE:
            blockers.append(
                "Select Children's Picture Book as the Final Output Format before building the 32-page layout."
            )
        if not snapshot.has_final_output:
            blockers.append(
                "Generate the 500-800 word Children's Picture Book final adaptation before building its layout."
            )

    if action in {
        DecisionAction.SAVE_DRAFT,
        DecisionAction.SAVE_FINAL,
        DecisionAction.SAVE_PROJECT,
        DecisionAction.MANAGE_VERSION,
    } and snapshot.demo_mode:
        blockers.append(
            "Saved Projects / Saved Versions are not included in the 7-Day Limited Free Trial."
        )

    return blockers


def _next_best_action(snapshot: WBSProjectSnapshot) -> str:
    if snapshot.step == 1:
        if not snapshot.project_title:
            return "Name the project."
        if not snapshot.has_story_source:
            return "Choose a story idea, enter a custom plot line, or upload a DOCX/TXT draft."
        return "Generate the three Scripting sandbox paths."

    if snapshot.step == 2:
        return (
            "Select Option A, B, or C."
            if snapshot.has_sandbox_slates
            else "Generate the three Scripting sandbox paths."
        )

    if snapshot.step == 3:
        if not snapshot.has_chosen_option:
            return "Return to Scripting and select Option A, B, or C."
        if not snapshot.has_plot_outline:
            return "Generate the four-beat Plot Architecture."
        return "Review the Plot Architecture, then proceed to Creative Draft."

    if snapshot.step == 4:
        if not snapshot.has_plot_outline:
            return "Generate the four-beat Plot Architecture."
        missing = [n for n in range(1, 5) if n not in snapshot.completed_beats]
        if missing:
            return f"Draft Scene Beat {missing[0]}."
        return "Proceed to Script Lock."

    if snapshot.step == 5:
        if not snapshot.has_current_draft:
            return "Return to Creative Draft and complete the manuscript."
        return "Review Script Lock, then save the current draft or proceed to Script Polish."

    if snapshot.step == 6:
        if not snapshot.has_revision_report:
            return "Run the selected Script Polish pass."
        return "Review the Polish Report, then proceed to Script Rewrite."

    if snapshot.step == 7:
        return "Run Script Rewrite, or use SKIP REWRITE — PROCEED TO FINAL OUTPUT."

    if snapshot.step == 8:
        if not snapshot.has_final_output:
            return "Choose a Final Output Format and generate Final Output."
        selected = snapshot.final_output_format or snapshot.format_type
        try:
            selected = normalize_project_type(selected)
        except ValueError:
            pass
        if selected == PICTURE_BOOK_PROJECT_TYPE and not snapshot.has_picture_book_layout:
            return "Build the 32-page / 16-spread Children's Picture Book Layout Draft."
        if snapshot.demo_mode:
            return "Review the generated Final Output."
        return "Review Final Output and save the final manuscript when approved."

    return "Review the current project state."


def _backend_hint(
    action: DecisionAction,
    snapshot: WBSProjectSnapshot,
    request_text: str,
) -> Dict[str, Any]:
    hint: Dict[str, Any] = {}

    if action == DecisionAction.GENERATE_SANDBOX:
        hint = {
            "story_seed": "use current story source / series-aware source",
            "format_type": snapshot.format_type,
            "dialogue_style": snapshot.dialogue_style,
        }

    elif action == DecisionAction.GENERATE_PLOT:
        hint = {
            "chosen_option": "use current selected Option A/B/C",
            "format_type": snapshot.format_type,
            "dialogue_style": snapshot.dialogue_style,
        }

    elif action == DecisionAction.DRAFT_NEXT_BEAT:
        missing = [n for n in range(1, 5) if n not in snapshot.completed_beats]
        hint = {
            "beat_number": missing[0] if missing else snapshot.current_processing_beat,
            "format_type": snapshot.format_type,
            "dialogue_style": snapshot.dialogue_style,
            "rolling_lore_required": True,
        }

    elif action == DecisionAction.RUN_POLISH:
        hint = {
            "source": "current_draft_output",
            "operation": "editorial report only",
        }

    elif action == DecisionAction.RUN_REWRITE:
        normalized = _normalise(request_text)
        ui_mode = "Creative Script Rewrite / Improve Scene"
        backend_mode = ui_mode
        if _contains_any(normalized, ("obey my instructions", "direct script change", "change story exactly")):
            ui_mode = "Direct Script Change / Obey My Instructions Exactly"
            # Current gemini_backend.py tests for "Direct Story Change", while
            # current app.py displays/passes "Direct Script Change". Translate
            # here so the purpose-built Agent invokes the intended backend mode.
            backend_mode = "Direct Story Change / Obey My Instructions Exactly"
        elif _contains_any(normalized, ("polish only", "do not change story")):
            ui_mode = "Polish Only / Do Not Change Story"
            backend_mode = ui_mode

        target_length = "Keep Current Length"
        custom_word_count = None
        if _contains_any(normalized, ("condense", "tighter pacing", "shorten")):
            target_length = "Keep Current Length"
            hint["length_translation"] = (
                "Current backend has no exact 'Condense for Tighter Pacing' branch; "
                "carry the condense requirement in the custom rewrite instruction."
            )
        elif _contains_any(normalized, ("expand to 400", "400 words")):
            target_length = "Custom Word Count"
            custom_word_count = 400
        else:
            match = re.search(r"\b(\d{2,5})\s*words?\b", normalized)
            if match:
                target_length = "Custom Word Count"
                custom_word_count = int(match.group(1))

        hint.update({
            "source": "current live manuscript only",
            "ui_rewrite_mode": ui_mode,
            "backend_rewrite_mode": backend_mode,
            "target_length": target_length,
            "custom_target_word_count": custom_word_count,
            "dialogue_style_default": snapshot.dialogue_style,
        })

    elif action == DecisionAction.GENERATE_FINAL_OUTPUT:
        selected = snapshot.final_output_format or snapshot.format_type
        try:
            selected = normalize_project_type(selected)
        except ValueError:
            selected = snapshot.format_type
        hint = {
            "source": "current_draft_output",
            "final_output_format": selected,
            "backend_rewrite_mode": "Direct Story Change / Obey My Instructions Exactly",
            "scene_choice": "Full Manuscript",
            "preserve_working_manuscript": True,
        }
        if selected == PICTURE_BOOK_PROJECT_TYPE:
            hint.update({
                "target_length": "Custom Word Count",
                "custom_target_word_count": 700,
                "required_range": "500-800 words; never over 800",
            })
        else:
            hint["target_length"] = "Keep Current Length"

    elif action == DecisionAction.BUILD_PICTURE_BOOK_LAYOUT:
        hint = {
            "source": "current final-output picture-book adaptation",
            "spreads": 16,
            "pages": 32,
            "page_size": snapshot.picture_book_page_size,
            "print_ready": False,
        }

    return hint


class WBSDecisionEngine:
    """Deterministic purpose-specific decision layer."""

    def analyze(
        self,
        request_text: str,
        project_state: WBSProjectSnapshot | Mapping[str, Any],
    ) -> WBSDecision:
        snapshot = (
            project_state
            if isinstance(project_state, WBSProjectSnapshot)
            else WBSProjectSnapshot.from_mapping(project_state)
        )
        text = _normalise(request_text)

        action = _explicit_action(text)
        if action is None:
            # Ordinary Quill conversation is not a workflow command.
            # Project prerequisites only apply to explicit workflow actions.
            action = DecisionAction.GENERAL

        # A plain "continue"/"go"/"next" should advance the current workflow.
        if text in {"continue", "go", "next", "proceed", "go ahead"}:
            action = WORKFLOW_ACTION_DEFAULTS.get(snapshot.step, DecisionAction.GENERAL)

        specialist = ACTION_SPECIALISTS[action]
        backend_operation = ACTION_BACKEND_OPERATIONS.get(action)
        blockers = _action_blockers(action, snapshot)
        next_best = _next_best_action(snapshot)
        backend_hint = _backend_hint(action, snapshot, text)

        reason = (
            f"Current WritersBlock state resolves to Step {snapshot.step}: "
            f"{snapshot.stage_name}. Request maps to '{action.value}'."
        )
        if backend_operation:
            reason += f" Matching application backend operation: {backend_operation}."

        routing = {
            "requested_specialists": [specialist],
            "force_route": "specialist",
            "wbs_action": action.value,
            "wbs_step": snapshot.step,
            "wbs_stage": snapshot.stage_name,
            "wbs_backend_operation": backend_operation,
        }

        return WBSDecision(
            action=action,
            step=snapshot.step,
            stage_name=snapshot.stage_name,
            specialist=specialist,
            backend_operation=backend_operation,
            executable=not blockers,
            blockers=tuple(blockers),
            next_best_action=next_best,
            reason=reason,
            preserves=PRESERVATION_RULES,
            backend_arguments_hint=backend_hint,
            routing_metadata=routing,
        )

    def next_best_action(
        self,
        project_state: WBSProjectSnapshot | Mapping[str, Any],
    ) -> str:
        snapshot = (
            project_state
            if isinstance(project_state, WBSProjectSnapshot)
            else WBSProjectSnapshot.from_mapping(project_state)
        )
        return _next_best_action(snapshot)


__all__ = [
    "ACTION_BACKEND_OPERATIONS",
    "ACTION_SPECIALISTS",
    "DecisionAction",
    "PRESERVATION_RULES",
    "WBS_DECISION_ENGINE_VERSION",
    "WBSDecision",
    "WBSDecisionEngine",
    "WBSProjectSnapshot",
]