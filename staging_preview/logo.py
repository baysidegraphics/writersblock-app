"""Staging-only embedded delivery of the existing Quill owl image."""
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image
from quill import wbs_quill_streamlit_ui as ui

_original = ui._render_quill_logo


def render(st, *, width):
    class EmbeddedTarget:
        def image(self, image, **kwargs):
            if isinstance(image, (str, Path)):
                with Image.open(image) as source:
                    output = source.copy()
            else:
                output = image
            buffer = BytesIO()
            output.save(buffer, format='PNG')
            encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
            st.markdown(
                '<img alt="Quill owl" src="data:image/png;base64,' + encoded
                + '" style="width:' + str(int(width))
                + 'px;max-width:100%;height:auto">', unsafe_allow_html=True)

        def __getattr__(self, name):
            return getattr(st, name)

    # Keep the established source selection and transparent-background handling.
    _original(EmbeddedTarget(), width=width)
