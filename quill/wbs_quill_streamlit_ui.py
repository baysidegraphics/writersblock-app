"""
WritersBlock Studios
Quill Streamlit Interface
Version: 1.0

Purpose
-------
Render Quill as a compact Studio Coach inside the existing WritersBlock
Streamlit application.

Design rules
------------
- Brief first. Detail only when requested.
- Quill never replaces existing WritersBlock controls.
- Quill never mutates normal project-state fields.
- Quill owns only session keys beginning with _wbs_quill_.
- Quill is always rendered in the fixed right-hand panel.
- No workflow stage may render Quill as a full-width page block or modal.
- A deeper discussion path is available without turning the main page into a
  large chat interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import html
import io
import json
import os
import re
from pathlib import Path
import wave
from typing import Any, Mapping, MutableMapping, Optional

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None

try:  # package import in WritersBlock Studio Agent/quill/
    from .wbs_quill_runtime_bridge import QuillRuntimeBridge, QuillRuntimeResult
    from .wbs_quill_studio_coach import QuillDetailMode
except ImportError:  # direct-file test/import
    from wbs_quill_runtime_bridge import QuillRuntimeBridge, QuillRuntimeResult
    from wbs_quill_studio_coach import QuillDetailMode

try:
    from .wbs_quill_intelligence import answer_quill
except ImportError:
    try:
        from wbs_quill_intelligence import answer_quill
    except ImportError:
        # Commercial build may not include the optional intelligence module.
        # Quill continues through the existing runtime bridge/agent fallback.
        answer_quill = None


QUILL_STREAMLIT_UI_VERSION = "32.3-RIGHT-PANEL-NAME-INTRO"
QUILL_STATE_PREFIX = "_wbs_quill_"
PRELUDE_SEEN_KEY = f"{QUILL_STATE_PREFIX}prelude_seen"
DISPLAY_NAME_KEY = f"{QUILL_STATE_PREFIX}display_name"
LAST_RESPONSE_KEY = f"{QUILL_STATE_PREFIX}last_response"
LAST_SOURCE_KEY = f"{QUILL_STATE_PREFIX}last_source"
QUESTION_KEY = f"{QUILL_STATE_PREFIX}question"
INTRO_RENDERED_KEY = f"{QUILL_STATE_PREFIX}intro_rendered"
CHAT_HISTORY_KEY = f"{QUILL_STATE_PREFIX}chat_history"
COLLAPSED_KEY = f"{QUILL_STATE_PREFIX}collapsed"
VOICE_ENABLED_KEY = f"{QUILL_STATE_PREFIX}voice_enabled_v32"
VOICE_GENDER_KEY = f"{QUILL_STATE_PREFIX}voice_gender"
LAST_SPOKEN_KEY = f"{QUILL_STATE_PREFIX}last_spoken"
VOICE_STOP_KEY = f"{QUILL_STATE_PREFIX}voice_stop"
VOICE_ERROR_KEY = f"{QUILL_STATE_PREFIX}voice_error"
SESSION_INITIALIZED_KEY = f"{QUILL_STATE_PREFIX}session_initialized_v33"
NAME_CONFIRMED_KEY = f"{QUILL_STATE_PREFIX}name_confirmed_v33"

QUILL_DIR = Path(__file__).resolve().parent
QUILL_LOGO_CANDIDATES = (
    QUILL_DIR / "quill_owl_transparent.png",
    QUILL_DIR / "quill_logo.png",
    QUILL_DIR / "quill_owl.png",
)


def _render_quill_logo(st: Any, *, width: int) -> None:
    """Render Quill with the surrounding dark image background made transparent."""
    for logo_path in QUILL_LOGO_CANDIDATES:
        if not logo_path.exists():
            continue

        if Image is not None and ImageDraw is not None:
            try:
                with Image.open(logo_path) as source:
                    logo = source.convert("RGBA")

                # Remove only the dark background connected to the image edges.
                # Internal dark details in the owl/logo remain intact.
                ImageDraw.floodfill(logo, (0, 0), (0, 0, 0, 0), thresh=42)
                ImageDraw.floodfill(logo, (logo.width - 1, 0), (0, 0, 0, 0), thresh=42)
                ImageDraw.floodfill(logo, (0, logo.height - 1), (0, 0, 0, 0), thresh=42)
                ImageDraw.floodfill(logo, (logo.width - 1, logo.height - 1), (0, 0, 0, 0), thresh=42)
                st.image(logo, width=width)
                return
            except Exception:
                pass

        st.image(str(logo_path), width=width)
        return

    st.markdown("### QUILL")


@dataclass(frozen=True)
class QuillUIPayload:
    text: str
    stage: str
    severity: str = "info"
    source: str = "coach"
    next_action: str = ""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _mapping_get(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return mapping.get(key, default)
    except AttributeError:
        try:
            return mapping[key]
        except Exception:
            return default


def _has_writer_access(state: Mapping[str, Any]) -> bool:
    """True when a paid license or the 7-day trial is already active."""
    return bool(
        _mapping_get(state, "licensed_mode", False)
        or _mapping_get(state, "demo_mode", False)
    )


def _access_reminder_text(state: Mapping[str, Any], preferred_name: str = "") -> str:
    name = _clean(preferred_name) or _clean(_mapping_get(state, DISPLAY_NAME_KEY, ""))
    greeting = f"{name}, " if name else ""
    return (
        f"{greeting}before we start working together, open **License / Trial** in the sidebar "
        "and either start your **7-Day Limited Free Trial** or enter the email for your "
        "Writer Edition license."
    )


def initialize_quill_state(state: MutableMapping[str, Any]) -> None:
    defaults = {
        PRELUDE_SEEN_KEY: True,
        DISPLAY_NAME_KEY: "",
        LAST_RESPONSE_KEY: "",
        LAST_SOURCE_KEY: "",
        QUESTION_KEY: "",
        INTRO_RENDERED_KEY: False,
        CHAT_HISTORY_KEY: [],
        COLLAPSED_KEY: False,
        VOICE_ENABLED_KEY: True,
        VOICE_GENDER_KEY: "Male",
        LAST_SPOKEN_KEY: "",
        VOICE_STOP_KEY: False,
        VOICE_ERROR_KEY: "",
        SESSION_INITIALIZED_KEY: False,
        NAME_CONFIRMED_KEY: False,
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value

    # A fresh Streamlit session begins as a fresh Quill conversation.
    # The writer supplies the Quill-facing name once on the opening entry page;
    # the normal Quill panel then reuses that name automatically.
    if not bool(state.get(SESSION_INITIALIZED_KEY, False)):
        state[CHAT_HISTORY_KEY] = []
        state[LAST_RESPONSE_KEY] = ""
        state[LAST_SOURCE_KEY] = ""
        state[QUESTION_KEY] = ""
        state[LAST_SPOKEN_KEY] = ""
        state[VOICE_STOP_KEY] = False
        state[VOICE_ERROR_KEY] = ""
        state[NAME_CONFIRMED_KEY] = False
        state[SESSION_INITIALIZED_KEY] = True


def clear_quill_response(state: MutableMapping[str, Any]) -> None:
    state[LAST_RESPONSE_KEY] = ""
    state[LAST_SOURCE_KEY] = ""


def _startup_welcome_text(active_name: str) -> str:
    clean_name = _clean(active_name)
    return (
        f"Welcome, {clean_name}.\n\n"
        "Start by giving your story a working title. "
        "It does not have to be permanent — you can rename it later."
    )


def _set_personal_startup_welcome(
    state: MutableMapping[str, Any],
    active_name: str,
) -> None:
    clean_name = _clean(active_name)
    if not clean_name:
        return

    message = _startup_welcome_text(clean_name)
    history = list(state.get(CHAT_HISTORY_KEY, []) or [])

    # Remove older startup variants and the zero-credit title prompt because
    # the personalized welcome already contains that exact first instruction.
    filtered = []
    for item in history:
        source = _clean(item.get("source", ""))
        content = _clean(item.get("content", ""))
        if source == "startup_welcome":
            continue
        if content.lower().startswith("start by giving your story a working title"):
            continue
        filtered.append(item)

    filtered.insert(0, {
        "role": "assistant",
        "content": message,
        "source": "startup_welcome",
    })
    state[CHAT_HISTORY_KEY] = filtered
    state[LAST_RESPONSE_KEY] = message
    state[LAST_SOURCE_KEY] = "startup_welcome"


def _resolve_kokoro_server_files() -> tuple[Path, Path]:
    """Find local Kokoro models or provision them for hosted Streamlit."""
    configured = str(os.getenv("WBS_QUILL_TTS_DIR", "") or "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        Path.cwd() / "static" / "quill_tts" / "server",
        Path.cwd() / "WritersBlock Integration-Test" / "static" / "quill_tts" / "server",
    ])
    for folder in candidates:
        model = folder / "kokoro-v1.0.onnx"
        voices = folder / "voices-v1.0.bin"
        if model.is_file() and voices.is_file():
            return model, voices

    # Models cannot be committed to an ordinary GitHub repository (100 MB limit).
    # Download the smaller official FP16 checkpoint lazily to the running server.
    folder = candidates[0] if configured else candidates[1]
    folder.mkdir(parents=True, exist_ok=True)
    model = folder / "kokoro-v1.0.onnx"
    voices = folder / "voices-v1.0.bin"
    base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"

    def fetch(url: str, target: Path, minimum_bytes: int) -> None:
        if target.is_file() and target.stat().st_size >= minimum_bytes:
            return
        import requests
        temporary = target.with_suffix(target.suffix + ".download")
        try:
            with requests.get(url, stream=True, timeout=(20, 180), allow_redirects=True) as response:
                response.raise_for_status()
                with temporary.open("wb") as out:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            out.write(chunk)
            if temporary.stat().st_size < minimum_bytes:
                raise RuntimeError(f"Incomplete voice model download: {target.name}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    fetch(base + "kokoro-v1.0.fp16.onnx", model, 100_000_000)
    fetch(base + "voices-v1.0.bin", voices, 20_000_000)
    return model, voices


@lru_cache(maxsize=1)
def _load_kokoro_engine() -> Any:
    """Load Kokoro once per Python process so normal Streamlit reruns stay fast."""
    try:
        from kokoro_onnx import Kokoro
    except ImportError as exc:
        raise RuntimeError(
            "kokoro-onnx is not installed in the Python environment running Streamlit."
        ) from exc

    model_path, voices_path = _resolve_kokoro_server_files()
    return Kokoro(str(model_path), str(voices_path))


def _samples_to_wav_bytes(samples: Any, sample_rate: int) -> bytes:
    """Convert Kokoro float samples to a browser-playable mono WAV."""
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("NumPy is required for Quill voice playback.") from exc

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _spoken_integer(value: int) -> str:
    """Small dependency-free number-to-words helper for Quill pricing speech."""
    value = int(value)
    if value < 0:
        return "minus " + _spoken_integer(abs(value))

    ones = [
        "zero", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
        "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    if value < 20:
        return ones[value]
    if value < 100:
        return tens[value // 10] + (f" {ones[value % 10]}" if value % 10 else "")
    if value < 1000:
        return (
            f"{ones[value // 100]} hundred"
            + (f" {_spoken_integer(value % 100)}" if value % 100 else "")
        )
    if value < 1_000_000:
        return (
            f"{_spoken_integer(value // 1000)} thousand"
            + (f" {_spoken_integer(value % 1000)}" if value % 1000 else "")
        )
    return str(value)


def _normalize_quill_tts_text(text: str) -> str:
    """Convert display-friendly prices into words before Kokoro sees them.

    Visible text remains unchanged. Examples:
    $99 -> "ninety nine dollars"
    $49 -> "forty nine dollars"
    $1.99 -> "one dollar and ninety nine cents"
    """
    clean = str(text or "")

    def replace_usd(match: re.Match[str]) -> str:
        whole_raw = (match.group(1) or "0").replace(",", "")
        cents_raw = match.group(2)
        whole = int(whole_raw)

        if cents_raw is None:
            return f"{_spoken_integer(whole)} {'dollar' if whole == 1 else 'dollars'}"

        cents = int(cents_raw.ljust(2, "0")[:2])
        pieces = []
        if whole:
            pieces.append(
                f"{_spoken_integer(whole)} {'dollar' if whole == 1 else 'dollars'}"
            )
        if cents:
            cent_text = f"{_spoken_integer(cents)} {'cent' if cents == 1 else 'cents'}"
            pieces.append(("and " if pieces else "") + cent_text)

        return " ".join(pieces) if pieces else "zero dollars"

    clean = re.sub(r"\$(\d[\d,]*)(?:\.(\d{1,2}))?", replace_usd, clean)
    return clean.strip()


def _generate_quill_voice(text: str, gender: str) -> bytes:
    """Generate Quill speech locally with Kokoro ONNX; no paid TTS API."""
    clean_text = _normalize_quill_tts_text(text)
    if not clean_text:
        return b""

    engine = _load_kokoro_engine()
    voice = "af_heart" if str(gender or "Male").lower() == "female" else "am_michael"

    samples, sample_rate = engine.create(
        clean_text,
        voice=voice,
        speed=1.0,
        lang="en-us",
    )
    return _samples_to_wav_bytes(samples, sample_rate)


def _browser_stop_speech() -> None:
    """Compatibility hook for the existing speaker toggle.

    Server-side Kokoro produces a one-shot audio element on each response.
    Streamlit removes that element on the next rerun, so there is no browser
    SpeechSynthesis session to cancel.
    """
    return



def _runtime_output(runtime_result: Any) -> str:
    """Extract the user-facing output from the Universal/WBS Agent result."""
    if runtime_result is None:
        return ""

    # AgentResult dataclass/object.
    output = getattr(runtime_result, "output", None)
    if output is not None:
        if isinstance(output, Mapping):
            for key in ("text", "message", "content", "output", "response"):
                value = output.get(key)
                if value:
                    return str(value).strip()
            return str(dict(output)).strip()
        return str(output).strip()

    # Serialized/summarized result.
    if isinstance(runtime_result, Mapping):
        for key in ("output", "text", "message", "content", "response"):
            value = runtime_result.get(key)
            if value:
                if isinstance(value, Mapping):
                    for nested in ("text", "message", "content", "response"):
                        nested_value = value.get(nested)
                        if nested_value:
                            return str(nested_value).strip()
                return str(value).strip()

    return ""


class QuillInterfaceController:
    """UI-neutral Quill controller used by the Streamlit renderer and tests."""

    def __init__(
        self,
        bridge: QuillRuntimeBridge,
        project_state: Mapping[str, Any] | Any,
    ) -> None:
        self.bridge = bridge
        self.project_state = project_state

    def prelude(self) -> str:
        return self.bridge.prelude()

    def brief(self) -> QuillUIPayload:
        result = self.bridge.guidance("what next?", self.project_state)
        return self._coach_payload(result, source="coach")

    def detail(self) -> QuillUIPayload:
        result = self.bridge.guidance(
            "explain why",
            self.project_state,
            detail_mode=QuillDetailMode.DETAIL,
        )
        return self._coach_payload(result, source="detail")

    def ask(
        self,
        question: str,
        *,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> QuillUIPayload:
        clean_question = _clean(question)
        if not clean_question:
            return self.brief()

        # Project-aware Quill intelligence handles both Program Coach and
        # Creative Collaboration questions before falling back to the runtime bridge.
        try:
            intelligent = (
                answer_quill(clean_question, self.project_state)
                if callable(answer_quill)
                else None
            )
            if intelligent is None:
                raise RuntimeError("Optional Quill intelligence module is not installed.")

            # The current intelligence layer still contains the older paid-only
            # Collaboration gate. Creative Collaboration is now INCLUDED in the
            # 7-Day Free Trial. If that old gate is returned, retry only this
            # collaboration request with a temporary entitlement overlay.
            if (
                bool(_mapping_get(self.project_state, "demo_mode", False))
                and str(getattr(intelligent, "mode", "") or "").lower() == "collaboration"
            ):
                blocked_text = str(getattr(intelligent, "text", "") or "").lower()
                old_gate_markers = (
                    "full version",
                    "$99",
                    "creative collaboration is included",
                    "collaboration is included",
                    "not included in the trial",
                )
                if any(marker in blocked_text for marker in old_gate_markers):
                    try:
                        trial_collaboration_state = dict(self.project_state)
                    except Exception:
                        trial_collaboration_state = {}

                    # Temporary view for Quill intelligence only.
                    # This does NOT change the user's actual product tier,
                    # Final Output rights, download rights, or app session state.
                    trial_collaboration_state["demo_mode"] = True
                    trial_collaboration_state["licensed_mode"] = True
                    trial_collaboration_state["product_tier"] = "studio"

                    retried = answer_quill(
                        clean_question,
                        trial_collaboration_state,
                    )
                    if getattr(retried, "text", None):
                        intelligent = retried

            if intelligent.text:
                return QuillUIPayload(
                    text=intelligent.text,
                    stage=intelligent.stage,
                    severity="info",
                    source=intelligent.mode,
                    next_action="",
                )
        except Exception:
            pass

        # Safe fallback: existing deterministic/runtime behavior remains available.
        if getattr(self.bridge, "agent", None) is None:
            result = self.bridge.guidance(
                clean_question,
                self.project_state,
                detail_mode=QuillDetailMode.DETAIL,
            )
            return self._coach_payload(result, source="detail")

        result = self.bridge.ask(
            clean_question,
            self.project_state,
            project_id=project_id,
            project_name=project_name,
            detail_mode=QuillDetailMode.DETAIL,
        )
        runtime_text = _runtime_output(result.runtime_result)
        if runtime_text:
            return QuillUIPayload(
                text=runtime_text,
                stage=result.coach.stage,
                severity=result.coach.severity.value,
                source="discussion",
                next_action=result.coach.next_action,
            )
        return self._coach_payload(result, source="detail")

    @staticmethod
    def _coach_payload(result: QuillRuntimeResult, *, source: str) -> QuillUIPayload:
        return QuillUIPayload(
            text=result.coach.text,
            stage=result.coach.stage,
            severity=result.coach.severity.value,
            source=source,
            next_action=result.coach.next_action,
        )


def build_quill_controller(
    session_state: Mapping[str, Any],
    *,
    agent: Any = None,
    bridge: Optional[QuillRuntimeBridge] = None,
    display_name: str = "",
) -> QuillInterfaceController:
    active_name = _clean(display_name) or _clean(_mapping_get(session_state, DISPLAY_NAME_KEY, ""))
    active_bridge = bridge or QuillRuntimeBridge(
        agent=agent,
        display_name=active_name,
    )
    return QuillInterfaceController(active_bridge, session_state)




def _revise_existing_quill_concept(state: MutableMapping[str, Any], request: str) -> Optional[QuillUIPayload]:
    """Route explicit concept feedback to the existing editable concept, not stage advice."""
    if state.get("starting_source_mode") != "Quill Assisted":
        return None
    format_id = str(state.get("active_format_id") or "")
    if not format_id:
        return None
    concept_key = f"wbs_quill_starting_concept_{format_id}"
    original = str(state.get(concept_key) or "").strip()
    if not original:
        return None

    lowered = request.lower()
    edit_intent = bool(re.search(
        r"\b(revise|rewrite|change|adjust|modify|tailor|rework|refine|less|more|instead|"
        r"tone down|make it|make the|not so|too dramatic|too dark|too much|"
        r"rather than|shift|different direction|another direction)\b", lowered
    ))
    concept_reference = bool(re.search(
        r"\b(story|concept|suggestion|premise|plot|direction|idea|ending|character|tone|"
        r"narrative|this|that|it|your)\b", lowered
    ))
    if not (edit_intent and concept_reference):
        return None

    backend = state.get("backend")
    client = getattr(backend, "client", None)
    model = getattr(backend, "model_name", None)
    if client is None or not model:
        return QuillUIPayload(
            text="I can revise the current concept when the writing service is available. Your existing suggestion is unchanged.",
            stage="Concept Development", source="concept_revision_unavailable"
        )

    setup_context = str(state.get("wbs_quill_continuity_context") or state.get("active_format_development_context") or "")
    format_name = str((state.get("active_format_template") or {}).get("display_name") or format_id)
    context_fields = []
    for key in ("tone_style", "genre", "story_genre", "dialogue_style", "production_influence", "quill_format_instructions"):
        value = state.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            context_fields.append(f"{key}: {value}")
    instructions = (
        "You are Quill, the WritersBlock Studios writing collaborator. "
        "The writer is revising the CURRENT suggested starting concept in Step 1, "
        "not requesting workflow instructions or entry into Scripting. "
        "The development setup was already selected. Never ask the writer to fill it again. "
        "Revise the existing concept according to the latest feedback. "
        "Retain the original premise, characters and key intent unless the writer asks otherwise. "
        "Honor the original genre, age range, tone and other available development settings. "
        "Return ONLY a natural, polished third-person synopsis in 100–180 words. "
        "Use character actions, stakes and events, not editorial observations. "
        "Never say 'this story explores', 'the narrative should', 'the story should', "
        "'the premise', 'the audience', 'the writer', or 'the theme'. "
        "No headings, commentary, stage instructions, analysis or status.\n\n"
        f"Writing format: {format_name}\n"
        f"Existing concept:\n{original}\n\n"
        f"Writer's requested change:\n{request}\n\n"
        f"Development details:\n{setup_context}\n" + "\n".join(context_fields)
    )
    try:
        result = client.models.generate_content(model=model, contents=instructions)
        revised = str(getattr(result, "text", "") or "").strip()
        if not revised:
            raise ValueError("No revised concept returned")
    except Exception:
        return QuillUIPayload(
            text="I couldn't revise the concept just now. The current suggestion has been preserved; please try again.",
            stage="Concept Development", source="concept_revision_failed"
        )
    # Streamlit has already instantiated the concept widget in this run.
    # Queue the revision; app.py will install it before recreating that widget.
    state[f"_wbs_quill_pending_concept_{format_id}"] = revised
    return QuillUIPayload(
        text="I've revised the starting concept to reflect your direction. The updated concept is in the editable box under Quill-Assisted Starting Point.",
        stage="Concept Development", source="concept_revision"
    )

def render_quill_studio_coach(
    *,
    agent: Any = None,
    bridge: Optional[QuillRuntimeBridge] = None,
    display_name: str = "",
    st_module: Any = None,
    show_prelude: bool = True,
    credit_manager: Any = None,
    credit_user_id: Any = None,
    usage_logger: Any = None,
) -> Optional[QuillUIPayload]:
    """Render Quill as a non-obstructive Studio Coach.

    First use:
      - Quill takes center stage in a modal introduction.
      - The user can choose the name Quill should use.

    Normal use:
      - Quill remains perched at the upper-right.
      - Clicking QUILL opens a compact popover coach.
      - Existing WritersBlock controls remain authoritative.
    """
    if st_module is None:
        import streamlit as st_module  # type: ignore

    st = st_module
    state = st.session_state
    initialize_quill_state(state)

    active_name = _clean(display_name) or _clean(state.get(DISPLAY_NAME_KEY, ""))

    # If the writer already entered a name on Quill's opening entry page and then
    # activates Trial / License from the sidebar, carry that name forward automatically.
    # Do not ask for the name a second time inside the normal Quill panel.
    pending_name = _clean(state.get(f"{QUILL_STATE_PREFIX}name_setup", ""))
    if (
        show_prelude
        and not bool(state.get(PRELUDE_SEEN_KEY))
        and bool(state.get(INTRO_RENDERED_KEY))
        and bool(pending_name)
        and _has_writer_access(state)
    ):
        state[DISPLAY_NAME_KEY] = pending_name
        active_name = pending_name
        state[NAME_CONFIRMED_KEY] = True
        state[CHAT_HISTORY_KEY] = []
        _set_personal_startup_welcome(state, pending_name)
        state[LAST_SPOKEN_KEY] = ""
        state[PRELUDE_SEEN_KEY] = True

    active_bridge = bridge or QuillRuntimeBridge(agent=agent, display_name=active_name)
    controller = QuillInterfaceController(active_bridge, state)

    # ---------- RIGHT-HAND PANEL LOCK ----------
    # Quill is never allowed to take over the main workflow area.
    # This applies to new projects, saved projects, and every Writer Studio stage.
    state[PRELUDE_SEEN_KEY] = True
    state[INTRO_RENDERED_KEY] = False

    # ---------- Resting Quill / collapsible professional chat ----------
    collapsed = bool(state.get(COLLAPSED_KEY, False))

    st.markdown(
        f"""
        <style>
        .wbs-quill-v18-marker {{ height: 0; overflow: hidden; }}
        .wbs-quill-v18-collapsed-marker {{ height: 0; overflow: hidden; }}

        /* Reserve permanent page space for the fixed Quill panel. */
        section.main > div.block-container,
        div[data-testid="stMainBlockContainer"] {{
            padding-right: 365px !important;
            box-sizing: border-box !important;
        }}

        /* Expanded Quill panel */
        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker) {{
            position: fixed !important;
            top: 6.5rem !important;
            right: 1.25rem !important;
            width: 330px !important;
            min-width: 330px !important;
            max-width: 330px !important;
            z-index: 80 !important;
            align-self: flex-start !important;
            background: #272A32 !important;
            border: 1px solid #0B84FF !important;
            border-radius: 8px !important;
            padding: 10px 12px 10px 12px !important;
            box-sizing: border-box !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker)
        div[data-testid="stVerticalBlock"] {{
            border: none !important;
            box-shadow: none !important;
            background: transparent !important;
        }}

        /* Collapsed Quill tab — intentionally very small so it does not cover work. */
        div[data-testid="stColumn"]:has(.wbs-quill-v18-collapsed-marker) {{
            position: fixed !important;
            top: 7.25rem !important;
            right: .55rem !important;
            width: 86px !important;
            min-width: 86px !important;
            max-width: 86px !important;
            z-index: 80 !important;
            align-self: flex-start !important;
            background: #272A32 !important;
            border: 1px solid #0B84FF !important;
            border-radius: 8px !important;
            padding: 7px 6px 7px 6px !important;
            box-sizing: border-box !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-collapsed-marker)
        div[data-testid="stVerticalBlock"] {{
            border: none !important;
            box-shadow: none !important;
            background: transparent !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-collapsed-marker) img {{
            display: block !important;
            margin: 0 auto 3px auto !important;
        }}

        .wbs-quill-v18-collapse-title {{
            color: #48A8FF;
            text-align: center;
            font-size: .68rem;
            font-weight: 700;
            line-height: 1.1;
            margin: 0 0 4px 0;
        }}

        /* Only the collapse/open controls are square.
           Do NOT shrink other Quill buttons/popovers. */
        .st-key-wbs_quill_collapse_v32 button,
        .st-key-wbs_quill_open_v32 button {{
            background: #2B3038 !important;
            color: #48A8FF !important;
            border: 1px solid #4A5360 !important;
            font-size: .92rem !important;
            font-weight: 700 !important;
            width: 30px !important;
            min-width: 30px !important;
            max-width: 30px !important;
            height: 30px !important;
            min-height: 30px !important;
            padding: 0 !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}

        .st-key-wbs_quill_collapse_v32 button:hover,
        .st-key-wbs_quill_open_v32 button:hover {{
            background: #343A44 !important;
            color: #72BBFF !important;
            border-color: #0B84FF !important;
        }}

        /* Speaker gets its own compact square style. */
        .st-key-wbs_quill_voice_toggle_v32 button {{
            background: #2B3038 !important;
            color: #48A8FF !important;
            border: 1px solid #4A5360 !important;
            width: 32px !important;
            min-width: 32px !important;
            max-width: 32px !important;
            height: 30px !important;
            min-height: 30px !important;
            padding: 0 !important;
            margin: 0 auto !important;
        }}

        /* Compact voice row: Male / Female + speaker, no white cards. */
        .st-key-wbs_quill_voice_gender_v32 div[role="radiogroup"] {{
            display: flex !important;
            flex-direction: row !important;
            gap: .85rem !important;
            justify-content: flex-start !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            padding-left: 48px !important;
            box-sizing: border-box !important;
        }}

        .st-key-wbs_quill_voice_gender_v32 div[role="radiogroup"] label {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 0 !important;
            width: auto !important;
            min-width: fit-content !important;
            white-space: nowrap !important;
        }}

        .st-key-wbs_quill_voice_gender_v32 div[role="radiogroup"] label p {{
            color: #FFFFFF !important;
            font-size: .78rem !important;
            font-weight: 600 !important;
            white-space: nowrap !important;
        }}

        .st-key-wbs_quill_voice_gender_v32 div[role="radiogroup"] label span {{
            color: #FFFFFF !important;
            background: transparent !important;
        }}

        /* "What can Quill do?" reference */
        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker)
        div[data-testid="stPopover"] > button {{
            width: 100% !important;
            min-width: 0 !important;
            max-width: none !important;
            height: auto !important;
            min-height: 30px !important;
            background: #22262D !important;
            color: #FFFFFF !important;
            border: 1px solid #4A5360 !important;
            border-radius: 7px !important;
            box-shadow: none !important;
            font-size: .72rem !important;
            font-weight: 700 !important;
            padding: 5px 8px !important;
            white-space: nowrap !important;
            overflow: visible !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker)
        div[data-testid="stPopover"] > button:hover {{
            color: #72BBFF !important;
            background: transparent !important;
        }}

        div[data-baseweb="popover"] > div {{
            background: #272A32 !important;
            color: #FFFFFF !important;
            border: 1px solid #0B84FF !important;
        }}
        div[data-baseweb="popover"] p,
        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] span,
        div[data-baseweb="popover"] strong {{
            color: #FFFFFF !important;
        }}

        /* Header */
        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker) img {{
            display: block !important;
            margin: 0 auto 2px auto !important;
        }}

        .wbs-quill-v11-title {{
            color: #FFFFFF;
            font-size: .90rem;
            font-weight: 700;
            letter-spacing: .01em;
            margin: 0;
            text-align: center;
            align-self: center;
            white-space: nowrap;
        }}

        .wbs-quill-v11-prompt {{
            color: #FFFFFF;
            font-size: .80rem;
            font-style: italic;
            text-align: center;
            margin: 0 0 10px 0;
        }}

        .wbs-quill-v11-chat {{
            height: 285px;
            overflow-y: auto;
            padding: 4px 5px 8px 5px;
            margin-bottom: 8px;
            background: #272A32;
        }}

        .wbs-quill-v11-user {{
            color: #FFFFFF;
            font-size: .82rem;
            font-style: normal;
            line-height: 1.42;
            margin: 0 0 10px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(11,132,255,.22);
        }}

        .wbs-quill-v11-quill {{
            color: #FFFFFF;
            font-size: .82rem;
            font-style: italic;
            line-height: 1.42;
            margin: 0 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(11,132,255,.22);
        }}

        .wbs-quill-v11-label {{
            color: #48A8FF;
            font-size: .70rem;
            font-weight: 700;
            font-style: normal;
            letter-spacing: .04em;
            margin-bottom: 2px;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker) textarea {{
            min-height: 128px !important;
            max-height: 180px !important;
            resize: vertical !important;
            background: #1F2228 !important;
            color: #FFFFFF !important;
            border: 1px solid #4A5360 !important;
            font-size: .82rem !important;
            line-height: 1.35 !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker) textarea::placeholder {{
            color: #AEB5BF !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker)
        div[data-testid="stFormSubmitButton"] button {{
            width: auto !important;
            min-width: 68px !important;
            float: right !important;
            background: #2B3038 !important;
            color: #48A8FF !important;
            border: 1px solid #4A5360 !important;
            font-size: .76rem !important;
            font-weight: 700 !important;
            padding: .25rem .75rem !important;
        }}

        div[data-testid="stColumn"]:has(.wbs-quill-v18-marker)
        div[data-testid="stFormSubmitButton"] button:hover {{
            background: #343A44 !important;
            color: #72BBFF !important;
            border-color: #0B84FF !important;
        }}

        @media (max-width: 1100px) {{
            section.main > div.block-container,
            div[data-testid="stMainBlockContainer"] {{
                padding-right: 1rem !important;
            }}
            div[data-testid="stColumn"]:has(.wbs-quill-v18-marker),
            div[data-testid="stColumn"]:has(.wbs-quill-v18-collapsed-marker) {{
                position: static !important;
                width: 100% !important;
                min-width: 0 !important;
                max-width: none !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    spacer, quill_col = st.columns([9.2, 0.8], vertical_alignment="top")

    with quill_col:
        if collapsed:
            st.markdown(
                '<div class="wbs-quill-v18-collapsed-marker"></div>',
                unsafe_allow_html=True,
            )
            _render_quill_logo(st, width=58)
            st.markdown(
                '<div class="wbs-quill-v18-collapse-title">QUILL</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "<",
                key="wbs_quill_open_v32",
                help="Open Quill",
                use_container_width=False,
            ):
                state[COLLAPSED_KEY] = False
                st.rerun()

            return None

        st.markdown(
            '<div class="wbs-quill-v18-marker"></div>',
            unsafe_allow_html=True,
        )

        # Row 1: full-width capability reference so the complete label is visible.
        if hasattr(st, "popover"):
            with st.popover("WHAT CAN QUILL DO?", use_container_width=True):
                st.markdown(
                    """
**Quill can collaborate with you on:**

- Plot direction and alternate story paths
- Character development, motivation, and interaction
- Conflict, tension, stakes, and scene ideas
- Dialogue choices and character voice- Pacing, structure, and scene order
- Continuity and story logic
- Tone, atmosphere, and style
- Twists, reveals, endings, and “what if?” ideas
- Brainstorming from your current manuscript or plot line
- Explaining WritersBlock stages and controls

Quill can discuss and suggest freely, but **you decide what becomes part of the project**.
                    """
                )

        # Row 2: Male/Female centered over the owl area; speaker at far right.
        voice_choices, voice_speaker = st.columns(
            [3.63, 1.87],
            vertical_alignment="center",
        )

        with voice_choices:
            current_gender = str(state.get(VOICE_GENDER_KEY, "Male") or "Male")
            selected_gender = st.radio(
                "Quill Voice",
                ["Male", "Female"],
                index=0 if current_gender == "Male" else 1,
                horizontal=True,
                label_visibility="collapsed",
                key="wbs_quill_voice_gender_v32",
            )
            state[VOICE_GENDER_KEY] = selected_gender

        with voice_speaker:
            voice_enabled = bool(state.get(VOICE_ENABLED_KEY, False))
            speaker_icon = "🔊" if voice_enabled else "🔇"
            if st.button(
                speaker_icon,
                key="wbs_quill_voice_toggle_v32",
                help="Turn Quill voice on or off",
                use_container_width=False,
            ):
                new_voice_state = not voice_enabled
                state[VOICE_ENABLED_KEY] = new_voice_state

                if new_voice_state:
                    state[LAST_SPOKEN_KEY] = str(state.get(LAST_RESPONSE_KEY, "") or "")
                else:
                    state[VOICE_STOP_KEY] = True
                st.rerun()

        if bool(state.get(VOICE_STOP_KEY, False)):
            _browser_stop_speech()
            state[VOICE_STOP_KEY] = False

        # Row 3: collapse control centered directly under the speaker.
        collapse_space, collapse_button = st.columns(
            [3.63, 1.87],
            vertical_alignment="center",
        )
        with collapse_button:
            if st.button(
                ">",
                key="wbs_quill_collapse_v32",
                help="Collapse Quill",
                use_container_width=False,
            ):
                state[COLLAPSED_KEY] = True
                st.rerun()
        # Row 4: Quill mark left, Ask QUILL centered in the remaining header area.
        logo_col, title_col, title_space = st.columns(
            [2.50, 1.20, 1.80],
            vertical_alignment="center",
        )

        with logo_col:
            _render_quill_logo(st, width=118)

        with title_col:
            st.markdown(
                '<div class="wbs-quill-v11-title">Ask QUILL</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="wbs-quill-v11-prompt">What would you like to ask?</div>',
            unsafe_allow_html=True,
        )

        # First-use name introduction stays inside the fixed right-hand Quill panel.
        # Ask once for the name Quill should use, then continue with the personalized welcome.
        if not bool(state.get(NAME_CONFIRMED_KEY, False)):
            st.markdown(
                '<div class="wbs-quill-v11-chat">'
                '<div class="wbs-quill-v11-quill">'
                '<div class="wbs-quill-v11-label">QUILL</div>'
                'Welcome to WritersBlock Studios! I’m Quill. '
                'What name would you like me to use?'
                '</div></div>',
                unsafe_allow_html=True,
            )

            with st.form(
                key=f"{QUILL_STATE_PREFIX}name_intro_form",
                clear_on_submit=False,
            ):
                entered_name = st.text_input(
                    "Your name",
                    value="",
                    placeholder="First name, full name, or pen name",
                    max_chars=60,
                    label_visibility="collapsed",
                )
                name_submitted = st.form_submit_button("CONTINUE")

            if name_submitted:
                chosen_name = _clean(entered_name)
                if not chosen_name:
                    st.warning("Please enter the name you would like Quill to use.")
                else:
                    state[DISPLAY_NAME_KEY] = chosen_name
                    state[NAME_CONFIRMED_KEY] = True
                    state[CHAT_HISTORY_KEY] = []
                    _set_personal_startup_welcome(state, chosen_name)
                    state[LAST_SPOKEN_KEY] = ""
                    st.rerun()

            return None

        # Keep Quill in the right-hand panel after the name introduction.
        active_name = _clean(state.get(DISPLAY_NAME_KEY, "")) or _clean(display_name)
        if not active_name:
            for _name_key in ("writer_name", "preferred_name", "user_name", "full_name", "name"):
                active_name = _clean(state.get(_name_key, ""))
                if active_name:
                    break
        if not active_name:
            for _row_key in ("licensed_user_row", "demo_user_row"):
                _row = state.get(_row_key) or {}
                if isinstance(_row, Mapping):
                    active_name = _clean(
                        _row.get("full_name")
                        or _row.get("name")
                        or _row.get("display_name")
                        or ""
                    )
                    if active_name:
                        break
        if active_name:
            state[DISPLAY_NAME_KEY] = active_name

        history = list(state.get(CHAT_HISTORY_KEY, []) or [])

        # Suppress any duplicate zero-credit title prompt that app.py may add
        # during the same startup rerun; the personalized welcome already says it.
        cleaned_history = []
        for item in history:
            content = _clean(item.get("content", ""))
            source = _clean(item.get("source", ""))
            if (
                source != "startup_welcome"
                and content.lower().startswith("start by giving your story a working title")
            ):
                continue
            cleaned_history.append(item)
        history = cleaned_history
        state[CHAT_HISTORY_KEY] = history

        if not any(_clean(item.get("source", "")) == "startup_welcome" for item in history):
            _set_personal_startup_welcome(state, active_name)
            history = list(state.get(CHAT_HISTORY_KEY, []) or [])

        if history:
            parts = ['<div class="wbs-quill-v11-chat">']
            for message in history:
                role = _clean(message.get("role", ""))
                content = html.escape(_clean(message.get("content", ""))).replace("\n", "<br>")
                if not content:
                    continue

                if role == "user":
                    label = html.escape(active_name or "YOU")
                    parts.append(
                        f'<div class="wbs-quill-v11-user">'
                        f'<div class="wbs-quill-v11-label">{label}</div>{content}</div>'
                    )
                else:
                    parts.append(
                        f'<div class="wbs-quill-v11-quill">'
                        f'<div class="wbs-quill-v11-label">QUILL</div>{content}</div>'
                    )
            parts.append("</div>")
            st.markdown("".join(parts), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="wbs-quill-v11-chat"></div>',
                unsafe_allow_html=True,
            )

        # Auto-read only new Quill responses when the speaker is ON.
        if bool(state.get(VOICE_ENABLED_KEY, False)):
            latest_quill_text = ""
            for message in reversed(history):
                if _clean(message.get("role", "")) == "assistant":
                    latest_quill_text = str(message.get("content", "") or "").strip()
                    break

            if (
                latest_quill_text
                and latest_quill_text != str(state.get(LAST_SPOKEN_KEY, "") or "")
            ):
                # Mark this response before synthesis so a failure does not cause
                # repeated model work on every unrelated Streamlit rerun.
                state[LAST_SPOKEN_KEY] = latest_quill_text
                try:
                    voice_audio = _generate_quill_voice(
                        latest_quill_text,
                        str(state.get(VOICE_GENDER_KEY, "Male") or "Male"),
                    )
                    if voice_audio:
                        state[VOICE_ERROR_KEY] = ""
                        st.audio(
                            voice_audio,
                            format="audio/wav",
                            autoplay=True,
                        )
                except Exception as exc:
                    state[VOICE_ERROR_KEY] = str(exc)

        voice_error = str(state.get(VOICE_ERROR_KEY, "") or "").strip()
        if voice_error and bool(state.get(VOICE_ENABLED_KEY, False)):
            st.caption(f"Quill voice: {voice_error}")

        with st.form(
            key=f"{QUILL_STATE_PREFIX}chat_form",
            clear_on_submit=True,
        ):
            question = st.text_input(
                "Message Quill",
                placeholder="Type your question here… then press Enter",
                max_chars=1000,
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("SEND")

        if submitted and _clean(question):
            user_text = _clean(question)
            history = list(state.get(CHAT_HISTORY_KEY, []) or [])
            history.append({"role": "user", "content": user_text})
            state[CHAT_HISTORY_KEY] = history

            quill_credit_charge = None
            if credit_manager is not None and credit_user_id:
                try:
                    quill_credit_charge = credit_manager.spend(
                        str(credit_user_id),
                        "quill_question",
                        project_id=_clean(state.get("current_project_id", "")) or None,
                        note="Ask Quill",
                    )
                except Exception as exc:
                    st.error(str(exc))
                    st.stop()

            try:
                backend_for_usage = state.get("backend")
                if backend_for_usage is not None and hasattr(backend_for_usage, "last_usage"):
                    backend_for_usage.last_usage = {}

                payload = _revise_existing_quill_concept(state, user_text)
                if payload is None:
                    payload = controller.ask(
                        user_text,
                        project_id=_clean(state.get("current_project_id", "")) or None,
                        project_name=_clean(state.get("project_title", "")) or None,
                    )

                if usage_logger is not None:
                    try:
                        usage_logger(
                            "quill_question",
                            input_text=user_text,
                            output_text=payload.text,
                            note="Ask Quill",
                        )
                    except Exception:
                        pass
            except BaseException:
                if quill_credit_charge is not None:
                    try:
                        credit_manager.refund(
                            str(credit_user_id),
                            quill_credit_charge,
                            note="Quill request failed - automatic refund",
                        )
                    except Exception:
                        pass
                raise

            history.append({"role": "assistant", "content": payload.text})
            state[CHAT_HISTORY_KEY] = history
            state[LAST_RESPONSE_KEY] = payload.text
            state[LAST_SOURCE_KEY] = payload.source
            st.rerun()

    return None


__all__ = [
    "CHAT_HISTORY_KEY",
    "COLLAPSED_KEY",
    "VOICE_ENABLED_KEY",
    "VOICE_GENDER_KEY",
    "VOICE_ERROR_KEY",
    "DISPLAY_NAME_KEY",
    "INTRO_RENDERED_KEY",
    "LAST_RESPONSE_KEY",
    "NAME_CONFIRMED_KEY",
    "PRELUDE_SEEN_KEY",
    "SESSION_INITIALIZED_KEY",
    "QUILL_STATE_PREFIX",
    "QUILL_LOGO_PATH",
    "QUILL_STREAMLIT_UI_VERSION",
    "QuillInterfaceController",
    "QuillUIPayload",
    "build_quill_controller",
    "clear_quill_response",
    "initialize_quill_state",
    "render_quill_studio_coach",
]