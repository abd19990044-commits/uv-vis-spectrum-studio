from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from io import BytesIO
import json
import os
import platform
import sys
import zipfile

import numpy as np

PROJECT_VERSION = 3
PROJECT_FORMAT = "UVVisSpectrumStudioProject"
_REPRO_PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "PyWavelets",
    "plotly",
    "streamlit",
)


def _finite_xy(x, y) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    if x.size != y.size or x.size < 2:
        raise ValueError("Each project spectrum must contain matching X/Y arrays with at least two points.")
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2:
        raise ValueError("A project spectrum contains too few finite points.")
    order = np.argsort(x)
    x, y = x[order], y[order]
    if np.any(np.diff(x) <= 0):
        # Project archives should be deterministic. Average duplicate wavelengths
        # rather than preserving an ambiguous acquisition/export artifact.
        unique, inverse = np.unique(x, return_inverse=True)
        sums = np.bincount(inverse, weights=y)
        counts = np.bincount(inverse)
        x, y = unique, sums / counts
    return x, y


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in _REPRO_PACKAGES:
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def reproducibility_metadata() -> dict:
    """Capture environment provenance useful for scientific reproducibility."""
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "git_commit": os.getenv("UVVIS_GIT_COMMIT") or os.getenv("GITHUB_SHA") or "unknown",
        "executable": os.path.basename(sys.executable),
    }


def project_bytes(
    spectra: list[dict],
    settings: dict | None = None,
    notes: str = "",
    *,
    analyst: str = "",
    instrument: str = "",
    audit_trail: list[dict] | None = None,
) -> bytes:
    """Serialize a reproducible project using raw spectra plus processing settings.

    Raw spectra are intentionally stored separately from processing settings so
    reopening a project recalculates the workspace exactly once rather than
    processing an already processed signal a second time.
    """
    meta = {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "notes": str(notes),
        "analyst": str(analyst),
        "instrument": str(instrument),
        "settings": settings or {},
        "audit_trail": list(audit_trail or []),
        "reproducibility": reproducibility_metadata(),
        "spectra": [],
    }
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as archive:
        for i, spectrum in enumerate(spectra):
            raw_y = spectrum.get("raw_y", spectrum.get("y", spectrum.get("analysis_y", [])))
            x, y = _finite_xy(spectrum.get("x", []), raw_y)
            member = f"spectra/{i:04d}.npz"
            array_bytes = BytesIO()
            np.savez_compressed(array_bytes, x=x, y=y)
            archive.writestr(member, array_bytes.getvalue())
            meta["spectra"].append(
                {
                    "name": str(spectrum.get("name", f"Spectrum {i + 1}")),
                    "color": str(spectrum.get("color", "#2563EB")),
                    "dash": str(spectrum.get("dash", "solid")),
                    "source": str(spectrum.get("source", "project")),
                    "column": str(spectrum.get("column", "signal")),
                    "source_sha256": str(spectrum.get("source_sha256", "")),
                    "file": member,
                }
            )
        archive.writestr("project.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return bio.getvalue()


def load_project(data: bytes) -> dict:
    try:
        archive = zipfile.ZipFile(BytesIO(data), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("The selected file is not a valid UV-Vis Spectrum Studio project.") from exc

    with archive as z:
        names = set(z.namelist())
        if "project.json" not in names:
            raise ValueError("The project archive does not contain project.json.")
        try:
            meta = json.loads(z.read("project.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("project.json is not valid UTF-8 JSON.") from exc
        if meta.get("format") != PROJECT_FORMAT:
            raise ValueError("Not a UV-Vis Spectrum Studio project file.")
        version = int(meta.get("version", 1))
        if version > PROJECT_VERSION:
            raise ValueError(
                f"This project was created by a newer project format (v{version}); "
                f"this application supports up to v{PROJECT_VERSION}."
            )

        spectra = []
        for item in meta.get("spectra", []):
            member = item.get("file")
            if not member or member not in names:
                raise ValueError("A spectrum referenced by project.json is missing from the project archive.")
            with np.load(BytesIO(z.read(member)), allow_pickle=False) as arr:
                if "x" not in arr or "y" not in arr:
                    raise ValueError("A project spectrum does not contain x/y arrays.")
                x, y = _finite_xy(arr["x"], arr["y"])
            spectra.append(
                {
                    "name": item.get("name", "Spectrum"),
                    "x": x,
                    "y": y,
                    "raw_y": y.copy(),
                    "analysis_y": y.copy(),
                    "plot_y": y.copy(),
                    "color": item.get("color", "#2563EB"),
                    "dash": item.get("dash", "solid"),
                    "source": item.get("source", "project"),
                    "column": item.get("column", "signal"),
                    "source_sha256": item.get("source_sha256", ""),
                }
            )

        return {
            "metadata": meta,
            "spectra": spectra,
            "settings": meta.get("settings", {}),
            "notes": meta.get("notes", ""),
            "audit_trail": meta.get("audit_trail", []),
            "reproducibility": meta.get("reproducibility", {}),
            "analyst": meta.get("analyst", ""),
            "instrument": meta.get("instrument", ""),
        }
