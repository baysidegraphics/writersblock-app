"""Staging-only Kokoro categories. No text, paths, keys or exception messages logged."""
import logging
import re
import streamlit as st
from quill import wbs_quill_streamlit_ui as ui
_synthesize = ui._generate_quill_voice
_logger = logging.getLogger('wbs.staging.kokoro')

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
