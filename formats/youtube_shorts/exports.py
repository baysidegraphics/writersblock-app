"""Format-owned structured exports using the existing output style base."""
from core.manuscript_structure import export_docx,export_text
from . import FORMAT_ID

def _checked(snapshot):
    if snapshot.get("active_format_id")!=FORMAT_ID:raise ValueError("Cross-format export refused")

def build_docx(snapshot,base_bytes=None):
    _checked(snapshot)
    return export_docx(snapshot,base_bytes)

def build_text(snapshot):
    _checked(snapshot)
    return export_text(snapshot)
