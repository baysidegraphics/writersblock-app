"""Existing private staging entrypoint; run the unchanged R2 commercial app.

Access is controlled by the verified Streamlit private-app sharing restriction.
This loader adds no Secrets flag, synthetic backend or authentication bypass.
Exclude it from the final production promotion.
"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("app.py")), run_name="__main__")
