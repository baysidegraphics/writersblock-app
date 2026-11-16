"""Disconnected private owner-acceptance screen; staging only.

No Secrets, credentials, database clients, AI clients or commercial app execution.
The verified 314-file commercial application remains unchanged beside this loader.
"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="WBS R2 — Owner Acceptance", page_icon="📚")
st.title("WritersBlock Studios")
st.subheader("R2 — Private Owner Acceptance")
st.success("The staging startup screen is ready.")
st.info("Database access is not enabled. No database connection has been attempted.")
st.write(
    "Your commercial application files remain unchanged. Registration, account linking, "
    "manuscript access, saving and AI requests remain unavailable until database access "
    "is separately approved and configured."
)
if not Path(__file__).resolve().with_name("app.py").is_file():
    st.error("The commercial entrypoint is missing. Do not proceed with acceptance.")
st.caption("This is a disconnected readiness screen, not the running writing application.")
st.stop()
