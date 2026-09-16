from __future__ import annotations

from io import BytesIO
import json
import zipfile
from datetime import datetime, timezone

import numpy as np

PROJECT_VERSION = 2
PROJECT_FORMAT = "UVVisSpectrumStudioProject"


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
    return x[order], y[order]


def project_bytes(spectra: list[dict], settings: dict | None = None, notes: str = "") -> bytes:
    """Serialize a reproducible project.

    The project deliberately stores the *raw* spectrum in ``y`` whenever it is
    available. Processing parameters are stored separately in ``settings`` so
    reopening a project recalculates processing exactly once instead of
    processing an already processed signal a second time.
    """
    meta = {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "notes": str(notes),
        "settings": settings or {},
        "spectra": [],
    }
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for i, spectrum in enumerate(spectra):
            raw_y = spectrum.get("raw_y", spectrum.get("y", spectrum.get("analysis_y", [])))
            x, y = _finite_xy(spectrum.get("x", []), raw_y)
            name = f"spectra/{i:04d}.npz"
            arr = BytesIO()
            np.savez_compressed(arr, x=x, y=y)
            z.writestr(name, arr.getvalue())
            meta["spectra"].append(
                {
                    "name": str(spectrum.get("name", f"Spectrum {i + 1}")),
                    "color": str(spectrum.get("color", "#2563EB")),
                    "dash": str(spectrum.get("dash", "solid")),
                    "source": str(spectrum.get("source", "project")),
                    "column": str(spectrum.get("column", "signal")),
                    "file": name,
                }
            )
        z.writestr("project.json", json.dumps(meta, ensure_ascii=False, indent=2))
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
        meta = json.loads(z.read("project.json").decode("utf-8"))
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
            with np.load(BytesIO(z.read(member))) as arr:
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
                }
            )

        return {
            "metadata": meta,
            "spectra": spectra,
            "settings": meta.get("settings", {}),
            "notes": meta.get("notes", ""),
        }
