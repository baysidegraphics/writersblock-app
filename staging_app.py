"""Staging-only entrypoint for the existing owner acceptance app.

Delegates to the unchanged commercial app. No synthetic clients or responses.
Publish only after Streamlit sharing is verified owner-only and deployment approved.
Exclude this loader from the final production promotion.
"""
from pathlib import Path
import runpy

import streamlit as st

if st.secrets.get("WBS_OWNER_ACCEPTANCE_ENABLED", False) is not True:
    st.error("Owner acceptance is not enabled. No application connection was attempted.")
    st.stop()

runpy.run_path(str(Path(__file__).resolve().with_name("app.py")), run_name="__main__")
