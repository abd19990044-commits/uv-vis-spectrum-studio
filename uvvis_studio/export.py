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


def _system_browser() -> Path | None:
    """Return a compatible system browser when one is discoverable on PATH.

    This is particularly important for Linux ARM64 builds, for which Kaleido's
    Chrome-for-Testing downloader does not currently provide the same bundled
    browser path used by the x86_64 release workflow. It also makes source and
    distro-package installations more robust without hard-coding one OS path.
    """
    executable_names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "msedge",
        "microsoft-edge",
    )
    for name in executable_names:
        resolved = shutil.which(name)
        if resolved:
            path = Path(resolved).resolve()
            if path.is_file():
                return path
    return None


def _standard_installed_browser() -> Path | None:
    """Check standard operating system installation directories for Chrome, Edge, or Brave.

    On Windows, Chrome and Edge are installed in Program Files or LocalAppData and are
    typically not included on system PATH. Checking these standard locations ensures
    flawless raster and vector figure export without requiring manual BROWSER_PATH setup.
    """
    candidates: list[Path] = []
    if sys.platform.startswith("win"):
        prog_files = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        local_app = os.environ.get("LocalAppData", "")
        for pf in prog_files:
            if pf:
                candidates.append(Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe")
                candidates.append(Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
                candidates.append(Path(pf) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe")
        if local_app:
            candidates.append(Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe")
            candidates.append(Path(local_app) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
            pw_path = Path(local_app) / "ms-playwright"
            if pw_path.is_dir():
                try:
                    candidates.extend(pw_path.glob("**/chrome.exe"))
                except OSError:
                    pass
    elif sys.platform == "darwin":
        candidates.extend([
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ])
    else:  # Linux / Unix
        candidates.extend([
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
            Path("/usr/bin/microsoft-edge"),
        ])

    for c in candidates:
        try:
            if c.is_file():
                return c.resolve()
        except OSError:
            continue
    return None


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
        cache_base.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="uvvis-browser-", dir=str(cache_base.parent)))
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(tmp)
            if cache_base.exists():
                shutil.rmtree(cache_base, ignore_errors=True)
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
    """Configure Kaleido/Choreographer to use an available compatible browser.

    Preference order is an explicit ``BROWSER_PATH``, a browser bundled with the
    desktop release, the lazily extracted macOS browser archive, a compatible
    browser installed on the host and discoverable on ``PATH``, and finally standard
    system installation directories.
    """
    existing = os.environ.get("BROWSER_PATH")
    if existing:
        path = Path(existing).expanduser()
        if path.is_file():
            resolved = str(path.resolve())
            os.environ["BROWSER_PATH"] = resolved
            return resolved

    for root in _runtime_roots():
        for candidate in _candidate_browsers(root):
            if candidate.is_file():
                resolved = str(candidate.resolve())
                os.environ["BROWSER_PATH"] = resolved
                return resolved

        archive = root / "vendor" / "chrome" / "chrome-macos.zip"
        browser = _extract_macos_browser_archive(archive)
        if browser is not None:
            resolved = str(browser.resolve())
            os.environ["BROWSER_PATH"] = resolved
            return resolved

    browser = _system_browser()
    if browser is not None:
        resolved = str(browser)
        os.environ["BROWSER_PATH"] = resolved
        return resolved

    installed_browser = _standard_installed_browser()
    if installed_browser is not None:
        resolved = str(installed_browser)
        os.environ["BROWSER_PATH"] = resolved
        return resolved

    return None


def _to_image(fig: go.Figure, *, fmt: str, width: float, height: float, scale: float = 1) -> bytes:
    browser = configure_publication_browser()
    try:
        return fig.to_image(format=fmt, width=width, height=height, scale=scale)
    except Exception as exc:
        details = f" (detected browser: {browser})" if browser else " (no browser executable located)"
        raise RuntimeError(
            f"Publication image export failed{details}: {exc}. "
            "Please ensure a compatible Chrome, Edge, or Chromium browser is installed or set BROWSER_PATH."
        ) from exc


def figure_png_bytes(fig: go.Figure, width_in: float, height_in: float, dpi: int = 600) -> bytes:
    import math
    if not all(math.isfinite(v) and v > 0 for v in (width_in, height_in, dpi)):
        raise ValueError("Figure dimensions and DPI must be positive finite numbers.")
    if not 72 <= dpi <= 1200:
        raise ValueError("DPI must be between 72 and 1200.")
    width_px = max(100, int(round(width_in * dpi)))
    height_px = max(100, int(round(height_in * dpi)))
    if width_px * height_px > 40_000_000:
        raise ValueError("Raster export exceeds 40 megapixels. Reduce dimensions or DPI.")
    # Match the SVG/PDF layout; DPI scales text and strokes as well as pixels.
    raw = _to_image(fig, fmt="png", width=width_in * 96, height=height_in * 96, scale=dpi / 96)
    im = Image.open(BytesIO(raw), formats=["PNG"])
    out = BytesIO()
    im.save(out, format="PNG", dpi=(dpi, dpi), optimize=True)
    return out.getvalue()


def figure_vector_bytes(fig: go.Figure, fmt: str, width_in: float, height_in: float) -> bytes:
    import math
    if not all(math.isfinite(v) and 0 < v <= 40 for v in (width_in, height_in)):
        raise ValueError("Vector figure dimensions must be between 0 and 40 inches.")
    fmt = str(fmt).lower()
    if fmt not in {"svg", "pdf"}:
        raise ValueError("Vector export format must be SVG or PDF.")
    return _to_image(fig, fmt=fmt, width=int(width_in * 96), height=int(height_in * 96))
