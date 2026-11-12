"""Private Streamlit deployment entrypoint; no synthetic UI or credential discovery."""
import os, runpy
from pathlib import Path
from urllib.parse import urlsplit
import streamlit as st


def setting(name):
    try:
        return str(st.secrets.get(name, '') or '')
    except Exception:
        return ''


def stop(message):
    st.error(message)
    st.stop()


if setting('WBS_STAGING_ISOLATION_CONFIRMED') != 'synthetic-only':
    stop('Private staging requires a separately verified synthetic-only database. No connection was attempted.')
ref=setting('WBS_STAGING_SUPABASE_PROJECT_REF')
url=setting('SUPABASE_URL')
parsed=urlsplit(url)
if not ref or parsed.scheme!='https' or parsed.hostname != ref+'.supabase.co' or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
    stop('Configure the verified synthetic Supabase project reference and matching HTTPS endpoint.')
# Never accept payment/commission credentials in this separate staging deployment.
for name in ('AFFITOR_API_KEY','STRIPE_SECRET_KEY','STRIPE_API_KEY','STRIPE_WEBHOOK_SECRET','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SERVICE_KEY'):
    if setting(name) or os.getenv(name):
        stop('Remove privileged database or payment credentials from private staging.')
from core.authentication import public_client_key
try:
    public_client_key(setting('SUPABASE_KEY'))
except Exception:
    stop('Private staging requires its own publishable or anon Supabase key.')
# No live model request is authorized by preparing or deploying this source.
if (setting('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')) and setting('WBS_STAGING_AI_AUTHORIZED')!='explicit-owner-approval':
    stop('Live AI credentials require separate owner authorization in this staging app.')
runpy.run_path(str(Path(__file__).with_name('app.py')),run_name='__main__')
