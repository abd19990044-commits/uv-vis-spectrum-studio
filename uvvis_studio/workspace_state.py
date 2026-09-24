from __future__ import annotations

from copy import deepcopy
import math

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
    "x_auto", "y_auto", "xmin_disp", "xmax_disp", "ymin_disp", "ymax_disp",
    "pub_fig_w", "pub_fig_h", "pub_fig_dpi", "view_mode_selector",
}

DASH_TO_LABEL = {
    "solid": "Solid",
    "dash": "Dashed",
    "dot": "Dotted",
    "dashdot": "Dash-dot",
    "longdash": "Long dash",
    "longdashdot": "Long dash-dot",
}


def validate_settings(settings: dict) -> None:
    """Validate persisted widget state before constructing Streamlit widgets."""
    bool_keys = {"crop", "x_auto", "y_auto", "auc_enabled", "shade_auc", "bw_mode",
                 "bw_auto", "grid", "legend", "label_peaks"}
    enums = {
        "derivative_order": list(range(5)),
        "smoothing_method": ["None", "Savitzky-Golay", "Moving average", "Gaussian"],
        "baseline_method": ["None", "ALS", "Linear endpoints", "Polynomial edges"],
        "norm": ["None", "Max = 1", "Min-Max 0–1", "Area = 1"],
        "conversion": ["None", "Absorbance → %Transmittance", "%Transmittance → Absorbance"],
        "legendpos": ["Top right", "Top left", "Bottom right", "Bottom left", "Outside right"],
        "font_family": ["Times New Roman", "Arial", "Calibri", "Cambria", "Georgia", "Verdana", "Courier New"],
        "view_mode_selector": ["Standard Spectrum Viewer", "Derivative Comparison (0D vs nD)",
                               "Selected-Range AUC Inspection", "Multi-Spectrum Overlay"],
        "pub_fig_dpi": [150, 300, 600, 1200],
    }
    ranges = {
        "window": (3, 201), "poly": (1, 9), "gaussian_sigma": (.1, 50),
        "blam": (1, math.inf), "bp": (.0001, .5), "baseline_poly_order": (1, 5),
        "baseline_edge_fraction": (.02, .4), "linewidth": (.5, 6), "fontsize": (8, 24),
        "titlesize": (1, 200), "peak_prominence_pct": (0, 100), "peak_distance": (1, math.inf),
        "pub_fig_w": (2, 20), "pub_fig_h": (2, 20),
    }
    integers = {"derivative_order", "window", "poly", "baseline_poly_order",
                "fontsize", "titlesize", "peak_distance", "pub_fig_dpi"}
    numeric = {"xmin", "xmax", "auc_min", "auc_max", "offset", "xmin_disp",
               "xmax_disp", "ymin_disp", "ymax_disp"}
    for key, value in settings.items():
        if key not in PROJECT_WIDGET_KEYS:
            continue
        if key in bool_keys:
            valid = type(value) is bool
        elif key in ranges or key in numeric or key in integers:
            valid = (type(value) in (int, float) and math.isfinite(value)
                     and (key not in integers or type(value) is int))
            if valid and key in ranges:
                lo, hi = ranges[key]
                valid = lo <= value <= hi
        else:
            valid = isinstance(value, str) and len(value) <= 10000
        if valid and key in enums:
            valid = value in enums[key]
        if not valid:
            raise ValueError(f"Invalid project setting: {key}.")


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
    validate_settings(settings)
    for key, value in settings.items():
        if key in PROJECT_WIDGET_KEYS:
            session_state[key] = value
    # These widgets mirror canonical settings; stale widget values must not
    # overwrite the freshly restored project on the next render.
    aliases = {"auc_min": "input_auc_min", "auc_max": "input_auc_max",
               "shade_auc": "auc_shade_toggle", "grid": "lab_grid",
               "legend": "lab_legend", "label_peaks": "lab_label_peaks",
               "bw_mode": "lab_bw_mode"}
    for canonical, widget in aliases.items():
        if canonical in settings:
            session_state[widget] = settings[canonical]
        elif widget in session_state:
            del session_state[widget]
    session_state["_pub_fig_ready"] = False
    if "_pub_fig_signature" in session_state:
        del session_state["_pub_fig_signature"]

    spectra = [deepcopy(spectrum) for spectrum in project.get("spectra", [])]
    session_state["_project_spectra"] = spectra
    session_state["_project_notes"] = str(project.get("notes", ""))

    for i, spectrum in enumerate(spectra):
        session_state[f"project_name_{i}"] = str(spectrum.get("name", f"Spectrum {i + 1}"))
        session_state[f"project_color_{i}"] = str(spectrum.get("color", "#2563EB"))
        dash = str(spectrum.get("dash", "solid"))
        session_state[f"project_style_{i}"] = DASH_TO_LABEL.get(dash, "Solid")


def clear_project_session(session_state) -> None:
    """Close an active project without forcing the file uploader value.

    The current project hash is intentionally retained. This prevents the same
    still-selected uploader file from being immediately re-opened on the next
    Streamlit rerun. A different project file receives a different hash and
    loads normally.
    """
    session_state.pop("_project_spectra", None)
    session_state.pop("_project_notes", None)
    session_state.pop("_project_loaded_message", None)
    for key in list(session_state.keys()):
        if (
            key in PROJECT_WIDGET_KEYS
            or key.startswith("project_name_")
            or key.startswith("project_color_")
            or key.startswith("project_style_")
            or key.startswith("lab_")
            or key.startswith("_pub_fig")
            or key in {"input_auc_min", "input_auc_max", "auc_shade_toggle"}
        ):
            session_state.pop(key, None)

    # Stop execution before main_app attempts to mutate the file_uploader key.
    # Calling rerun here is safe because this function is used by the UI close
    # action; importing this module for scientific tests does not trigger it.
    import streamlit as st
    st.rerun()
