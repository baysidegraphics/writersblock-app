"""Single-attempt Quill provider calls with bounded context/output and usage ledger."""
import time
class ProviderFailure(RuntimeError):
    def __init__(self,category,status=None,diagnostics=None):
        self.category=category;self.status=status;self.diagnostics=diagnostics or {}
        super().__init__('Quill writing service: '+category+(' (HTTP '+str(status)+')' if status else '')+'. Your saved writing is unchanged; no automatic retry was made.')

def request(state,question):
    from .modular_context import ai_prompt,scope,fingerprint
    backend=state.get('_wbs_quill_test_backend') if state.get('_wbs_quill_test_mode') else state.get('backend');client=getattr(backend,'client',None);model=getattr(backend,'model_name',None)
    if client is None or not model:raise ProviderFailure('UNAVAILABLE')
    request_scope=scope(state);request_hash=fingerprint(state)
    import hashlib
    from uuid import uuid4
    request_key=hashlib.sha256(repr((request_scope,request_hash,question)).encode()).hexdigest()
    now=time.time();recent=state.get('_wbs_quill_provider_recent') or {}
    if recent.get('key')==request_key and now-recent.get('time',0)<3:return recent['text']
    if state.get('_wbs_quill_provider_active'):raise ProviderFailure('REQUEST_IN_PROGRESS')
    ticket=uuid4().hex
    now=time.time();ledger=list(state.get('_wbs_quill_usage_ledger') or [])
    if sum(r.get('attempted',False) and now-r['time']<3600 for r in ledger)>=60:raise ProviderFailure('SESSION_REQUEST_LIMIT')
    prompt=ai_prompt(state,question)
    if len(prompt)>100000:raise ProviderFailure('INPUT_LIMIT')
    from google.genai import types
    config=types.GenerateContentConfig(max_output_tokens=2048,http_options=types.HttpOptions(timeout=20000,retry_options=types.HttpRetryOptions(attempts=1)))
    row={'time':now,'scope':request_scope,'model':str(model),'attempted':False,'status':'PENDING','input_tokens':0,'output_tokens':0,'thoughts_tokens':0,'total_tokens':0,'usage_reported':False}
    manager=state.get('_wbs_quill_credit_manager');logger=state.get('_wbs_quill_usage_logger');user=scope(state)[0];charge=None
    state['_wbs_quill_provider_active']=ticket
    try:
        if manager is not None and user:
            try:charge=manager.spend(user,'quill_question',project_id=request_scope[1] or None,note='Quill author request')
            except Exception:raise ProviderFailure('CREDIT_UNAVAILABLE') from None
        row['attempted']=True
        response=client.models.generate_content(model=model,contents=prompt,config=config)
        usage=getattr(response,'usage_metadata',None)
        row.update(input_tokens=int(getattr(usage,'prompt_token_count',0) or 0),output_tokens=int(getattr(usage,'candidates_token_count',0) or 0),thoughts_tokens=int(getattr(usage,'thoughts_token_count',0) or 0),total_tokens=int(getattr(usage,'total_token_count',0) or 0),usage_reported=usage is not None)
        if scope(state)!=request_scope or fingerprint(state)!=request_hash:raise ProviderFailure('STALE_PROJECT_RESPONSE')
        text=str(getattr(response,'text','') or '').strip()
        if not text:raise ProviderFailure('EMPTY_RESPONSE')
        row['status']='PASS'
        candidates=getattr(response,'candidates',[]) or []
        if candidates and 'MAX_TOKENS' in str(getattr(candidates[0],'finish_reason','')):
            text+='\n\n[Response reached the request limit. Ask Quill to continue if needed; nothing was applied to your manuscript.]';row['status']='PARTIAL'
        if backend is not None:backend.last_usage={'input_tokens':row['input_tokens'],'output_tokens':row['output_tokens'],'thoughts_tokens':row['thoughts_tokens'],'total_tokens':row['total_tokens'],'usage_reported':row['usage_reported'],'operation':'quill_question','status':row['status']}
        state['_wbs_quill_provider_recent']={'key':request_key,'time':time.time(),'text':text}
        return text
    except Exception as exc:
        status=getattr(exc,'code',None) or getattr(exc,'status_code',None) or getattr(getattr(exc,'response',None),'status_code',None)
        try:status=int(status)
        except (TypeError,ValueError):status=None
        category=exc.category if isinstance(exc,ProviderFailure) else 'AUTHENTICATION' if status in (401,403) else 'QUOTA_OR_RATE_LIMIT' if status==429 else 'BAD_REQUEST' if status==400 else 'PROVIDER_ERROR' if status else 'CONNECTION_OR_PROVIDER_ERROR'
        diagnostics={}
        try:
            from .provider_errors import safe_error_summary
            diagnostics=safe_error_summary(exc)
            response=getattr(exc,'response',None)
            if response is not None:
                content_type=str(response.headers.get('content-type','')).split(';',1)[0].strip().lower()
                diagnostics['response_format']='JSON' if content_type=='application/json' or content_type.endswith('+json') else 'HTML' if content_type=='text/html' else 'OTHER'
        except Exception:pass  # Diagnostics must not mask the safe original failure.
        row.update(status='FAIL',category=category,http_status=status)
        if manager is not None and charge is not None:
            try:manager.refund(user,charge,note='Quill request failed - automatic refund');row['credit_refunded']=True
            except Exception:row['credit_refund_pending']=True
        if backend is not None:backend.last_usage={'input_tokens':row['input_tokens'],'output_tokens':row['output_tokens'],'usage_reported':row['usage_reported'],'operation':'quill_question','status':'FAIL','category':category}
        raise ProviderFailure(category,status,diagnostics) from None
    finally:
        if state.get('_wbs_quill_provider_active')==ticket:state.pop('_wbs_quill_provider_active',None)
        if scope(state)[0]==request_scope[0]:
            ledger=list(state.get('_wbs_quill_usage_ledger') or []);ledger.append(row);state['_wbs_quill_usage_ledger']=ledger[-300:]
        if callable(logger) and scope(state)[0]==request_scope[0]:
            try:logger('quill_question',input_text='',output_text='',note=row['status']+'; '+str(row.get('category',''))+'; input='+str(row['input_tokens'])+'; output='+str(row['output_tokens']))
            except Exception:pass
