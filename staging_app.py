"""Disconnected private owner-acceptance screen; staging only.

Reads only the two approved database settings for offline format validation.
No database clients, AI clients or commercial app execution.
The verified 314-file commercial application remains unchanged beside this loader.
"""
from pathlib import Path
import base64
import json
import os
import httpx

import streamlit as st
from core.authentication import AuthenticationError, public_client_key, validate_endpoint

st.set_page_config(page_title="WBS R2 — Owner Acceptance", page_icon="📚")
st.title("WritersBlock Studios")
st.subheader("R2 — Private Owner Acceptance")
st.success("The staging startup screen is ready.")
st.info("Customer-data access, registration, linking, saving and AI requests remain disabled.")
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


def run_readonly_auth_check(url, key, receipt_directory, client_factory=None):
    """One approved GET; persist attempt before sending, never read a response body."""
    try:
        checks = configuration_categories(url, key)
        if checks["SUPABASE_URL"] != "PASS" or checks["SUPABASE_KEY"] != "PASS_PUBLIC_KEY_FORMAT" or checks["PROJECT_IDENTITY"] == "WRONG_PROJECT_CLAIM":
            return {"http_status": None, "category": "CONFIGURATION_NOT_READY"}
        endpoint = validate_endpoint(url) + "/auth/v1/settings"
        public = public_client_key(key)
        directory = Path(receipt_directory)
        directory.mkdir(parents=True, exist_ok=True)
        receipt = directory / "r2-authorized-auth-settings-one-get-20261116.json"
        try:
            descriptor = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                stored = json.loads(receipt.read_text(encoding="utf-8"))
                return {"http_status": stored.get("http_status"), "category": stored.get("category", "ATTEMPT_ALREADY_CONSUMED")}
            except (OSError, ValueError):
                return {"http_status": None, "category": "ATTEMPT_ALREADY_CONSUMED"}
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"http_status": None, "category": "ATTEMPT_STARTED_NO_RESULT"}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        result = {"http_status": None, "category": "CONNECTION_FAILED_NO_RETRY"}
        try:
            factory = client_factory or httpx.Client
            with factory(timeout=15.0, follow_redirects=False, transport=httpx.HTTPTransport(retries=0)) as client:
                with client.stream("GET", endpoint, headers={"apikey": public}) as response:
                    status = int(response.status_code)
                    category = (
                        "AUTH_SETTINGS_REACHABLE_KEY_ACCEPTED" if status == 200
                        else "KEY_REJECTED" if status == 401
                        else "ACCESS_DENIED" if status == 403
                        else "REDIRECT_REFUSED" if 300 <= status < 400
                        else "RATE_LIMITED_NO_RETRY" if status == 429
                        else "SERVICE_ERROR_NO_RETRY" if status >= 500
                        else "HTTP_ERROR_NO_RETRY"
                    )
                    result = {"http_status": status, "category": category}
        except (httpx.HTTPError, OSError, ValueError):
            pass
        # Only status/category persist. No key, headers, body or exception text.
        receipt.write_text(json.dumps(result), encoding="utf-8")
        return result
    except (AuthenticationError, OSError, TypeError, ValueError):
        return {"http_status": None, "category": "CHECK_NOT_STARTED_LOCAL_ERROR"}

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
st.caption("One read-only Auth settings check is owner-authorized. It does not start the writing application.")
if st.button("Run approved read-only connection check", key="r2_single_auth_settings_check"):
    result = run_readonly_auth_check(
        st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", ""),
        Path.home() / ".cache" / "wbs" / "owner-acceptance",
    )
    st.session_state["r2_auth_settings_safe_result"] = result
if "r2_auth_settings_safe_result" in st.session_state:
    safe_result = st.session_state["r2_auth_settings_safe_result"]
    st.text("HTTP_STATUS: " + str(safe_result["http_status"]))
    st.text("RESULT_CATEGORY: " + safe_result["category"])
st.write(
    "Your commercial application files remain unchanged. Registration, account linking, "
    "manuscript access, saving and AI requests remain unavailable until database access "
    "is separately approved and configured."
)
if not Path(__file__).resolve().with_name("app.py").is_file():
    st.error("The commercial entrypoint is missing. Do not proceed with acceptance.")
st.caption("This is a readiness screen, not the running writing application. Do not request another check after a hosting restart.")
st.stop()
