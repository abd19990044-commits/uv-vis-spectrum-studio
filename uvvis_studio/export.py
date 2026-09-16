from __future__ import annotations

from io import BytesIO
from PIL import Image
import plotly.graph_objects as go


def figure_png_bytes(fig: go.Figure, width_in: float, height_in: float, dpi: int = 600) -> bytes:
    if dpi < 72:
        raise ValueError("DPI must be at least 72.")
    width_px = max(100, int(round(width_in * dpi)))
    height_px = max(100, int(round(height_in * dpi)))
    raw = fig.to_image(format="png", width=width_px, height=height_px, scale=1)
    im = Image.open(BytesIO(raw))
    out = BytesIO()
    im.save(out, format="PNG", dpi=(dpi, dpi), optimize=True)
    return out.getvalue()


def figure_vector_bytes(fig: go.Figure, fmt: str, width_in: float, height_in: float) -> bytes:
    return fig.to_image(format=fmt, width=int(width_in * 96), height=int(height_in * 96), scale=1)
