"""Existing staging only: real commercial backend, synthetic persistence, two-call gate."""
import inspect, json, os, threading
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from google import genai
from google.genai import types
from google.genai.client import Client as SDK_CLIENT
LOCK=threading.Lock()
AUTHORIZATION='wbs-final-live-20261115'

def operation():
    for frame in inspect.stack(context=0):
        module=str(frame.frame.f_globals.get('__name__',''))
        if module in ('quill.provider','core.extended_quill'):return 'quill'
        if module=='engine.scenes' or (module.startswith('formats.') and module.endswith('.scene_scripting')):return 'scene'
    raise PermissionError('Only the approved normal-interface scene and Quill requests are enabled.')

class LimitedModels:
    def __init__(self,models,folder):self._models=models;self._folder=folder
    def generate_content(self,*,model,contents,config=None,**extra):
        kind=operation()
        if model!='gemini-2.5-flash' or extra or not isinstance(contents,str) or len(contents.encode('utf-8'))>64000:
            raise PermissionError('Live acceptance request exceeds its approved scope or input limit.')
        # Fail before any request if quota was already used, including a failed request.
        with LOCK:
            self._folder.mkdir(parents=True,exist_ok=True)
            try:
                with (self._folder/(AUTHORIZATION+'-'+kind+'.json')).open('x',encoding='utf-8') as receipt:
                    json.dump({'operation':kind,'attempt_consumed':True,'utc':datetime.now(timezone.utc).isoformat()},receipt)
            except FileExistsError:raise PermissionError('This live acceptance request allowance was already consumed.') from None
        bounded=types.GenerateContentConfig(max_output_tokens=1024,thinking_config=types.ThinkingConfig(thinking_budget=0),http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)))
        if config is not None:
            bounded.temperature=getattr(config,'temperature',None)
            bounded.system_instruction=getattr(config,'system_instruction',None)
        try:
            result=self._models.generate_content(model=model,contents=contents,config=bounded)
        except Exception as error:
            from quill.provider_errors import safe_error_summary
            diagnostic={'operation':kind,'attempt_consumed':True,'status':'FAIL',**safe_error_summary(error)}
            (self._folder/(AUTHORIZATION+'-'+kind+'.json')).write_text(json.dumps(diagnostic),encoding='utf-8')
            print('WBS_LIVE_AI_DIAGNOSTIC '+json.dumps(diagnostic),flush=True)
            raise
        # Record response shape only, never generated prose, prompts or credentials.
        diagnostic={'operation':kind,'attempt_consumed':True,'status':'RESPONSE_RECEIVED',
                    'has_text':bool(str(getattr(result,'text','') or '').strip())}
        (self._folder/(AUTHORIZATION+'-'+kind+'.json')).write_text(json.dumps(diagnostic),encoding='utf-8')
        return result

def backend(state,secrets):
    key=str(secrets.get('GEMINI_API_KEY','') or '').strip()
    if not key:raise ValueError('Set GEMINI_API_KEY in this staging app: Manage app > Settings > Secrets. Never send it in chat.')
    # Exact protected server setting only: no environment/parent credential discovery.
    from core.runtime_startup import customer_backend
    scratch=state.setdefault('_wbs_acceptance_backend_state',{})
    folder=Path.home()/'.cache'/'wbs'/'live-acceptance'
    def factory(**kwargs):
        from google.genai.client import Client as real_sdk_client
        client=real_sdk_client(api_key=kwargs['api_key'],vertexai=False,http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1),timeout=30000))
        return SimpleNamespace(models=LimitedModels(client.models,folder))
    return customer_backend(scratch,{'GEMINI_API_KEY':key},environ={},client_factory=factory)


def render_scene_test(st, writer):
    """Stage-3-only owner control; result is not author manuscript content."""
    receipt=Path.home()/'.cache'/'wbs'/'live-acceptance'/(AUTHORIZATION+'-scene.json')
    used=receipt.exists()
    st.markdown('### Staging Live Scene Test')
    st.caption('One real Gemini scene request only, within the approved combined $1 allowance. No retries. The result is not saved to your chapter. Quill retains its separate one-request allowance.')
    if st.button('Test ONE Real Gemini Scene',key='_staging_live_scene_test',disabled=used):
        try:
            text=writer.execute_recursive_draft_chunk(
                'Write a brief fictional scene: a gardener finds a blue notebook, asks a neighbor about it, and decides to return it. About 120 words. Invented test characters only.',
                'Synthetic staging acceptance only. No real people or historical claims.',
                'Novel / Prose / Novella','Warm and clear')
            if not str(text or '').strip():raise ValueError('Empty scene')
            st.session_state['_staging_live_scene_result']=str(text)
            st.session_state['_staging_live_scene_status']='PASS: real scene response received; chapter text unchanged.'
        except Exception:
            st.session_state['_staging_live_scene_status']='FAIL: scene request did not produce a usable result. No retry was made; chapter text is unchanged.'
        st.rerun()
    if used:
        st.caption('The one scene attempt has been consumed. This control cannot send another request.')
        try:diagnostic=json.loads(receipt.read_text(encoding='utf-8'))
        except (OSError,ValueError):diagnostic={}
        if diagnostic.get('status')=='FAIL':
            # Only controlled numeric status and allowlisted category leave the SDK boundary.
            code=diagnostic.get('http_status')
            if type(code) is int:st.caption('Recorded provider HTTP status: '+str(code))
            category=diagnostic.get('error_category')
            from quill.provider_errors import STATUSES,REASONS
            allowed=STATUSES|REASONS|{'CONNECTION_ERROR','CONNECTION_TIMEOUT','READ_TIMEOUT','CLIENT_ERROR','SERVER_ERROR','REQUEST_GUARD','OTHER_ERROR','NON_JSON_HTTP_ERROR','AUTH_METHOD_UNSUPPORTED','REQUEST_FIELD_INVALID','MODEL_ACCESS_RESTRICTED','FREE_TIER_UNAVAILABLE'}
            if category in allowed:st.caption('Recorded error category: '+category)
        elif '_staging_live_scene_status' in st.session_state and st.session_state['_staging_live_scene_status'].startswith('FAIL'):
            st.caption('The earlier attempt did not retain provider diagnostics; its exact rejection cannot be recovered from this receipt.')
    status=st.session_state.get('_staging_live_scene_status')
    if status:
        if status.startswith('PASS'):
            st.success(status)
            st.text_area('Live Gemini scene test result (not saved to chapter)',value=st.session_state.get('_staging_live_scene_result',''),height=260,disabled=True)
        else:st.error(status)
