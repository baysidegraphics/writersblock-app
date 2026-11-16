"""Disconnected private owner-acceptance screen; staging only.

Reads only the two approved database settings for offline format validation.
No database clients, AI clients or commercial app execution.
The verified 314-file commercial application remains unchanged beside this loader.
"""
from pathlib import Path
import base64
import json

import streamlit as st
from core.authentication import AuthenticationError, public_client_key, validate_endpoint

st.set_page_config(page_title="WBS R2 — Owner Acceptance", page_icon="📚")
st.title("WritersBlock Studios")
st.subheader("R2 — Private Owner Acceptance")
st.success("The staging startup screen is ready.")
st.info("Database access is not enabled. No database connection has been attempted.")
def configuration_categories(url, key):
    """Return fixed categories only. Never return input values or exception text."""
    result = {"SUPABASE_URL": "MISSING", "SUPABASE_KEY": "MISSING", "PROJECT_IDENTITY": "NOT_CHECKED"}
    if url:
        try:
            endpoint = validate_endpoint(url)
            result["SUPABASE_URL"] = "PASS" if endpoint == "https://svikvmuuvqpvndsmnutf.supabase.co" else "WRONG_PROJECT"
        except (AuthenticationError, TypeError, ValueError):
            result["SUPABASE_URL"] = "INVALID_URL_FORMAT"
    if key:
        try:
            public = public_client_key(key)
            result["SUPABASE_KEY"] = "PASS_PUBLIC_KEY_FORMAT"
            if public.startswith("sb_publishable_"):
                result["PROJECT_IDENTITY"] = "OPAQUE_KEY_NOT_VERIFIABLE_OFFLINE"
            else:
                encoded = public.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                reference = claims.get("ref")
                result["PROJECT_IDENTITY"] = (
                    "MATCHING_PROJECT_CLAIM_NOT_SIGNATURE_VERIFIED" if reference == "svikvmuuvqpvndsmnutf"
                    else "WRONG_PROJECT_CLAIM" if reference else "NO_PROJECT_CLAIM"
                )
        except (AuthenticationError, TypeError, ValueError, KeyError):
            result["SUPABASE_KEY"] = "INVALID_OR_PRIVILEGED_KEY_FORMAT"
    return result

try:
    configured_url = st.secrets.get("SUPABASE_URL", "")
    configured_key = st.secrets.get("SUPABASE_KEY", "")
    checks = configuration_categories(configured_url, configured_key)
    for name, category in checks.items():
        st.text(name + ": " + category)
    if checks["SUPABASE_URL"] == "PASS" and checks["SUPABASE_KEY"] == "PASS_PUBLIC_KEY_FORMAT" and checks["PROJECT_IDENTITY"] != "WRONG_PROJECT_CLAIM":
        st.success("WritersBlock Database target and publishable/anon key format checks passed.")
        st.caption("Key validity, provider acceptance and account access are not verified by offline format checks.")
    else:
        st.error("Configuration check failed. Use only the category lines above to identify the correction.")
except (AuthenticationError, KeyError, FileNotFoundError, TypeError, ValueError):
    st.error("SETTINGS_READ: UNAVAILABLE_OR_INVALID. No connection was attempted.")
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
