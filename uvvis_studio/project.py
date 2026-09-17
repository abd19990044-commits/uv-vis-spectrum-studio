from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from importlib import metadata as importlib_metadata
from io import BytesIO
import json
import os
import platform
import sys
import zipfile

import numpy as np

from . import __version__

PROJECT_VERSION = 4
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


def _embedded_git_commit() -> str:
    try:
        from .build_info import GIT_COMMIT

        if GIT_COMMIT and GIT_COMMIT != "unknown":
            return str(GIT_COMMIT)
    except Exception:
        pass
    return os.getenv("UVVIS_GIT_COMMIT") or os.getenv("GITHUB_SHA") or "unknown"


def reproducibility_metadata() -> dict:
    """Capture environment provenance useful for scientific reproducibility."""
    return {
        "application": "UV-Vis Spectrum Studio",
        "application_version": __version__,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "git_commit": _embedded_git_commit(),
        "executable": os.path.basename(sys.executable),
    }


def processing_audit_from_settings(settings: dict | None) -> list[dict]:
    """Create a deterministic, human-readable processing trail from workspace settings."""
    settings = dict(settings or {})
    trail: list[dict] = [{"step": 0, "operation": "raw_data", "parameters": {}}]
    operations = [
        (
            "crop",
            bool(settings.get("crop", False)),
            {"xmin_nm": settings.get("xmin"), "xmax_nm": settings.get("xmax")},
        ),
        (
            "signal_conversion",
            settings.get("conversion") not in {None, "", "None"},
            {"mode": settings.get("conversion")},
        ),
        (
            "smoothing",
            settings.get("smoothing_method") not in {None, "", "None"},
            {
                "method": settings.get("smoothing_method"),
                "window_points": settings.get("window"),
                "polyorder": settings.get("poly"),
                "gaussian_sigma_points": settings.get("gaussian_sigma"),
            },
        ),
        (
            "baseline_correction",
            settings.get("baseline_method") not in {None, "", "None"},
            {
                "method": settings.get("baseline_method"),
                "als_lambda": settings.get("blam"),
                "als_p": settings.get("bp"),
                "polynomial_order": settings.get("baseline_poly_order"),
                "edge_fraction": settings.get("baseline_edge_fraction"),
            },
        ),
        (
            "normalization",
            settings.get("norm") not in {None, "", "None"},
            {"mode": settings.get("norm")},
        ),
        (
            "derivative",
            int(settings.get("derivative_order", 0) or 0) > 0,
            {
                "order": int(settings.get("derivative_order", 0) or 0),
                "window_points": settings.get("window"),
                "requested_polyorder": settings.get("poly"),
            },
        ),
        (
            "manual_auc",
            bool(settings.get("auc_enabled", False)),
            {"from_nm": settings.get("auc_min"), "to_nm": settings.get("auc_max")},
        ),
    ]
    step = 1
    for operation, enabled, parameters in operations:
        if enabled:
            clean_parameters = {key: value for key, value in parameters.items() if value is not None}
            trail.append({"step": step, "operation": operation, "parameters": clean_parameters})
            step += 1
    trail.append(
        {
            "step": step,
            "operation": "figure_configuration",
            "parameters": {
                key: settings.get(key)
                for key in (
                    "title",
                    "xtitle",
                    "ytitle",
                    "bw_mode",
                    "bw_auto",
                    "font_family",
                    "linewidth",
                    "fontsize",
                    "titlesize",
                    "grid",
                    "legend",
                    "legendpos",
                    "label_peaks",
                    "peak_prominence_pct",
                    "peak_distance",
                    "offset",
                )
                if key in settings
            },
        }
    )
    return trail


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _manifest_bytes(members: dict[str, bytes]) -> bytes:
    manifest = {
        "algorithm": "SHA-256",
        "members": {name: _hash_bytes(data) for name, data in sorted(members.items())},
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _verify_manifest(archive: zipfile.ZipFile, names: set[str], *, required: bool) -> dict:
    if "manifest.json" not in names:
        if required:
            raise ValueError("Project integrity manifest is missing.")
        return {"verified": False, "reason": "legacy project without manifest"}
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Project integrity manifest is invalid.") from exc
    if manifest.get("algorithm") != "SHA-256":
        raise ValueError("Unsupported project integrity algorithm.")
    members = manifest.get("members")
    if not isinstance(members, dict) or not members:
        raise ValueError("Project integrity manifest contains no member hashes.")
    for member, expected in members.items():
        if member == "manifest.json":
            raise ValueError("Integrity manifest must not hash itself.")
        if member not in names:
            raise ValueError(f"Integrity check failed: {member} is missing.")
        actual = _hash_bytes(archive.read(member))
        if actual.lower() != str(expected).lower():
            raise ValueError(f"Integrity check failed for {member}; the project may have been modified or corrupted.")
    return {"verified": True, "algorithm": "SHA-256", "members": len(members)}


def project_bytes(
    spectra: list[dict],
    settings: dict | None = None,
    notes: str = "",
    *,
    analyst: str = "",
    instrument: str = "",
    audit_trail: list[dict] | None = None,
) -> bytes:
    """Serialize a reproducible, tamper-evident project archive.

    Raw spectra are stored separately from processing settings so reopening a
    project recalculates processing exactly once.  Version 4 adds a SHA-256
    manifest over ``project.json`` and every stored spectrum.  This makes silent
    post-hoc modification detectable; it is not a substitute for a regulated
    electronic signature or a validated LIMS audit-trail system.
    """
    settings = dict(settings or {})
    trail = list(audit_trail) if audit_trail is not None else processing_audit_from_settings(settings)
    created = datetime.now(timezone.utc).isoformat()
    meta = {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "created_utc": created,
        "notes": str(notes),
        "analyst": str(analyst),
        "instrument": str(instrument),
        "settings": settings,
        "audit_trail": trail,
        "reproducibility": reproducibility_metadata(),
        "integrity": {"algorithm": "SHA-256", "manifest": "manifest.json"},
        "spectra": [],
    }
    members: dict[str, bytes] = {}
    for index, spectrum in enumerate(spectra):
        raw_y = spectrum.get("raw_y", spectrum.get("y", spectrum.get("analysis_y", [])))
        x, y = _finite_xy(spectrum.get("x", []), raw_y)
        member = f"spectra/{index:04d}.npz"
        array_bytes = BytesIO()
        np.savez_compressed(array_bytes, x=x, y=y)
        payload = array_bytes.getvalue()
        members[member] = payload
        meta["spectra"].append(
            {
                "name": str(spectrum.get("name", f"Spectrum {index + 1}")),
                "color": str(spectrum.get("color", "#2563EB")),
                "dash": str(spectrum.get("dash", "solid")),
                "source": str(spectrum.get("source", "project")),
                "column": str(spectrum.get("column", "signal")),
                "source_sha256": str(spectrum.get("source_sha256", "")),
                "stored_sha256": _hash_bytes(payload),
                "file": member,
            }
        )
    project_json = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
    members["project.json"] = project_json
    manifest = _manifest_bytes(members)

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        archive.writestr("manifest.json", manifest)
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
        integrity = _verify_manifest(z, names, required=version >= 4)

        spectra = []
        for item in meta.get("spectra", []):
            member = item.get("file")
            if not member or member not in names:
                raise ValueError("A spectrum referenced by project.json is missing from the project archive.")
            payload = z.read(member)
            stored_hash = item.get("stored_sha256")
            if stored_hash and _hash_bytes(payload).lower() != str(stored_hash).lower():
                raise ValueError(f"Stored spectrum hash does not match for {member}.")
            with np.load(BytesIO(payload), allow_pickle=False) as arr:
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
            "integrity": integrity,
        }
