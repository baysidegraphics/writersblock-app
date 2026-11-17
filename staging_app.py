"""Disconnected private owner-acceptance screen; staging only.

Reads approved database settings and the private default owner email.
Only explicit owner Auth actions connect; no legacy-data or AI operations.
The verified 314-file commercial application remains unchanged beside this loader.
"""
from pathlib import Path
import base64
import json
import os
import httpx

import streamlit as st
from core.authentication import AuthenticationError, AuthController, public_client_key, validate_endpoint, session_controller, field

st.set_page_config(page_title="WBS R2 — Owner Acceptance", page_icon="📚")
st.title("WritersBlock Studios")
st.subheader("R2 — Private Owner Acceptance")
st.success("The staging startup screen is ready.")
st.info("Owner-linked records may be opened read-only. Account linking, editing, saving, deletion, payments and AI requests remain disabled.")
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
st.caption("The previously authorized read-only connection check is complete. No further check will run automatically.")


def confirm_owner_email(auth, email, code):
    """Staging-only confirmation: retain ONLY a server-verified returned session."""
    email = AuthController._registration_email(email)
    auth.sign_out()
    try:
        response = auth._client.auth.verify_otp({"email": email, "token": str(code or "").strip(), "type": "signup"})
        if field(response, "session") is None:
            user = field(response, "user")
            if not field(user, "email_confirmed_at") or str(field(user, "email", "")).strip().lower() != email:
                raise AuthenticationError()
            # Confirmation succeeded but supplied no usable login session.
            # The only available continuation is normal password sign-in.
            auth.sign_out()
            return False
        # Reuse the commercial token/session comparison and authenticated
        # get_user verification; this also checks confirmed email and owner.
        auth._accept_signin(response, email)
        return True
    except Exception:
        auth.sign_out()
        raise AuthenticationError("Email confirmation could not be verified. No signed-in access was granted.") from None


def readonly_owner_rows(auth, owner_email, table, project_id=None, row_id=None):
    """SELECT-only facade over the unchanged JWT/ownership boundary."""
    from core.persistence import OwnedClient, OwnershipError
    columns = {
        "writersblock_projects": "id,project_title,project_type,current_stage,project_status",
        "writersblock_project_drafts": "id,project_id,draft_title,draft_type,version_number,updated_at",
        "writersblock_manuscript_versions": "id,project_id,version_number,version_label,source_stage,created_at",
    }
    if table not in columns:
        raise OwnershipError("Unapproved read-only table")
    if table != "writersblock_projects" and not project_id:
        raise OwnershipError("Selected project required")
    if row_id:
        columns["writersblock_project_drafts"] += ",draft_content"
        columns["writersblock_manuscript_versions"] += ",manuscript_content"
    def verified_read_owner():
        account = auth.refresh_account()  # Auth get_user + read-only mapped-account RPC.
        if auth.email != owner_email or str(account.get("id", "")) != str(auth.owner_id or ""):
            raise OwnershipError("Read-only identity binding unavailable")
        return auth.owner_id
    verified_read_owner()
    # Read review does not grant a paid writing entitlement or alter the commercial
    # controller's license callback. RLS and refreshed mapping still enforce ownership.
    boundary = OwnedClient(auth._client, lambda: auth.owner_id, authorize=verified_read_owner)
    rows = []
    for start in range(0, 10000, 200):
        query = boundary.table(table).select(columns[table])
        if project_id:
            query = query.eq("project_id", str(project_id))
        if row_id:
            query = query.eq("id", str(row_id))
        page = query.order("id").range(start, start + 199).execute().data or []
        rows.extend(page)
        if row_id or len(page) < 200:
            return rows
    raise OwnershipError("Read-only listing is too large; no partial-list claim")


def render_readonly_owner_view(auth, owner_email):
    st.subheader("Existing account and writing — read only")
    st.caption("Only your linked records are read. Editing, saving, deletion, AI and payment controls are unavailable.")
    subject = auth.subject
    if st.session_state.get("_r2_readonly_subject") != subject:
        st.session_state["_r2_readonly_subject"] = subject
        st.session_state["_r2_readonly_open"] = False
    if not st.session_state.get("_r2_readonly_open"):
        if st.button("Open my linked account — read only", key="r2_open_linked_readonly"):
            st.session_state["_r2_readonly_open"] = True
            st.rerun()
        return
    try:
        projects = readonly_owner_rows(auth, owner_email, "writersblock_projects")
        st.success("Linked owner access verified. Read-only ownership filters are active.")
        if not projects:
            st.info("No projects are saved under this linked account. No other legacy account will be substituted.")
            return
        index = st.selectbox("Saved project", range(len(projects)),
            format_func=lambda i: str(projects[i].get("project_title") or "Untitled project") + " · " + str(i + 1),
            key="r2_readonly_project_choice")
        project = projects[index]
        st.caption(str(project.get("project_type") or "Saved writing format"))
        for table, label, content_key in (
            ("writersblock_project_drafts", "Saved drafts", "draft_content"),
            ("writersblock_manuscript_versions", "Saved manuscript versions", "manuscript_content"),
        ):
            st.markdown("**" + label + "**")
            records = readonly_owner_rows(auth, owner_email, table, project["id"])
            if not records:
                st.info("No " + label.lower() + " are saved for this project.")
                continue
            choice = st.selectbox(label, range(len(records)),
                format_func=lambda i, items=records: "V" + str(items[i].get("version_number", ""))
                    + " — " + str(items[i].get("draft_title") or items[i].get("version_label") or "Saved record")
                    + " · " + str(i + 1),
                key="r2_readonly_" + table + "_" + str(project["id"]))
            selected = records[choice]
            content = readonly_owner_rows(auth, owner_email, table, project["id"], selected["id"])
            if len(content) != 1:
                raise AuthenticationError()
            st.caption("Original saved text. Project-session snapshots may contain structured JSON; no text is regenerated or rewritten.")
            st.text(str(content[0].get(content_key) or ""))
    except Exception:
        st.session_state["_r2_readonly_open"] = False
        st.error("READ_ONLY_ACCESS_UNAVAILABLE: No records were changed. Verify the current session and owner mapping; no other account will be used.")


def render_owner_registration():
    """Private staging only; reuse approved Auth, never call a legacy-data RPC."""
    try:
        owner_email = AuthController._registration_email(st.secrets.get("WBS_OWNER_EMAIL", ""))
    except (AuthenticationError, KeyError, FileNotFoundError, TypeError, ValueError):
        st.warning("OWNER_EMAIL_SETUP_REQUIRED: Set the private staging WBS_OWNER_EMAIL value. Registration remains disabled.")
        return
    try:
        endpoint = validate_endpoint(st.secrets.get("SUPABASE_URL", ""))
        if endpoint != "https://svikvmuuvqpvndsmnutf.supabase.co":
            raise AuthenticationError()
        auth = session_controller(st.session_state, endpoint, st.secrets.get("SUPABASE_KEY", ""))
    except (AuthenticationError, KeyError, FileNotFoundError, TypeError, ValueError):
        st.error("Owner authentication configuration is unavailable. No registration was attempted.")
        return

    # Widget state is private to this browser session. Clear sensitive fields before
    # rebuilding widgets, as in the approved commercial authentication UI.
    if st.session_state.pop("_r2_owner_clear_sensitive", False):
        for name in ("r2_owner_password", "r2_owner_password_again", "r2_owner_code", "r2_owner_login_password"):
            st.session_state.pop(name, None)
    notice = st.session_state.pop("_r2_owner_notice", None)
    if notice:
        (st.error if notice[0] else st.success)(notice[1])
    # Configuration changes cannot reuse a registration/session belonging to a
    # different owner. No email literal is stored in public source or logs.
    previous_owner = st.session_state.get("_r2_owner_configured_email")
    if previous_owner is not None and previous_owner != owner_email:
        auth.sign_out()
        st.error("Owner configuration changed. Open a fresh private session before continuing.")
        return
    st.session_state["_r2_owner_configured_email"] = owner_email
    st.subheader("Owner access")
    st.caption("Register → Confirm Email → Signed In. No legacy account link or entitlement change is performed.")
    if auth.subject:
        try:
            auth.verify()
            if auth.email != owner_email:
                auth.sign_out()
                raise AuthenticationError()
            st.session_state["_r2_owner_phase"] = "signed_in"
            st.success("Signed In — owner identity verified. Account linking remains disabled.")
            st.caption("Your verified session is reused on ordinary reruns. Logout or an unusable/expired session requires sign-in again.")
            if st.session_state.get('_r2_interface_subject') != auth.subject:
                st.session_state['_r2_interface_subject'] = auth.subject
                st.session_state['_r2_interface_open'] = False
            if st.session_state.get('_r2_interface_open'):
                st.warning('PRIVATE READ-ONLY ACCEPTANCE: Saving, approval, deletion, AI, voice generation and payments are disabled. No changes are saved.')
                if st.button('Back to read-only account', key='r2_close_interface'):
                    st.session_state['_r2_interface_open'] = False
                    st.rerun()
                from staging_owner_interface import run_interface, AcceptanceBlocked
                try:
                    run_interface(st, auth, owner_email, Path(__file__).resolve().with_name('app.py'))
                except AcceptanceBlocked:
                    st.error('ACCEPTANCE_ACTION_BLOCKED: This operation requires separate authorization. No database write or provider request was sent.')
                except Exception:
                    st.error('ACCEPTANCE_INTERFACE_UNAVAILABLE: Return to the read-only account. No permissions were expanded.')
                st.stop()
            if st.button('Open commercial interface — read-only acceptance', key='r2_open_interface'):
                st.session_state['_r2_interface_open'] = True
                st.rerun()
            render_readonly_owner_view(auth, owner_email)
            if st.button("Sign out", key="r2_owner_sign_out"):
                auth.sign_out()
                st.session_state["_r2_owner_phase"] = "signin"
                st.rerun()
            return
        except AuthenticationError:
            st.session_state["_r2_owner_phase"] = "signin"
            st.warning("Your Auth session is unavailable or expired. Sign in again; it will not be bypassed.")

    receipt = Path.home() / ".cache" / "wbs" / "owner-acceptance" / "single-owner-registration-20261116.json"
    phase = st.session_state.get("_r2_owner_phase", "confirm" if receipt.exists() else "register")
    if phase == "signed_in":
        phase = "signin"
    if phase == "register":
        st.markdown("**1. Register**")
        with st.form("r2_owner_registration_form", clear_on_submit=True):
            st.text_input("Owner email", value=owner_email, disabled=True, key="r2_owner_registration_email")
            password = st.text_input("Create password (at least 12 characters)", type="password", key="r2_owner_password")
            repeated = st.text_input("Confirm password", type="password", key="r2_owner_password_again")
            register = st.form_submit_button("Register owner once", disabled=receipt.exists())
        if register:
            try:
                if password != repeated:
                    raise AuthenticationError("The passwords do not match.")
                AuthController._new_password(password)
                receipt.parent.mkdir(parents=True, exist_ok=True)
                with receipt.open("x", encoding="utf-8") as handle:
                    json.dump({"state": "owner_signup_attempt_started"}, handle)
                auth.register_password(owner_email, password)
                st.session_state["_r2_owner_phase"] = "confirm"
                st.session_state["_r2_owner_notice"] = (False, "Registration submitted. Enter the email confirmation code below.")
            except FileExistsError:
                st.session_state["_r2_owner_notice"] = (True, "The authorized registration attempt is already recorded. Do not repeat signup.")
            except AuthenticationError as error:
                st.session_state["_r2_owner_notice"] = (True, str(error))
            except OSError:
                st.session_state["_r2_owner_notice"] = (True, "The registration receipt could not be secured. Registration was not started.")
            finally:
                st.session_state["_r2_owner_clear_sensitive"] = True
            st.rerun()
        if st.button("Already registered? Sign in", key="r2_owner_existing_login"):
            st.session_state["_r2_owner_phase"] = "signin"
            st.rerun()
    elif phase == "confirm":
        st.markdown("**2. Confirm Email**")
        with st.form("r2_owner_confirmation_form", clear_on_submit=True):
            st.text_input("Registration email", value=owner_email, disabled=True, key="r2_owner_confirmation_email")
            code = st.text_input("Email confirmation code", type="password", key="r2_owner_code")
            confirm = st.form_submit_button("Confirm owner email")
        if confirm:
            try:
                signed_in = confirm_owner_email(auth, owner_email, code)
                st.session_state["_r2_owner_phase"] = "signed_in" if signed_in else "signin"
                st.session_state["_r2_owner_notice"] = (False, "Email confirmed. Owner session verified." if signed_in else "Email confirmed. No usable session was returned; sign in with your password.")
            except AuthenticationError as error:
                st.session_state["_r2_owner_notice"] = (True, str(error))
            finally:
                st.session_state["_r2_owner_clear_sensitive"] = True
            st.rerun()
        if st.button("Already confirmed? Sign in", key="r2_owner_confirmed_login"):
            st.session_state["_r2_owner_phase"] = "signin"
            st.rerun()
    else:
        st.markdown("**Sign in**")
        with st.form("r2_owner_password_login_form", clear_on_submit=True):
            st.text_input("Sign-in email", value=owner_email, disabled=True, key="r2_owner_login_email")
            login_password = st.text_input("Password", type="password", key="r2_owner_login_password")
            login = st.form_submit_button("Sign in as owner")
        if login:
            try:
                auth.sign_in_password(owner_email, login_password)
                st.session_state["_r2_owner_phase"] = "signed_in"
                st.session_state["_r2_owner_notice"] = (False, "Owner signed in. Existing account linking remains disabled.")
            except AuthenticationError as error:
                st.session_state["_r2_owner_notice"] = (True, str(error))
            finally:
                st.session_state["_r2_owner_clear_sensitive"] = True
            st.rerun()


render_owner_registration()
st.write(
    "Your commercial application files and all legacy accounts remain unchanged. "
    "Only explicitly opened owner-linked records may be viewed. Account linking, editing, saving and AI requests remain unavailable."
)
if not Path(__file__).resolve().with_name("app.py").is_file():
    st.error("The commercial entrypoint is missing. Do not proceed with acceptance.")
st.caption("This is a readiness screen, not the running writing application. Do not request another check after a hosting restart.")
st.stop()
