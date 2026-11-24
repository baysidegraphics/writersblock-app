"""Allowlisted provider diagnostics only: never return messages, bodies or keys."""
STATUSES=frozenset({'INVALID_ARGUMENT','UNAUTHENTICATED','PERMISSION_DENIED','NOT_FOUND',
    'RESOURCE_EXHAUSTED','FAILED_PRECONDITION','UNAVAILABLE','INTERNAL'})
REASONS=frozenset({'API_KEY_INVALID','API_KEY_EXPIRED','API_KEY_SERVICE_BLOCKED',
    'API_KEY_HTTP_REFERRER_BLOCKED','API_KEY_IP_ADDRESS_BLOCKED','API_KEY_ANDROID_APP_BLOCKED',
    'API_KEY_IOS_APP_BLOCKED','SERVICE_DISABLED','BILLING_DISABLED','CONSUMER_INVALID',
    'RATE_LIMIT_EXCEEDED','QUOTA_EXCEEDED','MODEL_NOT_FOUND'})

def safe_error_summary(error):
    code=getattr(error,'code',None)
    if type(code) is not int or not 100<=code<=599:
        code=getattr(getattr(error,'response',None),'status_code',None)
    if type(code) is not int or not 100<=code<=599:code=None
    category={'ConnectError':'CONNECTION_ERROR','ConnectTimeout':'CONNECTION_TIMEOUT',
      'ReadTimeout':'READ_TIMEOUT','ClientError':'CLIENT_ERROR','ServerError':'SERVER_ERROR',
      'PermissionError':'REQUEST_GUARD'}.get(type(error).__name__,'OTHER_ERROR')
    status=getattr(error,'status',None)
    if isinstance(status,str) and status in STATUSES:category=status
    details=getattr(error,'details',None)
    if isinstance(details,list) and len(details)==1:details=details[0]
    envelope=details.get('error',details) if isinstance(details,dict) else {}
    if not isinstance(envelope,dict):envelope={}
    if code is None and type(envelope.get('code')) is int and 100<=envelope['code']<=599:code=envelope['code']
    if isinstance(envelope.get('status'),str) and envelope['status'] in STATUSES:category=envelope['status']
    candidates=[envelope]
    if isinstance(envelope.get('details'),list):candidates+=envelope['details']
    for row in candidates:
        if isinstance(row,dict) and isinstance(row.get('reason'),str) and row['reason'] in REASONS:
            return {'http_status':code,'error_category':row['reason']}
    # Classify a few fixed phrases; the text itself NEVER leaves this function.
    text=envelope.get('message') or getattr(error,'message','')
    if isinstance(text,str):
        lowered=text.lower()
        if 'api key not valid' in lowered or 'api key is invalid' in lowered:category='API_KEY_INVALID'
        elif 'api key has expired' in lowered:category='API_KEY_EXPIRED'
        elif 'api keys are not supported' in lowered:category='AUTH_METHOD_UNSUPPORTED'
        elif 'unknown name "thinking_budget"' in lowered:category='REQUEST_FIELD_INVALID'
        elif 'no longer available to new users' in lowered:category='MODEL_ACCESS_RESTRICTED'
        elif 'unknown name ' in lowered or 'invalid json payload' in lowered:category='REQUEST_FIELD_INVALID'
        elif 'free tier is not available in your country' in lowered:category='FREE_TIER_UNAVAILABLE'
    # The SDK also wraps non-JSON gateway responses as ClientError. Classify
    # their shape without returning any body, URL, headers or credential text.
    if category in ('CLIENT_ERROR','SERVER_ERROR','OTHER_ERROR'):
        response=getattr(error,'response',None)
        if response is not None:
            try:
                payload=response.json()
            except (ValueError, UnicodeError):
                category='NON_JSON_HTTP_ERROR'
            except Exception:
                pass  # An unread/closed response must never mask the original error.
            else:
                if isinstance(payload,dict):
                    nested=payload.get('error')
                    if isinstance(nested,dict) and isinstance(nested.get('status'),str) and nested['status'] in STATUSES:
                        category=nested['status']
    return {'http_status':code,'error_category':category}
