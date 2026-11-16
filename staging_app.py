"""Disconnected private owner-acceptance screen; staging only.

Reads only the two approved database settings for offline format validation.
No database clients, AI clients or commercial app execution.
The verified 314-file commercial application remains unchanged beside this loader.
"""
from pathlib import Path

import streamlit as st
from core.authentication import AuthenticationError, public_client_key, validate_endpoint

st.set_page_config(page_title="WBS R2 — Owner Acceptance", page_icon="📚")
st.title("WritersBlock Studios")
st.subheader("R2 — Private Owner Acceptance")
st.success("The staging startup screen is ready.")
st.info("Database access is not enabled. No database connection has been attempted.")
try:
    configured_url = st.secrets.get("SUPABASE_URL", "")
    configured_key = st.secrets.get("SUPABASE_KEY", "")
    if not configured_url or not configured_key:
        st.warning("Database configuration is incomplete. Registration remains disabled.")
    elif validate_endpoint(configured_url) != "https://svikvmuuvqpvndsmnutf.supabase.co":
        st.error("Database target does not match WritersBlock Database. Registration remains disabled.")
    else:
        public_client_key(configured_key)
        st.success("WritersBlock Database target and publishable/anon key format checks passed.")
        st.caption("These are offline configuration checks. Provider acceptance and account access have not been tested.")
except (AuthenticationError, KeyError, FileNotFoundError, TypeError, ValueError):
    st.error("Database configuration could not be validated safely. No connection was attempted.")
finally:
    # Do not keep references in the module's returned run state or UI diagnostics.
    configured_url = configured_key = None
st.write(
    "Your commercial application files remain unchanged. Registration, account linking, "
    "manuscript access, saving and AI requests remain unavailable until database access "
    "is separately approved and configured."
)
if not Path(__file__).resolve().with_name("app.py").is_file():
    st.error("The commercial entrypoint is missing. Do not proceed with acceptance.")
st.caption("This is a disconnected readiness screen, not the running writing application.")
st.stop()
