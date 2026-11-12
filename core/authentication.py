"""Per-browser-session Supabase Auth boundary. Never trusts licensed-email state.

Existing writing user_id values are deliberately preserved. A protected database
mapping links a verified Auth UUID to the existing account id.
"""
import base64
from copy import deepcopy
import json
import hashlib
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
        self._disabled=True
        try:
            response=self._client.auth.sign_in_with_password({'email':email.strip().lower(),'password':password})
            self._accept_signin(response,email)
        except Exception:
            self._clear_identity()
            self._disabled=True
            raise AuthenticationError('Sign-in failed. Check your credentials and confirmed email.') from None

    def request_email_code(self,email):
        try:
            self._client.auth.sign_in_with_otp({'email':email.strip().lower(),'options':{'should_create_user':True}})
        except Exception:
            raise AuthenticationError('The sign-in email could not be sent. Please retry later.') from None

    def verify_email_code(self,email,code):
        self._clear_identity()
        self._disabled=True
        try:
            response=self._client.auth.verify_otp({'email':email.strip().lower(),'token':code.strip(),'type':'email'})
            self._accept_signin(response,email)
        except Exception:
            self._clear_identity()
            self._disabled=True
            raise AuthenticationError('The sign-in code is invalid or expired.') from None

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
