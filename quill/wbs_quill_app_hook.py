"""
WritersBlock Studios
Quill App Hook
Version: 1.0

Purpose
-------
Single safe entry point used by app.py to display Quill inside every
WritersBlock workflow stage.

The hook:
- uses the existing WritersBlock Studio Agent when it can start successfully,
- caches that agent for the Streamlit session/process,
- falls back to deterministic Quill stage coaching if the agent is unavailable,
- never blocks the existing WritersBlock workflow,
- writes only _wbs_quill_* session keys.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Optional

QUILL_APP_HOOK_VERSION = "1.0"

QUILL_DIR = Path(__file__).resolve().parent
WBS_AGENT_DIR = QUILL_DIR.parent
if str(WBS_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(WBS_AGENT_DIR))

try:
    from .wbs_quill_streamlit_ui import render_quill_studio_coach
except ImportError:
    from wbs_quill_streamlit_ui import render_quill_studio_coach

_AGENT_CACHE: Any = None
_AGENT_START_ATTEMPTED = False
_AGENT_START_ERROR = ""


def _start_wbs_agent_once() -> Optional[Any]:
    """Start the real WritersBlock Studio Agent once; fail safely if unavailable."""
    global _AGENT_CACHE, _AGENT_START_ATTEMPTED, _AGENT_START_ERROR

    if _AGENT_CACHE is not None:
        return _AGENT_CACHE
    if _AGENT_START_ATTEMPTED:
        return None

    _AGENT_START_ATTEMPTED = True

    try:
        from wbs_agent import start_wbs_agent  # type: ignore

        agent = start_wbs_agent()
        if not getattr(agent, "ready", False):
            _AGENT_START_ERROR = "WritersBlock Studio Agent did not report READY."
            return None

        _AGENT_CACHE = agent
        return agent
    except Exception as exc:  # Quill UI must never stop the working WBS app.
        _AGENT_START_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def get_quill_agent_status() -> dict[str, Any]:
    """Small diagnostic helper for tests/support; not displayed in normal UI."""
    return {
        "attempted": _AGENT_START_ATTEMPTED,
        "connected": _AGENT_CACHE is not None,
        "error": _AGENT_START_ERROR,
        "version": QUILL_APP_HOOK_VERSION,
    }


def render_quill_for_current_stage(
    *,
    st_module: Any = None,
    display_name: str = "",
    show_prelude: bool = True,
) -> Any:
    """Render Quill for the active WritersBlock stage.

    Safe to call once from render_project_title_banner(...). If the full
    WritersBlock Studio Agent cannot start, the Quill interface still works
    using the deterministic decision/stage coaching layer.
    """
    if st_module is None:
        import streamlit as st_module  # type: ignore

    agent = _start_wbs_agent_once()

    try:
        return render_quill_studio_coach(
            agent=agent,
            display_name=display_name,
            st_module=st_module,
            show_prelude=show_prelude,
        )
    except Exception as exc:
        # Never allow Quill to break the existing WritersBlock application.
        try:
            st_module.session_state["_wbs_quill_hook_error"] = (
                f"{type(exc).__name__}: {exc}"
            )
        except Exception:
            pass
        return None


__all__ = [
    "QUILL_APP_HOOK_VERSION",
    "get_quill_agent_status",
    "render_quill_for_current_stage",
]
