from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from PIL import Image
import plotly.graph_objects as go


def _runtime_roots() -> list[Path]:
    """Return plausible roots for source and PyInstaller deployments."""
    roots: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.extend([Path(__file__).resolve().parent.parent, Path.cwd()])

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _candidate_browsers(root: Path) -> list[Path]:
    return [
        root / "vendor" / "chrome" / "chrome.exe",
        root / "vendor" / "chrome" / "chrome",
        root / "vendor" / "chrome" / "chrome-linux64" / "chrome",
        root / "vendor" / "chrome" / "Google Chrome for Testing.app" / "Contents" / "MacOS" / "Google Chrome for Testing",
        root / "vendor" / "chrome" / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome",
    ]


def _extract_macos_browser_archive(archive: Path) -> Path | None:
    """Extract the opaque macOS Chrome ZIP outside the PyInstaller bundle.

    Keeping the .app bundle inside a ZIP avoids PyInstaller treating Chrome's
    nested frameworks as application frameworks during its own bundle analysis.
    The archive is expanded only when publication export is first requested.
    """
    if not archive.is_file():
        return None

    cache_base = Path.home() / ".uvvis-spectrum-studio" / "browser"
    marker = cache_base / ".source-size"
    expected_marker = str(archive.stat().st_size)
    needs_extract = not cache_base.exists() or not marker.exists() or marker.read_text(errors="ignore") != expected_marker
    if needs_extract:
        tmp = Path(tempfile.mkdtemp(prefix="uvvis-browser-", dir=str(cache_base.parent) if cache_base.parent.exists() else None))
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(tmp)
            if cache_base.exists():
                shutil.rmtree(cache_base, ignore_errors=True)
            cache_base.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), str(cache_base))
            marker.write_text(expected_marker, encoding="utf-8")
        finally:
            if tmp.exists() and tmp != cache_base:
                shutil.rmtree(tmp, ignore_errors=True)

    candidates = list(cache_base.rglob("*.app/Contents/MacOS/*"))
    preferred = [p for p in candidates if "chrome" in p.name.lower()]
    for path in preferred + candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def configure_publication_browser() -> str | None:
    """Configure Kaleido/Choreographer to use a bundled browser when present.

    Windows and Linux x86_64 packages can carry an unpacked Chrome-for-Testing
    directory. macOS carries Chrome as an opaque ZIP to avoid PyInstaller
    framework-bundle collisions. Linux ARM64 intentionally relies on a locally
    installed compatible Chromium/Chrome because Chrome-for-Testing does not
    currently provide a linux-arm64 download through Kaleido.
    """
    existing = os.environ.get("BROWSER_PATH")
    if existing and Path(existing).is_file():
        return existing

    for root in _runtime_roots():
        for candidate in _candidate_browsers(root):
            if candidate.is_file():
                os.environ["BROWSER_PATH"] = str(candidate)
                return str(candidate)

        archive = root / "vendor" / "chrome" / "chrome-macos.zip"
        browser = _extract_macos_browser_archive(archive)
        if browser is not None:
            os.environ["BROWSER_PATH"] = str(browser)
            return str(browser)
    return None


def _to_image(fig: go.Figure, *, fmt: str, width: int, height: int) -> bytes:
    configure_publication_browser()
    try:
        return fig.to_image(format=fmt, width=width, height=height, scale=1)
    except Exception as exc:
        raise RuntimeError(
            "Publication image export requires a compatible Chrome/Chromium browser for Kaleido. "
            "Windows and Linux x86_64 release bundles include one; macOS releases extract their bundled browser "
            "on first export. On Linux ARM64, install a compatible Chromium/Chrome build and, if auto-detection "
            "does not find it, set the BROWSER_PATH environment variable to the browser executable."
        ) from exc


def figure_png_bytes(fig: go.Figure, width_in: float, height_in: float, dpi: int = 600) -> bytes:
    if dpi < 72:
        raise ValueError("DPI must be at least 72.")
    width_px = max(100, int(round(width_in * dpi)))
    height_px = max(100, int(round(height_in * dpi)))
    raw = _to_image(fig, fmt="png", width=width_px, height=height_px)
    im = Image.open(BytesIO(raw))
    out = BytesIO()
    im.save(out, format="PNG", dpi=(dpi, dpi), optimize=True)
    return out.getvalue()


def figure_vector_bytes(fig: go.Figure, fmt: str, width_in: float, height_in: float) -> bytes:
    fmt = str(fmt).lower()
    if fmt not in {"svg", "pdf"}:
        raise ValueError("Vector export format must be SVG or PDF.")
    return _to_image(fig, fmt=fmt, width=int(width_in * 96), height=int(height_in * 96))
