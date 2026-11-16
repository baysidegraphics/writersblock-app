"""Per-browser-session Supabase Auth boundary. Never trusts licensed-email state.

Existing writing user_id values are deliberately preserved. A protected database
mapping links a verified Auth UUID to the existing account id.
"""
import base64
from copy import deepcopy
import json
import hashlib
import re
import time
from uuid import UUID
from urllib.parse import urlsplit


class AuthenticationError(PermissionError):
    pass


def public_client_key(key):
    """Reject service/secret keys before constructing any client; no secret logging."""
    value=str(key or '').strip()
    if value.startswith('sb_publishable_') and len(value)>20:
        return value
    try:
        parts=value.split('.')
        if len(parts)!=3: raise ValueError()
        payload=json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
        if payload.get('role')!='anon': raise ValueError()
    except Exception:
        raise AuthenticationError('A Supabase publishable or legacy anon key is required; privileged keys are forbidden.') from None
    return value


def validate_endpoint(url):
    parsed=urlsplit(str(url))
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise AuthenticationError('Invalid Supabase endpoint configuration.')
    if not parsed.hostname or (parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1'))):
        raise AuthenticationError('Supabase requires HTTPS except for local staging.')
    return str(url).rstrip('/')


def field(value, name, default=None):
    return value.get(name,default) if isinstance(value,dict) else getattr(value,name,default)


class AuthController:
    """SDK client belongs to exactly one Streamlit session, never a global cache."""
    def __init__(self, client):
        self._client=client
        self._subject=None
        self._owner=None
        self._account=None
        self._email=None
        self.access_check=None
        self._disabled=False
        self._recovery_subject=None
        self._recovery_email=None
        self._recovery_started=None

    @property
    def owner_id(self): return self._owner

    @property
    def subject(self): return self._subject

    @property
    def email(self): return self._email

    @property
    def account(self): return deepcopy(self._account)

    def _clear_identity(self):
        self._subject=self._owner=self._account=self._email=None

    def _clear_recovery(self):
        self._recovery_subject=self._recovery_email=self._recovery_started=None

    @staticmethod
    def _registration_email(email):
        value=str(email or '').strip().lower()
        if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise AuthenticationError('Enter a valid email address.')
        return value

    @staticmethod
    def _new_password(password):
        if not isinstance(password,str) or len(password)<12 or not password.strip():
            raise AuthenticationError('Choose a password of at least 12 characters.')
        return password  # Never trim, log or store a customer's password.

    def verify(self):
        """Refresh through the SDK, then validate the bearer at the Auth server.

        get_session's locally stored user/claims are NEVER used as identity.
        """
        try:
            if self._disabled: raise AuthenticationError()
            session=self._client.auth.get_session()
            token=field(session,'access_token')
            if not token: raise AuthenticationError()
            user=field(self._client.auth.get_user(token),'user')
            subject=str(UUID(str(field(user,'id'))))
            if not field(user,'email_confirmed_at') or not field(user,'email'):
                raise AuthenticationError()
            if self._subject and self._subject!=subject:
                raise AuthenticationError()
            # Ensure a query built after this check uses this exact user bearer,
            # even when get_session refreshed/replaced the SDK PostgREST client.
            self._client.postgrest.auth(token)
            self._subject=subject
            self._email=str(field(user,'email')).strip().lower()
            return subject
        except Exception:
            self._clear_identity()
            self._disabled=True
            raise AuthenticationError('Sign in with a confirmed account to continue.') from None

    def refresh_account(self):
        subject=self.verify()
        try:
            result=self._client.rpc('wbs_authenticated_account').execute().data
            if not isinstance(result,dict) or result.get('auth_subject')!=subject:
                raise AuthenticationError()
            row=result.get('account')
            if not isinstance(row,dict) or row.get('id') is None:
                raise AuthenticationError()
            if str(result.get('owner_id'))!=str(row['id']):
                raise AuthenticationError()
            self._owner=row['id']
            self._account=deepcopy(row)
            return self.account
        except Exception:
            self._owner=self._account=None
            raise AuthenticationError('Account access is unavailable. Existing accounts must be securely linked before use.') from None

    def require_owner(self):
        row=self.refresh_account()
        if self.access_check is None or not self.access_check(row):
            raise AuthenticationError('An active license or valid trial is required.')
        return self._owner

    def _accept_signin(self,response,email):
        issued=field(field(response,'session'),'access_token')
        current=field(self._client.auth.get_session(),'access_token')
        if not issued or issued!=current:
            raise AuthenticationError()
        self._disabled=False
        self.verify()
        if self.email!=str(email).strip().lower():
            raise AuthenticationError()

    def sign_in_password(self,email,password):
        self._clear_identity()
        self._clear_recovery()
        self._disabled=True
        try:
            response=self._client.auth.sign_in_with_password({'email':email.strip().lower(),'password':password})
            self._accept_signin(response,email)
        except Exception:
            self._clear_identity()
            self._disabled=True
            raise AuthenticationError('Sign-in failed. Check your credentials and confirmed email.') from None

    def register_password(self,email,password):
        email=self._registration_email(email)
        password=self._new_password(password)
        self.sign_out()
        try:
            response=self._client.auth.sign_up({'email':email,'password':password})
            # Fail closed if the host has disabled confirmation: registration
            # must not silently become an authenticated customer workspace.
            if field(response,'session') is not None:
                self.sign_out()
                raise AuthenticationError('Registration requires email confirmation to be enabled.')
        except AuthenticationError:
            raise
        except Exception:
            self.sign_out()
            raise AuthenticationError('Registration could not be completed. Please try again later.') from None

    def resend_confirmation(self,email):
        email=self._registration_email(email)
        try:
            self._client.auth.resend({'type':'signup','email':email})
        except Exception:
            raise AuthenticationError('The confirmation email could not be sent. Please try again later.') from None

    def confirm_registration(self,email,code):
        email=self._registration_email(email)
        self.sign_out()
        try:
            response=self._client.auth.verify_otp({'email':email,'token':str(code or '').strip(),'type':'signup'})
            self._accept_signin(response,email)
        except Exception:
            raise AuthenticationError('The confirmation code is invalid or expired.') from None
        finally:
            # Confirmation proves email ownership; password login is still
            # required. No account link, license or trial is created here.
            self.sign_out()

    def request_password_recovery(self,email):
        email=self._registration_email(email)
        self.sign_out()
        try:
            self._client.auth.reset_password_email(email)
        except Exception:
            raise AuthenticationError('The recovery email could not be sent. Please try again later.') from None

    def verify_recovery_code(self,email,code):
        email=self._registration_email(email)
        self.sign_out()
        try:
            response=self._client.auth.verify_otp({'email':email,'token':str(code or '').strip(),'type':'recovery'})
            issued=field(field(response,'session'),'access_token')
            if not issued or issued!=field(self._client.auth.get_session(),'access_token'):
                raise AuthenticationError()
            user=field(self._client.auth.get_user(issued),'user')
            subject=str(UUID(str(field(user,'id'))))
            if not field(user,'email_confirmed_at') or str(field(user,'email') or '').strip().lower()!=email:
                raise AuthenticationError()
            self._recovery_subject=subject
            self._recovery_email=email
            self._recovery_started=time.monotonic()
            # Recovery tokens can only change the password through this flow.
            # The normal owner/data boundary remains disabled throughout.
            self._disabled=True
        except Exception:
            self.sign_out()
            raise AuthenticationError('The recovery code is invalid or expired.') from None

    @property
    def recovery_pending(self):
        return self._recovery_subject is not None

    def complete_password_recovery(self,password):
        password=self._new_password(password)
        try:
            if (not self._recovery_subject or self._recovery_started is None
                    or not 0<=time.monotonic()-self._recovery_started<600):
                raise AuthenticationError()
            token=field(self._client.auth.get_session(),'access_token')
            user=field(self._client.auth.get_user(token),'user') if token else None
            if (str(field(user,'id'))!=self._recovery_subject
                    or str(field(user,'email') or '').strip().lower()!=self._recovery_email
                    or not field(user,'email_confirmed_at')):
                raise AuthenticationError()
            result=self._client.auth.update_user({'password':password})
            if str(field(field(result,'user'),'id'))!=self._recovery_subject:
                raise AuthenticationError()
        except Exception:
            self.sign_out()
            raise AuthenticationError('The password reset could not be confirmed. Request a new recovery code or try signing in.') from None
        try:
            self._client.auth.sign_out({'scope':'global'})
        except Exception:
            self.sign_out()
            raise AuthenticationError('Your password was updated, but other sessions could not be signed out. Sign in again and contact support.') from None
        finally:
            self._clear_identity()
            self._clear_recovery()
            self._disabled=True

    def start_trial(self,email):
        self.verify()
        if str(email or '').strip().lower()!=self.email:
            raise AuthenticationError('Use the confirmed signed-in email for account access.')
        try:
            self._client.rpc('wbs_start_trial').execute()
            return self.refresh_account()
        except Exception:
            raise AuthenticationError('Trial access is unavailable. Existing accounts require their approved account link.') from None

    def sign_out(self):
        try:
            self._client.auth.sign_out({'scope':'local'})
        except Exception:
            # UI still discards this controller/client and all browser state.
            pass
        finally:
            self._clear_identity()
            self._clear_recovery()
            self._disabled=True

    def owned_client(self, observer=None, checkpoint_state=None):
        from core.persistence import OwnedClient
        return OwnedClient(self._client,lambda:self.owner_id,observer,authorize=self.require_owner,checkpoint_state=checkpoint_state)


def session_controller(state,url,key,factory=None):
    """Construct only from an explicitly public key, with private memory storage."""
    url=validate_endpoint(url)
    key=public_client_key(key)
    fingerprint=hashlib.sha256((url+'\0'+key).encode()).hexdigest()
    existing=state.get('_wbs_auth_controller')
    if existing is not None:
        if not isinstance(existing,AuthController):
            raise AuthenticationError('Invalid authentication session. Sign in again.')
        if getattr(existing,'_configuration',None)!=fingerprint:
            existing.sign_out()
            raise AuthenticationError('Authentication configuration changed. Open a new session to sign in.')
        return existing
    if factory is None:
        from supabase import create_client, ClientOptions
        try:
            client=create_client(url,key,options=ClientOptions(auto_refresh_token=False,persist_session=True))
        except Exception:
            raise AuthenticationError('Supabase authentication could not be initialized.') from None
    else:
        client=factory(url,key)
    controller=AuthController(client)
    controller._configuration=fingerprint
    state['_wbs_auth_controller']=controller
    return controller
