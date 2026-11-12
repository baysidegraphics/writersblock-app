"""Staging-only Kokoro categories. No text, paths, keys or exception messages logged."""
import logging
import re
from unittest.mock import patch
import requests
import streamlit as st
from quill import wbs_quill_streamlit_ui as ui
_synthesize = ui._generate_quill_voice
_resolve = ui._resolve_kokoro_server_files
_get = requests.get
_logger = logging.getLogger('wbs.staging.kokoro')

_OLD = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
_APPROVED = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
_URLS = {_OLD + name: _APPROVED + name for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin')}

def approved_get(url, *args, **kwargs):
    return _get(_URLS.get(url, url), *args, **kwargs)

def resolve_original_assets():
    # Preserve original checksums, atomic cache writes, lock and voices.
    with patch('requests.get', approved_get):
        return _resolve()

def synthesize(text, gender):
    try:
        return _synthesize(text, gender)
    except Exception as error:
        chain, seen = [], set()
        current, status, phase = error, None, 'synthesis'
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            name = type(current).__name__
            chain.append(name if re.fullmatch(r'[A-Za-z_]{1,60}', name) else 'UnknownError')
            response = getattr(current, 'response', None)
            value = getattr(response, 'status_code', None)
            if isinstance(value, int) and 100 <= value <= 599:
                status = value
            tb = current.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code.co_name in ('fetch', '_resolve_kokoro_server_files'):
                    phase = 'asset_load'
                tb = tb.tb_next
            current = current.__cause__ or current.__context__
        event = 'phase=' + phase + ' category=' + '/'.join(chain[:5]) + ' http=' + str(status)
        _logger.error('WBS_KOKORO_DIAGNOSTIC %s', event)
        st.caption('Kokoro staging diagnostic: ' + event)
        raise
