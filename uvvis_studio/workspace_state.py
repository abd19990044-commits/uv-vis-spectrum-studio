from __future__ import annotations

from copy import deepcopy

PROJECT_WIDGET_KEYS = {
    "derivative_order",
    "crop",
    "xmin",
    "xmax",
    "smoothing_method",
    "window",
    "poly",
    "gaussian_sigma",
    "baseline_method",
    "blam",
    "bp",
    "baseline_poly_order",
    "baseline_edge_fraction",
    "norm",
    "conversion",
    "auc_enabled",
    "auc_min",
    "auc_max",
    "shade_auc",
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
}


def capture_settings(session_state) -> dict:
    """Capture only stable user-facing workspace settings."""
    out = {}
    for key in PROJECT_WIDGET_KEYS:
        if key in session_state:
            value = session_state[key]
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[key] = value
    return out


def restore_project_to_session(session_state, project: dict) -> None:
    """Populate Streamlit session state before widgets are constructed."""
    settings = project.get("settings", {}) or {}
    for key, value in settings.items():
        if key in PROJECT_WIDGET_KEYS:
            session_state[key] = value

    spectra = []
    for spectrum in project.get("spectra", []):
        item = deepcopy(spectrum)
        spectra.append(item)
    session_state["_project_spectra"] = spectra
    session_state["_project_notes"] = str(project.get("notes", ""))

    for i, spectrum in enumerate(spectra):
        session_state[f"project_name_{i}"] = str(spectrum.get("name", f"Spectrum {i + 1}"))
        session_state[f"project_color_{i}"] = str(spectrum.get("color", "#2563EB"))
        session_state[f"project_dash_{i}"] = str(spectrum.get("dash", "solid"))


def clear_project_session(session_state) -> None:
    session_state.pop("_project_spectra", None)
    session_state.pop("_project_notes", None)
    session_state.pop("_loaded_project_token", None)
    for key in list(session_state.keys()):
        if key in PROJECT_WIDGET_KEYS or key.startswith("project_name_") or key.startswith("project_color_") or key.startswith("project_dash_"):
            session_state.pop(key, None)
