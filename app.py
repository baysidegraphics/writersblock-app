"""Reviewed maintenance entrypoint; no database/provider/payment imports."""
import streamlit as st

st.set_page_config(page_title="WritersBlock Studios — Maintenance", page_icon="📚")
st.title("WritersBlock Studios")
st.info("Scheduled maintenance is in progress. Writing and registration are temporarily unavailable.")
st.stop()
